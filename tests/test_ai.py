import json
from collections import Counter
from unittest.mock import patch

import pytest

import ai
from taxonomy import count_taxonomy_skills, count_specific_skills, TAXONOMY_NAMES


#taxonomy

class TestTaxonomyCounting:
    def test_finds_common_skills_in_text(self):
        desc = "We need Python, SQL, and Tableau experience. AWS is a plus."
        counts = count_taxonomy_skills([desc])
        assert counts["Python"] == 1
        assert counts["SQL"] == 1
        assert counts["Tableau"] == 1
        assert counts["AWS"] == 1

    def test_counts_across_multiple_descriptions(self):
        descs = [
            "Python and SQL required.",
            "SQL and Excel needed.",
            "Python, SQL, and Tableau.",
        ]
        counts = count_taxonomy_skills(descs)
        assert counts["SQL"] == 3
        assert counts["Python"] == 2
        assert counts["Tableau"] == 1
        assert counts["Excel"] == 1

    def test_case_insensitive(self):
        counts = count_taxonomy_skills(["PYTHON and sql and TABLEAU"])
        assert counts["Python"] == 1
        assert counts["SQL"] == 1

    def test_power_bi_variations(self):
        counts = count_taxonomy_skills(["Experience with Power BI and PowerBI dashboards"])
        assert counts["Power BI"] == 1

    def test_databricks_not_caught_by_data_search(self):
        counts = count_taxonomy_skills(["Experience with Databricks"])
        assert "Databricks" in counts

    def test_empty_descriptions(self):
        assert count_taxonomy_skills([]) == Counter()

    def test_no_false_positives_on_common_words(self):
        counts = count_taxonomy_skills(["We need good communication and management skills"])
        assert len(counts) == 0


class TestCountSpecificSkills:
    def test_counts_custom_skills(self):
        descs = ["Use Plaid API for banking", "Plaid and Stripe integration", "No relevant skills"]
        counts = count_specific_skills(descs, ["Plaid", "Stripe"])
        assert counts["Plaid"] == 2
        assert counts["Stripe"] == 1

    def test_empty_skill_list(self):
        assert count_specific_skills(["some text"], []) == Counter()

    def test_case_insensitive(self):
        counts = count_specific_skills(["Use PLAID for banking"], ["Plaid"])
        assert counts["Plaid"] == 1


#normalization

class TestNormalizeSkill:
    def test_alias_maps_to_canonical(self):
        assert ai._normalize_skill("js") == "JavaScript"
        assert ai._normalize_skill("sklearn") == "Scikit-learn"
        assert ai._normalize_skill("powerbi") == "Power BI"

    def test_unknown_skill_gets_title_cased(self):
        assert ai._normalize_skill("zendesk") == "Zendesk"

    def test_unicode_spaces_collapsed(self):
        assert ai._normalize_skill("Power\u202fBI") == "Power BI"
        assert ai._normalize_skill("Power\u00a0BI") == "Power BI"

    def test_empty_and_garbage(self):
        assert ai._normalize_skill("") == ""
        assert ai._normalize_skill("...") == ""


class TestIsRoleNoise:
    def test_whole_word_match_is_noise(self):
        assert ai._is_role_noise("data analysis", {"data", "analyst"}) is True

    def test_substring_is_not_noise(self):
        assert ai._is_role_noise("databricks", {"data", "analyst"}) is False

    def test_short_words_ignored(self):
        assert ai._is_role_noise("bi tools", {"bi"}) is False


#niche discovery

class TestDiscoverNicheSkills:
    def test_returns_only_skills_not_in_known_set(self):
        with patch.object(ai, "_call_groq", return_value="Python, SQL, Plaid, Stripe"):
            niche = ai._discover_niche_skills(["desc"], {"Python", "SQL"})
        assert "Plaid" in niche
        assert "Stripe" in niche
        assert "Python" not in niche
        assert "SQL" not in niche

    def test_groq_failure_returns_empty(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai._discover_niche_skills(["desc"], set()) == []

    def test_excludes_vague_terms(self):
        with patch.object(ai, "_call_groq", return_value="Programming, Analytics, Plaid"):
            niche = ai._discover_niche_skills(["desc"], set())
        assert "Plaid" in niche
        assert "Programming" not in niche
        assert "Analytics" not in niche

    def test_sentence_non_answers_filtered(self):
        with patch.object(ai, "_call_groq", return_value="No technical skills mentioned, Plaid"):
            niche = ai._discover_niche_skills(["desc"], set())
        assert "Plaid" in niche
        assert len(niche) == 1


#hybrid extraction

class TestExtractSkills:
    def test_empty_input(self):
        result = ai.extract_skills([])
        assert result.is_empty()

    def test_taxonomy_skills_counted_without_groq(self):
        descs = [
            "We need Python and SQL.",
            "SQL and Tableau required.",
            "Python, SQL, and Excel.",
        ]
        with patch.object(ai, "_call_groq", return_value="") as mock:
            result = ai.extract_skills(descs)
        #only 1 groq call for niche discovery, not per-description
        assert mock.call_count == 1
        assert result.counts["SQL"] == 3
        assert result.counts["Python"] == 2

    def test_niche_skills_added_to_taxonomy_counts(self):
        descs = ["Use Plaid API and Python for banking."] * 3
        with patch.object(ai, "_call_groq", return_value="Plaid"):
            result = ai.extract_skills(descs)
        assert result.counts["Python"] == 3
        assert result.counts["Plaid"] == 3

    def test_caps_at_max_descriptions(self):
        descs = ["Python required."] * 40
        with patch.object(ai, "_call_groq", return_value=""):
            result = ai.extract_skills(descs)
        assert result.counts["Python"] == ai.MAX_DESCRIPTIONS


#groq wrapper

def fake_response(content, finish_reason="stop"):
    from types import SimpleNamespace as NS
    return NS(choices=[NS(message=NS(content=content), finish_reason=finish_reason)])


class TestCallGroq:
    def test_returns_stripped_content(self):
        with patch.object(ai._client.chat.completions, "create", return_value=fake_response("  hello  ")):
            assert ai._call_groq("prompt", 50) == "hello"

    @pytest.mark.parametrize("content", [None, "", "   "])
    def test_empty_content_returns_none(self, content, caplog):
        with patch.object(ai._client.chat.completions, "create", return_value=fake_response(content, "length")):
            with caplog.at_level("WARNING"):
                assert ai._call_groq("prompt", 50) is None

    def test_exception_returns_none(self, caplog):
        with patch.object(ai._client.chat.completions, "create", side_effect=RuntimeError("boom")):
            with caplog.at_level("ERROR"):
                assert ai._call_groq("prompt", 50) is None


#insight

class TestInsight:
    def test_truncates_to_two_sentences(self):
        long = "One. Two. Three. Four."
        with patch.object(ai, "_call_groq", return_value=long):
            result = ai.generate_insight("analyst", ["Python"])
        assert result.text == "One. Two."

    def test_groq_failure(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai.generate_insight("analyst", ["Python"]).available is False


class TestSoftSkills:
    def test_parses_list(self):
        with patch.object(ai, "_call_groq", return_value="Communication, Teamwork"):
            assert ai.suggest_soft_skills("analyst") == ["Communication", "Teamwork"]

    def test_groq_failure(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai.suggest_soft_skills("analyst") == []


class TestRoadmap:
    def test_no_missing_skills_skips_groq(self):
        with patch.object(ai, "_call_groq") as mock:
            msg = ai.generate_roadmap("analyst", [], ["Python"])
        mock.assert_not_called()
        assert "already have all" in msg


#tiers

class TestComputeSkillTiers:
    def test_empty(self):
        result = ai.compute_skill_tiers(Counter(), "analyst")
        assert result == {"must_have": [], "good_to_have": [], "nice_to_have": []}

    def test_splits_by_frequency(self):
        counts = Counter({"A": 9, "B": 8, "C": 7, "D": 6, "E": 5, "F": 4})
        tiers = ai.compute_skill_tiers(counts, "unrelated")
        assert tiers["must_have"] == ["A", "B"]
        assert tiers["good_to_have"] == ["C", "D"]
        assert tiers["nice_to_have"] == ["E", "F"]

    def test_excludes_role_noise(self):
        counts = Counter({"Data Analysis": 9, "Python": 5})
        tiers = ai.compute_skill_tiers(counts, "data analyst")
        all_skills = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert all_skills == ["Python"]

    def test_excludes_vague_terms(self):
        counts = Counter({"AI": 5, "Python": 3})
        tiers = ai.compute_skill_tiers(counts, "unrelated")
        all_skills = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert "AI" not in all_skills

    def test_canonical_casing_preserved(self):
        tiers = ai.compute_skill_tiers(Counter({"Power BI": 3}), "unrelated")
        assert tiers["must_have"] == ["Power BI"]


#pipeline

class TestPipeline:
    def test_empty_extraction(self):
        result = ai.run_ai_pipeline("analyst", [])
        assert len(result) == 5
        assert result[0].is_empty()

    def test_full_run(self):
        def fake(prompt, max_tokens):
            if "technical skill" in prompt.lower():
                return "Plaid, Stripe"
            if "Categorize" in prompt:
                return json.dumps({"Fintech": ["Plaid", "Stripe"]})
            if "soft skills" in prompt.lower():
                return "Communication, Curiosity"
            return "One. Two."

        descs = ["Use Python and SQL with Plaid API."] * 3
        with patch.object(ai, "_call_groq", side_effect=fake):
            skill_result, categories, insight, soft_skills, tiers = ai.run_ai_pipeline("fintech", descs)

        assert skill_result.counts["Python"] == 3
        assert skill_result.counts["SQL"] == 3
        assert insight.available is True
        assert len(soft_skills) == 2
