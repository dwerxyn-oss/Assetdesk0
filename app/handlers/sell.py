from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PAYMENT_CRYPTO, PAYMENT_RUB, PAYMENT_STARS
from app.db.models import User
from app.keyboards.admin import new_sell_kb, open_record_kb
from app.keyboards.callbacks import MenuCB, SellCB
from app.keyboards.menu import back_main
from app.keyboards.sell import after_accept, payment_methods, sell_entry, step_back
from app.middlewares.context import PLAIN_TEXT, ensure_user
from app.services.content import gift_transfer_text
from app.services.notify import send_admin
from app.services.sells import (
    active_for_user,
    create_request,
    get_request,
    user_cancel,
    user_decide,
)
from app.states.flows import SellStates
from app.texts.admin import new_sell, sell_decision
from app.texts.messages import (
    offer_accepted,
    sell_sent,
    sell_step_backdrop,
    sell_step_model,
    sell_step_name,
    sell_step_number,
    sell_step_pattern,
    sell_summary,
    sell_text,
    transfer_guide,
)
from app.utils.parsing import parse_gift_number, parse_trait
from app.utils.ui import show_screen

router = Router(name="sell")

_METHODS = {
    "stars": PAYMENT_STARS,
    "rub": PAYMENT_RUB,
    "crypto": PAYMENT_CRYPTO,
}

_REQUIRED = ("gift_name", "gift_number", "gift_model", "gift_pattern", "gift_backdrop")


async def _open(event, session: AsyncSession, user: User) -> None:
    await session.refresh(user)
    active = await active_for_user(session, user.id)
    await show_screen(event, sell_text(user, active), sell_entry(active=active), photo="sell")


def _ready(data: dict) -> bool:
    return all(data.get(key) for key in _REQUIRED)


@router.callback_query(MenuCB.filter(F.action == "sell"))
async def open_sell(
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
    await _open(query, session, user)


@router.callback_query(SellCB.filter(F.action == "begin"))
async def begin(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    if await active_for_user(session, user.id) is not None:
        await query.answer("Сначала закройте текущую заявку.", show_alert=True)
        return
    await state.set_state(SellStates.name)
    await state.set_data({})
    await show_screen(query, sell_step_name(), step_back("abort"))


@router.callback_query(SellCB.filter(F.action == "edit"))
async def edit_draft(query: CallbackQuery, state: FSMContext) -> None:
    if await state.get_state() != SellStates.payment.state:
        await query.answer("Сначала заполните данные подарка.", show_alert=True)
        return
    await state.set_state(SellStates.name)
    await show_screen(query, sell_step_name(), step_back("abort"))


@router.callback_query(SellCB.filter(F.action == "back_name"))
async def back_name(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellStates.name)
    await show_screen(query, sell_step_name(), step_back("abort"))


@router.callback_query(SellCB.filter(F.action == "back_number"))
async def back_number(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellStates.number)
    await show_screen(query, sell_step_number(), step_back("back_name"))


@router.callback_query(SellCB.filter(F.action == "back_model"))
async def back_model(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellStates.model)
    await show_screen(query, sell_step_model(), step_back("back_number"))


@router.callback_query(SellCB.filter(F.action == "back_pattern"))
async def back_pattern(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellStates.pattern)
    await show_screen(query, sell_step_pattern(), step_back("back_model"))


@router.message(SellStates.name, PLAIN_TEXT)
async def take_name(message: Message, state: FSMContext) -> None:
    name = parse_trait(message.text or "")
    if name is None:
        await message.answer("Введите название одним сообщением, до 80 символов.")
        return
    await state.update_data(gift_name=name)
    await state.set_state(SellStates.number)
    await message.answer(sell_step_number(), reply_markup=step_back("back_name"))


@router.message(SellStates.number, PLAIN_TEXT)
async def take_number(message: Message, state: FSMContext) -> None:
    number = parse_gift_number(message.text or "")
    if number is None:
        await message.answer("Нужен номер: 12345 или #12345.")
        return
    await state.update_data(gift_number=number)
    await state.set_state(SellStates.model)
    await message.answer(sell_step_model(), reply_markup=step_back("back_number"))


@router.message(SellStates.model, PLAIN_TEXT)
async def take_model(message: Message, state: FSMContext) -> None:
    value = parse_trait(message.text or "")
    if value is None:
        await message.answer("Укажите модель одним сообщением, до 80 символов.")
        return
    await state.update_data(gift_model=value)
    await state.set_state(SellStates.pattern)
    await message.answer(sell_step_pattern(), reply_markup=step_back("back_model"))


@router.message(SellStates.pattern, PLAIN_TEXT)
async def take_pattern(message: Message, state: FSMContext) -> None:
    value = parse_trait(message.text or "")
    if value is None:
        await message.answer("Укажите узор одним сообщением, до 80 символов.")
        return
    await state.update_data(gift_pattern=value)
    await state.set_state(SellStates.backdrop)
    await message.answer(sell_step_backdrop(), reply_markup=step_back("back_pattern"))


@router.message(SellStates.backdrop, PLAIN_TEXT)
async def take_backdrop(message: Message, state: FSMContext) -> None:
    value = parse_trait(message.text or "")
    if value is None:
        await message.answer("Укажите фон одним сообщением, до 80 символов.")
        return
    await state.update_data(gift_backdrop=value)
    data = await state.get_data()
    if not _ready(data):
        await state.set_state(SellStates.name)
        await message.answer("Часть данных потерялась. Начните с названия.", reply_markup=step_back("abort"))
        return
    await state.set_state(SellStates.payment)
    await message.answer(sell_summary(data), reply_markup=payment_methods())


@router.message(SellStates.name, ~F.text)
@router.message(SellStates.number, ~F.text)
@router.message(SellStates.model, ~F.text)
@router.message(SellStates.pattern, ~F.text)
@router.message(SellStates.backdrop, ~F.text)
async def need_text(message: Message) -> None:
    await message.answer("На этом шаге нужен текст.")


@router.message(SellStates.payment, PLAIN_TEXT)
async def remind_payment(message: Message) -> None:
    await message.answer("Выберите способ оплаты кнопкой под карточкой.")


@router.callback_query(SellCB.filter(F.action.in_({"stars", "rub", "crypto"})))
async def choose_payment(
    query: CallbackQuery,
    callback_data: SellCB,
    session: AsyncSession,
    db_user: User | None,
    bot: Bot,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    if await state.get_state() != SellStates.payment.state:
        await query.answer("Сначала заполните данные подарка.", show_alert=True)
        return
    data = await state.get_data()
    if not _ready(data):
        await state.clear()
        await query.answer("Заявка устарела. Начните заново.", show_alert=True)
        return
    user = await ensure_user(session, query.from_user, db_user)
    code, request = await create_request(
        session,
        user_id=user.id,
        gift_name=data["gift_name"],
        gift_link="",
        gift_identifier=data["gift_number"],
        gift_model=data["gift_model"],
        gift_pattern=data["gift_pattern"],
        gift_backdrop=data["gift_backdrop"],
        payment_method=_METHODS[callback_data.action],
    )
    await state.clear()
    if code == "active_exists":
        await query.answer("У вас уже есть открытая заявка.", show_alert=True)
        return
    if code != "ok" or request is None:
        await query.answer("Не получилось отправить заявку.", show_alert=True)
        return
    await send_admin(bot, new_sell(user, request), new_sell_kb(user, request.id))
    await show_screen(query, sell_sent(request.id), back_main())


@router.callback_query(SellCB.filter(F.action == "abort"))
async def abort(
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
    await _open(query, session, user)


@router.callback_query(SellCB.filter(F.action.in_({"accept", "decline"})))
async def decide(
    query: CallbackQuery,
    callback_data: SellCB,
    session: AsyncSession,
    db_user: User | None,
    bot: Bot,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    await state.clear()
    user = await ensure_user(session, query.from_user, db_user)
    accepted = callback_data.action == "accept"
    code = await user_decide(session, callback_data.item_id, user.id, accept=accepted)
    if code == "forbidden":
        await query.answer("Это не ваша заявка.", show_alert=True)
        return
    if code != "ok":
        await query.answer("Предложение уже недоступно.", show_alert=True)
        return
    request = await get_request(session, callback_data.item_id)
    if request is None:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    await send_admin(
        bot,
        sell_decision(user, request, accepted=accepted),
        open_record_kb("sell", request.id),
    )
    if accepted:
        await show_screen(query, offer_accepted(request.id), after_accept(request.id))
        return
    await show_screen(query, f"Предложение по заявке #{request.id} отклонено.", back_main())


@router.callback_query(SellCB.filter(F.action == "howto"))
async def howto(
    query: CallbackQuery,
    callback_data: SellCB,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    request = await get_request(session, callback_data.item_id)
    if request is None or request.user_id != user.id:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    if request.status not in {"awaiting_transfer", "received", "paid"}:
        await query.answer("Инструкция появится после принятия предложения.", show_alert=True)
        return
    body = await gift_transfer_text(session)
    await show_screen(query, transfer_guide(body), after_accept(request.id))


@router.callback_query(SellCB.filter(F.action == "usercancel"))
async def cancel_own(
    query: CallbackQuery,
    callback_data: SellCB,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    await state.clear()
    user = await ensure_user(session, query.from_user, db_user)
    code = await user_cancel(session, callback_data.item_id, user.id)
    if code == "forbidden":
        await query.answer("Это не ваша заявка.", show_alert=True)
        return
    if code != "ok":
        await query.answer("Эту заявку уже нельзя отменить.", show_alert=True)
        return
    await session.refresh(user)
    await _open(query, session, user)
