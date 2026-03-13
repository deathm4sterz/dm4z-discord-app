from __future__ import annotations

import logging
from typing import cast

import discord

from dm4z_bot.services.games.registry import GameRegistry

logger = logging.getLogger(__name__)


class HelpCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, registry: GameRegistry) -> None:
        self.bot = bot
        self.registry = registry

    @discord.slash_command(description="Show command reference and getting started tips")
    async def help(self, ctx: discord.ApplicationContext) -> None:
        logger.debug("/help invoked by %s", ctx.author)

        game_keys = ", ".join(f"`{key}`" for key in sorted(self.registry.keys()))
        message = "\n".join(
            [
                "**DM4Z Bot Help**",
                "",
                "**Getting started**",
                "• `/link <game> <account_id>` Link your account for approval",
                "• `/profile [member]` Show linked accounts and latest stats",
                "• `/stats <game> [member]` Show latest cached stats",
                "• `/rank [player_name] [profile_id]` Look up AoE2 ranked data",
                "• `/leaderboard` Show the server leaderboard",
                "• `/match_info <link_or_match_id>` Extract a match id and quick links",
                "• `/age [user]` Show Discord account creation date",
                "",
                "**Server setup**",
                "• `/register_game <game> <channel>` Register a game feed in this server",
                "• `/disable_game <game>` Disable a configured game feed",
                "• `/set_mod_channel <channel>` Set approval notifications channel",
                "• `/approve <member> <game>` Approve a pending link request",
                "• `/reject <member> <game>` Reject a pending link request",
                "• `/pending [game]` List pending approvals",
                "",
                "**Match tracking**",
                "• `/enable_tracking <game> <member>` Enable live match tracking (mod-only)",
                "• `/disable_tracking <game> <member>` Disable live match tracking (mod-only)",
                "• `/tracked [game]` List tracked members (mod-only)",
                "",
                f"**Supported game keys:** {game_keys or '`none`'}",
                "Tip: start with `/link`, then use `/profile` or `/stats` once approved.",
            ]
        )
        await ctx.respond(message, ephemeral=True)


def setup(bot: discord.Bot) -> None:
    registry = cast(GameRegistry, bot.game_registry)
    bot.add_cog(HelpCommands(bot, registry))
