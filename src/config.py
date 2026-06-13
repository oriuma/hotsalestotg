import os

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# --- Scraper settings ---
MIN_TEMPERATURE      = int(os.getenv("MIN_TEMPERATURE", "100"))   # degrees on pepper
MAX_PAGES            = int(os.getenv("MAX_PAGES", "3"))
TELEGRAM_SLEEP_SECONDS = float(os.getenv("TELEGRAM_SLEEP_SECONDS", "0.5"))

# --- State ---
STATE_FILE = os.getenv("STATE_FILE", "data/seen_ids.json")

# --- Pepper.pl ---
PEPPER_GRAPHQL_URL = "https://www.pepper.pl/graphql"
PEPPER_HOT_URL     = "https://www.pepper.pl/najgoretsze"
