from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import CHANNEL_TASK_TYPES, TASK_REFERRAL, TASK_STATUS_COMPLETED, TIMED_TASK_SECONDS
from app.db.models import User
from app.keyboards.callbacks import MenuCB, TaskCB
from app.keyboards.menu import daily_menu
from app.keyboards.tasks import task_card, task_list
from app.middlewares.context import ensure_user
from app.services import tasks as task_service
from app.services.daily import claim
from app.services.membership import check_membership
from app.services.referrals import count_qualified
from app.texts.messages import daily_result, daily_screen, earn_text, task_text
from app.utils.money import format_stars
from app.utils.time import today_in_tz
from app.utils.ui import show_screen

router = Router(name="earn")

_CHECK_ALERTS = {
    "not_member": "Сначала выполните условие задания.",
    "no_rights": "Сейчас не получается проверить подписку. Попробуйте позже.",
    "bad_channel": "Канал для проверки не настроен. Напишите в поддержку.",
    "already": "Награда за это задание уже начислена.",
    "limit": "Лимит выполнений исчерпан.",
    "inactive": "Задание больше недоступно.",
    "not_ready": "Условие ещё не выполнено.",
    "missing": "Задание не найдено.",
    "bad_target": "Задание настроено неполностью.",
}


async def _show_tasks(event, session: AsyncSession) -> None:
    tasks = await task_service.list_active(session)
    await show_screen(event, earn_text(bool(tasks)), task_list(tasks), photo="earn")


@router.callback_query(MenuCB.filter(F.action == "earn"))
async def open_earn(query: CallbackQuery, session: AsyncSession) -> None:
    await _show_tasks(query, session)


async def _daily(
    event,
    session: AsyncSession,
    user: User,
    *,
    just_claimed: str | None = None,
    alert: str | None = None,
) -> None:
    await session.refresh(user)
    amount = get_settings().daily_bonus
    claimed = user.last_daily_bonus == today_in_tz()
    text = daily_screen(amount, claimed=claimed)
    if just_claimed == "ok":
        text = f"{daily_result('ok', amount)}\n\n{text}"
    can_claim = amount > 0 and not claimed
    await show_screen(event, text, daily_menu(can_claim=can_claim), alert=alert)


@router.callback_query(MenuCB.filter(F.action == "daily"))
async def daily_bonus(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    await _daily(query, session, user)


@router.callback_query(MenuCB.filter(F.action == "claim_daily"))
async def claim_daily(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    code = await claim(session, user.id)
    if code not in {"ok", "already", "disabled"}:
        await query.answer(daily_result(code, get_settings().daily_bonus), show_alert=True)
        return
    alert = "Бонус за сегодня уже получен." if code == "already" else None
    await _daily(query, session, user, just_claimed=code if code == "ok" else None, alert=alert)


@router.callback_query(TaskCB.filter(F.action == "open"))
async def open_task(
    query: CallbackQuery,
    callback_data: TaskCB,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    task = await task_service.get_task(session, callback_data.task_id)
    if task is None or not task.active or task.archived:
        await query.answer("Задание недоступно.", show_alert=True)
        return
    done = callback_data.task_id in await task_service.completed_task_ids(session, user.id)
    progress = await task_service.task_progress(session, user.id, callback_data.task_id)
    pending = progress is not None and progress != TASK_STATUS_COMPLETED
    qualified = None
    if task.task_type == TASK_REFERRAL:
        qualified = await count_qualified(session, user.id)
    await show_screen(
        query,
        task_text(task, completed=done, qualified=qualified, pending=pending),
        task_card(task, completed=done, pending=pending),
    )


async def _start_timed(query: CallbackQuery, session: AsyncSession, user: User, task) -> None:
    code = await task_service.start_timed(session, user.id, task.id)
    if code == "already":
        await query.answer("Награда за это задание уже начислена.", show_alert=True)
        return
    if code != "waiting":
        await query.answer(_CHECK_ALERTS.get(code, "Не получилось начать задание."), show_alert=True)
        return
    await show_screen(
        query,
        "✅ Принято.\n\n"
        + task_text(task, completed=False, pending=True),
        task_card(task, completed=False, pending=True),
    )


@router.callback_query(TaskCB.filter(F.action == "start"))
async def start_task(
    query: CallbackQuery,
    callback_data: TaskCB,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    task = await task_service.get_task(session, callback_data.task_id)
    if task is None or task.task_type not in TIMED_TASK_SECONDS:
        await query.answer("Задание недоступно.", show_alert=True)
        return
    await _start_timed(query, session, user, task)


@router.callback_query(TaskCB.filter(F.action == "check"))
async def check_task(
    query: CallbackQuery,
    callback_data: TaskCB,
    session: AsyncSession,
    db_user: User | None,
    bot: Bot,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    task = await task_service.get_task(session, callback_data.task_id)
    if task is None:
        await query.answer("Задание не найдено.", show_alert=True)
        return
    if task.task_type in TIMED_TASK_SECONDS:
        await _start_timed(query, session, user, task)
        return
    confirmed = False
    if task.task_type in CHANNEL_TASK_TYPES:
        membership = await check_membership(
            bot,
            user.telegram_id,
            channel_username=task.channel_username,
            channel_id=task.channel_id,
        )
        if membership != "member":
            await query.answer(_CHECK_ALERTS.get(membership, "Условие не выполнено."), show_alert=True)
            return
        confirmed = True
    code = await task_service.complete_task(
        session,
        user.id,
        task.id,
        membership_confirmed=confirmed,
    )
    if code != "ok":
        await query.answer(_CHECK_ALERTS.get(code, "Не получилось засчитать задание."), show_alert=True)
        return
    qualified = None
    if task.task_type == TASK_REFERRAL:
        qualified = await count_qualified(session, user.id)
    prefix = (
        f"Начислено {format_stars(task.reward)}.\n\n"
        if task.reward
        else "Задание выполнено.\n\n"
    )
    await show_screen(
        query,
        prefix + task_text(task, completed=True, qualified=qualified),
        task_card(task, completed=True),
    )
