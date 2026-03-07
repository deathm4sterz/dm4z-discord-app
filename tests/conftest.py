from __future__ import annotations

import pytest

from dm4z_bot.database.db import Database


@pytest.fixture
async def memory_db() -> Database:
    db = Database(":memory:")
    await db.connect()
    yield db
    await db.close()
