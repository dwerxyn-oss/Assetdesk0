"""Тексты, которые администратор может заменить без правки кода."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_meta

META_GIFT_TRANSFER = "gift_transfer_text"


async def gift_transfer_text(session: AsyncSession) -> str:
    stored = await get_meta(session, META_GIFT_TRANSFER)
    if stored and stored.strip():
        return stored.strip()
    custom = get_settings().gift_transfer_text.strip()
    if custom:
        return custom
    support = get_settings().support_username
    return (
        f"Напишите @{support} и передайте NFT вручную. "
        "В первом сообщении укажите номер заявки. "
        "Бот NFT не принимает."
    )
