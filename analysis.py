import re
import pandas as pd
from collections import Counter
from api import extract_job_fields
from ai import _is_role_noise
from config import TOP_SKILLS_COUNT, CATEGORY_PREVIEW_COUNT, ACRONYM_MAP

class ProcessedJobs:
    def __init__(self, descriptions: list[str], job_count: int):
        self.descriptions = descriptions
        self.job_count = job_count
        self.has_descriptions = len(descriptions) > 0

def process_jobs(jobs: list[dict], search_term: str) -> ProcessedJobs:
    #extracts clean descriptions from raw api jobs
    #filters out postings that dont match the search term
    descriptions = []

    for raw_job in jobs:
        job = extract_job_fields(raw_job)

        if not job["description"]:
            continue

        title_lower = job["title"].lower()
        search_lower = search_term.lower()
        if search_lower not in title_lower and not any(
            word in title_lower
            for word in search_lower.split()
        ):
            continue

        descriptions.append(job["description"])

    return ProcessedJobs(
        descriptions=descriptions,
        job_count=len(jobs)
    )

def build_skill_dataframe(skill_counts: Counter, search_term: str) -> pd.DataFrame:
    #skills arrive already normalized from _normalize_skill in ai.py
    #this function only filters, applies acronym corrections, and ranks
    search_words = set(search_term.lower().split())

    #generic terms that aren't concrete technical skills
    generic_terms = {
        'Word', 'Access', 'Windows', 'Office', 'Udb',
        'Powerpoint', 'Power Point', 'Outlook', 'Teams',
        'None', 'N/A', 'Na', 'Optimization', 'Programming',
        'Scaled Agile Framework',
    }

    normalized = Counter()
    for skill, count in skill_counts.items():
        normalized_skill = skill.strip().title()
        normalized_skill = ACRONYM_MAP.get(normalized_skill, normalized_skill)
        normalized[normalized_skill] += count

    filtered = {
        skill: count
        for skill, count in normalized.items()
        if not _is_role_noise(skill.lower(), search_words)
        and len(skill) > 1
        and len(skill) < 50
        and count > 0
        and skill not in generic_terms
    }

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
        "is_strong_match": overlap_pct >= 60
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
            "total": len(skills)
        })

    return previews