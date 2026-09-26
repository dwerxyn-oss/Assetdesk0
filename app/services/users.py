"""Пользователи и профиль продавца."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import SELLER_LEVELS, SELLER_NEW
from app.db.models import User
from app.db.session import unit_of_work
from app.services.common import fresh
from app.services.referrals import reward_referrer_if_needed
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def available(user: User) -> int:
    return user.balance - user.reserved_balance


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = username.strip().lstrip("@").lower()
    if not normalized:
        return None
    return await session.scalar(
        select(User)
        .where(func.lower(User.username) == normalized)
        .order_by(User.id.desc())
    )


async def touch(session: AsyncSession, user: User, username: str | None, first_name: str) -> None:
    user.username = username[:64] if username else None
    user.first_name = (first_name or "")[:128]
    user.last_active_at = utcnow()
    user.updated_at = utcnow()
    await session.commit()


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str,
    referrer_telegram_id: int | None = None,
) -> tuple[User, bool]:
    """Возвращает пользователя и флаг «только что создан»."""
    existing = await get_by_telegram_id(session, telegram_id)
    if existing is not None:
        return existing, False

    settings = get_settings()
    referrer: User | None = None
    if (
        referrer_telegram_id is not None
        and referrer_telegram_id != telegram_id
        and referrer_telegram_id > 0
    ):
        referrer = await get_by_telegram_id(session, referrer_telegram_id)
        if referrer is not None and referrer.blocked:
            referrer = None

    now = utcnow()
    referrer_id = referrer.id if referrer is not None else None
    user = User(
        telegram_id=telegram_id,
        username=username[:64] if username else None,
        first_name=(first_name or "")[:128],
        registration_date=now,
        created_at=now,
        updated_at=now,
        last_active_at=now,
        balance=0,
        reserved_balance=0,
        referred_by=referrer_id,
        referral_count=0,
        referral_reward_paid=False,
        total_earned=0,
        total_withdrawn=0,
        successful_deals=0,
        failed_deals=0,
        total_volume=0,
        seller_limit=settings.new_seller_limit_usd,
        seller_level=SELLER_NEW,
        manual_verified=False,
        blocked=False,
    )

    try:
        async with unit_of_work(session):
            session.add(user)
            await session.flush()
            if referrer_id is not None:
                locked_referrer = await fresh(session, User, referrer_id)
                if locked_referrer is not None and not locked_referrer.blocked:
                    locked_referrer.referral_count += 1
                    user.referred_by = locked_referrer.id
                    await reward_referrer_if_needed(session, user)
                else:
                    user.referred_by = None
    except IntegrityError:
        await session.rollback()
        existing = await get_by_telegram_id(session, telegram_id)
        if existing is None:
            raise
        return existing, False

    logger.info("user created telegram_id=%s referred_by=%s", telegram_id, user.referred_by)
    return user, True


async def set_blocked(session: AsyncSession, user_id: int, blocked: bool) -> str:
    settings = get_settings()
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing"
        if blocked and user.telegram_id == settings.admin_id:
            return "admin"
        user.blocked = blocked
        user.updated_at = utcnow()
    logger.info("user block user_id=%s blocked=%s", user_id, blocked)
    return "ok"


async def set_seller_level(session: AsyncSession, user_id: int, level: str) -> str:
    if level not in SELLER_LEVELS:
        return "bad_level"
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing"
        user.seller_level = level
        user.updated_at = utcnow()
    logger.info("seller level user_id=%s level=%s", user_id, level)
    return "ok"


async def set_seller_limit(session: AsyncSession, user_id: int, limit_usd: int) -> str:
    if limit_usd <= 0:
        return "bad_limit"
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing"
        user.seller_limit = limit_usd
        user.updated_at = utcnow()
    logger.info("seller limit user_id=%s limit_usd=%s", user_id, limit_usd)
    return "ok"


async def set_manual_verified(session: AsyncSession, user_id: int, verified: bool) -> str:
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing"
        user.manual_verified = verified
        user.updated_at = utcnow()
    logger.info("seller verified user_id=%s verified=%s", user_id, verified)
    return "ok"


async def seller_level_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(User.seller_level, func.count()).group_by(User.seller_level)
    )
    return {str(level): int(count) for level, count in rows.all()}


async def count_users(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(User)) or 0)


async def count_active_since(session: AsyncSession, since: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.last_active_at >= since)
        )
        or 0
    )
