"""Реферальная награда за первый заход по ссылке, с дневным лимитом."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import TASK_STATUS_COMPLETED, TRANSACTION_REFERRAL_REWARD
from app.db.models import Transaction, User, UserTask
from app.services.common import fresh
from app.services.ledger import credit
from app.utils.time import start_of_today_utc

logger = logging.getLogger(__name__)


async def count_invited(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by == user_id)
        )
        or 0
    )


async def count_qualified(session: AsyncSession, user_id: int) -> int:
    invited_ids = select(User.id).where(User.referred_by == user_id)
    return int(
        await session.scalar(
            select(func.count(func.distinct(UserTask.user_id))).where(
                UserTask.user_id.in_(invited_ids),
                UserTask.status == TASK_STATUS_COMPLETED,
            )
        )
        or 0
    )


async def referral_earned(session: AsyncSession, user_id: int) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == TRANSACTION_REFERRAL_REWARD,
        )
    )
    return int(total or 0)


async def rewards_today(session: AsyncSession, user_id: int) -> int:
    total = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == TRANSACTION_REFERRAL_REWARD,
            Transaction.created_at >= start_of_today_utc(),
        )
    )
    return int(total or 0)


async def reward_referrer_if_needed(session: AsyncSession, invited: User) -> None:
    """Вызывается внутри уже открытой транзакции записи."""
    if invited.referred_by is None or invited.referral_reward_paid:
        return
    settings = get_settings()
    referrer = await fresh(session, User, invited.referred_by)
    invited.referral_reward_paid = True
    if referrer is None or referrer.blocked:
        logger.info("referral reward skipped invited_id=%s", invited.id)
        return
    if settings.referral_reward <= 0:
        logger.info("referral reward disabled invited_id=%s", invited.id)
        return
    if await rewards_today(session, referrer.id) >= settings.referral_daily_limit:
        logger.info("referral daily limit referrer_id=%s", referrer.id)
        return
    await credit(
        session,
        referrer,
        settings.referral_reward,
        TRANSACTION_REFERRAL_REWARD,
        "Награда за приглашённого пользователя",
    )
    logger.info(
        "referral reward referrer_id=%s invited_id=%s amount=%s",
        referrer.id,
        invited.id,
        settings.referral_reward,
    )
