import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
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

class JobFetchError(Exception):
    #raised when job fetching fails in a way the caller needs to handle differently
    pass

#marker returned by _fetch_page when a page timed out (vs None for any other failure)
#lets fetch_jobs tell "jsearch is slow" apart from "connection / api key problem"
_TIMED_OUT = object()

def _fetch_single_page(query: str, page: int) -> list:
    #fetches one page of job results — returns empty list on failure (kept for existing callers)
    result = _fetch_page(query, page)
    return result if isinstance(result, list) else []

def _fetch_page(query: str, page: int):
    #fetches one page of job results — designed to run in parallel
    #returns a list (possibly empty = zero results), _TIMED_OUT on timeout, or None on other failures
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
        #timeout is expected under load — log and continue, dont crash
        logger.warning("timeout on page %d for query '%s'", page, query)
        return _TIMED_OUT

    except requests.exceptions.HTTPError as e:
        #4xx means bad request or auth issue — worth surfacing differently from network errors
        logger.error("http error on page %d: %s", page, e)
        return None

    except requests.exceptions.RequestException as e:
        #catch-all for network level failures
        logger.error("network error on page %d: %s", page, e)
        return None

def fetch_jobs(query: str) -> list:
    #fetches all pages in parallel — significantly faster than sequential fetching
    #raises JobFetchError if api key is missing or all pages fail
    if not JSEARCH_API_KEY:
        raise JobFetchError("jsearch api key is not configured")

    pages = range(1, JSEARCH_PAGES + 1)
    all_jobs = []
    failed = 0
    timed_out = 0

    #threadpoolexecutor fires all page requests simultaneously
    #max_workers matches page count — no reason to queue when all can run at once
    with ThreadPoolExecutor(max_workers=JSEARCH_PAGES) as executor:
        futures = {
            executor.submit(_fetch_page, query, page): page
            for page in pages
        }
        for future in as_completed(futures):
            result = future.result()
            if not isinstance(result, list):
                failed += 1
                timed_out += result is _TIMED_OUT
                continue
            all_jobs.extend(result)

    if failed == JSEARCH_PAGES:
        if timed_out == JSEARCH_PAGES:
            #every page was just slow — nothing is wrong on the user's side
            raise JobFetchError("the job search is taking too long right now. try again in a moment.")
        raise JobFetchError("all page requests failed — check your connection or API key")

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
