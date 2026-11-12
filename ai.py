import logging
import json
import re
from groq import Groq
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    MAX_DESCRIPTIONS,
    MAX_SOFT_SKILLS,
    ACRONYM_MAP,
    NICHE_SAMPLE_SIZE,
)
from taxonomy import count_taxonomy_skills, count_specific_skills, TAXONOMY_NAMES

logger = logging.getLogger(__name__)

#client built once at module level
_client = Groq(api_key=GROQ_API_KEY)

#skill name variations for normalizing groq output
_SKILL_ALIASES = {
    'js': 'JavaScript', 'javascript': 'JavaScript', 'node': 'Node.js',
    'node.js': 'Node.js', 'nodejs': 'Node.js', 'react.js': 'React',
    'reactjs': 'React', 'vue.js': 'Vue', 'vuejs': 'Vue',
    'postgres': 'PostgreSQL', 'postgresql': 'PostgreSQL',
    'mongo': 'MongoDB', 'mongodb': 'MongoDB',
    'py': 'Python', 'python3': 'Python',
    'powerbi': 'Power BI', 'power bi': 'Power BI',
    'scikit learn': 'Scikit-learn', 'sklearn': 'Scikit-learn',
    'tensorflow': 'TensorFlow', 'pytorch': 'PyTorch',
    'dbt': 'dbt', 'data build tool': 'dbt',
    'k8s': 'Kubernetes', 'kubernetes': 'Kubernetes',
    'graphql': 'GraphQL',
    'quickbooks': 'QuickBooks',
    'autocad': 'AutoCAD', 'solidworks': 'SolidWorks',
    'matlab': 'MATLAB', 'sas': 'SAS', 'spss': 'SPSS',
}

#terms to exclude even after normalization
_EXCLUDED_SKILLS = {
    'ai', 'optimization', 'programming', 'analytics', 'reporting',
    'data', 'analysis', 'management', 'development', 'testing',
    'design', 'research', 'modeling', 'automation', 'integration',
    'infrastructure', 'engineering', 'architecture', 'monitoring',
    'documentation', 'security', 'networking', 'communication',
}


class SkillExtractionResult:
    def __init__(self, counts: Counter):
        self.counts = counts

    @property
    def total(self) -> int:
        return len(self.counts)

    def is_empty(self) -> bool:
        return self.total == 0


class InsightResult:
    def __init__(self, text: str | None):
        self.text = text
        self.available = text is not None and len(text.strip()) > 0


def _call_groq(prompt: str, max_tokens: int) -> str | None:
    #single groq call, returns none on failure or empty response
    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=GROQ_TEMPERATURE,
        )
    except Exception as e:
        logger.error("groq call failed: %s", e)
        return None

    choice = response.choices[0]
    content = choice.message.content
    if not content or not content.strip():
        logger.warning("groq returned empty content (finish_reason=%s)", choice.finish_reason)
        return None
    return content.strip()


def _truncate_description(description: str, max_chars: int = 600) -> str:
    if len(description) <= max_chars:
        return description
    return description[:max_chars]


def _normalize_skill(skill: str) -> str:
    #collapse unicode spaces, strip punctuation, look up alias, fallback to title case with acronym fix
    cleaned = " ".join(skill.split()).strip('.-•*– ').strip()
    if not cleaned:
        return ""
    lookup = cleaned.lower()
    if lookup in _SKILL_ALIASES:
        return _SKILL_ALIASES[lookup]
    result = cleaned.title()
    return ACRONYM_MAP.get(result, result)


def _is_role_noise(skill_lower: str, search_words: set) -> bool:
    skill_words = set(re.findall(r'\b\w+\b', skill_lower))
    return any(word in skill_words for word in search_words if len(word) > 3)


def _discover_niche_skills(sample_descriptions: list[str], known_skills: set) -> list[str]:
    #asks groq to find skills in a sample that the taxonomy missed
    #returns only skills NOT already in the taxonomy — no duplicates
    #this is the one groq call in the extraction pipeline
    combined = "\n---\n".join(sample_descriptions)

    prompt = f"""List every technical skill, tool, software, platform, or framework mentioned in these job postings.
Return ONLY a comma-separated list. Nothing else.

{combined}"""

    result = _call_groq(prompt, max_tokens=200)
    if not result:
        return []

    #normalize and filter — keep only skills the taxonomy doesn't already cover
    niche = []
    known_lower = {s.lower() for s in known_skills}
    seen = set()
    for raw in result.split(','):
        raw = raw.strip()
        if not raw or len(raw) < 2 or len(raw) > 40 or len(raw.split()) > 3:
            continue
        normalized = _normalize_skill(raw)
        if not normalized:
            continue
        norm_lower = normalized.lower()
        if norm_lower in known_lower or norm_lower in _EXCLUDED_SKILLS or norm_lower in seen:
            continue
        seen.add(norm_lower)
        niche.append(normalized)

    return niche


def extract_skills(descriptions: list[str]) -> SkillExtractionResult:
    #hybrid extraction pipeline:
    #  step 1: python regex scans ALL descriptions against 200-skill taxonomy (0 api calls)
    #  step 2: groq reads a sample for niche skills not in taxonomy (1 api call)
    #  step 3: python counts niche skills across ALL descriptions (0 api calls)
    #  step 4: merge both counters
    #total: 1 groq call, every description counted, deterministic frequency
    if not descriptions:
        return SkillExtractionResult(counts=Counter())

    capped = [_truncate_description(d) for d in descriptions[:MAX_DESCRIPTIONS]]

    #step 1 — taxonomy scan, all descriptions, instant
    taxonomy_counts = count_taxonomy_skills(capped)

    #step 2 — groq discovers niche skills from a sample
    sample = capped[:NICHE_SAMPLE_SIZE]
    niche_skills = _discover_niche_skills(sample, set(taxonomy_counts.keys()))

    #step 3 — python counts niche skills across all descriptions
    niche_counts = count_specific_skills(capped, niche_skills)

    #step 4 — merge
    merged = taxonomy_counts + niche_counts

    return SkillExtractionResult(counts=merged)


def categorize_skills(skills: list[str]) -> dict | None:
    if not skills:
        return None

    skills_str = ", ".join(skills)
    prompt = f"""Categorize these skills into logical groups.
Use clear category names: Programming, Data Analysis, Cloud, Databases, Visualization, DevOps.
Return ONLY valid JSON. No markdown. No explanation.
Example: {{"Programming": ["Python", "Java"], "Data": ["SQL", "Excel"]}}

Skills: {skills_str}"""

    result = _call_groq(prompt, max_tokens=400)
    if not result:
        return None

    cleaned = result.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return None
        return {k: v for k, v in parsed.items() if isinstance(v, list) and len(v) > 0}
    except json.JSONDecodeError:
        logger.error("groq returned malformed json for categorization")
        return None


def generate_insight(query: str, top_skills: list[str]) -> InsightResult:
    skills_str = ", ".join(top_skills[:8])
    prompt = f"""Write exactly 2 sentences about the '{query}' job market based on these skills: {skills_str}.
Sentence 1: what skills dominate. Sentence 2: what to focus on.
Stop after the second period. No filler phrases. Don't start with I or As an AI."""

    result = _call_groq(prompt, max_tokens=150)
    if not result:
        return InsightResult(text=None)

    sentences = re.split(r'(?<=[.!?])\s+', result.strip())
    capped = ' '.join(sentences[:2])
    return InsightResult(text=capped)


def suggest_soft_skills(query: str) -> list[str]:
    prompt = f"""List the {MAX_SOFT_SKILLS} most important soft skills for a '{query}' role.
Return ONLY a comma separated list. No numbering, no explanation."""

    result = _call_groq(prompt, max_tokens=80)
    if not result:
        return []
    return [s.strip() for s in result.split(',') if s.strip()]


def generate_roadmap(query: str, missing_skills: list[str], user_skills: list[str]) -> str | None:
    if not missing_skills:
        return "you already have all the top skills for this role. focus on deepening expertise and building projects."

    missing_str = ", ".join(missing_skills[:10])
    known_str = ", ".join(user_skills)

    prompt = f"""You are a career coach. Someone wants to become a '{query}'.
They know: {known_str}
They are missing: {missing_str}
Write exactly 5 steps. Each step is one sentence starting with Step N:.
Do NOT repeat the step label inside the sentence.
Prioritize the most in-demand missing skills first. Nothing else."""

    return _call_groq(prompt, max_tokens=300)


def compute_skill_tiers(counts: Counter, search_term: str) -> dict:
    if not counts:
        return {"must_have": [], "good_to_have": [], "nice_to_have": []}

    search_words = set(search_term.lower().split())

    filtered = {}
    for skill, count in counts.items():
        if _is_role_noise(skill.lower(), search_words):
            continue
        if skill.lower() in _EXCLUDED_SKILLS:
            continue
        filtered[skill] = count

    if not filtered:
        return {"must_have": [], "good_to_have": [], "nice_to_have": []}

    sorted_skills = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    total = len(sorted_skills)

    top_cut = max(1, total // 3)
    mid_cut = max(2, (total * 2) // 3)

    must_have = [s for s, _ in sorted_skills[:top_cut]]
    good_to_have = [s for s, _ in sorted_skills[top_cut:mid_cut]]
    nice_to_have = [s for s, _ in sorted_skills[mid_cut:]]

    return {
        "must_have": must_have[:8],
        "good_to_have": good_to_have[:8],
        "nice_to_have": nice_to_have[:8],
    }


def run_ai_pipeline(query: str, descriptions: list[str]) -> tuple:
    #hybrid extraction first (1 groq call), then 3 parallel groq calls
    #total: 4 groq calls per search regardless of description count
    skill_result = extract_skills(descriptions)

    if skill_result.is_empty():
        return skill_result, None, InsightResult(text=None), [], {}

    top_skills = [skill for skill, _ in skill_result.counts.most_common(20)]

    with ThreadPoolExecutor(max_workers=3) as executor:
        insight_future = executor.submit(generate_insight, query, top_skills)
        soft_skills_future = executor.submit(suggest_soft_skills, query)
        categories_future = executor.submit(categorize_skills, top_skills)

        insight = insight_future.result()
        soft_skills = soft_skills_future.result()
        categories = categories_future.result()

    tiers = compute_skill_tiers(skill_result.counts, query)

    return skill_result, categories, insight, soft_skills, tiers
