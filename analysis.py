import re
import pandas as pd
from collections import Counter
from api import extract_job_fields
from config import TOP_SKILLS_COUNT, CATEGORY_PREVIEW_COUNT, ACRONYM_MAP


class ProcessedJobs:
    def __init__(self, descriptions: list[str], job_count: int):
        self.descriptions = descriptions
        self.job_count = job_count
        self.has_descriptions = len(descriptions) > 0


def process_jobs(jobs: list[dict], search_term: str) -> ProcessedJobs:
    descriptions = []
    search_words = search_term.lower().split()

    for raw_job in jobs:
        job = extract_job_fields(raw_job)

        if not job["description"]:
            continue

        title_lower = job["title"].lower()

        if search_term.lower() not in title_lower:
            if not all(word in title_lower for word in search_words):
                continue

        descriptions.append(job["description"])

    return ProcessedJobs(
        descriptions=descriptions,
        job_count=len(jobs)
    )


def build_skill_dataframe(skill_counts: Counter, search_term: str, total_analyzed: int) -> pd.DataFrame:
    #builds the bar chart dataframe with percentage column
    #pct = what fraction of scanned postings mention this skill
    search_words = set(search_term.lower().split())

    generic_terms = {
        'Word', 'Access', 'Windows', 'Office',
        'Powerpoint', 'Power Point', 'Outlook', 'Teams',
        'None', 'N/A',
    }

    normalized = Counter()
    for skill, count in skill_counts.items():
        clean = ACRONYM_MAP.get(skill.strip(), skill.strip())
        normalized[clean] += count

    skill_words_cache = {}
    filtered = {}
    for skill, count in normalized.items():
        skill_lower = skill.lower()
        if skill_lower not in skill_words_cache:
            skill_words_cache[skill_lower] = set(re.findall(r'\b\w+\b', skill_lower))
        skill_words = skill_words_cache[skill_lower]

        is_noise = any(w in skill_words for w in search_words if len(w) > 3)
        if is_noise:
            continue
        if len(skill) < 2 or len(skill) > 50:
            continue
        if skill in generic_terms:
            continue

        filtered[skill] = count

    if not filtered:
        return pd.DataFrame(columns=['skill', 'count', 'pct'])

    top = Counter(filtered).most_common(TOP_SKILLS_COUNT)
    df = pd.DataFrame(top, columns=['skill', 'count'])

    #percentage of postings that mention each skill
    if total_analyzed > 0:
        #clip: merged spellings ("Powerbi" + "Power BI") could otherwise exceed 100% of postings
        df['pct'] = (df['count'] / total_analyzed * 100).round(0).clip(upper=100).astype(int)
    else:
        df['pct'] = 0

    return df


#"Step 3:", "step 3 -", "3.", "3)", optionally wrapped in markdown bold
_STEP_PREFIX = re.compile(r'^\s*(?:\*\*)?\s*(?:step\s*\d+\s*[:.)\-–]|\d+\s*[.):])\s*(?:\*\*)?\s*', re.IGNORECASE)


def parse_roadmap_steps(roadmap: str) -> list[str]:
    #turns the model's roadmap text into clean step strings (no "Step N:" / "N." prefix)
    #if the model numbered its steps, intro/outro lines ("Here are your steps:") are dropped;
    #if nothing is numbered (e.g. the "you already have all the skills" message), every line is kept
    if not roadmap:
        return []
    lines = [line.strip() for line in roadmap.splitlines() if line.strip()]
    numbered = []
    for line in lines:
        match = _STEP_PREFIX.match(line)
        if match:
            text = line[match.end():]
            #models sometimes repeat the label: "Step 1: Step 1: learn x"
            while (inner := _STEP_PREFIX.match(text)):
                text = text[inner.end():]
            text = text.strip().strip('*').strip()
            if text:
                numbered.append(text)
    return numbered if numbered else lines


def _skill_key(skill: str) -> str:
    #case/space/punctuation-insensitive key: "Power BI" == "powerbi" == "power-bi"
    #keeps + and # so C++ and C# stay distinct from C
    return re.sub(r'[^a-z0-9+#]', '', skill.lower())


def compute_skill_gap(top_skills: list[str], user_skills: list[str]) -> dict:
    user_keys = {_skill_key(s) for s in user_skills if s.strip()}
    user_keys.discard("")

    matched = [s for s in top_skills if _skill_key(s) in user_keys]
    missing = [s for s in top_skills if _skill_key(s) not in user_keys]

    overlap_pct = round((len(matched) / len(top_skills)) * 100) if top_skills else 0

    return {
        "matched": matched,
        "missing": missing,
        "overlap_pct": overlap_pct,
        "is_strong_match": overlap_pct >= 60,
    }


def get_category_previews(categories: dict) -> list[dict]:
    if not categories:
        return []

    previews = []
    for category, skills in categories.items():
        if not isinstance(skills, list):
            continue
        preview_skills = skills[:CATEGORY_PREVIEW_COUNT]
        previews.append({
            "category": category,
            "preview": ", ".join(preview_skills),
            "has_more": len(skills) > CATEGORY_PREVIEW_COUNT,
            "total": len(skills),
        })

    return previews