"""Сессии SQLite и короткие транзакции на запись."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, select, text, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import ROOT_DIR, Settings, get_settings
from app.constants import META_LAUNCHED_AT, SELLER_NEW
from app.db.base import Base
from app.db.locks import db_write_lock
from app.db.models import AppMeta, User
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def _sqlite_path(url: str) -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix) or url.endswith(":memory:"):
        return None
    raw = url[len(prefix) :]
    if raw.startswith("file:"):
        return None
    return Path(raw)


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    settings = settings or get_settings()
    url = settings.resolved_database_url()
    path = _sqlite_path(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, object] = {}
    if ":memory:" in url:
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def create_session_factory(
    engine: AsyncEngine | None = None,
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    bound = engine or create_engine(settings)
    return async_sessionmaker(bound, expire_on_commit=False, class_=AsyncSession)


_COLUMN_ADDITIONS: dict[str, dict[str, str]] = {
    "withdrawals": {
        "currency": "VARCHAR(16) NOT NULL DEFAULT 'STARS'",
        "payment_method": "VARCHAR(16) NOT NULL DEFAULT 'STARS'",
    },
    "sell_requests": {
        "gift_model": "VARCHAR(200) NOT NULL DEFAULT ''",
        "gift_pattern": "VARCHAR(200) NOT NULL DEFAULT ''",
        "gift_backdrop": "VARCHAR(200) NOT NULL DEFAULT ''",
    },
    "user_tasks": {
        "reward_at": "DATETIME",
    },
}


def _add_missing_columns(connection) -> None:
    for table, columns in _COLUMN_ADDITIONS.items():
        rows = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
        if not rows:
            continue
        existing = {row[1] for row in rows}
        for name, ddl in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


async def init_db(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_add_missing_columns)

    async with session_factory() as session:
        existing = await session.get(AppMeta, META_LAUNCHED_AT)
        if existing is None:
            session.add(AppMeta(key=META_LAUNCHED_AT, value=utcnow().isoformat()))
            await session.commit()
            logger.info("launch date stored")
        await session.execute(
            update(User).where(User.seller_level == "verified").values(seller_level=SELLER_NEW)
        )
        await session.commit()
        new_limit = get_settings().new_seller_limit_usd
        if new_limit != 10:
            raised = await session.execute(
                update(User)
                .where(User.seller_level == SELLER_NEW, User.seller_limit.in_((10, 20)))
                .values(seller_limit=new_limit)
            )
            await session.commit()
            if raised.rowcount:
                logger.info("new seller limit set to %s for %s users", new_limit, raised.rowcount)
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("database ready")


@asynccontextmanager
async def unit_of_work(session: AsyncSession) -> AsyncIterator[None]:
    """Короткая запись под общим замком процесса.

    Замок не реентерабельный: внутри нельзя открывать второй unit_of_work.
    Чтение в SQLAlchemy 2 само открывает транзакцию. Её нужно закрыть до
    записи, но не через rollback: rollback помечает объекты просроченными,
    и следующее обращение к ним ломает async-сессию. Чистое чтение фиксируется,
    а строка, которую меняем, заново читается уже внутри записи.
    """
    async with db_write_lock:
        if session.new or session.dirty or session.deleted:
            raise RuntimeError("Есть несохранённые изменения вне операции записи")
        if session.in_transaction():
            await session.commit()
        async with session.begin():
            yield


async def set_meta(session: AsyncSession, key: str, value: str) -> None:
    async with unit_of_work(session):
        row = await session.get(AppMeta, key)
        if row is None:
            session.add(AppMeta(key=key, value=value))
        else:
            row.value = value


async def get_meta(session: AsyncSession, key: str) -> str | None:
    row = await session.scalar(select(AppMeta).where(AppMeta.key == key))
    if row is None:
        return None
    return row.value
