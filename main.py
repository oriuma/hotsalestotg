import os, json, time, requests
from pathlib import Path
from datetime import datetime, timezone

# ── config ──────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT   = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE      = Path(os.environ.get("STATE_FILE", "data/seen_ids.json"))
MIN_TEMPERATURE = int(os.environ.get("MIN_TEMPERATURE", "100"))  # min pepper temp
MAX_PAGES       = int(os.environ.get("MAX_PAGES", "3"))

# ── pepper.pl GraphQL ────────────────────────────────────────
GRAPHQL_URL = "https://www.pepper.pl/graphql"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl,ru;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "origin": "https://www.pepper.pl",
    "referer": "https://www.pepper.pl/najgoretsze",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "x-pepper-txn": "index",
    "x-request-type": "application/vnd.pepper.v1+json",
    "x-requested-with": "XMLHttpRequest",
}

# ── GraphQL query (persisted hash from HAR for hottest feed) ─
GQL_QUERY = """
query HottestDeals($page: Int, $filter: ThreadFilterInput) {
  threadList(page: $page, filter: $filter, sort: temperature) {
    threads {
      threadId
      title
      titleSlug
      url
      temperature
      mainImage {
        path
        name
      }
      price
      nextBestPrice
      merchant {
        merchantName
        merchantUrlName
      }
      publishedAt
      category {
        name
      }
    }
  }
}
"""


def load_seen() -> set:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_seen(seen: set):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(list(seen)))


def time_ago(published_at: str) -> str:
    if not published_at:
        return ""
    try:
        published_at = published_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(published_at)
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())
        if diff < 60:
            return f"{diff} сек назад"
        elif diff < 3600:
            m = diff // 60
            return f"{m} мин назад"
        elif diff < 86400:
            h = diff // 3600
            return f"{h} ч назад"
        else:
            d = diff // 86400
            return f"{d} дней назад"
    except Exception:
        return ""


def fetch_hot_deals(page: int = 1) -> list:
    """Fetch hot deals from pepper.pl /najgoretsze via GraphQL."""
    payload = {
        "operationName": "HottestDeals",
        "variables": {
            "page": page,
            "filter": {
                "feed": "hot"
            }
        },
        "query": GQL_QUERY,
    }
    try:
        resp = requests.post(
            GRAPHQL_URL,
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        threads = (
            data
            .get("data", {})
            .get("threadList", {})
            .get("threads", [])
        )
        return threads or []
    except Exception as e:
        print(f"[pepper] fetch_hot_deals(page={page}) error: {e}")
        return []


def build_message(thread: dict) -> str | None:
    """Build Telegram message from a pepper.pl thread."""
    thread_id  = str(thread.get("threadId", ""))
    title      = thread.get("title", "Brak tytułu")
    url        = thread.get("url", "")
    temperature = thread.get("temperature", 0)
    price      = thread.get("price")
    next_price = thread.get("nextBestPrice")
    merchant   = (thread.get("merchant") or {}).get("merchantName", "")
    category   = (thread.get("category") or {}).get("name", "")
    published  = thread.get("publishedAt", "")
    image_path = (thread.get("mainImage") or {}).get("path", "")

    if not title or not url:
        return None

    if temperature < MIN_TEMPERATURE:
        return None

    # Build price string
    if price:
        price_str = f"💰 *{price} PLN*"
        if next_price and float(next_price) > float(price):
            discount = round((1 - float(price) / float(next_price)) * 100)
            price_str += f"  ~~{next_price} PLN~~  (-{discount}%)"
    else:
        price_str = "💰 Bezpłatnie / cena w sklepie"

    ago = time_ago(published)
    ago_line = f"⏰ {ago}\n" if ago else ""

    merchant_line = f"🏪 {merchant}\n" if merchant else ""
    category_line = f"🗂 {category}\n" if category else ""

    text = (
        f"🔥 *{title}*\n"
        f"{price_str}\n"
        f"🌡 Temperatura: {temperature}°\n"
        f"{merchant_line}"
        f"{category_line}"
        f"{ago_line}"
        f"\n🔗 [Смотреть на Pepper.pl]({url})"
    )
    return text


def send_telegram(text: str, image_url: str | None = None) -> bool:
    base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    if image_url:
        r = requests.post(
            f"{base}/sendPhoto",
            json={
                "chat_id": TELEGRAM_CHAT,
                "photo": image_url,
                "caption": text,
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        if r.status_code == 200:
            return True
        print(f"  [sendPhoto] {r.status_code} — fallback to text")

    r = requests.post(
        f"{base}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=15,
    )
    if r.status_code != 200:
        print(f"  [sendMessage] error: {r.status_code} {r.text[:200]}")
    return r.status_code == 200


def main():
    seen = load_seen()
    new_count = 0

    for page in range(1, MAX_PAGES + 1):
        print(f"[pepper] Fetching page {page}...")
        threads = fetch_hot_deals(page)

        if not threads:
            print(f"  No threads on page {page}, stopping.")
            break

        for thread in threads:
            thread_id = str(thread.get("threadId", ""))
            if not thread_id:
                continue
            if thread_id in seen:
                continue

            text = build_message(thread)
            if not text:
                continue

            image_path = (thread.get("mainImage") or {}).get("path", "")
            image_url = f"https://www.pepper.pl{image_path}" if image_path else None

            print(f"  NEW: {thread_id} | {thread.get('title', '')[:60]} | temp={thread.get('temperature', 0)}")
            ok = send_telegram(text, image_url)
            if ok:
                seen.add(thread_id)
                new_count += 1
                time.sleep(0.5)

        time.sleep(1)

    save_seen(seen)
    print(f"\n[pepper] Done. Sent {new_count} new deals.")


if __name__ == "__main__":
    main()
