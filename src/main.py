from __future__ import annotations

import asyncio
import logging

from dm4z_bot.bot import Dm4zBot
from dm4z_bot.config import load_settings


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


async def async_main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    bot = Dm4zBot()
    await bot.start(settings.discord_token)


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")


if __name__ == "__main__":  # pragma: no cover
    main()

