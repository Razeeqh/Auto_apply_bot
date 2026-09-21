"""Centralized CSS selectors for naukri.com.

Naukri's DOM changes fairly often. If the bot stops finding elements, use
`playwright codegen https://www.naukri.com/nlogin/login` to record fresh
selectors and update them here (this is the only file that should need edits).
"""

LOGIN_URL = "https://www.naukri.com/nlogin/login"
SEARCH_URL = "https://www.naukri.com/{keywords}-jobs"
SEARCH_URL_PAGED = "https://www.naukri.com/{keywords}-jobs-{page}"

LOGIN_EMAIL_INPUT = "#usernameField"
LOGIN_PASSWORD_INPUT = "#passwordField"
LOGIN_SUBMIT_BUTTON = "button[type='submit']"

JOB_CARD = "div.cust-job-tuple"
JOB_TITLE = "a.title"
JOB_COMPANY_NAME = "a.comp-name, .companyInfo a"
JOB_SKILLS_TAGS = "ul.tags-gt li"
JOB_APPLY_BUTTON = "button#apply-button, button.apply-button"
COMPANY_SITE_APPLY_BUTTON = "button:has-text('Apply on company site'), a:has-text('Apply on company site')"
ALREADY_APPLIED_INDICATOR = "button.already-applied, span.already-applied"

CHATBOT_CONTAINER = "div.chatbot_DrawerContentWrapper"
# Confirmed against a live debug snapshot (2026-08-26): the bot message text sits in a <span>,
# not a <p>, so the old "div.botMsg p" selector matched nothing and every chatbot question was
# silently treated as "no question to answer" - see logs/debug/20260826-121716_*.html.
CHATBOT_QUESTION_TEXT = "div.botMsg span"
# The free-text reply box is a contenteditable div (id="userInput__..." class="textArea") inside
# div.chatbot_InputContainer, not a <textarea>/<input> inside div.chatbot_InputAreaBox.
CHATBOT_TEXT_INPUT = "div.chatbot_InputContainer div[contenteditable='true']"
CHATBOT_SEND_BUTTON = "div.sendMsg"
CHATBOT_OPTION_BUTTON = "div.chatbot_ListItemHolder li"
