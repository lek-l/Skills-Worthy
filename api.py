import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

import requests

from config import (
    JSEARCH_API_KEY,
    JSEARCH_BASE_URL,
    JSEARCH_HOST,
    JSEARCH_PAGES,
    JSEARCH_TIMEOUT
)

logger = logging.getLogger(__name__)

#headers built once, reused across every request
_HEADERS = {
    "X-RapidAPI-Key": JSEARCH_API_KEY,
    "X-RapidAPI-Host": JSEARCH_HOST
}


class FetchError(Enum):
    #named reasons a single page fetch failed — surfaces in logs and tests instead of anonymous sentinels
    TIMED_OUT = "timed_out"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILED = "auth_failed"
    NETWORK = "network"


class JobFetchError(Exception):
    #raised when job fetching fails in a way the caller needs to handle differently
    pass


class PartialFetchError(Exception):
    #raised when some pages succeeded and others failed
    #the jobs attribute carries the usable results so the caller can still render them
    #deliberately an exception so @st.cache_data does not cache partial results
    def __init__(self, jobs: list, failed: int, total: int):
        self.jobs = jobs
        self.failed = failed
        self.total = total
        super().__init__(f"{failed} of {total} pages failed")


#messages for the all-failures-of-one-kind cases — kept next to FetchError for easy pairing
_ALL_FAILED_MESSAGES = {
    FetchError.RATE_LIMITED: "the job search is temporarily rate-limited. try again in a minute.",
    FetchError.AUTH_FAILED: "the job search is not authorized — the jsearch api key is invalid or revoked.",
    FetchError.TIMED_OUT: "the job search is taking too long right now. try again in a moment.",
    FetchError.NETWORK: "could not reach the job search right now — check your connection.",
}


def _fetch_single_page(query: str, page: int) -> list:
    #legacy wrapper: returns empty list on any failure
    #kept so direct callers (and the TestFetchSinglePage tests) don't have to care about FetchError
    result = _fetch_page(query, page)
    return result if isinstance(result, list) else []


def _fetch_page(query: str, page: int):
    #fetches one page of job results — designed to run in parallel
    #returns a list on success (possibly empty = zero real results), or a FetchError member on failure
    params = {
        "query": query,
        "num_pages": "1",
        "page": str(page)
    }
    try:
        response = requests.get(
            JSEARCH_BASE_URL,
            headers=_HEADERS,
            params=params,
            timeout=JSEARCH_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])

    except requests.exceptions.Timeout:
        logger.warning("timeout on page %d for query '%s'", page, query)
        return FetchError.TIMED_OUT

    except requests.exceptions.HTTPError as e:
        #distinguish rate limits and auth failures so the user sees the right message
        status = getattr(e.response, "status_code", None)
        if status == 429:
            logger.warning("rate limited on page %d for query '%s'", page, query)
            return FetchError.RATE_LIMITED
        if status in (401, 403):
            logger.error("auth failed on page %d (status %s)", page, status)
            return FetchError.AUTH_FAILED
        logger.error("http error on page %d: %s", page, e)
        return FetchError.NETWORK

    except ValueError as e:
        #catches json.JSONDecodeError on old requests versions where it is not a RequestException
        logger.error("decode error on page %d: %s", page, e)
        return FetchError.NETWORK

    except requests.exceptions.RequestException as e:
        #catch-all for network level failures (dns, connection reset, ssl, etc.)
        logger.error("network error on page %d: %s", page, e)
        return FetchError.NETWORK


def fetch_jobs(query: str) -> list:
    #fetches all pages in parallel — significantly faster than sequential fetching
    #raises JobFetchError if api key is missing or all pages fail with the same reason
    #raises PartialFetchError if some pages fail so a thin result is not cached
    if not JSEARCH_API_KEY:
        raise JobFetchError("jsearch api key is not configured")

    pages = range(1, JSEARCH_PAGES + 1)
    all_jobs = []
    failures = Counter()

    #threadpoolexecutor fires all page requests simultaneously
    #max_workers matches page count — no reason to queue when all can run at once
    with ThreadPoolExecutor(max_workers=JSEARCH_PAGES) as executor:
        futures = {
            executor.submit(_fetch_page, query, page): page
            for page in pages
        }
        for future in as_completed(futures):
            result = future.result()
            if isinstance(result, list):
                all_jobs.extend(result)
            else:
                failures[result] += 1

    total_failed = sum(failures.values())

    if total_failed == JSEARCH_PAGES:
        #every page failed — pick the most-specific message if one reason dominates, else generic
        dominant, count = failures.most_common(1)[0]
        if count == JSEARCH_PAGES:
            raise JobFetchError(_ALL_FAILED_MESSAGES[dominant])
        raise JobFetchError(_ALL_FAILED_MESSAGES[FetchError.NETWORK])

    if total_failed > 0:
        #some pages worked, others did not — raise so the result is not cached
        #the caller uses PartialFetchError.jobs to still render what we got
        raise PartialFetchError(all_jobs, total_failed, JSEARCH_PAGES)

    return all_jobs

def extract_job_fields(job: dict) -> dict:
    #extracts only the fields we actually use — keeps downstream code clean
    #every field has a safe default so callers never deal with KeyError
    return {
        "title": job.get("job_title", ""),
        "company": job.get("employer_name", ""),
        "description": job.get("job_description", ""),
        "is_remote": job.get("job_is_remote", False),
        "location": job.get("job_city", "") or job.get("job_country", ""),
        "posted_at": job.get("job_posted_at", ""),
        "highlights": job.get("job_highlights", {})
    }
