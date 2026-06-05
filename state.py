import streamlit as st

_DEFAULTS = {
    "jobs": None,
    "last_search": None,
    "skill_result": None,
    "top_skills": [],
    "categories": None,
    "insight": None,
    "soft_skills": [],
    "processed": None,
    "tiers": {}
}

def initialize():
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            #copy mutable defaults so module-level list/dict is never mutated
            if isinstance(default, (list, dict)):
                st.session_state[key] = type(default)()
            else:
                st.session_state[key] = default

def is_new_search(query: str) -> bool:
    return st.session_state.last_search != query.strip()

def store_results(
    query: str,
    jobs: list,
    skill_result,
    top_skills: list,
    categories: dict | None,
    insight,
    soft_skills: list,
    processed,
    tiers: dict
):
    st.session_state.last_search = query
    st.session_state.jobs = jobs
    st.session_state.skill_result = skill_result
    st.session_state.top_skills = top_skills
    st.session_state.categories = categories
    st.session_state.insight = insight
    st.session_state.soft_skills = soft_skills
    st.session_state.processed = processed
    st.session_state.tiers = tiers

def get_results() -> dict:
    return {
        "jobs": st.session_state.jobs,
        "skill_result": st.session_state.skill_result,
        "top_skills": st.session_state.top_skills,
        "categories": st.session_state.categories,
        "insight": st.session_state.insight,
        "soft_skills": st.session_state.soft_skills,
        "processed": st.session_state.processed,
        "tiers": st.session_state.tiers
    }

def has_results() -> bool:
    return (
        st.session_state.last_search is not None
        and st.session_state.skill_result is not None
        and not st.session_state.skill_result.is_empty()
    )
