from datetime import datetime, timezone


def _fmt_date(iso: str | None, prefix: str) -> str:
    """Format an ISO date string into a human-readable line."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())

        if prefix == "added":  # published — how long ago
            if diff < 60:
                return f"⏰ Dodano: {diff} sek. temu"
            elif diff < 3600:
                return f"⏰ Dodano: {diff // 60} min. temu"
            elif diff < 86400:
                return f"⏰ Dodano: {diff // 3600} godz. temu"
            else:
                return f"⏰ Dodano: {diff // 86400} dni temu ({dt.strftime('%d.%m.%Y')})"
        else:  # expiry — time remaining or already expired
            remaining = int((dt - now).total_seconds())
            if remaining <= 0:
                return f"⌛ Wygasło: {dt.strftime('%d.%m.%Y %H:%M')}"
            elif remaining < 3600:
                return f"⌛ Kończy się za: {remaining // 60} min."
            elif remaining < 86400:
                h = remaining // 3600
                m = (remaining % 3600) // 60
                return f"⌛ Kończy się za: {h}h {m}min ({dt.strftime('%d.%m %H:%M')})"
            else:
                days = remaining // 86400
                return f"⌛ Kończy się za: {days} dni ({dt.strftime('%d.%m.%Y')})"
    except Exception:
        return ""


def build_caption(deal: dict) -> str:
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
    expiry      = deal.get("expiry", "")

    # Price line
    if price is not None and str(price).strip() not in ("", "0", "0.0"):
        price_str = str(price).rstrip("0").rstrip(".")
        price_line = f"💰 <b>{price_str} zł</b>"
        if next_price is not None and str(next_price).strip() not in ("", "0", "0.0"):
            np_str = str(next_price).rstrip("0").rstrip(".")
            try:
                disc = round((1 - float(price) / float(next_price)) * 100)
                price_line += f"  <s>{np_str} zł</s>  <b>(-{disc}%)</b>"
            except (ValueError, ZeroDivisionError):
                pass
    else:
        price_line = "💰 <b>Bezpłatnie / sprawdź cenę</b>"

    lines = [
        f"🔥 <b>{title}</b>",
        "",
        price_line,
        f"🌡 Temperatura: <b>{temperature}°</b>",
    ]

    if merchant:
        lines.append(f"🏪 {merchant}")
    if category:
        lines.append(f"🗂 {category}")

    added_line = _fmt_date(published, "added")
    if added_line:
        lines.append(added_line)

    expiry_line = _fmt_date(expiry, "expiry")
    if expiry_line:
        lines.append(expiry_line)

    if url:
        lines.append("")
        lines.append(f'🔗 <a href="{url}">Zobacz na Pepper.pl →</a>')

    return "\n".join(lines)
