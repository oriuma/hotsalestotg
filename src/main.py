import os
from src.config import MAX_PAGES, STATE_FILE
from src.state import load_sent_ids, save_sent_ids, push_state_to_github
from src.pepper_client import fetch_page, normalize_deal, is_valid_deal
from src.telegram_client import send_deal
from src.ai_scorer import score_deal

GITHUB_REPO        = os.environ.get("GITHUB_REPOSITORY", "oriuma/hotsalestotg")
REMOTE_STATE_PATH  = "data/seen_ids.json"


def main():
    print(f"[main] Loading state from {STATE_FILE}")
    sent_ids = load_sent_ids(STATE_FILE)
    print(f"[main] Already sent: {len(sent_ids)} deals")

    new_count  = 0
    total_seen = 0

    for page in range(1, MAX_PAGES + 1):
        print(f"[main] Fetching page {page}/{MAX_PAGES}")
        threads = fetch_page(page)

        if not threads:
            print(f"[main] No threads on page {page}, stopping.")
            break

        for thread in threads:
            deal = normalize_deal(thread)
            if not deal:
                continue
            total_seen += 1

            if deal["id"] in sent_ids:
                continue

            if not is_valid_deal(deal):
                continue

            print(f"[main] New deal: {deal['title'][:60]} | temp={deal['temperature']}")

            # AI scoring (non-blocking: if it fails, post goes out without score)
            ai_score = score_deal(deal)

            success = send_deal(deal, ai_score=ai_score)

            if success:
                sent_ids.add(deal["id"])
                new_count += 1
            else:
                print(f"[main] Failed to send deal {deal['id']}")

    save_sent_ids(STATE_FILE, sent_ids)
    push_state_to_github(STATE_FILE, GITHUB_REPO, REMOTE_STATE_PATH)
    print(f"[main] Done. Seen: {total_seen}, sent new: {new_count}")


if __name__ == "__main__":
    main()
