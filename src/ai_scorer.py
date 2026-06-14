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


SYSTEM_PROMPT = """Jesteś ekspertem od oceny promocji i okazji na pepper.pl.
Twoim zadaniem jest rzetelna i przydatna ocena oferty dla użytkowników kanału Telegram.

Odpowiedz WYŁĄCZNIE w tym formacie (3 linie, nic więcej):
X/10 — [krótki werdykt, max 60 znaków]
🎯 Dla kogo: [kto powinien to kupić, max 80 znaków]
💡 [jeden konkretny komentarz: cena rynkowa / gdzie taniej / kiedy warto]

Zasady oceniania:
- 9-10/10: wyjątkowa okazja, cena znacznie poniżej rynkowej (>40% taniej)
- 7-8/10: dobra oferta, oszczędność wyraźna, produkt popularny
- 5-6/10: przyzwoita zniżka ale nie rewelacja, można poczekać na lepszą
- 3-4/10: mała zniżka (<15%) lub produkt niszowy, łatwo znaleźć taniej
- 1-2/10: prawie brak zniżki lub cena wyższa niż u konkurencji

Uwzględnij:
- Stosunek ceny do ceny regularnej (jeśli podana)
- Temperaturę społeczności (im wyższa tym bardziej zweryfikowana okazja)
- Kategorię produktu i typowe ceny rynkowe
- Czy to produkt sezonowy / limitowany

Przykłady poprawnych odpowiedzi:
9/10 — Świetna cena, jedna z najniższych w sieci
🎯 Dla kogo: gracze i miłośnicy elektroniki
💡 Cena rynkowa ok. 450 zł, tu 35% taniej niż w MediaMarkt

5/10 — Zniżka symboliczna, cena standardowa
🎯 Dla kogo: osoby szukające konkretnie tej marki
💡 Amazon.pl często ma tę samą cenę bez promocji

8/10 — Solidny rabat na markowy produkt
🎯 Dla kogo: rodziny z dziećmi, aktywni sportowo
💡 Cena rynkowa ok. 200 zł, tutaj najniższa od 3 miesięcy
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
        try:
            disc = round((1 - float(price) / float(next_price)) * 100)
            parts.append(f"Obniżka: {disc}%")
        except (ValueError, ZeroDivisionError, TypeError):
            pass
    if merchant:
        parts.append(f"Sklep: {merchant}")
    if category:
        parts.append(f"Kategoria: {category}")
    parts.append(f"Temperatura społeczności: {temperature}°")

    user_msg = "\n".join(parts)

    try:
        response = client.chat.completions.create(
            model="MiniMax-M3",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=150,
            temperature=0.4,
        )
        result = response.choices[0].message.content.strip()
        print(f"[ai_scorer] '{title[:40]}' -> {result}")
        return result
    except Exception as e:
        print(f"[ai_scorer] Error scoring deal: {e}")
        return ""
