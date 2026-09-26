from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ADMIN_PAGE_SIZE,
    WITHDRAWAL_APPROVED,
    WITHDRAWAL_COMPLETED,
    WITHDRAWAL_PENDING,
    WITHDRAWAL_PROCESSING,
    WITHDRAWAL_REJECTED,
)
from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import confirm_kb, withdrawal_card_kb, withdrawal_list_kb
from app.keyboards.callbacks import AdminCB
from app.services.notify import send_user
from app.services.rewards import get_reward
from app.services.users import get_by_id
from app.services.withdrawals import get_withdrawal, list_by_status, set_status
from app.texts.admin import withdrawal_card
from app.texts.messages import withdrawal_status_text
from app.utils.ui import show_screen

router = Router(name="admin-withdrawals")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())

_ACTIONS = {
    "approve": WITHDRAWAL_APPROVED,
    "process": WITHDRAWAL_PROCESSING,
    "done": WITHDRAWAL_COMPLETED,
    "reject": WITHDRAWAL_REJECTED,
}


async def _show(query: CallbackQuery, session: AsyncSession, withdrawal_id: int) -> None:
    item = await get_withdrawal(session, withdrawal_id)
    if item is None:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    user = await get_by_id(session, item.user_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    reward_title = None
    reference = ""
    if item.reward_id is not None:
        reward = await get_reward(session, item.reward_id)
        if reward is not None:
            reward_title = reward.title
            reference = reward.gift_reference
    await show_screen(
        query,
        withdrawal_card(item, user, reward_title, reference),
        withdrawal_card_kb(item, user_id=user.id),
    )


@router.callback_query(AdminCB.filter((F.section == "wd") & (F.action == "list")))
async def wd_list(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    page = max(callback_data.page, 0)
    rows = await list_by_status(
        session,
        WITHDRAWAL_PENDING,
        offset=page * ADMIN_PAGE_SIZE,
        limit=ADMIN_PAGE_SIZE + 1,
    )
    has_next = len(rows) > ADMIN_PAGE_SIZE
    items = rows[:ADMIN_PAGE_SIZE]
    text = "<b>Выводы</b>\n\nНа рассмотрении нет заявок." if not items else "<b>Выводы</b>"
    await show_screen(query, text, withdrawal_list_kb(items, page, has_next))


@router.callback_query(AdminCB.filter((F.section == "wd") & (F.action == "view")))
async def wd_view(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    await _show(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "wd") & (F.action == "askdone")))
async def wd_ask_done(query: CallbackQuery, callback_data: AdminCB) -> None:
    await show_screen(
        query,
        "Подтвердите, что награда выдана вручную. До этого заявка не считается завершённой.",
        confirm_kb("wd", "done", callback_data.item_id, "view"),
    )


@router.callback_query(AdminCB.filter((F.section == "wd") & (F.action == "askrej")))
async def wd_ask_reject(query: CallbackQuery, callback_data: AdminCB) -> None:
    await show_screen(
        query,
        "Отклонить заявку и вернуть сумму на баланс?",
        confirm_kb("wd", "reject", callback_data.item_id, "view"),
    )


@router.callback_query(AdminCB.filter((F.section == "wd") & (F.action.in_(_ACTIONS.keys()))))
async def wd_status(
    query: CallbackQuery,
    callback_data: AdminCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    new_status = _ACTIONS[callback_data.action]
    code = await set_status(session, callback_data.item_id, new_status)
    if code != "ok":
        await query.answer("Нельзя сменить статус.", show_alert=True)
        return
    item = await get_withdrawal(session, callback_data.item_id)
    if item is not None:
        user = await get_by_id(session, item.user_id)
        if user is not None:
            await send_user(bot, user.telegram_id, withdrawal_status_text(item.id, item.status, item.amount))
    await _show(query, session, callback_data.item_id)
