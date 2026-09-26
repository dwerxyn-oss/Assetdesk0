from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.keyboards.callbacks import MenuCB
from app.keyboards.menu import back_main
from app.middlewares.context import ensure_user
from app.services.referrals import count_invited, referral_earned
from app.texts.messages import referral_text
from app.utils.ui import show_screen

router = Router(name="referral")


@router.callback_query(MenuCB.filter(F.action == "referral"))
async def open_referral(
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
    text = referral_text(
        invited=await count_invited(session, user.id),
        earned=await referral_earned(session, user.id),
        telegram_id=user.telegram_id,
    )
    await show_screen(query, text, back_main())
