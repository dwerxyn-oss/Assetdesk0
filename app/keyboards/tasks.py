from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import TASK_CHANNEL_SUBSCRIPTION, TASK_PARTNER, TIMED_TASK_SECONDS
from app.db.models import Task
from app.keyboards.callbacks import MenuCB, TaskCB
from app.keyboards.common import back, btn, kb
from app.utils.links import channel_link


def task_list(tasks: list[Task]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for task in tasks:
        title = " ".join(task.title.split())[:60]
        rows.append([btn(title, TaskCB(action="open", task_id=task.id))])
    rows.append([back(MenuCB(action="main"))])
    return kb(*rows)


def task_card(task: Task, *, completed: bool, pending: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not completed and not pending:
        url = channel_link(task.channel_username)
        if task.task_type == TASK_CHANNEL_SUBSCRIPTION and url:
            rows.append([InlineKeyboardButton(text="Подписаться", url=url)])
        elif task.task_type == TASK_PARTNER and task.target.startswith(("http://", "https://")):
            rows.append([InlineKeyboardButton(text="Перейти", url=task.target)])
        if task.task_type in TIMED_TASK_SECONDS:
            rows.append([btn("✅ Готово", TaskCB(action="start", task_id=task.id))])
        else:
            rows.append([btn("Проверить", TaskCB(action="check", task_id=task.id))])
    rows.append([back(MenuCB(action="earn"))])
    return kb(*rows)
