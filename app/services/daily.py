"""Бонус одного календарного дня в таймзоне из ENV."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import TRANSACTION_DAILY_BONUS
from app.db.models import User
from app.db.session import unit_of_work
from app.services.common import fresh
from app.services.ledger import credit
from app.utils.time import today_in_tz

logger = logging.getLogger(__name__)


async def claim(session: AsyncSession, user_id: int) -> str:
    """Коды: ok, already, disabled, missing."""
    settings = get_settings()
    if settings.daily_bonus <= 0:
        return "disabled"
    today = today_in_tz()
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing"
        if user.last_daily_bonus == today:
            return "already"
        user.last_daily_bonus = today
        await credit(
            session,
            user,
            settings.daily_bonus,
            TRANSACTION_DAILY_BONUS,
            "Бонус дня",
        )
    logger.info("daily bonus user_id=%s amount=%s", user_id, settings.daily_bonus)
    return "ok"
