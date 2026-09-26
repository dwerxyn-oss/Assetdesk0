from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.callbacks import MenuCB
from app.keyboards.menu import balance_menu
from app.middlewares.context import ensure_user
from app.texts.messages import balance_text
from app.utils.ui import show_screen

router = Router(name="balance")


@router.callback_query(MenuCB.filter(F.action == "balance"))
async def open_balance(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    await session.refresh(user)
    await show_screen(query, balance_text(user), balance_menu())
