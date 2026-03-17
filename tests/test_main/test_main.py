from __future__ import annotations

import logging
from argparse import Namespace
from types import SimpleNamespace

import pytest

import main as main_module


def test_configure_logging_sets_up_app_logger() -> None:
    app_logger = logging.getLogger(main_module.APP_LOGGER_NAME)
    app_logger.handlers.clear()

    main_module.configure_logging("INFO")

    assert app_logger.handlers
    assert app_logger.level == logging.INFO


def test_configure_logging_does_not_duplicate_handlers() -> None:
    app_logger = logging.getLogger(main_module.APP_LOGGER_NAME)
    app_logger.handlers.clear()

    main_module.configure_logging("INFO")
    main_module.configure_logging("DEBUG")

    assert len(app_logger.handlers) == 1
    assert app_logger.level == logging.DEBUG


@pytest.mark.asyncio
async def test_async_main_loads_settings_and_starts_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(discord_token="token", log_level="INFO", database_path=":memory:")
    monkeypatch.setattr(main_module, "load_settings", lambda cli_args=None: settings)
    called: list[tuple[str, str]] = []

    class FakeBot:
        def __init__(self, settings: object) -> None:
            pass

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


def test_main_handles_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def mock_async_main(cli_args: Namespace | None = None) -> None:
        raise KeyboardInterrupt("Test interrupt")

    monkeypatch.setattr(main_module, "async_main", mock_async_main)
    monkeypatch.setattr(main_module, "parse_args", Namespace)

    with caplog.at_level(logging.INFO, logger=main_module.APP_LOGGER_NAME):
        main_module.main()

    assert "Bot stopped by user" in caplog.text


def test_parse_args_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py"])
    args = main_module.parse_args()
    assert args.discord_token is None
    assert args.log_level is None
    assert args.database_path is None


def test_parse_args_with_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py", "--discord-token", "tok", "--log-level", "DEBUG",
            "--database-path", "/x.db",
        ],
    )
    args = main_module.parse_args()
    assert args.discord_token == "tok"
    assert args.log_level == "DEBUG"
    assert args.database_path == "/x.db"
