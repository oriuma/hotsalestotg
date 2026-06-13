import time
import requests
from src.config import PEPPER_GRAPHQL_URL, MIN_TEMPERATURE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.pepper.pl",
    "referer": "https://www.pepper.pl/najgoretsze",
    "x-pepper-txn": "index",
    "x-request-type": "application/vnd.pepper.v1+json",
    "x-requested-with": "XMLHttpRequest",
}

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

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # seconds between retries on 418/5xx


def fetch_page(page: int) -> list[dict]:
    """Fetch one page of hot deals from pepper.pl with retry on 418/5xx."""
    payload = {
        "operationName": "HottestDeals",
        "variables": {"page": page, "filter": {"feed": "hot"}},
        "query": GQL_QUERY,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                PEPPER_GRAPHQL_URL,
                headers=HEADERS,
                json=payload,
                timeout=20,
            )

            if resp.status_code == 200:
                data = resp.json()
                return (
                    data
                    .get("data", {})
                    .get("threadList", {})
                    .get("threads", [])
                ) or []

            elif resp.status_code == 418:
                # Server treating us as a bot - backoff and retry
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 30
                print(
                    f"[pepper_client] 418 I'm a teapot on page={page}, "
                    f"attempt {attempt + 1}/{MAX_RETRIES}. "
                    f"Waiting {delay}s before retry..."
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                else:
                    print(f"[pepper_client] All retries exhausted for page={page} (418).")
                    return []

            elif resp.status_code >= 500:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 30
                print(
                    f"[pepper_client] {resp.status_code} server error on page={page}, "
                    f"attempt {attempt + 1}/{MAX_RETRIES}. Waiting {delay}s..."
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                else:
                    return []

            else:
                # 4xx (not 418) — don't retry
                print(
                    f"[pepper_client] HTTP {resp.status_code} on page={page}: {resp.text[:200]}"
                )
                return []

        except requests.exceptions.Timeout:
            print(f"[pepper_client] Timeout on page={page}, attempt {attempt + 1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
        except Exception as e:
            print(f"[pepper_client] Exception on page={page}: {e}")
            return []

    return []


def normalize_deal(thread: dict) -> dict | None:
    """Convert raw pepper.pl thread into a clean deal dict."""
    thread_id = str(thread.get("threadId", ""))
    if not thread_id:
        return None

    title = thread.get("title", "")
    url   = thread.get("url", "")
    if not title or not url:
        return None

    temperature = thread.get("temperature", 0)
    price       = thread.get("price")
    next_price  = thread.get("nextBestPrice")
    merchant    = (thread.get("merchant") or {}).get("merchantName", "")
    category    = (thread.get("category") or {}).get("name", "")
    published   = thread.get("publishedAt", "")
    image_path  = (thread.get("mainImage") or {}).get("path", "")
    image_url   = f"https://www.pepper.pl{image_path}" if image_path else ""

    return {
        "id":          thread_id,
        "title":       title,
        "url":         url,
        "temperature": temperature,
        "price":       price,
        "next_price":  next_price,
        "merchant":    merchant,
        "category":    category,
        "published":   published,
        "image_url":   image_url,
    }


def is_valid_deal(deal: dict) -> bool:
    """Only pass deals that are hot enough and have a title+url."""
    return bool(
        deal.get("title")
        and deal.get("url")
        and deal.get("temperature", 0) >= MIN_TEMPERATURE
    )
