from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from dm4z_bot.bot import COMMAND_EXTENSIONS, EVENT_EXTENSIONS, Dm4zBot


@pytest.mark.asyncio
async def test_setup_hook_loads_all_extensions(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    loaded: list[str] = []
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    monkeypatch.setattr(bot, "load_extension", loaded.append)
    
    async def successful_sync():
        return ["cmd1", "cmd2"]
    
    monkeypatch.setattr(bot, "sync_commands", successful_sync)
    with caplog.at_level(logging.INFO):
        await bot.setup_hook()
    assert loaded == [*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS]
    assert "Synced 2 command(s)" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_logs_when_user_available(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    bot._connection.user = SimpleNamespace(name="dm4z")  # pyright/mypy not enforced in tests
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    assert "Logged in as dm4z" in caplog.text
    assert "Bot is ready! Loaded" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_no_user_does_not_log(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    bot._connection.user = None
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    assert "Logged in as" not in caplog.text
    assert "Bot is ready!" not in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_logs_sync_error(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    
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
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    
    async def none_sync():
        return None
    
    monkeypatch.setattr(bot, "sync_commands", none_sync)
    monkeypatch.setattr(type(bot), "pending_application_commands", property(lambda self: []))
    
    with caplog.at_level(logging.INFO):
        await bot.setup_hook()
    assert "Command sync completed (no commands to sync)" in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_logs_extension_loading(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    monkeypatch.setattr(bot, "sync_commands", lambda: [])
    monkeypatch.setattr(type(bot), "pending_application_commands", property(lambda self: []))
    
    with caplog.at_level(logging.INFO):
        await bot.setup_hook()
    
    assert "Loading 6 extensions..." in caplog.text
    assert "Extensions loaded. Pending commands: 0" in caplog.text


@pytest.mark.asyncio
async def test_bot_debug_mode_logging(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    monkeypatch.setenv("DEBUG_GUILD_ID", "123456789")
    
    with caplog.at_level(logging.INFO):
        Dm4zBot()
    
    assert "Debug mode enabled for guild: 123456789" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_calls_setup_if_not_complete(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    bot._connection.user = SimpleNamespace(name="dm4z")
    monkeypatch.setattr(bot, "load_extension", lambda x: None)
    
    async def mock_sync():
        return []
    monkeypatch.setattr(bot, "sync_commands", mock_sync)
    monkeypatch.setattr(type(bot), "pending_application_commands", property(lambda self: []))
    
    # Simulate setup_hook not being called automatically
    bot._setup_complete = False
    
    with caplog.at_level(logging.WARNING):
        await bot.on_ready()
    
    assert "Setup not completed - running setup_hook manually" in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_handles_extension_load_failure(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    
    # Mock load_extension to raise an exception for the first extension
    original_extensions = (*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS)
    call_count = 0
    
    def mock_load_extension(extension: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # Fail on first extension
            raise RuntimeError("Mock extension load failure")
    
    monkeypatch.setattr(bot, "load_extension", mock_load_extension)
    monkeypatch.setattr(bot, "sync_commands", lambda: [])
    monkeypatch.setattr(type(bot), "pending_application_commands", property(lambda self: []))
    
    with caplog.at_level(logging.ERROR):
        await bot.setup_hook()
    
    assert f"Failed to load extension {original_extensions[0]}: Mock extension load failure" in caplog.text


@pytest.mark.asyncio
async def test_setup_hook_skips_if_already_complete(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    bot._setup_complete = True
    
    with caplog.at_level(logging.INFO):
        await bot.setup_hook()
    
    assert "Setup already completed, skipping" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_skips_setup_if_already_complete(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token")
    bot = Dm4zBot()
    bot._connection.user = SimpleNamespace(name="dm4z")
    bot._setup_complete = True
    
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    
    assert "Logged in as dm4z" in caplog.text
    assert "Setup not completed" not in caplog.text

