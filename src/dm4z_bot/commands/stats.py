from __future__ import annotations

import json
import logging
from typing import cast

import discord
from discord import option

from dm4z_bot.database.db import Database
from dm4z_bot.services.games.registry import GameRegistry

logger = logging.getLogger(__name__)


class StatsCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, db: Database, registry: GameRegistry) -> None:
        self.bot = bot
        self.db = db
        self.registry = registry

    @discord.slash_command(description="Show latest cached stats for a game")
    @option("game", str, description="Game key (e.g. aoe2, cs2)")
    @option("member", discord.Member, description="Member to look up", required=False)
    async def stats(
        self, ctx: discord.ApplicationContext, game: str, member: discord.Member | None = None
    ) -> None:
        target = member or ctx.author
        guild_id = ctx.guild_id

        row = await self.db.fetch_one(
            "SELECT ga.id, ga.display_name, ga.account_identifier, gs.stats_json "
            "FROM game_accounts ga "
            "LEFT JOIN game_stats gs ON gs.game_account_id = ga.id "
            "AND gs.id = (SELECT MAX(gs2.id) FROM game_stats gs2 WHERE gs2.game_account_id = ga.id) "
            "WHERE ga.member_id = ? AND ga.guild_id = ? AND ga.game = ? AND ga.status = 'approved'",
            (target.id, guild_id, game),
        )

        if not row:
            await ctx.respond(f"❌ No approved **{game}** account found for {target.mention}.")
            return

        name = row["display_name"] or row["account_identifier"]
        if not row["stats_json"]:
            await ctx.respond(f"**{game}** stats for `{name}`: No data yet. Stats are fetched periodically.")
            return

        stats = json.loads(row["stats_json"])
        summary = "\n".join(f"• **{k}**: {v}" for k, v in stats.items() if v is not None)
        await ctx.respond(f"**{game}** stats for `{name}`:\n{summary}")


def setup(bot: discord.Bot) -> None:
    db = cast(Database, bot.db)
    registry = cast(GameRegistry, bot.game_registry)
    bot.add_cog(StatsCommands(bot, db, registry))
