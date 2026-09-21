"""Persists job URLs the bot has already resolved so re-runs never revisit or re-count them."""
from __future__ import annotations

import json
from pathlib import Path

APPLIED_TRACKER_PATH = Path("data/applied_jobs.json")

# Terminal outcomes for a job URL; once reached, the URL is never processed again.
FINAL_STATUSES = {"applied", "already_applied", "company_site"}


class AppliedTracker:
    def __init__(self):
        self._by_url: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if APPLIED_TRACKER_PATH.exists():
            return json.loads(APPLIED_TRACKER_PATH.read_text(encoding="utf-8"))
        return {}

    def _save(self) -> None:
        APPLIED_TRACKER_PATH.parent.mkdir(exist_ok=True)
        APPLIED_TRACKER_PATH.write_text(json.dumps(self._by_url, indent=2), encoding="utf-8")

    def is_processed(self, url: str) -> bool:
        return self._by_url.get(url) in FINAL_STATUSES

    def mark(self, url: str, status: str) -> None:
        if status in FINAL_STATUSES:
            self._by_url[url] = status
            self._save()
