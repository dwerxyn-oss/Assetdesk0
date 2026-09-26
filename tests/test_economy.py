from datetime import date

import pytest

from app.config import get_settings
from app.constants import TASK_CHANNEL_SUBSCRIPTION, TASK_CUSTOM, TRANSACTION_ADMIN_ADJUSTMENT
from app.db.models import User
from app.filters import is_admin_id
from app.services.daily import claim
from app.services.ledger import adjust_balance
from app.services.tasks import complete_task, create_task
from app.services.users import create_user, set_seller_level
from app.services.withdrawals import create_withdrawal, set_status
from app.utils.parsing import parse_start_referrer
from tests.conftest import balance_of, tx_sum


def test_referrer_payload() -> None:
    assert parse_start_referrer(None) is None
    assert parse_start_referrer("hello") is None
    assert parse_start_referrer("ref_0") is None
    assert parse_start_referrer("ref_42") == 42


def test_admin_id_gate() -> None:
    assert is_admin_id(1) is True
    assert is_admin_id(2) is False


async def test_referral_is_paid_once_when_the_link_is_opened(session) -> None:
    inviter, _ = await create_user(session, telegram_id=10, username="inviter", first_name="Ann")
    invited, created = await create_user(
        session,
        telegram_id=11,
        username="invited",
        first_name="Bob",
        referrer_telegram_id=10,
    )
    assert created is True
    assert invited.referred_by == inviter.id
    assert invited.referral_reward_paid is True
    assert await balance_of(session, inviter.id) == get_settings().referral_reward

    again, created_again = await create_user(
        session,
        telegram_id=11,
        username="invited",
        first_name="Bob",
        referrer_telegram_id=99,
    )
    assert created_again is False
    assert again.referred_by == inviter.id
    assert await balance_of(session, inviter.id) == get_settings().referral_reward


async def test_self_referral_is_ignored(session) -> None:
    user, _ = await create_user(
        session,
        telegram_id=12,
        username="self",
        first_name="Self",
        referrer_telegram_id=12,
    )
    assert user.referred_by is None


async def test_task_reward_is_paid_once_and_referrer_gets_one_bonus(session) -> None:
    inviter, _ = await create_user(session, telegram_id=20, username="a", first_name="A")
    invited, _ = await create_user(
        session,
        telegram_id=21,
        username="b",
        first_name="B",
        referrer_telegram_id=20,
    )
    task = await create_task(
        session,
        title="Обычное",
        description="",
        reward=7,
        task_type=TASK_CUSTOM,
    )
    assert not isinstance(task, str)
    assert await complete_task(session, invited.id, task.id) == "ok"
    assert await complete_task(session, invited.id, task.id) == "already"
    assert await balance_of(session, invited.id) == 7
    assert await balance_of(session, inviter.id) == 5
    assert await tx_sum(session, invited.id) == 7
    assert await tx_sum(session, inviter.id) == 5

    second = await create_task(
        session,
        title="Ещё одно",
        description="",
        reward=3,
        task_type=TASK_CUSTOM,
    )
    assert not isinstance(second, str)
    assert await complete_task(session, invited.id, second.id) == "ok"
    assert await balance_of(session, inviter.id) == 5
    invited_row = await session.get(User, invited.id)
    assert invited_row is not None
    assert invited_row.referral_reward_paid is True


async def test_referral_daily_limit_stops_extra_payouts(session, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "referral_daily_limit", 1)
    inviter, _ = await create_user(session, telegram_id=21, username="cap", first_name="Cap")
    first, _ = await create_user(
        session,
        telegram_id=22,
        username="one",
        first_name="One",
        referrer_telegram_id=21,
    )
    second, _ = await create_user(
        session,
        telegram_id=23,
        username="two",
        first_name="Two",
        referrer_telegram_id=21,
    )
    assert first.referred_by == inviter.id
    assert second.referred_by == inviter.id
    assert await balance_of(session, inviter.id) == settings.referral_reward
    assert second.referral_reward_paid is True


async def test_channel_task_requires_confirmed_membership(session) -> None:
    user, _ = await create_user(session, telegram_id=30, username="c", first_name="C")
    task = await create_task(
        session,
        title="Канал",
        description="",
        reward=4,
        task_type=TASK_CHANNEL_SUBSCRIPTION,
        channel_username="assetdesk",
    )
    assert not isinstance(task, str)
    assert await complete_task(session, user.id, task.id, membership_confirmed=False) == "not_member"
    assert await balance_of(session, user.id) == 0
    assert await complete_task(session, user.id, task.id, membership_confirmed=True) == "ok"
    assert await complete_task(session, user.id, task.id, membership_confirmed=True) == "already"
    assert await balance_of(session, user.id) == 4


async def test_daily_bonus_once_per_day(session, monkeypatch: pytest.MonkeyPatch) -> None:
    user, _ = await create_user(session, telegram_id=40, username="d", first_name="D")
    monkeypatch.setattr("app.services.daily.today_in_tz", lambda: date(2026, 9, 26))
    assert await claim(session, user.id) == "ok"
    assert await claim(session, user.id) == "already"
    assert await balance_of(session, user.id) == get_settings().daily_bonus


async def test_withdrawal_reserves_once_and_completes_once(session) -> None:
    user, _ = await create_user(session, telegram_id=50, username="e", first_name="E")
    assert await adjust_balance(session, user.id, 40, "начисление для теста") == "ok"
    small, _ = await create_withdrawal(session, user.id, 10)
    assert small == "too_small"

    code, withdrawal = await create_withdrawal(session, user.id, 30)
    assert code == "ok"
    assert withdrawal is not None
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.balance == 40
    assert fresh.reserved_balance == 30

    second, _ = await create_withdrawal(session, user.id, 15)
    assert second == "insufficient"

    assert await set_status(session, withdrawal.id, "approved") == "ok"
    assert await set_status(session, withdrawal.id, "completed") == "ok"
    assert await set_status(session, withdrawal.id, "completed") == "bad_status"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.balance == 10
    assert fresh.reserved_balance == 0
    assert fresh.total_withdrawn == 30
    assert await tx_sum(session, user.id) == 10


async def test_rejected_withdrawal_releases_the_reserve(session) -> None:
    user, _ = await create_user(session, telegram_id=51, username="f", first_name="F")
    await adjust_balance(session, user.id, 20, "тест")
    code, withdrawal = await create_withdrawal(session, user.id, 15)
    assert code == "ok" and withdrawal is not None
    assert await set_status(session, withdrawal.id, "rejected") == "ok"
    assert await set_status(session, withdrawal.id, "rejected") == "bad_status"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.balance == 20
    assert fresh.reserved_balance == 0
    code, again = await create_withdrawal(session, user.id, 15)
    assert code == "ok" and again is not None


async def test_adjustment_cannot_eat_reserved_funds(session) -> None:
    user, _ = await create_user(session, telegram_id=52, username="g", first_name="G")
    await adjust_balance(session, user.id, 20, "тест")
    await create_withdrawal(session, user.id, 15)
    assert await adjust_balance(session, user.id, -10, "слишком много") == "insufficient"
    assert await adjust_balance(session, user.id, -5, "корректировка") == "ok"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.balance == 15
    assert fresh.reserved_balance == 15
    from sqlalchemy import select

    from app.db.models import Transaction

    kinds = list(
        await session.scalars(
            select(Transaction.type).where(Transaction.user_id == user.id)
        )
    )
    assert TRANSACTION_ADMIN_ADJUSTMENT in kinds


async def test_seller_level_does_not_change_limit(session) -> None:
    user, _ = await create_user(session, telegram_id=53, username="h", first_name="H")
    assert user.seller_limit == 10
    assert await set_seller_level(session, user.id, "regular") == "ok"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.seller_level == "regular"
    assert fresh.seller_limit == 10


async def test_unverified_task_pays_once_after_the_delay(session) -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from app.constants import TASK_PARTNER
    from app.db.models import UserTask
    from app.services.tasks import settle_due_tasks, start_timed
    from app.utils.time import utcnow

    user, _ = await create_user(session, telegram_id=60, username="vpn", first_name="Vpn")
    task = await create_task(
        session,
        title="VPN",
        description="",
        reward=4,
        task_type=TASK_PARTNER,
    )
    assert not isinstance(task, str)
    assert await start_timed(session, user.id, task.id) == "waiting"
    assert await balance_of(session, user.id) == 0
    assert await start_timed(session, user.id, task.id) == "waiting"
    assert await balance_of(session, user.id) == 0
    row = await session.scalar(select(UserTask).where(UserTask.user_id == user.id))
    assert row is not None
    row.reward_at = utcnow() - timedelta(seconds=1)
    await session.commit()
    notices = await settle_due_tasks(session)
    assert len(notices) == 1
    assert notices[0][0] == 60
    assert await balance_of(session, user.id) == 4
    assert await settle_due_tasks(session) == []
    assert await start_timed(session, user.id, task.id) == "already"


async def test_rub_withdrawal_is_stored_and_debited_once(session) -> None:
    user, _ = await create_user(session, telegram_id=54, username="rub", first_name="Rub")
    await adjust_balance(session, user.id, 20, "тест")
    code, withdrawal = await create_withdrawal(session, user.id, 15, None, "RUB")
    assert code == "ok" and withdrawal is not None
    assert withdrawal.currency == "RUB"
    assert withdrawal.payment_method == "RUB"
    assert withdrawal.status == "pending"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.balance == 20
    assert fresh.reserved_balance == 15
    assert await set_status(session, withdrawal.id, "approved") == "ok"
    assert await set_status(session, withdrawal.id, "completed") == "ok"
    assert await set_status(session, withdrawal.id, "completed") == "bad_status"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.balance == 5
    assert fresh.reserved_balance == 0
    assert fresh.total_withdrawn == 15
