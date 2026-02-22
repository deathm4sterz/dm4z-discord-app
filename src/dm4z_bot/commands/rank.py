from __future__ import annotations

from typing import cast

import discord
from discord import option

from dm4z_bot.services.aoe2_api import Aoe2Api, PlayerNotFoundError


class RankCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api) -> None:
        self.bot = bot
        self.api = api

    @discord.slash_command(description="Show player rank statistic from aoe companion")
    @option("player_name", str, description="In-game player name to search")
    async def rank(
        self,
        ctx: discord.ApplicationContext,
        player_name: str,
    ) -> None:
        await ctx.defer()
        try:
            response = await self.api.rank(player_name=player_name)
            await ctx.followup.send(response)
        except PlayerNotFoundError:
            await ctx.followup.send(f"❌ Rank information for player '{player_name}' not found")
        except Exception:
            await ctx.followup.send(f"❌ Failed to fetch rank details for '{player_name}'. Try again later...")


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(RankCommands(bot, api))

