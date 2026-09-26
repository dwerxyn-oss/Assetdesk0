"""Единственная точка изменения баланса. Каждое изменение пишет transaction."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    EARNING_TYPES,
    MAX_MONEY,
    TRANSACTION_ADMIN_ADJUSTMENT,
    TRANSACTION_TYPES,
    TRANSACTION_WITHDRAWAL,
)
from app.db.models import Transaction, User
from app.db.session import unit_of_work
from app.services.common import fresh
from app.utils.text import clip

logger = logging.getLogger(__name__)


class LedgerError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _log_balance(user: User, tx_type: str, amount: int) -> None:
    logger.info(
        "balance change user_id=%s telegram_id=%s type=%s amount=%s balance=%s reserved=%s",
        user.id,
        user.telegram_id,
        tx_type,
        amount,
        user.balance,
        user.reserved_balance,
    )


async def credit(
    session: AsyncSession,
    user: User,
    amount: int,
    tx_type: str,
    description: str,
) -> Transaction:
    if type(amount) is not int or amount <= 0 or amount > MAX_MONEY:
        raise LedgerError("bad_amount")
    if tx_type not in EARNING_TYPES and tx_type != TRANSACTION_ADMIN_ADJUSTMENT:
        raise LedgerError("bad_type")
    if tx_type not in TRANSACTION_TYPES:
        raise LedgerError("bad_type")
    user.balance += amount
    if tx_type in EARNING_TYPES:
        user.total_earned += amount
    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        description=clip(description, 300),
    )
    session.add(tx)
    await session.flush()
    _log_balance(user, tx_type, amount)
    return tx


async def admin_adjust(
    session: AsyncSession,
    user: User,
    amount: int,
    description: str,
) -> Transaction:
    note = description.strip()
    if not note:
        raise LedgerError("comment_required")
    if type(amount) is not int or amount == 0 or abs(amount) > MAX_MONEY:
        raise LedgerError("bad_amount")
    new_balance = user.balance + amount
    if new_balance < 0 or new_balance < user.reserved_balance:
        raise LedgerError("insufficient")
    user.balance = new_balance
    tx = Transaction(
        user_id=user.id,
        type=TRANSACTION_ADMIN_ADJUSTMENT,
        amount=amount,
        description=clip(note, 300),
    )
    session.add(tx)
    await session.flush()
    _log_balance(user, TRANSACTION_ADMIN_ADJUSTMENT, amount)
    return tx


async def record_withdrawal(
    session: AsyncSession,
    user: User,
    amount: int,
    description: str,
) -> Transaction:
    if type(amount) is not int or amount <= 0 or amount > MAX_MONEY:
        raise LedgerError("bad_amount")
    if user.balance < amount or user.reserved_balance < amount:
        raise LedgerError("insufficient")
    user.balance -= amount
    user.reserved_balance -= amount
    user.total_withdrawn += amount
    tx = Transaction(
        user_id=user.id,
        type=TRANSACTION_WITHDRAWAL,
        amount=-amount,
        description=clip(description, 300),
    )
    session.add(tx)
    await session.flush()
    _log_balance(user, TRANSACTION_WITHDRAWAL, -amount)
    return tx


async def adjust_balance(
    session: AsyncSession,
    user_id: int,
    amount: int,
    description: str,
) -> str:
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing"
        try:
            await admin_adjust(session, user, amount, description)
        except LedgerError as exc:
            return exc.code
    return "ok"
