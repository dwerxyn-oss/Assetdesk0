from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import (
    ADMIN_PAGE_SIZE,
    SELL_AWAITING_TRANSFER,
    SELL_CANCELLED,
    SELL_OFFER_SENT,
    SELL_PAID,
    SELL_PENDING,
    SELL_RECEIVED,
    SELL_REJECTED,
    SELL_REVIEWING,
    SELL_TRANSITIONS,
    SELLER_LEVEL_LABELS,
    WITHDRAWAL_APPROVED,
    WITHDRAWAL_PENDING,
    WITHDRAWAL_PROCESSING,
)
from app.db.models import Reward, SellRequest, Task, User, Withdrawal
from app.keyboards.callbacks import AdminCB, MenuCB
from app.keyboards.common import back, btn, kb


def admin_menu() -> InlineKeyboardMarkup:
    return kb(
        [btn("👥 Пользователи", AdminCB(section="users", action="search"))],
        [btn("📋 Задания", AdminCB(section="task", action="list"))],
        [btn("🎁 Выводы", AdminCB(section="wd", action="list"))],
        [btn("📦 Продажа NFT", AdminCB(section="sell", action="list", item_id=0))],
        [btn("💰 Баланс", AdminCB(section="balance", action="open"))],
        [btn("🎖 Награды", AdminCB(section="reward", action="list"))],
        [btn("📊 Статистика", AdminCB(section="stats", action="open"))],
        [btn("⚙️ Настройки", AdminCB(section="settings", action="open"))],
        [btn("📢 Рассылка", AdminCB(section="bcast", action="start"))],
        [btn("🛡️ Продавцы", AdminCB(section="seller", action="open"))],
        [back(MenuCB(action="main"))],
    )


def user_card_kb(user_id: int, *, blocked: bool, verified: bool) -> InlineKeyboardMarkup:
    block_action = "unblock" if blocked else "block"
    block_label = "Разблокировать" if blocked else "Заблокировать"
    verify_label = "Снять ручную проверку" if verified else "Подтвердить проверку"
    return kb(
        [btn(block_label, AdminCB(section="users", action=block_action, item_id=user_id))],
        [btn("Изменить баланс", AdminCB(section="users", action="bal", item_id=user_id))],
        [btn("История", AdminCB(section="users", action="hist", item_id=user_id))],
        [btn("Уровень продавца", AdminCB(section="users", action="level", item_id=user_id))],
        [btn("Лимит продавца", AdminCB(section="users", action="limit", item_id=user_id))],
        [btn(verify_label, AdminCB(section="users", action="verify", item_id=user_id))],
        [back(AdminCB(section="menu", action="open"))],
    )


def seller_levels_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [btn(label, AdminCB(section="users", action=f"lv_{level}", item_id=user_id))]
        for level, label in SELLER_LEVEL_LABELS.items()
    ]
    rows.append([btn("Лимит по текущему уровню", AdminCB(section="users", action="lvlim", item_id=user_id))])
    rows.append([back(AdminCB(section="users", action="view", item_id=user_id))])
    return kb(*rows)


def task_list_kb(tasks: list[Task], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [btn("Создать задание", AdminCB(section="task", action="new"))]
    ]
    start = page * ADMIN_PAGE_SIZE
    for task in tasks[start : start + ADMIN_PAGE_SIZE]:
        mark = " · архив" if task.archived else ""
        if not task.active and not task.archived:
            mark = " · выкл"
        title = " ".join(task.title.split())[:40]
        rows.append([btn(f"{title}{mark}", AdminCB(section="task", action="view", item_id=task.id))])
    rows.append(_pager("task", "list", page, has_next))
    rows.append([back(AdminCB(section="menu", action="open"))])
    return kb(*rows)


def task_type_kb() -> InlineKeyboardMarkup:
    return kb(
        [btn("Подписка на канал", AdminCB(section="task", action="typ_sub"))],
        [btn("Без проверки · 1 мин", AdminCB(section="task", action="typ_partner"))],
        [btn("Своё условие · 1 мин", AdminCB(section="task", action="typ_custom"))],
        [btn("Рефералы", AdminCB(section="task", action="typ_ref"))],
        [back(AdminCB(section="menu", action="open"))],
    )


def task_card_kb(task: Task) -> InlineKeyboardMarkup:
    toggle = "Выключить" if task.active else "Включить"
    rows = [
        [btn("Название", AdminCB(section="task", action="ed_title", item_id=task.id))],
        [btn("Описание", AdminCB(section="task", action="ed_desc", item_id=task.id))],
        [btn("Награда", AdminCB(section="task", action="ed_reward", item_id=task.id))],
        [btn("Канал или условие", AdminCB(section="task", action="ed_extra", item_id=task.id))],
        [btn("Лимит выполнений", AdminCB(section="task", action="ed_max", item_id=task.id))],
        [btn(toggle, AdminCB(section="task", action="toggle", item_id=task.id))],
    ]
    if task.archived:
        rows.append([btn("Вернуть из архива", AdminCB(section="task", action="unarchive", item_id=task.id))])
    else:
        rows.append([btn("В архив", AdminCB(section="task", action="archive", item_id=task.id))])
    rows.append([btn("Удалить", AdminCB(section="task", action="delete", item_id=task.id))])
    rows.append([back(AdminCB(section="task", action="list"))])
    return kb(*rows)


def withdrawal_list_kb(items: list[Withdrawal], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        rows.append(
            [btn(f"#{item.id} · {item.amount} ⭐", AdminCB(section="wd", action="view", item_id=item.id))]
        )
    rows.append(_pager("wd", "list", page, has_next))
    rows.append([back(AdminCB(section="menu", action="open"))])
    return kb(*rows)


def withdrawal_card_kb(item: Withdrawal, *, user_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if item.status == WITHDRAWAL_PENDING:
        rows.append([btn("Одобрить", AdminCB(section="wd", action="approve", item_id=item.id))])
    if item.status in {WITHDRAWAL_PENDING, WITHDRAWAL_APPROVED}:
        rows.append([btn("В обработку", AdminCB(section="wd", action="process", item_id=item.id))])
    if item.status in {WITHDRAWAL_APPROVED, WITHDRAWAL_PROCESSING}:
        rows.append([btn("Завершить", AdminCB(section="wd", action="askdone", item_id=item.id))])
    if item.status in {WITHDRAWAL_PENDING, WITHDRAWAL_APPROVED, WITHDRAWAL_PROCESSING}:
        rows.append([btn("Отклонить", AdminCB(section="wd", action="askrej", item_id=item.id))])
    rows.append([btn("Профиль", AdminCB(section="users", action="view", item_id=user_id))])
    rows.append([back(AdminCB(section="wd", action="list"))])
    return kb(*rows)


def confirm_kb(section: str, yes_action: str, item_id: int, back_action: str) -> InlineKeyboardMarkup:
    return kb(
        [btn("Подтвердить", AdminCB(section=section, action=yes_action, item_id=item_id))],
        [btn("Назад", AdminCB(section=section, action=back_action, item_id=item_id))],
    )


def sell_list_kb(items: list[SellRequest], *, mode: int, page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            btn("Новые", AdminCB(section="sell", action="list", item_id=0)),
            btn("В работе", AdminCB(section="sell", action="list", item_id=1)),
        ]
    ]
    for item in items:
        name = " ".join(item.gift_name.split())[:24]
        rows.append([btn(f"#{item.id} · {name}", AdminCB(section="sell", action="view", item_id=item.id))])
    rows.append(_pager("sell", "list", page, has_next, item_id=mode))
    rows.append([back(AdminCB(section="menu", action="open"))])
    return kb(*rows)


def sell_card_kb(request: SellRequest, *, user_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if request.status == SELL_PENDING:
        rows.append([btn("В проверку", AdminCB(section="sell", action="review", item_id=request.id))])
    if request.status in {SELL_PENDING, SELL_REVIEWING}:
        rows.append([btn("Указать цену", AdminCB(section="sell", action="price", item_id=request.id))])
    if request.status == SELL_AWAITING_TRANSFER:
        rows.append([btn("NFT получен", AdminCB(section="sell", action="recv", item_id=request.id))])
    if request.status == SELL_RECEIVED:
        rows.append([btn("Оплата отмечена", AdminCB(section="sell", action="paid", item_id=request.id))])
    if request.status in {SELL_AWAITING_TRANSFER, SELL_RECEIVED, SELL_PAID}:
        rows.append([btn("Завершить сделку", AdminCB(section="sell", action="askdone", item_id=request.id))])
    allowed = SELL_TRANSITIONS[request.status]
    if SELL_REJECTED in allowed:
        rows.append([btn("Отклонить", AdminCB(section="sell", action="reject", item_id=request.id))])
    elif SELL_CANCELLED in allowed and request.status != SELL_PAID:
        rows.append([btn("Отменить", AdminCB(section="sell", action="cancel", item_id=request.id))])
    if request.status in {SELL_PENDING, SELL_REVIEWING, SELL_OFFER_SENT, SELL_AWAITING_TRANSFER}:
        rows.append([btn("Неуспешная сделка", AdminCB(section="sell", action="fail", item_id=request.id))])
    rows.append([btn("Заметка", AdminCB(section="sell", action="note", item_id=request.id))])
    rows.append([btn("Профиль", AdminCB(section="users", action="view", item_id=user_id))])
    rows.append([back(AdminCB(section="sell", action="list", item_id=0))])
    return kb(*rows)


def offer_confirm_kb(request_id: int) -> InlineKeyboardMarkup:
    return kb(
        [btn("Отправить предложение", AdminCB(section="sell", action="send", item_id=request_id))],
        [btn("Назад", AdminCB(section="sell", action="view", item_id=request_id))],
    )


def reward_list_kb(rewards: list[Reward]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [btn("Добавить награду", AdminCB(section="reward", action="new"))]
    ]
    for reward in rewards:
        mark = "" if reward.active else " · выкл"
        rows.append(
            [btn(f"{reward.title[:40]}{mark}", AdminCB(section="reward", action="view", item_id=reward.id))]
        )
    rows.append([back(AdminCB(section="menu", action="open"))])
    return kb(*rows)


def reward_card_kb(reward: Reward) -> InlineKeyboardMarkup:
    toggle = "Выключить" if reward.active else "Включить"
    return kb(
        [btn("Изменить стоимость", AdminCB(section="reward", action="cost", item_id=reward.id))],
        [btn(toggle, AdminCB(section="reward", action="toggle", item_id=reward.id))],
        [btn("Удалить", AdminCB(section="reward", action="delete", item_id=reward.id))],
        [back(AdminCB(section="reward", action="list"))],
    )


def new_sell_kb(user: User, request_id: int) -> InlineKeyboardMarkup:
    if user.username:
        contact: InlineKeyboardButton = InlineKeyboardButton(
            text="💬 Связаться",
            url=f"https://t.me/{user.username}",
        )
    else:
        contact = btn("💬 Связаться", AdminCB(section="users", action="view", item_id=user.id))
    return kb(
        [contact],
        [btn("💰 Указать цену", AdminCB(section="sell", action="price", item_id=request_id))],
        [btn("❌ Отклонить", AdminCB(section="sell", action="reject", item_id=request_id))],
    )


def open_record_kb(section: str, item_id: int) -> InlineKeyboardMarkup:
    return kb([btn("Открыть", AdminCB(section=section, action="view", item_id=item_id))])


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return kb(
        [btn("Отправить", AdminCB(section="bcast", action="send"))],
        [back(AdminCB(section="menu", action="open"))],
    )


def _pager(
    section: str,
    action: str,
    page: int,
    has_next: bool,
    *,
    item_id: int = 0,
) -> list[InlineKeyboardButton]:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(btn("◀️", AdminCB(section=section, action=action, item_id=item_id, page=page - 1)))
    if has_next:
        nav.append(btn("▶️", AdminCB(section=section, action=action, item_id=item_id, page=page + 1)))
    return nav
