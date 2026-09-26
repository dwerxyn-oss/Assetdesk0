from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    MAX_MONEY,
    PAYOUT_CRYPTO,
    PAYOUT_LABELS,
    PAYOUT_RUB,
    PAYOUT_STARS,
    WITHDRAWAL_PENDING,
    WITHDRAWAL_STATUS_LABELS,
)
from app.db.models import User
from app.keyboards.admin import open_record_kb
from app.keyboards.callbacks import MenuCB, WithdrawCB
from app.keyboards.withdraw import my_withdrawals, payout_methods, withdraw_back, withdraw_menu
from app.middlewares.context import PLAIN_TEXT, ensure_user
from app.services import withdrawals as withdrawal_service
from app.services.notify import send_admin
from app.services.rewards import get_reward, list_active
from app.states.flows import WithdrawStates
from app.texts.admin import new_withdrawal
from app.texts.messages import (
    my_withdrawals_text,
    withdraw_payout_text,
    withdraw_text,
    withdrawal_created,
)
from app.utils.money import format_stars
from app.utils.parsing import parse_positive_int
from app.utils.ui import show_screen

router = Router(name="withdraw")


async def _screen(event, session: AsyncSession, user: User) -> None:
    await session.refresh(user)
    rewards = await list_active(session)
    requests = await withdrawal_service.list_for_user(session, user.id)
    available = user.balance - user.reserved_balance
    minimum = withdrawal_service.minimum_for(user)
    await show_screen(
        event,
        withdraw_text(user, has_rewards=bool(rewards)),
        withdraw_menu(rewards, can_request=available >= minimum, requests=requests),
    )


@router.callback_query(MenuCB.filter(F.action == "withdraw"))
async def open_withdraw(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    await state.clear()
    user = await ensure_user(session, query.from_user, db_user)
    await _screen(query, session, user)


@router.callback_query(WithdrawCB.filter(F.action == "reward"))
async def choose_reward(
    query: CallbackQuery,
    callback_data: WithdrawCB,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    await state.clear()
    await ensure_user(session, query.from_user, db_user)
    reward = await get_reward(session, callback_data.item_id)
    if reward is None or not reward.active:
        await query.answer("Награда недоступна.", show_alert=True)
        return
    await state.set_state(WithdrawStates.payout)
    await state.set_data(
        {"amount": reward.cost_stars, "reward_id": reward.id, "reward_title": reward.title}
    )
    await show_screen(query, withdraw_payout_text(reward.cost_stars), payout_methods())


@router.callback_query(WithdrawCB.filter(F.action == "custom"))
async def ask_amount(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WithdrawStates.amount)
    await show_screen(
        query,
        "Введите сумму вывода целым числом ⭐.",
        withdraw_back(),
    )


@router.message(WithdrawStates.amount, PLAIN_TEXT)
async def take_amount(
    message: Message,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if message.from_user is None or message.text is None:
        return
    amount = parse_positive_int(message.text)
    if amount is None or amount > MAX_MONEY:
        await message.answer("Нужно целое число больше нуля.")
        return
    user = await ensure_user(session, message.from_user, db_user)
    available = user.balance - user.reserved_balance
    minimum = withdrawal_service.minimum_for(user)
    if amount < minimum:
        await message.answer(f"Минимум сейчас — {format_stars(minimum)}.")
        return
    if amount > available:
        await message.answer("Недостаточно доступного баланса. Сумма в других заявках уже зарезервирована.")
        return
    await state.set_state(WithdrawStates.payout)
    await state.set_data({"amount": amount, "reward_id": None, "reward_title": None})
    await message.answer(withdraw_payout_text(amount), reply_markup=payout_methods())


_PAYOUTS = {
    "pay_stars": PAYOUT_STARS,
    "pay_rub": PAYOUT_RUB,
    "pay_crypto": PAYOUT_CRYPTO,
}


@router.callback_query(WithdrawCB.filter(F.action.in_(_PAYOUTS)))
async def choose_payout(
    query: CallbackQuery,
    callback_data: WithdrawCB,
    session: AsyncSession,
    db_user: User | None,
    bot: Bot,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    if await state.get_state() != WithdrawStates.payout.state:
        await query.answer("Сначала выберите сумму.", show_alert=True)
        return
    data = await state.get_data()
    amount = data.get("amount")
    if not isinstance(amount, int):
        await state.clear()
        await query.answer("Заявка устарела. Начните заново.", show_alert=True)
        return
    user = await ensure_user(session, query.from_user, db_user)
    reward_id = data.get("reward_id")
    reward_title = data.get("reward_title")
    await state.clear()
    await _create(
        query,
        session,
        bot,
        user,
        amount,
        reward_id if isinstance(reward_id, int) else None,
        reward_title if isinstance(reward_title, str) else None,
        _PAYOUTS[callback_data.action],
    )


@router.callback_query(WithdrawCB.filter(F.action == "mine"))
async def mine(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    items = await withdrawal_service.list_for_user(session, user.id)
    await show_screen(query, my_withdrawals_text(_lines(items)), my_withdrawals(items))


@router.callback_query(WithdrawCB.filter(F.action == "cancel"))
async def cancel_request(
    query: CallbackQuery,
    callback_data: WithdrawCB,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    current = await withdrawal_service.get_withdrawal(session, callback_data.item_id)
    if current is None or current.user_id != user.id:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    if current.status != WITHDRAWAL_PENDING:
        await query.answer("Эту заявку уже нельзя отменить.", show_alert=True)
        return
    code = await withdrawal_service.set_status(session, current.id, "cancelled")
    if code != "ok":
        await query.answer("Статус уже изменился.", show_alert=True)
        return
    await session.refresh(user)
    items = await withdrawal_service.list_for_user(session, user.id)
    await show_screen(query, "Заявка отменена.\n\n" + my_withdrawals_text(_lines(items)), my_withdrawals(items))


def _lines(items) -> list[str]:
    return [
        (
            f"#{item.id} · {format_stars(item.amount)} · "
            f"{PAYOUT_LABELS.get(item.payment_method, item.payment_method)} · "
            f"{WITHDRAWAL_STATUS_LABELS.get(item.status, item.status)}"
        )
        for item in items
    ]


async def _create(
    event,
    session,
    bot,
    user: User,
    amount: int,
    reward_id: int | None,
    reward_title: str | None,
    payout: str,
) -> None:
    code, withdrawal = await withdrawal_service.create_withdrawal(
        session,
        user.id,
        amount,
        reward_id,
        payout,
    )
    if code == "too_small":
        await session.refresh(user)
        minimum = withdrawal_service.minimum_for(user)
        text = f"Минимум сейчас — {format_stars(minimum)}."
        if isinstance(event, CallbackQuery):
            await show_screen(event, f"{text}\n\n{withdraw_text(user, has_rewards=True)}", withdraw_back())
        else:
            await event.answer(text)
        return
    if code == "insufficient":
        text = "Недостаточно доступного баланса. Сумма в других заявках уже зарезервирована."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return
    if code != "ok" or withdrawal is None:
        text = "Не получилось создать заявку."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return
    await send_admin(
        bot,
        new_withdrawal(user, withdrawal, reward_title),
        open_record_kb("wd", withdrawal.id),
    )
    text = withdrawal_created(withdrawal.id, withdrawal.amount, withdrawal.payment_method)
    if isinstance(event, CallbackQuery):
        await show_screen(event, text, withdraw_back())
    else:
        await event.answer(text, reply_markup=withdraw_back())
