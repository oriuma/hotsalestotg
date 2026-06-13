import requests
from src.config import PEPPER_GRAPHQL_URL, MIN_TEMPERATURE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
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


def fetch_page(page: int) -> list[dict]:
    """Fetch one page of hot deals from pepper.pl. Returns list of thread dicts."""
    payload = {
        "operationName": "HottestDeals",
        "variables": {"page": page, "filter": {"feed": "hot"}},
        "query": GQL_QUERY,
    }
    try:
        resp = requests.post(
            PEPPER_GRAPHQL_URL,
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return (
            data
            .get("data", {})
            .get("threadList", {})
            .get("threads", [])
        ) or []
    except Exception as e:
        print(f"[pepper_client] fetch_page({page}) error: {e}")
        return []


def normalize_deal(thread: dict) -> dict | None:
    """Convert raw pepper.pl thread into a clean deal dict."""
    thread_id   = str(thread.get("threadId", ""))
    if not thread_id:
        return None

    title       = thread.get("title", "")
    url         = thread.get("url", "")
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
