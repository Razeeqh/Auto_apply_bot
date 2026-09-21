"""Skill / title matching against the profile & rules in Questionnaire.yaml."""
from __future__ import annotations

from rapidfuzz import fuzz


def skill_match_percent(job_skills: list[str], core_skills: list[str]) -> float:
    """Percent of the candidate's core_skills that appear (fuzzy) in the job's skills."""
    if not core_skills:
        return 0.0

    job_skills_lower = [s.lower().strip() for s in job_skills]
    matched = 0
    for skill in core_skills:
        skill_lower = skill.lower().strip()
        if any(
            skill_lower in js or fuzz.partial_ratio(skill_lower, js) >= 85
            for js in job_skills_lower
        ):
            matched += 1

    return round((matched / len(core_skills)) * 100, 1)


def title_matches(title: str, required_substrings: list[str]) -> bool:
    title_lower = title.lower()
    return any(sub.lower() in title_lower for sub in required_substrings)


def is_strong_title_match(title: str) -> bool:
    """True if the title contains both 'data' and 'engineer' (any order), bypassing the skill-match filter."""
    title_lower = title.lower()
    return "data" in title_lower and "engineer" in title_lower
