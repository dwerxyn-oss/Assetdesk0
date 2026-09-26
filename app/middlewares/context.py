from __future__ import annotations

from aiogram import F
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.filters import is_admin_id
from app.services.users import create_user, get_by_telegram_id, touch


def is_private(event: TelegramObject) -> bool:
    if isinstance(event, Message):
        return event.chat.type == ChatType.PRIVATE
    if isinstance(event, CallbackQuery):
        message = event.message
        if message is None or not hasattr(message, "chat"):
            return False
        return message.chat.type == ChatType.PRIVATE
    return False


class DbSessionMiddleware:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if not is_private(event):
            return None
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware:
    async def __call__(self, handler, event: TelegramObject, data: dict):
        tg_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession = data["session"]
        user: User | None = None
        if tg_user is not None and not tg_user.is_bot:
            user = await get_by_telegram_id(session, tg_user.id)
            if user is not None:
                await touch(session, user, tg_user.username, tg_user.first_name or "")
        data["db_user"] = user
        data["is_admin"] = bool(tg_user and is_admin_id(tg_user.id))
        return await handler(event, data)


class BlockedMiddleware:
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user: User | None = data.get("db_user")
        if user is not None and user.blocked and not data.get("is_admin"):
            support = get_settings().support_username
            text = f"Аккаунт ограничен. Если это ошибка, напишите @{support}."
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return None
        return await handler(event, data)


async def ensure_user(session: AsyncSession, tg_user: TgUser, db_user: User | None) -> User:
    if db_user is not None:
        return db_user
    user, _ = await create_user(
        session,
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name or "",
    )
    return user


PLAIN_TEXT = F.text & ~F.text.startswith("/")
