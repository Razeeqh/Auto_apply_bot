"""Caps how many applications the bot submits per calendar day.

Naukri itself enforces a daily application ceiling (around 50); staying well under it - and under
what a genuinely engaged human applicant would do in a day - is one of the clearest signals that
separates a real job-seeker from a bot. This persists across runs (and across process restarts) so
several shorter runs in the same day still add up against a single daily cap.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

DAILY_COUNT_PATH = Path("data/daily_apply_count.json")

# Recommended range is 15-20/day, well under Naukri's own ~50/day cap. Override via the
# DAILY_APPLY_LIMIT env var if you want to tune this.
DEFAULT_DAILY_LIMIT = 20


class DailyApplicationLimiter:
    def __init__(self, limit: int = DEFAULT_DAILY_LIMIT):
        self.limit = limit
        self._today = date.today().isoformat()
        self._count = self._load()

    def _load(self) -> int:
        if DAILY_COUNT_PATH.exists():
            data = json.loads(DAILY_COUNT_PATH.read_text(encoding="utf-8"))
            if data.get("date") == self._today:
                return int(data.get("count", 0))
        return 0

    def _save(self) -> None:
        DAILY_COUNT_PATH.parent.mkdir(exist_ok=True)
        DAILY_COUNT_PATH.write_text(
            json.dumps({"date": self._today, "count": self._count}, indent=2), encoding="utf-8"
        )

    @property
    def count(self) -> int:
        return self._count

    def has_capacity(self) -> bool:
        return self._count < self.limit

    def record_application(self) -> None:
        self._count += 1
        self._save()
