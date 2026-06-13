import time
from json import JSONDecodeError
import requests
from src.config import PEPPER_GRAPHQL_URL, MIN_TEMPERATURE

# Persistent session — reuses cookies across requests (looks more like a real browser)
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "accept-encoding": "gzip, deflate, br",
    "content-type": "application/json",
    "origin": "https://www.pepper.pl",
    "referer": "https://www.pepper.pl/najgoretsze",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-pepper-txn": "index",
    "x-request-type": "application/vnd.pepper.v1+json",
    "x-requested-with": "XMLHttpRequest",
})

GQL_QUERY = """
query HottestDeals($page: Int, $filter: ThreadFilterInput) {
  threadList(page: $page, filter: $filter, sort: temperature) {
    threads {
      threadId
      title
      url
      temperature
      mainImage { path name }
      price
      nextBestPrice
      merchant { merchantName }
      publishedAt
      category { name }
    }
  }
}
"""

MAX_RETRIES = 4
RETRY_DELAYS = [3, 10, 20, 40]


def _warm_up_session():
    """GET the listing page first to pick up cookies, like a real browser would."""
    try:
        r = _session.get(
            "https://www.pepper.pl/najgoretsze",
            timeout=15,
            headers={"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        print(f"[pepper_client] Warm-up GET /najgoretsze → {r.status_code}")
    except Exception as e:
        print(f"[pepper_client] Warm-up failed (non-fatal): {e}")


def fetch_page(page: int) -> list[dict]:
    """Fetch one page of hot deals from pepper.pl with retry on 418/5xx/invalid JSON."""
    if page == 1:
        _warm_up_session()
        time.sleep(1.5)

    payload = {
        "operationName": "HottestDeals",
        "variables": {"page": page, "filter": {"feed": "hot"}},
        "query": GQL_QUERY,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = _session.post(PEPPER_GRAPHQL_URL, json=payload, timeout=20)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except JSONDecodeError:
                    print(
                        f"[pepper_client] Invalid JSON on page={page}, "
                        f"attempt {attempt + 1}/{MAX_RETRIES}. "
                        f"Body preview: {resp.text[:200]!r}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue
                    return []

                threads = (
                    data
                    .get("data", {})
                    .get("threadList", {})
                    .get("threads", [])
                ) or []
                print(f"[pepper_client] page={page} → {len(threads)} threads")
                return threads

            elif resp.status_code == 418:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 40
                print(
                    f"[pepper_client] 418 on page={page}, "
                    f"attempt {attempt + 1}/{MAX_RETRIES}, waiting {delay}s..."
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    _warm_up_session()
                    time.sleep(2)
                else:
                    print(f"[pepper_client] All retries exhausted for page={page}.")
                    return []

            elif resp.status_code >= 500:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 40
                print(f"[pepper_client] {resp.status_code} on page={page}, waiting {delay}s...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                else:
                    return []

            else:
                print(f"[pepper_client] HTTP {resp.status_code} on page={page}: {resp.text[:300]}")
                return []

        except requests.exceptions.Timeout:
            print(f"[pepper_client] Timeout page={page}, attempt {attempt + 1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
        except Exception as e:
            print(f"[pepper_client] Exception page={page}: {e}")
            return []

    return []


def normalize_deal(thread: dict) -> dict | None:
    thread_id = str(thread.get("threadId", ""))
    if not thread_id:
        return None
    title = thread.get("title", "")
    url   = thread.get("url", "")
    if not title or not url:
        return None

    image_path = (thread.get("mainImage") or {}).get("path", "")
    return {
        "id":          thread_id,
        "title":       title,
        "url":         url,
        "temperature": thread.get("temperature", 0),
        "price":       thread.get("price"),
        "next_price":  thread.get("nextBestPrice"),
        "merchant":    (thread.get("merchant") or {}).get("merchantName", ""),
        "category":    (thread.get("category") or {}).get("name", ""),
        "published":   thread.get("publishedAt", ""),
        "image_url":   f"https://www.pepper.pl{image_path}" if image_path else "",
    }


def is_valid_deal(deal: dict) -> bool:
    return bool(
        deal.get("title")
        and deal.get("url")
        and deal.get("temperature", 0) >= MIN_TEMPERATURE
    )
