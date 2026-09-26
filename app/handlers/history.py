from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.callbacks import HistCB, MenuCB
from app.keyboards.history import history_nav
from app.middlewares.context import ensure_user
from app.services.history import page_for_user
from app.texts.messages import history_text
from app.utils.ui import show_screen

router = Router(name="history")


async def _show(event, session: AsyncSession, user: User, page: int) -> None:
    rows, pages = await page_for_user(session, user.id, page)
    safe_page = min(max(page, 0), pages - 1)
    await show_screen(event, history_text(rows, safe_page, pages), history_nav(safe_page, pages))


@router.callback_query(MenuCB.filter(F.action == "history"))
async def open_history(
    query: CallbackQuery,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    await _show(query, session, user, 0)


@router.callback_query(HistCB.filter())
async def history_page(
    query: CallbackQuery,
    callback_data: HistCB,
    session: AsyncSession,
    db_user: User | None,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    user = await ensure_user(session, query.from_user, db_user)
    await _show(query, session, user, max(callback_data.page, 0))
