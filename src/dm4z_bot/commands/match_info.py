from __future__ import annotations

import logging

import discord
from discord import option

from dm4z_bot.utils.match_reply import build_match_response_text, build_match_view
from dm4z_bot.utils.regex_patterns import extract_match_id

logger = logging.getLogger(__name__)


class MatchInfoCommands(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Show match information from link or match id")
    @option("match_id", str, description="aoe2 insight link, or lobby link or plain match id")
    async def match_info(
        self,
        ctx: discord.ApplicationContext,
        match_id: str,
    ) -> None:
        extracted_id = extract_match_id(match_id)
        if not extracted_id:
            logger.error("Invalid input for match_id: %s", match_id)
            await ctx.respond("No 9-digit match ID found in the input.")
            return

        await ctx.respond(
            build_match_response_text(extracted_id),
            view=build_match_view(extracted_id),
        )


def setup(bot: discord.Bot) -> None:
    bot.add_cog(MatchInfoCommands(bot))

