from collections import Counter
import pytest
import analysis
from config import TOP_SKILLS_COUNT


def make_job(title, description="A real description"):
    return {"job_title": title, "job_description": description}


class TestProcessJobs:
    def test_keeps_exact_match(self):
        result = analysis.process_jobs([make_job("Data Analyst")], "data analyst")
        assert len(result.descriptions) == 1

    def test_requires_all_words(self):
        result = analysis.process_jobs([make_job("Data Engineer")], "data analyst")
        assert len(result.descriptions) == 0

    def test_drops_empty_description(self):
        result = analysis.process_jobs([make_job("Data Analyst", "")], "data analyst")
        assert len(result.descriptions) == 0

    def test_case_insensitive(self):
        result = analysis.process_jobs([make_job("DATA ANALYST")], "Data Analyst")
        assert len(result.descriptions) == 1

    def test_empty_list(self):
        result = analysis.process_jobs([], "data analyst")
        assert result.has_descriptions is False


class TestBuildSkillDataframe:
    def test_empty(self):
        df = analysis.build_skill_dataframe(Counter(), "a", 10)
        assert df.empty

    def test_sorted_descending(self):
        df = analysis.build_skill_dataframe(Counter({"Python": 2, "Tableau": 9, "Looker": 5}), "x", 10)
        assert df["skill"].tolist() == ["Tableau", "Looker", "Python"]

    def test_pct_column(self):
        df = analysis.build_skill_dataframe(Counter({"Python": 8}), "x", 10)
        assert df["pct"].tolist() == [80]

    def test_capped(self):
        counts = Counter({f"S{i}": i + 1 for i in range(TOP_SKILLS_COUNT + 10)})
        df = analysis.build_skill_dataframe(counts, "x", 100)
        assert len(df) == TOP_SKILLS_COUNT

    def test_casing_preserved(self):
        for name in ["Power BI", "JavaScript", "PostgreSQL", "TensorFlow"]:
            df = analysis.build_skill_dataframe(Counter({name: 3}), "x", 10)
            assert df["skill"].tolist() == [name], f"{name} was mangled"

    def test_generic_terms_filtered(self):
        df = analysis.build_skill_dataframe(Counter({"Word": 5, "Python": 1}), "x", 10)
        assert df["skill"].tolist() == ["Python"]


class TestComputeSkillGap:
    def test_matched_and_missing(self):
        gap = analysis.compute_skill_gap(["Python", "SQL"], ["python"])
        assert gap["matched"] == ["Python"]
        assert gap["missing"] == ["SQL"]

    def test_full_overlap(self):
        gap = analysis.compute_skill_gap(["A", "B"], ["a", "b"])
        assert gap["overlap_pct"] == 100
        assert gap["is_strong_match"] is True