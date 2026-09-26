from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import AdminCB, MenuCB


def btn(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


def back(data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="⬅️ Назад", callback_data=data.pack())


def kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def main_cb() -> MenuCB:
    return MenuCB(action="main")


def admin_back() -> AdminCB:
    return AdminCB(section="menu", action="open")
