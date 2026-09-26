from __future__ import annotations

from aiogram import Dispatcher, Router

from app.filters import PrivateFilter
from app.handlers import balance, earn, fallback, help, history, referral, sell, start, withdraw
from app.handlers.admin import router as admin_router

public_router = Router(name="public")
public_router.message.filter(PrivateFilter())
public_router.callback_query.filter(PrivateFilter())
public_router.include_router(start.router)
public_router.include_router(earn.router)
public_router.include_router(balance.router)
public_router.include_router(withdraw.router)
public_router.include_router(referral.router)
public_router.include_router(sell.router)
public_router.include_router(history.router)
public_router.include_router(help.router)
public_router.include_router(fallback.router)


def setup_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(admin_router)
    dispatcher.include_router(public_router)
