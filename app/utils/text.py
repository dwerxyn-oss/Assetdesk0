from __future__ import annotations

from html import escape


def h(value: object) -> str:
    return escape(str(value), quote=False)


def clip(value: str, limit: int) -> str:
    cleaned = value.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"
