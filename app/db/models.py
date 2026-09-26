"""Модели SQLite. Баланс и цены хранятся целыми числами."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.time import utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_users_balance_nonneg"),
        CheckConstraint("reserved_balance >= 0", name="ck_users_reserved_nonneg"),
        CheckConstraint(
            "reserved_balance <= balance", name="ck_users_reserved_le_balance"
        ),
        CheckConstraint("total_earned >= 0", name="ck_users_earned_nonneg"),
        CheckConstraint("total_withdrawn >= 0", name="ck_users_withdrawn_nonneg"),
        CheckConstraint("seller_limit >= 0", name="ck_users_seller_limit_nonneg"),
        CheckConstraint("successful_deals >= 0", name="ck_users_deals_nonneg"),
        CheckConstraint("failed_deals >= 0", name="ck_users_failed_nonneg"),
        CheckConstraint("total_volume >= 0", name="ck_users_volume_nonneg"),
        CheckConstraint("referral_count >= 0", name="ck_users_refs_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    reserved_balance: Mapped[int] = mapped_column(Integer, default=0)
    referred_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    referral_reward_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    total_earned: Mapped[int] = mapped_column(Integer, default=0)
    total_withdrawn: Mapped[int] = mapped_column(Integer, default=0)
    successful_deals: Mapped[int] = mapped_column(Integer, default=0)
    failed_deals: Mapped[int] = mapped_column(Integer, default=0)
    total_volume: Mapped[int] = mapped_column(Integer, default=0)
    seller_limit: Mapped[int] = mapped_column(Integer, default=0)
    seller_level: Mapped[str] = mapped_column(String(32), default="new")
    manual_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_daily_bonus: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    referrer: Mapped[User | None] = relationship(remote_side=[id])
    transactions: Mapped[list[Transaction]] = relationship(back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="transactions")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    reward: Mapped[int] = mapped_column(Integer)
    task_type: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(300), default="")
    channel_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    max_completions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint("reward >= 0", name="ck_tasks_reward_nonneg"),
        CheckConstraint("max_completions >= 0", name="ck_tasks_max_nonneg"),
    )


class UserTask(Base):
    __tablename__ = "user_tasks"
    __table_args__ = (UniqueConstraint("user_id", "task_id", name="uq_user_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    reward_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Reward(Base):
    __tablename__ = "rewards"
    __table_args__ = (CheckConstraint("cost_stars > 0", name="ck_rewards_cost_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    cost_stars: Mapped[int] = mapped_column(Integer)
    gift_reference: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_withdrawals_amount_positive"),
        Index("ix_withdrawals_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reward_id: Mapped[int | None] = mapped_column(ForeignKey("rewards.id"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(16), default="STARS")
    payment_method: Mapped[str] = mapped_column(String(16), default="STARS")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    funds_held: Mapped[bool] = mapped_column(Boolean, default=True)
    admin_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SellRequest(Base):
    __tablename__ = "sell_requests"
    __table_args__ = (Index("ix_sell_requests_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    gift_name: Mapped[str] = mapped_column(String(200))
    gift_link: Mapped[str] = mapped_column(String(500), default="")
    gift_identifier: Mapped[str] = mapped_column(String(500), default="")
    gift_model: Mapped[str] = mapped_column(String(200), default="")
    gift_pattern: Mapped[str] = mapped_column(String(200), default="")
    gift_backdrop: Mapped[str] = mapped_column(String(200), default="")
    requested_payment_method: Mapped[str] = mapped_column(String(16))
    admin_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    stats_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
