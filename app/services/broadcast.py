"""Рассылка только незаблокированным пользователям."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.utils.ui import PREVIEW_OFF

logger = logging.getLogger(__name__)


async def recipient_ids(session: AsyncSession) -> list[int]:
    rows = await session.scalars(
        select(User.telegram_id).where(User.blocked.is_(False)).order_by(User.id.asc())
    )
    return list(rows)


async def broadcast(bot: Bot, telegram_ids: list[int], text: str) -> tuple[int, int]:
    delivered = 0
    failed = 0
    for index, telegram_id in enumerate(telegram_ids, start=1):
        try:
            await bot.send_message(telegram_id, text, link_preview_options=PREVIEW_OFF)
            delivered += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(telegram_id, text, link_preview_options=PREVIEW_OFF)
                delivered += 1
            except Exception:
                failed += 1
                logger.info("broadcast retry failed telegram_id=%s", telegram_id)
        except TelegramForbiddenError:
            failed += 1
            logger.info("broadcast skipped telegram_id=%s", telegram_id)
        except Exception:
            failed += 1
            logger.exception("broadcast failed telegram_id=%s", telegram_id)
        if index % 100 == 0:
            logger.info("broadcast progress %s/%s", index, len(telegram_ids))
        await asyncio.sleep(0.05)
    logger.info("broadcast finished delivered=%s failed=%s", delivered, failed)
    return delivered, failed
