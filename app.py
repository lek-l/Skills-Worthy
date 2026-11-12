import logging
import re
from html import escape
import streamlit as st
import plotly.express as px
import state
from api import fetch_jobs, JobFetchError
from analysis import process_jobs, build_skill_dataframe, compute_skill_gap
from ai import run_ai_pipeline, generate_roadmap
from config import MIN_SEARCH_LENGTH, MAX_SEARCH_LENGTH, MAX_MISSING_SKILLS_SHOWN, MAX_DESCRIPTIONS

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Skills Worthy — Live Job Market Intelligence", layout="wide")
state.initialize()

#search history — stores past queries for sidebar, capped at 10
if "search_history" not in st.session_state:
    st.session_state.search_history = []

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

    :root {
        --bg:           #1a1d24;
        --bg-mid:       #22262f;
        --bg-surface:   #2a2e38;
        --text:         #f0f2f5;
        --text-muted:   #8a9099;
        --text-faint:   #4a5060;
        --ivory:        #e8d876;
        --ivory-dim:    #c9ba5e;
        --amber:        #c17f3a;
        --amber-pale:   #2a1f10;
        --green-soft:   #5a9465;
        --green-pale:   #1a2e1f;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }

    .stApp { background-color: var(--bg) !important; }
    #MainMenu, footer, header { visibility: hidden; }

    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }

    p, li {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: var(--text-muted) !important;
        font-size: 0.95rem !important;
        line-height: 1.75 !important;
    }

    input[type="text"] {
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid var(--text-faint) !important;
        border-radius: 0 !important;
        color: var(--text) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 1rem !important;
        padding: 0.75rem 0 !important;
        transition: border-color 0.3s ease, box-shadow 0.3s ease !important;
        text-align: center !important;
    }

    input[type="text"]:focus {
        border-bottom: 1px solid var(--ivory) !important;
        box-shadow: 0 1px 8px rgba(232, 216, 118, 0.08) !important;
    }

    input[type="text"]::placeholder {
        color: var(--text-faint) !important;
        text-align: center !important;
    }

    small, .stTextInput small { display: none !important; }
    .stTextInput label { display: none !important; }
    .stTextInput > div > div { border: none !important; background: transparent !important; padding: 0 !important; }
    .stTextInput > div { background: transparent !important; }
    div[data-baseweb="input"] { background: transparent !important; border: none !important; }
    .stTextInput { margin-top: 0 !important; }
    div[data-testid="column"] { padding: 0 0.5rem !important; }

    .stSpinner > div { border-top-color: var(--ivory) !important; }

    .stWarning {
        background: var(--amber-pale) !important;
        border-radius: 0 !important;
        color: var(--amber) !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    }
    .stWarning p { color: var(--amber) !important; }

    .stError {
        background: #1f1212 !important;
        border-radius: 0 !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    }

    .js-plotly-plot .plotly .modebar { display: none !important; }
    .stPlotlyChart { background: transparent !important; }

    /* sidebar */
    section[data-testid="stSidebar"] {
        background-color: #16181e !important;
        padding: 1.5rem 1rem !important;
    }

    section[data-testid="stSidebar"] .stMarkdown p {
        font-size: 0.8rem !important;
        color: var(--text-faint) !important;
    }

    .sidebar-brand {
        font-size: 1.3rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        margin-bottom: 0.25rem !important;
    }

    .sidebar-brand span { color: var(--ivory) !important; }

    .sidebar-label {
        font-size: 0.7rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin: 2rem 0 0.75rem !important;
        display: block !important;
    }

    .sidebar-item {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.82rem !important;
        color: var(--text-muted) !important;
        padding: 0.4rem 0.6rem !important;
        margin: 0.15rem 0 !important;
        display: block !important;
        background: transparent !important;
        transition: color 0.2s ease !important;
    }

    .sidebar-item:hover { color: var(--ivory) !important; }

    /* hero */
    .hero {
        background: var(--bg) !important;
        padding: 5rem 2rem 4rem !important;
        text-align: center !important;
    }

    h1.hero-title {
        font-size: 3.5rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        line-height: 1.1 !important;
        margin-bottom: 0.75rem !important;
        padding: 0 !important;
    }

    h1.hero-title span { color: var(--ivory) !important; }

    .hero-sub {
        font-size: 0.9rem !important;
        color: var(--text-faint) !important;
        margin-bottom: 2.5rem !important;
        display: block !important;
    }

    .try-line {
        font-size: 0.7rem !important;
        color: var(--text-faint) !important;
        margin-top: 1rem !important;
        text-align: center !important;
        display: block !important;
    }

    .try-line span { color: var(--ivory-dim) !important; }

    /* content */
    .page-content {
        max-width: 860px !important;
        margin: 0 auto !important;
        padding: 0 3rem !important;
    }

    .role-title {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        text-align: center !important;
        margin-bottom: 0.5rem !important;
        padding-top: 3rem !important;
    }

    .stat-row {
        display: flex !important;
        justify-content: center !important;
        gap: 3.5rem !important;
        margin: 1.25rem 0 3rem !important;
    }

    .stat-block { text-align: center !important; }

    .stat-number {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: var(--ivory) !important;
        line-height: 1 !important;
        display: block !important;
    }

    .stat-label {
        font-size: 0.65rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin-top: 0.35rem !important;
        display: block !important;
    }

    /* sections — spacing only, no dividers */
    .section {
        padding: 3rem 0 !important;
        text-align: center !important;
    }

    .section-heading {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: var(--text) !important;
        margin-bottom: 1.5rem !important;
        display: block !important;
        text-align: center !important;
    }

    /* insight */
    .insight-text {
        font-size: 0.95rem !important;
        color: var(--text-muted) !important;
        line-height: 1.9 !important;
        padding-left: 1.25rem !important;
        text-align: left !important;
        max-width: 600px !important;
        margin: 0 auto !important;
        border-left: 2px solid var(--ivory) !important;
    }

    /* tiers */
    .tier-col-label {
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.75rem !important;
        display: block !important;
        text-align: center !important;
    }

    .tier-skill {
        padding: 0.45rem 0.75rem !important;
        margin: 0.25rem 0 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        display: block !important;
        text-align: left !important;
        background: var(--bg-mid) !important;
        color: var(--text) !important;
        transition: background 0.2s ease !important;
    }

    .tier-skill:hover { background: var(--bg-surface) !important; }

    .tier-label-must { color: var(--ivory) !important; }
    .tier-label-good { color: var(--amber) !important; }
    .tier-label-nice { color: var(--text-faint) !important; }

    .tier-empty {
        font-size: 0.8rem !important;
        color: var(--text-faint) !important;
        text-align: center !important;
        padding: 0.5rem 0 !important;
    }

    /* skill gap */
    .overlap-wrap {
        max-width: 520px !important;
        margin: 0 auto 2rem !important;
        text-align: left !important;
    }

    .overlap-label {
        font-size: 0.7rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin-bottom: 0.5rem !important;
        display: block !important;
    }

    .overlap-track {
        height: 2px !important;
        background: var(--bg-surface) !important;
    }

    .overlap-fill {
        height: 100% !important;
        background: var(--ivory) !important;
    }

    .gap-label {
        font-size: 0.7rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin: 1.5rem 0 0.5rem !important;
        display: block !important;
        text-align: center !important;
    }

    .skill-list {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.88rem !important;
        line-height: 1.8 !important;
        text-align: center !important;
        max-width: 520px !important;
        margin: 0 auto !important;
    }

    .skill-matched { color: var(--green-soft) !important; }
    .skill-missing { color: var(--amber) !important; }

    .strong-match {
        display: inline-block !important;
        font-size: 0.7rem !important;
        font-weight: 500 !important;
        padding: 0.3rem 0.8rem !important;
        background: var(--green-pale) !important;
        color: var(--green-soft) !important;
        margin-bottom: 1rem !important;
    }

    .roadmap-step {
        padding: 0.75rem 1rem !important;
        margin: 0.3rem auto !important;
        background: var(--bg-mid) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.85rem !important;
        color: var(--text-muted) !important;
        line-height: 1.7 !important;
        text-align: left !important;
        max-width: 520px !important;
        display: block !important;
    }

    /* footer */
    .app-footer {
        text-align: center !important;
        padding: 2.5rem 2rem !important;
        font-size: 0.72rem !important;
        color: var(--text-faint) !important;
        margin-top: 4rem !important;
        line-height: 2.2 !important;
    }

    .app-footer a {
        color: var(--ivory-dim) !important;
        text-decoration: none !important;
    }

    .app-footer a:hover { text-decoration: underline !important; }
    </style>
""", unsafe_allow_html=True)


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("<div class='sidebar-brand'>Skills <span>Worthy</span></div>", unsafe_allow_html=True)
    st.markdown("Live job market intelligence", unsafe_allow_html=True)

    if st.session_state.search_history:
        st.markdown("<span class='sidebar-label'>Recent</span>", unsafe_allow_html=True)
        for past_query in st.session_state.search_history:
            st.markdown(
                f"<span class='sidebar-item'>{escape(past_query)}</span>",
                unsafe_allow_html=True
            )


# ── render helpers ────────────────────────────────────────────────────────────

def _section_start(heading: str):
    st.markdown("<div class='page-content'><div class='section'>", unsafe_allow_html=True)
    st.markdown(f"<span class='section-heading'>{heading}</span>", unsafe_allow_html=True)

def _section_end():
    st.markdown("</div></div>", unsafe_allow_html=True)

def _render_bar_chart(skill_df):
    fig = px.bar(
        skill_df,
        x='pct', y='skill',
        orientation='h',
        color='pct',
        color_continuous_scale=[[0, '#2e3340'], [1, '#e8d876']]
    )
    fig.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title='% of postings',
        yaxis_title='',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Plus Jakarta Sans', color='#8a9099', size=12),
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(gridcolor='#2e3340', zerolinecolor='#2e3340', range=[0, 100]),
        height=460
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

def _render_tiers(tiers: dict):
    must = tiers.get("must_have", [])
    good = tiers.get("good_to_have", [])
    nice = tiers.get("nice_to_have", [])

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("<span class='tier-col-label tier-label-must'>Must have</span>", unsafe_allow_html=True)
        if must:
            for s in must:
                st.markdown(f"<div class='tier-skill'>{escape(s)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='tier-empty'>no single skill dominates</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<span class='tier-col-label tier-label-good'>Good to have</span>", unsafe_allow_html=True)
        if good:
            for s in good:
                st.markdown(f"<div class='tier-skill'>{escape(s)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='tier-empty'>—</div>", unsafe_allow_html=True)

    with c3:
        st.markdown("<span class='tier-col-label tier-label-nice'>Nice to have</span>", unsafe_allow_html=True)
        if nice:
            for s in nice:
                st.markdown(f"<div class='tier-skill'>{escape(s)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='tier-empty'>—</div>", unsafe_allow_html=True)

def _clean_roadmap_steps(roadmap: str) -> list[str]:
    steps = []
    for line in roadmap.split('\n'):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^(Step\s+\d+:\s*)+', lambda m: m.group(0).split(':', 1)[0] + ': ', line, flags=re.IGNORECASE)
        steps.append(line)
    return steps

def _render_skill_gap(gap: dict, search_term: str, missing_skills: list, user_skills: list):
    overlap_pct = gap["overlap_pct"]
    matched = gap["matched"]

    st.markdown(
        f"<div class='overlap-wrap'>"
        f"<span class='overlap-label'>Skill overlap — {overlap_pct}%</span>"
        f"<div class='overlap-track'><div class='overlap-fill' style='width:{overlap_pct}%;'></div></div>"
        f"</div>",
        unsafe_allow_html=True
    )

    if gap["is_strong_match"]:
        st.markdown(
            "<div style='text-align:center; margin-bottom:1rem;'><span class='strong-match'>Strong match</span></div>",
            unsafe_allow_html=True
        )

    if matched:
        st.markdown("<span class='gap-label'>Skills you have</span>", unsafe_allow_html=True)
        matched_str = ", ".join([escape(s) for s in matched])
        st.markdown(f"<div class='skill-list skill-matched'>{matched_str}</div>", unsafe_allow_html=True)

    if missing_skills:
        st.markdown("<span class='gap-label'>Skills to learn</span>", unsafe_allow_html=True)
        missing_str = ", ".join([escape(s) for s in missing_skills[:MAX_MISSING_SKILLS_SHOWN]])
        st.markdown(f"<div class='skill-list skill-missing'>{missing_str}</div>", unsafe_allow_html=True)

    cache_key = f"roadmap:{search_term}:{','.join(sorted(user_skills))}"
    if cache_key not in st.session_state:
        with st.spinner("building your roadmap..."):
            st.session_state[cache_key] = generate_roadmap(search_term, missing_skills, user_skills)

    roadmap = st.session_state[cache_key]
    if roadmap:
        st.markdown("<span class='gap-label'>Learning roadmap</span>", unsafe_allow_html=True)
        steps = _clean_roadmap_steps(roadmap)
        for step in steps:
            st.markdown(f"<div class='roadmap-step'>{escape(step)}</div>", unsafe_allow_html=True)


# ── page layout ───────────────────────────────────────────────────────────────

st.markdown("""
    <div class='hero'>
        <h1 class='hero-title'>Skills <span>Worthy</span></h1>
        <span class='hero-sub'>Search any role. See what the market wants right now.</span>
    </div>
""", unsafe_allow_html=True)

_, search_col, _ = st.columns([1, 2, 1])
with search_col:
    search_term = st.text_input("search", label_visibility="collapsed", placeholder="data analyst, accountant, marketing manager...")
    st.markdown(
        "<span class='try-line'>Try <span>Data Analyst</span> · <span>Accountant</span> · <span>Software Engineer</span></span>",
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

if not search_term:
    st.stop()

search_term_clean = search_term.strip()

if len(search_term_clean) < MIN_SEARCH_LENGTH:
    st.warning(f"please enter at least {MIN_SEARCH_LENGTH} characters.")
    st.stop()

if len(search_term_clean) > MAX_SEARCH_LENGTH:
    st.warning(f"search term is too long. keep it under {MAX_SEARCH_LENGTH} characters.")
    st.stop()

if not re.search(r'[a-zA-Z]', search_term_clean):
    st.warning("please enter a valid job title.")
    st.stop()

if state.is_new_search(search_term_clean):
    with st.spinner(f"scanning live postings for '{search_term_clean}'..."):
        try:
            jobs = fetch_jobs(search_term_clean)
        except JobFetchError as e:
            st.error(f"could not fetch jobs: {e}")
            st.stop()
        except Exception as e:
            logger.error("unexpected fetch error: %s", e)
            st.error("could not reach job data. check your connection and try again.")
            st.stop()

    if not jobs:
        st.warning(f"no postings found for '{search_term_clean}'. try a broader search term.")
        st.stop()

    processed = process_jobs(jobs, search_term_clean)

    if not processed.has_descriptions:
        st.warning("job postings found but no descriptions available to analyze.")
        st.stop()

    with st.spinner("analyzing job market..."):
        skill_result, categories, insight, tiers = run_ai_pipeline(
            search_term_clean,
            processed.descriptions
        )

    if skill_result.is_empty():
        st.warning("could not extract skills from these postings. try a different search term.")
        st.stop()

    top_skills = [skill for skill, _ in skill_result.counts.most_common(20)]

    state.store_results(
        query=search_term_clean,
        jobs=jobs,
        skill_result=skill_result,
        top_skills=top_skills,
        categories=categories,
        insight=insight,
        soft_skills=[],
        processed=processed,
        tiers=tiers
    )

    #add to search history — most recent first, no duplicates, cap at 10
    if search_term_clean in st.session_state.search_history:
        st.session_state.search_history.remove(search_term_clean)
    st.session_state.search_history.insert(0, search_term_clean)
    st.session_state.search_history = st.session_state.search_history[:10]

#read from state
results = state.get_results()
jobs = results["jobs"]
skill_result = results["skill_result"]
top_skills = results["top_skills"]
insight = results["insight"]
processed = results["processed"]
tiers = results["tiers"]

total_analyzed = min(len(processed.descriptions), MAX_DESCRIPTIONS)
skill_df = build_skill_dataframe(skill_result.counts, search_term_clean, total_analyzed)

#role title and stats
st.markdown(f"""
    <div class='page-content'>
        <div class='role-title'>{escape(search_term_clean.title())}</div>
        <div class='stat-row'>
            <div class='stat-block'>
                <span class='stat-number'>{processed.job_count}</span>
                <span class='stat-label'>Postings fetched</span>
            </div>
            <div class='stat-block'>
                <span class='stat-number'>{total_analyzed}</span>
                <span class='stat-label'>Scanned</span>
            </div>
            <div class='stat-block'>
                <span class='stat-number'>{len(skill_result.counts)}</span>
                <span class='stat-label'>Skills extracted</span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

#section 1 — bar chart with percentages
if not skill_df.empty:
    if len(skill_df) < 3:
        _section_start("Top in-demand skills")
        st.markdown(
            "<p style='text-align:center; color:#4a5060; font-size:0.85rem;'>"
            "not enough skills found — try a more specific role like "
            f"<span style='color:#e8d876;'>{escape(search_term_clean)} analyst</span> or "
            f"<span style='color:#e8d876;'>{escape(search_term_clean)} engineer</span></p>",
            unsafe_allow_html=True
        )
        _section_end()
    else:
        _section_start("Top in-demand skills")
        _render_bar_chart(skill_df)
        _section_end()

#section 2 — skill priority tiers
if tiers and any(tiers.values()):
    _section_start("Skill priority")
    _render_tiers(tiers)
    _section_end()

#section 3 — skill gap and roadmap
st.markdown("<div class='page-content'><div class='section'>", unsafe_allow_html=True)
st.markdown("<span class='section-heading'>Skill gap</span>", unsafe_allow_html=True)

_, skills_col, _ = st.columns([1, 2, 1])
with skills_col:
    user_skills_input = st.text_input("your skills", label_visibility="collapsed", placeholder="Python, SQL, Excel...")

if user_skills_input:
    user_skills = [s.strip() for s in user_skills_input.split(',') if s.strip()]
    if not user_skills:
        st.warning("please enter at least one skill.")
    else:
        gap = compute_skill_gap(top_skills, user_skills)
        _render_skill_gap(gap, search_term_clean, gap["missing"], user_skills)

st.markdown("</div></div>", unsafe_allow_html=True)

#section 4 — ai insight
if insight and insight.available:
    _section_start("Market insight")
    st.markdown(f"<p class='insight-text'>{escape(insight.text)}</p>", unsafe_allow_html=True)
    _section_end()

#footer
st.markdown("""
    <div class='app-footer'>
        <a href='https://github.com/lek-l/Skills-Worthy' target='_blank'>GitHub</a>
        &nbsp;&middot;&nbsp;
        <a href='https://www.linkedin.com/in/lekha-londhe/' target='_blank'>LinkedIn</a>
        <br>
        Searches are not stored. Descriptions are sent to Groq for analysis.
    </div>
""", unsafe_allow_html=True)