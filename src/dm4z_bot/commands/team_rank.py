from __future__ import annotations

from typing import cast

import discord

from dm4z_bot.services.aoe2_api import Aoe2Api


class TeamRankCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api) -> None:
        self.bot = bot
        self.api = api

    @discord.slash_command(description="Show player team-rank statistic from aoe companion")
    async def team_rank(
        self,
        ctx: discord.ApplicationContext,
        player_name: discord.Option(str, description="In-game player name to search"),
    ) -> None:
        response = await self.api.team_rank(player_name=player_name)
        await ctx.respond(response)


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(TeamRankCommands(bot, api))

