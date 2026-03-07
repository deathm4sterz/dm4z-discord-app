from __future__ import annotations

import asyncio
import logging

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


async def async_main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    bot = Dm4zBot()
    await bot.start(settings.discord_token)


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


if __name__ == "__main__":  # pragma: no cover
    main()

