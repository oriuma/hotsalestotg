import time
import requests
from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_SLEEP_SECONDS

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    url = f"{TG_API}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] sendMessage error: {e}")
        return False


def send_photo(photo_url: str, caption: str, parse_mode: str = "HTML") -> bool:
    url = f"{TG_API}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] sendPhoto error: {e}")
        return False


def send_deal(deal: dict) -> bool:
    from src.formatter import build_caption

    caption = build_caption(deal)
    photo   = deal.get("image_url")

    success = False
    if photo:
        success = send_photo(photo, caption)
    if not success:
        success = send_message(caption)

    time.sleep(TELEGRAM_SLEEP_SECONDS)
    return success
