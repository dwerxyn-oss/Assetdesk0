from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import SELLER_LEVELS
from app.db.models import User
from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import seller_levels_kb, user_card_kb
from app.keyboards.callbacks import AdminCB
from app.keyboards.common import back, btn, kb
from app.middlewares.context import PLAIN_TEXT
from app.services.history import page_for_user
from app.services.ledger import adjust_balance
from app.services.users import (
    get_by_id,
    get_by_telegram_id,
    get_by_username,
    set_blocked,
    set_manual_verified,
    set_seller_level,
    set_seller_limit,
)
from app.states.flows import AdminUserStates
from app.texts.admin import user_card
from app.texts.messages import history_text
from app.utils.parsing import parse_int, parse_positive_int
from app.utils.ui import show_screen

router = Router(name="admin-users")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())


async def show_user(event: Message | CallbackQuery, user: User) -> None:
    await show_screen(
        event,
        user_card(user),
        user_card_kb(user.id, blocked=user.blocked, verified=user.manual_verified),
    )


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "search")))
async def ask_search(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminUserStates.search)
    await show_screen(
        query,
        "Введите Telegram ID или @username.",
        kb([back(AdminCB(section="menu", action="open"))]),
    )


@router.message(AdminUserStates.search, PLAIN_TEXT)
async def find_user(message: Message, session: AsyncSession, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    user = None
    if raw.isdigit():
        user = await get_by_telegram_id(session, int(raw))
    elif raw:
        user = await get_by_username(session, raw)
    if user is None:
        await message.answer("Пользователь не найден.")
        return
    await state.clear()
    await show_user(message, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "view")))
async def view_user(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await get_by_id(session, callback_data.item_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    await show_user(query, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action.in_({"block", "unblock"}))))
async def toggle_block(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    blocked = callback_data.action == "block"
    code = await set_blocked(session, callback_data.item_id, blocked)
    if code == "admin":
        await query.answer("Нельзя заблокировать администратора.", show_alert=True)
        return
    if code != "ok":
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    user = await get_by_id(session, callback_data.item_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    await session.refresh(user)
    await show_user(query, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "bal")))
async def ask_balance(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.balance_amount)
    await state.set_data({"user_id": callback_data.item_id})
    await show_screen(
        query,
        "Введите изменение баланса целым числом ⭐. Можно отрицательное.",
        kb([back(AdminCB(section="users", action="view", item_id=callback_data.item_id))]),
    )


@router.message(AdminUserStates.balance_amount, PLAIN_TEXT)
async def take_balance_amount(message: Message, state: FSMContext) -> None:
    amount = parse_int(message.text or "")
    if amount is None or amount == 0:
        await message.answer("Нужно целое число, кроме нуля.")
        return
    await state.update_data(amount=amount)
    await state.set_state(AdminUserStates.balance_comment)
    await message.answer("Комментарий к операции. Он сохранится в истории.")


@router.message(AdminUserStates.balance_comment, PLAIN_TEXT)
async def take_balance_comment(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Комментарий обязателен.")
        return
    user_id = int(data["user_id"])
    code = await adjust_balance(session, user_id, int(data["amount"]), comment)
    await state.clear()
    if code == "insufficient":
        await message.answer("Нельзя опустить баланс ниже суммы, которая уже в заявках на вывод.")
        return
    if code != "ok":
        await message.answer("Не получилось изменить баланс.")
        return
    user = await get_by_id(session, user_id)
    if user is None:
        return
    await session.refresh(user)
    await show_user(message, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "level")))
async def ask_level(query: CallbackQuery, callback_data: AdminCB) -> None:
    await show_screen(
        query,
        "Уровень меняется отдельно от лимита.",
        seller_levels_kb(callback_data.item_id),
    )


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action.startswith("lv"))))
async def set_level(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    if callback_data.action == "lvlim":
        user = await get_by_id(session, callback_data.item_id)
        if user is None:
            await query.answer("Пользователь не найден.", show_alert=True)
            return
        limit = get_settings().seller_limit_for_level(user.seller_level)
        code = await set_seller_limit(session, user.id, limit)
        if code != "ok":
            await query.answer("Не получилось изменить лимит.", show_alert=True)
            return
        await session.refresh(user)
        await show_user(query, user)
        return
    level = callback_data.action.removeprefix("lv_")
    if level not in SELLER_LEVELS:
        await query.answer("Некорректное действие", show_alert=True)
        return
    code = await set_seller_level(session, callback_data.item_id, level)
    if code != "ok":
        await query.answer("Не получилось изменить уровень.", show_alert=True)
        return
    user = await get_by_id(session, callback_data.item_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    await session.refresh(user)
    await show_user(query, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "limit")))
async def ask_limit(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    await state.set_state(AdminUserStates.seller_limit)
    await state.set_data({"user_id": callback_data.item_id})
    await show_screen(
        query,
        "Новый лимит продавца в целых долларах.",
        kb([back(AdminCB(section="users", action="view", item_id=callback_data.item_id))]),
    )


@router.message(AdminUserStates.seller_limit, PLAIN_TEXT)
async def take_limit(message: Message, session: AsyncSession, state: FSMContext) -> None:
    limit = parse_positive_int(message.text or "")
    if limit is None or limit > 1_000_000:
        await message.answer("Нужно целое число больше нуля.")
        return
    data = await state.get_data()
    user_id = int(data["user_id"])
    code = await set_seller_limit(session, user_id, limit)
    await state.clear()
    if code != "ok":
        await message.answer("Не получилось изменить лимит.")
        return
    user = await get_by_id(session, user_id)
    if user is None:
        return
    await session.refresh(user)
    await show_user(message, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "verify")))
async def toggle_verify(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    user = await get_by_id(session, callback_data.item_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    code = await set_manual_verified(session, user.id, not user.manual_verified)
    if code != "ok":
        await query.answer("Не получилось обновить проверку.", show_alert=True)
        return
    await session.refresh(user)
    await show_user(query, user)


@router.callback_query(AdminCB.filter((F.section == "users") & (F.action == "hist")))
async def user_history(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    user = await get_by_id(session, callback_data.item_id)
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    page = max(callback_data.page, 0)
    rows, pages = await page_for_user(session, user.id, page)
    safe = min(page, pages - 1)
    nav: list[InlineKeyboardButton] = []
    if safe > 0:
        nav.append(btn("◀️", AdminCB(section="users", action="hist", item_id=user.id, page=safe - 1)))
    if safe + 1 < pages:
        nav.append(btn("▶️", AdminCB(section="users", action="hist", item_id=user.id, page=safe + 1)))
    await show_screen(
        query,
        history_text(rows, safe, pages),
        kb(nav, [back(AdminCB(section="users", action="view", item_id=user.id))]),
    )
