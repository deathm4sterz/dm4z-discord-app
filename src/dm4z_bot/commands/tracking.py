from __future__ import annotations

import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.database.db import Database
from dm4z_bot.tasks.match_tracker import MatchTracker
from dm4z_bot.utils.mod_notifications import notify_guild_mod_channel

logger = logging.getLogger(__name__)


class TrackingCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database, tracker: MatchTracker) -> None:
        self.bot = bot
        self.db = db
        self.tracker = tracker

    @discord.slash_command(description="Enable match tracking for a member's linked game account")
    @option("game", str, description="Game key (e.g. aoe2)")
    @option("member", discord.Member, description="The member to enable tracking for")
    @discord.default_permissions(manage_roles=True)
    async def enable_tracking(
        self, ctx: discord.ApplicationContext, game: str, member: discord.Member,
    ) -> None:
        logger.debug("/enable_tracking invoked by %s: game=%s, member=%s", ctx.author, game, member)
        guild_id = ctx.guild_id

        row = await self.db.fetch_one(
            "SELECT id, status, tracking, account_identifier, display_name FROM game_accounts "
            "WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member.id, guild_id, game),
        )
        if not row:
            await ctx.respond(
                f"❌ No linked **{game}** account found for {member.mention}.", ephemeral=True,
            )
            return
        if row["status"] != "approved":
            await ctx.respond(
                f"❌ {member.mention}'s **{game}** account must be approved before enabling tracking.",
                ephemeral=True,
            )
            return
        if row["tracking"]:
            await ctx.respond(
                f"ℹ️ Tracking is already enabled for {member.mention}'s **{game}** account.",
                ephemeral=True,
            )
            return

        await self.db.execute(
            "UPDATE game_accounts SET tracking = 1, updated_at = datetime('now') WHERE id = ?",
            (row["id"],),
        )
        logger.info(
            "Tracking enabled for member %d (%s) in guild %d by %s",
            member.id, game, guild_id, ctx.author,
        )
        await ctx.respond(
            f"✅ Match tracking enabled for {member.mention}'s **{game}** account "
            f"(`{row['display_name'] or row['account_identifier']}`).",
            ephemeral=True,
        )

        await self.tracker.reconnect()
        await notify_guild_mod_channel(
            self.bot, self.db, guild_id,
            f"Match tracking enabled for <@{member.id}> ({game}) by {ctx.author.mention}.",
        )

    @discord.slash_command(description="Disable match tracking for a member's linked game account")
    @option("game", str, description="Game key (e.g. aoe2)")
    @option("member", discord.Member, description="The member to disable tracking for")
    @discord.default_permissions(manage_roles=True)
    async def disable_tracking(
        self, ctx: discord.ApplicationContext, game: str, member: discord.Member,
    ) -> None:
        logger.debug("/disable_tracking invoked by %s: game=%s, member=%s", ctx.author, game, member)
        guild_id = ctx.guild_id

        result = await self.db.execute(
            "UPDATE game_accounts SET tracking = 0, updated_at = datetime('now') "
            "WHERE member_id = ? AND guild_id = ? AND game = ? AND tracking = 1",
            (member.id, guild_id, game),
        )
        if result.rowcount:
            logger.info(
                "Tracking disabled for member %d (%s) in guild %d by %s",
                member.id, game, guild_id, ctx.author,
            )
            await ctx.respond(
                f"✅ Match tracking disabled for {member.mention}'s **{game}** account.",
                ephemeral=True,
            )
            await self.tracker.reconnect()
            await notify_guild_mod_channel(
                self.bot, self.db, guild_id,
                f"Match tracking disabled for <@{member.id}> ({game}) by {ctx.author.mention}.",
            )
        else:
            await ctx.respond(
                f"❌ Tracking was not enabled for {member.mention}'s **{game}** account.",
                ephemeral=True,
            )

    @discord.slash_command(description="List members with active match tracking")
    @option("game", str, description="Filter by game key", required=False)
    @discord.default_permissions(manage_roles=True)
    async def tracked(self, ctx: discord.ApplicationContext, game: str | None = None) -> None:
        logger.debug("/tracked invoked by %s (game=%s)", ctx.author, game)
        guild_id = ctx.guild_id

        if game:
            rows = await self.db.fetch_all(
                "SELECT member_id, game, account_identifier, display_name FROM game_accounts "
                "WHERE guild_id = ? AND tracking = 1 AND status = 'approved' AND game = ?",
                (guild_id, game),
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT member_id, game, account_identifier, display_name FROM game_accounts "
                "WHERE guild_id = ? AND tracking = 1 AND status = 'approved'",
                (guild_id,),
            )

        if not rows:
            await ctx.respond("No members are being tracked.", ephemeral=True)
            return

        lines = [
            f"<@{r['member_id']}> — **{r['game']}** (`{r['display_name'] or r['account_identifier']}`)"
            for r in rows
        ]
        await ctx.respond("**Tracked members:**\n" + "\n".join(lines), ephemeral=True)


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    tracker = cast(MatchTracker, bot.match_tracker)
    bot.add_cog(TrackingCommands(bot, db, tracker))
