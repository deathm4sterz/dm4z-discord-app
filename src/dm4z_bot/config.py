from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from os import getenv

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    log_level: str = "INFO"
    database_path: str = "dm4z_bot.db"
    leetify_api_key: str | None = None


def _resolve(cli_args: Namespace | None, attr: str, env_key: str, default: str | None = None) -> str | None:
    cli_val = getattr(cli_args, attr, None) if cli_args else None
    if cli_val is not None:
        return str(cli_val)
    env_val = getenv(env_key)
    if env_val is not None:
        return env_val
    return default


def load_settings(cli_args: Namespace | None = None) -> Settings:
    load_dotenv()

    token = _resolve(cli_args, "discord_token", "DISCORD_TOKEN")
    if not token:
        raise RuntimeError("missing DISCORD_TOKEN")

    log_level = _resolve(cli_args, "log_level", "LOG_LEVEL", "INFO")

    database_path = _resolve(cli_args, "database_path", "DATABASE_PATH", "dm4z_bot.db")

    leetify_api_key = _resolve(cli_args, "leetify_api_key", "LEETIFY_API_KEY")

    return Settings(
        discord_token=token,
        log_level=log_level.upper() if log_level else "INFO",
        database_path=database_path or "dm4z_bot.db",
        leetify_api_key=leetify_api_key,
    )
