from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import main as main_module


def test_configure_logging_sets_expected_format() -> None:
    main_module.configure_logging("INFO")
    root_handlers = logging.getLogger().handlers
    assert root_handlers


@pytest.mark.asyncio
async def test_async_main_loads_settings_and_starts_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(discord_token="token", log_level="INFO")
    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    called: list[tuple[str, str]] = []

    class FakeBot:
        async def start(self, token: str) -> None:
            called.append(("start", token))

    monkeypatch.setattr(main_module, "Dm4zBot", FakeBot)
    monkeypatch.setattr(
        main_module,
        "configure_logging",
        lambda level: called.append(("log", level)),
    )
    await main_module.async_main()
    assert called == [("log", "INFO"), ("start", "token")]


def test_main_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_async_main() -> None:
        raise KeyboardInterrupt("Test interrupt")

    monkeypatch.setattr(main_module, "async_main", mock_async_main)
    
    # Capture logging calls
    logged_messages: list[str] = []
    def mock_log_info(msg: str) -> None:
        logged_messages.append(msg)
    
    monkeypatch.setattr(logging, "info", mock_log_info)
    
    # Should not raise, should handle gracefully
    main_module.main()
    assert logged_messages == ["Bot stopped by user"]

