from __future__ import annotations

import re

_INT = re.compile(r"^-?\d+$")
_PRICE = re.compile(r"^(\d{1,9})\s+([A-Za-z]{2,10})$")
_CHANNEL_ID = re.compile(r"^-?\d+$")


def parse_int(value: str) -> int | None:
    raw = value.strip().replace(" ", "")
    if not _INT.fullmatch(raw):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_positive_int(value: str) -> int | None:
    number = parse_int(value)
    if number is None or number <= 0:
        return None
    return number


def parse_non_negative_int(value: str) -> int | None:
    number = parse_int(value)
    if number is None or number < 0:
        return None
    return number


def parse_price(value: str) -> tuple[int, str] | None:
    match = _PRICE.fullmatch(value.strip())
    if match is None:
        return None
    amount = int(match.group(1))
    if amount <= 0:
        return None
    return amount, match.group(2).upper()


def parse_channel(value: str) -> tuple[str | None, str | None] | None:
    raw = value.strip()
    if not raw or raw == "-":
        return None, None
    if raw.startswith("https://t.me/"):
        raw = raw.removeprefix("https://t.me/").split("/")[0]
    if raw.startswith("t.me/"):
        raw = raw.removeprefix("t.me/").split("/")[0]
    raw = raw.lstrip("@")
    if _CHANNEL_ID.fullmatch(raw):
        return None, raw
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", raw):
        return raw, None
    return None


def parse_start_referrer(payload: str | None) -> int | None:
    if not payload:
        return None
    raw = payload.strip()
    if not raw.startswith("ref_"):
        return None
    number = raw.removeprefix("ref_")
    if not number.isdigit():
        return None
    value = int(number)
    if value <= 0:
        return None
    return value


def parse_gift_number(value: str) -> str | None:
    raw = value.strip()
    if raw.startswith("#"):
        raw = raw[1:].strip()
    if not raw.isdigit() or not 1 <= len(raw) <= 12 or set(raw) == {"0"}:
        return None
    return raw.lstrip("0") or raw


def parse_trait(value: str, *, limit: int = 80) -> str | None:
    text = " ".join(value.split())
    if not text or len(text) > limit:
        return None
    return text


def parse_gift_text(value: str) -> tuple[str, str, str] | None:
    text = value.strip()
    if not text or len(text) > 500:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    link = ""
    for line in lines:
        if line.startswith(("http://", "https://")):
            link = line[:500]
            break
        if line.startswith("t.me/"):
            link = f"https://{line}"[:500]
            break
    name = lines[0][:200]
    if link and name.rstrip("/") == link.rstrip("/"):
        name = "Telegram Gift"
    return name, link, text[:500]
