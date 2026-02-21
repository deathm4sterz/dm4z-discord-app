from __future__ import annotations

from typing import cast

import discord

from dm4z_bot.services.aoe2_api import Aoe2Api


class RankCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api) -> None:
        self.bot = bot
        self.api = api

    @discord.slash_command(description="Show player rank statistic from aoe companion")
    async def rank(
        self,
        ctx: discord.ApplicationContext,
        player_name: discord.Option(str, description="In-game player name to search"),
    ) -> None:
        response = await self.api.rank(player_name=player_name)
        await ctx.respond(response)


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(RankCommands(bot, api))

