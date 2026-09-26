from sqlalchemy import select

from app.constants import SELL_COMPLETED, TRANSACTION_REFERRAL_REWARD
from app.db.models import Transaction, User
from app.services.history import page_for_user
from app.services.sells import create_request, mark_failed, send_offer, set_status, user_decide
from app.services.users import create_user
from app.utils.parsing import parse_gift_number


async def test_sell_deal_is_counted_once(session) -> None:
    user, _ = await create_user(session, telegram_id=70, username="seller", first_name="Seller")
    code, request = await create_request(
        session,
        user_id=user.id,
        gift_name="Desk Gift",
        gift_link="",
        gift_identifier="desk-gift",
        payment_method="crypto",
    )
    assert code == "ok" and request is not None
    other, _ = await create_user(session, telegram_id=71, username="other", first_name="Other")
    assert await user_decide(session, request.id, other.id, accept=True) == "forbidden"
    assert await send_offer(session, request.id, 25, "USD") == "ok"
    assert await user_decide(session, request.id, user.id, accept=True) == "ok"
    assert await set_status(session, request.id, SELL_COMPLETED) == "ok"
    assert await set_status(session, request.id, SELL_COMPLETED) == "bad_status"
    fresh = await session.get(User, user.id)
    assert fresh is not None
    assert fresh.successful_deals == 1
    assert fresh.total_volume == 25
    assert await mark_failed(session, request.id) == "bad_status"


async def test_history_hides_other_users(session) -> None:
    first, _ = await create_user(session, telegram_id=80, username="one", first_name="One")
    second, _ = await create_user(session, telegram_id=81, username="two", first_name="Two")
    await create_request(
        session,
        user_id=first.id,
        gift_name="Secret Gift",
        gift_link="",
        gift_identifier="secret",
        payment_method="stars",
    )
    rows, _pages = await page_for_user(session, second.id, 0)
    assert rows == []
    own, _pages = await page_for_user(session, first.id, 0)
    assert len(own) == 1
    assert "Secret Gift" in own[0].text


async def test_referral_history_has_no_personal_data(session) -> None:
    inviter, _ = await create_user(session, telegram_id=90, username="secretname", first_name="Secret")
    invited, _ = await create_user(
        session,
        telegram_id=91,
        username="friend",
        first_name="Friend",
        referrer_telegram_id=90,
    )
    from app.constants import TASK_CUSTOM
    from app.services.tasks import complete_task, create_task

    task = await create_task(session, title="Шаг", description="", reward=1, task_type=TASK_CUSTOM)
    assert not isinstance(task, str)
    await complete_task(session, invited.id, task.id)
    tx = await session.scalar(
        select(Transaction).where(
            Transaction.user_id == inviter.id,
            Transaction.type == TRANSACTION_REFERRAL_REWARD,
        )
    )
    assert tx is not None
    assert parse_gift_number("#12345") == "12345"
    assert parse_gift_number("12345") == "12345"
    assert parse_gift_number("pepe") is None
    code, request = await create_request(
        session,
        user_id=invited.id,
        gift_name="Plush Pepe",
        gift_link="",
        gift_identifier="12345",
        gift_model="Gold",
        gift_pattern="Stars",
        gift_backdrop="Night",
        payment_method="rub",
    )
    assert code == "ok" and request is not None
    assert request.requested_payment_method == "rub"
    assert request.gift_model == "Gold"
    assert request.status == "pending"
    assert request.admin_price is None
    assert await user_decide(session, request.id, invited.id, accept=True) == "bad_status"
    fresh_request = await session.get(type(request), request.id)
    assert fresh_request is not None
    assert fresh_request.admin_price is None
    assert "secretname" not in tx.description
    assert "friend" not in tx.description
    assert str(invited.telegram_id) not in tx.description
