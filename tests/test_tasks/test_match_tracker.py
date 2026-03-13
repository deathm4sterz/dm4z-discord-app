from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api
from dm4z_bot.services.aoe2_websocket import Aoe2WebSocket, MatchEvent
from dm4z_bot.tasks.match_tracker import MatchTracker

SAMPLE_MATCH_DATA = {
    "matchId": 462419759,
    "started": "2026-03-12T08:19:43.000Z",
    "finished": None,
    "leaderboardName": "Team Random Map",
    "gameModeName": "Random Map",
    "mapName": "MegaRandom",
    "mapImageUrl": "https://example.com/megarandom.png",
    "server": "centralindia",
    "averageRating": 1255,
    "players": [
        {
            "profileId": 1228227,
            "name": "hjpotter92",
            "rating": 1315,
            "civ": "sicilians",
            "civName": "Sicilians",
            "civImageUrl": "https://example.com/sicilians.png",
            "color": 2,
            "colorHex": "#FF0000",
            "team": 1,
            "teamName": "Team 1",
            "country": "in",
        },
        {
            "profileId": 17771111,
            "name": "Opponent",
            "rating": 1225,
            "civ": "mongols",
            "civName": "Mongols",
            "civImageUrl": "https://example.com/mongols.png",
            "color": 1,
            "colorHex": "#405BFF",
            "team": 2,
            "teamName": "Team 2",
            "country": "bd",
        },
    ],
}


async def _setup_tracking(db: Database) -> None:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    await db.execute(
        "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1)",
        (1, "aoe2", 555),
    )
    await db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (100, 1))
    await db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status, tracking) "
        "VALUES (?, ?, ?, ?, ?, 'approved', 1)",
        (100, 1, "aoe2", "1228227", "hjpotter92"),
    )


class FakeMessage:
    def __init__(self, message_id: int = 999) -> None:
        self.id = message_id

    async def edit(self, **kwargs: object) -> None:
        self.edited_kwargs = kwargs


class FakeChannel:
    def __init__(self, channel_id: int = 555) -> None:
        self.id = channel_id
        self.messages: list[object] = []
        self._message = FakeMessage()

    async def send(self, content: str | None = None, **kwargs: object) -> FakeMessage:
        self.messages.append(content or kwargs)
        return self._message

    async def fetch_message(self, message_id: int) -> FakeMessage:
        return self._message


@pytest.mark.asyncio
async def test_get_tracked_profiles(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    profiles = await tracker._get_tracked_profiles()
    assert len(profiles) == 1
    assert profiles[0]["account_identifier"] == "1228227"


@pytest.mark.asyncio
async def test_get_tracked_profiles_empty(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    profiles = await tracker._get_tracked_profiles()
    assert profiles == []


@pytest.mark.asyncio
async def test_get_guild_tracking_counts(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    counts = await tracker._get_guild_tracking_counts()
    assert counts == {1: 1}


@pytest.mark.asyncio
async def test_resolve_match_guilds(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    result = await tracker._resolve_match_guilds(["1228227"])
    assert 1 in result
    assert "1228227" in result[1]["tracked_ids"]
    assert result[1]["member_map"]["1228227"] == 100
    assert result[1]["channel_id"] == 555


@pytest.mark.asyncio
async def test_resolve_match_guilds_empty(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    result = await tracker._resolve_match_guilds([])
    assert result == {}


@pytest.mark.asyncio
async def test_resolve_match_guilds_no_matches(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    result = await tracker._resolve_match_guilds(["99999"])
    assert result == {}


@pytest.mark.asyncio
async def test_handle_match_added(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._handle_match_added(SAMPLE_MATCH_DATA)
    assert len(channel.messages) == 1

    row = await memory_db.fetch_one(
        "SELECT match_id, status FROM tracked_matches WHERE match_id = '462419759'"
    )
    assert row is not None
    assert row["status"] == "active"


@pytest.mark.asyncio
async def test_handle_match_added_no_guilds(memory_db: Database) -> None:
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._handle_match_added(SAMPLE_MATCH_DATA)


@pytest.mark.asyncio
async def test_handle_match_added_channel_not_found(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._handle_match_added(SAMPLE_MATCH_DATA)


@pytest.mark.asyncio
async def test_handle_match_removed(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None, emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_match = AsyncMock(return_value={
        "finished": "2026-03-12T08:55:00.000Z",
        "players": [
            {"profileId": 1228227, "team": 1, "won": True},
            {"profileId": 17771111, "team": 2, "won": False},
        ],
    })
    api.fetch_text = AsyncMock()

    tracker = MatchTracker(bot=bot, db=memory_db, api=api)

    # First add the match
    await tracker._handle_match_added(SAMPLE_MATCH_DATA)

    # Then remove it
    await tracker._handle_match_removed(462419759)

    row = await memory_db.fetch_one(
        "SELECT status FROM tracked_matches WHERE match_id = '462419759'"
    )
    assert row["status"] == "finished"


@pytest.mark.asyncio
async def test_handle_match_removed_no_tracked(memory_db: Database) -> None:
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._handle_match_removed(999999)


@pytest.mark.asyncio
async def test_handle_match_removed_channel_not_found(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())

    await tracker._handle_match_added(SAMPLE_MATCH_DATA)

    bot_no_channel = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker.bot = bot_no_channel
    await tracker._handle_match_removed(462419759)


@pytest.mark.asyncio
async def test_fetch_match_result_success(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_match = AsyncMock(return_value={"finished": "2026-03-12T09:00:00.000Z", "players": []})
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)
    result = await tracker._fetch_match_result(123)
    assert result is not None
    assert result["finished"] == "2026-03-12T09:00:00.000Z"


@pytest.mark.asyncio
async def test_fetch_match_result_retry(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_match = AsyncMock(side_effect=[
        {"finished": None},
        {"finished": "2026-03-12T09:00:00.000Z", "players": []},
    ])
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)
    with patch("dm4z_bot.tasks.match_tracker.asyncio.sleep", new_callable=AsyncMock):
        result = await tracker._fetch_match_result(123)
    assert result is not None


@pytest.mark.asyncio
async def test_fetch_match_result_failure(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_match = AsyncMock(side_effect=Exception("API error"))
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)
    result = await tracker._fetch_match_result(123)
    assert result is None


@pytest.mark.asyncio
async def test_trigger_analysis(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_text = AsyncMock()
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)
    tracker._trigger_analysis(462419759)
    await asyncio.sleep(0.05)
    api.fetch_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_and_stop(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    tracker.start()
    assert tracker._task is not None
    tracker.stop()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_reconnect(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker.reconnect()
    assert tracker._reconnect_event.is_set()


@pytest.mark.asyncio
async def test_notify_per_guild(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    ch = FakeChannel(channel_id=100)
    bot = SimpleNamespace(get_channel=lambda cid: ch if cid == 100 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._notify_per_guild("Monitoring {n} player(s).")
    assert len(ch.messages) == 1
    assert "1 player" in ch.messages[0]


@pytest.mark.asyncio
async def test_notify_per_guild_no_counts(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._notify_per_guild("Monitoring {n} player(s).")


@pytest.mark.asyncio
async def test_notify_per_guild_channel_not_found(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._notify_per_guild("Monitoring {n} player(s).")


@pytest.mark.asyncio
async def test_notify_per_guild_send_failure(memory_db: Database) -> None:
    await _setup_tracking(memory_db)

    class BrokenChannel:
        async def send(self, content: str) -> None:
            raise RuntimeError("send failed")

    bot = SimpleNamespace(get_channel=lambda cid: BrokenChannel() if cid == 100 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._notify_per_guild("Monitoring {n} player(s).")


@pytest.mark.asyncio
async def test_notify_tracking_status(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    ch = FakeChannel(channel_id=100)
    bot = SimpleNamespace(get_channel=lambda cid: ch if cid == 100 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._notify_tracking_status("Tracking {n} player(s).")
    assert len(ch.messages) >= 1


@pytest.mark.asyncio
async def test_handle_match_added_send_failure(memory_db: Database) -> None:
    await _setup_tracking(memory_db)

    class BrokenSendChannel:
        async def send(self, content: str | None = None, **kwargs: object) -> None:
            raise RuntimeError("send failed")

    bot = SimpleNamespace(get_channel=lambda cid: BrokenSendChannel() if cid == 555 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._handle_match_added(SAMPLE_MATCH_DATA)
    row = await memory_db.fetch_one("SELECT id FROM tracked_matches WHERE match_id = '462419759'")
    assert row is None


@pytest.mark.asyncio
async def test_handle_match_removed_edit_failure(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    channel = FakeChannel()
    bot = SimpleNamespace(get_channel=lambda cid: channel if cid == 555 else None, emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_match = AsyncMock(return_value={"finished": "2026-03-12T08:55:00.000Z", "players": []})
    api.fetch_text = AsyncMock()
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)
    await tracker._handle_match_added(SAMPLE_MATCH_DATA)

    class BrokenEditChannel:
        async def send(self, content: str | None = None, **kwargs: object) -> None:
            pass

        async def fetch_message(self, message_id: int) -> None:
            raise RuntimeError("fetch failed")

    tracker.bot = SimpleNamespace(
        get_channel=lambda cid: BrokenEditChannel() if cid == 555 else None, emoji_cache={},
    )
    await tracker._handle_match_removed(462419759)


@pytest.mark.asyncio
async def test_trigger_analysis_failure(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_text = AsyncMock(side_effect=Exception("analysis fail"))
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)
    tracker._trigger_analysis(462419759)
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_consume_events(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    ch = FakeChannel(channel_id=100)
    game_ch = FakeChannel(channel_id=555)

    def get_channel(cid: int) -> FakeChannel | None:
        if cid == 100:
            return ch
        if cid == 555:
            return game_ch
        return None

    bot = SimpleNamespace(get_channel=get_channel, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())

    events = [
        MatchEvent(type="__connected__", data={"profile_count": 1}),
        MatchEvent(type="__disconnected__", data={}),
        MatchEvent(type="matchAdded", data=SAMPLE_MATCH_DATA),
        MatchEvent(type="unknownType", data={}),
    ]

    async def fake_listen():
        for e in events:
            yield e

    tracker._ws.listen = fake_listen
    await tracker._consume_events()


@pytest.mark.asyncio
async def test_run_no_profiles_then_reconnect(memory_db: Database) -> None:
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())

    call_count = 0

    async def mock_get_profiles():
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return []
        tracker.stop()
        return []

    tracker._get_tracked_profiles = mock_get_profiles

    async def trigger_reconnect():
        await asyncio.sleep(0.05)
        tracker._reconnect_event.set()

    asyncio.create_task(trigger_reconnect())

    try:
        await asyncio.wait_for(tracker._run(), timeout=1.0)
    except (TimeoutError, asyncio.CancelledError):
        pass


@pytest.mark.asyncio
async def test_run_with_profiles_reconnect(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    ch = FakeChannel(channel_id=100)
    bot = SimpleNamespace(get_channel=lambda cid: ch if cid == 100 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())

    run_count = 0

    async def fake_listen():
        nonlocal run_count
        run_count += 1
        yield MatchEvent(type="__connected__", data={"profile_count": 1})
        if run_count >= 2:
            tracker.stop()
            return
        await asyncio.sleep(10)

    async def patched_run():
        profiles = await tracker._get_tracked_profiles()
        profile_ids = list({p["account_identifier"] for p in profiles})
        tracker._ws = Aoe2WebSocket(profile_ids=profile_ids)
        tracker._ws.listen = fake_listen
        tracker._reconnect_event.clear()

        listen_task = asyncio.ensure_future(tracker._consume_events())
        reconnect_task = asyncio.ensure_future(tracker._reconnect_event.wait())

        await asyncio.sleep(0.05)
        tracker._reconnect_event.set()

        done, pending = await asyncio.wait(
            {listen_task, reconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await tracker._ws.close()

    try:
        await asyncio.wait_for(patched_run(), timeout=2.0)
    except (TimeoutError, asyncio.CancelledError):
        pass


@pytest.mark.asyncio
async def test_consume_events_match_removed(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    ch = FakeChannel(channel_id=555)
    bot = SimpleNamespace(get_channel=lambda cid: ch if cid == 555 else None, emoji_cache={})
    api = MagicMock(spec=Aoe2Api)
    api.fetch_match = AsyncMock(return_value=None)
    api.fetch_text = AsyncMock()
    tracker = MatchTracker(bot=bot, db=memory_db, api=api)

    events_list = [
        MatchEvent(type="matchAdded", data=SAMPLE_MATCH_DATA),
        MatchEvent(type="matchRemoved", data={"matchId": 462419759}),
    ]

    async def fake_listen():
        for e in events_list:
            yield e

    tracker._ws.listen = fake_listen
    await tracker._consume_events()


@pytest.mark.asyncio
async def test_run_listen_ends_restarts(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())

    consume_count = 0

    async def mock_consume():
        nonlocal consume_count
        consume_count += 1
        if consume_count >= 2:
            raise asyncio.CancelledError

    tracker._consume_events = mock_consume
    tracker._notify_per_guild = AsyncMock()

    try:
        await asyncio.wait_for(tracker._run(), timeout=1.0)
    except (asyncio.CancelledError, TimeoutError):
        pass

    assert consume_count >= 2


@pytest.mark.asyncio
async def test_run_reconnect_path(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    bot = SimpleNamespace(get_channel=lambda cid: None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())

    async def mock_consume():
        await asyncio.sleep(10)

    tracker._consume_events = mock_consume
    tracker._notify_per_guild = AsyncMock()

    async def trigger_reconnect():
        await asyncio.sleep(0.05)
        tracker._reconnect_event.set()
        await asyncio.sleep(0.1)
        tracker.stop()

    asyncio.create_task(trigger_reconnect())

    try:
        await asyncio.wait_for(tracker._run(), timeout=2.0)
    except (asyncio.CancelledError, TimeoutError):
        pass

    tracker._notify_per_guild.assert_awaited()


@pytest.mark.asyncio
async def test_start_when_task_done(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    tracker.start()
    task = tracker._task
    tracker.stop()
    await asyncio.sleep(0.05)
    assert task.done()
    tracker.start()
    assert tracker._task is not task
    tracker.stop()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_resolve_match_guilds_multiple_profiles_same_guild(memory_db: Database) -> None:
    await _setup_tracking(memory_db)
    await memory_db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (200, 1))
    await memory_db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status, tracking) "
        "VALUES (?, ?, ?, ?, ?, 'approved', 1)",
        (200, 1, "aoe2", "17771111", "OpponentPlayer"),
    )
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    result = await tracker._resolve_match_guilds(["1228227", "17771111"])
    assert 1 in result
    assert len(result[1]["tracked_ids"]) == 2


@pytest.mark.asyncio
async def test_start_noop_when_running(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    tracker.start()
    first_task = tracker._task
    tracker.start()
    assert tracker._task is first_task
    tracker.stop()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_stop_already_stopped(memory_db: Database) -> None:
    bot = SimpleNamespace(emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    tracker.stop()


@pytest.mark.asyncio
async def test_notify_tracking_status_no_counts(memory_db: Database) -> None:
    await memory_db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await memory_db.execute("UPDATE guilds SET mod_channel_id = 100 WHERE guild_id = 1")
    ch = FakeChannel(channel_id=100)
    bot = SimpleNamespace(get_channel=lambda cid: ch if cid == 100 else None, emoji_cache={})
    tracker = MatchTracker(bot=bot, db=memory_db, api=Aoe2Api())
    await tracker._notify_tracking_status("Tracking {n} player(s).")
