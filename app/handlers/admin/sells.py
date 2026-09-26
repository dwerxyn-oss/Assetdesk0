from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ADMIN_PAGE_SIZE,
    SELL_ACTIVE,
    SELL_CANCELLED,
    SELL_COMPLETED,
    SELL_PAID,
    SELL_PENDING,
    SELL_RECEIVED,
    SELL_REJECTED,
    SELL_REVIEWING,
)
from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import confirm_kb, offer_confirm_kb, sell_card_kb, sell_list_kb
from app.keyboards.callbacks import AdminCB
from app.keyboards.common import back, kb
from app.keyboards.sell import offer_decision
from app.middlewares.context import PLAIN_TEXT
from app.services.notify import send_user
from app.services.sells import (
    get_request,
    list_by_statuses,
    mark_failed,
    send_offer,
    set_note,
    set_status,
)
from app.services.users import get_by_id
from app.states.flows import AdminSellStates
from app.texts.admin import offer_preview, sell_card
from app.texts.messages import sell_offer, sell_user_notice
from app.utils.parsing import parse_price
from app.utils.ui import show_screen

router = Router(name="admin-sells")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())

_ACTIONS = {
    "review": SELL_REVIEWING,
    "recv": SELL_RECEIVED,
    "paid": SELL_PAID,
    "done": SELL_COMPLETED,
    "reject": SELL_REJECTED,
    "cancel": SELL_CANCELLED,
}


async def _show(query: CallbackQuery, session: AsyncSession, request_id: int) -> None:
    request = await get_request(session, request_id)
    if request is None:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    user = await get_by_id(session, request.user_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    await show_screen(query, sell_card(request, user), sell_card_kb(request, user_id=user.id))


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "list")))
async def sell_list(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    mode = 1 if callback_data.item_id == 1 else 0
    statuses = SELL_ACTIVE if mode == 1 else {SELL_PENDING}
    page = max(callback_data.page, 0)
    rows = await list_by_statuses(
        session,
        statuses,
        offset=page * ADMIN_PAGE_SIZE,
        limit=ADMIN_PAGE_SIZE + 1,
    )
    has_next = len(rows) > ADMIN_PAGE_SIZE
    items = rows[:ADMIN_PAGE_SIZE]
    title = "В работе" if mode == 1 else "Новые заявки"
    text = f"<b>{title}</b>" if items else f"<b>{title}</b>\n\nЗаявок нет."
    await show_screen(query, text, sell_list_kb(items, mode=mode, page=page, has_next=has_next))


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "view")))
async def sell_view(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await _show(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "price")))
async def ask_price(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    await state.set_state(AdminSellStates.price)
    await state.set_data({"sell_id": callback_data.item_id})
    await show_screen(
        query,
        "Введите цену: число и валюта, например 1500 RUB, 25 USD или 400 STARS.",
        kb([back(AdminCB(section="sell", action="view", item_id=callback_data.item_id))]),
    )


@router.message(AdminSellStates.price, PLAIN_TEXT)
async def take_price(message: Message, session: AsyncSession, state: FSMContext) -> None:
    parsed = parse_price(message.text or "")
    if parsed is None:
        await message.answer("Формат: 1500 RUB, 25 USD или 400 STARS.")
        return
    price, currency = parsed
    data = await state.get_data()
    request = await get_request(session, int(data["sell_id"]))
    if request is None:
        await state.clear()
        await message.answer("Заявка не найдена.")
        return
    user = await get_by_id(session, request.user_id)
    if user is None:
        await state.clear()
        await message.answer("Пользователь не найден.")
        return
    await state.update_data(price=price, currency=currency)
    await state.set_state(AdminSellStates.confirm)
    await message.answer(
        offer_preview(request, user, price, currency),
        reply_markup=offer_confirm_kb(request.id),
    )


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "send")))
async def confirm_offer(
    query: CallbackQuery,
    callback_data: AdminCB,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
) -> None:
    if await state.get_state() != AdminSellStates.confirm.state:
        await query.answer("Сначала укажите цену.", show_alert=True)
        return
    data = await state.get_data()
    if int(data.get("sell_id", 0)) != callback_data.item_id:
        await query.answer("Это другое предложение.", show_alert=True)
        return
    code = await send_offer(session, callback_data.item_id, int(data["price"]), str(data["currency"]))
    await state.clear()
    if code != "ok":
        await query.answer("Нельзя отправить предложение.", show_alert=True)
        return
    request = await get_request(session, callback_data.item_id)
    if request is not None:
        user = await get_by_id(session, request.user_id)
        if user is not None:
            await send_user(bot, user.telegram_id, sell_offer(request), offer_decision(request.id))
    await _show(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "note")))
async def ask_note(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    await state.set_state(AdminSellStates.note)
    await state.set_data({"sell_id": callback_data.item_id})
    await show_screen(
        query,
        "Внутренняя заметка. Пользователь её не увидит.",
        kb([back(AdminCB(section="sell", action="view", item_id=callback_data.item_id))]),
    )


@router.message(AdminSellStates.note, PLAIN_TEXT)
async def take_note(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    request_id = int(data["sell_id"])
    code = await set_note(session, request_id, message.text or "")
    await state.clear()
    if code != "ok":
        await message.answer("Заявка не найдена.")
        return
    request = await get_request(session, request_id)
    user = await get_by_id(session, request.user_id) if request else None
    if request is None or user is None:
        return
    await message.answer(sell_card(request, user), reply_markup=sell_card_kb(request, user_id=user.id))


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "askdone")))
async def ask_done(query: CallbackQuery, callback_data: AdminCB) -> None:
    await show_screen(
        query,
        "Подтвердите, что NFT получен и оплата проведена вручную.",
        confirm_kb("sell", "done", callback_data.item_id, "view"),
    )


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action == "fail")))
async def fail_deal(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession, bot: Bot) -> None:
    code = await mark_failed(session, callback_data.item_id)
    if code != "ok":
        await query.answer("Эту заявку нельзя отметить неуспешной.", show_alert=True)
        return
    await _notify(bot, session, callback_data.item_id)
    await _show(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "sell") & (F.action.in_(_ACTIONS.keys()))))
async def change_status(
    query: CallbackQuery,
    callback_data: AdminCB,
    session: AsyncSession,
    bot: Bot,
) -> None:
    code = await set_status(session, callback_data.item_id, _ACTIONS[callback_data.action])
    if code != "ok":
        await query.answer("Нельзя сменить статус.", show_alert=True)
        return
    await _notify(bot, session, callback_data.item_id)
    await _show(query, session, callback_data.item_id)


async def _notify(bot: Bot, session: AsyncSession, request_id: int) -> None:
    request = await get_request(session, request_id)
    if request is None:
        return
    text = sell_user_notice(request)
    if text is None:
        return
    user = await get_by_id(session, request.user_id)
    if user is not None:
        markup = offer_decision(request.id) if request.status == "offer_sent" else None
        await send_user(bot, user.telegram_id, text, markup)
