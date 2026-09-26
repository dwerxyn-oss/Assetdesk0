from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import reward_card_kb, reward_list_kb
from app.keyboards.callbacks import AdminCB
from app.keyboards.common import back, kb
from app.middlewares.context import PLAIN_TEXT
from app.services.rewards import (
    create_reward,
    delete_reward,
    get_reward,
    list_all,
    set_active,
    set_cost,
)
from app.states.flows import AdminRewardStates
from app.texts.admin import reward_card
from app.utils.parsing import parse_positive_int
from app.utils.ui import show_screen

router = Router(name="admin-rewards")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())


async def _show(event, session: AsyncSession, reward_id: int) -> None:
    reward = await get_reward(session, reward_id)
    if reward is None:
        if isinstance(event, CallbackQuery):
            await event.answer("Награда не найдена.", show_alert=True)
        return
    await show_screen(event, reward_card(reward), reward_card_kb(reward))


@router.callback_query(AdminCB.filter((F.section == "reward") & (F.action == "list")))
async def reward_list(query: CallbackQuery, session: AsyncSession) -> None:
    rewards = await list_all(session)
    text = "<b>Награды</b>" if rewards else "<b>Награды</b>\n\nКаталог пуст."
    await show_screen(query, text, reward_list_kb(rewards))


@router.callback_query(AdminCB.filter((F.section == "reward") & (F.action == "view")))
async def reward_view(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    await _show(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "reward") & (F.action == "new")))
async def reward_new(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminRewardStates.title)
    await show_screen(query, "Название награды.", kb([back(AdminCB(section="reward", action="list"))]))


@router.message(AdminRewardStates.title, PLAIN_TEXT)
async def reward_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 150:
        await message.answer("Название нужно, до 150 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminRewardStates.description)
    await message.answer("Описание для пользователя. «-», если его нет.")


@router.message(AdminRewardStates.description, PLAIN_TEXT)
async def reward_description(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    await state.update_data(description="" if raw == "-" else raw[:1000])
    await state.set_state(AdminRewardStates.cost)
    await message.answer("Стоимость в целых ⭐.")


@router.message(AdminRewardStates.cost, PLAIN_TEXT)
async def reward_cost(message: Message, state: FSMContext) -> None:
    cost = parse_positive_int(message.text or "")
    if cost is None or cost > 1_000_000:
        await message.answer("Нужно целое число больше нуля.")
        return
    await state.update_data(cost=cost)
    await state.set_state(AdminRewardStates.reference)
    await message.answer("Служебная метка подарка. Пользователь её не увидит. «-», если нет.")


@router.message(AdminRewardStates.reference, PLAIN_TEXT)
async def reward_reference(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    raw = (message.text or "").strip()
    await state.clear()
    created = await create_reward(
        session,
        title=data["title"],
        description=data.get("description", ""),
        cost_stars=int(data["cost"]),
        gift_reference="" if raw == "-" else raw[:200],
    )
    if isinstance(created, str):
        await message.answer("Не получилось добавить награду.")
        return
    await _show(message, session, created.id)


@router.callback_query(AdminCB.filter((F.section == "reward") & (F.action == "cost")))
async def ask_cost(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    await state.set_state(AdminRewardStates.edit_cost)
    await state.set_data({"reward_id": callback_data.item_id})
    await show_screen(
        query,
        "Новая стоимость в целых ⭐.",
        kb([back(AdminCB(section="reward", action="view", item_id=callback_data.item_id))]),
    )


@router.message(AdminRewardStates.edit_cost, PLAIN_TEXT)
async def take_cost(message: Message, session: AsyncSession, state: FSMContext) -> None:
    cost = parse_positive_int(message.text or "")
    if cost is None:
        await message.answer("Нужно целое число больше нуля.")
        return
    data = await state.get_data()
    reward_id = int(data["reward_id"])
    code = await set_cost(session, reward_id, cost)
    await state.clear()
    if code != "ok":
        await message.answer("Не получилось изменить стоимость.")
        return
    await _show(message, session, reward_id)


@router.callback_query(AdminCB.filter((F.section == "reward") & (F.action == "toggle")))
async def reward_toggle(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    reward = await get_reward(session, callback_data.item_id)
    if reward is None:
        await query.answer("Награда не найдена.", show_alert=True)
        return
    code = await set_active(session, reward.id, not reward.active)
    if code != "ok":
        await query.answer("Не получилось изменить награду.", show_alert=True)
        return
    await _show(query, session, reward.id)


@router.callback_query(AdminCB.filter((F.section == "reward") & (F.action == "delete")))
async def reward_delete(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    code = await delete_reward(session, callback_data.item_id)
    if code == "used":
        await query.answer("Награда уже есть в заявках. Её можно только выключить.", show_alert=True)
        return
    if code != "ok":
        await query.answer("Награда не найдена.", show_alert=True)
        return
    rewards = await list_all(session)
    await show_screen(query, "Награда удалена.\n\n<b>Награды</b>", reward_list_kb(rewards))
