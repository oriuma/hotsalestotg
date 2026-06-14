import os
from openai import OpenAI

_client = None


def _get_client() -> OpenAI | None:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("MINIMAX_API_TOKEN")
    if not api_key:
        print("[ai_scorer] MINIMAX_API_TOKEN not set, skipping AI scoring")
        return None
    _client = OpenAI(
        base_url="https://api.tokenrouter.com/v1",
        api_key=api_key,
    )
    return _client


SYSTEM_PROMPT = """Ты эксперт по оценке скидок и акций на польском сайте pepper.pl.
Твоя задача — кратко и честно оценить выгодность предложения.
Отвечай ТОЛЬКО в формате: X/10 — [одна фраза до 60 символов]
Примеры:
8/10 — Хорошая скидка, цена ниже рыночной
4/10 — Скидка небольшая, можно найти дешевле
9/10 — Отличная цена, бери не думая
"""


def score_deal(deal: dict) -> str:
    """
    Returns a short AI score string like '8/10 — Хорошая скидка'.
    Returns empty string if API is unavailable or fails.
    """
    client = _get_client()
    if client is None:
        return ""

    title = deal.get("title", "")
    price = deal.get("price", "")
    next_price = deal.get("next_price", "")
    temperature = deal.get("temperature", 0)
    merchant = deal.get("merchant", "")

    parts = [f"Title: {title}"]
    if price:
        parts.append(f"Price: {price} PLN")
    if next_price:
        parts.append(f"Regular price: {next_price} PLN")
    if merchant:
        parts.append(f"Store: {merchant}")
    parts.append(f"Community temperature: {temperature}")
    user_msg = "\n".join(parts)

    try:
        response = client.chat.completions.create(
            model="MiniMax-M3",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=60,
            temperature=0.3,
        )
        result = response.choices[0].message.content.strip()
        print(f"[ai_scorer] '{title[:40]}' -> {result}")
        return result
    except Exception as e:
        print(f"[ai_scorer] Error scoring deal: {e}")
        return ""
