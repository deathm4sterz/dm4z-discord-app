from __future__ import annotations

import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.database.db import Database
from dm4z_bot.services.games.registry import GameRegistry

logger = logging.getLogger(__name__)


class GuildConfigCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database, registry: GameRegistry) -> None:
        self.bot = bot
        self.db = db
        self.registry = registry

    @discord.slash_command(description="Register a game for this server with a dedicated channel")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @option("channel", discord.TextChannel, description="Channel for this game's notifications")
    @discord.default_permissions(administrator=True)
    async def register_game(
        self, ctx: discord.ApplicationContext, game: str, channel: discord.TextChannel
    ) -> None:
        logger.debug("/register_game invoked by %s: game=%s, channel=%s", ctx.author, game, channel)
        if game not in self.registry:
            await ctx.respond(f"❌ Unknown game `{game}`. Available: {', '.join(self.registry.keys())}", ephemeral=True)
            return

        guild_id = ctx.guild_id
        await self.db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
        await self.db.execute(
            "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(guild_id, game) DO UPDATE SET channel_id = ?, enabled = 1, "
            "updated_at = datetime('now')",
            (guild_id, game, channel.id, channel.id),
        )
        logger.info("Game %s enabled in guild %d, channel %d", game, guild_id, channel.id)
        await ctx.respond(f"✅ **{game}** enabled in {channel.mention}.", ephemeral=True)

    @discord.slash_command(description="Set the moderation channel for approval notifications")
    @option("channel", discord.TextChannel, description="Channel for moderation notifications")
    @discord.default_permissions(administrator=True)
    async def set_mod_channel(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ) -> None:
        logger.debug("/set_mod_channel invoked by %s: channel=%s", ctx.author, channel)
        guild_id = ctx.guild_id
        await self.db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
        await self.db.execute(
            "UPDATE guilds SET mod_channel_id = ?, updated_at = datetime('now') WHERE guild_id = ?",
            (channel.id, guild_id),
        )
        logger.info("Mod channel set to %d in guild %d", channel.id, guild_id)
        await ctx.respond(f"✅ Moderation channel set to {channel.mention}.", ephemeral=True)

    @discord.slash_command(description="Disable a game for this server")
    @option("game", str, description="Game key to disable")
    @discord.default_permissions(administrator=True)
    async def disable_game(self, ctx: discord.ApplicationContext, game: str) -> None:
        logger.debug("/disable_game invoked by %s: game=%s", ctx.author, game)
        guild_id = ctx.guild_id
        result = await self.db.execute(
            "UPDATE guild_games SET enabled = 0, updated_at = datetime('now') "
            "WHERE guild_id = ? AND game = ?",
            (guild_id, game),
        )
        if result.rowcount:
            logger.info("Game %s disabled in guild %d", game, guild_id)
            await ctx.respond(f"✅ **{game}** disabled for this server.", ephemeral=True)
        else:
            await ctx.respond(f"❌ **{game}** was not enabled in this server.", ephemeral=True)


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    registry = cast(GameRegistry, bot.game_registry)
    bot.add_cog(GuildConfigCommands(bot, db, registry))
