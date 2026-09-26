from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from app.keyboards.callbacks import MenuCB
from app.keyboards.common import back, btn, kb


def main_menu() -> InlineKeyboardMarkup:
    return kb(
        [btn("💰 Заработать", MenuCB(action="earn")), btn("🎁 Бонус дня", MenuCB(action="daily"))],
        [btn("🎁 Вывести", MenuCB(action="withdraw")), btn("💎 Мой баланс", MenuCB(action="balance"))],
        [btn("📦 Продать NFT", MenuCB(action="sell"))],
        [btn("👥 Пригласить друзей", MenuCB(action="referral"))],
        [btn("📜 История", MenuCB(action="history")), btn("❓ Помощь", MenuCB(action="help"))],
    )


def daily_menu(*, can_claim: bool) -> InlineKeyboardMarkup:
    rows: list[list] = []
    if can_claim:
        rows.append([btn("Получить", MenuCB(action="claim_daily"))])
    rows.append([back(MenuCB(action="main"))])
    return kb(*rows)


def balance_menu() -> InlineKeyboardMarkup:
    return kb(
        [btn("🎁 Вывести", MenuCB(action="withdraw")), btn("📜 История", MenuCB(action="history"))],
        [back(MenuCB(action="main"))],
    )


def back_main() -> InlineKeyboardMarkup:
    return kb([back(MenuCB(action="main"))])
