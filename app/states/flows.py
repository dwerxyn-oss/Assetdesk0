from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SellStates(StatesGroup):
    name = State()
    number = State()
    model = State()
    pattern = State()
    backdrop = State()
    payment = State()


class WithdrawStates(StatesGroup):
    amount = State()
    payout = State()


class AdminUserStates(StatesGroup):
    search = State()
    balance_amount = State()
    balance_comment = State()
    seller_limit = State()


class AdminTaskStates(StatesGroup):
    title = State()
    description = State()
    reward = State()
    task_type = State()
    extra = State()
    max_completions = State()
    edit_value = State()


class AdminRewardStates(StatesGroup):
    title = State()
    description = State()
    cost = State()
    reference = State()
    edit_cost = State()


class AdminSellStates(StatesGroup):
    price = State()
    confirm = State()
    note = State()


class AdminSettingsStates(StatesGroup):
    transfer = State()


class AdminBroadcastStates(StatesGroup):
    text = State()
    confirm = State()
