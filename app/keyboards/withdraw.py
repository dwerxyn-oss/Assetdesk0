from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Reward, Withdrawal
from app.keyboards.callbacks import MenuCB, WithdrawCB
from app.keyboards.common import back, btn, kb
from app.utils.text import clip


def withdraw_menu(
    rewards: list[Reward],
    *,
    can_request: bool,
    requests: list[Withdrawal],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for reward in rewards:
        label = clip(f"{reward.title} · {reward.cost_stars} ⭐", 60)
        rows.append([btn(label, WithdrawCB(action="reward", item_id=reward.id))])
    if can_request:
        rows.append([btn("Указать сумму", WithdrawCB(action="custom"))])
    if requests:
        rows.append([btn("Мои заявки", WithdrawCB(action="mine"))])
    rows.append([back(MenuCB(action="main"))])
    return kb(*rows)


def withdraw_back() -> InlineKeyboardMarkup:
    return kb([back(MenuCB(action="withdraw"))])


def payout_methods() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("⭐ Stars", WithdrawCB(action="pay_stars")),
            btn("₽ Рубли", WithdrawCB(action="pay_rub")),
        ],
        [btn("₿ Crypto", WithdrawCB(action="pay_crypto"))],
        [back(MenuCB(action="withdraw"))],
    )


def my_withdrawals(requests: list[Withdrawal]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in requests:
        if item.status == "pending":
            rows.append(
                [btn(f"Отменить #{item.id} · {item.amount} ⭐", WithdrawCB(action="cancel", item_id=item.id))]
            )
    rows.append([back(MenuCB(action="withdraw"))])
    return kb(*rows)
