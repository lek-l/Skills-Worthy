#edge cases found during the pre-commit review: empty/garbage inputs, boundaries, case handling
from collections import Counter
from unittest.mock import patch

import pytest

import ai
import api
from analysis import compute_skill_gap, build_skill_dataframe, parse_roadmap_steps


class TestSkillGapEdgeCases:
    def test_empty_market_skills_gives_zero_not_division_error(self):
        gap = compute_skill_gap([], ["Python"])
        assert gap["overlap_pct"] == 0
        assert gap["matched"] == [] and gap["missing"] == []

    def test_punctuation_only_input_matches_nothing(self):
        #"!!!" normalizes to an empty key; it must not match anything
        gap = compute_skill_gap(["SQL", "Python"], ["!!!", "  ", "--"])
        assert gap["matched"] == []
        assert gap["overlap_pct"] == 0

    @pytest.mark.parametrize("typed", ["powerbi", "POWER BI", "power-bi", "Power.BI", " power  bi "])
    def test_spacing_case_punctuation_variants_match(self, typed):
        gap = compute_skill_gap(["Power BI"], [typed])
        assert gap["matched"] == ["Power BI"]

    def test_c_plus_plus_and_c_sharp_stay_distinct_from_c(self):
        gap = compute_skill_gap(["C", "C++", "C#"], ["c++"])
        assert gap["matched"] == ["C++"]
        assert set(gap["missing"]) == {"C", "C#"}

    def test_duplicate_user_skills_do_not_inflate_overlap(self):
        gap = compute_skill_gap(["SQL", "Python"], ["sql", "SQL", "Sql"])
        assert gap["overlap_pct"] == 50

    def test_strong_match_boundary_at_sixty_percent(self):
        market = ["A", "B", "C", "D", "E"]
        assert compute_skill_gap(market, ["a", "b", "c"])["is_strong_match"] is True   #60%
        assert compute_skill_gap(market, ["a", "b"])["is_strong_match"] is False       #40%


class TestSkillDataframeEdgeCases:
    def test_zero_analyzed_does_not_divide_by_zero(self):
        df = build_skill_dataframe(Counter({"SQL": 3}), "accountant", 0)
        assert df["pct"].tolist() == [0]

    def test_pct_never_exceeds_100_when_spellings_merge(self):
        #"Powerbi" normalizes to "Power BI"; merged count 8 out of 5 postings must cap at 100
        df = build_skill_dataframe(Counter({"Power BI": 5, "Powerbi": 3}), "accountant", 5)
        assert df["pct"].max() == 100

    def test_all_noise_returns_empty_frame_with_columns(self):
        df = build_skill_dataframe(Counter({"Data Analysis": 5}), "data analyst", 5)
        assert df.empty
        assert list(df.columns) == ["skill", "count", "pct"]


class TestFetchEdgeCases:
    def test_partial_page_failure_still_returns_jobs(self):
        #one page times out, others succeed -> no exception, jobs from good pages kept
        def page(query, n):
            return None if n == 1 else [{"job_title": f"job {n}"}]
        with patch.object(api, "_fetch_page", side_effect=page):
            jobs = api.fetch_jobs("x")
        assert len(jobs) == api.JSEARCH_PAGES - 1

    def test_all_pages_failed_raises(self):
        with patch.object(api, "_fetch_page", return_value=None):
            with pytest.raises(api.JobFetchError):
                api.fetch_jobs("x")

    def test_all_pages_timed_out_says_slow_not_connection(self):
        with patch.object(api, "_fetch_page", return_value=api._TIMED_OUT):
            with pytest.raises(api.JobFetchError, match="taking too long"):
                api.fetch_jobs("x")

    def test_mixed_timeout_and_error_keeps_connection_message(self):
        results = iter([api._TIMED_OUT, None, api._TIMED_OUT])
        with patch.object(api, "_fetch_page", side_effect=lambda q, p: next(results)):
            with pytest.raises(api.JobFetchError, match="check your connection"):
                api.fetch_jobs("x")

    def test_single_page_helper_hides_timeout_marker(self):
        with patch.object(api, "_fetch_page", return_value=api._TIMED_OUT):
            assert api._fetch_single_page("x", 1) == []

    def test_zero_real_results_is_empty_list_not_error(self):
        #UI then shows "no postings found" instead of "could not fetch jobs"
        with patch.object(api, "_fetch_page", return_value=[]):
            assert api.fetch_jobs("underwater basket weaving") == []


class TestAiEdgeCases:
    def test_insight_with_no_sentence_terminator_kept_whole(self):
        with patch.object(ai, "_call_groq", return_value="Python dominates"):
            assert ai.generate_insight("q", ["Python"]).text == "Python dominates"

    def test_categorize_non_dict_json_returns_none(self):
        with patch.object(ai, "_call_groq", return_value='["a", "b"]'):
            assert ai.categorize_skills(["a"]) is None

    def test_categorize_strips_markdown_fences(self):
        with patch.object(ai, "_call_groq", return_value='```json\n{"Data": ["SQL"]}\n```'):
            assert ai.categorize_skills(["SQL"]) == {"Data": ["SQL"]}

    def test_tiers_zero_total_analyzed(self):
        assert ai.compute_skill_tiers(Counter({"SQL": 3}), "x", 0)["must_have"] == []


class TestParseRoadmapSteps:
    def test_drops_intro_and_outro_when_steps_are_numbered(self):
        text = "Here is your plan:\nStep 1: Learn Excel.\nStep 2: Learn Tableau.\nGood luck!"
        assert parse_roadmap_steps(text) == ["Learn Excel.", "Learn Tableau."]

    @pytest.mark.parametrize("line", [
        "Step 1: Learn Excel.", "step 1 - Learn Excel.", "1. Learn Excel.", "1) Learn Excel.",
        "**Step 1:** Learn Excel.", "Step 1: Step 1: Learn Excel.",
    ])
    def test_strips_every_prefix_style(self, line):
        assert parse_roadmap_steps(line) == ["Learn Excel."]

    def test_unnumbered_text_kept_as_is(self):
        msg = "you already have all the top skills for this role."
        assert parse_roadmap_steps(msg) == [msg]

    @pytest.mark.parametrize("empty", [None, "", "   \n  \n"])
    def test_empty_input(self, empty):
        assert parse_roadmap_steps(empty) == []

    def test_does_not_strip_numbers_inside_text(self):
        assert parse_roadmap_steps("Step 1: Learn Python 3.12 basics.") == ["Learn Python 3.12 basics."]
