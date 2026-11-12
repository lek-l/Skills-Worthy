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

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

    :root {
        --bg:           #1a1d24;
        --bg-card:      #22262f;
        --bg-surface:   #2a2e38;
        --text:         #f0f2f5;
        --text-muted:   #8a9099;
        --text-faint:   #4a5060;
        --ivory:        #e8d876;
        --ivory-dim:    #c9ba5e;
        --amber:        #c17f3a;
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
        max-width: 1060px !important;
        margin: 0 auto !important;
        padding: 0 2.5rem !important;
    }

    p, li {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: var(--text-muted) !important;
        font-size: 0.95rem !important;
        line-height: 1.75 !important;
    }

    /* search input */
    input[type="text"] {
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid var(--text-faint) !important;
        border-radius: 0 !important;
        color: var(--text) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.95rem !important;
        padding: 0.6rem 0 !important;
        transition: border-color 0.3s ease !important;
        text-align: center !important;
    }

    input[type="text"]:focus {
        border-bottom: 1px solid var(--ivory) !important;
        box-shadow: none !important;
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
    div[data-testid="column"] { padding: 0 0.75rem !important; }

    /* spinner centered */
    .stSpinner { text-align: center !important; }
    .stSpinner > div { border-top-color: var(--ivory) !important; margin: 0 auto !important; }

    .stWarning {
        background: rgba(193, 127, 58, 0.08) !important;
        border-radius: 4px !important;
        color: var(--amber) !important;
    }
    .stWarning p { color: var(--amber) !important; }

    .stError {
        background: rgba(217, 83, 79, 0.08) !important;
        border-radius: 4px !important;
    }

    .js-plotly-plot .plotly .modebar { display: none !important; }
    .stPlotlyChart { background: transparent !important; }

    /* hide sidebar */
    section[data-testid="stSidebar"] { display: none !important; }

    /* hero */
    .hero {
        padding: 5rem 0 3.5rem !important;
        text-align: center !important;
    }

    h1.hero-title {
        font-size: 3rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        line-height: 1.15 !important;
        margin: 0 0 0.5rem !important;
        padding: 0 !important;
    }

    h1.hero-title span { color: var(--ivory) !important; }

    .hero-sub {
        font-size: 0.88rem !important;
        color: var(--text-faint) !important;
        margin-bottom: 2rem !important;
        display: block !important;
    }

    .try-line {
        font-size: 0.7rem !important;
        color: var(--text-faint) !important;
        margin-top: 0.75rem !important;
        text-align: center !important;
        display: block !important;
    }

    .try-line span { color: var(--ivory-dim) !important; }

    /* role header */
    .role-title {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        text-align: center !important;
        padding-top: 2rem !important;
        margin-bottom: 0.3rem !important;
    }

    .stat-row {
        display: flex !important;
        justify-content: center !important;
        gap: 2.5rem !important;
        margin: 0.8rem 0 0 !important;
    }

    .stat-block { text-align: center !important; }

    .stat-number {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: var(--ivory) !important;
        line-height: 1 !important;
        display: block !important;
    }

    .stat-label {
        font-size: 0.6rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin-top: 0.25rem !important;
        display: block !important;
    }

    /* section headings */
    .s-heading {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        color: var(--ivory) !important;
        margin: 3rem 0 1.25rem !important;
        display: block !important;
    }

    .s-heading-inline {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        color: var(--ivory) !important;
        margin: 0 0 1.25rem !important;
        display: block !important;
    }

    /* tiers */
    .tier-col-label {
        font-size: 0.68rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.5rem !important;
        display: block !important;
    }

    .tier-label-must { color: var(--ivory) !important; }
    .tier-label-good { color: var(--amber) !important; }
    .tier-label-nice { color: var(--text-faint) !important; }

    .tier-skill {
        padding: 0.4rem 0.6rem !important;
        margin: 0.2rem 0 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        display: block !important;
        text-align: left !important;
        background: var(--bg-card) !important;
        color: var(--text-muted) !important;
        border-radius: 4px !important;
    }

    .tier-empty {
        font-size: 0.75rem !important;
        color: var(--text-faint) !important;
        padding: 0.5rem 0 !important;
    }

    /* skill gap */
    .overlap-wrap {
        max-width: 100% !important;
        margin: 0 0 1rem !important;
        text-align: left !important;
    }

    .overlap-label {
        font-size: 0.68rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin-bottom: 0.35rem !important;
        display: block !important;
    }

    .overlap-track {
        height: 3px !important;
        background: var(--bg-surface) !important;
        border-radius: 2px !important;
    }

    .overlap-fill {
        height: 100% !important;
        background: var(--ivory) !important;
        border-radius: 2px !important;
    }

    .gap-label {
        font-size: 0.68rem !important;
        font-weight: 500 !important;
        color: var(--text-faint) !important;
        margin: 1rem 0 0.3rem !important;
        display: block !important;
    }

    .skill-list {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.83rem !important;
        line-height: 1.8 !important;
    }

    .skill-matched { color: var(--green-soft) !important; }
    .skill-missing { color: var(--amber) !important; }

    .strong-match {
        display: inline-block !important;
        font-size: 0.68rem !important;
        font-weight: 500 !important;
        padding: 0.2rem 0.6rem !important;
        background: var(--green-pale) !important;
        color: var(--green-soft) !important;
        border-radius: 3px !important;
        margin-bottom: 0.5rem !important;
    }

    .roadmap-step {
        padding: 0.5rem 0.75rem !important;
        margin: 0.2rem 0 !important;
        background: var(--bg-card) !important;
        border-radius: 4px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.8rem !important;
        color: var(--text-muted) !important;
        line-height: 1.7 !important;
        text-align: left !important;
        display: block !important;
    }

    /* insight */
    .insight-text {
        font-size: 0.88rem !important;
        color: var(--text-muted) !important;
        line-height: 1.85 !important;
        text-align: left !important;
    }

    /* footer */
    .app-footer {
        text-align: center !important;
        padding: 3rem 0 2rem !important;
        font-size: 0.7rem !important;
        color: var(--text-faint) !important;
        margin-top: 4rem !important;
        line-height: 2 !important;
    }

    .app-footer a {
        color: var(--ivory-dim) !important;
        text-decoration: none !important;
    }

    .app-footer a:hover { text-decoration: underline !important; }
    </style>
""", unsafe_allow_html=True)


# ── render helpers ────────────────────────────────────────────────────────────

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
        font=dict(family='Plus Jakarta Sans', color='#8a9099', size=11),
        coloraxis_showscale=False,
        margin=dict(l=0, r=10, t=0, b=0),
        xaxis=dict(gridcolor='#2a2e38', zerolinecolor='#2a2e38', range=[0, 100]),
        height=420
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

def _render_tiers_stacked(tiers: dict):
    #renders all three tiers vertically in a single column
    for label, key, color_class in [
        ("Must have", "must_have", "tier-label-must"),
        ("Good to have", "good_to_have", "tier-label-good"),
        ("Nice to have", "nice_to_have", "tier-label-nice"),
    ]:
        skills = tiers.get(key, [])
        st.markdown(f"<span class='tier-col-label {color_class}'>{label}</span>", unsafe_allow_html=True)
        if skills:
            for s in skills:
                st.markdown(f"<div class='tier-skill'>{escape(s)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='tier-empty'>—</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

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
        st.markdown("<span class='strong-match'>Strong match</span>", unsafe_allow_html=True)

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

#hero
st.markdown("""
    <div class='hero'>
        <h1 class='hero-title'>Skills <span>Worthy</span></h1>
        <span class='hero-sub'>Search any role. See what the market wants right now.</span>
    </div>
""", unsafe_allow_html=True)

#search bar
_, search_col, _ = st.columns([1.5, 2, 1.5])
with search_col:
    search_term = st.text_input("search", label_visibility="collapsed", placeholder="data analyst, accountant, marketing manager...")
    st.markdown(
        "<span class='try-line'>Try <span>Data Analyst</span> · <span>Accountant</span> · <span>Software Engineer</span></span>",
        unsafe_allow_html=True
    )

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

#role header and stats
st.markdown(f"""
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
""", unsafe_allow_html=True)

#row 1 — bar chart (left) + skill priority tiers (right)
st.markdown("<span class='s-heading' style='text-align:center;'>Top in-demand skills</span>", unsafe_allow_html=True)

if not skill_df.empty and len(skill_df) >= 3:
    chart_col, tier_col = st.columns([3, 1.5])

    with chart_col:
        _render_bar_chart(skill_df)

    with tier_col:
        st.markdown("<span class='s-heading-inline'>Skill priority</span>", unsafe_allow_html=True)
        if tiers and any(tiers.values()):
            _render_tiers_stacked(tiers)
        else:
            st.markdown("<p style='color:#4a5060; font-size:0.82rem;'>not enough data to rank priorities</p>", unsafe_allow_html=True)

elif not skill_df.empty:
    st.markdown(
        "<p style='text-align:center; color:#4a5060; font-size:0.85rem;'>"
        "not enough skills found — try a more specific role like "
        f"<span style='color:#e8d876;'>{escape(search_term_clean)} analyst</span> or "
        f"<span style='color:#e8d876;'>{escape(search_term_clean)} engineer</span></p>",
        unsafe_allow_html=True
    )

#row 2 — skill gap (left) + market insight (right)
gap_col, insight_col = st.columns([3, 2])

with gap_col:
    st.markdown("<span class='s-heading-inline' style='margin-top:3rem;'>Skill gap</span>", unsafe_allow_html=True)
    user_skills_input = st.text_input("your skills", label_visibility="collapsed", placeholder="Python, SQL, Excel...")

    if user_skills_input:
        user_skills = [s.strip() for s in user_skills_input.split(',') if s.strip()]
        if not user_skills:
            st.warning("please enter at least one skill.")
        else:
            gap = compute_skill_gap(top_skills, user_skills)
            _render_skill_gap(gap, search_term_clean, gap["missing"], user_skills)

with insight_col:
    if insight and insight.available:
        st.markdown("<span class='s-heading-inline' style='margin-top:3rem;'>Market insight</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='insight-text'>{escape(insight.text)}</p>", unsafe_allow_html=True)

#footer
st.markdown("""
    <div class='app-footer'>
        <a href='https://github.com/lek-l/Skills-Worthy' target='_blank'>GitHub</a>
        &nbsp;&middot;&nbsp;
        <a href='https://linkedin.com/in/lekha-londhe' target='_blank'>LinkedIn</a>
        <br>
        Searches are not stored. Descriptions are sent to Groq for analysis.
    </div>
""", unsafe_allow_html=True)