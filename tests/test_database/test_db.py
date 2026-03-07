from __future__ import annotations

import pytest

from dm4z_bot.database.db import Database


@pytest.mark.asyncio
async def test_connect_creates_tables() -> None:
    db = Database(":memory:")
    await db.connect()
    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [t["name"] for t in tables]
    assert "guilds" in table_names
    assert "guild_games" in table_names
    assert "members" in table_names
    assert "game_accounts" in table_names
    assert "game_stats" in table_names
    assert "command_usage" in table_names
    assert "schema_version" in table_names
    await db.close()


@pytest.mark.asyncio
async def test_execute_and_fetch_one() -> None:
    db = Database(":memory:")
    await db.connect()
    await db.execute("INSERT INTO guilds (guild_id) VALUES (?)", (123,))
    row = await db.fetch_one("SELECT guild_id FROM guilds WHERE guild_id = ?", (123,))
    assert row is not None
    assert row["guild_id"] == 123
    await db.close()


@pytest.mark.asyncio
async def test_fetch_one_returns_none() -> None:
    db = Database(":memory:")
    await db.connect()
    row = await db.fetch_one("SELECT guild_id FROM guilds WHERE guild_id = ?", (999,))
    assert row is None
    await db.close()


@pytest.mark.asyncio
async def test_fetch_all_returns_list() -> None:
    db = Database(":memory:")
    await db.connect()
    await db.execute("INSERT INTO guilds (guild_id) VALUES (?)", (1,))
    await db.execute("INSERT INTO guilds (guild_id) VALUES (?)", (2,))
    rows = await db.fetch_all("SELECT guild_id FROM guilds ORDER BY guild_id")
    assert len(rows) == 2
    assert rows[0]["guild_id"] == 1
    assert rows[1]["guild_id"] == 2
    await db.close()


@pytest.mark.asyncio
async def test_conn_property_raises_when_not_connected() -> None:
    db = Database(":memory:")
    with pytest.raises(RuntimeError, match="Database not connected"):
        _ = db.conn


@pytest.mark.asyncio
async def test_close_when_not_connected() -> None:
    db = Database(":memory:")
    await db.close()


@pytest.mark.asyncio
async def test_migrations_are_idempotent() -> None:
    db = Database(":memory:")
    await db.connect()
    version_before = await db.fetch_one("SELECT MAX(version) as v FROM schema_version")
    await db.close()

    db2 = Database(":memory:")
    await db2.connect()
    version_after = await db2.fetch_one("SELECT MAX(version) as v FROM schema_version")
    assert version_before["v"] == version_after["v"]
    await db2.close()


@pytest.mark.asyncio
async def test_double_connect_skips_applied_migrations() -> None:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(path)
        await db.connect()
        await db.close()

        db2 = Database(path)
        await db2.connect()
        tables = await db2.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        assert "guilds" in [t["name"] for t in tables]
        await db2.close()
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_foreign_keys_enabled() -> None:
    db = Database(":memory:")
    await db.connect()
    row = await db.fetch_one("PRAGMA foreign_keys")
    assert row is not None
    assert list(row.values())[0] == 1
    await db.close()
