"""Opens a job listing, clicks Apply, and answers any chatbot questions."""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import Page

from bot import selectors
from bot.job_search import JobListing
from bot.logger import get_logger
from bot.questionnaire import QuestionBank

logger = get_logger(__name__)

COMPANY_SITE_APPLICATIONS_PATH = Path("data/missing_apply.txt")
APPLY_ISSUES_PATH = Path("data/apply_issues.txt")
DEBUG_SNAPSHOT_DIR = Path("logs/debug")

ALREADY_APPLIED_TEXT = re.compile(r"applied", re.I)
APPLY_ON_COMPANY_SITE_TEXT = re.compile(r"apply on company site", re.I)
APPLY_BUTTON_TEXT = re.compile(r"^(easy )?apply( now)?$", re.I)

# Any of these appearing means the job's action area has finished rendering (it's a React SPA).
ACTION_AREA_READY_SELECTOR = (
    "button:has-text('Apply on company site'), a:has-text('Apply on company site'), "
    "button:has-text('Applied'), button:has-text('Easy Apply'), "
    "button:has-text('Apply Now'), button:has-text('Apply')"
)


def apply_to_job(page: Page, job: JobListing, question_bank: QuestionBank) -> str:
    """Applies to a job. Returns one of: 'applied', 'already_applied', 'company_site', 'skipped', 'error'."""
    try:
        page.goto(job.url, wait_until="domcontentloaded")
        page.wait_for_selector(ACTION_AREA_READY_SELECTOR, timeout=15_000)

        if _find_button(page, ALREADY_APPLIED_TEXT, selectors.ALREADY_APPLIED_INDICATOR).count() > 0:
            return "already_applied"

        if _find_button(page, APPLY_ON_COMPANY_SITE_TEXT, selectors.COMPANY_SITE_APPLY_BUTTON).count() > 0:
            _record_company_site_application(job)
            return "company_site"

        apply_button = _find_button(page, APPLY_BUTTON_TEXT, selectors.JOB_APPLY_BUTTON)
        apply_button.first.click(timeout=10_000)

        if page.locator(selectors.CHATBOT_CONTAINER).count() > 0:
            unanswered_question = _handle_chatbot(page, question_bank)
            if unanswered_question and question_bank.rules.never_invent_answers:
                logger.info("Skipping '%s': unanswerable question and never_invent_answers=true.", job.title)
                _record_apply_issue(job, unanswered_question)
                return "skipped"

        if not _confirm_application_submitted(page):
            # No "Applied" confirmation showed up after the apply click / chatbot flow (extra popup/resume-check
            # step, a stuck chatbot, or a UI variant we don't recognize) - don't blindly count this as applied.
            logger.warning("Could not confirm '%s' was actually submitted; flagging for manual review.", job.title)
            _record_apply_issue(job, "Apply flow did not show an 'Applied' confirmation - verify manually")
            _save_debug_snapshot(page, job)
            return "error"

        return "applied"
    except Exception:
        logger.exception("Failed to apply to '%s'.", job.title)
        _save_debug_snapshot(page, job)
        return "error"


def _confirm_application_submitted(page: Page, timeout: int = 10_000) -> bool:
    """After clicking Apply (no chatbot), polls for the button to flip to an 'Applied' state.

    Uses the same role-based lookup as the initial already-applied check, since a single
    get_by_text().first can latch onto an unrelated/hidden 'applied' match elsewhere on the page.
    """
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        if _find_button(page, ALREADY_APPLIED_TEXT, selectors.ALREADY_APPLIED_INDICATOR).count() > 0:
            return True
        page.wait_for_timeout(500)
    return False


def _find_button(page: Page, text: re.Pattern, css_fallback: str):
    """Prefers a resilient role/text-based locator, falling back to a raw CSS selector."""
    by_role = page.get_by_role("button", name=text)
    if by_role.count() > 0:
        return by_role

    by_text = page.get_by_text(text)
    if by_text.count() > 0:
        return by_text

    return page.locator(css_fallback)


def _save_debug_snapshot(page: Page, job: JobListing) -> None:
    """Saves a screenshot + HTML dump so selectors can be updated without re-running the bot."""
    try:
        DEBUG_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", job.title.lower()).strip("-")[:60]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = DEBUG_SNAPSHOT_DIR / f"{stamp}_{slug}"
        page.screenshot(path=f"{base}.png", full_page=True)
        Path(f"{base}.html").write_text(page.content(), encoding="utf-8")
        logger.info("Saved debug snapshot for '%s' to %s.{png,html}", job.title, base)
    except Exception:
        logger.exception("Failed to save debug snapshot for '%s'.", job.title)


def _record_company_site_application(job: JobListing) -> None:
    """Appends jobs that require applying on the company's own site, for manual follow-up."""
    COMPANY_SITE_APPLICATIONS_PATH.parent.mkdir(exist_ok=True)
    line = f"{job.company} | {job.title} | {job.url}\n"

    existing = (
        COMPANY_SITE_APPLICATIONS_PATH.read_text(encoding="utf-8")
        if COMPANY_SITE_APPLICATIONS_PATH.exists()
        else ""
    )
    if line not in existing:
        with COMPANY_SITE_APPLICATIONS_PATH.open("a", encoding="utf-8") as f:
            f.write(line)

    logger.info("'%s' at '%s' requires applying on the company site; recorded for manual follow-up.", job.title, job.company)


def _record_apply_issue(job: JobListing, question: str) -> None:
    """Appends jobs stuck on an unanswerable chatbot question, for manual follow-up."""
    APPLY_ISSUES_PATH.parent.mkdir(exist_ok=True)
    line = f"{job.company} | {job.title} | {question} | {job.url}\n"

    existing = APPLY_ISSUES_PATH.read_text(encoding="utf-8") if APPLY_ISSUES_PATH.exists() else ""
    if line not in existing:
        with APPLY_ISSUES_PATH.open("a", encoding="utf-8") as f:
            f.write(line)


def _handle_chatbot(page: Page, question_bank: QuestionBank, max_turns: int = 15) -> str | None:
    """Answers each chatbot question in turn. Returns the first unanswered question's text, or None."""
    for _ in range(max_turns):
        if page.locator(selectors.CHATBOT_CONTAINER).count() == 0:
            break

        questions = page.locator(selectors.CHATBOT_QUESTION_TEXT)
        if questions.count() == 0:
            break

        asked_text = questions.last.inner_text().strip()
        answer = question_bank.find_answer(asked_text)

        if answer is None:
            return asked_text

        options = page.locator(selectors.CHATBOT_OPTION_BUTTON)
        if options.count() > 0:
            options.filter(has_text=str(answer)).first.click()
        else:
            page.fill(selectors.CHATBOT_TEXT_INPUT, str(answer))
            page.click(selectors.CHATBOT_SEND_BUTTON)

        page.wait_for_timeout(1500)

    return None
