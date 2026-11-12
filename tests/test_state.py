import sys
import types

import pytest


class FakeSessionState(dict):
    #minimal stand in for streamlit session state, supports key and attribute access
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def state(monkeypatch):
    #stub the streamlit module so these tests need no streamlit install or runtime
    fake_st = types.ModuleType("streamlit")
    fake_st.session_state = FakeSessionState()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    sys.modules.pop("state", None)
    import state as state_module
    yield state_module
    sys.modules.pop("state", None)


class FakeSkillResult:
    def __init__(self, empty):
        self._empty = empty

    def is_empty(self):
        return self._empty


def store(state, query="data analyst", skill_result=None):
    state.store_results(
        query=query, jobs=[1], skill_result=skill_result or FakeSkillResult(False),
        top_skills=["SQL"], categories={"Data": ["SQL"]}, insight="i",
        soft_skills=["x"], processed="p", tiers={"must_have": ["SQL"]},
    )


class TestState:
    def test_initialize_sets_every_default(self, state):
        state.initialize()
        assert state.st.session_state["last_search"] is None
        assert state.st.session_state["top_skills"] == []
        assert state.st.session_state["tiers"] == {}

    def test_initialize_does_not_overwrite_existing_values(self, state):
        state.st.session_state["last_search"] = "kept"
        state.initialize()
        assert state.st.session_state["last_search"] == "kept"

    def test_initialize_gives_each_session_its_own_mutable_defaults(self, state):
        state.initialize()
        state.st.session_state["top_skills"].append("SQL")
        assert state._DEFAULTS["top_skills"] == []

    def test_is_new_search_true_before_any_search(self, state):
        state.initialize()
        assert state.is_new_search("data analyst") is True

    def test_is_new_search_ignores_surrounding_whitespace(self, state):
        state.initialize()
        store(state, query="data analyst")
        assert state.is_new_search("  data analyst  ") is False
        assert state.is_new_search("accountant") is True

    def test_store_then_get_round_trips(self, state):
        state.initialize()
        store(state)
        results = state.get_results()
        assert results["top_skills"] == ["SQL"]
        assert results["tiers"] == {"must_have": ["SQL"]}
        assert set(results) == set(state._DEFAULTS) - {"last_search"}

    def test_has_results_false_initially(self, state):
        state.initialize()
        assert state.has_results() is False

    def test_has_results_true_after_store(self, state):
        state.initialize()
        store(state)
        assert state.has_results() is True

    def test_has_results_false_when_extraction_was_empty(self, state):
        state.initialize()
        store(state, skill_result=FakeSkillResult(True))
        assert state.has_results() is False
