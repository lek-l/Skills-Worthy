import logging
import re
from html import escape
import streamlit as st
import plotly.express as px
import state
from api import fetch_jobs, JobFetchError
from analysis import process_jobs, build_skill_dataframe, compute_skill_gap, parse_roadmap_steps
from ai import run_ai_pipeline, generate_roadmap
from config import MIN_SEARCH_LENGTH, MAX_SEARCH_LENGTH, MAX_MISSING_SKILLS_SHOWN, MAX_DESCRIPTIONS

logger = logging.getLogger(__name__)

MAX_USER_SKILLS = 30
MAX_USER_SKILLS_CHARS = 500


#shared across sessions: the same role searched twice within an hour costs one api round-trip
#exceptions (JobFetchError) are not cached, so failures retry on the next search
@st.cache_data(ttl=3600, show_spinner=False, max_entries=200)
def _cached_fetch_jobs(query_key: str) -> list:
    return fetch_jobs(query_key)


TRENDING_ROLES = [
    "Data Analyst", "Software Engineer", "Product Manager", "Accountant",
    "UX Designer", "Cloud Engineer", "Nurse", "Marketing Manager",
]

st.set_page_config(page_title="Skills Worthy", layout="wide")
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
        max-width: 1100px !important;
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
    [data-testid="InputInstructions"] { display: none !important; }

    /* pill search bar (home search only) */
    .st-key-hero_search {
        background: var(--bg-surface) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 999px !important;
        padding: 0.35rem 0.35rem 0.35rem 1.6rem !important;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35) !important;
        transition: border-color 0.2s ease !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }
    .st-key-hero_search:focus-within {
        border-color: rgba(232, 216, 118, 0.45) !important;
    }
    .st-key-hero_search .stTextInput { flex: 1 1 auto !important; min-width: 0 !important; }

    /* trending role chips */
    .trending-label {
        text-align: center !important;
        font-size: 0.7rem !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        color: var(--text-muted) !important;
        margin: 1.6rem 0 0.6rem !important;
    }
    .st-key-trending { max-width: 720px !important; margin: 0 auto !important; flex-wrap: wrap !important; }
    .st-key-trending .stButton button {
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.10) !important;
        border-radius: 999px !important;
        color: var(--text-muted) !important;
        font-size: 0.8rem !important;
        padding: 0.3rem 0.95rem !important;
        min-height: 0 !important;
        transition: all 0.2s ease !important;
    }
    .st-key-trending .stButton button p { font-size: 0.8rem !important; color: inherit !important; margin: 0 !important; }
    .st-key-trending .stButton button:hover {
        border-color: var(--ivory) !important;
        color: var(--ivory) !important;
        background: rgba(232, 216, 118, 0.06) !important;
    }

    /* how it works row (landing only) */
    .how-row {
        display: grid !important;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 1.25rem !important;
        max-width: 860px !important;
        margin: 3rem auto 2rem !important;
    }
    .how-step {
        background: var(--bg-card) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        padding: 1.4rem 1.4rem 1.5rem !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 0.35rem !important;
    }
    .how-num { color: var(--ivory) !important; font-size: 0.75rem !important; font-weight: 600 !important; letter-spacing: 0.1em !important; }
    .how-title { color: var(--text) !important; font-size: 1rem !important; font-weight: 600 !important; }
    .how-text { color: var(--text-muted) !important; font-size: 0.85rem !important; line-height: 1.6 !important; }
    @media (max-width: 720px) {
        .how-row { grid-template-columns: 1fr !important; margin-top: 2.5rem !important; }
    }
    .st-key-hero_search input[type="text"] {
        border: none !important;
        color: var(--text) !important;
        font-weight: 500 !important;
        font-size: 1.05rem !important;
        text-align: left !important;
        padding: 0.5rem 0 !important;
        caret-color: var(--ivory) !important;
    }
    .st-key-hero_search input[type="text"]:focus { border: none !important; }
    .st-key-hero_search input[type="text"]::placeholder {
        color: var(--text-muted) !important;
        opacity: 1 !important;
        text-align: left !important;
    }
    .st-key-hero_search .stButton button {
        width: 3.2rem !important;
        height: 3.2rem !important;
        min-height: 3.2rem !important;
        border-radius: 50% !important;
        padding: 0 !important;
        background: var(--ivory) !important;
        border: none !important;
        color: var(--bg) !important;
        box-shadow: -8px 0 16px rgba(0, 0, 0, 0.3) !important;
        transition: transform 0.15s ease !important;
    }
    .st-key-hero_search .stButton button:hover { transform: scale(1.05) !important; background: var(--ivory-dim) !important; color: var(--bg) !important; }
    .st-key-hero_search .stButton button span[data-testid="stIconMaterial"] { font-size: 1.5rem !important; }
    .stTextInput label { display: none !important; }
    .stTextInput > div > div { border: none !important; background: transparent !important; padding: 0 !important; }
    .stTextInput > div { background: transparent !important; }
    div[data-baseweb="input"] { background: transparent !important; border: none !important; }
    .stTextInput { margin-top: 0 !important; }
    div[data-testid="column"] { padding: 0 0.5rem !important; }

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

    section[data-testid="stSidebar"] { display: none !important; }

    /* tabs styling */
    /* tabs: segmented pill, same shape as the search bar */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem !important;
        width: fit-content !important;
        margin: 0 auto 2rem !important;
        padding: 0.3rem !important;
        background: var(--bg-card) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 999px !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: var(--text-muted) !important;
        padding: 0.55rem 1.4rem !important;
        height: auto !important;
        background: transparent !important;
        border: none !important;
        border-radius: 999px !important;
        transition: all 0.2s ease !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text) !important;
    }

    .stTabs [aria-selected="true"] {
        color: var(--bg) !important;
        background: var(--ivory) !important;
    }
    .stTabs [aria-selected="true"] p { color: var(--bg) !important; font-weight: 600 !important; }
    .stTabs [data-baseweb="tab"] p { color: inherit !important; font-size: 0.82rem !important; margin: 0 !important; }

    .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* hero */
    .hero {
        padding: 9vh 0 1.25rem !important;
        text-align: center !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        margin: 0 auto !important;
    }

    .hero h1.hero-title, .hero .hero-sub {
        text-align: center !important;
        width: 100% !important;
    }

    h1.hero-title {
        font-size: 3rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        line-height: 1.15 !important;
        margin: 0 0 0.5rem !important;
        padding: 0 !important;
        align-items: center !important;
    }

    h1.hero-title span { color: var(--ivory) !important; }

    /* hide streamlit's heading anchor icon so it doesn't push the title off-center */
    .hero [data-testid="stHeaderActionElements"], .hero h1 a { display: none !important; }

    .hero-sub {
        font-size: 0.88rem !important;
        color: var(--text-muted) !important;
        margin-bottom: 0 !important;
        display: block !important;
    }


    /* ── results page: same language as the landing (cards, pills, eyebrow labels) ── */

    /* compact hero once a role is searched */
    .hero.compact { padding: 2.2rem 0 1rem !important; }
    .hero.compact h1.hero-title { font-size: 1.6rem !important; margin-bottom: 0.2rem !important; }
    .hero.compact .hero-sub { font-size: 0.78rem !important; }

    /* small uppercase label used everywhere */
    .eyebrow {
        display: block !important;
        font-size: 0.68rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        color: var(--text-muted) !important;
        margin: 0 0 0.75rem !important;
    }
    .eyebrow.center { text-align: center !important; }
    .eyebrow.must { color: var(--ivory) !important; }
    .eyebrow.good { color: var(--amber) !important; }

    /* role header */
    .role-title {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        text-align: center !important;
        margin: 2rem 0 1.2rem !important;
    }

    /* stat cards */
    .stat-row {
        display: grid !important;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 1.25rem !important;
        max-width: 760px !important;
        margin: 0 auto 2.2rem !important;
    }
    .stat-block {
        background: var(--bg-card) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        padding: 1.1rem 1rem !important;
        text-align: center !important;
    }
    .stat-number {
        font-size: 1.7rem !important;
        font-weight: 700 !important;
        color: var(--ivory) !important;
        line-height: 1 !important;
        display: block !important;
    }
    .stat-label {
        font-size: 0.66rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        color: var(--text-muted) !important;
        margin-top: 0.5rem !important;
        display: block !important;
    }

    /* generic card for streamlit containers */
    .st-key-chart_card, .st-key-tier_must, .st-key-tier_good, .st-key-tier_nice,
    .st-key-overlap_card, .st-key-gap_have, .st-key-gap_learn, .st-key-insight_card {
        background: var(--bg-card) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        padding: 1.3rem 1.4rem !important;
    }

    /* skill chips (tiers, skill gap) */
    .chip-wrap { display: flex !important; flex-wrap: wrap !important; gap: 0.45rem !important; }
    .chip {
        display: inline-block !important;
        padding: 0.3rem 0.85rem !important;
        border-radius: 999px !important;
        border: 1px solid rgba(255, 255, 255, 0.10) !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        color: var(--text-muted) !important;
        background: transparent !important;
        white-space: nowrap !important;
    }
    .chip.must { border-color: rgba(232, 216, 118, 0.45) !important; color: var(--ivory) !important; background: rgba(232, 216, 118, 0.06) !important; }
    .chip.good { border-color: rgba(193, 127, 58, 0.45) !important; color: #d9995a !important; background: rgba(193, 127, 58, 0.06) !important; }
    .chip.have { border-color: rgba(90, 148, 101, 0.5) !important; color: #7fbf8a !important; background: rgba(90, 148, 101, 0.08) !important; }
    .chip.learn { border-color: rgba(193, 127, 58, 0.45) !important; color: #d9995a !important; background: rgba(193, 127, 58, 0.06) !important; }
    .chip-empty { font-size: 0.8rem !important; color: var(--text-muted) !important; }

    /* skill gap */
    .gap-intro { text-align: center !important; font-size: 0.85rem !important; color: var(--text-muted) !important; margin: 0 0 1rem !important; }
    .overlap-head { display: flex !important; justify-content: space-between !important; align-items: baseline !important; margin-bottom: 0.7rem !important; }
    .overlap-pct { font-size: 1.7rem !important; font-weight: 700 !important; color: var(--ivory) !important; line-height: 1 !important; }
    .overlap-track {
        height: 8px !important;
        background: var(--bg-surface) !important;
        border-radius: 999px !important;
        overflow: hidden !important;
    }
    .overlap-fill {
        height: 100% !important;
        background: var(--ivory) !important;
        border-radius: 999px !important;
    }
    .strong-match {
        display: inline-block !important;
        font-size: 0.66rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        padding: 0.25rem 0.7rem !important;
        background: var(--green-pale) !important;
        color: #7fbf8a !important;
        border-radius: 999px !important;
        margin-top: 0.8rem !important;
    }

    /* roadmap steps — same card as "how it works" */
    .roadmap-list { display: flex !important; flex-direction: column !important; gap: 0.7rem !important; }
    .roadmap-step {
        display: flex !important;
        gap: 1rem !important;
        align-items: flex-start !important;
        background: var(--bg-card) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        padding: 1rem 1.3rem !important;
    }
    .roadmap-num { color: var(--ivory) !important; font-size: 0.75rem !important; font-weight: 600 !important; letter-spacing: 0.1em !important; padding-top: 0.15rem !important; min-width: 1.4rem !important; }
    .roadmap-text { color: var(--text) !important; font-size: 0.88rem !important; line-height: 1.65 !important; }

    /* skills-you-have input: same pill as the main search, no button */
    .st-key-gap_search {
        background: var(--bg-surface) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 999px !important;
        padding: 0.3rem 1.4rem !important;
        transition: border-color 0.2s ease !important;
    }
    .st-key-gap_search:focus-within { border-color: rgba(232, 216, 118, 0.45) !important; }
    .st-key-gap_search input[type="text"] { border: none !important; text-align: left !important; caret-color: var(--ivory) !important; }
    .st-key-gap_search input[type="text"]:focus { border: none !important; }
    .st-key-gap_search input[type="text"]::placeholder { color: var(--text-muted) !important; text-align: left !important; }

    /* insight */
    .insight-text {
        font-size: 1rem !important;
        color: var(--text) !important;
        line-height: 1.85 !important;
        margin: 0 !important;
    }
    .st-key-insight_card { max-width: 760px !important; margin: 0 auto !important; padding: 1.8rem 2rem !important; }

    .muted-note { text-align: center !important; color: var(--text-muted) !important; font-size: 0.85rem !important; }
    .muted-note span { color: var(--ivory) !important; }

    @media (max-width: 720px) {
        .stat-row { gap: 0.6rem !important; }
        .stat-number { font-size: 1.3rem !important; }
    }

    /* footer */
    .app-footer {
        text-align: center !important;
        padding: 2.5rem 0 1.5rem !important;
        font-size: 0.68rem !important;
        color: var(--text-faint) !important;
        margin-top: 3rem !important;
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
    st.plotly_chart(fig, width="stretch")

def _chips_html(skills: list, chip_class: str = "") -> str:
    if not skills:
        return "<span class='chip-empty'>—</span>"
    chips = "".join(f"<span class='chip {chip_class}'>{escape(s)}</span>" for s in skills)
    return f"<div class='chip-wrap'>{chips}</div>"

def _render_tier_card(key: str, label: str, skills: list, tone: str):
    with st.container(key=key):
        st.markdown(
            f"<span class='eyebrow {tone}'>{label}</span>{_chips_html(skills[:6], tone)}",
            unsafe_allow_html=True
        )

MAX_CACHED_ROADMAPS = 10


def _get_roadmap(search_term: str, missing_skills: list, user_skills: list) -> str | None:
    #per-session roadmap cache, capped so trying many skill combos doesn't grow memory forever
    #failures (None) aren't stored, so the next rerun retries
    cache = st.session_state.setdefault("_roadmaps", {})
    key = f"{search_term.casefold()}:{','.join(sorted(s.casefold() for s in user_skills))}"
    if key in cache:
        return cache[key]
    with st.spinner("building your roadmap..."):
        roadmap = generate_roadmap(search_term, missing_skills, user_skills)
    if roadmap:
        cache[key] = roadmap
        while len(cache) > MAX_CACHED_ROADMAPS:
            cache.pop(next(iter(cache)))  #dicts keep insertion order -> drops the oldest
    return roadmap

def _render_skill_gap(gap: dict, search_term: str, missing_skills: list, user_skills: list):
    overlap_pct = gap["overlap_pct"]
    matched = gap["matched"]

    strong = "<span class='strong-match'>Strong match</span>" if gap["is_strong_match"] else ""
    with st.container(key="overlap_card"):
        st.markdown(
            f"<div class='overlap-head'><span class='eyebrow' style='margin:0;'>Skill overlap</span>"
            f"<span class='overlap-pct'>{overlap_pct}%</span></div>"
            f"<div class='overlap-track'><div class='overlap-fill' style='width:{overlap_pct}%;'></div></div>"
            f"{strong}",
            unsafe_allow_html=True
        )

    have_col, learn_col = st.columns(2)
    with have_col:
        with st.container(key="gap_have"):
            st.markdown(
                f"<span class='eyebrow'>Skills you have</span>{_chips_html(matched, 'have')}",
                unsafe_allow_html=True
            )
    with learn_col:
        with st.container(key="gap_learn"):
            st.markdown(
                f"<span class='eyebrow'>Skills to learn</span>"
                f"{_chips_html(missing_skills[:MAX_MISSING_SKILLS_SHOWN], 'learn')}",
                unsafe_allow_html=True
            )

    steps = parse_roadmap_steps(_get_roadmap(search_term, missing_skills, user_skills))
    if steps:
        st.markdown("<span class='eyebrow' style='margin-top:1.8rem;'>Learning roadmap</span>", unsafe_allow_html=True)
        cards = "".join(
            f"<div class='roadmap-step'><span class='roadmap-num'>{i:02d}</span>"
            f"<span class='roadmap-text'>{escape(text)}</span></div>"
            for i, text in enumerate(steps, start=1)
        )
        st.markdown(f"<div class='roadmap-list'>{cards}</div>", unsafe_allow_html=True)
    else:
        #groq failed or returned nothing — say so instead of silently rendering nothing
        st.markdown("<p class='muted-note'>couldn't generate a roadmap right now. try again in a moment.</p>", unsafe_allow_html=True)


# ── page layout ───────────────────────────────────────────────────────────────

#hero — full size on the landing, compact once a role has been searched
_has_search = bool(st.session_state.get("search_input", "").strip())
st.markdown(f"""
    <div class='hero{" compact" if _has_search else ""}'>
        <h1 class='hero-title'>Skills Worthy</h1>
        <span class='hero-sub'>Search any role. See what the market wants right now.</span>
    </div>
""", unsafe_allow_html=True)

#search bar — narrow centered column
_, search_col, _ = st.columns([2, 3, 2])
with search_col:
    #pill search bar: input + round button share one container (styled via .st-key-hero_search)
    with st.container(key="hero_search", horizontal=True, vertical_alignment="center", gap=None):
        search_term = st.text_input("search", key="search_input", label_visibility="collapsed", placeholder="data analyst, accountant...")
        #clicking blurs the input, which commits its value and reruns — same effect as Enter
        st.button("", icon=":material/search:", key="search_btn", width="content")


def _pick_role(role: str):
    #runs before the rerun, so the input already holds the role when the script reads it
    st.session_state["search_input"] = role


if not search_term:
    #landing only: trending role chips (clicking one runs that search) + how it works
    st.markdown("<div class='trending-label'>Trending roles</div>", unsafe_allow_html=True)
    with st.container(key="trending", horizontal=True, horizontal_alignment="center", gap="small"):
        for role in TRENDING_ROLES:
            st.button(role, key=f"chip_{role}", on_click=_pick_role, args=(role,), width="content")

    st.markdown("""
        <div class='how-row'>
            <div class='how-step'>
                <span class='how-num'>01</span>
                <span class='how-title'>Search a role</span>
                <span class='how-text'>We scan live job postings for the title you enter.</span>
            </div>
            <div class='how-step'>
                <span class='how-num'>02</span>
                <span class='how-title'>See the skills</span>
                <span class='how-text'>Ranked by how often employers actually ask for them.</span>
            </div>
            <div class='how-step'>
                <span class='how-num'>03</span>
                <span class='how-title'>Find your gap</span>
                <span class='how-text'>Add your skills and get a roadmap for what to learn next.</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
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
            jobs = _cached_fetch_jobs(search_term_clean.casefold())
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

#tabs for navigation
tab_skills, tab_gap, tab_insight = st.tabs(["Skills", "Skill Gap & Roadmap", "Insight"])

#tab 1 — skills bar chart + tier columns side by side
with tab_skills:
    if not skill_df.empty and len(skill_df) >= 3:
        chart_col, tier_col = st.columns([3, 2], gap="medium")

        with chart_col:
            with st.container(key="chart_card"):
                st.markdown("<span class='eyebrow'>Most requested skills</span>", unsafe_allow_html=True)
                _render_bar_chart(skill_df)

        with tier_col:
            _render_tier_card("tier_must", "Must have", tiers.get("must_have", []), "must")
            _render_tier_card("tier_good", "Good to have", tiers.get("good_to_have", []), "good")
            _render_tier_card("tier_nice", "Nice to have", tiers.get("nice_to_have", []), "")

    elif not skill_df.empty:
        st.markdown(
            "<p class='muted-note'>"
            "not enough skills found — try a more specific role like "
            f"<span>{escape(search_term_clean)} analyst</span> or "
            f"<span>{escape(search_term_clean)} engineer</span></p>",
            unsafe_allow_html=True
        )

#tab 2 — skill gap + roadmap
with tab_gap:
    st.markdown(
        "<p class='gap-intro'>List the skills you already have, separated by commas.</p>",
        unsafe_allow_html=True
    )

    _, gap_input_col, _ = st.columns([2, 3, 2])
    with gap_input_col:
        with st.container(key="gap_search"):
            user_skills_input = st.text_input(
                "your skills", label_visibility="collapsed", placeholder="Python, SQL, Excel...",
                max_chars=MAX_USER_SKILLS_CHARS,
            )

    if user_skills_input:
        #dedupe case-insensitively, keep first spelling, cap count (bounds prompt size + roadmap cache keys)
        seen, user_skills = set(), []
        for s in user_skills_input.split(','):
            s = s.strip()
            if s and s.casefold() not in seen:
                seen.add(s.casefold())
                user_skills.append(s)
        user_skills = user_skills[:MAX_USER_SKILLS]
        if not user_skills:
            st.warning("please enter at least one skill.")
        else:
            #compare against the same filtered list the chart shows, not the raw top-20
            #(raw list can contain role-noise / generic terms the user never sees)
            gap_skills = skill_df["skill"].tolist() if not skill_df.empty else top_skills
            gap = compute_skill_gap(gap_skills, user_skills)
            _render_skill_gap(gap, search_term_clean, gap["missing"], user_skills)

#tab 3 — market insight
with tab_insight:
    if insight and insight.available:
        with st.container(key="insight_card"):
            st.markdown(
                f"<span class='eyebrow must'>Market insight</span>"
                f"<p class='insight-text'>{escape(insight.text)}</p>",
                unsafe_allow_html=True
            )
    else:
        st.markdown("<p class='muted-note'>no insight available for this search.</p>", unsafe_allow_html=True)

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