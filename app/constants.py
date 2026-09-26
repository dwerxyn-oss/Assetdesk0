"""Доменные константы. Денежные суммы — целые числа."""

from __future__ import annotations

TRANSACTION_TASK_REWARD = "task_reward"
TRANSACTION_DAILY_BONUS = "daily_bonus"
TRANSACTION_REFERRAL_REWARD = "referral_reward"
TRANSACTION_WITHDRAWAL = "withdrawal"
TRANSACTION_ADMIN_ADJUSTMENT = "admin_adjustment"
TRANSACTION_OTHER = "other"

TRANSACTION_TYPES = frozenset(
    {
        TRANSACTION_TASK_REWARD,
        TRANSACTION_DAILY_BONUS,
        TRANSACTION_REFERRAL_REWARD,
        TRANSACTION_WITHDRAWAL,
        TRANSACTION_ADMIN_ADJUSTMENT,
        TRANSACTION_OTHER,
    }
)

EARNING_TYPES = frozenset(
    {
        TRANSACTION_TASK_REWARD,
        TRANSACTION_DAILY_BONUS,
        TRANSACTION_REFERRAL_REWARD,
    }
)

TASK_CHANNEL_SUBSCRIPTION = "channel_subscription"
TASK_CHANNEL_OPEN = "channel_open"
TASK_CUSTOM = "custom"
TASK_REFERRAL = "referral"
TASK_PARTNER = "partner"

TASK_TYPES = frozenset(
    {
        TASK_CHANNEL_SUBSCRIPTION,
        TASK_CHANNEL_OPEN,
        TASK_CUSTOM,
        TASK_REFERRAL,
        TASK_PARTNER,
    }
)

CHANNEL_TASK_TYPES = frozenset({TASK_CHANNEL_SUBSCRIPTION})

TIMED_TASK_SECONDS = {
    TASK_CHANNEL_OPEN: 60,
    TASK_PARTNER: 60,
    TASK_CUSTOM: 60,
}

TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_PENDING = "pending"

WITHDRAWAL_PENDING = "pending"
WITHDRAWAL_APPROVED = "approved"
WITHDRAWAL_PROCESSING = "processing"
WITHDRAWAL_COMPLETED = "completed"
WITHDRAWAL_REJECTED = "rejected"
WITHDRAWAL_CANCELLED = "cancelled"

WITHDRAWAL_STATUSES = frozenset(
    {
        WITHDRAWAL_PENDING,
        WITHDRAWAL_APPROVED,
        WITHDRAWAL_PROCESSING,
        WITHDRAWAL_COMPLETED,
        WITHDRAWAL_REJECTED,
        WITHDRAWAL_CANCELLED,
    }
)

WITHDRAWAL_TERMINAL = frozenset(
    {WITHDRAWAL_COMPLETED, WITHDRAWAL_REJECTED, WITHDRAWAL_CANCELLED}
)

WITHDRAWAL_TRANSITIONS: dict[str, frozenset[str]] = {
    WITHDRAWAL_PENDING: frozenset(
        {
            WITHDRAWAL_APPROVED,
            WITHDRAWAL_PROCESSING,
            WITHDRAWAL_REJECTED,
            WITHDRAWAL_CANCELLED,
        }
    ),
    WITHDRAWAL_APPROVED: frozenset(
        {WITHDRAWAL_PROCESSING, WITHDRAWAL_COMPLETED, WITHDRAWAL_REJECTED}
    ),
    WITHDRAWAL_PROCESSING: frozenset({WITHDRAWAL_COMPLETED, WITHDRAWAL_REJECTED}),
    WITHDRAWAL_COMPLETED: frozenset(),
    WITHDRAWAL_REJECTED: frozenset(),
    WITHDRAWAL_CANCELLED: frozenset(),
}

SELL_PENDING = "pending"
SELL_REVIEWING = "reviewing"
SELL_OFFER_SENT = "offer_sent"
SELL_ACCEPTED = "accepted"
SELL_AWAITING_TRANSFER = "awaiting_transfer"
SELL_RECEIVED = "received"
SELL_PAID = "paid"
SELL_COMPLETED = "completed"
SELL_REJECTED = "rejected"
SELL_CANCELLED = "cancelled"

SELL_STATUSES = frozenset(
    {
        SELL_PENDING,
        SELL_REVIEWING,
        SELL_OFFER_SENT,
        SELL_ACCEPTED,
        SELL_AWAITING_TRANSFER,
        SELL_RECEIVED,
        SELL_PAID,
        SELL_COMPLETED,
        SELL_REJECTED,
        SELL_CANCELLED,
    }
)

SELL_TERMINAL = frozenset({SELL_COMPLETED, SELL_REJECTED, SELL_CANCELLED})

SELL_ACTIVE = frozenset(
    {
        SELL_PENDING,
        SELL_REVIEWING,
        SELL_OFFER_SENT,
        SELL_ACCEPTED,
        SELL_AWAITING_TRANSFER,
        SELL_RECEIVED,
        SELL_PAID,
    }
)

# Администратор двигает заявку по шагам. Подтверждение пользователя
# переводит offer_sent сразу в awaiting_transfer.
SELL_TRANSITIONS: dict[str, frozenset[str]] = {
    SELL_PENDING: frozenset(
        {SELL_REVIEWING, SELL_OFFER_SENT, SELL_REJECTED, SELL_CANCELLED}
    ),
    SELL_REVIEWING: frozenset({SELL_OFFER_SENT, SELL_REJECTED, SELL_CANCELLED}),
    SELL_OFFER_SENT: frozenset(
        {SELL_AWAITING_TRANSFER, SELL_REJECTED, SELL_CANCELLED}
    ),
    SELL_ACCEPTED: frozenset({SELL_AWAITING_TRANSFER, SELL_CANCELLED}),
    SELL_AWAITING_TRANSFER: frozenset(
        {SELL_RECEIVED, SELL_COMPLETED, SELL_CANCELLED}
    ),
    SELL_RECEIVED: frozenset({SELL_PAID, SELL_COMPLETED, SELL_CANCELLED}),
    SELL_PAID: frozenset({SELL_COMPLETED}),
    SELL_COMPLETED: frozenset(),
    SELL_REJECTED: frozenset(),
    SELL_CANCELLED: frozenset(),
}

SELLER_NEW = "new"
SELLER_REGULAR = "regular"
SELLER_TRUSTED = "trusted"

SELLER_LEVELS = (SELLER_NEW, SELLER_REGULAR, SELLER_TRUSTED)

SELLER_LEVEL_LABELS = {
    SELLER_NEW: "Новый продавец",
    SELLER_REGULAR: "Постоянный продавец",
    SELLER_TRUSTED: "Доверенный продавец",
}

SELLER_LEVEL_MARKS = {
    SELLER_NEW: "🟡",
    SELLER_REGULAR: "🟠",
    SELLER_TRUSTED: "🟢",
}

PAYMENT_STARS = "stars"
PAYMENT_RUB = "rub"
PAYMENT_CRYPTO = "crypto"
PAYMENT_METHODS = frozenset({PAYMENT_STARS, PAYMENT_RUB, PAYMENT_CRYPTO})

PAYMENT_LABELS = {
    PAYMENT_STARS: "Stars",
    PAYMENT_RUB: "RUB",
    PAYMENT_CRYPTO: "Crypto",
}

PAYOUT_STARS = "STARS"
PAYOUT_RUB = "RUB"
PAYOUT_CRYPTO = "CRYPTO"
PAYOUT_METHODS = frozenset({PAYOUT_STARS, PAYOUT_RUB, PAYOUT_CRYPTO})

PAYOUT_LABELS = {
    PAYOUT_STARS: "Stars",
    PAYOUT_RUB: "Рубли",
    PAYOUT_CRYPTO: "Crypto",
}

TASK_TYPE_LABELS = {
    TASK_CHANNEL_SUBSCRIPTION: "Подписка на канал",
    TASK_CHANNEL_OPEN: "Без проверки · 1 мин",
    TASK_CUSTOM: "Своё условие · 1 мин",
    TASK_REFERRAL: "Рефералы",
    TASK_PARTNER: "Без проверки · 1 мин",
}

WITHDRAWAL_STATUS_LABELS = {
    WITHDRAWAL_PENDING: "На рассмотрении",
    WITHDRAWAL_APPROVED: "Одобрена",
    WITHDRAWAL_PROCESSING: "В обработке",
    WITHDRAWAL_COMPLETED: "Завершена",
    WITHDRAWAL_REJECTED: "Отклонена",
    WITHDRAWAL_CANCELLED: "Отменена",
}

SELL_STATUS_LABELS = {
    SELL_PENDING: "На рассмотрении",
    SELL_REVIEWING: "Проверяем заявку",
    SELL_OFFER_SENT: "Есть предложение",
    SELL_ACCEPTED: "Вы подтвердили",
    SELL_AWAITING_TRANSFER: "Ожидаем передачу подарка",
    SELL_RECEIVED: "NFT получен",
    SELL_PAID: "Оплата отмечена",
    SELL_COMPLETED: "Сделка завершена",
    SELL_REJECTED: "Отклонена",
    SELL_CANCELLED: "Отменена",
}

TRANSACTION_LABELS = {
    TRANSACTION_TASK_REWARD: "Задание",
    TRANSACTION_DAILY_BONUS: "Бонус дня",
    TRANSACTION_REFERRAL_REWARD: "Реферал",
    TRANSACTION_WITHDRAWAL: "Вывод",
    TRANSACTION_ADMIN_ADJUSTMENT: "Корректировка",
    TRANSACTION_OTHER: "Операция",
}

HISTORY_PAGE_SIZE = 8
ADMIN_PAGE_SIZE = 6
META_LAUNCHED_AT = "launched_at"
MAX_MONEY = 1_000_000_000
