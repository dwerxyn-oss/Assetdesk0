"""История только своего пользователя."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    HISTORY_PAGE_SIZE,
    SELL_STATUS_LABELS,
    TRANSACTION_LABELS,
    WITHDRAWAL_COMPLETED,
    WITHDRAWAL_STATUS_LABELS,
)
from app.db.models import SellRequest, Transaction, Withdrawal
from app.utils.money import format_signed_stars, format_stars
from app.utils.text import h
from app.utils.time import format_local


@dataclass(frozen=True, slots=True)
class HistoryRow:
    at: datetime
    text: str


async def page_for_user(
    session: AsyncSession,
    user_id: int,
    page: int,
    page_size: int = HISTORY_PAGE_SIZE,
) -> tuple[list[HistoryRow], int]:
    transactions = list(
        await session.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.id.desc())
            .limit(200)
        )
    )
    withdrawals = list(
        await session.scalars(
            select(Withdrawal)
            .where(
                Withdrawal.user_id == user_id,
                Withdrawal.status != WITHDRAWAL_COMPLETED,
            )
            .order_by(Withdrawal.id.desc())
            .limit(50)
        )
    )
    sells = list(
        await session.scalars(
            select(SellRequest)
            .where(SellRequest.user_id == user_id)
            .order_by(SellRequest.id.desc())
            .limit(50)
        )
    )
    rows: list[HistoryRow] = []
    for tx in transactions:
        label = TRANSACTION_LABELS.get(tx.type, "Операция")
        rows.append(HistoryRow(tx.created_at, f"{label} · {format_signed_stars(tx.amount)}"))
    for withdrawal in withdrawals:
        label = WITHDRAWAL_STATUS_LABELS.get(withdrawal.status, withdrawal.status)
        rows.append(
            HistoryRow(
                withdrawal.created_at,
                f"Заявка на вывод · {format_stars(withdrawal.amount)} · {label}",
            )
        )
    for sell in sells:
        label = SELL_STATUS_LABELS.get(sell.status, sell.status)
        price = ""
        if sell.admin_price is not None and sell.currency:
            price = f" · {sell.admin_price} {h(sell.currency)}"
        name = h(" ".join(sell.gift_name.split()))
        rows.append(HistoryRow(sell.created_at, f"Продажа · {name}{price} · {label}"))
    rows.sort(key=lambda row: row.at, reverse=True)
    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    safe_page = min(max(page, 0), pages - 1)
    start = safe_page * page_size
    return rows[start : start + page_size], pages


def render_rows(rows: list[HistoryRow]) -> str:
    if not rows:
        return "Пока пусто."
    lines = [f"{format_local(row.at)} · {row.text}" for row in rows]
    return "\n".join(lines)
