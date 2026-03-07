from __future__ import annotations

import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.database.db import Database

logger = logging.getLogger(__name__)


class ApproveCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    @discord.slash_command(description="Approve a member's game account link request")
    @option("member", discord.Member, description="The member to approve")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @discord.default_permissions(manage_roles=True)
    async def approve(self, ctx: discord.ApplicationContext, member: discord.Member, game: str) -> None:
        guild_id = ctx.guild_id
        row = await self.db.fetch_one(
            "SELECT id, status, account_identifier FROM game_accounts "
            "WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member.id, guild_id, game),
        )
        if not row:
            await ctx.respond(f"❌ No link request found for {member.mention} / **{game}**.")
            return
        if row["status"] == "approved":
            await ctx.respond(f"ℹ️ {member.mention}'s **{game}** account is already approved.")
            return

        await self.db.execute(
            "UPDATE game_accounts SET status = 'approved', reviewed_by = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (ctx.author.id, row["id"]),
        )
        await ctx.respond(
            f"✅ Approved {member.mention}'s **{game}** account (`{row['account_identifier']}`). "
            "It will now be tracked."
        )

    @discord.slash_command(description="Reject a member's game account link request")
    @option("member", discord.Member, description="The member to reject")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @discord.default_permissions(manage_roles=True)
    async def reject(self, ctx: discord.ApplicationContext, member: discord.Member, game: str) -> None:
        guild_id = ctx.guild_id
        row = await self.db.fetch_one(
            "SELECT id, status FROM game_accounts WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member.id, guild_id, game),
        )
        if not row:
            await ctx.respond(f"❌ No link request found for {member.mention} / **{game}**.")
            return

        await self.db.execute(
            "UPDATE game_accounts SET status = 'rejected', reviewed_by = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (ctx.author.id, row["id"]),
        )
        await ctx.respond(f"✅ Rejected {member.mention}'s **{game}** link request.")

    @discord.slash_command(description="List pending link requests in this server")
    @option("game", str, description="Filter by game key", required=False)
    @discord.default_permissions(manage_roles=True)
    async def pending(self, ctx: discord.ApplicationContext, game: str | None = None) -> None:
        guild_id = ctx.guild_id
        if game:
            rows = await self.db.fetch_all(
                "SELECT member_id, game, account_identifier FROM game_accounts "
                "WHERE guild_id = ? AND status = 'pending' AND game = ?",
                (guild_id, game),
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT member_id, game, account_identifier FROM game_accounts "
                "WHERE guild_id = ? AND status = 'pending'",
                (guild_id,),
            )

        if not rows:
            await ctx.respond("No pending link requests.")
            return

        lines = [
            f"<@{r['member_id']}> — **{r['game']}** (`{r['account_identifier']}`)"
            for r in rows
        ]
        await ctx.respond("**Pending link requests:**\n" + "\n".join(lines))


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    bot.add_cog(ApproveCommands(bot, db))
