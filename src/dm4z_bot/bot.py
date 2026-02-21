from __future__ import annotations

import logging

import discord

from dm4z_bot.services.aoe2_api import Aoe2Api

logger = logging.getLogger(__name__)

COMMAND_EXTENSIONS: tuple[str, ...] = (
    "dm4z_bot.commands.age",
    "dm4z_bot.commands.match_info",
    "dm4z_bot.commands.rank",
    "dm4z_bot.commands.team_rank",
    "dm4z_bot.commands.leaderboard",
)

EVENT_EXTENSIONS: tuple[str, ...] = ("dm4z_bot.events.message_handler",)


class Dm4zBot(discord.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.aoe2_api = Aoe2Api()

    async def setup_hook(self) -> None:
        for extension in (*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS):
            self.load_extension(extension)

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Logged in as %s", self.user.name)

