from datetime import datetime, timezone


def time_ago(published_at: str) -> str:
    if not published_at:
        return ""
    # Pepper sometimes returns strings like "10 min temu" directly in GraphQL
    if "temu" in published_at or "ago" in published_at:
        return published_at
        
    try:
        published_at = published_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(published_at)
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())
        if diff < 60:
            return f"{diff} сек назад"
        elif diff < 3600:
            return f"{diff // 60} мин назад"
        elif diff < 86400:
            return f"{diff // 3600} ч назад"
        else:
            return f"{diff // 86400} дней назад"
    except Exception:
        return published_at


def build_caption(deal: dict, ai_score: str = "") -> str:
    """
    Build an HTML-formatted Telegram caption for one pepper.pl deal.
    """
    title       = deal.get("title", "Brak tytułu")
    url         = deal.get("url", "")
    temperature = deal.get("temperature", 0)
    price       = deal.get("price")
    next_price  = deal.get("next_price")
    merchant    = deal.get("merchant", "")
    category    = deal.get("category", "")
    published   = deal.get("published", "")

    # Price line
    if price:
        price_line = f"💰 <b>{price} PLN</b>"
        if next_price:
            try:
                disc = round((1 - float(price) / float(next_price)) * 100)
                price_line += f"  <s>{next_price} PLN</s>  <b>(-{disc}%)</b>"
            except (ValueError, ZeroDivisionError, TypeError):
                pass
    else:
        price_line = "💰 <b>Bezpłatnie / sprawdź cenę</b>"

    lines = [
        f"🔥 <b>{title}</b>",
        price_line,
        f"🌡 Temperatura: <b>{temperature}°</b>",
    ]

    if merchant:
        lines.append(f"🏪 Sklep: <b>{merchant}</b>")
    
    if category:
        lines.append(f"🗂 Kategoria: <b>{category}</b>")

    if ai_score:
        lines.append(f"\n🤖 <b>Ocena AI:</b>\n{ai_score}")

    ago = time_ago(published)
    if ago:
        lines.append(f"\n⏰ {ago}")

    if url:
        lines.append(f'🔗 <a href="{url}">Pepper.pl</a>')

    return "\n".join(lines)
