"""Answers application questions from Questionnaire.yaml, with fuzzy matching,
dedup and collection of unanswered questions per the configured rules.
"""
from __future__ import annotations

import json
import yaml
from pathlib import Path
from rapidfuzz import fuzz, process

from bot.config import Question, Rules

FUZZY_MATCH_THRESHOLD = 80
SEEN_QUESTIONS_PATH = Path("data/seen_questions.json")
NEW_QUESTIONS_PATH = Path("data/new_questions.yaml")


class QuestionBank:
    def __init__(self, questions: list[Question], rules: Rules):
        self.questions = questions
        self.rules = rules
        self._by_text = {q.question: q for q in questions}
        self._seen: set[str] = self._load_seen() if rules.deduplicate_questions else set()
        self._new_questions: list[str] = []

    def _load_seen(self) -> set[str]:
        if SEEN_QUESTIONS_PATH.exists():
            return set(json.loads(SEEN_QUESTIONS_PATH.read_text(encoding="utf-8")))
        return set()

    def _save_seen(self) -> None:
        SEEN_QUESTIONS_PATH.parent.mkdir(exist_ok=True)
        SEEN_QUESTIONS_PATH.write_text(json.dumps(sorted(self._seen), indent=2), encoding="utf-8")

    def find_answer(self, asked_text: str) -> object | None:
        """Return the configured answer for a question asked on a form, or None."""
        asked_text = asked_text.strip()
        if not asked_text:
            return None

        match = process.extractOne(
            asked_text, self._by_text.keys(), scorer=fuzz.token_sort_ratio
        )
        if match and match[1] >= FUZZY_MATCH_THRESHOLD:
            return self._by_text[match[0]].answer

        self._record_unanswered(asked_text)
        return None

    def _record_unanswered(self, asked_text: str) -> None:
        if self.rules.deduplicate_questions:
            if asked_text in self._seen:
                return
            self._seen.add(asked_text)
            self._save_seen()

        if self.rules.collect_new_questions:
            self._new_questions.append(asked_text)
            self._save_new_questions()

    def _save_new_questions(self) -> None:
        NEW_QUESTIONS_PATH.parent.mkdir(exist_ok=True)
        existing: list[str] = []
        if NEW_QUESTIONS_PATH.exists():
            existing = yaml.safe_load(NEW_QUESTIONS_PATH.read_text(encoding="utf-8")) or []
        merged = sorted(set(existing) | set(self._new_questions))
        NEW_QUESTIONS_PATH.write_text(yaml.safe_dump(merged, allow_unicode=True), encoding="utf-8")
