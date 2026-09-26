"""Ссылки бота. Username берётся из настроек, не из кода."""

from __future__ import annotations

from app.config import get_settings


def referral_link(telegram_id: int) -> str:
    username = get_settings().bot_username
    return f"https://t.me/{username}?start=ref_{telegram_id}"


def support_link() -> str:
    return f"https://t.me/{get_settings().support_username}"


def channel_link(username: str | None) -> str | None:
    if not username:
        return None
    return f"https://t.me/{username.lstrip('@')}"
