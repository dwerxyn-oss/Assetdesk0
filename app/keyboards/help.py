from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.callbacks import HelpCB, MenuCB
from app.keyboards.common import back, btn, kb
from app.utils.links import support_link


def help_menu() -> InlineKeyboardMarkup:
    return kb(
        [btn("Как заработать?", HelpCB(topic="earn"))],
        [btn("Как получить награду?", HelpCB(topic="reward"))],
        [btn("Как работает вывод?", HelpCB(topic="out"))],
        [btn("Как продать NFT?", HelpCB(topic="gift"))],
        [btn("Почему у новых продавцов есть лимит?", HelpCB(topic="lim"))],
        [btn("Как увеличить лимит?", HelpCB(topic="lvl"))],
        [btn("Куда обратиться по вопросу?", HelpCB(topic="err"))],
        [InlineKeyboardButton(text="👨‍💻 Поддержка", url=support_link())],
        [btn("ℹ️ О AssetDesk", MenuCB(action="about"))],
        [back(MenuCB(action="main"))],
    )


def help_back() -> InlineKeyboardMarkup:
    return kb([back(MenuCB(action="help"))])
