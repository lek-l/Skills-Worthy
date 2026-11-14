import json
from collections import Counter
from unittest.mock import patch

import pytest

import ai
from taxonomy import count_taxonomy_skills, count_specific_skills


class TestTaxonomyCounting:
    def test_finds_common_skills(self):
        counts = count_taxonomy_skills(["We need Python, SQL, and Tableau."])
        assert counts["Python"] == 1
        assert counts["SQL"] == 1

    def test_counts_across_descriptions(self):
        counts = count_taxonomy_skills(["Python and SQL.", "SQL and Excel.", "Python, SQL, Tableau."])
        assert counts["SQL"] == 3
        assert counts["Python"] == 2

    def test_case_insensitive(self):
        counts = count_taxonomy_skills(["PYTHON and sql"])
        assert counts["Python"] == 1
        assert counts["SQL"] == 1

    def test_no_false_positives(self):
        counts = count_taxonomy_skills(["We need good communication and management skills"])
        assert len(counts) == 0


class TestCountSpecificSkills:
    def test_counts_custom_skills(self):
        counts = count_specific_skills(["Use Plaid API", "Plaid and Stripe", "Nothing"], ["Plaid", "Stripe"])
        assert counts["Plaid"] == 2
        assert counts["Stripe"] == 1

    def test_empty_list(self):
        assert count_specific_skills(["text"], []) == Counter()


class TestNormalizeSkill:
    def test_alias(self):
        assert ai._normalize_skill("js") == "JavaScript"
        assert ai._normalize_skill("powerbi") == "Power BI"

    def test_unicode_spaces(self):
        assert ai._normalize_skill("Power\u202fBI") == "Power BI"

    def test_empty(self):
        assert ai._normalize_skill("") == ""


class TestIsRoleNoise:
    def test_whole_word_match(self):
        assert ai._is_role_noise("data analysis", {"data", "analyst"}) is True

    def test_substring_not_noise(self):
        assert ai._is_role_noise("databricks", {"data"}) is False


class TestDiscoverNicheSkills:
    def test_filters_known_skills(self):
        with patch.object(ai, "_call_groq", return_value="Python, SQL, Plaid"):
            niche = ai._discover_niche_skills(["desc"], {"Python", "SQL"})
        assert niche == ["Plaid"]

    def test_groq_failure(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai._discover_niche_skills(["desc"], set()) == []

    def test_excludes_vague_terms(self):
        with patch.object(ai, "_call_groq", return_value="Programming, Analytics, Plaid"):
            niche = ai._discover_niche_skills(["desc"], set())
        assert "Plaid" in niche
        assert "Programming" not in niche


class TestExtractSkills:
    def test_empty(self):
        assert ai.extract_skills([]).is_empty()

    def test_taxonomy_counted_without_groq(self):
        with patch.object(ai, "_call_groq", return_value="") as mock:
            result = ai.extract_skills(["Python and SQL.", "SQL and Excel.", "Python, SQL, Tableau."])
        assert mock.call_count == 1
        assert result.counts["SQL"] == 3
        assert result.counts["Python"] == 2

    def test_niche_added(self):
        with patch.object(ai, "_call_groq", return_value="Plaid"):
            result = ai.extract_skills(["Use Plaid API and Python."] * 3)
        assert result.counts["Python"] == 3
        assert result.counts["Plaid"] == 3

    def test_caps_at_max(self):
        with patch.object(ai, "_call_groq", return_value=""):
            result = ai.extract_skills(["Python required."] * 40)
        assert result.counts["Python"] == ai.MAX_DESCRIPTIONS


class TestInsight:
    def test_truncates(self):
        with patch.object(ai, "_call_groq", return_value="One. Two. Three."):
            assert ai.generate_insight("a", ["P"]).text == "One. Two."

    def test_failure(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai.generate_insight("a", ["P"]).available is False


class TestRoadmap:
    def test_no_missing(self):
        with patch.object(ai, "_call_groq") as mock:
            msg = ai.generate_roadmap("a", [], ["P"])
        mock.assert_not_called()
        assert "already have" in msg


class TestComputeSkillTiers:
    def test_empty(self):
        assert ai.compute_skill_tiers(Counter(), "a", 10) == {
            "must_have": [], "good_to_have": [], "nice_to_have": []
        }

    def test_percentage_thresholds(self):
        #thresholds: must >= 30%, good 15-29%, nice < 15%
        #out of 10: A=8(80%) must, B=2(20%) good, C=1(10%) nice
        counts = Counter({"A": 8, "B": 2, "C": 1})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 10)
        assert tiers["must_have"] == ["A"]
        assert tiers["good_to_have"] == ["B"]
        assert tiers["nice_to_have"] == ["C"]

    def test_boundaries_are_inclusive_at_lower_edge(self):
        #out of 20: A=6(30%) must, B=3(15%) good, C=2(10%) nice
        counts = Counter({"A": 6, "B": 3, "C": 2})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 20)
        assert tiers["must_have"] == ["A"]
        assert tiers["good_to_have"] == ["B"]
        assert tiers["nice_to_have"] == ["C"]

    def test_nothing_hits_must_threshold(self):
        #out of 10: A=2(20%) good, B=1(10%) nice, C=1(10%) nice
        counts = Counter({"A": 2, "B": 1, "C": 1})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 10)
        assert tiers["must_have"] == []
        assert tiers["good_to_have"] == ["A"]
        assert tiers["nice_to_have"] == ["B", "C"]

    def test_each_tier_capped_at_eight(self):
        counts = Counter({f"S{i}": 9 for i in range(12)})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 10)
        assert len(tiers["must_have"]) == 8

    def test_excludes_role_noise(self):
        counts = Counter({"Data Analysis": 9, "Python": 5})
        tiers = ai.compute_skill_tiers(counts, "data analyst", 10)
        all_placed = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert "Data Analysis" not in all_placed

    def test_excludes_vague_terms(self):
        counts = Counter({"AI": 5, "Python": 3})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 10)
        all_placed = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert "AI" not in all_placed

    def test_casing_preserved(self):
        tiers = ai.compute_skill_tiers(Counter({"Power BI": 8}), "unrelated", 10)
        assert tiers["must_have"] == ["Power BI"]


def fake_response(content, finish_reason="stop"):
    from types import SimpleNamespace as NS
    return NS(choices=[NS(message=NS(content=content), finish_reason=finish_reason)])


def fake_client(**create_kwargs):
    from unittest.mock import MagicMock
    client = MagicMock()
    client.chat.completions.create.configure_mock(**create_kwargs)
    return client


class TestCallGroq:
    def test_returns_content(self):
        with patch.object(ai, "_get_client", return_value=fake_client(return_value=fake_response("  hello  "))):
            assert ai._call_groq("p", 50) == "hello"

    @pytest.mark.parametrize("content", [None, "", "   "])
    def test_empty_returns_none(self, content, caplog):
        with patch.object(ai, "_get_client", return_value=fake_client(return_value=fake_response(content, "length"))):
            with caplog.at_level("WARNING"):
                assert ai._call_groq("p", 50) is None

    def test_exception_returns_none(self, caplog):
        with patch.object(ai, "_get_client", return_value=fake_client(side_effect=RuntimeError("boom"))):
            with caplog.at_level("ERROR"):
                assert ai._call_groq("p", 50) is None

    def test_no_choices_returns_none(self):
        from types import SimpleNamespace as NS
        with patch.object(ai, "_get_client", return_value=fake_client(return_value=NS(choices=[]))):
            assert ai._call_groq("p", 50) is None

    def test_missing_api_key_skips_call(self, monkeypatch):
        #no key -> no client, no crash, ai features just return None
        monkeypatch.setattr(ai, "GROQ_API_KEY", None)
        monkeypatch.setattr(ai, "_client", None)
        assert ai._get_client() is None
        assert ai._call_groq("p", 50) is None


class TestPipeline:
    def test_empty(self):
        result = ai.run_ai_pipeline("a", [])
        assert len(result) == 4
        assert result[0].is_empty()

    def test_full_run(self):
        def fake(prompt, max_tokens):
            if "technical skill" in prompt.lower():
                return "Plaid, Stripe"
            if "Categorize" in prompt:
                return json.dumps({"Fintech": ["Plaid"]})
            return "One. Two."

        with patch.object(ai, "_call_groq", side_effect=fake):
            skill_result, categories, insight, tiers = ai.run_ai_pipeline("fintech", ["Python and SQL with Plaid."] * 3)

        assert skill_result.counts["Python"] == 3
        assert insight.available is True