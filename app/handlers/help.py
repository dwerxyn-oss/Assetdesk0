from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.callbacks import HelpCB, MenuCB
from app.keyboards.help import help_back, help_menu
from app.keyboards.menu import back_main
from app.middlewares.context import ensure_user
from app.services.stats import collect
from app.texts.messages import about_text, faq_text, help_text
from app.utils.ui import show_screen

router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(
    message: Message,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if message.from_user is None:
        return
    user = await ensure_user(session, message.from_user, db_user)
    await message.answer(help_text(user.telegram_id), reply_markup=help_menu())


@router.callback_query(MenuCB.filter(F.action == "help"))
async def open_help(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    await show_screen(query, help_text(user.telegram_id), help_menu())


@router.callback_query(HelpCB.filter())
async def open_faq(query: CallbackQuery, callback_data: HelpCB) -> None:
    await show_screen(query, faq_text(callback_data.topic), help_back())


@router.callback_query(MenuCB.filter(F.action == "about"))
async def open_about(query: CallbackQuery, session: AsyncSession) -> None:
    stats = await collect(session)
    await show_screen(query, about_text(stats), back_main())
