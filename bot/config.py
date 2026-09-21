"""Loads Questionnaire.yaml and typed access to profile, questions and rules."""
from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Profile:
    total_experience_years: float
    primary_role: str
    core_skills: list[str] = field(default_factory=list)


@dataclass
class Question:
    question: str
    normalized_key: str
    answer: object


@dataclass
class Rules:
    minimum_skill_match_percent: float
    apply_if_title_contains: list[str]
    apply_if_skill_match_gte_percent: float
    never_invent_answers: bool
    collect_new_questions: bool
    deduplicate_questions: bool


@dataclass
class Config:
    profile: Profile
    questions: list[Question]
    rules: Rules


def load_config(path: str | Path = "Questionnaire.yaml") -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    profile = Profile(**raw["profile"])
    questions = [Question(**q) for q in raw["application_questions"]]
    rules = Rules(**raw["rules"])

    return Config(profile=profile, questions=questions, rules=rules)
