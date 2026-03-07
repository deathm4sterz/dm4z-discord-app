from __future__ import annotations

import logging
from typing import cast

import discord

from dm4z_bot.services.aoe2_api import Aoe2Api

logger = logging.getLogger(__name__)


class LeaderboardCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api) -> None:
        self.bot = bot
        self.api = api

    @discord.slash_command(description="Show server-local leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext) -> None:
        logger.debug("/leaderboard invoked by %s", ctx.author)
        await ctx.defer()

        try:
            response = await self.api.leaderboard()
            await ctx.followup.send(response)
        except Exception as e:
            logger.error("Leaderboard command failed: %s", e)
            await ctx.followup.send("❌ Failed to fetch leaderboard data. Please try again later.")


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(LeaderboardCommands(bot, api))

