from __future__ import annotations

import json
import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.database.db import Database

logger = logging.getLogger(__name__)


class ProfileCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    @discord.slash_command(description="Show linked game accounts and latest stats")
    @option("member", discord.Member, description="Member to look up", required=False)
    async def profile(self, ctx: discord.ApplicationContext, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        guild_id = ctx.guild_id

        accounts = await self.db.fetch_all(
            "SELECT ga.game, ga.account_identifier, ga.display_name, ga.status, gs.stats_json "
            "FROM game_accounts ga "
            "LEFT JOIN game_stats gs ON gs.game_account_id = ga.id "
            "AND gs.id = (SELECT MAX(gs2.id) FROM game_stats gs2 WHERE gs2.game_account_id = ga.id) "
            "WHERE ga.member_id = ? AND ga.guild_id = ? AND ga.status = 'approved'",
            (target.id, guild_id),
        )

        if not accounts:
            await ctx.respond(f"{target.mention} has no approved linked accounts.")
            return

        lines: list[str] = [f"**Profile for {target.mention}:**"]
        for acc in accounts:
            name = acc["display_name"] or acc["account_identifier"]
            line = f"• **{acc['game']}**: `{name}`"
            if acc["stats_json"]:
                stats = json.loads(acc["stats_json"])
                summary = ", ".join(f"{k}: {v}" for k, v in stats.items() if v is not None)
                if summary:
                    line += f" — {summary}"
            lines.append(line)

        await ctx.respond("\n".join(lines))


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    bot.add_cog(ProfileCommands(bot, db))
