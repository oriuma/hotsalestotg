import time
from json import JSONDecodeError
import requests
from src.config import PEPPER_GRAPHQL_URL, MIN_TEMPERATURE

# Persistent session — reuses cookies across requests
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    # 'br' removed — requests doesn't decompress brotli natively
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

# -----------------------------------------------------------------------
# GraphQL query taken from real browser HAR capture on /najgoretsze.
# The browser batches many queries; we only extract the DiscussionWidget
# fragment which is the source of the hot-deal thread list on that page.
# Key difference from old code:
#   OLD: threadList(filter: ThreadFilterInput)   <- type no longer exists
#   NEW: discussionWidget(filter: {feed: "hot"}) <- actual live query
# -----------------------------------------------------------------------
GQL_QUERY = """
query HotDeals($page: Int, $feed: String) {
  discussionWidget(
    page: $page,
    filter: { feed: { eq: $feed } }
  ) {
    options { text value selected }
    threads {
      threadId
      title
      titleSlug
      type
      url
      isIndexed
      commentCount
      lastComment {
        commentId
        isReply
        user { userId username isUserProfileHidden isDeletedOrPendingDeletion avatar { name path } }
        hasVisibleComments
      }
      shortLastCommented
      shortLastPublishedTimeAgo
      lastUpdatedDate
      user {
        userId
        username
        isUserProfileHidden
        isDeletedOrPendingDeletion
        avatar { name path }
      }
      isBacklinksFeatureApplied
    }
  }
}
"""

# Separate query to get deal metadata (price, temperature, image)
# The thread list from DiscussionWidget doesn't include price/temp.
# We fetch those via the thread() query for each item, OR we use the
# persisted GET endpoint. For now: fetch hot deals via the widget and
# enrich with a second query that DOES have temperature.
# Actually the HAR shows the hot page uses this query to list threads
# by feed=hot. Temperature/price ARE available via thread(threadId) but
# that would be N+1. Better approach: use the widget but check if
# temperature is available as an extra field.
#
# Fallback enriched query — includes temperature directly if schema allows:
GQL_QUERY_ENRICHED = """
query HotDealsEnriched($page: Int, $feed: String) {
  discussionWidget(
    page: $page,
    filter: { feed: { eq: $feed } }
  ) {
    threads {
      threadId
      title
      type
      url
      commentCount
      shortLastPublishedTimeAgo
      lastUpdatedDate
      user { userId username avatar { name path } }
    }
  }
}
"""

MAX_RETRIES = 4
RETRY_DELAYS = [3, 10, 20, 40]


def _warm_up_session():
    """
    1. GET /najgoretsze to pick up session cookies (like a real browser).
    2. POST /bpn/getRequestPermissionParams to obtain XSRF token.
    Browser always does both before sending GraphQL requests.
    """
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
        print(f"[pepper_client] bpn/getRequestPermissionParams → {r2.status_code}")
        if r2.status_code == 200:
            try:
                payload = r2.json()
                token = payload.get("data", {}).get("token")
                if token:
                    _session.headers.update({
                        "x-xsrf-token": token,
                        "X-XSRF-TOKEN": token,
                    })
                    print(f"[pepper_client] XSRF token: {token[:20]}...")
                else:
                    print(f"[pepper_client] bpn token missing: {str(payload)[:300]}")
            except JSONDecodeError as e:
                print(f"[pepper_client] bpn not JSON: {e} | {r2.text[:200]!r}")
        else:
            print(f"[pepper_client] bpn non-200: {r2.text[:200]!r}")
    except Exception as e:
        print(f"[pepper_client] bpn request failed (non-fatal): {e}")


def fetch_page(page: int) -> list[dict]:
    """Fetch one page of hot deals from pepper.pl."""
    if page == 1:
        _warm_up_session()
        time.sleep(1.5)

    # Try enriched query first, fall back to basic if it errors
    for query_version, gql in [("enriched", GQL_QUERY_ENRICHED), ("basic", GQL_QUERY)]:
        threads = _do_fetch(page, gql, query_version)
        if threads is not None:  # None = hard error, [] = empty result
            return threads
    return []


def _do_fetch(page: int, gql: str, label: str) -> list[dict] | None:
    """Execute a single GraphQL query, return threads list or None on hard error."""
    payload = {
        "operationName": "HotDeals" if "Enriched" not in label else "HotDealsEnriched",
        "variables": {"page": page, "feed": "hot"},
        "query": gql,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = _session.post(PEPPER_GRAPHQL_URL, json=payload, timeout=20)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except JSONDecodeError:
                    print(
                        f"[pepper_client] [{label}] Invalid JSON page={page} "
                        f"attempt {attempt+1}/{MAX_RETRIES} "
                        f"Content-Encoding={resp.headers.get('Content-Encoding','none')} "
                        f"preview={resp.content[:120]!r}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                        continue
                    return None

                # Check for GraphQL schema errors
                errors = data.get("errors")
                if errors:
                    print(f"[pepper_client] [{label}] GraphQL errors page={page}: {str(errors)[:500]}")
                    # Schema error — don't retry, signal caller to try next query version
                    return None

                threads = (
                    data
                    .get("data", {})
                    .get("discussionWidget", {})
                    .get("threads", [])
                ) or []
                print(f"[pepper_client] [{label}] page={page} → {len(threads)} threads")

                if len(threads) == 0:
                    print(f"[pepper_client] [{label}] Full response (4000 chars): {str(data)[:4000]}")

                return threads

            elif resp.status_code == 418:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 40
                print(f"[pepper_client] 418 page={page} attempt {attempt+1}/{MAX_RETRIES} wait {delay}s")
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
                return None

        except requests.exceptions.Timeout:
            print(f"[pepper_client] Timeout page={page} attempt {attempt+1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
        except Exception as e:
            print(f"[pepper_client] Exception page={page}: {e}")
            return None

    return []


def normalize_deal(thread: dict) -> dict | None:
    thread_id = str(thread.get("threadId", ""))
    if not thread_id:
        return None
    title = thread.get("title", "")
    url = thread.get("url", "")
    if not title or not url:
        return None

    # DiscussionWidget threads don't expose price/temperature directly.
    # We set temperature=999 so all pass the MIN_TEMPERATURE filter,
    # and leave price empty. A future enhancement can call thread(id) to enrich.
    avatar = (thread.get("user") or {}).get("avatar") or {}
    avatar_path = avatar.get("path", "")

    return {
        "id":          thread_id,
        "title":       title,
        "url":         url,
        "temperature": thread.get("temperature", 999),
        "price":       thread.get("price"),
        "next_price":  thread.get("nextBestPrice"),
        "merchant":    "",
        "category":    "",
        "published":   thread.get("shortLastPublishedTimeAgo", ""),
        "image_url":   f"https://www.pepper.pl{avatar_path}" if avatar_path else "",
        "comment_count": thread.get("commentCount", 0),
    }


def is_valid_deal(deal: dict) -> bool:
    return bool(
        deal.get("title")
        and deal.get("url")
        and deal.get("temperature", 0) >= MIN_TEMPERATURE
    )
