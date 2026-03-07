from __future__ import annotations

from types import SimpleNamespace

import pytest

from dm4z_bot.commands.approve import ApproveCommands
from dm4z_bot.commands.guild_config import GuildConfigCommands
from dm4z_bot.commands.link import LinkCommands
from dm4z_bot.commands.profile import ProfileCommands
from dm4z_bot.commands.stats import StatsCommands
from dm4z_bot.database.db import Database
from dm4z_bot.services.games.registry import GameRegistry


class FakeContext:
    def __init__(self, guild_id: int = 1, author_id: int = 100) -> None:
        self.guild_id = guild_id
        self.author = SimpleNamespace(id=author_id)
        self.responses: list[tuple[str, object | None]] = []
        self.followup = self

    async def respond(self, content: str, view: object | None = None) -> None:
        self.responses.append((content, view))

    async def defer(self) -> None:
        pass

    async def send(self, content: str, view: object | None = None) -> None:
        self.responses.append((content, view))


class FakeService:
    game_key = "testgame"
    display_name = "Test Game"

    async def fetch_stats(self, account_identifier: str) -> dict:
        return {"score": 42}

    async def validate_account(self, account_identifier: str) -> str | None:
        if account_identifier == "invalid":
            return None
        return f"Display_{account_identifier}"


class FailValidateService:
    game_key = "failgame"
    display_name = "Fail Game"

    async def fetch_stats(self, account_identifier: str) -> dict:
        return {}

    async def validate_account(self, account_identifier: str) -> str | None:
        return None


def _make_registry() -> GameRegistry:
    reg = GameRegistry()
    reg.register(FakeService())
    return reg


# --- Link command tests ---


@pytest.mark.asyncio
async def test_link_unknown_game(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = LinkCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await LinkCommands.link.callback(cog, ctx, "nope", "acc")
    assert "Unknown game" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_link_invalid_account(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = LinkCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await LinkCommands.link.callback(cog, ctx, "testgame", "invalid")
    assert "Could not validate" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_link_success_creates_pending(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = LinkCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await LinkCommands.link.callback(cog, ctx, "testgame", "myacc")
    assert "submitted" in ctx.responses[0][0].lower()

    row = await memory_db.fetch_one(
        "SELECT status FROM game_accounts WHERE member_id = ? AND guild_id = ? AND game = ?",
        (100, 1, "testgame"),
    )
    assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_link_updates_existing(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = LinkCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await LinkCommands.link.callback(cog, ctx, "testgame", "acc1")
    await LinkCommands.link.callback(cog, ctx, "testgame", "acc2")

    row = await memory_db.fetch_one(
        "SELECT account_identifier FROM game_accounts WHERE member_id = ? AND guild_id = ? AND game = ?",
        (100, 1, "testgame"),
    )
    assert row["account_identifier"] == "acc2"


@pytest.mark.asyncio
async def test_unlink_success(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = LinkCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await LinkCommands.link.callback(cog, ctx, "testgame", "myacc")

    ctx2 = FakeContext()
    await LinkCommands.unlink.callback(cog, ctx2, "testgame")
    assert "Unlinked" in ctx2.responses[0][0]


@pytest.mark.asyncio
async def test_unlink_not_found(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = LinkCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await LinkCommands.unlink.callback(cog, ctx, "testgame")
    assert "No linked" in ctx.responses[0][0]


# --- Approve command tests ---


@pytest.mark.asyncio
async def test_approve_success(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")

    ctx = FakeContext(author_id=300)
    member = SimpleNamespace(id=200, mention="<@200>")
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.approve.callback(cog, ctx, member, "testgame")
    assert "Approved" in ctx.responses[0][0]

    row = await memory_db.fetch_one(
        "SELECT status, reviewed_by FROM game_accounts WHERE member_id = 200 AND guild_id = 1 AND game = 'testgame'"
    )
    assert row["status"] == "approved"
    assert row["reviewed_by"] == 300


@pytest.mark.asyncio
async def test_approve_no_request(memory_db: Database) -> None:
    ctx = FakeContext()
    member = SimpleNamespace(id=999, mention="<@999>")
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.approve.callback(cog, ctx, member, "testgame")
    assert "No link request" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_approve_already_approved(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    await memory_db.execute(
        "UPDATE game_accounts SET status = 'approved' WHERE member_id = 200 AND guild_id = 1 AND game = 'testgame'"
    )

    ctx = FakeContext()
    member = SimpleNamespace(id=200, mention="<@200>")
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.approve.callback(cog, ctx, member, "testgame")
    assert "already approved" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_reject_success(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")

    ctx = FakeContext(author_id=300)
    member = SimpleNamespace(id=200, mention="<@200>")
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.reject.callback(cog, ctx, member, "testgame")
    assert "Rejected" in ctx.responses[0][0]

    row = await memory_db.fetch_one(
        "SELECT status FROM game_accounts WHERE member_id = 200 AND guild_id = 1 AND game = 'testgame'"
    )
    assert row["status"] == "rejected"


@pytest.mark.asyncio
async def test_reject_no_request(memory_db: Database) -> None:
    ctx = FakeContext()
    member = SimpleNamespace(id=999, mention="<@999>")
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.reject.callback(cog, ctx, member, "testgame")
    assert "No link request" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_pending_lists_requests(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    await _insert_pending_account(memory_db, 201, 1, "testgame", "acc2")

    ctx = FakeContext()
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.pending.callback(cog, ctx, None)
    assert "Pending link requests" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_pending_with_game_filter(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")

    ctx = FakeContext()
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.pending.callback(cog, ctx, "testgame")
    assert "Pending link requests" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_pending_empty(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = ApproveCommands(bot=SimpleNamespace(), db=memory_db)
    await ApproveCommands.pending.callback(cog, ctx, None)
    assert "No pending" in ctx.responses[0][0]


# --- Profile command tests ---


@pytest.mark.asyncio
async def test_profile_no_accounts(memory_db: Database) -> None:
    ctx = FakeContext()
    ctx.author = SimpleNamespace(id=100, mention="<@100>")
    cog = ProfileCommands(bot=SimpleNamespace(), db=memory_db)
    await ProfileCommands.profile.callback(cog, ctx, None)
    assert "no approved" in ctx.responses[0][0].lower()


@pytest.mark.asyncio
async def test_profile_with_accounts(memory_db: Database) -> None:
    await _insert_approved_account(memory_db, 100, 1, "testgame", "acc1", "Display1")
    await memory_db.execute(
        "INSERT INTO game_stats (game_account_id, stats_json) VALUES (?, ?)",
        (1, '{"score": 42}'),
    )

    ctx = FakeContext()
    target = SimpleNamespace(id=100, mention="<@100>")
    cog = ProfileCommands(bot=SimpleNamespace(), db=memory_db)
    await ProfileCommands.profile.callback(cog, ctx, target)
    assert "Profile for" in ctx.responses[0][0]
    assert "score: 42" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_profile_no_stats(memory_db: Database) -> None:
    await _insert_approved_account(memory_db, 100, 1, "testgame", "acc1", "Display1")

    ctx = FakeContext()
    target = SimpleNamespace(id=100, mention="<@100>")
    cog = ProfileCommands(bot=SimpleNamespace(), db=memory_db)
    await ProfileCommands.profile.callback(cog, ctx, target)
    assert "Profile for" in ctx.responses[0][0]
    assert "testgame" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_profile_with_all_none_stats(memory_db: Database) -> None:
    await _insert_approved_account(memory_db, 100, 1, "testgame", "acc1", "Display1")
    await memory_db.execute(
        "INSERT INTO game_stats (game_account_id, stats_json) VALUES (?, ?)",
        (1, '{"score": null}'),
    )

    ctx = FakeContext()
    target = SimpleNamespace(id=100, mention="<@100>")
    cog = ProfileCommands(bot=SimpleNamespace(), db=memory_db)
    await ProfileCommands.profile.callback(cog, ctx, target)
    assert "Profile for" in ctx.responses[0][0]
    assert "—" not in ctx.responses[0][0]


# --- Stats command tests ---


@pytest.mark.asyncio
async def test_stats_no_account(memory_db: Database) -> None:
    ctx = FakeContext()
    ctx.author = SimpleNamespace(id=100, mention="<@100>")
    cog = StatsCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await StatsCommands.stats.callback(cog, ctx, "testgame", None)
    assert "No approved" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_stats_no_data_yet(memory_db: Database) -> None:
    await _insert_approved_account(memory_db, 100, 1, "testgame", "acc1", "Disp")

    ctx = FakeContext()
    target = SimpleNamespace(id=100, mention="<@100>")
    cog = StatsCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await StatsCommands.stats.callback(cog, ctx, "testgame", target)
    assert "No data yet" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_stats_with_data(memory_db: Database) -> None:
    await _insert_approved_account(memory_db, 100, 1, "testgame", "acc1", "Disp")
    await memory_db.execute(
        "INSERT INTO game_stats (game_account_id, stats_json) VALUES (?, ?)",
        (1, '{"score": 99}'),
    )

    ctx = FakeContext()
    target = SimpleNamespace(id=100, mention="<@100>")
    cog = StatsCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await StatsCommands.stats.callback(cog, ctx, "testgame", target)
    assert "score" in ctx.responses[0][0]
    assert "99" in ctx.responses[0][0]


# --- Guild config command tests ---


@pytest.mark.asyncio
async def test_enable_game_success(memory_db: Database) -> None:
    ctx = FakeContext()
    channel = SimpleNamespace(id=555, mention="#channel")
    cog = GuildConfigCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await GuildConfigCommands.enable_game.callback(cog, ctx, "testgame", channel)
    assert "enabled" in ctx.responses[0][0].lower()

    row = await memory_db.fetch_one(
        "SELECT channel_id, enabled FROM guild_games WHERE guild_id = 1 AND game = 'testgame'"
    )
    assert row["channel_id"] == 555
    assert row["enabled"] == 1


@pytest.mark.asyncio
async def test_enable_game_unknown(memory_db: Database) -> None:
    ctx = FakeContext()
    channel = SimpleNamespace(id=555, mention="#channel")
    cog = GuildConfigCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await GuildConfigCommands.enable_game.callback(cog, ctx, "nope", channel)
    assert "Unknown game" in ctx.responses[0][0]


@pytest.mark.asyncio
async def test_disable_game_success(memory_db: Database) -> None:
    ctx = FakeContext()
    channel = SimpleNamespace(id=555, mention="#channel")
    cog = GuildConfigCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await GuildConfigCommands.enable_game.callback(cog, ctx, "testgame", channel)

    ctx2 = FakeContext()
    await GuildConfigCommands.disable_game.callback(cog, ctx2, "testgame")
    assert "disabled" in ctx2.responses[0][0].lower()


@pytest.mark.asyncio
async def test_disable_game_not_enabled(memory_db: Database) -> None:
    ctx = FakeContext()
    cog = GuildConfigCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await GuildConfigCommands.disable_game.callback(cog, ctx, "testgame")
    assert "was not enabled" in ctx.responses[0][0]


# --- Helpers ---


async def _insert_pending_account(
    db: Database, member_id: int, guild_id: int, game: str, account_id: str
) -> None:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
    await db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (member_id, guild_id))
    await db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        (member_id, guild_id, game, account_id, account_id),
    )


async def _insert_approved_account(
    db: Database, member_id: int, guild_id: int, game: str, account_id: str, display_name: str
) -> None:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
    await db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (member_id, guild_id))
    await db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status) "
        "VALUES (?, ?, ?, ?, ?, 'approved')",
        (member_id, guild_id, game, account_id, display_name),
    )
