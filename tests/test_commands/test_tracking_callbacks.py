from __future__ import annotations

from types import SimpleNamespace

import pytest

from dm4z_bot.commands.tracking import TrackingCommands
from dm4z_bot.database.db import Database


class FakeContext:
    def __init__(self, guild_id: int = 1, author_id: int = 100) -> None:
        self.guild_id = guild_id
        self.author = SimpleNamespace(id=author_id, mention=f"<@{author_id}>")
        self.responses: list[tuple[str, object | None]] = []

    async def respond(self, content: str, **kwargs: object) -> None:
        self.responses.append((content, None))


class FakeTracker:
    def __init__(self) -> None:
        self.reconnected = False

    async def reconnect(self) -> None:
        self.reconnected = True


async def _setup_approved_account(
    db: Database, member_id: int = 200, guild_id: int = 1,
    game: str = "aoe2", account: str = "12345", display: str = "Player1",
) -> None:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
    await db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (member_id, guild_id))
    await db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status) "
        "VALUES (?, ?, ?, ?, ?, 'approved')",
        (member_id, guild_id, game, account, display),
    )


# --- enable_tracking tests ---


@pytest.mark.asyncio
async def test_enable_tracking_success(memory_db: Database) -> None:
    await _setup_approved_account(memory_db)
    tracker = FakeTracker()
    bot = SimpleNamespace(get_channel=lambda _: None)
    cog = TrackingCommands(bot=bot, db=memory_db, tracker=tracker)
    ctx = FakeContext()
    member = SimpleNamespace(id=200, mention="<@200>")
    await TrackingCommands.enable_tracking.callback(cog, ctx, "aoe2", member)
    assert "tracking enabled" in ctx.responses[0][0].lower()
    assert tracker.reconnected

    row = await memory_db.fetch_one(
        "SELECT tracking FROM game_accounts WHERE member_id = 200 AND guild_id = 1 AND game = 'aoe2'"
    )
    assert row["tracking"] == 1


@pytest.mark.asyncio
async def test_enable_tracking_no_account(memory_db: Database) -> None:
    tracker = FakeTracker()
    bot = SimpleNamespace(get_channel=lambda _: None)
    cog = TrackingCommands(bot=bot, db=memory_db, tracker=tracker)
    ctx = FakeContext()
    member = SimpleNamespace(id=999, mention="<@999>")
    await TrackingCommands.enable_tracking.callback(cog, ctx, "aoe2", member)
    assert "No linked" in ctx.responses[0][0]
    assert not tracker.reconnected


@pytest.mark.asyncio
async def test_enable_tracking_not_approved(memory_db: Database) -> None:
    await db_insert_pending(memory_db)
    tracker = FakeTracker()
    bot = SimpleNamespace(get_channel=lambda _: None)
    cog = TrackingCommands(bot=bot, db=memory_db, tracker=tracker)
    ctx = FakeContext()
    member = SimpleNamespace(id=200, mention="<@200>")
    await TrackingCommands.enable_tracking.callback(cog, ctx, "aoe2", member)
    assert "must be approved" in ctx.responses[0][0].lower()


@pytest.mark.asyncio
async def test_enable_tracking_already_enabled(memory_db: Database) -> None:
    await _setup_approved_account(memory_db)
    await memory_db.execute(
        "UPDATE game_accounts SET tracking = 1 WHERE member_id = 200 AND guild_id = 1 AND game = 'aoe2'"
    )
    tracker = FakeTracker()
    bot = SimpleNamespace(get_channel=lambda _: None)
    cog = TrackingCommands(bot=bot, db=memory_db, tracker=tracker)
    ctx = FakeContext()
    member = SimpleNamespace(id=200, mention="<@200>")
    await TrackingCommands.enable_tracking.callback(cog, ctx, "aoe2", member)
    assert "already enabled" in ctx.responses[0][0].lower()
    assert not tracker.reconnected


# --- disable_tracking tests ---


@pytest.mark.asyncio
async def test_disable_tracking_success(memory_db: Database) -> None:
    await _setup_approved_account(memory_db)
    await memory_db.execute(
        "UPDATE game_accounts SET tracking = 1 WHERE member_id = 200 AND guild_id = 1 AND game = 'aoe2'"
    )
    tracker = FakeTracker()
    bot = SimpleNamespace(get_channel=lambda _: None)
    cog = TrackingCommands(bot=bot, db=memory_db, tracker=tracker)
    ctx = FakeContext()
    member = SimpleNamespace(id=200, mention="<@200>")
    await TrackingCommands.disable_tracking.callback(cog, ctx, "aoe2", member)
    assert "tracking disabled" in ctx.responses[0][0].lower()
    assert tracker.reconnected


@pytest.mark.asyncio
async def test_disable_tracking_not_enabled(memory_db: Database) -> None:
    await _setup_approved_account(memory_db)
    tracker = FakeTracker()
    bot = SimpleNamespace(get_channel=lambda _: None)
    cog = TrackingCommands(bot=bot, db=memory_db, tracker=tracker)
    ctx = FakeContext()
    member = SimpleNamespace(id=200, mention="<@200>")
    await TrackingCommands.disable_tracking.callback(cog, ctx, "aoe2", member)
    assert "was not enabled" in ctx.responses[0][0].lower()
    assert not tracker.reconnected


# --- tracked tests ---


@pytest.mark.asyncio
async def test_tracked_lists_members(memory_db: Database) -> None:
    await _setup_approved_account(memory_db)
    await memory_db.execute(
        "UPDATE game_accounts SET tracking = 1 WHERE member_id = 200 AND guild_id = 1 AND game = 'aoe2'"
    )
    tracker = FakeTracker()
    cog = TrackingCommands(bot=SimpleNamespace(), db=memory_db, tracker=tracker)
    ctx = FakeContext()
    await TrackingCommands.tracked.callback(cog, ctx, None)
    assert "Tracked members" in ctx.responses[0][0]
    assert "<@200>" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_tracked_with_game_filter(memory_db: Database) -> None:
    await _setup_approved_account(memory_db)
    await memory_db.execute(
        "UPDATE game_accounts SET tracking = 1 WHERE member_id = 200 AND guild_id = 1 AND game = 'aoe2'"
    )
    tracker = FakeTracker()
    cog = TrackingCommands(bot=SimpleNamespace(), db=memory_db, tracker=tracker)
    ctx = FakeContext()
    await TrackingCommands.tracked.callback(cog, ctx, "aoe2")
    assert "Tracked members" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_tracked_empty(memory_db: Database) -> None:
    tracker = FakeTracker()
    cog = TrackingCommands(bot=SimpleNamespace(), db=memory_db, tracker=tracker)
    ctx = FakeContext()
    await TrackingCommands.tracked.callback(cog, ctx, None)
    assert "No members" in ctx.responses[0][0]


# --- helpers ---


async def db_insert_pending(db: Database) -> None:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (200, 1))
    await db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        (200, 1, "aoe2", "12345", "Player1"),
    )
