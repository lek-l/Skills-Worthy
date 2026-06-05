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
    DESCRIPTION_BATCH_SIZE,
    MAX_DESCRIPTIONS,
    MAX_SOFT_SKILLS,
    ACRONYM_MAP,
)

logger = logging.getLogger(__name__)

#client built once at module level
_client = Groq(api_key=GROQ_API_KEY)

#common skill name variations — normalize to canonical form
#ensures js and javascript count as the same skill across batches
#groq is prompted to use canonical names but doesn't always comply
_SKILL_ALIASES = {
    'js': 'JavaScript', 'javascript': 'JavaScript', 'node': 'Node.js',
    'node.js': 'Node.js', 'nodejs': 'Node.js', 'react.js': 'React',
    'reactjs': 'React', 'vue.js': 'Vue', 'vuejs': 'Vue',
    'postgres': 'PostgreSQL', 'postgresql': 'PostgreSQL',
    'mongo': 'MongoDB', 'mongodb': 'MongoDB',
    'py': 'Python', 'python3': 'Python',
    'ms excel': 'Excel', 'microsoft excel': 'Excel',
    'ms sql': 'SQL Server', 'microsoft sql server': 'SQL Server',
    'gcp': 'Google Cloud', 'google cloud platform': 'Google Cloud',
    'amazon web services': 'AWS', 'azure': 'Azure',
    'powerbi': 'Power BI', 'power bi': 'Power BI',
    'tableau': 'Tableau', 'looker': 'Looker',
    'scikit learn': 'Scikit-learn', 'sklearn': 'Scikit-learn',
    'tensorflow': 'TensorFlow', 'tf': 'TensorFlow',
    'pytorch': 'PyTorch', 'torch': 'PyTorch',
    'dbt': 'dbt', 'data build tool': 'dbt',
    'git': 'Git', 'github': 'GitHub', 'gitlab': 'GitLab',
    'docker': 'Docker', 'kubernetes': 'Kubernetes', 'k8s': 'Kubernetes',
    'spark': 'Apache Spark', 'apache spark': 'Apache Spark',
    'airflow': 'Apache Airflow', 'apache airflow': 'Apache Airflow',
    'snowflake': 'Snowflake', 'redshift': 'Redshift',
    'bigquery': 'BigQuery', 'databricks': 'Databricks',
    'machine learning': 'Machine Learning', 'ml': 'Machine Learning',
    'artificial intelligence': 'AI', 'deep learning': 'Deep Learning',
    'natural language processing': 'NLP', 'nlp': 'NLP',
    'sql server': 'SQL Server', 'mysql': 'MySQL', 'sqlite': 'SQLite',
    'r language': 'R', 'r programming': 'R',
    'excel': 'Excel', 'vba': 'VBA', 'power query': 'Power Query',
    'quickbooks': 'QuickBooks', 'quickbooks online': 'QuickBooks Online',
    'salesforce': 'Salesforce', 'sap': 'SAP', 'oracle': 'Oracle',
    'jira': 'Jira', 'confluence': 'Confluence', 'trello': 'Trello',
    'figma': 'Figma', 'sketch': 'Sketch', 'photoshop': 'Photoshop',
    'autocad': 'AutoCAD', 'solidworks': 'SolidWorks',
    'matlab': 'MATLAB', 'sas': 'SAS', 'spss': 'SPSS',
}

class SkillExtractionResult:
    def __init__(self, counts: Counter):
        self.counts = counts

    @property
    def total(self) -> int:
        #number of distinct skills found
        return len(self.counts)

    def is_empty(self) -> bool:
        return self.total == 0

class InsightResult:
    def __init__(self, text: str | None):
        self.text = text
        self.available = text is not None and len(text.strip()) > 0

def _call_groq(prompt: str, max_tokens: int) -> str | None:
    #single groq call — returns none on failure
    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=GROQ_TEMPERATURE
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("groq call failed: %s", e)
        return None

def _truncate_description(description: str, max_chars: int = 600) -> str:
    #truncate to first max_chars — skills appear early in postings
    if len(description) <= max_chars:
        return description
    return description[:max_chars]

def _normalize_skill(skill: str) -> str:
    #normalize skill name to canonical form using _SKILL_ALIASES
    #unknown skills fall back to their original casing from groq
    cleaned = skill.strip().strip('.-').strip()
    lookup = cleaned.lower()
    return _SKILL_ALIASES.get(lookup, cleaned)

def _is_role_noise(skill_lower: str, search_words: set) -> bool:
    #returns true if any search word appears as a whole word in the skill name
    #prevents "data analyst" from filtering out "databricks" (substring false positive)
    skill_words = set(re.findall(r'\b\w+\b', skill_lower))
    return any(word in skill_words for word in search_words if len(word) > 3)

def _extract_skills_from_all(descriptions: list[str]) -> Counter:
    #extract skills per description then count in python
    #normalization ensures js and javascript count as the same skill
    #python does the counting — groq just identifies skills per posting
    all_skills = []

    for i in range(0, len(descriptions), DESCRIPTION_BATCH_SIZE):
        batch = descriptions[i:i + DESCRIPTION_BATCH_SIZE]
        numbered = "\n\n".join([f"[{j+1}] {d}" for j, d in enumerate(batch)])

        prompt = f"""For each numbered job posting, list every technical skill mentioned.
Technical skills only: programming languages, tools, software, frameworks, platforms, databases, methodologies.
Do NOT include: industry terms, business concepts, soft skills, job titles, company names, general concepts.
Use full canonical names: JavaScript not JS, PostgreSQL not Postgres, Machine Learning not ML.

Return one line per posting:
1: Python, SQL, Tableau
2: Java, AWS, Docker

Job postings:
{numbered}"""

        result = _call_groq(prompt, max_tokens=200)
        if not result:
            continue

        for line in result.strip().split('\n'):
            if ':' not in line:
                continue
            skills_part = line.split(':', 1)[1]
            skills = [
            
                _normalize_skill(s)
                for s in skills_part.split(',')
                if s.strip()
                and 1 < len(s.strip()) < 30
                and s.strip().lower() not in (
                    'none', 'n/a', 'na', 'null',
                    'no technical skills mentioned',
                    'no technical skills',
                    'not mentioned',
                )
            ]
            all_skills.extend(skills)

    return Counter(all_skills)

def extract_skills(descriptions: list[str]) -> SkillExtractionResult:
    #extracts skills with accurate frequency counts across all descriptions
    if not descriptions:
        return SkillExtractionResult(counts=Counter())

    capped = [_truncate_description(d) for d in descriptions[:MAX_DESCRIPTIONS]]
    counts = _extract_skills_from_all(capped)

    return SkillExtractionResult(counts=counts)

def categorize_skills(skills: list[str]) -> dict | None:
    #dynamically categorizes skills into standard groups
    if not skills:
        return None

    skills_str = ", ".join(skills)
    prompt = f"""You are a job market analyst. Categorize these skills into logical groups.
Use clear professional category names a recruiter would recognize.
Good names: Programming, Data Analysis, Machine Learning, Cloud, Databases, Visualization, Statistics, Finance, Management.
Bad names: Intelligence, Modeling, Computation, Cognition, Things.
Return ONLY a valid JSON object. No markdown, no explanation, just raw JSON.
Example: {{"Programming": ["Python", "Java"], "Data Analysis": ["SQL", "Excel"]}}

Skills:
{skills_str}"""

    result = _call_groq(prompt, max_tokens=500)
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
    #2 sentence max — tight and actionable
    skills_str = ", ".join(top_skills[:8])
    prompt = f"""You are a job market analyst. Write exactly 2 sentences about the '{query}' job market.
Base it on these top skills: {skills_str}.
Be specific and actionable. No filler. No "in today's landscape". Don't start with I or As an AI."""

    result = _call_groq(prompt, max_tokens=120)
    return InsightResult(text=result)

def suggest_soft_skills(query: str) -> list[str]:
    #returns top soft skills for the role
    prompt = f"""List the {MAX_SOFT_SKILLS} most important soft skills for a '{query}' role.
Return ONLY a comma separated list. No numbering, no explanation."""

    result = _call_groq(prompt, max_tokens=60)
    if not result:
        return []
    return [s.strip() for s in result.split(',') if s.strip()]

def generate_roadmap(query: str, missing_skills: list[str], user_skills: list[str]) -> str | None:
    #generates prioritized roadmap from precomputed skill gap
    #missing_skills should come from compute_skill_gap to avoid recomputing the diff
    if not missing_skills:
        return "you already have all the top skills for this role. focus on deepening expertise and building projects."

    missing_str = ", ".join(missing_skills[:10])
    known_str = ", ".join(user_skills)

    prompt = f"""You are a career coach. Someone wants to become a '{query}'.
They know: {known_str}
They are missing: {missing_str}
Write exactly 5 steps. Each step is one sentence starting with Step N:.
Prioritize the most in-demand missing skills first. Nothing else."""

    return _call_groq(prompt, max_tokens=300)

def compute_skill_tiers(counts: Counter, search_term: str) -> dict:
    #splits skills into must have, good to have, nice to have based on frequency
    #frequency relative to other skills tells you priority
    if not counts:
        return {"must_have": [], "good_to_have": [], "nice_to_have": []}

    search_words = set(search_term.lower().split())

    filtered = {}
    for skill, count in counts.items():
        skill_clean = skill.strip().title()
        skill_clean = ACRONYM_MAP.get(skill_clean, skill_clean)

        if _is_role_noise(skill_clean.lower(), search_words):
            continue

        filtered[skill_clean] = count

    if not filtered:
        return {"must_have": [], "good_to_have": [], "nice_to_have": []}

    sorted_skills = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    total_skills = len(sorted_skills)

    top_cut = max(1, total_skills // 3)
    mid_cut = max(2, (total_skills * 2) // 3)

    must_have = [s for s, _ in sorted_skills[:top_cut]]
    good_to_have = [s for s, _ in sorted_skills[top_cut:mid_cut]]
    nice_to_have = [s for s, _ in sorted_skills[mid_cut:]]

    return {
        "must_have": must_have[:8],
        "good_to_have": good_to_have[:8],
        "nice_to_have": nice_to_have[:8]
    }

def run_ai_pipeline(query: str, descriptions: list[str]) -> tuple:
    #runs skill extraction first then fires insight, soft skills, categorization in parallel
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
