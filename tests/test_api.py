from unittest.mock import MagicMock, patch

import pytest
import requests

import api


def ok_response(n_jobs):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": [{"job_title": f"Job {i}"} for i in range(n_jobs)]}
    return response


#_fetch_single_page

class TestFetchSinglePage:
    def test_returns_jobs_on_success(self):
        with patch.object(api.requests, "get", return_value=ok_response(10)):
            assert len(api._fetch_single_page("analyst", 1)) == 10

    def test_missing_data_key_returns_empty_list(self):
        response = MagicMock()
        response.json.return_value = {"status": "OK"}
        with patch.object(api.requests, "get", return_value=response):
            assert api._fetch_single_page("analyst", 1) == []

    @pytest.mark.parametrize("error", [
        requests.exceptions.Timeout(),
        requests.exceptions.ConnectionError(),
        requests.exceptions.HTTPError("429"),
    ])
    def test_request_errors_return_empty_list_instead_of_raising(self, error):
        with patch.object(api.requests, "get", side_effect=error):
            assert api._fetch_single_page("analyst", 1) == []

    def test_request_uses_timeout_and_page_param(self):
        with patch.object(api.requests, "get", return_value=ok_response(1)) as mock_get:
            api._fetch_single_page("analyst", 3)
        kwargs = mock_get.call_args.kwargs
        assert kwargs["timeout"] == api.JSEARCH_TIMEOUT
        assert kwargs["params"]["page"] == "3"
        assert kwargs["params"]["query"] == "analyst"


#fetch_jobs

class TestFetchJobs:
    def test_aggregates_all_pages(self):
        with patch.object(api.requests, "get", return_value=ok_response(10)) as mock_get:
            jobs = api.fetch_jobs("analyst")
        assert mock_get.call_count == api.JSEARCH_PAGES
        assert len(jobs) == 10 * api.JSEARCH_PAGES

    def test_missing_api_key_raises(self):
        with patch.object(api, "JSEARCH_API_KEY", None):
            with pytest.raises(api.JobFetchError, match="not configured"):
                api.fetch_jobs("analyst")

    def test_all_pages_failing_raises(self):
        with patch.object(api.requests, "get", side_effect=requests.exceptions.Timeout()):
            with pytest.raises(api.JobFetchError):
                api.fetch_jobs("analyst")

    def test_partial_failure_returns_surviving_pages(self):
        responses = [ok_response(10), requests.exceptions.Timeout(), ok_response(8)]
        with patch.object(api.requests, "get", side_effect=responses):
            jobs = api.fetch_jobs("analyst")
        assert len(jobs) == 18

    @pytest.mark.xfail(strict=True, reason="known bug: a query with zero real results raises JobFetchError, which the UI labels a configuration error")
    def test_zero_results_is_not_treated_as_an_error(self):
        empty = MagicMock()
        empty.raise_for_status.return_value = None
        empty.json.return_value = {"data": []}
        with patch.object(api.requests, "get", return_value=empty):
            assert api.fetch_jobs("underwater basket weaving") == []


#extract_job_fields

class TestExtractJobFields:
    def test_maps_fields(self):
        job = {
            "job_title": "Analyst", "employer_name": "Acme", "job_description": "text",
            "job_is_remote": True, "job_city": "Camden", "job_posted_at": "2 days ago",
            "job_highlights": {"Qualifications": ["SQL"]},
        }
        fields = api.extract_job_fields(job)
        assert fields["title"] == "Analyst"
        assert fields["company"] == "Acme"
        assert fields["is_remote"] is True
        assert fields["location"] == "Camden"

    def test_empty_job_gets_safe_defaults(self):
        fields = api.extract_job_fields({})
        assert fields["title"] == ""
        assert fields["description"] == ""
        assert fields["is_remote"] is False
        assert fields["highlights"] == {}

    def test_location_falls_back_to_country(self):
        assert api.extract_job_fields({"job_country": "US"})["location"] == "US"

    def test_none_values_do_not_break_location(self):
        assert api.extract_job_fields({"job_city": None, "job_country": None})["location"] is None
