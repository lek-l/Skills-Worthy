import logging
from html import escape
import streamlit as st
import plotly.express as px
import state
from api import fetch_jobs, JobFetchError
from analysis import process_jobs, build_skill_dataframe, compute_skill_gap
from ai import run_ai_pipeline, generate_roadmap
from config import MIN_SEARCH_LENGTH, MAX_SEARCH_LENGTH, MAX_MISSING_SKILLS_SHOWN

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Skills Worthy", layout="wide")
state.initialize()

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

    :root {
        --bg:           #1a1d24;
        --bg-mid:       #22262f;
        --bg-surface:   #2a2e38;
        --bg-hover:     #2e3340;
        --text:         #f0f2f5;
        --text-muted:   #8a9099;
        --text-faint:   #4a5060;
        --border:       #2e3340;
        --border-mid:   #3a3f4a;
        --ivory:        #e8d876;
        --ivory-dim:    #c9ba5e;
        --amber:        #c17f3a;
        --amber-pale:   #2a1f10;
        --green-soft:   #5a9465;
        --green-pale:   #1a2e1f;
        --green-border: #3a6645;
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
        border-bottom: 1px solid var(--border-mid) !important;
        border-radius: 0 !important;
        color: var(--text) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 1rem !important;
        padding: 0.75rem 0 !important;
        transition: border-color 0.2s !important;
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

    .stTextInput > div > div {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
    }

    .stTextInput > div { background: transparent !important; }

    div[data-baseweb="input"] {
        background: transparent !important;
        border: none !important;
    }

    .stTextInput { margin-top: 0 !important; }
    div[data-testid="column"] { padding: 0 0.5rem !important; }

    .stSpinner > div { border-top-color: var(--ivory) !important; }

    .stWarning {
        background: var(--amber-pale) !important;
        border: 1px solid var(--amber) !important;
        border-radius: 0 !important;
        color: var(--amber) !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    }

    .stWarning p { color: var(--amber) !important; }

    .stError {
        background: #1f1212 !important;
        border: 1px solid #d9534f !important;
        border-radius: 0 !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    }

    .js-plotly-plot .plotly .modebar { display: none !important; }
    .stPlotlyChart { background: transparent !important; }

    .hero {
        background: var(--bg) !important;
        padding: 5rem 2rem 4rem !important;
        text-align: center !important;
    }

    .hero-eyebrow {
        font-size: 0.65rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.24em !important;
        text-transform: uppercase !important;
        color: var(--text-faint) !important;
        margin-bottom: 1.25rem !important;
        display: block !important;
    }

    .hero-title {
        font-size: 4rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.04em !important;
        color: var(--text) !important;
        line-height: 1 !important;
        margin-bottom: 1rem !important;
    }

    .hero-title span { color: var(--ivory) !important; }

    .hero-sub {
        font-size: 0.95rem !important;
        color: var(--text-faint) !important;
        margin-bottom: 2.5rem !important;
        display: block !important;
    }

    .try-line {
        font-size: 0.65rem !important;
        color: var(--text-faint) !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        margin-top: 1rem !important;
        text-align: center !important;
        display: block !important;
    }

    .try-line span { color: var(--ivory-dim) !important; }

    .page-content {
        max-width: 860px !important;
        margin: 0 auto !important;
        padding: 0 3rem !important;
    }

    .role-title {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.03em !important;
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
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: var(--ivory) !important;
        line-height: 1 !important;
        display: block !important;
    }

    .stat-label {
        font-size: 0.6rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.18em !important;
        text-transform: uppercase !important;
        color: var(--text-faint) !important;
        margin-top: 0.35rem !important;
        display: block !important;
    }

    .section {
        border-top: 1px solid var(--border) !important;
        padding: 3rem 0 !important;
        text-align: center !important;
    }

    .section-label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.24em !important;
        text-transform: uppercase !important;
        color: var(--ivory) !important;
        margin-bottom: 0.6rem !important;
        display: block !important;
        text-align: center !important;
    }

    .section-sub {
        font-size: 0.85rem !important;
        color: var(--text-faint) !important;
        margin-bottom: 2rem !important;
        display: block !important;
        text-align: center !important;
    }

    .insight-text {
        font-size: 1rem !important;
        color: var(--text-muted) !important;
        line-height: 1.9 !important;
        border-left: 2px solid var(--ivory) !important;
        padding-left: 1.5rem !important;
        text-align: left !important;
        max-width: 600px !important;
        margin: 0 auto !important;
    }

    .chips {
        display: flex !important;
        flex-wrap: wrap !important;
        justify-content: center !important;
        gap: 8px !important;
    }

    .chip {
        display: inline-block !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
        padding: 0.45rem 1.1rem !important;
        border: 1px solid var(--border-mid) !important;
        color: var(--text-muted) !important;
        background: var(--bg-mid) !important;
    }

    .chip-missing {
        display: inline-block !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        padding: 0.45rem 1.1rem !important;
        border: 1px solid var(--amber) !important;
        color: var(--amber) !important;
        background: var(--amber-pale) !important;
    }

    .chip-matched {
        display: inline-block !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        padding: 0.45rem 1.1rem !important;
        border: 1px solid var(--green-border) !important;
        color: var(--green-soft) !important;
        background: var(--green-pale) !important;
    }

    .overlap-wrap {
        max-width: 520px !important;
        margin: 0 auto 2rem !important;
        text-align: left !important;
    }

    .overlap-label {
        font-size: 0.62rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.16em !important;
        text-transform: uppercase !important;
        color: var(--text-faint) !important;
        margin-bottom: 0.5rem !important;
        display: block !important;
    }

    .overlap-track {
        height: 2px !important;
        background: var(--border) !important;
    }

    .overlap-fill {
        height: 100% !important;
        background: var(--ivory) !important;
    }

    .roadmap-step {
        padding: 1rem 1.25rem !important;
        margin: 0.4rem auto !important;
        border-left: 2px solid var(--ivory) !important;
        background: var(--bg-mid) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.88rem !important;
        color: var(--text-muted) !important;
        line-height: 1.75 !important;
        text-align: left !important;
        max-width: 520px !important;
        display: block !important;
    }

    .strong-match {
        display: inline-block !important;
        font-size: 0.62rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase !important;
        padding: 0.35rem 0.85rem !important;
        background: var(--green-pale) !important;
        color: var(--green-soft) !important;
        border: 1px solid var(--green-border) !important;
        margin-bottom: 1.25rem !important;
    }

    .gap-meta-label {
        font-size: 0.62rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.16em !important;
        text-transform: uppercase !important;
        color: var(--text-faint) !important;
        margin: 1.5rem 0 0.75rem !important;
        display: block !important;
        text-align: center !important;
    }

    .tier-col-label {
        font-size: 0.65rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.18em !important;
        text-transform: uppercase !important;
        margin-bottom: 1rem !important;
        display: block !important;
        text-align: center !important;
    }

    .tier-skill {
        padding: 0.45rem 0.85rem !important;
        margin: 0.3rem 0 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        display: block !important;
        text-align: left !important;
    }

    .tier-label-must { color: #e8d876 !important; }
    .tier-label-good { color: #c17f3a !important; }
    .tier-label-nice { color: #4a5060 !important; }

    .tier-skill-must { border-left: 2px solid #e8d876 !important; background: #22201a !important; color: #f0f2f5 !important; }
    .tier-skill-good { border-left: 2px solid #c17f3a !important; background: #221a10 !important; color: #f0f2f5 !important; }
    .tier-skill-nice { border-left: 2px solid #3a3f4a !important; background: #1e2028 !important; color: #8a9099 !important; }

    .app-footer {
        text-align: center !important;
        padding: 2.5rem 2rem !important;
        border-top: 1px solid var(--border) !important;
        font-size: 0.62rem !important;
        letter-spacing: 0.16em !important;
        text-transform: uppercase !important;
        color: var(--text-faint) !important;
        margin-top: 3rem !important;
    }
    </style>
""", unsafe_allow_html=True)


# ── render helpers ────────────────────────────────────────────────────────────

def _section_start(label: str, sub: str = None):
    st.markdown("<div class='page-content'><div class='section'>", unsafe_allow_html=True)
    st.markdown(f"<span class='section-label'>{label}</span>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<span class='section-sub'>{sub}</span>", unsafe_allow_html=True)

def _section_end():
    st.markdown("</div></div>", unsafe_allow_html=True)

def _render_bar_chart(skill_df):
    fig = px.bar(
        skill_df,
        x='count', y='skill',
        orientation='h',
        color='count',
        color_continuous_scale=[[0, '#2e3340'], [1, '#e8d876']]
    )
    fig.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title='frequency',
        yaxis_title='',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Plus Jakarta Sans', color='#8a9099', size=12),
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(gridcolor='#2e3340', zerolinecolor='#2e3340'),
        height=460
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

def _render_tiers(tiers: dict):
    #renders must have / good to have / nice to have columns
    #directly answers "what should I learn first?"
    must = tiers.get("must_have", [])
    good = tiers.get("good_to_have", [])
    nice = tiers.get("nice_to_have", [])

    tier_col_must, tier_col_good, tier_col_nice = st.columns(3)

    with tier_col_must:
        st.markdown(
            "<span class='tier-col-label tier-label-must'>Must Have</span>",
            unsafe_allow_html=True
        )
        for skill in must:
            st.markdown(
                f"<div class='tier-skill tier-skill-must'>{escape(skill)}</div>",
                unsafe_allow_html=True
            )

    with tier_col_good:
        st.markdown(
            "<span class='tier-col-label tier-label-good'>Good To Have</span>",
            unsafe_allow_html=True
        )
        for skill in good:
            st.markdown(
                f"<div class='tier-skill tier-skill-good'>{escape(skill)}</div>",
                unsafe_allow_html=True
            )

    with tier_col_nice:
        st.markdown(
            "<span class='tier-col-label tier-label-nice'>Nice To Have</span>",
            unsafe_allow_html=True
        )
        for skill in nice:
            st.markdown(
                f"<div class='tier-skill tier-skill-nice'>{escape(skill)}</div>",
                unsafe_allow_html=True
            )

def _render_skill_gap(gap: dict, search_term: str, missing_skills: list, user_skills: list):
    overlap_pct = gap["overlap_pct"]
    matched = gap["matched"]

    st.markdown(
        f"<div class='overlap-wrap'>"
        f"<span class='overlap-label'>Skill Overlap — {overlap_pct}%</span>"
        f"<div class='overlap-track'><div class='overlap-fill' style='width:{overlap_pct}%;'></div></div>"
        f"</div>",
        unsafe_allow_html=True
    )

    if gap["is_strong_match"]:
        st.markdown(
            "<div style='text-align:center; margin-bottom:1rem;'><span class='strong-match'>Strong Match</span></div>",
            unsafe_allow_html=True
        )

    if matched:
        st.markdown("<span class='gap-meta-label'>Skills You Have</span>", unsafe_allow_html=True)
        st.markdown(
            "<div class='chips'>" + "".join([f"<span class='chip-matched'>{escape(s)}</span>" for s in matched]) + "</div>",
            unsafe_allow_html=True
        )

    if missing_skills:
        st.markdown("<span class='gap-meta-label'>Skills You're Missing</span>", unsafe_allow_html=True)
        st.markdown(
            "<div class='chips'>" + "".join([f"<span class='chip-missing'>{escape(s)}</span>" for s in missing_skills[:MAX_MISSING_SKILLS_SHOWN]]) + "</div>",
            unsafe_allow_html=True
        )

    #roadmap is keyed on (search_term, user_skills) so it only re-calls groq when input changes
    cache_key = f"roadmap:{search_term}:{','.join(sorted(user_skills))}"
    if cache_key not in st.session_state:
        with st.spinner("building your roadmap..."):
            st.session_state[cache_key] = generate_roadmap(search_term, missing_skills, user_skills)

    roadmap = st.session_state[cache_key]
    if roadmap:
        st.markdown("<span class='gap-meta-label'>Your Learning Roadmap</span>", unsafe_allow_html=True)
        steps = [line.strip() for line in roadmap.split('\n') if line.strip()]
        for step in steps:
            st.markdown(f"<div class='roadmap-step'>{escape(step)}</div>", unsafe_allow_html=True)


# ── page layout ───────────────────────────────────────────────────────────────

#hero section
st.markdown("""
    <div class='hero'>
        <span class='hero-eyebrow'>Live Job Market Intelligence</span>
        <div class='hero-title'>Skills <span>Worthy</span></div>
        <span class='hero-sub'>Search any job field. See what the market wants right now.</span>
    </div>
""", unsafe_allow_html=True)

#search bar
_, search_col, _ = st.columns([1, 2, 1])
with search_col:
    search_term = st.text_input("", placeholder="data analyst, quant, fintech, accountant...")
    st.markdown(
        "<span class='try-line'>Try: <span>Data Analyst</span> · <span>Machine Learning</span> · <span>Data Scientist</span></span>",
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
        skill_result, categories, insight, soft_skills, tiers = run_ai_pipeline(
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
        soft_skills=soft_skills,
        processed=processed,
        tiers=tiers
    )

#read from state
results = state.get_results()
jobs = results["jobs"]
skill_result = results["skill_result"]
top_skills = results["top_skills"]
categories = results["categories"]
insight = results["insight"]
soft_skills = results["soft_skills"]
processed = results["processed"]
tiers = results["tiers"]

skill_df = build_skill_dataframe(skill_result.counts, search_term_clean)

#role title and stats
st.markdown(f"""
    <div class='page-content'>
        <div class='role-title'>{escape(search_term_clean.title())}</div>
        <div class='stat-row'>
            <div class='stat-block'>
                <span class='stat-number'>{processed.job_count}</span>
                <span class='stat-label'>Postings Fetched</span>
            </div>
            <div class='stat-block'>
                <span class='stat-number'>{len(processed.descriptions)}</span>
                <span class='stat-label'>Analyzed</span>
            </div>
            <div class='stat-block'>
                <span class='stat-number'>{len(top_skills)}</span>
                <span class='stat-label'>Skills Found</span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

#section 1 - top skills bar chart
if not skill_df.empty:
    if len(skill_df) < 3:
        _section_start("Top In-Demand Skills")
        st.markdown(
            "<p style='text-align:center; color:#4a5060; font-size:0.85rem;'>"
            "not enough specific skills found. try a more specific role — e.g. "
            "<span style='color:#e8d876;'>fintech data analyst</span> or "
            "<span style='color:#e8d876;'>fintech software engineer</span>.</p>",
            unsafe_allow_html=True
        )
        _section_end()
    else:
        _section_start("Top In-Demand Skills", "Most frequently required technical skills across live postings.")
        _render_bar_chart(skill_df)
        _section_end()

#section 2 - skill priority tiers
if tiers and any(tiers.values()):
    _section_start("Skill Priority", "What to learn first — ranked by how often employers ask for it.")
    _render_tiers(tiers)
    _section_end()

#section 3 - ai insight
if insight and insight.available:
    _section_start("AI Insight", "Generated from real job postings pulled today.")
    st.markdown(f"<p class='insight-text'>{escape(insight.text)}</p>", unsafe_allow_html=True)
    _section_end()

#section 4 - soft skills
if soft_skills:
    _section_start("Soft Skills", "Non-technical skills employers consistently look for in this role.")
    st.markdown(
        "<div class='chips'>" + "".join([f"<span class='chip'>{escape(s)}</span>" for s in soft_skills]) + "</div>",
        unsafe_allow_html=True
    )
    _section_end()

#section 5 - skill gap and roadmap
st.markdown("<div class='page-content'><div class='section'>", unsafe_allow_html=True)
st.markdown("<span class='section-label'>Skill Gap & Roadmap</span>", unsafe_allow_html=True)
st.markdown("<span class='section-sub'>Enter your current skills to see your gap and get a personalized learning path.</span>", unsafe_allow_html=True)

_, skills_col, _ = st.columns([1, 2, 1])
with skills_col:
    user_skills_input = st.text_input("your skills", placeholder="Python, SQL, Excel...")

if user_skills_input:
    user_skills = [s.strip() for s in user_skills_input.split(',') if s.strip()]
    if not user_skills:
        st.warning("please enter at least one skill.")
    else:
        gap = compute_skill_gap(top_skills, user_skills)
        _render_skill_gap(gap, search_term_clean, gap["missing"], user_skills)

st.markdown("</div></div>", unsafe_allow_html=True)

#footer
st.markdown("<div class='app-footer'>Powered by JSearch API & Groq AI</div>", unsafe_allow_html=True)
