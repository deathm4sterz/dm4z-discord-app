from __future__ import annotations

import logging

import discord

from dm4z_bot.utils.match_reply import build_match_response_text, build_match_view
from dm4z_bot.utils.regex_patterns import extract_match_id

logger = logging.getLogger(__name__)


class MessageEvents(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        message_content_lower = message.content.lower()
        if "aoe2de" not in message_content_lower:
            return

        extracted_id = extract_match_id(message_content_lower)
        if not extracted_id:
            logger.error("Failed to find aoe2de link in %s", message.content)
            return

        logger.info("Received aoe2de link %s", message.content)
        await message.channel.send(
            build_match_response_text(extracted_id),
            view=build_match_view(extracted_id),
        )


def setup(bot: discord.Bot) -> None:
    bot.add_cog(MessageEvents(bot))

