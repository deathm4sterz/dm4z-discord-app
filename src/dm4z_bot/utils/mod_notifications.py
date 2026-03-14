from __future__ import annotations

import logging

import discord

from dm4z_bot.database.db import Database

logger = logging.getLogger(__name__)


async def notify_mod_channels(bot: discord.Bot, db: Database, message: str) -> None:
    """Send a plain-text notification to every guild's mod channel."""
    rows = await db.fetch_all(
        "SELECT guild_id, mod_channel_id FROM guilds WHERE mod_channel_id IS NOT NULL"
    )
    for row in rows:
        channel = bot.get_channel(row["mod_channel_id"])
        if channel is None:
            logger.warning(
                "Mod channel %d not found for guild %d", row["mod_channel_id"], row["guild_id"],
            )
            continue
        try:
            await channel.send(message)
            logger.debug("Mod notification sent to guild %d", row["guild_id"])
        except Exception:
            logger.exception("Failed to send mod notification to guild %d", row["guild_id"])


async def notify_guild_mod_channel(
    bot: discord.Bot, db: Database, guild_id: int, message: str,
) -> None:
    """Send a plain-text notification to a specific guild's mod channel."""
    row = await db.fetch_one(
        "SELECT mod_channel_id FROM guilds WHERE guild_id = ?", (guild_id,),
    )
    if not row or not row["mod_channel_id"]:
        logger.debug("No mod channel configured for guild %d", guild_id)
        return

    channel = bot.get_channel(row["mod_channel_id"])
    if channel is None:
        logger.warning("Mod channel %d not found for guild %d", row["mod_channel_id"], guild_id)
        return

    try:
        await channel.send(message)
        logger.debug("Mod notification sent to guild %d", guild_id)
    except Exception:
        logger.exception("Failed to send mod notification to guild %d", guild_id)
