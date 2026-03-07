from __future__ import annotations

from argparse import Namespace

import pytest

from dm4z_bot.config import load_settings


def test_load_settings_reads_token_and_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "abc123")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings = load_settings()
    assert settings.discord_token == "abc123"
    assert settings.log_level == "DEBUG"


def test_load_settings_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="missing DISCORD_TOKEN"):
        load_settings()


def test_load_settings_default_database_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "tok")
    settings = load_settings()
    assert settings.database_path == "dm4z_bot.db"


def test_load_settings_env_database_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "tok")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/test.db")
    settings = load_settings()
    assert settings.database_path == "/tmp/test.db"


def test_load_settings_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env_token")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    cli = Namespace(discord_token="cli_token", log_level="error", debug_guild_id=999, database_path="/cli.db")
    settings = load_settings(cli)
    assert settings.discord_token == "cli_token"
    assert settings.log_level == "ERROR"
    assert settings.debug_guild_id == 999
    assert settings.database_path == "/cli.db"


def test_load_settings_cli_none_falls_through_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env_token")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    cli = Namespace(discord_token=None, log_level=None, debug_guild_id=None, database_path=None)
    settings = load_settings(cli)
    assert settings.discord_token == "env_token"
    assert settings.log_level == "DEBUG"


def test_load_settings_debug_guild_id_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "tok")
    monkeypatch.setenv("DEBUG_GUILD_ID", "12345")
    settings = load_settings()
    assert settings.debug_guild_id == 12345
