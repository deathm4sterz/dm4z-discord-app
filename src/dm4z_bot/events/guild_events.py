from __future__ import annotations

import logging
from typing import cast

import discord

from dm4z_bot.database.db import Database

logger = logging.getLogger(__name__)


class GuildEvents(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    @discord.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("Joined guild: %s (%d)", guild.name, guild.id)
        await self.db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild.id,))

    @discord.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info("Removed from guild: %s (%d)", guild.name, guild.id)


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    bot.add_cog(GuildEvents(bot, db))
