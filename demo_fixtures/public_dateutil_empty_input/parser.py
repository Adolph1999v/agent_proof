from datetime import date


def parse_date(text: str, default: date) -> date:
    normalized = text.strip()
    if not normalized:
        return default

    parts = normalized.split("-")
    if len(parts) != 3:
        raise ValueError("date must use YYYY-MM-DD")

    year, month, day = (int(part) for part in parts)
    return date(year, month, day)


def format_date(value: date) -> str:
    return value.isoformat()
