"""Заявки на вывод. Средства резервируются сразу и списываются один раз."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import (
    PAYOUT_METHODS,
    PAYOUT_STARS,
    WITHDRAWAL_CANCELLED,
    WITHDRAWAL_COMPLETED,
    WITHDRAWAL_REJECTED,
    WITHDRAWAL_TRANSITIONS,
)
from app.db.models import Reward, User, Withdrawal
from app.db.session import unit_of_work
from app.services.common import fresh
from app.services.ledger import LedgerError, record_withdrawal
from app.utils.text import clip
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def minimum_for(user: User) -> int:
    settings = get_settings()
    if user.total_withdrawn <= 0:
        return settings.first_withdraw_min
    return settings.regular_withdraw_min


async def list_for_user(session: AsyncSession, user_id: int, limit: int = 10) -> list[Withdrawal]:
    rows = await session.scalars(
        select(Withdrawal)
        .where(Withdrawal.user_id == user_id)
        .order_by(Withdrawal.id.desc())
        .limit(limit)
    )
    return list(rows)


async def list_by_status(
    session: AsyncSession,
    status: str,
    *,
    offset: int,
    limit: int,
) -> list[Withdrawal]:
    rows = await session.scalars(
        select(Withdrawal)
        .where(Withdrawal.status == status)
        .order_by(Withdrawal.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows)


async def get_withdrawal(session: AsyncSession, withdrawal_id: int) -> Withdrawal | None:
    return await session.get(Withdrawal, withdrawal_id)


async def create_withdrawal(
    session: AsyncSession,
    user_id: int,
    amount: int,
    reward_id: int | None = None,
    payout: str = PAYOUT_STARS,
) -> tuple[str, Withdrawal | None]:
    if payout not in PAYOUT_METHODS:
        return "bad_method", None
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing", None
        if type(amount) is not int or amount <= 0:
            return "bad_amount", None
        minimum = minimum_for(user)
        available = user.balance - user.reserved_balance
        if amount < minimum:
            return "too_small", None
        if amount > available:
            return "insufficient", None
        if reward_id is not None:
            reward = await fresh(session, Reward, reward_id)
            if reward is None or not reward.active:
                return "bad_reward", None
            if reward.cost_stars != amount:
                return "bad_reward", None
        user.reserved_balance += amount
        withdrawal = Withdrawal(
            user_id=user.id,
            reward_id=reward_id,
            amount=amount,
            currency=payout,
            payment_method=payout,
            status="pending",
            funds_held=True,
        )
        session.add(withdrawal)
        await session.flush()
        logger.info(
            "withdrawal created id=%s user_id=%s telegram_id=%s amount=%s payout=%s",
            withdrawal.id,
            user.id,
            user.telegram_id,
            amount,
            payout,
        )
        return "ok", withdrawal


async def set_status(
    session: AsyncSession,
    withdrawal_id: int,
    new_status: str,
    *,
    note: str = "",
) -> str:
    if new_status not in WITHDRAWAL_TRANSITIONS:
        return "bad_status"
    async with unit_of_work(session):
        try:
            withdrawal = await fresh(session, Withdrawal, withdrawal_id)
            if withdrawal is None:
                return "missing"
            if new_status not in WITHDRAWAL_TRANSITIONS[withdrawal.status]:
                return "bad_status"
            user = await fresh(session, User, withdrawal.user_id)
            if user is None:
                return "missing"
            if new_status == WITHDRAWAL_COMPLETED:
                if not withdrawal.funds_held:
                    return "bad_status"
                await record_withdrawal(
                    session,
                    user,
                    withdrawal.amount,
                    f"Вывод #{withdrawal.id}",
                )
                withdrawal.funds_held = False
                withdrawal.completed_at = utcnow()
            elif new_status in {WITHDRAWAL_REJECTED, WITHDRAWAL_CANCELLED}:
                if withdrawal.funds_held:
                    user.reserved_balance -= withdrawal.amount
                    withdrawal.funds_held = False
            withdrawal.status = new_status
            if note.strip():
                withdrawal.admin_note = clip(note.strip(), 1000)
            withdrawal.updated_at = utcnow()
        except LedgerError:
            logger.exception("withdrawal completion failed id=%s", withdrawal_id)
            return "inconsistent"
    logger.info("withdrawal status id=%s status=%s", withdrawal_id, new_status)
    return "ok"
