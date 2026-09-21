"""Playwright browser/session management.

Launches a persistent Chrome(ium) profile instead of a fresh throwaway context. Reusing the same
profile directory run after run means cookies, local storage and cache accumulate like a real
returning visitor - one of the more effective anti-bot signals - instead of every run looking like
a brand-new browser. It also means you only ever go through the actual login form once; every run
after that reuses the still-valid session, so you don't repeatedly trigger Naukri's 2FA/verification
flow the way scripted logins do.

Always launches headed (headless=False). Headless Chromium has a distinct, easily fingerprinted
navigator/rendering signature, and Naukri is known to flag it - there is intentionally no toggle
for this.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import BrowserContext, Playwright

from bot import selectors
from bot.logger import get_logger

logger = get_logger(__name__)

# A dedicated profile the bot reuses every run, kept separate from your everyday Chrome profile so
# automation activity never mixes with your regular browsing/cookies. Override via
# CHROME_USER_DATA_DIR in .env if you deliberately want to point this at a different profile
# (e.g. your real daily Chrome profile) - just make sure Chrome/Chromium isn't already running
# against that same profile directory, since only one process can hold it at a time.
DEFAULT_PROFILE_DIR = Path("data/browser_profile")


def _install_chromium() -> None:
    logger.info("Chromium browser not found, installing via 'playwright install chromium'...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def launch_context(playwright: Playwright) -> BrowserContext:
    profile_dir = Path(os.environ.get("CHROME_USER_DATA_DIR", str(DEFAULT_PROFILE_DIR)))
    profile_dir.mkdir(parents=True, exist_ok=True)

    # CHROME_CHANNEL=chrome uses your actual installed Google Chrome instead of Playwright's
    # bundled Chromium, for an even closer match to a real daily-use browser. Optional - falls
    # back to bundled Chromium (auto-installed on first run) if unset or not found.
    channel = os.environ.get("CHROME_CHANNEL") or None

    launch_kwargs = dict(user_data_dir=str(profile_dir), headless=False, channel=channel)
    try:
        return playwright.chromium.launch_persistent_context(**launch_kwargs)
    except Exception as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        _install_chromium()
        return playwright.chromium.launch_persistent_context(**launch_kwargs)


def ensure_logged_in(context: BrowserContext, email: str, password: str) -> None:
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(selectors.LOGIN_URL, wait_until="domcontentloaded")

    # The reused session may redirect to the homepage after domcontentloaded fires, so wait it out here.
    try:
        page.wait_for_url("**/mnjuser/homepage**", timeout=5_000)
        logger.info("Already logged in (reused persistent profile session).")
        return
    except Exception:
        pass

    if "mnjuser" in page.url:
        logger.info("Already logged in (reused persistent profile session).")
        return

    page.wait_for_selector(selectors.LOGIN_EMAIL_INPUT, timeout=15_000)
    page.fill(selectors.LOGIN_EMAIL_INPUT, email)
    page.fill(selectors.LOGIN_PASSWORD_INPUT, password)
    page.click(selectors.LOGIN_SUBMIT_BUTTON)

    # If Naukri challenges this login (2FA/OTP/captcha), it'll show up in the visible browser here -
    # the longer timeout gives you room to clear it by hand before the wait gives up.
    page.wait_for_url("**/mnjuser/homepage**", timeout=60_000)
    logger.info("Login successful - this profile will stay logged in for future runs.")
