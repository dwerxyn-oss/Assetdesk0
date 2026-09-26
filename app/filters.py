from __future__ import annotations

from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app.config import get_settings


def is_admin_id(telegram_id: int) -> bool:
    return telegram_id == get_settings().admin_id


class AdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, event_from_user: User | None = None) -> bool:
        if event_from_user is None:
            return False
        return is_admin_id(event_from_user.id)


class PrivateFilter(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        if isinstance(event, Message):
            return event.chat.type == ChatType.PRIVATE
        if isinstance(event, CallbackQuery):
            message = event.message
            if message is None or not hasattr(message, "chat"):
                return False
            return message.chat.type == ChatType.PRIVATE
        return False
