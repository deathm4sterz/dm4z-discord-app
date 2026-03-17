from __future__ import annotations

import asyncio
import logging
from argparse import ArgumentParser, Namespace

from dm4z_bot.bot import Dm4zBot
from dm4z_bot.config import load_settings

APP_LOGGER_NAME = "dm4z_bot"

logger = logging.getLogger(APP_LOGGER_NAME)


def configure_logging(level: str) -> None:
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
        app_logger.addHandler(handler)


def parse_args() -> Namespace:
    parser = ArgumentParser(description="dm4z Discord bot")
    parser.add_argument("--discord-token", default=None)
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--database-path", default=None)
    parser.add_argument("--leetify-api-key", default=None)
    return parser.parse_args()


async def async_main(cli_args: Namespace | None = None) -> None:
    settings = load_settings(cli_args)
    configure_logging(settings.log_level)
    bot = Dm4zBot(settings)
    await bot.start(settings.discord_token)


def main() -> None:
    try:
        args = parse_args()
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


if __name__ == "__main__":  # pragma: no cover
    main()
