from __future__ import annotations

from typing import cast

import discord

from dm4z_bot.services.aoe2_api import Aoe2Api


class LeaderboardCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api) -> None:
        self.bot = bot
        self.api = api

    @discord.slash_command(description="Show server-local leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext) -> None:
        # Defer the response to give us more time (up to 15 minutes)
        await ctx.defer()
        
        try:
            response = await self.api.leaderboard()
            await ctx.followup.send(response)
        except Exception as e:
            error_msg = "❌ Failed to fetch leaderboard data. Please try again later."
            await ctx.followup.send(error_msg)
            # Log the actual error for debugging
            import logging
            logging.getLogger(__name__).error("Leaderboard command failed: %s", e)


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(LeaderboardCommands(bot, api))

