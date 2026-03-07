from __future__ import annotations

import logging
from types import SimpleNamespace

import discord
import pytest

from dm4z_bot.bot import COMMAND_EXTENSIONS, EVENT_EXTENSIONS, Dm4zBot
from dm4z_bot.config import Settings


def _make_settings(**overrides: object) -> Settings:
    defaults = {
        "discord_token": "fake_token",
        "log_level": "INFO",
        "debug_guild_id": None,
        "database_path": ":memory:",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _make_bot(settings: Settings | None = None) -> Dm4zBot:
    s = settings or _make_settings()
    return Dm4zBot(s)


@pytest.mark.asyncio
async def test_setup_hook_loads_all_extensions(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    loaded: list[str] = []
    bot = _make_bot()
    monkeypatch.setattr(bot, "load_extension", loaded.append)
    monkeypatch.setattr(bot.db, "connect", lambda: _async_noop())

    async def successful_sync():
        return ["cmd1", "cmd2"]

    monkeypatch.setattr(bot, "sync_commands", successful_sync)
    monkeypatch.setattr(bot.stat_fetcher, "start", lambda: None)
    with caplog.at_level(logging.INFO):
        await bot.setup_hook()
    assert loaded == [*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS]
    assert "Synced 2 command(s)" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_logs_when_user_available(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = _make_bot()
    bot._connection.user = SimpleNamespace(name="dm4z")
    bot._setup_complete = True
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    assert "Logged in as dm4z" in caplog.text
    assert "Bot is ready! Loaded" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_no_user_does_not_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = _make_bot()
    bot._connection.user = None
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    assert "Logged in as" not in caplog.text
    assert "Bot is ready!" not in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_logs_sync_error(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = _make_bot()
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    monkeypatch.setattr(bot.db, "connect", lambda: _async_noop())
    monkeypatch.setattr(bot.stat_fetcher, "start", lambda: None)

    async def failing_sync():
        raise Exception("Sync failed")

    monkeypatch.setattr(bot, "sync_commands", failing_sync)
    with caplog.at_level(logging.ERROR):
        await bot.setup_hook()
    assert "Failed to sync commands: Sync failed" in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_handles_none_sync_result(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = _make_bot()
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    monkeypatch.setattr(bot.db, "connect", lambda: _async_noop())
    monkeypatch.setattr(bot.stat_fetcher, "start", lambda: None)

    async def none_sync():
        return None

    monkeypatch.setattr(bot, "sync_commands", none_sync)
    monkeypatch.setattr(
        type(bot), "pending_application_commands", property(lambda self: [])
    )

    with caplog.at_level(logging.INFO):
        await bot.setup_hook()
    assert "Command sync completed (no commands to sync)" in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_logs_extension_loading(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = _make_bot()
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    monkeypatch.setattr(bot.db, "connect", lambda: _async_noop())
    monkeypatch.setattr(bot.stat_fetcher, "start", lambda: None)
    monkeypatch.setattr(bot, "sync_commands", lambda: [])
    monkeypatch.setattr(
        type(bot), "pending_application_commands", property(lambda self: [])
    )

    with caplog.at_level(logging.INFO):
        await bot.setup_hook()

    expected_count = len(COMMAND_EXTENSIONS) + len(EVENT_EXTENSIONS)
    assert f"Loading {expected_count} extensions..." in caplog.text
    assert "Extensions loaded. Pending commands: 0" in caplog.text


@pytest.mark.asyncio
async def test_bot_debug_mode_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        _make_bot(_make_settings(debug_guild_id=123456789))
    assert "Debug mode enabled for guild: 123456789" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_calls_setup_if_not_complete(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = _make_bot()
    bot._connection.user = SimpleNamespace(name="dm4z")
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    monkeypatch.setattr(bot.db, "connect", lambda: _async_noop())
    monkeypatch.setattr(bot.stat_fetcher, "start", lambda: None)

    async def mock_sync():
        return []

    monkeypatch.setattr(bot, "sync_commands", mock_sync)
    monkeypatch.setattr(
        type(bot), "pending_application_commands", property(lambda self: [])
    )

    bot._setup_complete = False

    with caplog.at_level(logging.WARNING):
        await bot.on_ready()

    assert "Setup not completed - running setup_hook manually" in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_handles_extension_load_failure(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = _make_bot()
    monkeypatch.setattr(bot.db, "connect", lambda: _async_noop())
    monkeypatch.setattr(bot.stat_fetcher, "start", lambda: None)

    original_extensions = (*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS)
    call_count = 0

    def mock_load_extension(extension: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Mock extension load failure")

    monkeypatch.setattr(bot, "load_extension", mock_load_extension)
    monkeypatch.setattr(bot, "sync_commands", lambda: [])
    monkeypatch.setattr(
        type(bot), "pending_application_commands", property(lambda self: [])
    )

    with caplog.at_level(logging.ERROR):
        await bot.setup_hook()

    assert (
        f"Failed to load extension {original_extensions[0]}: Mock extension load failure"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_setup_hook_skips_if_already_complete(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = _make_bot()
    bot._setup_complete = True

    with caplog.at_level(logging.INFO):
        await bot.setup_hook()

    assert "Setup already completed, skipping" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_skips_setup_if_already_complete(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = _make_bot()
    bot._connection.user = SimpleNamespace(name="dm4z")
    bot._setup_complete = True

    with caplog.at_level(logging.INFO):
        await bot.on_ready()

    assert "Logged in as dm4z" in caplog.text
    assert "Setup not completed" not in caplog.text


@pytest.mark.asyncio
async def test_close_stops_fetcher_and_closes_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _make_bot()
    stopped: list[bool] = []
    closed: list[bool] = []
    monkeypatch.setattr(bot.stat_fetcher, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(bot.db, "close", lambda: _async_noop_track(closed))
    monkeypatch.setattr(
        discord.Bot, "close", lambda self: _async_noop()
    )
    await bot.close()
    assert stopped == [True]
    assert closed == [True]


@pytest.mark.asyncio
async def test_before_invoke_hook_inserts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _make_bot()
    inserted: list[tuple] = []

    async def mock_execute(sql: str, params: tuple = ()) -> None:
        inserted.append(params)

    monkeypatch.setattr(bot.db, "execute", mock_execute)

    ctx = SimpleNamespace(
        guild_id=111,
        author=SimpleNamespace(id=222),
        command=SimpleNamespace(qualified_name="link"),
    )
    await bot._before_invoke_hook(ctx)
    assert inserted == [(111, 222, "link")]


@pytest.mark.asyncio
async def test_before_invoke_hook_skips_dm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _make_bot()
    inserted: list[tuple] = []

    async def mock_execute(sql: str, params: tuple = ()) -> None:
        inserted.append(params)

    monkeypatch.setattr(bot.db, "execute", mock_execute)
    ctx = SimpleNamespace(
        guild_id=None,
        author=SimpleNamespace(id=222),
        command=SimpleNamespace(qualified_name="age"),
    )
    await bot._before_invoke_hook(ctx)
    assert inserted == []


@pytest.mark.asyncio
async def test_before_invoke_hook_handles_db_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    bot = _make_bot()

    async def failing_execute(sql: str, params: tuple = ()) -> None:
        raise RuntimeError("db error")

    monkeypatch.setattr(bot.db, "execute", failing_execute)
    ctx = SimpleNamespace(
        guild_id=111,
        author=SimpleNamespace(id=222),
        command=SimpleNamespace(qualified_name="link"),
    )
    with caplog.at_level(logging.ERROR):
        await bot._before_invoke_hook(ctx)
    assert "Failed to track command usage" in caplog.text


async def _async_noop() -> None:
    pass


async def _async_noop_track(tracker: list) -> None:
    tracker.append(True)
