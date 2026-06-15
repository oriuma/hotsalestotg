import os
from openai import OpenAI

_client = None


def _get_client() -> OpenAI | None:
    global _client
    if _client is not None:
        return _client
    
    # Используем стандартные переменные окружения Manus для OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE")
    
    if not api_key:
        print("[ai_scorer] OPENAI_API_KEY not set, skipping AI scoring")
        return None
        
    _client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )
    return _client


SYSTEM_PROMPT = """Jesteś ekspertem od oceny promocji i okazji na pepper.pl.
Twoim zadaniem jest rzetelna i przydatna ocena oferty dla użytkowników kanału Telegram.

Odpowiedz WYŁĄCZNIE w tym formacie (3 linie, nic więcej):
X/10 — [krótki werdykt po polsku, max 60 znaków]
🎯 Dla kogo: [kto powinien to kupić po polsku, max 80 znaków]
💡 [jeden konkretny komentarz po polsku: cena rynkowa / gdzie taniej / kiedy warto]

Zasady oceniania:
- 9-10/10: wyjątkowa okazja, cena znacznie poniżej rynkowej (>40% taniej)
- 7-8/10: dobra oferta, oszczędność wyraźna, produkt popularny
- 5-6/10: przyzwoita zniżka ale nie rewelacja, można poczekać na lepszą
- 3-4/10: mała zniżka (<15%) или produkt niszowy, łatwo znaleźć taniej
- 1-2/10: prawie brak zniżki lub cena wyższa niż u konkurencji

Uwzględnij:
- Stosunek ceny do ceny regularnej
- Temperaturę społeczности (im wyższa tym bardziej zweryfikowana okazja)
- Kategorię produktu i typowe ceny rynkowe
"""


def score_deal(deal: dict) -> str:
    """
    Returns a multi-line AI score string.
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
    category = deal.get("category", "")

    parts = [f"Produkt: {title}"]
    if price:
        parts.append(f"Cena promocyjna: {price} PLN")
    if next_price:
        parts.append(f"Cena regularna: {next_price} PLN")
    if merchant:
        parts.append(f"Sklep: {merchant}")
    if category:
        parts.append(f"Kategoria: {category}")
    parts.append(f"Temperatura społeczności: {temperature}°")

    user_msg = "\n".join(parts)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Используем доступную модель
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=200,
            temperature=0.4,
        )
        result = response.choices[0].message.content.strip()
        print(f"[ai_scorer] '{title[:40]}' -> {result}")
        return result
    except Exception as e:
        print(f"[ai_scorer] Error scoring deal: {e}")
        return ""
