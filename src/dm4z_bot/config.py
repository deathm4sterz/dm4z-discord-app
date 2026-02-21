from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    log_level: str = "INFO"


def load_settings() -> Settings:
    load_dotenv()
    token = getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("missing DISCORD_TOKEN")
    return Settings(
        discord_token=token,
        log_level=getenv("LOG_LEVEL", "INFO").upper(),
    )

