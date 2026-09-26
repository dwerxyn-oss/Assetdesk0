from __future__ import annotations

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


async def fresh(session: AsyncSession, model: type[ModelT], pk: int) -> ModelT | None:
    """Перечитать строку внутри транзакции записи, чтобы не затереть чужое обновление."""
    return await session.get(model, pk, populate_existing=True)
