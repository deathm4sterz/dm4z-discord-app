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
        response = await self.api.leaderboard()
        await ctx.respond(response)


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(LeaderboardCommands(bot, api))

