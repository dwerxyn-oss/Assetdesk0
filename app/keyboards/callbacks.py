from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="m"):
    action: str


class TaskCB(CallbackData, prefix="t"):
    action: str
    task_id: int


class WithdrawCB(CallbackData, prefix="w"):
    action: str
    item_id: int = 0


class SellCB(CallbackData, prefix="s"):
    action: str
    item_id: int = 0


class HistCB(CallbackData, prefix="h"):
    page: int


class HelpCB(CallbackData, prefix="hp"):
    topic: str


class AdminCB(CallbackData, prefix="a"):
    section: str
    action: str
    item_id: int = 0
    page: int = 0
