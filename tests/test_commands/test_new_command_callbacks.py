from __future__ import annotations

from types import SimpleNamespace

import pytest

from dm4z_bot.commands.approve import (
    ApprovalView,
    ApproveCommands,
    _notify_game_channel,
    send_mod_notification,
)
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

    async def respond(self, content: str, view: object | None = None, **kwargs: object) -> None:
        self.responses.append((content, view))

    async def defer(self) -> None:
        pass

    async def send(self, content: str, view: object | None = None) -> None:
        self.responses.append((content, view))


class FakeInteraction:
    def __init__(
        self, *, manage_roles: bool = True, user_id: int = 300,
        guild_id: int = 1, client: object | None = None,
    ) -> None:
        perms = SimpleNamespace(manage_roles=manage_roles)
        self.user = SimpleNamespace(id=user_id, mention=f"<@{user_id}>", guild_permissions=perms)
        self.response = self
        self.guild_id = guild_id
        self.client = client or SimpleNamespace(get_channel=lambda _: None)
        self.sent: list[tuple[str, dict]] = []
        self.edited: list[tuple[str, object | None]] = []

    async def send_message(self, content: str, **kwargs: object) -> None:
        self.sent.append((content, kwargs))

    async def edit_message(self, content: str, view: object | None = None, **kwargs: object) -> None:
        self.edited.append((content, view))


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
async def test_link_mod_notification_failure_does_not_break(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 888 WHERE guild_id = 1")

    def bad_get_channel(_cid: int) -> None:
        raise RuntimeError("boom")

    bot = SimpleNamespace(get_channel=bad_get_channel)
    ctx = FakeContext()
    cog = LinkCommands(bot=bot, db=memory_db, registry=_make_registry())
    await LinkCommands.link.callback(cog, ctx, "testgame", "myacc")
    assert "submitted" in ctx.responses[0][0].lower()


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


# --- Approval button tests ---


@pytest.mark.asyncio
async def test_approve_button_no_permission(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")

    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=False)
    await view.approve_button.callback(interaction)

    assert "don't have permission" in interaction.sent[0][0]


@pytest.mark.asyncio
async def test_deny_button_no_permission(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")

    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=False)
    await view.deny_button.callback(interaction)

    assert "don't have permission" in interaction.sent[0][0]


@pytest.mark.asyncio
async def test_approve_button_success(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")

    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=True)
    await view.approve_button.callback(interaction)

    assert "Approved" in interaction.edited[0][0]
    db_row = await memory_db.fetch_one("SELECT status FROM game_accounts WHERE id = ?", (row["id"],))
    assert db_row["status"] == "approved"


@pytest.mark.asyncio
async def test_deny_button_success(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")

    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=True)
    await view.deny_button.callback(interaction)

    assert "Denied" in interaction.edited[0][0]
    db_row = await memory_db.fetch_one("SELECT status FROM game_accounts WHERE id = ?", (row["id"],))
    assert db_row["status"] == "rejected"


@pytest.mark.asyncio
async def test_approve_button_already_handled(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")
    await memory_db.execute("UPDATE game_accounts SET status = 'approved' WHERE id = ?", (row["id"],))

    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=True)
    await view.approve_button.callback(interaction)

    assert "already been handled" in interaction.sent[0][0]


@pytest.mark.asyncio
async def test_deny_button_already_handled(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")
    await memory_db.execute("UPDATE game_accounts SET status = 'rejected' WHERE id = ?", (row["id"],))

    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=True)
    await view.deny_button.callback(interaction)

    assert "already been handled" in interaction.sent[0][0]


# --- send_mod_notification tests ---


class FakeChannel:
    def __init__(self) -> None:
        self.messages: list[tuple[str, object | None]] = []

    async def send(self, content: str, view: object | None = None) -> None:
        self.messages.append((content, view))


@pytest.mark.asyncio
async def test_send_mod_notification_no_guild_row(memory_db: Database) -> None:
    bot = SimpleNamespace(get_channel=lambda _: None)
    await send_mod_notification(bot, memory_db, 1, 200, "testgame", "acc1", 1)


@pytest.mark.asyncio
async def test_send_mod_notification_no_mod_channel_id(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    bot = SimpleNamespace(get_channel=lambda _: None)
    await send_mod_notification(bot, memory_db, 1, 200, "testgame", "acc1", 1)


@pytest.mark.asyncio
async def test_send_mod_notification_channel_not_found(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 999 WHERE guild_id = 1")
    bot = SimpleNamespace(get_channel=lambda _: None)
    await send_mod_notification(bot, memory_db, 1, 200, "testgame", "acc1", 1)


@pytest.mark.asyncio
async def test_send_mod_notification_success(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 888 WHERE guild_id = 1")
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 888 else None)
    await send_mod_notification(bot, memory_db, 1, 200, "testgame", "acc1", 42)
    assert len(channel.messages) == 1
    assert "New link request" in channel.messages[0][0]


# --- _notify_game_channel tests ---


@pytest.mark.asyncio
async def test_notify_game_channel_no_game_row(memory_db: Database) -> None:
    bot = SimpleNamespace(get_channel=lambda _: None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "approved")


@pytest.mark.asyncio
async def test_notify_game_channel_no_channel_id(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id) VALUES (?, ?, NULL)", (1, "testgame"),
    )
    bot = SimpleNamespace(get_channel=lambda _: None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "approved")


@pytest.mark.asyncio
async def test_notify_game_channel_disabled(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 0)",
        (1, "testgame", 555),
    )
    bot = SimpleNamespace(get_channel=lambda _: None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "approved")


@pytest.mark.asyncio
async def test_notify_game_channel_channel_not_found(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1)",
        (1, "testgame", 555),
    )
    bot = SimpleNamespace(get_channel=lambda _: None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "approved")


@pytest.mark.asyncio
async def test_notify_game_channel_approved(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1)",
        (1, "testgame", 555),
    )
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "approved")
    assert len(channel.messages) == 1
    assert "approved" in channel.messages[0][0]
    assert "<@200>" in channel.messages[0][0]


@pytest.mark.asyncio
async def test_notify_game_channel_rejected(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1)",
        (1, "testgame", 555),
    )
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "rejected")
    assert len(channel.messages) == 1
    assert "denied" in channel.messages[0][0].lower()
    assert "<@200>" in channel.messages[0][0]


@pytest.mark.asyncio
async def test_notify_game_channel_send_failure(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1)",
        (1, "testgame", 555),
    )

    class BrokenChannel:
        async def send(self, content: str, **kwargs: object) -> None:
            raise RuntimeError("boom")

    bot = SimpleNamespace(get_channel=lambda cid: BrokenChannel() if cid == 555 else None)
    await _notify_game_channel(bot, memory_db, 1, 200, "testgame", "acc1", "approved")


# --- Button game-channel notification integration tests ---


async def _setup_game_channel(db: Database, guild_id: int = 1, game: str = "testgame") -> FakeChannel:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
    await db.execute(
        "INSERT OR REPLACE INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1)",
        (guild_id, game, 555),
    )
    return FakeChannel()


@pytest.mark.asyncio
async def test_approve_button_notifies_game_channel(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    channel = await _setup_game_channel(memory_db)
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")

    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None)
    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=True, client=bot)
    await view.approve_button.callback(interaction)

    assert len(channel.messages) == 1
    assert "approved" in channel.messages[0][0]
    assert "<@200>" in channel.messages[0][0]


@pytest.mark.asyncio
async def test_deny_button_notifies_game_channel(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    channel = await _setup_game_channel(memory_db)
    row = await memory_db.fetch_one("SELECT id FROM game_accounts WHERE member_id = 200")

    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None)
    view = ApprovalView(memory_db, row["id"], 200, "testgame", "acc1")
    interaction = FakeInteraction(manage_roles=True, client=bot)
    await view.deny_button.callback(interaction)

    assert len(channel.messages) == 1
    assert "denied" in channel.messages[0][0].lower()
    assert "<@200>" in channel.messages[0][0]


# --- Slash command game-channel notification integration tests ---


@pytest.mark.asyncio
async def test_approve_command_notifies_game_channel(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    channel = await _setup_game_channel(memory_db)

    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None)
    ctx = FakeContext(author_id=300)
    member = SimpleNamespace(id=200, mention="<@200>")
    cog = ApproveCommands(bot=bot, db=memory_db)
    await ApproveCommands.approve.callback(cog, ctx, member, "testgame")

    assert len(channel.messages) == 1
    assert "approved" in channel.messages[0][0]
    assert "<@200>" in channel.messages[0][0]


@pytest.mark.asyncio
async def test_reject_command_notifies_game_channel(memory_db: Database) -> None:
    await _insert_pending_account(memory_db, 200, 1, "testgame", "acc1")
    channel = await _setup_game_channel(memory_db)

    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None)
    ctx = FakeContext(author_id=300)
    member = SimpleNamespace(id=200, mention="<@200>")
    cog = ApproveCommands(bot=bot, db=memory_db)
    await ApproveCommands.reject.callback(cog, ctx, member, "testgame")

    assert len(channel.messages) == 1
    assert "denied" in channel.messages[0][0].lower()
    assert "<@200>" in channel.messages[0][0]


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
async def test_set_mod_channel(memory_db: Database) -> None:
    ctx = FakeContext()
    channel = SimpleNamespace(id=777, mention="#mod-channel")
    cog = GuildConfigCommands(bot=SimpleNamespace(), db=memory_db, registry=_make_registry())
    await GuildConfigCommands.set_mod_channel.callback(cog, ctx, channel)
    assert "Moderation channel set" in ctx.responses[0][0]

    row = await memory_db.fetch_one("SELECT mod_channel_id FROM guilds WHERE guild_id = 1")
    assert row["mod_channel_id"] == 777


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
