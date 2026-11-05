import json
from collections import Counter
from unittest.mock import patch

import pytest

import ai


#normalization

class TestNormalizeSkill:
    def test_alias_maps_to_canonical_name(self):
        assert ai._normalize_skill("js") == "JavaScript"
        assert ai._normalize_skill("sklearn") == "Scikit-learn"
        assert ai._normalize_skill("powerbi") == "Power BI"

    def test_alias_lookup_is_case_insensitive(self):
        assert ai._normalize_skill("JS") == "JavaScript"
        assert ai._normalize_skill("Postgres") == "PostgreSQL"

    def test_unknown_skill_keeps_original_casing(self):
        assert ai._normalize_skill("Zendesk") == "Zendesk"

    def test_strips_whitespace_and_trailing_punctuation(self):
        assert ai._normalize_skill("  Python.  ") == "Python"
        assert ai._normalize_skill("-SQL-") == "SQL"

    def test_unicode_spaces_are_collapsed_before_alias_lookup(self):
        #the narrow no break space was seen in real model output for Power BI
        assert ai._normalize_skill("Power\u202fBI") == "Power BI"
        assert ai._normalize_skill("Power\u00a0BI") == "Power BI"


class TestTruncateDescription:
    def test_short_text_is_unchanged(self):
        assert ai._truncate_description("short") == "short"

    def test_long_text_is_cut_to_limit(self):
        assert len(ai._truncate_description("x" * 5000)) == 600

    def test_custom_limit(self):
        assert ai._truncate_description("abcdef", max_chars=3) == "abc"


class TestIsRoleNoise:
    def test_whole_word_match_is_noise(self):
        assert ai._is_role_noise("data analysis", {"data", "analyst"}) is True

    def test_substring_is_not_noise(self):
        #databricks contains the letters of data but is not the word data
        assert ai._is_role_noise("databricks", {"data", "analyst"}) is False

    def test_short_search_words_are_ignored(self):
        assert ai._is_role_noise("bi tools", {"bi"}) is False

    def test_empty_search_words(self):
        assert ai._is_role_noise("python", set()) is False


#extraction

class TestExtractSkillsFromAll:
    def test_counts_skills_across_postings(self):
        response = "1: Python, SQL\n2: python3, Tableau\n3: Python"
        with patch.object(ai, "_call_groq", return_value=response):
            counts = ai._extract_skills_from_all(["a", "b", "c"])
        assert counts == Counter({"Python": 3, "SQL": 1, "Tableau": 1})

    def test_excluded_terms_are_dropped(self):
        response = "1: None, N/A, Python\n2: No technical skills mentioned"
        with patch.object(ai, "_call_groq", return_value=response):
            counts = ai._extract_skills_from_all(["a", "b"])
        assert counts == Counter({"Python": 1})

    def test_lines_without_colon_are_skipped(self):
        with patch.object(ai, "_call_groq", return_value="Here are the skills\n1: SQL"):
            counts = ai._extract_skills_from_all(["a"])
        assert counts == Counter({"SQL": 1})

    def test_overlong_skill_names_are_dropped(self):
        long_name = "x" * 40
        with patch.object(ai, "_call_groq", return_value=f"1: {long_name}, SQL"):
            counts = ai._extract_skills_from_all(["a"])
        assert counts == Counter({"SQL": 1})

    def test_failed_groq_call_yields_empty_counter(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai._extract_skills_from_all(["a", "b"]) == Counter()

    def test_one_failed_batch_does_not_lose_other_batches(self):
        #batch size is 3, so 4 descriptions means 2 calls
        responses = [None, "1: Python"]
        with patch.object(ai, "_call_groq", side_effect=responses):
            counts = ai._extract_skills_from_all(["a", "b", "c", "d"])
        assert counts == Counter({"Python": 1})

    def test_batching_uses_configured_batch_size(self):
        with patch.object(ai, "_call_groq", return_value="1: SQL") as mock_call:
            ai._extract_skills_from_all(["d"] * 7)
        expected_calls = -(-7 // ai.DESCRIPTION_BATCH_SIZE)
        assert mock_call.call_count == expected_calls

    @pytest.mark.xfail(strict=True, reason="known bug: sentence style non answers pass the filter, seen live as 'Only Etl Is Mentioned'")
    def test_sentence_style_non_answers_are_dropped(self):
        with patch.object(ai, "_call_groq", return_value="1: Only ETL is mentioned"):
            counts = ai._extract_skills_from_all(["a"])
        assert counts == Counter()


class TestExtractSkills:
    def test_empty_input_makes_no_groq_call(self):
        with patch.object(ai, "_call_groq") as mock_call:
            result = ai.extract_skills([])
        mock_call.assert_not_called()
        assert result.is_empty()

    def test_caps_descriptions_at_configured_maximum(self):
        with patch.object(ai, "_call_groq", return_value="1: SQL") as mock_call:
            ai.extract_skills(["d"] * 40)
        expected_calls = -(-ai.MAX_DESCRIPTIONS // ai.DESCRIPTION_BATCH_SIZE)
        assert mock_call.call_count == expected_calls

    def test_result_total_is_distinct_skill_count(self):
        with patch.object(ai, "_call_groq", return_value="1: SQL, Python\n2: SQL"):
            result = ai.extract_skills(["a", "b"])
        assert result.total == 2
        assert result.counts["SQL"] == 2


#categorization

class TestCategorizeSkills:
    def test_empty_input_returns_none_without_calling_groq(self):
        with patch.object(ai, "_call_groq") as mock_call:
            assert ai.categorize_skills([]) is None
        mock_call.assert_not_called()

    def test_valid_json(self):
        payload = json.dumps({"Programming": ["Python"], "Data": ["SQL"]})
        with patch.object(ai, "_call_groq", return_value=payload):
            assert ai.categorize_skills(["Python", "SQL"]) == {"Programming": ["Python"], "Data": ["SQL"]}

    def test_markdown_fenced_json(self):
        payload = "```json\n" + json.dumps({"Cloud": ["AWS"]}) + "\n```"
        with patch.object(ai, "_call_groq", return_value=payload):
            assert ai.categorize_skills(["AWS"]) == {"Cloud": ["AWS"]}

    def test_malformed_json_returns_none(self):
        with patch.object(ai, "_call_groq", return_value="{not json"):
            assert ai.categorize_skills(["AWS"]) is None

    def test_non_dict_json_returns_none(self):
        with patch.object(ai, "_call_groq", return_value="[1, 2, 3]"):
            assert ai.categorize_skills(["AWS"]) is None

    def test_groq_failure_returns_none(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai.categorize_skills(["AWS"]) is None

    def test_empty_and_non_list_categories_are_dropped(self):
        payload = json.dumps({"Good": ["SQL"], "Empty": [], "Bad": "text"})
        with patch.object(ai, "_call_groq", return_value=payload):
            assert ai.categorize_skills(["SQL"]) == {"Good": ["SQL"]}


#insight, soft skills, roadmap

class TestInsightResult:
    def test_available_when_text_present(self):
        assert ai.InsightResult("Two sentences here.").available is True

    @pytest.mark.parametrize("text", [None, "", "   "])
    def test_unavailable_when_empty(self, text):
        assert ai.InsightResult(text).available is False

    def test_generate_insight_wraps_groq_output(self):
        with patch.object(ai, "_call_groq", return_value="Python leads."):
            assert ai.generate_insight("data analyst", ["Python"]).text == "Python leads."

    def test_generate_insight_survives_groq_failure(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai.generate_insight("data analyst", ["Python"]).available is False


class TestSoftSkills:
    def test_parses_comma_separated_list(self):
        with patch.object(ai, "_call_groq", return_value="Communication, Teamwork , Curiosity"):
            assert ai.suggest_soft_skills("analyst") == ["Communication", "Teamwork", "Curiosity"]

    def test_groq_failure_returns_empty_list(self):
        with patch.object(ai, "_call_groq", return_value=None):
            assert ai.suggest_soft_skills("analyst") == []


class TestGenerateRoadmap:
    def test_no_missing_skills_skips_groq(self):
        with patch.object(ai, "_call_groq") as mock_call:
            message = ai.generate_roadmap("analyst", [], ["Python"])
        mock_call.assert_not_called()
        assert "already have all" in message

    def test_prompt_contains_only_first_ten_missing_skills(self):
        missing = [f"Skill{i}" for i in range(15)]
        with patch.object(ai, "_call_groq", return_value="Step 1: x") as mock_call:
            ai.generate_roadmap("analyst", missing, ["Python"])
        prompt = mock_call.call_args[0][0]
        assert "Skill9" in prompt
        assert "Skill10" not in prompt


#tiers

class TestComputeSkillTiers:
    def test_empty_counts(self):
        assert ai.compute_skill_tiers(Counter(), "analyst") == {
            "must_have": [], "good_to_have": [], "nice_to_have": []
        }

    def test_splits_into_thirds_ordered_by_frequency(self):
        counts = Counter({"A": 9, "B": 8, "C": 7, "D": 6, "E": 5, "F": 4})
        tiers = ai.compute_skill_tiers(counts, "unrelated")
        assert tiers["must_have"] == ["A", "B"]
        assert tiers["good_to_have"] == ["C", "D"]
        assert tiers["nice_to_have"] == ["E", "F"]

    def test_every_skill_lands_in_exactly_one_tier(self):
        counts = Counter({f"S{i}": 20 - i for i in range(10)})
        tiers = ai.compute_skill_tiers(counts, "unrelated")
        placed = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert sorted(placed) == sorted(counts)

    def test_role_noise_is_excluded(self):
        counts = Counter({"Data Analysis": 9, "Python": 5})
        tiers = ai.compute_skill_tiers(counts, "data analyst")
        placed = tiers["must_have"] + tiers["good_to_have"] + tiers["nice_to_have"]
        assert placed == ["Python"]

    def test_each_tier_is_capped_at_eight(self):
        counts = Counter({f"S{i}": 100 - i for i in range(60)})
        tiers = ai.compute_skill_tiers(counts, "unrelated")
        assert all(len(v) <= 8 for v in tiers.values())

    def test_acronyms_are_restored(self):
        tiers = ai.compute_skill_tiers(Counter({"SQL": 3}), "unrelated")
        assert tiers["must_have"] == ["SQL"]

    @pytest.mark.xfail(strict=True, reason="known bug: title casing destroys canonical names, seen live as 'Power Bi'")
    def test_canonical_casing_survives(self):
        tiers = ai.compute_skill_tiers(Counter({"Power BI": 3}), "unrelated")
        assert tiers["must_have"] == ["Power BI"]


#pipeline

class TestRunAiPipeline:
    def test_empty_extraction_returns_five_item_tuple_without_extra_calls(self):
        with patch.object(ai, "_call_groq", return_value=None) as mock_call:
            result = ai.run_ai_pipeline("analyst", ["desc"])
        assert len(result) == 5
        skill_result, categories, insight, soft_skills, tiers = result
        assert skill_result.is_empty()
        assert categories is None
        assert insight.available is False
        assert soft_skills == []
        assert tiers == {}
        #only the single extraction call happened
        assert mock_call.call_count == 1

    def test_full_run_returns_populated_results(self):
        def fake_groq(prompt, max_tokens):
            if "technical skill mentioned" in prompt:
                return "1: Python, SQL"
            if "Categorize" in prompt:
                return json.dumps({"Programming": ["Python"], "Data": ["SQL"]})
            if "soft skills" in prompt:
                return "Communication, Curiosity"
            return "Insight text."

        with patch.object(ai, "_call_groq", side_effect=fake_groq):
            skill_result, categories, insight, soft_skills, tiers = ai.run_ai_pipeline("analyst", ["desc"])

        assert skill_result.total == 2
        assert categories == {"Programming": ["Python"], "Data": ["SQL"]}
        assert insight.text == "Insight text."
        assert soft_skills == ["Communication", "Curiosity"]
        assert tiers["must_have"]


#the groq wrapper

def fake_response(content, finish_reason="stop"):
    from types import SimpleNamespace as NS
    return NS(choices=[NS(message=NS(content=content), finish_reason=finish_reason)])


class TestCallGroq:
    def test_returns_stripped_content(self):
        with patch.object(ai._client.chat.completions, "create", return_value=fake_response("  hello  ")):
            assert ai._call_groq("prompt", 50) == "hello"

    def test_token_cap_includes_reasoning_headroom(self):
        with patch.object(ai._client.chat.completions, "create", return_value=fake_response("x")) as mock_create:
            ai._call_groq("prompt", 50)
        assert mock_create.call_args.kwargs["max_tokens"] == 50 + ai.GROQ_REASONING_HEADROOM

    def test_gpt_oss_models_get_reasoning_effort(self):
        with patch.object(ai, "GROQ_MODEL", "openai/gpt-oss-120b"):
            with patch.object(ai._client.chat.completions, "create", return_value=fake_response("x")) as mock_create:
                ai._call_groq("prompt", 50)
        assert mock_create.call_args.kwargs["extra_body"] == {"reasoning_effort": ai.GROQ_REASONING_EFFORT}

    def test_other_models_do_not_get_reasoning_effort(self):
        with patch.object(ai, "GROQ_MODEL", "some/other-model"):
            with patch.object(ai._client.chat.completions, "create", return_value=fake_response("x")) as mock_create:
                ai._call_groq("prompt", 50)
        assert "extra_body" not in mock_create.call_args.kwargs

    @pytest.mark.parametrize("content", [None, "", "   "])
    def test_empty_content_is_a_failure_and_is_logged(self, content, caplog):
        response = fake_response(content, finish_reason="length")
        with patch.object(ai._client.chat.completions, "create", return_value=response):
            with caplog.at_level("WARNING"):
                assert ai._call_groq("prompt", 50) is None
        assert "finish_reason=length" in caplog.text

    def test_exception_returns_none_and_is_logged(self, caplog):
        with patch.object(ai._client.chat.completions, "create", side_effect=RuntimeError("boom")):
            with caplog.at_level("ERROR"):
                assert ai._call_groq("prompt", 50) is None
        assert "boom" in caplog.text