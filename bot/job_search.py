"""Searches naukri.com for job listings matching keywords."""
from __future__ import annotations

import time
from dataclasses import dataclass
from playwright.sync_api import Page

from bot import selectors
from bot.logger import get_logger

logger = get_logger(__name__)

# Same rationale as APPLY_DELAY_SECONDS in main.py: back-to-back page.goto calls with no
# pause read as bot traffic and provoke Naukri's rate-limiting.
SEARCH_DELAY_SECONDS = 1


@dataclass
class JobListing:
    title: str
    company: str
    url: str
    skills: list[str]


def search_jobs(page: Page, keywords: str, max_results: int = 20, max_pages: int = 10) -> list[JobListing]:
    """Fetches job cards across multiple result pages, until max_results is reached or pages run out."""
    slug = keywords.lower().replace(" ", "-")
    listings: list[JobListing] = []

    for page_num in range(1, max_pages + 1):
        if page_num > 1:
            time.sleep(SEARCH_DELAY_SECONDS)

        page_url = (
            selectors.SEARCH_URL.format(keywords=slug)
            if page_num == 1
            else selectors.SEARCH_URL_PAGED.format(keywords=slug, page=page_num)
        )
        page.goto(page_url, wait_until="domcontentloaded")

        try:
            page.wait_for_selector(selectors.JOB_CARD, timeout=15_000)
        except Exception:
            logger.info("No more job cards found at page %d; stopping search.", page_num)
            break

        cards = page.locator(selectors.JOB_CARD)
        card_count = cards.count()
        logger.info("Found %d job cards on page %d for keywords '%s'.", card_count, page_num, keywords)

        for i in range(card_count):
            card = cards.nth(i)
            title_el = card.locator(selectors.JOB_TITLE)
            title = title_el.inner_text().strip()
            job_url = title_el.get_attribute("href") or ""
            company_el = card.locator(selectors.JOB_COMPANY_NAME)
            company = company_el.first.inner_text().strip() if company_el.count() > 0 else "Unknown"
            skills = [s.strip() for s in card.locator(selectors.JOB_SKILLS_TAGS).all_inner_texts()]
            listings.append(JobListing(title=title, company=company, url=job_url, skills=skills))

            if len(listings) >= max_results:
                return listings

    return listings
