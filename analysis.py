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
    #extracts clean descriptions from raw api jobs
    #requires ALL search words to appear in the title, not just one
    #this prevents "data analyst" from matching "data engineer"
    descriptions = []
    search_words = search_term.lower().split()

    for raw_job in jobs:
        job = extract_job_fields(raw_job)

        if not job["description"]:
            continue

        title_lower = job["title"].lower()

        #full phrase match first, then all-words match
        if search_term.lower() not in title_lower:
            if not all(word in title_lower for word in search_words):
                continue

        descriptions.append(job["description"])

    return ProcessedJobs(
        descriptions=descriptions,
        job_count=len(jobs)
    )


def build_skill_dataframe(skill_counts: Counter, search_term: str) -> pd.DataFrame:
    #skills arrive already normalized from _normalize_skill in ai.py
    #no .title() call here — that was destroying canonical names like Power BI
    #only applies acronym map as a safety net, filters, and ranks
    search_words = set(search_term.lower().split())

    generic_terms = {
        'Word', 'Access', 'Windows', 'Office',
        'Powerpoint', 'Power Point', 'Outlook', 'Teams',
        'None', 'N/A',
    }

    #safety net — apply acronym map without .title()
    normalized = Counter()
    for skill, count in skill_counts.items():
        clean = ACRONYM_MAP.get(skill.strip(), skill.strip())
        normalized[clean] += count

    #filter role noise using whole-word matching
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
        return pd.DataFrame(columns=['skill', 'count'])

    top = Counter(filtered).most_common(TOP_SKILLS_COUNT)
    return pd.DataFrame(top, columns=['skill', 'count'])


def compute_skill_gap(top_skills: list[str], user_skills: list[str]) -> dict:
    user_lower = {s.lower().strip() for s in user_skills if s.strip()}

    matched = [s for s in top_skills if s.lower() in user_lower]
    missing = [s for s in top_skills if s.lower() not in user_lower]

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
