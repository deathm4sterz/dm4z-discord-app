from __future__ import annotations

from types import SimpleNamespace

import pytest

from dm4z_bot.database.db import Database
from dm4z_bot.events.member_events import MemberEvents


@pytest.mark.asyncio
async def test_on_member_join_inserts_member(memory_db: Database) -> None:
    await memory_db.execute("INSERT INTO guilds (guild_id) VALUES (?)", (1,))

    cog = MemberEvents(bot=SimpleNamespace(), db=memory_db)
    member = SimpleNamespace(id=200, name="User", guild=SimpleNamespace(id=1))
    await cog.on_member_join(member)

    row = await memory_db.fetch_one("SELECT member_id FROM members WHERE member_id = 200 AND guild_id = 1")
    assert row is not None


@pytest.mark.asyncio
async def test_on_member_join_creates_guild_if_missing(memory_db: Database) -> None:
    cog = MemberEvents(bot=SimpleNamespace(), db=memory_db)
    member = SimpleNamespace(id=200, name="User", guild=SimpleNamespace(id=99))
    await cog.on_member_join(member)

    guild_row = await memory_db.fetch_one("SELECT guild_id FROM guilds WHERE guild_id = 99")
    assert guild_row is not None
    member_row = await memory_db.fetch_one("SELECT member_id FROM members WHERE member_id = 200 AND guild_id = 99")
    assert member_row is not None


@pytest.mark.asyncio
async def test_on_member_remove_does_not_crash(memory_db: Database) -> None:
    cog = MemberEvents(bot=SimpleNamespace(), db=memory_db)
    member = SimpleNamespace(id=200, name="User", guild=SimpleNamespace(id=1))
    await cog.on_member_remove(member)


def test_setup_registers_cog() -> None:
    from dm4z_bot.events import member_events

    class FakeBot:
        def __init__(self) -> None:
            self.cogs: list[str] = []
            self.db = Database(":memory:")

        def add_cog(self, cog: object) -> None:
            self.cogs.append(type(cog).__name__)

    bot = FakeBot()
    member_events.setup(bot)  # type: ignore[arg-type]
    assert bot.cogs == ["MemberEvents"]
