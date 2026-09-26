from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.handlers.start import show_main
from app.middlewares.context import ensure_user

router = Router(name="fallback")


@router.message(Command("admin"))
async def admin_denied(message: Message) -> None:
    await message.answer("Команда доступна только администрации.")


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
@router.message(StateFilter(None), ~F.text)
async def hint(
    message: Message,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    user = await ensure_user(session, message.from_user, db_user)
    await show_main(message, user, state=state)


@router.callback_query()
async def stale(query: CallbackQuery) -> None:
    await query.answer("Кнопка устарела. Откройте /menu", show_alert=True)
