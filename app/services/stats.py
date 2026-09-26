"""Агрегаты из базы. Нулевые значения не подменяются."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import (
    EARNING_TYPES,
    META_LAUNCHED_AT,
    SELL_COMPLETED,
    WITHDRAWAL_COMPLETED,
    WITHDRAWAL_PENDING,
)
from app.db.models import SellRequest, Transaction, User, UserTask, Withdrawal
from app.db.session import get_meta
from app.utils.time import as_utc, today_in_tz, utcnow


@dataclass(slots=True)
class ServiceStats:
    launched_at: datetime | None
    users: int
    active_today: int
    active_7d: int
    tasks_completed: int
    total_rewards: int
    withdrawals_completed: int
    withdrawals_pending: int
    withdrawn_stars: int
    completed_deals: int
    deal_volume: dict[str, int] = field(default_factory=dict)


def _parse_launch(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return as_utc(datetime.fromisoformat(raw))
    except ValueError:
        return None


async def collect(session: AsyncSession) -> ServiceStats:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    start_today = datetime.combine(today_in_tz(), time.min, tzinfo=tz).astimezone(timezone.utc)
    week_ago = utcnow() - timedelta(days=7)

    users = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    active_today = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.last_active_at >= start_today)
        )
        or 0
    )
    active_7d = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.last_active_at >= week_ago)
        )
        or 0
    )
    tasks_completed = int(await session.scalar(select(func.count()).select_from(UserTask)) or 0)
    total_rewards = int(
        await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type.in_(EARNING_TYPES)
            )
        )
        or 0
    )
    withdrawals_completed = int(
        await session.scalar(
            select(func.count())
            .select_from(Withdrawal)
            .where(Withdrawal.status == WITHDRAWAL_COMPLETED)
        )
        or 0
    )
    withdrawals_pending = int(
        await session.scalar(
            select(func.count()).select_from(Withdrawal).where(Withdrawal.status == WITHDRAWAL_PENDING)
        )
        or 0
    )
    withdrawn_stars = int(
        await session.scalar(
            select(func.coalesce(func.sum(Withdrawal.amount), 0)).where(
                Withdrawal.status == WITHDRAWAL_COMPLETED
            )
        )
        or 0
    )
    completed_deals = int(
        await session.scalar(
            select(func.count()).select_from(SellRequest).where(SellRequest.status == SELL_COMPLETED)
        )
        or 0
    )
    volume_rows = await session.execute(
        select(SellRequest.currency, func.coalesce(func.sum(SellRequest.admin_price), 0))
        .where(SellRequest.status == SELL_COMPLETED, SellRequest.admin_price.is_not(None))
        .group_by(SellRequest.currency)
    )
    deal_volume = {currency: int(total) for currency, total in volume_rows.all() if currency}

    return ServiceStats(
        launched_at=_parse_launch(await get_meta(session, META_LAUNCHED_AT)),
        users=users,
        active_today=active_today,
        active_7d=active_7d,
        tasks_completed=tasks_completed,
        total_rewards=total_rewards,
        withdrawals_completed=withdrawals_completed,
        withdrawals_pending=withdrawals_pending,
        withdrawn_stars=withdrawn_stars,
        completed_deals=completed_deals,
        deal_volume=deal_volume,
    )
