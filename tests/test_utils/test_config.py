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

