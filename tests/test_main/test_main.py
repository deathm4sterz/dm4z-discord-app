from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import main as main_module


def test_configure_logging_sets_expected_format() -> None:
    main_module.configure_logging("INFO")
    root_handlers = logging.getLogger().handlers
    assert root_handlers


def test_main_loads_settings_and_runs_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(discord_token="token", log_level="INFO")
    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    called: list[tuple[str, str]] = []

    class FakeBot:
        def run(self, token: str) -> None:
            called.append(("run", token))

    monkeypatch.setattr(main_module, "Dm4zBot", FakeBot)
    monkeypatch.setattr(
        main_module,
        "configure_logging",
        lambda level: called.append(("log", level)),
    )
    main_module.main()
    assert called == [("log", "INFO"), ("run", "token")]

