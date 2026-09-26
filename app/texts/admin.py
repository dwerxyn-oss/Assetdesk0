"""Тексты админки. Пользователь их не видит."""

from __future__ import annotations

from app.config import get_settings
from app.constants import (
    PAYMENT_LABELS,
    PAYOUT_LABELS,
    SELL_STATUS_LABELS,
    SELLER_LEVEL_LABELS,
    TASK_TYPE_LABELS,
    WITHDRAWAL_STATUS_LABELS,
)
from app.db.models import Reward, SellRequest, Task, User, Withdrawal
from app.services.stats import ServiceStats
from app.utils.money import format_stars, format_usd
from app.utils.text import h
from app.utils.time import format_local


def home() -> str:
    return (
        "<b>Админ-панель</b>\n\n"
        "Заявки, задания и баланс. Выдача наград и сделки с NFT "
        "выполняются вручную, бот их не проводит."
    )


def user_card(user: User) -> str:
    username = f"@{h(user.username)}" if user.username else "без username"
    level = SELLER_LEVEL_LABELS.get(user.seller_level, user.seller_level)
    return (
        "<b>Пользователь</b>\n\n"
        f"{username}\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Имя: {h(user.first_name or '—')}\n"
        f"Регистрация: {format_local(user.registration_date)}\n\n"
        f"Баланс: {format_stars(user.balance)}\n"
        f"В заявках: {format_stars(user.reserved_balance)}\n"
        f"Заработано: {format_stars(user.total_earned)}\n"
        f"Выведено: {format_stars(user.total_withdrawn)}\n\n"
        f"Уровень: {h(level)}\n"
        f"Лимит: {format_usd(user.seller_limit)}\n"
        f"Успешных сделок: {user.successful_deals}\n"
        f"Неуспешных: {user.failed_deals}\n"
        f"Объём USD: {format_usd(user.total_volume)}\n"
        f"Ручная проверка: {'да' if user.manual_verified else 'нет'}\n"
        f"Приглашено: {user.referral_count}\n"
        f"Блокировка: {'да' if user.blocked else 'нет'}"
    )


def task_card(task: Task, completions: int) -> str:
    channel = task.channel_username or task.channel_id or "—"
    state = "архив" if task.archived else ("активно" if task.active else "выключено")
    limit = "без лимита" if task.max_completions == 0 else str(task.max_completions)
    return (
        f"<b>Задание #{task.id}</b>\n\n"
        f"{h(task.title)}\n"
        f"Тип: {h(TASK_TYPE_LABELS.get(task.task_type, task.task_type))}\n"
        f"Награда: {format_stars(task.reward)}\n"
        f"Канал / условие: {h(channel)}\n"
        f"Цель: {h(task.target or '—')}\n"
        f"Выполнено: {completions}\n"
        f"Лимит: {limit}\n"
        f"Статус: {state}\n\n"
        f"{h(task.description or 'Без описания')}"
    )


def withdrawal_card(item: Withdrawal, user: User, reward_title: str | None, reference: str) -> str:
    username = f"@{h(user.username)}" if user.username else h(user.first_name or "—")
    reward = h(reward_title) if reward_title else "без награды из каталога"
    hidden = f"\nСлужебная метка: {h(reference)}" if reference else ""
    note = f"\nЗаметка: {h(item.admin_note)}" if item.admin_note else ""
    method = PAYOUT_LABELS.get(item.payment_method, item.payment_method or "STARS")
    currency = item.currency or "STARS"
    return (
        f"<b>Вывод #{item.id}</b>\n\n"
        f"{username}\nID: <code>{user.telegram_id}</code>\n"
        f"Сумма: {format_stars(item.amount)}\n"
        f"Валюта: {h(currency)}\n"
        f"Способ: {h(method)}\n"
        f"Награда: {reward}{hidden}\n"
        f"Статус: {WITHDRAWAL_STATUS_LABELS.get(item.status, item.status)}\n"
        f"Резерв: {'да' if item.funds_held else 'нет'}\n"
        f"Создана: {format_local(item.created_at)}"
        f"{note}"
    )


def sell_card(request: SellRequest, user: User) -> str:
    username = f"@{h(user.username)}" if user.username else h(user.first_name or "—")
    level = SELLER_LEVEL_LABELS.get(user.seller_level, user.seller_level)
    price = "ещё нет"
    if request.admin_price is not None and request.currency:
        price = f"{request.admin_price} {h(request.currency)}"
    link = f"Ссылка: {h(request.gift_link)}\n" if request.gift_link else ""
    note = h(request.admin_note or "—")
    warning = ""
    if (
        request.admin_price is not None
        and request.currency == "USD"
        and request.admin_price > user.seller_limit
    ):
        warning = f"\n\nЦена выше лимита продавца ({format_usd(user.seller_limit)})."
    return (
        f"<b>Продажа #{request.id}</b>\n\n"
        f"{username}\nID: <code>{user.telegram_id}</code>\n"
        f"Уровень: {h(level)} · лимит {format_usd(user.seller_limit)}\n"
        f"Сделок: {user.successful_deals}\n\n"
        f"Название: {h(request.gift_name)}\n"
        f"Номер: {_gift_number(request)}\n"
        f"Модель: {h(request.gift_model or '—')}\n"
        f"Узор: {h(request.gift_pattern or '—')}\n"
        f"Фон: {h(request.gift_backdrop or '—')}\n"
        f"{link}"
        f"Оплата: {PAYMENT_LABELS.get(request.requested_payment_method, request.requested_payment_method)}\n"
        f"Цена: {price}\n"
        f"Статус: {SELL_STATUS_LABELS.get(request.status, request.status)}\n"
        f"Заметка: {note}"
        f"{warning}"
    )


def reward_card(reward: Reward) -> str:
    state = "активна" if reward.active else "выключена"
    reference = h(reward.gift_reference or "—")
    return (
        f"<b>Награда #{reward.id}</b>\n\n"
        f"{h(reward.title)}\n"
        f"Стоимость: {format_stars(reward.cost_stars)}\n"
        f"Статус: {state}\n"
        f"Служебная метка: {reference}\n\n"
        f"{h(reward.description or 'Без описания')}\n\n"
        "Метка не показывается пользователю. Это не автоматическая отправка NFT."
    )


def _gift_number(request: SellRequest) -> str:
    raw = (request.gift_identifier or "").strip()
    if raw.isdigit():
        return f"#{h(raw)}"
    return h(raw) if raw else "—"


def settings_text(transfer_text: str = "") -> str:
    config = get_settings()
    return (
        "<b>Настройки</b>\n\n"
        "Значения читаются из .env. После изменения перезапустите бота.\n\n"
        f"Бот: @{h(config.bot_username)}\n"
        f"Поддержка: @{h(config.support_username)}\n"
        f"Таймзона: {h(config.timezone)}\n"
        f"Первый вывод: {config.first_withdraw_min} ⭐\n"
        f"Повторный вывод: {config.regular_withdraw_min} ⭐\n"
        f"Бонус дня: {config.daily_bonus} ⭐\n"
        f"Реферальная награда: {config.referral_reward} ⭐\n"
        f"Рефералов в день: {config.referral_daily_limit}\n"
        f"Лимит нового продавца: {format_usd(config.new_seller_limit_usd)}\n"
        f"Постоянный: {format_usd(config.regular_seller_limit_usd)}\n"
        f"Доверенный: {format_usd(config.trusted_seller_limit_usd)}\n\n"
        "Инструкцию передачи можно сменить кнопкой ниже, без перезапуска.\n\n"
        "Инструкция передачи подарка:\n"
        f"{h(transfer_text or '—')}"
    )


def stats_text(stats: ServiceStats) -> str:
    volume = "0"
    if stats.deal_volume:
        volume = ", ".join(f"{amount} {h(currency)}" for currency, amount in sorted(stats.deal_volume.items()))
    return (
        "<b>Статистика</b>\n\n"
        f"Пользователей: {stats.users}\n"
        f"Активны сегодня: {stats.active_today}\n"
        f"Активны за 7 дней: {stats.active_7d}\n"
        f"Выполнено заданий: {stats.tasks_completed}\n"
        f"Начислено наградами: {format_stars(stats.total_rewards)}\n"
        f"Выводов завершено: {stats.withdrawals_completed}\n"
        f"Выводов в ожидании: {stats.withdrawals_pending}\n"
        f"Сумма выводов: {format_stars(stats.withdrawn_stars)}\n"
        f"Сделок с NFT завершено: {stats.completed_deals}\n"
        f"Объём сделок: {volume}"
    )


def sellers_text(counts: dict[str, int]) -> str:
    lines = ["<b>Продавцы</b>", "", "Уровень меняется только вручную.", ""]
    for level, label in SELLER_LEVEL_LABELS.items():
        lines.append(f"{label}: {counts.get(level, 0)}")
    lines.append("\nКарточка продавца открывается через поиск пользователя.")
    return "\n".join(lines)


def balance_help() -> str:
    return (
        "<b>Баланс</b>\n\n"
        "Изменение баланса делается в карточке пользователя. "
        "Каждая правка записывается как admin_adjustment и требует комментарий."
    )


def new_withdrawal(user: User, item: Withdrawal, reward_title: str | None) -> str:
    username = f"@{h(user.username)}" if user.username else h(user.first_name or "пользователь")
    method = PAYOUT_LABELS.get(item.payment_method, item.payment_method or "STARS")
    currency = item.currency or "STARS"
    reward = f"\n🎁 Награда: {h(reward_title)}" if reward_title else ""
    return (
        "<b>🎁 Новая заявка на вывод</b>\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n\n"
        f"💰 Сумма: {format_stars(item.amount)}\n"
        f"💵 Валюта: {h(currency)}\n"
        f"📌 Способ: {h(method)}"
        f"{reward}"
    )


def new_sell(user: User, request: SellRequest) -> str:
    username = f"@{h(user.username)}" if user.username else h(user.first_name or "пользователь")
    level = SELLER_LEVEL_LABELS.get(user.seller_level, user.seller_level)
    pay = PAYMENT_LABELS.get(request.requested_payment_method, request.requested_payment_method)
    return (
        "<b>📦 Новая заявка на выкуп</b>\n\n"
        f"👤 {username}\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n\n"
        "🎁 NFT:\n"
        f"Название: {h(request.gift_name)}\n"
        f"Номер: {_gift_number(request)}\n"
        f"Модель: {h(request.gift_model or '—')}\n"
        f"Узор: {h(request.gift_pattern or '—')}\n"
        f"Фон: {h(request.gift_backdrop or '—')}\n\n"
        "💳 Желаемый способ оплаты:\n"
        f"{h(pay)}\n\n"
        "🛡️ Статус продавца:\n"
        f"{h(level)}\n\n"
        "📊 Сделок:\n"
        f"{user.successful_deals}\n\n"
        "💰 Лимит:\n"
        f"{format_usd(user.seller_limit)}"
    )


def sell_decision(user: User, request: SellRequest, *, accepted: bool) -> str:
    action = "подтвердил предложение" if accepted else "отклонил предложение"
    username = f"@{h(user.username)}" if user.username else str(user.telegram_id)
    return f"Пользователь {username} {action} по заявке #{request.id}."


def offer_preview(request: SellRequest, user: User, price: int, currency: str) -> str:
    warning = "Лимит продавца не превышен."
    if currency == "USD" and price > user.seller_limit:
        warning = (
            f"Сумма выше лимита продавца ({format_usd(user.seller_limit)}). "
            "Отправляйте предложение только если это осознанное решение."
        )
    elif currency != "USD":
        warning = (
            f"Лимит продавца указан в USD ({format_usd(user.seller_limit)}). "
            f"С {h(currency)} бот его сам не сравнивает."
        )
    return (
        f"<b>Предложение по заявке #{request.id}</b>\n\n"
        f"Цена: {price} {h(currency)}\n"
        f"{warning}"
    )
