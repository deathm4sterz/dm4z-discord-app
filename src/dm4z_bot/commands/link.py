from __future__ import annotations

import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.commands.approve import send_mod_notification
from dm4z_bot.database.db import Database
from dm4z_bot.services.games.registry import GameRegistry

logger = logging.getLogger(__name__)


class LinkCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database, registry: GameRegistry) -> None:
        self.bot = bot
        self.db = db
        self.registry = registry

    @discord.slash_command(description="Link your game account for tracking")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @option("account_id", str, description="Your in-game account identifier")
    async def link(self, ctx: discord.ApplicationContext, game: str, account_id: str) -> None:
        logger.debug("/link invoked by %s: game=%s, account_id=%s", ctx.author, game, account_id)
        await ctx.defer()

        if game not in self.registry:
            logger.debug("Unknown game requested in /link: %s", game)
            await ctx.followup.send(f"❌ Unknown game `{game}`. Available: {', '.join(self.registry.keys())}")
            return

        service = self.registry.get(game)
        display_name = await service.validate_account(account_id)
        if display_name is None:
            logger.info("Account validation failed for /link: game=%s, account=%s", game, account_id)
            await ctx.followup.send(f"❌ Could not validate account `{account_id}` for {game}.")
            return

        guild_id = ctx.guild_id
        member_id = ctx.author.id

        await self.db.execute(
            "INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,)
        )
        await self.db.execute(
            "INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)",
            (member_id, guild_id),
        )

        existing = await self.db.fetch_one(
            "SELECT id, status FROM game_accounts WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member_id, guild_id, game),
        )
        if existing:
            logger.info("Updating existing link request %d for member %d (%s)", existing["id"], member_id, game)
            await self.db.execute(
                "UPDATE game_accounts SET account_identifier = ?, display_name = ?, status = 'pending', "
                "reviewed_by = NULL, updated_at = datetime('now') "
                "WHERE id = ?",
                (account_id, display_name, existing["id"]),
            )
            request_id = existing["id"]
        else:
            logger.info("Creating new link request for member %d (%s / %s)", member_id, game, account_id)
            cursor = await self.db.execute(
                "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name) "
                "VALUES (?, ?, ?, ?, ?)",
                (member_id, guild_id, game, account_id, display_name),
            )
            request_id = cursor.lastrowid

        await ctx.followup.send(
            f"✅ Link request for **{game}** (`{display_name}`) submitted. Awaiting moderator approval."
        )

        try:
            await send_mod_notification(self.bot, self.db, guild_id, member_id, game, account_id, request_id)
        except Exception:
            logger.exception("Failed to send mod channel notification")

    @discord.slash_command(description="Unlink your game account")
    @option("game", str, description="Game key to unlink (e.g. aoe2, cs2)")
    async def unlink(self, ctx: discord.ApplicationContext, game: str) -> None:
        guild_id = ctx.guild_id
        member_id = ctx.author.id
        logger.debug("/unlink invoked by %s: game=%s", ctx.author, game)

        result = await self.db.execute(
            "DELETE FROM game_accounts WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member_id, guild_id, game),
        )
        if result.rowcount:
            logger.info("Unlinked %s account for member %d in guild %d", game, member_id, guild_id)
            await ctx.respond(f"✅ Unlinked your **{game}** account.")
        else:
            await ctx.respond(f"❌ No linked **{game}** account found.")


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    registry = cast(GameRegistry, bot.game_registry)
    bot.add_cog(LinkCommands(bot, db, registry))
