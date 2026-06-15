import time
from datetime import datetime, timezone
from json import JSONDecodeError
import requests
from src.config import PEPPER_GRAPHQL_URL, MIN_TEMPERATURE, MAX_AGE_DAYS

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.pepper.pl",
    "referer": "https://www.pepper.pl/najgoretsze",
})

GQL_QUERY = """
query DiscussionWidget($page: Int, $feed: String) {
  discussionWidget(
    page: $page,
    filter: { feed: { eq: $feed } }
  ) {
    threads {
      threadId
      title
      url
      temperature
      price
      nextBestPrice
      shortLastPublishedTimeAgo
      publishedAt
      mainImage {
        path
      }
    }
  }
}
"""

MAX_RETRIES = 4
RETRY_DELAYS = [3, 10, 20, 40]

# Discussion-only keywords — threads that are not deals
_SKIP_KEYWORDS = [
    "instrukcja", "poradnik", "jak kupic", "jak kupić",
    "pytanie", "scam", "oszustwo", "nowe funkcje",
    "informacje o", "czy ktoś", "czy znacie", "czy warto",
    "numer do odbierania", "wirtualny numer", "bramka sms",
    "legitny", "polecacie", "poszukuje", "szukam",
]


def _warm_up_session():
    try:
        _session.get(
            "https://www.pepper.pl/najgoretsze",
            timeout=15,
            headers={"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        print("[pepper_client] Warm-up GET /najgoretsze -> 200")
    except Exception:
        pass

    try:
        r2 = _session.post(
            "https://www.pepper.pl/bpn/getRequestPermissionParams",
            timeout=15,
            json={},
        )
        if r2.status_code == 200:
            print("[pepper_client] bpn -> 200")
            try:
                payload = r2.json()
                token = payload.get("data", {}).get("token")
                if token:
                    _session.headers.update({"x-xsrf-token": token, "X-XSRF-TOKEN": token})
                    print("[pepper_client] XSRF token acquired")
            except JSONDecodeError:
                pass
    except Exception:
        pass


def _extract_threads(data) -> tuple[list, list]:
    if isinstance(data, list):
        errors = []
        for item in data:
            if "errors" in item:
                errors.extend(item["errors"])
            widget = item.get("data", {}).get("discussionWidget")
            if widget:
                return widget.get("threads", []) or [], errors
        return [], errors
    else:
        errors = data.get("errors") or []
        threads = (
            data
            .get("data", {})
            .get("discussionWidget", {})
            .get("threads", [])
        ) or []
        return threads, errors


def fetch_page(page: int) -> list[dict]:
    if page == 1:
        _warm_up_session()
        time.sleep(1.5)

    payload = {
        "operationName": "DiscussionWidget",
        "variables": {"page": page, "feed": "popular"},
        "query": GQL_QUERY,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = _session.post(PEPPER_GRAPHQL_URL, json=payload, timeout=20)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except JSONDecodeError:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue
                    return []

                threads, errors = _extract_threads(data)
                if errors:
                    print(f"[pepper_client] GraphQL errors page={page}: {str(errors)[:600]}")
                    if not threads:
                        return []

                print(f"[pepper_client] page={page} -> {len(threads)} threads")
                return threads

            elif resp.status_code == 418:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 40
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    _warm_up_session()
                    time.sleep(2)
                else:
                    return []
            else:
                return []
        except Exception as e:
            print(f"[pepper_client] Exception page={page}: {e}")
            return []

    return []


def _is_old(published_at: str) -> bool:
    """Return True if published_at is older than MAX_AGE_DAYS. Skips check if MAX_AGE_DAYS=0."""
    if not MAX_AGE_DAYS or not published_at:
        return False
    # pepper shortLastPublishedTimeAgo strings like "10 min temu", "3 godz. temu",
    # "wczoraj", "2 dni temu", month names, or ISO timestamps
    low = published_at.lower()
    # already relative — safe heuristics
    if any(x in low for x in ["min temu", "godz. temu", "godzin", "dziś", "dzis", "just now"]):
        return False
    if "wczoraj" in low or "yesterday" in low:
        return MAX_AGE_DAYS < 2
    # "X dni temu"
    for word in low.split():
        if word.isdigit():
            val = int(word)
            if "dni" in low or "day" in low:
                return val > MAX_AGE_DAYS
    # ISO timestamp fallback
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - dt).days
        return age_days > MAX_AGE_DAYS
    except Exception:
        pass
    # Month names in Polish indicate old post (> 7 days)
    months_pl = ["sty", "lut", "mar", "kwi", "maj", "cze",
                 "lip", "sie", "wrz", "paź", "lis", "gru"]
    if any(m in low for m in months_pl):
        return True
    return False


def _is_discussion(title: str) -> bool:
    """Return True if the title looks like a discussion/question rather than a deal."""
    low = title.lower()
    # Ends with question mark = discussion
    if low.strip().endswith("?"):
        return True
    for kw in _SKIP_KEYWORDS:
        if kw in low:
            return True
    return False


def normalize_deal(thread: dict) -> dict | None:
    thread_id = str(thread.get("threadId", ""))
    if not thread_id:
        return None
    title = thread.get("title", "")
    url = thread.get("url", "")
    if not title or not url:
        return None

    image_path = (thread.get("mainImage") or {}).get("path", "")
    image_url = ""
    if image_path:
        if not image_path.startswith("http"):
            image_url = f"https://static.pepper.pl/{image_path}"
        else:
            image_url = image_path

    # prefer ISO publishedAt for age check, fallback to short string
    published_iso = thread.get("publishedAt", "")
    published_short = thread.get("shortLastPublishedTimeAgo", "")

    return {
        "id":            thread_id,
        "title":         title,
        "url":           url,
        "temperature":   thread.get("temperature", 0),
        "price":         thread.get("price"),
        "next_price":    thread.get("nextBestPrice"),
        "merchant":      "",
        "category":      "",
        "published":     published_short,
        "published_iso": published_iso,
        "image_url":     image_url,
        "comment_count": thread.get("commentCount", 0),
    }


def is_valid_deal(deal: dict) -> bool:
    """Return True only for real, recent, hot-enough deals."""
    if not deal.get("title") or not deal.get("url"):
        return False

    temp = deal.get("temperature", 0)
    # temp=999 is a sentinel Pepper uses for pinned/discussion threads
    if temp == 999:
        print(f"[filter] Skipped (temp=999 discussion): {deal['title'][:60]}")
        return False

    if temp < MIN_TEMPERATURE:
        print(f"[filter] Skipped (temp={temp} < {MIN_TEMPERATURE}): {deal['title'][:60]}")
        return False

    # Skip questions / how-to threads by title
    if _is_discussion(deal["title"]):
        print(f"[filter] Skipped (discussion): {deal['title'][:60]}")
        return False

    # Skip old posts
    age_field = deal.get("published_iso") or deal.get("published", "")
    if _is_old(age_field):
        print(f"[filter] Skipped (old): {deal['title'][:60]}")
        return False

    return True
