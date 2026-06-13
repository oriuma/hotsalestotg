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

# Minimal query — only fields confirmed to exist in pepper.pl schema from HAR.
# Removed: options.selected, lastComment.hasVisibleComments (cause schema errors).
# No operationName in payload — avoids "Unknown operation" errors.
GQL_QUERY = """
query ($page: Int, $feed: String) {
  discussionWidget(
    page: $page,
    filter: { feed: { eq: $feed } }
  ) {
    threads {
      threadId
      title
      titleSlug
      type
      url
      isIndexed
      commentCount
      shortLastPublishedTimeAgo
      lastUpdatedDate
      user {
        userId
        username
        avatar { name path }
      }
      isBacklinksFeatureApplied
    }
  }
}
"""

MAX_RETRIES = 4
RETRY_DELAYS = [3, 10, 20, 40]


def _warm_up_session():
    """Replicate browser flow: GET /najgoretsze → POST /bpn/getRequestPermissionParams."""
    try:
        r = _session.get(
            "https://www.pepper.pl/najgoretsze",
            timeout=15,
            headers={"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        print(f"[pepper_client] Warm-up GET /najgoretsze → {r.status_code}")
    except Exception as e:
        print(f"[pepper_client] Warm-up GET failed (non-fatal): {e}")

    try:
        r2 = _session.post(
            "https://www.pepper.pl/bpn/getRequestPermissionParams",
            timeout=15,
            json={},
        )
        print(f"[pepper_client] bpn → {r2.status_code}")
        if r2.status_code == 200:
            try:
                payload = r2.json()
                token = payload.get("data", {}).get("token")
                if token:
                    _session.headers.update({"x-xsrf-token": token, "X-XSRF-TOKEN": token})
                    print(f"[pepper_client] XSRF token: {token[:20]}...")
                else:
                    print(f"[pepper_client] bpn: token not found in: {str(payload)[:300]}")
            except JSONDecodeError as e:
                print(f"[pepper_client] bpn not JSON: {e} | {r2.text[:200]!r}")
        else:
            print(f"[pepper_client] bpn non-200: {r2.text[:200]!r}")
    except Exception as e:
        print(f"[pepper_client] bpn failed (non-fatal): {e}")


def _extract_threads(data) -> tuple[list, list]:
    """
    Extract threads from a GraphQL response that may be:
    - a dict  (single response)
    - a list  (batched responses — browser sends multiple queries at once)
    Returns (threads, errors).
    """
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

    # No operationName — avoids "Unknown operation named X" schema errors
    payload = {
        "variables": {"page": page, "feed": "hot"},
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
                        f"[pepper_client] Invalid JSON page={page} "
                        f"attempt {attempt+1}/{MAX_RETRIES} "
                        f"encoding={resp.headers.get('Content-Encoding','none')} "
                        f"preview={resp.content[:120]!r}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue
                    return []

                threads, errors = _extract_threads(data)

                if errors:
                    print(f"[pepper_client] GraphQL errors page={page}: {str(errors)[:600]}")
                    if not threads:
                        # Schema error — no point retrying same payload
                        return []

                print(f"[pepper_client] page={page} → {len(threads)} threads")
                if not threads:
                    print(f"[pepper_client] Full response (4000): {str(data)[:4000]}")

                return threads

            elif resp.status_code == 418:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 40
                print(f"[pepper_client] 418 page={page} attempt {attempt+1} wait {delay}s")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    _warm_up_session()
                    time.sleep(2)
                else:
                    return []

            elif resp.status_code >= 500:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 40
                print(f"[pepper_client] {resp.status_code} page={page} wait {delay}s")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                else:
                    return []

            else:
                print(f"[pepper_client] HTTP {resp.status_code} page={page}: {resp.text[:300]}")
                return []

        except requests.exceptions.Timeout:
            print(f"[pepper_client] Timeout page={page} attempt {attempt+1}/{MAX_RETRIES}")
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
    url = thread.get("url", "")
    if not title or not url:
        return None

    avatar_path = ((thread.get("user") or {}).get("avatar") or {}).get("path", "")

    return {
        "id":           thread_id,
        "title":        title,
        "url":          url,
        # discussionWidget doesn't expose temperature — default high so filter passes
        "temperature":  thread.get("temperature", 999),
        "price":        thread.get("price"),
        "next_price":   thread.get("nextBestPrice"),
        "merchant":     "",
        "category":     "",
        "published":    thread.get("shortLastPublishedTimeAgo", ""),
        "image_url":    f"https://www.pepper.pl{avatar_path}" if avatar_path else "",
        "comment_count": thread.get("commentCount", 0),
    }


def is_valid_deal(deal: dict) -> bool:
    return bool(
        deal.get("title")
        and deal.get("url")
        and deal.get("temperature", 0) >= MIN_TEMPERATURE
    )
