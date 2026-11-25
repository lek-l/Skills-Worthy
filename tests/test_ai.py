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

    def test_discover_niche_skips_html_fragments(self):
        #postings pasted with raw markup must not surface tags like </div> as skills
        with patch.object(ai, "_call_groq", return_value="Python, </div>, <br>, Workday"):
            result = ai._discover_niche_skills(["a job description"], set())
        joined = " ".join(result)
        assert "<" not in joined and ">" not in joined
        assert "Workday" in result


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

    def test_top_seven_rank_as_must_have(self):
        #position based: the 7 most frequent skills are must have
        counts = Counter({f"S{i}": 30 - i for i in range(10)})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 30)
        assert tiers["must_have"] == [f"S{i}" for i in range(7)]

    def test_next_seven_rank_as_good_to_have(self):
        #skills ranked 8 through 14 are good to have
        counts = Counter({f"S{i}": 30 - i for i in range(16)})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 30)
        assert tiers["good_to_have"] == [f"S{i}" for i in range(7, 14)]

    def test_remainder_ranks_as_nice_to_have(self):
        #skills ranked 15 onward are nice to have (also capped at 7)
        counts = Counter({f"S{i}": 30 - i for i in range(18)})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 30)
        assert tiers["nice_to_have"] == [f"S{i}" for i in range(14, 18)]

    def test_few_skills_all_land_in_must_have(self):
        #narrow roles: with only a few skills they all rank must have, lower tiers stay empty
        counts = Counter({"A": 8, "B": 2, "C": 1})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 10)
        assert tiers["must_have"] == ["A", "B", "C"]
        assert tiers["good_to_have"] == []
        assert tiers["nice_to_have"] == []

    def test_each_tier_capped_at_seven(self):
        counts = Counter({f"S{i}": 30 - i for i in range(30)})
        tiers = ai.compute_skill_tiers(counts, "unrelated", 30)
        assert len(tiers["must_have"]) == 7
        assert len(tiers["good_to_have"]) == 7
        assert len(tiers["nice_to_have"]) == 7

    def test_academic_prereqs_excluded(self):
        #degree fields like statistics and mathematics are prerequisites, not learnable skills
        counts = Counter({"Statistics": 9, "Mathematics": 8, "SQL": 7})
        tiers = ai.compute_skill_tiers(counts, "data analyst", 10)
        all_placed = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert "Statistics" not in all_placed
        assert "Mathematics" not in all_placed
        assert "SQL" in all_placed

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