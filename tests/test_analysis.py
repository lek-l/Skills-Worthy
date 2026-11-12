from collections import Counter

import pandas as pd
import pytest

import analysis
from config import TOP_SKILLS_COUNT, CATEGORY_PREVIEW_COUNT


def make_job(title, description="A real description", **extra):
    job = {"job_title": title, "job_description": description}
    job.update(extra)
    return job


class TestProcessJobs:
    def test_keeps_exact_phrase_match(self):
        jobs = [make_job("Senior Data Analyst"), make_job("Data Analyst II")]
        result = analysis.process_jobs(jobs, "data analyst")
        assert len(result.descriptions) == 2

    def test_drops_jobs_with_empty_description(self):
        jobs = [make_job("Data Analyst", description=""), make_job("Data Analyst")]
        result = analysis.process_jobs(jobs, "data analyst")
        assert len(result.descriptions) == 1

    def test_drops_jobs_with_unrelated_titles(self):
        jobs = [make_job("Registered Nurse"), make_job("Data Analyst")]
        result = analysis.process_jobs(jobs, "data analyst")
        assert len(result.descriptions) == 1

    def test_requires_all_words_not_just_one(self):
        #"data engineer" should NOT match "data analyst" search
        result = analysis.process_jobs([make_job("Data Engineer")], "data analyst")
        assert len(result.descriptions) == 0

    def test_job_count_reports_all_fetched(self):
        jobs = [make_job("Nurse"), make_job("Data Analyst"), make_job("Cook")]
        result = analysis.process_jobs(jobs, "data analyst")
        assert result.job_count == 3

    def test_matching_is_case_insensitive(self):
        result = analysis.process_jobs([make_job("DATA ANALYST")], "Data Analyst")
        assert len(result.descriptions) == 1

    def test_empty_job_list(self):
        result = analysis.process_jobs([], "data analyst")
        assert result.has_descriptions is False

    def test_missing_fields_do_not_crash(self):
        result = analysis.process_jobs([{}], "data analyst")
        assert result.descriptions == []


class TestBuildSkillDataframe:
    def test_empty_counter(self):
        df = analysis.build_skill_dataframe(Counter(), "analyst")
        assert df.empty
        assert list(df.columns) == ["skill", "count"]

    def test_sorted_by_count_descending(self):
        df = analysis.build_skill_dataframe(Counter({"Python": 2, "Tableau": 9, "Looker": 5}), "unrelated")
        assert df["skill"].tolist() == ["Tableau", "Looker", "Python"]

    def test_capped_at_top_skills_count(self):
        counts = Counter({f"Skill{i}": i + 1 for i in range(TOP_SKILLS_COUNT + 10)})
        df = analysis.build_skill_dataframe(counts, "unrelated")
        assert len(df) == TOP_SKILLS_COUNT

    def test_generic_terms_filtered(self):
        df = analysis.build_skill_dataframe(Counter({"Word": 5, "Outlook": 4, "Python": 1}), "unrelated")
        assert df["skill"].tolist() == ["Python"]

    def test_role_words_filtered(self):
        df = analysis.build_skill_dataframe(Counter({"Data Analysis": 7, "Python": 3}), "data analyst")
        assert df["skill"].tolist() == ["Python"]

    def test_databricks_survives_data_search(self):
        df = analysis.build_skill_dataframe(Counter({"Databricks": 4}), "data engineer")
        assert df["skill"].tolist() == ["Databricks"]

    def test_overlong_names_filtered(self):
        df = analysis.build_skill_dataframe(Counter({"x" * 60: 3, "SQL": 1}), "unrelated")
        assert df["skill"].tolist() == ["SQL"]

    def test_canonical_casing_preserved(self):
        #skills arrive already normalized — no .title() to break them
        for canonical in ["Power BI", "JavaScript", "PostgreSQL", "TensorFlow"]:
            df = analysis.build_skill_dataframe(Counter({canonical: 3}), "unrelated")
            assert df["skill"].tolist() == [canonical], f"{canonical} was mangled"


class TestComputeSkillGap:
    def test_matched_and_missing(self):
        gap = analysis.compute_skill_gap(["Python", "SQL", "Tableau"], ["python", "excel"])
        assert gap["matched"] == ["Python"]
        assert gap["missing"] == ["SQL", "Tableau"]

    def test_overlap_percentage(self):
        gap = analysis.compute_skill_gap(["A", "B", "C"], ["a"])
        assert gap["overlap_pct"] == 33

    def test_strong_match_threshold(self):
        top = ["A", "B", "C", "D", "E"]
        assert analysis.compute_skill_gap(top, ["a", "b", "c"])["is_strong_match"] is True
        assert analysis.compute_skill_gap(top, ["a", "b"])["is_strong_match"] is False

    def test_empty_top_skills(self):
        gap = analysis.compute_skill_gap([], ["Python"])
        assert gap["overlap_pct"] == 0

    def test_full_overlap(self):
        gap = analysis.compute_skill_gap(["A", "B"], ["a", "b"])
        assert gap["overlap_pct"] == 100
        assert gap["missing"] == []


class TestGetCategoryPreviews:
    def test_empty_inputs(self):
        assert analysis.get_category_previews({}) == []
        assert analysis.get_category_previews(None) == []

    def test_preview_truncated_and_flags_overflow(self):
        skills = [f"S{i}" for i in range(CATEGORY_PREVIEW_COUNT + 2)]
        preview = analysis.get_category_previews({"Cloud": skills})[0]
        assert preview["has_more"] is True

    def test_small_category_no_overflow(self):
        preview = analysis.get_category_previews({"Cloud": ["AWS"]})[0]
        assert preview["has_more"] is False

    def test_non_list_values_skipped(self):
        previews = analysis.get_category_previews({"Bad": "text", "Good": ["SQL"]})
        assert previews[0]["category"] == "Good"
