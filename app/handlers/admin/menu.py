from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_meta
from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import admin_menu
from app.keyboards.callbacks import AdminCB
from app.keyboards.common import back, btn, kb
from app.middlewares.context import PLAIN_TEXT
from app.services.content import META_GIFT_TRANSFER, gift_transfer_text
from app.services.stats import collect
from app.services.users import seller_level_counts
from app.states.flows import AdminSettingsStates
from app.texts.admin import balance_help, home, sellers_text, settings_text, stats_text
from app.utils.text import clip
from app.utils.ui import show_screen

router = Router(name="admin-menu")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())


async def open_panel(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_screen(event, home(), admin_menu())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await open_panel(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await open_panel(message, state)


@router.callback_query(AdminCB.filter((F.section == "menu") & (F.action == "open")))
async def menu_open(query: CallbackQuery, state: FSMContext) -> None:
    await open_panel(query, state)


@router.callback_query(AdminCB.filter((F.section == "balance") & (F.action == "open")))
async def balance_open(query: CallbackQuery) -> None:
    await show_screen(
        query,
        balance_help(),
        kb(
            [btn("Найти пользователя", AdminCB(section="users", action="search"))],
            [back(AdminCB(section="menu", action="open"))],
        ),
    )


@router.callback_query(AdminCB.filter((F.section == "settings") & (F.action == "open")))
async def settings_open(query: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    current = await gift_transfer_text(session)
    await show_screen(
        query,
        settings_text(clip(current, 700)),
        kb(
            [btn("Изменить инструкцию передачи", AdminCB(section="settings", action="transfer"))],
            [back(AdminCB(section="menu", action="open"))],
        ),
    )


@router.callback_query(AdminCB.filter((F.section == "settings") & (F.action == "transfer")))
async def ask_transfer(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSettingsStates.transfer)
    await show_screen(
        query,
        "Новый текст инструкции по передаче подарка. До 1000 символов.\n\n"
        "Пользователь увидит его только после принятия цены.",
        kb([back(AdminCB(section="settings", action="open"))]),
    )


@router.message(AdminSettingsStates.transfer, PLAIN_TEXT)
async def save_transfer(message: Message, session: AsyncSession, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > 1000:
        await message.answer("Нужен текст до 1000 символов.")
        return
    await set_meta(session, META_GIFT_TRANSFER, text)
    await state.clear()
    await message.answer("Инструкция обновлена.", reply_markup=admin_menu())


@router.callback_query(AdminCB.filter((F.section == "stats") & (F.action == "open")))
async def stats_open(query: CallbackQuery, session: AsyncSession) -> None:
    await show_screen(
        query,
        stats_text(await collect(session)),
        kb([back(AdminCB(section="menu", action="open"))]),
    )


@router.callback_query(AdminCB.filter((F.section == "seller") & (F.action == "open")))
async def sellers_open(query: CallbackQuery, session: AsyncSession) -> None:
    counts = await seller_level_counts(session)
    await show_screen(
        query,
        sellers_text(counts),
        kb(
            [btn("Найти продавца", AdminCB(section="users", action="search"))],
            [back(AdminCB(section="menu", action="open"))],
        ),
    )
