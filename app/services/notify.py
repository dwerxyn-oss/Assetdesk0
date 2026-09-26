"""Сообщения пользователю и администратору. Ошибки доставки не ломают заявку."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from app.config import get_settings
from app.utils.ui import PREVIEW_OFF

logger = logging.getLogger(__name__)


async def send_user(
    bot: Bot,
    telegram_id: int,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    try:
        await bot.send_message(
            telegram_id,
            text,
            reply_markup=markup,
            link_preview_options=PREVIEW_OFF,
        )
    except TelegramForbiddenError:
        logger.info("user blocked the bot telegram_id=%s", telegram_id)
    except Exception:
        logger.exception("failed to message user telegram_id=%s", telegram_id)


async def send_admin(
    bot: Bot,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    admin_id = get_settings().admin_id
    try:
        await bot.send_message(
            admin_id,
            text,
            reply_markup=markup,
            link_preview_options=PREVIEW_OFF,
        )
    except Exception:
        logger.exception("failed to message admin")
