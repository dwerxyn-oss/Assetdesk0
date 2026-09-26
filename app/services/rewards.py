"""Каталог наград. Это не отправка Telegram Gift."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reward, Withdrawal
from app.db.session import unit_of_work
from app.services.common import fresh

logger = logging.getLogger(__name__)


async def list_active(session: AsyncSession) -> list[Reward]:
    rows = await session.scalars(
        select(Reward)
        .where(Reward.active.is_(True))
        .order_by(Reward.sort_order.asc(), Reward.id.asc())
    )
    return list(rows)


async def list_all(session: AsyncSession) -> list[Reward]:
    rows = await session.scalars(select(Reward).order_by(Reward.sort_order.asc(), Reward.id.asc()))
    return list(rows)


async def get_reward(session: AsyncSession, reward_id: int) -> Reward | None:
    return await session.get(Reward, reward_id)


async def create_reward(
    session: AsyncSession,
    *,
    title: str,
    description: str,
    cost_stars: int,
    gift_reference: str,
) -> Reward | str:
    if not title.strip() or cost_stars <= 0:
        return "bad"
    reward = Reward(
        title=title.strip()[:150],
        description=description.strip(),
        cost_stars=cost_stars,
        gift_reference=gift_reference.strip()[:200],
        active=True,
    )
    async with unit_of_work(session):
        session.add(reward)
        await session.flush()
    logger.info("reward created id=%s cost=%s", reward.id, reward.cost_stars)
    return reward


async def set_active(session: AsyncSession, reward_id: int, active: bool) -> str:
    async with unit_of_work(session):
        reward = await fresh(session, Reward, reward_id)
        if reward is None:
            return "missing"
        reward.active = active
    logger.info("reward active id=%s active=%s", reward_id, active)
    return "ok"


async def set_cost(session: AsyncSession, reward_id: int, cost_stars: int) -> str:
    if cost_stars <= 0:
        return "bad"
    async with unit_of_work(session):
        reward = await fresh(session, Reward, reward_id)
        if reward is None:
            return "missing"
        reward.cost_stars = cost_stars
    logger.info("reward cost id=%s cost=%s", reward_id, cost_stars)
    return "ok"


async def delete_reward(session: AsyncSession, reward_id: int) -> str:
    used = await session.scalar(
        select(func.count()).select_from(Withdrawal).where(Withdrawal.reward_id == reward_id)
    )
    if used:
        return "used"
    async with unit_of_work(session):
        reward = await fresh(session, Reward, reward_id)
        if reward is None:
            return "missing"
        await session.delete(reward)
    logger.info("reward deleted id=%s", reward_id)
    return "ok"
