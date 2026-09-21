"""Entry point: logs in, searches jobs per profile, filters by rules, and applies."""
from __future__ import annotations

import os
import random
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from bot.applied_tracker import AppliedTracker
from bot.applier import apply_to_job
from bot.browser import ensure_logged_in, launch_context
from bot.config import load_config
from bot.job_search import search_jobs
from bot.logger import get_logger
from bot.matcher import is_strong_title_match, skill_match_percent, title_matches
from bot.questionnaire import QuestionBank
from bot.rate_limit import DailyApplicationLimiter, DEFAULT_DAILY_LIMIT

logger = get_logger(__name__)

# Applying back-to-back is a strong bot signal. A wide, randomized gap between apply attempts reads
# far more like a human reading each posting than a fixed short delay would.
APPLY_DELAY_RANGE_SECONDS = (30, 180)

# The search/browse phase isn't the sensitive part (no applications are submitted here), so it only
# needs a small randomized gap to avoid perfectly-uniform request timing between search terms.
SEARCH_TERM_DELAY_RANGE_SECONDS = (2, 5)


def main() -> None:
    load_dotenv()
    email = os.environ["NAUKRI_EMAIL"]
    password = os.environ["NAUKRI_PASSWORD"]
    daily_limit = int(os.environ.get("DAILY_APPLY_LIMIT", DEFAULT_DAILY_LIMIT))

    logger.warning(
        "Reminder: if selectors.py or applier.py changed since your last run, try it against a "
        "throwaway/test Naukri account first - not your primary profile - to confirm it doesn't "
        "trip a verification/captcha challenge before trusting it with real applications."
    )

    config = load_config("Questionnaire.yaml")
    question_bank = QuestionBank(config.questions, config.rules)
    applied_tracker = AppliedTracker()
    daily_limiter = DailyApplicationLimiter(limit=daily_limit)

    if not daily_limiter.has_capacity():
        logger.warning(
            "Daily application limit (%d) already reached today (%d applied) - not starting a run.",
            daily_limiter.limit, daily_limiter.count,
        )
        return

    summary = {"applied": 0, "already_applied": 0, "skipped": 0, "error": 0, "not_matched": 0, "previously_processed": 0}

    with sync_playwright() as playwright:
        context = launch_context(playwright)
        ensure_logged_in(context, email, password)
        page = context.pages[0] if context.pages else context.new_page()

        # A single exact-phrase search misses many postings (e.g. plain "Data Engineer" or
        # "Azure Data Engineer"), so search multiple broader terms and dedupe by URL.
        search_terms = list(dict.fromkeys(
            [config.profile.primary_role, *config.rules.apply_if_title_contains]
            + [f"{skill} Data Engineer" for skill in config.profile.core_skills]
        ))

        jobs_by_url = {}
        for i, term in enumerate(search_terms):
            if i > 0:
                time.sleep(random.uniform(*SEARCH_TERM_DELAY_RANGE_SECONDS))
            for job in search_jobs(page, term, max_results=60, max_pages=3):
                jobs_by_url.setdefault(job.url, job)
        jobs = list(jobs_by_url.values())
        logger.info("Collected %d unique jobs across %d search terms.", len(jobs), len(search_terms))

        for job in jobs:
            if applied_tracker.is_processed(job.url):
                summary["previously_processed"] += 1
                continue

            if page.is_closed():
                logger.error(
                    "Browser page was closed (crashed, or closed manually/by Naukri) - stopping the run "
                    "early instead of burning through the remaining %d jobs as instant failures.",
                    len(jobs) - sum(summary.values()),
                )
                break

            if not daily_limiter.has_capacity():
                logger.warning(
                    "Daily application limit (%d) reached - stopping the run early to stay well "
                    "under Naukri's own daily cap and avoid looking automated.",
                    daily_limiter.limit,
                )
                break

            if is_strong_title_match(job.title):
                logger.info("Applying to '%s' (title contains 'data' + 'engineer'; skill match check bypassed).", job.title)
                result = apply_to_job(page, job, question_bank)
                summary[result] = summary.get(result, 0) + 1
                applied_tracker.mark(job.url, result)
                if result not in ("already_applied", "company_site"):
                    daily_limiter.record_application()
                time.sleep(random.uniform(*APPLY_DELAY_RANGE_SECONDS))
                continue

            if not title_matches(job.title, config.rules.apply_if_title_contains):
                summary["not_matched"] += 1
                continue

            match_percent = skill_match_percent(job.skills, config.profile.core_skills)
            if match_percent < config.rules.apply_if_skill_match_gte_percent:
                logger.info("Skipping '%s': skill match %.1f%% below threshold.", job.title, match_percent)
                summary["not_matched"] += 1
                continue

            logger.info("Applying to '%s' (skill match %.1f%%).", job.title, match_percent)
            result = apply_to_job(page, job, question_bank)
            summary[result] = summary.get(result, 0) + 1
            applied_tracker.mark(job.url, result)
            if result not in ("already_applied", "company_site"):
                daily_limiter.record_application()
            time.sleep(random.uniform(*APPLY_DELAY_RANGE_SECONDS))

        logger.info("Run summary: %s (daily total: %d/%d)", summary, daily_limiter.count, daily_limiter.limit)

        input("Run finished. Press Enter to close the browser...")
        context.close()


if __name__ == "__main__":
    main()
