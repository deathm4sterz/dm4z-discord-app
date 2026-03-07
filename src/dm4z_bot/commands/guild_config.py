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

    @discord.slash_command(description="Enable a game for this server with a dedicated channel")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @option("channel", discord.TextChannel, description="Channel for this game's notifications")
    @discord.default_permissions(administrator=True)
    async def enable_game(
        self, ctx: discord.ApplicationContext, game: str, channel: discord.TextChannel
    ) -> None:
        if game not in self.registry:
            await ctx.respond(f"❌ Unknown game `{game}`. Available: {', '.join(self.registry.keys())}")
            return

        guild_id = ctx.guild_id
        await self.db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
        await self.db.execute(
            "INSERT INTO guild_games (guild_id, game, channel_id, enabled) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(guild_id, game) DO UPDATE SET channel_id = ?, enabled = 1, "
            "updated_at = datetime('now')",
            (guild_id, game, channel.id, channel.id),
        )
        await ctx.respond(f"✅ **{game}** enabled in {channel.mention}.")

    @discord.slash_command(description="Disable a game for this server")
    @option("game", str, description="Game key to disable")
    @discord.default_permissions(administrator=True)
    async def disable_game(self, ctx: discord.ApplicationContext, game: str) -> None:
        guild_id = ctx.guild_id
        result = await self.db.execute(
            "UPDATE guild_games SET enabled = 0, updated_at = datetime('now') "
            "WHERE guild_id = ? AND game = ?",
            (guild_id, game),
        )
        if result.rowcount:
            await ctx.respond(f"✅ **{game}** disabled for this server.")
        else:
            await ctx.respond(f"❌ **{game}** was not enabled in this server.")


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    registry = cast(GameRegistry, bot.game_registry)
    bot.add_cog(GuildConfigCommands(bot, db, registry))
