"""Задания и однократное начисление награды."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    CHANNEL_TASK_TYPES,
    TASK_REFERRAL,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_TYPES,
    TIMED_TASK_SECONDS,
    TRANSACTION_TASK_REWARD,
)
from app.db.models import Task, User, UserTask
from app.db.session import unit_of_work
from app.services import referrals
from app.services.common import fresh
from app.services.ledger import credit
from app.utils.money import format_stars
from app.utils.text import h
from app.utils.time import as_utc, utcnow

logger = logging.getLogger(__name__)


async def list_active(session: AsyncSession) -> list[Task]:
    rows = await session.scalars(
        select(Task)
        .where(Task.active.is_(True), Task.archived.is_(False))
        .order_by(Task.sort_order.asc(), Task.id.asc())
    )
    return list(rows)


async def list_all(session: AsyncSession) -> list[Task]:
    rows = await session.scalars(select(Task).order_by(Task.archived.asc(), Task.sort_order.asc(), Task.id.asc()))
    return list(rows)


async def get_task(session: AsyncSession, task_id: int) -> Task | None:
    return await session.get(Task, task_id)


async def completed_task_ids(session: AsyncSession, user_id: int) -> set[int]:
    rows = await session.scalars(
        select(UserTask.task_id).where(
            UserTask.user_id == user_id,
            UserTask.status == TASK_STATUS_COMPLETED,
        )
    )
    return set(rows)


async def completion_count(session: AsyncSession, task_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(UserTask)
            .where(UserTask.task_id == task_id, UserTask.status == TASK_STATUS_COMPLETED)
        )
        or 0
    )


async def _occupied_slots(session: AsyncSession, task_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(UserTask)
            .where(
                UserTask.task_id == task_id,
                UserTask.status.in_((TASK_STATUS_COMPLETED, TASK_STATUS_PENDING)),
            )
        )
        or 0
    )


async def user_completed_any(session: AsyncSession, user_id: int) -> bool:
    found = await session.scalar(
        select(UserTask.id).where(
            UserTask.user_id == user_id,
            UserTask.status == TASK_STATUS_COMPLETED,
        )
    )
    return found is not None


async def create_task(
    session: AsyncSession,
    *,
    title: str,
    description: str,
    reward: int,
    task_type: str,
    target: str = "",
    channel_username: str | None = None,
    channel_id: str | None = None,
    max_completions: int = 0,
    sort_order: int = 0,
) -> Task | str:
    if task_type not in TASK_TYPES:
        return "bad_type"
    if reward < 0:
        return "bad_reward"
    if not title.strip():
        return "bad_title"
    task = Task(
        title=title.strip()[:150],
        description=description.strip(),
        reward=reward,
        task_type=task_type,
        target=target.strip()[:300],
        channel_username=channel_username,
        channel_id=channel_id,
        active=True,
        archived=False,
        sort_order=sort_order,
        max_completions=max_completions,
    )
    async with unit_of_work(session):
        session.add(task)
        await session.flush()
    logger.info("task created id=%s type=%s reward=%s", task.id, task.task_type, task.reward)
    return task


async def update_task_fields(session: AsyncSession, task_id: int, **fields: object) -> str:
    allowed = {
        "title",
        "description",
        "reward",
        "target",
        "channel_username",
        "channel_id",
        "active",
        "archived",
        "sort_order",
        "max_completions",
        "task_type",
    }
    unknown = set(fields) - allowed
    if unknown:
        return "bad_field"
    async with unit_of_work(session):
        task = await fresh(session, Task, task_id)
        if task is None:
            return "missing"
        for key, value in fields.items():
            setattr(task, key, value)
    logger.info("task updated id=%s fields=%s", task_id, ",".join(fields))
    return "ok"


async def delete_task(session: AsyncSession, task_id: int) -> str:
    try:
        async with unit_of_work(session):
            task = await fresh(session, Task, task_id)
            if task is None:
                return "missing"
            done = await completion_count(session, task_id)
            if done > 0:
                return "has_completions"
            await session.delete(task)
    except IntegrityError:
        logger.info("task delete blocked id=%s", task_id)
        return "has_completions"
    logger.info("task deleted id=%s", task_id)
    return "ok"


async def complete_task(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    membership_confirmed: bool = False,
) -> str:
    """Коды: ok, already, missing, inactive, limit, not_member, not_ready, bad_target."""
    try:
        async with unit_of_work(session):
            user = await fresh(session, User, user_id)
            task = await fresh(session, Task, task_id)
            if user is None or task is None:
                return "missing"
            if not task.active or task.archived:
                return "inactive"
            existing = await session.scalar(
                select(UserTask.id).where(UserTask.user_id == user.id, UserTask.task_id == task.id)
            )
            if existing is not None:
                return "already"
            if task.max_completions > 0:
                done = await _occupied_slots(session, task.id)
                if done >= task.max_completions:
                    return "limit"
            if task.task_type in CHANNEL_TASK_TYPES:
                if not task.channel_username and not task.channel_id:
                    return "bad_target"
                if not membership_confirmed:
                    return "not_member"
            elif task.task_type == TASK_REFERRAL:
                needed = _referral_target(task.target)
                if needed is None:
                    return "bad_target"
                qualified = await referrals.count_qualified(session, user.id)
                if qualified < needed:
                    return "not_ready"
            session.add(
                UserTask(
                    user_id=user.id,
                    task_id=task.id,
                    status=TASK_STATUS_COMPLETED,
                    completed_at=utcnow(),
                )
            )
            await session.flush()
            if task.reward > 0:
                await credit(
                    session,
                    user,
                    task.reward,
                    TRANSACTION_TASK_REWARD,
                    f"Задание: {task.title}"[:300],
                )
    except IntegrityError:
        logger.info("task completion duplicate user_id=%s task_id=%s", user_id, task_id)
        return "already"
    logger.info("task completed user_id=%s task_id=%s", user_id, task_id)
    return "ok"


async def task_progress(session: AsyncSession, user_id: int, task_id: int) -> str | None:
    row = await session.scalar(
        select(UserTask).where(UserTask.user_id == user_id, UserTask.task_id == task_id)
    )
    if row is None:
        return None
    return row.status


async def start_timed(session: AsyncSession, user_id: int, task_id: int) -> str:
    """Коды: waiting, already, missing, inactive, limit, bad_type."""
    delay = None
    try:
        async with unit_of_work(session):
            user = await fresh(session, User, user_id)
            task = await fresh(session, Task, task_id)
            if user is None or task is None:
                return "missing"
            if task.task_type not in TIMED_TASK_SECONDS:
                return "bad_type"
            if not task.active or task.archived:
                return "inactive"
            existing = await session.scalar(
                select(UserTask).where(UserTask.user_id == user.id, UserTask.task_id == task.id)
            )
            if existing is not None:
                return "already" if existing.status == TASK_STATUS_COMPLETED else "waiting"
            if task.max_completions > 0:
                done = await _occupied_slots(session, task.id)
                if done >= task.max_completions:
                    return "limit"
            delay = TIMED_TASK_SECONDS[task.task_type]
            session.add(
                UserTask(
                    user_id=user.id,
                    task_id=task.id,
                    status=TASK_STATUS_PENDING,
                    reward_at=utcnow() + timedelta(seconds=delay),
                )
            )
            await session.flush()
    except IntegrityError:
        logger.info("timed task duplicate user_id=%s task_id=%s", user_id, task_id)
        return "waiting"
    logger.info("timed task started user_id=%s task_id=%s delay=%s", user_id, task_id, delay)
    return "waiting"


async def settle_due_tasks(session: AsyncSession) -> list[tuple[int, str]]:
    pending = list(
        await session.scalars(select(UserTask).where(UserTask.status == TASK_STATUS_PENDING))
    )
    now = utcnow()
    due_ids = [
        row.id
        for row in pending
        if row.reward_at is None or as_utc(row.reward_at) <= now
    ]
    notices: list[tuple[int, str]] = []
    for row_id in due_ids:
        notice = await _settle_one(session, row_id)
        if notice is not None:
            notices.append(notice)
    return notices


async def _settle_one(session: AsyncSession, row_id: int) -> tuple[int, str] | None:
    async with unit_of_work(session):
        row = await fresh(session, UserTask, row_id)
        if row is None or row.status != TASK_STATUS_PENDING:
            return None
        if row.reward_at is not None and as_utc(row.reward_at) > utcnow():
            return None
        user = await fresh(session, User, row.user_id)
        task = await fresh(session, Task, row.task_id)
        if user is None or task is None or not task.active or task.archived:
            row.status = "cancelled"
            return None
        if task.max_completions > 0:
            done = await completion_count(session, task.id)
            if done >= task.max_completions:
                row.status = "cancelled"
                return None
        row.status = TASK_STATUS_COMPLETED
        row.completed_at = utcnow()
        if task.reward > 0:
            await credit(
                session,
                user,
                task.reward,
                TRANSACTION_TASK_REWARD,
                f"Задание: {task.title}"[:300],
            )
        text = (
            f"Начислено {format_stars(task.reward)}.\n{h(task.title)}"
            if task.reward
            else f"Задание выполнено.\n{h(task.title)}"
        )
        logger.info("timed task paid user_id=%s task_id=%s", user.id, task.id)
        return user.telegram_id, text


def _referral_target(target: str) -> int | None:
    raw = (target or "").strip()
    if not raw:
        return 1
    if not raw.isdigit():
        return None
    value = int(raw)
    if value <= 0:
        return None
    return value
