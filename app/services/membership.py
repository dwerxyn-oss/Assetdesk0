"""Проверка подписки. Ошибки прав пишутся в лог, пользователю уходит короткое сообщение."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.config import get_settings

logger = logging.getLogger(__name__)

_MEMBER = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}


def _chat_ref(channel_username: str | None, channel_id: str | None) -> int | str | None:
    if channel_id:
        raw = channel_id.strip()
        if raw.lstrip("-").isdigit():
            return int(raw)
        return raw
    if channel_username:
        return f"@{channel_username.lstrip('@')}"
    return None


async def check_membership(
    bot: Bot,
    telegram_id: int,
    *,
    channel_username: str | None,
    channel_id: str | None,
) -> str:
    """Коды: member, not_member, no_rights, bad_channel."""
    chat_ref = _chat_ref(channel_username, channel_id)
    if chat_ref is None:
        logger.warning("subscription check skipped: channel is not configured")
        return "bad_channel"
    try:
        member = await bot.get_chat_member(chat_ref, telegram_id)
    except TelegramForbiddenError:
        logger.warning("subscription check forbidden chat=%s", chat_ref)
        return "no_rights"
    except TelegramBadRequest as exc:
        token = get_settings().bot_token
        detail = str(exc)
        if token:
            detail = detail.replace(token, "***")
        lowered = detail.lower()
        if "chat not found" in lowered or "username not occupied" in lowered:
            logger.warning("subscription check bad channel chat=%s detail=%s", chat_ref, detail)
            return "bad_channel"
        logger.warning("subscription check failed chat=%s detail=%s", chat_ref, detail)
        return "no_rights"
    status = member.status
    if status in _MEMBER:
        return "member"
    if status == ChatMemberStatus.RESTRICTED and bool(getattr(member, "is_member", False)):
        return "member"
    return "not_member"
