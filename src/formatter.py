from datetime import datetime, timezone


def _fmt_published(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = int((now - dt).total_seconds())
        if diff < 60:
            return f"{diff} sek. temu"
        elif diff < 3600:
            return f"{diff // 60} min. temu"
        elif diff < 86400:
            return f"{diff // 3600} godz. temu"
        else:
            return f"{diff // 86400} dni temu ({dt.strftime('%d.%m.%Y')})"
    except Exception:
        return ""


def build_caption(deal: dict) -> str:
    title       = deal.get("title", "Brak tytu\u0142u")
    url         = deal.get("url", "")
    temperature = deal.get("temperature", 0)
    price       = deal.get("price")
    next_price  = deal.get("next_price")
    merchant    = deal.get("merchant", "")
    category    = deal.get("category", "")
    published   = deal.get("published", "")

    # Price line
    if price is not None and str(price).strip() not in ("", "0", "0.0"):
        price_str = str(price).rstrip("0").rstrip(".")
        price_line = f"\U0001f4b0 <b>{price_str} z\u0142</b>"
        if next_price is not None and str(next_price).strip() not in ("", "0", "0.0"):
            np_str = str(next_price).rstrip("0").rstrip(".")
            try:
                disc = round((1 - float(price) / float(next_price)) * 100)
                price_line += f"  <s>{np_str} z\u0142</s>  <b>(-{disc}%)</b>"
            except (ValueError, ZeroDivisionError):
                pass
    else:
        price_line = "\U0001f4b0 <b>Bezp\u0142atnie / sprawd\u017a cen\u0119</b>"

    lines = [
        f"\U0001f525 <b>{title}</b>",
        "",
        price_line,
        f"\U0001f321 Temperatura: <b>{temperature}\u00b0</b>",
    ]

    if merchant:
        lines.append(f"\U0001f3ea {merchant}")
    if category:
        lines.append(f"\U0001f5c2 {category}")

    ago = _fmt_published(published)
    if ago:
        lines.append(f"\u23f0 Dodano: {ago}")

    if url:
        lines.append("")
        lines.append(f'\U0001f517 <a href="{url}">Zobacz na Pepper.pl \u2192</a>')

    return "\n".join(lines)
