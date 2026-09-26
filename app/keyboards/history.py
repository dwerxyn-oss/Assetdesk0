from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import HistCB, MenuCB
from app.keyboards.common import back, btn, kb


def history_nav(page: int, pages: int) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(btn("◀️", HistCB(page=page - 1)))
    if page + 1 < pages:
        nav.append(btn("▶️", HistCB(page=page + 1)))
    return kb(nav, [back(MenuCB(action="main"))])
