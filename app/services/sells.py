"""Заявки на продажу NFT. Бот не принимает и не переводит NFT."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    PAYMENT_METHODS,
    SELL_ACTIVE,
    SELL_AWAITING_TRANSFER,
    SELL_CANCELLED,
    SELL_COMPLETED,
    SELL_OFFER_SENT,
    SELL_REJECTED,
    SELL_TERMINAL,
    SELL_TRANSITIONS,
)
from app.db.models import SellRequest, User
from app.db.session import unit_of_work
from app.services.common import fresh
from app.utils.text import clip
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


async def get_request(session: AsyncSession, request_id: int) -> SellRequest | None:
    return await session.get(SellRequest, request_id)


async def active_for_user(session: AsyncSession, user_id: int) -> SellRequest | None:
    return await session.scalar(
        select(SellRequest)
        .where(SellRequest.user_id == user_id, SellRequest.status.in_(SELL_ACTIVE))
        .order_by(SellRequest.id.desc())
    )


async def list_for_user(session: AsyncSession, user_id: int, limit: int = 10) -> list[SellRequest]:
    rows = await session.scalars(
        select(SellRequest)
        .where(SellRequest.user_id == user_id)
        .order_by(SellRequest.id.desc())
        .limit(limit)
    )
    return list(rows)


async def list_by_statuses(
    session: AsyncSession,
    statuses: frozenset[str] | set[str],
    *,
    offset: int,
    limit: int,
) -> list[SellRequest]:
    rows = await session.scalars(
        select(SellRequest)
        .where(SellRequest.status.in_(statuses))
        .order_by(SellRequest.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows)


async def create_request(
    session: AsyncSession,
    *,
    user_id: int,
    gift_name: str,
    gift_link: str,
    gift_identifier: str,
    payment_method: str,
    gift_model: str = "",
    gift_pattern: str = "",
    gift_backdrop: str = "",
) -> tuple[str, SellRequest | None]:
    if payment_method not in PAYMENT_METHODS:
        return "bad_method", None
    async with unit_of_work(session):
        user = await fresh(session, User, user_id)
        if user is None:
            return "missing", None
        existing = await active_for_user(session, user.id)
        if existing is not None:
            return "active_exists", existing
        request = SellRequest(
            user_id=user.id,
            gift_name=clip(gift_name, 200),
            gift_link=gift_link[:500],
            gift_identifier=gift_identifier[:500],
            gift_model=clip(gift_model, 200),
            gift_pattern=clip(gift_pattern, 200),
            gift_backdrop=clip(gift_backdrop, 200),
            requested_payment_method=payment_method,
            status="pending",
        )
        session.add(request)
        await session.flush()
        logger.info(
            "sell request created id=%s user_id=%s telegram_id=%s method=%s",
            request.id,
            user.id,
            user.telegram_id,
            payment_method,
        )
        return "ok", request


async def send_offer(
    session: AsyncSession,
    request_id: int,
    price: int,
    currency: str,
) -> str:
    if price <= 0 or not currency.strip():
        return "bad_price"
    async with unit_of_work(session):
        request = await fresh(session, SellRequest, request_id)
        if request is None:
            return "missing"
        if SELL_OFFER_SENT not in SELL_TRANSITIONS[request.status]:
            return "bad_status"
        request.admin_price = price
        request.currency = currency.strip().upper()[:16]
        request.status = SELL_OFFER_SENT
        request.updated_at = utcnow()
    logger.info(
        "sell offer id=%s price=%s currency=%s",
        request_id,
        price,
        currency.upper(),
    )
    return "ok"


async def user_decide(session: AsyncSession, request_id: int, user_id: int, *, accept: bool) -> str:
    new_status = SELL_AWAITING_TRANSFER if accept else SELL_CANCELLED
    async with unit_of_work(session):
        request = await fresh(session, SellRequest, request_id)
        if request is None:
            return "missing"
        if request.user_id != user_id:
            return "forbidden"
        if request.status != SELL_OFFER_SENT:
            return "bad_status"
        if new_status not in SELL_TRANSITIONS[request.status]:
            return "bad_status"
        request.status = new_status
        request.updated_at = utcnow()
    logger.info("sell user decision id=%s accept=%s", request_id, accept)
    return "ok"


async def set_status(
    session: AsyncSession,
    request_id: int,
    new_status: str,
    *,
    note: str = "",
) -> str:
    if new_status not in SELL_TRANSITIONS:
        return "bad_status"
    async with unit_of_work(session):
        request = await fresh(session, SellRequest, request_id)
        if request is None:
            return "missing"
        if new_status not in SELL_TRANSITIONS[request.status]:
            return "bad_status"
        if new_status == SELL_OFFER_SENT and (request.admin_price is None or not request.currency):
            return "no_price"
        user = await fresh(session, User, request.user_id)
        if user is None:
            return "missing"
        if new_status == SELL_COMPLETED and not request.stats_applied:
            user.successful_deals += 1
            if request.currency == "USD" and request.admin_price:
                user.total_volume += request.admin_price
            request.stats_applied = True
            request.completed_at = utcnow()
        request.status = new_status
        if note.strip():
            request.admin_note = clip(note.strip(), 2000)
        request.updated_at = utcnow()
    logger.info("sell status id=%s status=%s", request_id, new_status)
    return "ok"


async def set_note(session: AsyncSession, request_id: int, note: str) -> str:
    async with unit_of_work(session):
        request = await fresh(session, SellRequest, request_id)
        if request is None:
            return "missing"
        request.admin_note = clip(note.strip(), 2000)
        request.updated_at = utcnow()
    logger.info("sell note id=%s", request_id)
    return "ok"


async def mark_failed(session: AsyncSession, request_id: int) -> str:
    async with unit_of_work(session):
        request = await fresh(session, SellRequest, request_id)
        if request is None:
            return "missing"
        if (
            request.status in {SELL_COMPLETED, SELL_CANCELLED}
            or request.stats_applied
            or request.failure_applied
        ):
            return "bad_status"
        user = await fresh(session, User, request.user_id)
        if user is None:
            return "missing"
        if request.status not in SELL_TERMINAL:
            request.status = SELL_REJECTED
        request.failure_applied = True
        user.failed_deals += 1
        request.updated_at = utcnow()
    logger.info("sell marked failed id=%s", request_id)
    return "ok"


async def user_cancel(session: AsyncSession, request_id: int, user_id: int) -> str:
    async with unit_of_work(session):
        request = await fresh(session, SellRequest, request_id)
        if request is None:
            return "missing"
        if request.user_id != user_id:
            return "forbidden"
        if request.status not in { "pending", "reviewing", "offer_sent"}:
            return "bad_status"
        request.status = SELL_CANCELLED
        request.updated_at = utcnow()
    logger.info("sell cancelled by user id=%s", request_id)
    return "ok"


async def count_by_status(session: AsyncSession, status: str) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(SellRequest).where(SellRequest.status == status)
        )
        or 0
    )
