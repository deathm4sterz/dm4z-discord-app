from __future__ import annotations

import logging

import discord
from discord import option

logger = logging.getLogger(__name__)


class AgeCommands(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Displays your or another user's account creation date")
    @option("user", discord.User, description="Selected user", required=False)
    async def age(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User | None = None,
    ) -> None:
        selected_user = user or ctx.author
        logger.debug("/age invoked by %s for user %s", ctx.author, selected_user)
        await ctx.respond(
            f"{selected_user.name}'s account was created at {selected_user.created_at}"
        )


def setup(bot: discord.Bot) -> None:
    bot.add_cog(AgeCommands(bot))

