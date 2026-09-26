from __future__ import annotations

import asyncio

db_write_lock = asyncio.Lock()
