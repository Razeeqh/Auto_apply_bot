# Naukri Auto Applier Bot

Automates job search + application on naukri.com using Playwright, driven by
`Questionnaire.yaml` (profile, skill list, saved answers, and matching rules).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edit .env with your NAUKRI_EMAIL / NAUKRI_PASSWORD
```

The Chromium browser binary is installed automatically on first run (no
separate `playwright install` step needed).

## Run

```powershell
python main.py
```

## How it works

- `Questionnaire.yaml` — your profile, core skills, saved Q&A answers, and rules
  (minimum skill match %, title filters, whether to invent answers, etc.).
- `bot/matcher.py` — computes skill match % and title match against the rules.
- `bot/questionnaire.py` — fuzzy-matches a chatbot question to a saved answer;
  unmatched questions are appended to `data/new_questions.yaml` for you to
  review and add to `Questionnaire.yaml` (since `never_invent_answers: true`
  means the bot will never guess).
- `bot/selectors.py` — all CSS selectors used to interact with naukri.com in one
  place. Naukri's DOM changes periodically — if the bot can't find elements,
  run `playwright codegen https://www.naukri.com/nlogin/login` to capture fresh
  selectors and update this file.
- `data/browser_profile/` — a persistent Chrome profile the bot reuses every
  run (see below), so you only go through the real login form once.
- `data/daily_apply_count.json` — tracks today's application count against
  `DAILY_APPLY_LIMIT`, so several shorter runs in the same day still add up.

## Account safety / anti-detection

Naukri actively watches for automated application activity, and this bot's
defaults are built around not tripping that:

- **Always headed, never headless.** Headless Chromium has a distinct,
  fingerprintable signature. There's intentionally no config flag to turn
  this off.
- **Persistent browser profile.** `bot/browser.py` launches a dedicated Chrome
  profile at `data/browser_profile/` (via Playwright's
  `launch_persistent_context`) instead of a fresh context every run. Cookies,
  cache and local storage build up like a real returning visitor, and you
  only ever fill the login form once — after that the session is just reused,
  so you don't repeatedly trigger 2FA/OTP challenges the way scripted logins
  do. If Naukri does challenge a login, the browser is visible, so you can
  clear it by hand. See `.env.example` for `CHROME_USER_DATA_DIR` (point at a
  different profile) and `CHROME_CHANNEL=chrome` (use your real installed
  Chrome instead of bundled Chromium) if you want to go further.
- **Randomized delays, not fixed ones.** `main.py` waits 30 seconds to 3
  minutes (randomized) between apply attempts, and a short randomized gap
  between search terms. Fixed-interval timing is itself a bot signature —
  don't shrink this back down to a constant.
- **Daily application cap.** `DAILY_APPLY_LIMIT` (default 20, in `.env`) stops
  the run once reached, well under Naukri's own daily apply ceiling
  (~50) and under typical human volume. `already_applied`/`company_site`
  results don't count against it since no Apply click happens for those.
- **Test on a throwaway account first.** Whenever you change `selectors.py`
  or `applier.py`, run it against a test/dummy Naukri account before pointing
  it at your primary professional profile, to confirm it doesn't trip a
  verification challenge.

## Notes

- Review `logs/bot.log` after each run for a summary and any errors.
- At 15–20 applications/day with 30s–3min gaps, a full day's quota takes a
  while to run — that's the intended tradeoff for account safety over speed.
# Auto_apply_bot
