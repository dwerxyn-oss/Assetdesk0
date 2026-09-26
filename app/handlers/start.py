from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.callbacks import MenuCB
from app.keyboards.menu import main_menu
from app.middlewares.context import ensure_user
from app.services.users import create_user
from app.texts.messages import welcome
from app.utils.parsing import parse_start_referrer
from app.utils.ui import show_screen

router = Router(name="start")


async def show_main(
    event: Message | CallbackQuery,
    user: User,
    *,
    state: FSMContext | None = None,
) -> None:
    if state is not None:
        await state.clear()
    await show_screen(event, welcome(user), main_menu(), photo="menu")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    await state.clear()
    if message.from_user is None:
        return
    if db_user is None:
        user, _ = await create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or "",
            referrer_telegram_id=parse_start_referrer(command.args),
        )
    else:
        user = db_user
    await show_main(message, user)


@router.message(Command("menu", "cancel"))
async def cmd_menu(
    message: Message,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return
    user = await ensure_user(session, message.from_user, db_user)
    await show_main(message, user, state=state)


@router.callback_query(MenuCB.filter(F.action == "main"))
async def open_main(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
    state: FSMContext,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    await show_main(query, user, state=state)
