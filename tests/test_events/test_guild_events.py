from __future__ import annotations

from types import SimpleNamespace

import pytest

from dm4z_bot.database.db import Database
from dm4z_bot.events.guild_events import GuildEvents


@pytest.mark.asyncio
async def test_on_guild_join_inserts_guild(memory_db: Database) -> None:
    cog = GuildEvents(bot=SimpleNamespace(), db=memory_db)
    guild = SimpleNamespace(id=42, name="TestGuild")
    await cog.on_guild_join(guild)

    row = await memory_db.fetch_one("SELECT guild_id FROM guilds WHERE guild_id = 42")
    assert row is not None
    assert row["guild_id"] == 42


@pytest.mark.asyncio
async def test_on_guild_join_idempotent(memory_db: Database) -> None:
    cog = GuildEvents(bot=SimpleNamespace(), db=memory_db)
    guild = SimpleNamespace(id=42, name="TestGuild")
    await cog.on_guild_join(guild)
    await cog.on_guild_join(guild)

    rows = await memory_db.fetch_all("SELECT guild_id FROM guilds WHERE guild_id = 42")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_on_guild_remove_does_not_crash(memory_db: Database) -> None:
    cog = GuildEvents(bot=SimpleNamespace(), db=memory_db)
    guild = SimpleNamespace(id=42, name="TestGuild")
    await cog.on_guild_remove(guild)


def test_setup_registers_cog() -> None:
    from dm4z_bot.events import guild_events

    class FakeBot:
        def __init__(self) -> None:
            self.cogs: list[str] = []
            self.db = Database(":memory:")

        def add_cog(self, cog: object) -> None:
            self.cogs.append(type(cog).__name__)

    bot = FakeBot()
    guild_events.setup(bot)  # type: ignore[arg-type]
    assert bot.cogs == ["GuildEvents"]
