from __future__ import annotations

import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.database.db import Database

logger = logging.getLogger(__name__)


async def _notify_game_channel(
    bot: discord.Bot,
    db: Database,
    guild_id: int,
    member_id: int,
    game: str,
    account: str,
    status: str,
) -> None:
    row = await db.fetch_one(
        "SELECT channel_id FROM guild_games WHERE guild_id = ? AND game = ? AND enabled = 1",
        (guild_id, game),
    )
    if not row or not row["channel_id"]:
        return

    channel = bot.get_channel(row["channel_id"])
    if channel is None:
        logger.warning("Game channel %d not found for guild %d / %s", row["channel_id"], guild_id, game)
        return

    if status == "approved":
        msg = f"✅ <@{member_id}>'s **{game}** account (`{account}`) has been approved!"
    else:
        msg = f"❌ <@{member_id}>'s **{game}** account (`{account}`) link request was denied."

    try:
        await channel.send(msg)
    except Exception:
        logger.exception("Failed to send game-channel notification for guild %d / %s", guild_id, game)


class ApprovalView(discord.ui.View):
    def __init__(self, db: Database, request_id: int, member_id: int, game: str, account: str) -> None:
        super().__init__(timeout=None)
        self.db = db
        self.request_id = request_id
        self.member_id = member_id
        self.game = game
        self.account = account

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approval_approve")
    async def approve_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("⚠️ You don't have permission to do this.", ephemeral=True)
            return

        row = await self.db.fetch_one(
            "SELECT status FROM game_accounts WHERE id = ?", (self.request_id,)
        )
        if not row or row["status"] != "pending":
            await interaction.response.send_message("⚠️ This request has already been handled.", ephemeral=True)
            return

        await self.db.execute(
            "UPDATE game_accounts SET status = 'approved', reviewed_by = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (interaction.user.id, self.request_id),
        )
        logger.info("Approved request %d via button by %s", self.request_id, interaction.user)

        for child in self.children:
            child.disabled = True
        msg = (
            f"✅ **Approved** by {interaction.user.mention}"
            f" — <@{self.member_id}>'s **{self.game}** (`{self.account}`)"
        )
        await interaction.response.edit_message(content=msg, view=self)
        await _notify_game_channel(
            interaction.client, self.db, interaction.guild_id,
            self.member_id, self.game, self.account, "approved",
        )

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="approval_deny")
    async def deny_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("⚠️ You don't have permission to do this.", ephemeral=True)
            return

        row = await self.db.fetch_one(
            "SELECT status FROM game_accounts WHERE id = ?", (self.request_id,)
        )
        if not row or row["status"] != "pending":
            await interaction.response.send_message("⚠️ This request has already been handled.", ephemeral=True)
            return

        await self.db.execute(
            "UPDATE game_accounts SET status = 'rejected', reviewed_by = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (interaction.user.id, self.request_id),
        )
        logger.info("Rejected request %d via button by %s", self.request_id, interaction.user)

        for child in self.children:
            child.disabled = True
        msg = (
            f"❌ **Denied** by {interaction.user.mention}"
            f" — <@{self.member_id}>'s **{self.game}** (`{self.account}`)"
        )
        await interaction.response.edit_message(content=msg, view=self)
        await _notify_game_channel(
            interaction.client, self.db, interaction.guild_id,
            self.member_id, self.game, self.account, "rejected",
        )


async def send_mod_notification(
    bot: discord.Bot, db: Database, guild_id: int,
    member_id: int, game: str, account: str, request_id: int,
) -> None:
    guild_row = await db.fetch_one(
        "SELECT mod_channel_id FROM guilds WHERE guild_id = ?", (guild_id,)
    )
    if not guild_row or not guild_row["mod_channel_id"]:
        return

    channel = bot.get_channel(guild_row["mod_channel_id"])
    if channel is None:
        logger.warning("Mod channel %d not found for guild %d", guild_row["mod_channel_id"], guild_id)
        return

    view = ApprovalView(db, request_id, member_id, game, account)
    await channel.send(
        f"📋 **New link request** — <@{member_id}> wants to link **{game}** account `{account}`",
        view=view,
    )


class ApproveCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    @discord.slash_command(description="Approve a member's game account link request")
    @option("member", discord.Member, description="The member to approve")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @discord.default_permissions(manage_roles=True)
    async def approve(self, ctx: discord.ApplicationContext, member: discord.Member, game: str) -> None:
        logger.debug("/approve invoked by %s for member %s (%s)", ctx.author, member, game)
        guild_id = ctx.guild_id
        row = await self.db.fetch_one(
            "SELECT id, status, account_identifier FROM game_accounts "
            "WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member.id, guild_id, game),
        )
        if not row:
            await ctx.respond(f"❌ No link request found for {member.mention} / **{game}**.", ephemeral=True)
            return
        if row["status"] == "approved":
            await ctx.respond(f"ℹ️ {member.mention}'s **{game}** account is already approved.", ephemeral=True)
            return

        await self.db.execute(
            "UPDATE game_accounts SET status = 'approved', reviewed_by = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (ctx.author.id, row["id"]),
        )
        logger.info("Approved link request %d for member %s (%s) by %s", row["id"], member, game, ctx.author)
        await ctx.respond(
            f"✅ Approved {member.mention}'s **{game}** account (`{row['account_identifier']}`). "
            "It will now be tracked.",
            ephemeral=True,
        )
        await _notify_game_channel(
            self.bot, self.db, guild_id,
            member.id, game, row["account_identifier"], "approved",
        )

    @discord.slash_command(description="Reject a member's game account link request")
    @option("member", discord.Member, description="The member to reject")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @discord.default_permissions(manage_roles=True)
    async def reject(self, ctx: discord.ApplicationContext, member: discord.Member, game: str) -> None:
        logger.debug("/reject invoked by %s for member %s (%s)", ctx.author, member, game)
        guild_id = ctx.guild_id
        row = await self.db.fetch_one(
            "SELECT id, status, account_identifier FROM game_accounts "
            "WHERE member_id = ? AND guild_id = ? AND game = ?",
            (member.id, guild_id, game),
        )
        if not row:
            await ctx.respond(f"❌ No link request found for {member.mention} / **{game}**.", ephemeral=True)
            return

        await self.db.execute(
            "UPDATE game_accounts SET status = 'rejected', reviewed_by = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (ctx.author.id, row["id"]),
        )
        logger.info("Rejected link request %d for member %s (%s) by %s", row["id"], member, game, ctx.author)
        await ctx.respond(f"✅ Rejected {member.mention}'s **{game}** link request.", ephemeral=True)
        await _notify_game_channel(
            self.bot, self.db, guild_id,
            member.id, game, row["account_identifier"], "rejected",
        )

    @discord.slash_command(description="List pending link requests in this server")
    @option("game", str, description="Filter by game key", required=False)
    @discord.default_permissions(manage_roles=True)
    async def pending(self, ctx: discord.ApplicationContext, game: str | None = None) -> None:
        logger.debug("/pending invoked by %s (game=%s)", ctx.author, game)
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
            await ctx.respond("No pending link requests.", ephemeral=True)
            return

        lines = [
            f"<@{r['member_id']}> — **{r['game']}** (`{r['account_identifier']}`)"
            for r in rows
        ]
        await ctx.respond("**Pending link requests:**\n" + "\n".join(lines), ephemeral=True)


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    bot.add_cog(ApproveCommands(bot, db))
