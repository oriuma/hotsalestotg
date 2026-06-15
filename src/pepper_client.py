import time
from json import JSONDecodeError
import requests
from src.config import PEPPER_GRAPHQL_URL, MIN_TEMPERATURE

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "accept-encoding": "gzip, deflate",
    "content-type": "application/json",
    "origin": "https://www.pepper.pl",
    "referer": "https://www.pepper.pl/najgoretsze",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not-A.Brand";v="99"',
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
      mainImage {
        name
        path
      }
      merchant {
        name
      }
      groups {
        name
      }
    }
  }
}
"""

MAX_RETRIES = 4
RETRY_DELAYS = [3, 10, 20, 40]


def _warm_up_session():
    try:
        r = _session.get(
            "https://www.pepper.pl/najgoretsze",
            timeout=15,
            headers={"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        print(f"[pepper_client] Warm-up GET /najgoretsze -> {r.status_code}")
    except Exception as e:
        print(f"[pepper_client] Warm-up GET failed (non-fatal): {e}")

    try:
        r2 = _session.post(
            "https://www.pepper.pl/bpn/getRequestPermissionParams",
            timeout=15,
            json={},
        )
        if r2.status_code == 200:
            try:
                payload = r2.json()
                token = payload.get("data", {}).get("token")
                if token:
                    _session.headers.update({"x-xsrf-token": token, "X-XSRF-TOKEN": token})
                    print(f"[pepper_client] XSRF token acquired")
            except JSONDecodeError:
                pass
    except Exception as e:
        print(f"[pepper_client] bpn failed (non-fatal): {e}")


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


def normalize_deal(thread: dict) -> dict | None:
    thread_id = str(thread.get("threadId", ""))
    if not thread_id:
        return None
    title = thread.get("title", "")
    url = thread.get("url", "")
    if not title or not url:
        return None

    # Исправлено: берем изображение товара, а не аватар пользователя
    image_path = (thread.get("mainImage") or {}).get("path", "")
    image_url = ""
    if image_path:
        # Pepper использует разные домены для изображений, но часто работает через основной
        image_url = f"https://www.pepper.pl/assets/img/{image_path}"
        # Для GraphQL ответов путь обычно уже содержит необходимые части
        if image_path.startswith("threads/"):
            image_url = f"https://static.pepper.pl/{image_path}"

    merchant = (thread.get("merchant") or {}).get("name", "")
    groups = thread.get("groups", [])
    category = groups[0].get("name", "") if groups else ""

    return {
        "id":           thread_id,
        "title":        title,
        "url":          url,
        "temperature":  thread.get("temperature", 0),
        "price":        thread.get("price"),
        "next_price":   thread.get("nextBestPrice"),
        "merchant":     merchant,
        "category":     category,
        "published":    thread.get("shortLastPublishedTimeAgo", ""),
        "image_url":    image_url,
        "comment_count": thread.get("commentCount", 0),
    }


def is_valid_deal(deal: dict) -> bool:
    return bool(
        deal.get("title")
        and deal.get("url")
        and deal.get("temperature", 0) >= MIN_TEMPERATURE
    )
