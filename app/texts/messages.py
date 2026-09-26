"""Тексты для пользователя. Короткие, без обещаний, которых бот не выполняет."""

from __future__ import annotations

from app.config import get_settings
from app.constants import (
    CHANNEL_TASK_TYPES,
    PAYMENT_LABELS,
    PAYOUT_LABELS,
    SELL_STATUS_LABELS,
    SELLER_LEVEL_LABELS,
    SELLER_LEVEL_MARKS,
    TASK_REFERRAL,
    TIMED_TASK_SECONDS,
    WITHDRAWAL_STATUS_LABELS,
)
from app.db.models import SellRequest, Task, User
from app.services.history import HistoryRow, render_rows
from app.services.stats import ServiceStats
from app.services.withdrawals import minimum_for
from app.utils.links import referral_link
from app.utils.money import format_quote, format_stars, format_usd
from app.utils.text import h
from app.utils.time import format_local_date


def trust_line(user: User) -> str:
    mark = SELLER_LEVEL_MARKS.get(user.seller_level, "🟡")
    label = SELLER_LEVEL_LABELS.get(user.seller_level, user.seller_level)
    return f"{mark} {h(label)}"


def welcome(user: User) -> str:
    return (
        f"Баланс: {format_stars(user.balance)}\n\n"
        "Выполняйте задания, получайте награды или направляйте их на награды.\n\n"
        f"{trust_line(user)}\n"
        "Выберите действие снизу"
    )


def balance_text(user: User) -> str:
    lines = [
        "<b>💎 Ваш баланс</b>",
        "",
        f"⭐ Сейчас: {format_stars(user.balance)}",
        f"📈 Заработано: {format_stars(user.total_earned)}",
        f"🎁 Выведено: {format_stars(user.total_withdrawn)}",
    ]
    if user.reserved_balance:
        lines.append(f"В заявках: {format_stars(user.reserved_balance)}")
    lines.extend(["", "Выберите действие:"])
    return "\n".join(lines)


def seller_block(user: User) -> str:
    return (
        f"{trust_line(user)}\n"
        f"{user.successful_deals} сделок · лимит {format_usd(user.seller_limit)}"
    )


def earn_text(tasks_exist: bool) -> str:
    if not tasks_exist:
        return "Сейчас заданий нет."
    return "Выберите задание."


def daily_screen(amount: int, *, claimed: bool) -> str:
    if amount <= 0:
        return "<b>🎁 Бонус дня</b>\n\nСейчас бонус не начисляется."
    if claimed:
        return "<b>🎁 Бонус дня</b>\n\nБонус за сегодня уже получен.\nСледующий будет доступен завтра."
    return (
        "<b>🎁 Бонус дня</b>\n\n"
        f"Сегодня вам доступно: +{format_stars(amount)}\n\n"
        "Получайте бонус раз в день."
    )


def task_text(task: Task, *, completed: bool, qualified: int | None = None, pending: bool = False) -> str:
    lines = [f"<b>{h(task.title)}</b>", f"+ {format_stars(task.reward)}"]
    if task.description:
        lines.extend(["", h(task.description)])
    if task.task_type == TASK_REFERRAL:
        needed = task.target.strip() or "1"
        current = 0 if qualified is None else qualified
        lines.extend(["", f"Прогресс: {current}/{h(needed)}"])
    lines.append("")
    delay = TIMED_TASK_SECONDS.get(task.task_type)
    if completed:
        lines.append("Статус: выполнено.")
    elif pending:
        lines.append("Награда будет зачислена.")
    elif task.task_type in CHANNEL_TASK_TYPES:
        lines.append("Подпишитесь на канал и нажмите «Проверить».")
    elif task.task_type == TASK_REFERRAL:
        lines.append("Когда условие выполнено, нажмите «Проверить».")
    elif delay:
        lines.append("Подпишитесь и нажмите «Готово». Награда будет зачислена.")
    else:
        lines.append("После выполнения нажмите «Проверить».")
    return "\n".join(lines)


def daily_result(code: str, amount: int) -> str:
    if code == "ok":
        return f"Бонус начислен: +{format_stars(amount)}.\nСледующий будет доступен завтра."
    if code == "already":
        return "Бонус за сегодня уже получен.\nСледующий будет доступен завтра."
    if code == "disabled":
        return "Сейчас бонус не начисляется."
    return "Не получилось начислить бонус. Попробуйте позже."


def referral_text(*, invited: int, earned: int, telegram_id: int) -> str:
    settings = get_settings()
    link = referral_link(telegram_id)
    return (
        "<b>👥 Пригласить друзей</b>\n\n"
        f"Приглашено: {invited}\n"
        f"Заработано: {format_stars(earned)}\n\n"
        "Ваша ссылка:\n"
        f"<code>{h(link)}</code>\n\n"
        f"{format_stars(settings.referral_reward)} за первый заход человека по этой ссылке.\n"
        f"В день учитывается до {settings.referral_daily_limit} человек."
    )


def withdraw_text(user: User, *, has_rewards: bool) -> str:
    available = user.balance - user.reserved_balance
    minimum = minimum_for(user)
    first = user.total_withdrawn <= 0
    minimum_line = (
        f"Минимальная сумма первого вывода — {format_stars(minimum)}."
        if first
        else f"Минимальная сумма вывода — {format_stars(minimum)}."
    )
    lines = [
        "<b>🎁 Вывод</b>",
        "",
        f"Доступно: {format_stars(available)}",
        "",
        minimum_line,
    ]
    if available < minimum:
        lines.extend(["", f"Не хватает {format_stars(minimum - available)}."])
    elif has_rewards:
        lines.extend(["", "Выберите подходящую награду:"])
    else:
        lines.extend(["", "Можно указать сумму и способ выплаты."])
    return "\n".join(lines)


def withdraw_payout_text(amount: int) -> str:
    return (
        "<b>Способ выплаты</b>\n\n"
        f"Сумма: {format_stars(amount)}\n\n"
        "Выберите вариант:"
    )


def withdrawal_created(withdrawal_id: int, amount: int, payout: str) -> str:
    label = PAYOUT_LABELS.get(payout, payout)
    return (
        f"Заявка #{withdrawal_id} на {format_stars(amount)} создана.\n"
        f"Способ: {h(label)}.\n\n"
        "Сумма зарезервирована до завершения или отмены заявки."
    )


def withdrawal_status_text(withdrawal_id: int, status: str, amount: int) -> str:
    label = WITHDRAWAL_STATUS_LABELS.get(status, status)
    extra = {
        "approved": "Заявка взята в работу.",
        "processing": "Заявка в обработке.",
        "rejected": "Сумма снова доступна на балансе.",
        "cancelled": "Сумма снова доступна на балансе.",
        "completed": "Заявка завершена. Сумма списана с баланса.",
    }.get(status, "")
    text = f"Заявка на вывод #{withdrawal_id}\n{format_stars(amount)} · {label}"
    if extra:
        text = f"{text}\n\n{extra}"
    return text


def my_withdrawals_text(lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "Заявок пока нет."
    return f"<b>Мои заявки на вывод</b>\n\n{body}"


def sell_text(user: User, active: SellRequest | None) -> str:
    parts = [seller_block(user), "", "Сначала цена, потом передача."]
    if active is not None:
        parts.extend(["", active_sell_summary(active)])
    return "\n".join(parts)


def active_sell_summary(request: SellRequest) -> str:
    label = SELL_STATUS_LABELS.get(request.status, request.status)
    number = gift_number(request)
    lines = [
        f"Заявка #{request.id}",
        f"NFT: {h(request.gift_name)}",
        f"Номер: {number}",
        f"Оплата: {PAYMENT_LABELS.get(request.requested_payment_method, request.requested_payment_method)}",
        f"Статус: {label}",
    ]
    if request.admin_price is not None and request.currency:
        lines.append(f"Предложение: {format_quote(request.admin_price, request.currency)}")
    return "\n".join(lines)


def gift_number(request: SellRequest) -> str:
    raw = (request.gift_identifier or "").strip()
    if raw.isdigit():
        return f"#{h(raw)}"
    return h(raw) if raw else "—"


def sell_step_name() -> str:
    return (
        "<b>1/5</b>\n"
        "Введите название NFT.\n\n"
        "Например:\n"
        "Plush Pepe\n"
        "Durov's Cap\n"
        "Toy Bear"
    )


def sell_step_number() -> str:
    return (
        "<b>2/5</b>\n"
        "Введите уникальный номер NFT.\n\n"
        "Это номер после символа #.\n\n"
        "Например:\n"
        "#12345"
    )


def sell_step_model() -> str:
    return "<b>3/5</b>\nУкажите модель NFT."


def sell_step_pattern() -> str:
    return "<b>4/5</b>\nУкажите узор NFT."


def sell_step_backdrop() -> str:
    return "<b>5/5</b>\nУкажите фон NFT."


def sell_summary(data: dict[str, str]) -> str:
    return (
        "<b>📦 Данные NFT</b>\n\n"
        f"Название: {h(data['gift_name'])}\n"
        f"Номер: #{h(data['gift_number'])}\n"
        f"Модель: {h(data['gift_model'])}\n"
        f"Узор: {h(data['gift_pattern'])}\n"
        f"Фон: {h(data['gift_backdrop'])}\n\n"
        "Выберите способ оплаты:"
    )


def sell_sent(request_id: int) -> str:
    return (
        f"Заявка #{request_id} принята.\n\n"
        "Цену пришлём после проверки.\n"
        "Передавать NFT нужно только после вашего согласия."
    )


def sell_offer(request: SellRequest) -> str:
    price = "—"
    if request.admin_price is not None and request.currency:
        price = format_quote(request.admin_price, request.currency)
    return (
        "<b>📦 Оценка готова</b>\n\n"
        f"NFT: {h(request.gift_name)}\n"
        f"{gift_number(request)}\n\n"
        "Предложенная цена:\n"
        f"💰 {price}\n\n"
        "Если условия подходят, подтвердите сделку."
    )


def offer_accepted(request_id: int) -> str:
    return (
        "<b>✅ Цена принята.</b>\n\n"
        "Дальше — передача NFT.\n"
        "Сначала откройте инструкцию и сверьтесь с реквизитами.\n\n"
        f"Заявка #{request_id}"
    )


def transfer_guide(body: str) -> str:
    return f"<b>📨 Инструкция по передаче</b>\n\n{h(body)}"


def sell_user_notice(request: SellRequest) -> str | None:
    if request.status in {"offer_sent", "awaiting_transfer"}:
        return None
    if request.status == "reviewing":
        return f"Заявка #{request.id} принята в проверку."
    if request.status == "received":
        return f"По заявке #{request.id} NFT получен. Дальше — оплата."
    if request.status == "paid":
        return f"По заявке #{request.id} отмечен этап оплаты. Сделка ещё не закрыта."
    if request.status == "completed":
        return f"Заявка #{request.id} завершена."
    if request.status == "rejected":
        return f"Заявка #{request.id} отклонена."
    if request.status == "cancelled":
        return f"Заявка #{request.id} отменена."
    return None


def history_text(rows: list[HistoryRow], page: int, pages: int) -> str:
    return (
        "<b>История</b>\n\n"
        f"{render_rows(rows)}\n\n"
        f"Страница {page + 1} из {pages}"
    )


def help_text(telegram_id: int) -> str:
    return (
        "<b>❓ Помощь</b>\n\n"
        f"Ваш ID: <code>{telegram_id}</code>\n\n"
        "Выберите вопрос:"
    )


def faq_text(topic: str) -> str:
    settings = get_settings()
    answers = {
        "earn": (
            "Как заработать?",
            "Откройте «Заработать», выполните задание и нажмите «Проверить». "
            "Награда за одно задание начисляется один раз. "
            "Раз в день доступен бонус.",
        ),
        "reward": (
            "Как получить награду?",
            "Откройте «Вывести», выберите награду или сумму и способ выплаты. "
            "Заявка закрывается после фактической выдачи.",
        ),
        "out": (
            "Как работает вывод?",
            f"Первая заявка — от {format_stars(settings.first_withdraw_min)}, "
            f"следующая — от {format_stars(settings.regular_withdraw_min)}. "
            "Сумма резервируется, пока заявка открыта, и списывается один раз при завершении. "
            "Доступны Stars, рубли и crypto.",
        ),
        "gift": (
            "Как продать NFT?",
            "Откройте «Продать NFT» и заполните название, номер, модель, узор и фон. "
            "Сначала придёт цена. Передавать NFT нужно только после согласия с ней.",
        ),
        "lim": (
            "Почему у новых продавцов есть лимит?",
            f"Первая сделка — до {format_usd(settings.new_seller_limit_usd)}. "
            "Это долларовый ориентир, не рубли. Сам лимит не растёт.",
        ),
        "lvl": (
            "Как увеличить лимит?",
            "Лимит увеличивают после успешных сделок. "
            "Сам по себе он не меняется.",
        ),
        "err": (
            "Куда обратиться по вопросу?",
            "Напишите в поддержку и укажите ваш ID из этого раздела. "
            "Если заявка уже создана, добавьте её номер.",
        ),
    }
    title, body = answers.get(topic, ("Помощь", "Раздел не найден. Вернитесь в меню помощи."))
    return f"<b>{title}</b>\n\n{body}\n\nЕсли не нашли ответ — напишите в поддержку."


def about_text(stats: ServiceStats) -> str:
    launched = format_local_date(stats.launched_at)
    volume = "0"
    if stats.deal_volume:
        volume = ", ".join(f"{amount} {h(currency)}" for currency, amount in sorted(stats.deal_volume.items()))
    return (
        "<b>ℹ️ О AssetDesk</b>\n\n"
        "AssetDesk — задания, награды и выкуп NFT.\n\n"
        "Stars копятся за задания. NFT продаётся по заявке: сначала цена, потом передача.\n\n"
        "Историю операций и условия можно посмотреть в соответствующих разделах.\n\n"
        f"Запуск: {launched}\n"
        f"Пользователей: {stats.users}\n"
        f"Завершённых сделок: {stats.completed_deals}\n"
        f"Объём сделок: {volume}\n"
        f"Успешных выводов: {stats.withdrawals_completed}\n"
        f"Выплачено: {format_stars(stats.withdrawn_stars)}"
    )
