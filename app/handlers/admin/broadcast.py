from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import broadcast_confirm_kb
from app.keyboards.callbacks import AdminCB
from app.keyboards.common import back, kb
from app.middlewares.context import PLAIN_TEXT
from app.services.broadcast import broadcast, recipient_ids
from app.states.flows import AdminBroadcastStates
from app.utils.text import h
from app.utils.ui import show_screen

router = Router(name="admin-broadcast")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())


@router.callback_query(AdminCB.filter((F.section == "bcast") & (F.action == "start")))
async def ask_text(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminBroadcastStates.text)
    await show_screen(
        query,
        "Отправьте текст рассылки. Он уйдёт обычным текстом всем, кто не заблокирован.",
        kb([back(AdminCB(section="menu", action="open"))]),
    )


@router.message(AdminBroadcastStates.text, PLAIN_TEXT)
async def take_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > 3000:
        await message.answer("Нужен текст до 3000 символов.")
        return
    count = len(await recipient_ids(session))
    await state.update_data(text=text)
    await state.set_state(AdminBroadcastStates.confirm)
    await message.answer(
        f"Получателей: {count}\n\n{h(text[:700])}",
        reply_markup=broadcast_confirm_kb(),
    )


@router.callback_query(AdminCB.filter((F.section == "bcast") & (F.action == "send")))
async def send(query: CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext) -> None:
    if await state.get_state() != AdminBroadcastStates.confirm.state:
        await query.answer("Сначала подготовьте текст.", show_alert=True)
        return
    data = await state.get_data()
    raw = data.get("text")
    if not isinstance(raw, str) or not raw.strip():
        await state.clear()
        await query.answer("Текст не найден.", show_alert=True)
        return
    ids = await recipient_ids(session)
    await state.clear()
    await query.answer("Рассылка началась")
    delivered, failed = await broadcast(bot, ids, h(raw))
    if query.message is not None:
        await query.message.answer(f"Готово.\nДоставлено: {delivered}\nНе доставлено: {failed}")
