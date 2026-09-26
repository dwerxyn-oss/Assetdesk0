import os

os.environ["BOT_TOKEN"] = "123:TEST"
os.environ["ADMIN_ID"] = "1"
os.environ["BOT_USERNAME"] = "assetdesk_test_bot"
os.environ["SUPPORT_USERNAME"] = "AssetDeskOriginal"
os.environ["TIMEZONE"] = "Europe/Moscow"
os.environ["FIRST_WITHDRAW_MIN"] = "15"
os.environ["REGULAR_WITHDRAW_MIN"] = "15"
os.environ["NEW_SELLER_LIMIT_USD"] = "10"
os.environ["REGULAR_SELLER_LIMIT_USD"] = "50"
os.environ["TRUSTED_SELLER_LIMIT_USD"] = "100"
os.environ["REFERRAL_REWARD"] = "5"
os.environ["DAILY_BONUS"] = "2"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import Transaction
from app.db.session import create_engine, create_session_factory, init_db


@pytest.fixture
async def session():
    get_settings.cache_clear()
    engine = create_engine()
    factory = create_session_factory(engine)
    await init_db(engine, factory)
    async with factory() as db:
        yield db
    await engine.dispose()
    get_settings.cache_clear()


async def balance_of(session, user_id: int) -> int:
    from app.db.models import User

    user = await session.get(User, user_id)
    assert user is not None
    return user.balance


async def tx_sum(session, user_id: int) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id)
    )
    return int(total or 0)
