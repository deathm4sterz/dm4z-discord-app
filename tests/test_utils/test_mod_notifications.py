from __future__ import annotations

from types import SimpleNamespace

import pytest

from dm4z_bot.database.db import Database
from dm4z_bot.utils.mod_notifications import notify_guild_mod_channel, notify_mod_channels


class FakeChannel:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, content: str) -> None:
        self.messages.append(content)


class BrokenChannel:
    async def send(self, content: str) -> None:
        raise RuntimeError("channel send failed")


@pytest.mark.asyncio
async def test_notify_mod_channels_sends_to_all(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (2,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 200 WHERE guild_id = 2")

    ch1 = FakeChannel()
    ch2 = FakeChannel()
    channels = {100: ch1, 200: ch2}
    bot = SimpleNamespace(get_channel=lambda cid: channels.get(cid))

    await notify_mod_channels(bot, memory_db, "hello all")
    assert ch1.messages == ["hello all"]
    assert ch2.messages == ["hello all"]


@pytest.mark.asyncio
async def test_notify_mod_channels_skips_null(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    bot = SimpleNamespace(get_channel=lambda cid: None)
    await notify_mod_channels(bot, memory_db, "hello")


@pytest.mark.asyncio
async def test_notify_mod_channels_channel_not_found(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 999 WHERE guild_id = 1")
    bot = SimpleNamespace(get_channel=lambda cid: None)
    await notify_mod_channels(bot, memory_db, "hello")


@pytest.mark.asyncio
async def test_notify_mod_channels_send_failure(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    bot = SimpleNamespace(get_channel=lambda cid: BrokenChannel() if cid == 100 else None)
    await notify_mod_channels(bot, memory_db, "hello")


@pytest.mark.asyncio
async def test_notify_guild_mod_channel_success(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    ch = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: ch if cid == 100 else None)
    await notify_guild_mod_channel(bot, memory_db, 1, "guild msg")
    assert ch.messages == ["guild msg"]


@pytest.mark.asyncio
async def test_notify_guild_mod_channel_no_guild(memory_db: Database) -> None:
    bot = SimpleNamespace(get_channel=lambda cid: None)
    await notify_guild_mod_channel(bot, memory_db, 999, "msg")


@pytest.mark.asyncio
async def test_notify_guild_mod_channel_no_mod_channel(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    bot = SimpleNamespace(get_channel=lambda cid: None)
    await notify_guild_mod_channel(bot, memory_db, 1, "msg")


@pytest.mark.asyncio
async def test_notify_guild_mod_channel_not_found(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 999 WHERE guild_id = 1")
    bot = SimpleNamespace(get_channel=lambda cid: None)
    await notify_guild_mod_channel(bot, memory_db, 1, "msg")


@pytest.mark.asyncio
async def test_notify_guild_mod_channel_send_failure(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    bot = SimpleNamespace(get_channel=lambda cid: BrokenChannel() if cid == 100 else None)
    await notify_guild_mod_channel(bot, memory_db, 1, "msg")
