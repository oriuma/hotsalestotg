import os

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# --- Scraper settings ---
# MIN_TEMPERATURE: minimum community heat score to post
# Default 30 — filters out dead/zero-temp discussions
MIN_TEMPERATURE        = int(os.getenv("MIN_TEMPERATURE", "30"))
MAX_PAGES              = int(os.getenv("MAX_PAGES", "3"))
TELEGRAM_SLEEP_SECONDS = float(os.getenv("TELEGRAM_SLEEP_SECONDS", "3.0"))

# MAX_AGE_DAYS: skip deals older than N days (0 = no limit)
# Default 7 — filters out deals from months/years ago
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "7"))

# --- State ---
STATE_FILE = os.getenv("STATE_FILE", "data/seen_ids.json")

# --- Pepper.pl ---
PEPPER_GRAPHQL_URL = "https://www.pepper.pl/graphql"
PEPPER_HOT_URL     = "https://www.pepper.pl/najgoretsze"

# --- AI Scoring (MiniMax via TokenRouter) ---
# Secret: MINIMAX_API_TOKEN (set in GitHub Actions secrets)
# If not set, scoring is silently skipped — posts still go out without AI score
MINIMAX_API_TOKEN  = os.getenv("MINIMAX_API_TOKEN", "")
