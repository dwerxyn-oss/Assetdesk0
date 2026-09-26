from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from app.constants import SELL_AWAITING_TRANSFER, SELL_OFFER_SENT
from app.db.models import SellRequest
from app.keyboards.callbacks import MenuCB, SellCB
from app.keyboards.common import back, btn, kb


def sell_entry(*, active: SellRequest | None) -> InlineKeyboardMarkup:
    rows: list[list] = []
    if active is None:
        rows.append([btn("Начать", SellCB(action="begin"))])
    elif active.status == SELL_OFFER_SENT:
        rows.append([btn("✅ Принять предложение", SellCB(action="accept", item_id=active.id))])
        rows.append([btn("❌ Отказаться", SellCB(action="decline", item_id=active.id))])
    elif active.status == SELL_AWAITING_TRANSFER:
        rows.append([btn("📨 Инструкция по передаче", SellCB(action="howto", item_id=active.id))])
    elif active.status in {"pending", "reviewing"}:
        rows.append([btn("Отменить заявку", SellCB(action="usercancel", item_id=active.id))])
    rows.append([back(MenuCB(action="main"))])
    return kb(*rows)


def payment_methods() -> InlineKeyboardMarkup:
    return kb(
        [
            btn("⭐ Stars", SellCB(action="stars")),
            btn("₽ Рубли", SellCB(action="rub")),
        ],
        [btn("₿ Crypto", SellCB(action="crypto"))],
        [
            btn("✏️ Изменить", SellCB(action="edit")),
            btn("❌ Отмена", SellCB(action="abort")),
        ],
    )


def offer_decision(request_id: int) -> InlineKeyboardMarkup:
    return kb(
        [btn("✅ Принять предложение", SellCB(action="accept", item_id=request_id))],
        [btn("❌ Отказаться", SellCB(action="decline", item_id=request_id))],
    )


def after_accept(request_id: int) -> InlineKeyboardMarkup:
    return kb(
        [btn("📨 Инструкция по передаче", SellCB(action="howto", item_id=request_id))],
        [back(MenuCB(action="main"))],
    )


def step_back(action: str) -> InlineKeyboardMarkup:
    if action == "abort":
        return kb([btn("❌ Отмена", SellCB(action="abort"))])
    return kb([back(SellCB(action=action))])
