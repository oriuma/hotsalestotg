import time
import requests
from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_SLEEP_SECONDS
from src.formatter import build_caption

_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_deal(deal: dict, ai_score: str = "") -> bool:
    """
    Send a single deal to the Telegram channel.
    Returns True on success, False on failure.
    """
    caption = build_caption(deal, ai_score=ai_score)
    image_url = deal.get("image_url", "")

    if image_url:
        ok = _send_photo(image_url, caption)
        if not ok:
            ok = _send_message(caption)
    else:
        ok = _send_message(caption)

    if ok:
        time.sleep(TELEGRAM_SLEEP_SECONDS)
    return ok


def _send_photo(image_url: str, caption: str) -> bool:
    try:
        resp = requests.post(
            f"{_BASE}/sendPhoto",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("ok"):
            return True
        print(f"[telegram] sendPhoto failed: {data.get('description')}")
        return False
    except Exception as e:
        print(f"[telegram] sendPhoto exception: {e}")
        return False


def _send_message(caption: str) -> bool:
    try:
        resp = requests.post(
            f"{_BASE}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("ok"):
            return True
        print(f"[telegram] sendMessage failed: {data.get('description')}")
        return False
    except Exception as e:
        print(f"[telegram] sendMessage exception: {e}")
        return False
