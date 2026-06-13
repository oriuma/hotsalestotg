import json
import os
import base64
import requests

GITHUB_API = "https://api.github.com"


def _gh_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_file_sha(repo: str, path: str) -> str | None:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=_gh_headers(), timeout=10)
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None


def load_sent_ids(path: str) -> set:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(x) for x in data) if isinstance(data, list) else set()
    except FileNotFoundError:
        return set()


def save_sent_ids(path: str, sent_ids: set):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(sent_ids), f, ensure_ascii=False, indent=2)


def push_state_to_github(local_path: str, repo: str, remote_path: str):
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[state] No GITHUB_TOKEN — skipping remote state push")
        return

    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read()

    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    file_sha = _get_file_sha(repo, remote_path)

    url = f"{GITHUB_API}/repos/{repo}/contents/{remote_path}"
    payload = {
        "message": "chore: update pepper seen_ids state",
        "content": encoded,
        "branch": "main",
    }
    if file_sha:
        payload["sha"] = file_sha

    resp = requests.put(url, headers=_gh_headers(), json=payload, timeout=15)
    if resp.status_code in (200, 201):
        print(f"[state] Remote state updated OK ({resp.status_code})")
    else:
        print(f"[state] Remote state update failed: {resp.status_code} {resp.text[:200]}")
