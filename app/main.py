from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent

from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory, init_db
from app.handlers import setup_routers
from app.logging_setup import setup_logging
from app.middlewares.context import BlockedMiddleware, DbSessionMiddleware, UserMiddleware
from app.services.notify import send_user
from app.services.tasks import settle_due_tasks

logger = logging.getLogger(__name__)


def build_dispatcher(session_factory) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.middleware(DbSessionMiddleware(session_factory))
        observer.middleware(UserMiddleware())
        observer.middleware(BlockedMiddleware())
    setup_routers(dispatcher)
    dispatcher.errors.register(on_error)
    return dispatcher


async def on_error(event: ErrorEvent) -> None:
    logger.exception("unhandled error", exc_info=event.exception)
    text = "Не получилось выполнить действие. Попробуйте ещё раз."
    try:
        if event.update.callback_query is not None:
            await event.update.callback_query.answer(text, show_alert=True)
        elif event.update.message is not None:
            await event.update.message.answer(text)
    except Exception:
        logger.exception("failed to report the error to the user")


async def setup_commands(bot: Bot, settings: Settings) -> None:
    common = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(common)
    try:
        await bot.set_my_commands(
            [*common, BotCommand(command="admin", description="Админ-панель")],
            scope=BotCommandScopeChat(chat_id=settings.admin_id),
        )
    except Exception:
        logger.exception("admin commands were not set")


async def _reward_loop(bot: Bot, session_factory) -> None:
    while True:
        try:
            async with session_factory() as session:
                notices = await settle_due_tasks(session)
            for telegram_id, text in notices:
                await send_user(bot, telegram_id, text)
        except Exception:
            logger.exception("timed task rewards failed")
        await asyncio.sleep(2)


async def run(settings: Settings) -> None:
    setup_logging()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await init_db(engine, session_factory)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    dispatcher = build_dispatcher(session_factory)
    rewards = asyncio.create_task(_reward_loop(bot, session_factory))
    logger.info(
        "AssetDesk starting admin_id=%s timezone=%s",
        settings.admin_id,
        settings.timezone,
    )
    try:
        await setup_commands(bot, settings)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        rewards.cancel()
        with suppress(asyncio.CancelledError):
            await rewards
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    settings = get_settings()
    settings.assert_runtime()
    asyncio.run(run(settings))
