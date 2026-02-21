from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from dm4z_bot.bot import COMMAND_EXTENSIONS, EVENT_EXTENSIONS, Dm4zBot


@pytest.mark.asyncio
async def test_setup_hook_loads_all_extensions(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded: list[str] = []
    bot = Dm4zBot()
    monkeypatch.setattr(bot, "load_extension", loaded.append)
    await bot.setup_hook()
    assert loaded == [*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS]


@pytest.mark.asyncio
async def test_on_ready_logs_when_user_available(caplog: pytest.LogCaptureFixture) -> None:
    bot = Dm4zBot()
    bot._connection.user = SimpleNamespace(name="dm4z")  # pyright/mypy not enforced in tests
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    assert "Logged in as dm4z" in caplog.text


@pytest.mark.asyncio
async def test_on_ready_no_user_does_not_log(caplog: pytest.LogCaptureFixture) -> None:
    bot = Dm4zBot()
    bot._connection.user = None
    with caplog.at_level(logging.INFO):
        await bot.on_ready()
    assert "Logged in as" not in caplog.text

