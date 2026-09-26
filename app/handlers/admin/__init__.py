from __future__ import annotations

from aiogram import Router

from app.filters import AdminFilter, PrivateFilter
from app.handlers.admin import broadcast, menu, rewards, sells, tasks_admin, users, withdrawals

router = Router(name="admin")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())
router.include_router(menu.router)
router.include_router(users.router)
router.include_router(tasks_admin.router)
router.include_router(withdrawals.router)
router.include_router(sells.router)
router.include_router(rewards.router)
router.include_router(broadcast.router)
