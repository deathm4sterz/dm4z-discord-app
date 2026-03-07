from __future__ import annotations

import logging
from typing import cast

import discord

from dm4z_bot.database.db import Database

logger = logging.getLogger(__name__)


class MemberEvents(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    @discord.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        logger.info("Member joined: %s (%d) in guild %d", member.name, member.id, member.guild.id)
        await self.db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (member.guild.id,))
        await self.db.execute(
            "INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)",
            (member.id, member.guild.id),
        )

    @discord.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        logger.info("Member left: %s (%d) from guild %d", member.name, member.id, member.guild.id)


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    bot.add_cog(MemberEvents(bot, db))
