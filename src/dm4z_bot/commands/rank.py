from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

import discord
from discord import option

from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api
from dm4z_bot.utils.constants import PLATFORM_ICONS

logger = logging.getLogger(__name__)

def _country_flag(profile: dict[str, Any]) -> str:
    if icon := profile.get("countryIcon"):
        return str(icon)
    code = profile.get("country")
    if code and len(code) == 2:
        return f":flag_{code}:"
    return ""


def build_profile_embeds(
    profile: dict[str, Any], *, timestamp: datetime | None = None
) -> list[discord.Embed]:
    name = profile.get("name", "Unknown")
    clan = profile.get("clan")
    flag = _country_flag(profile)
    avatar = profile.get("avatarMediumUrl")
    platform = profile.get("platformName", "Unknown")
    profile_id = profile.get("profileId", "?")

    author_text = f"[{clan}] {name}" if clan else name
    if flag:
        author_text = f"{author_text} {flag}"

    embed = discord.Embed()
    if avatar:
        embed.set_author(name=author_text, icon_url=avatar)
        embed.set_thumbnail(url=avatar)
    else:
        embed.set_author(name=author_text)

    for lb in profile.get("leaderboards", []):
        if lb.get("games", 0) == 0:
            continue
        abbr = lb.get("abbreviation", lb.get("leaderboardId", "?"))
        status = ":green_circle:" if lb.get("active") else ":red_circle:"
        value = (
            f"**Rating**\n"
            f"Current: {lb.get('rating', '?')}\n"
            f"Peak: {lb.get('maxRating', '?')}\n\n"
            f"**Rank**\n"
            f"Global: #{lb.get('rank', '?')}\n"
            f"Country: #{lb.get('rankCountry', '?')}\n\n"
            f"**Performance**\n"
            f"Win: {lb.get('wins', 0)}\n"
            f"Loss: {lb.get('losses', 0)}\n"
            f"Streak: {lb.get('streak', 0)}"
        )
        embed.add_field(name=f"{status} {abbr}", value=value, inline=True)

    footer_icon = PLATFORM_ICONS.get(platform.lower())
    embed.set_footer(
        text=f"Platform: {platform} | Profile ID: {profile_id}",
        icon_url=footer_icon,
    )
    embed.timestamp = timestamp or datetime.now(UTC)
    return [embed]


class ProfileSelectView(discord.ui.View):
    def __init__(self, api: Aoe2Api, profiles: list[dict[str, Any]]) -> None:
        super().__init__(timeout=60)
        self.api = api
        options = []
        for p in profiles[:25]:
            clan = p.get("clan")
            name = p.get("name", "Unknown")
            label = f"[{clan}] {name}" if clan else name
            flag = _country_flag(p)
            desc = f"{flag} Games: {p.get('games', '?')} | {p.get('platformName', '')}".strip()
            options.append(discord.SelectOption(
                label=label[:100],
                value=str(p["profileId"]),
                description=desc[:100],
            ))
        self.select = discord.ui.Select(placeholder="Select a player...", options=options)
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        selected_id = self.select.values[0]
        try:
            profile = await self.api.fetch_profile(selected_id)
            embeds = build_profile_embeds(profile)
            await interaction.response.edit_message(content=None, embeds=embeds, view=None)
        except Exception:
            logger.exception("Error fetching profile %s from select", selected_id)
            await interaction.response.edit_message(
                content=f"\u274c Failed to fetch profile for ID {selected_id}.",
                view=None,
            )


class RankCommands(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api, db: Database) -> None:
        self.bot = bot
        self.api = api
        self.db = db

    @discord.slash_command(description="Show player rank stats from AoE2 Companion")
    @option("player_name", str, description="Player name to search", required=False, default=None)
    @option("profile_id", int, description="Exact profile ID to look up", required=False, default=None)
    async def rank(
        self,
        ctx: discord.ApplicationContext,
        player_name: str | None = None,
        profile_id: int | None = None,
    ) -> None:
        logger.debug("/rank invoked by %s (player_name=%s, profile_id=%s)", ctx.author, player_name, profile_id)
        await ctx.defer()

        try:
            if profile_id is not None:
                await self._handle_profile_id(ctx, profile_id)
            elif player_name is not None:
                await self._handle_search(ctx, player_name)
            else:
                await self._handle_linked_account(ctx)
        except Exception:
            logger.exception("Error in /rank")
            await ctx.followup.send("\u274c Failed to fetch rank details. Try again later...")

    async def _handle_profile_id(self, ctx: discord.ApplicationContext, profile_id: int) -> None:
        row = await self.db.fetch_one(
            "SELECT gs.stats_json, gs.updated_at "
            "FROM game_accounts ga "
            "JOIN game_stats gs ON gs.game_account_id = ga.id "
            "WHERE ga.account_identifier = ? AND ga.game = 'aoe2' AND ga.status = 'approved' "
            "ORDER BY gs.updated_at DESC LIMIT 1",
            (str(profile_id),),
        )
        if row and row.get("stats_json"):
            profile = json.loads(row["stats_json"])
            updated_at = datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC)
            embeds = build_profile_embeds(profile, timestamp=updated_at)
            await ctx.followup.send(embeds=embeds)
            return

        try:
            profile = await self.api.fetch_profile(str(profile_id))
        except Exception:
            logger.debug("Profile not found for ID: %s", profile_id)
            await ctx.followup.send(f"\u274c No player found with profile ID {profile_id}.")
            return
        embeds = build_profile_embeds(profile)
        await ctx.followup.send(embeds=embeds)

    async def _handle_search(self, ctx: discord.ApplicationContext, player_name: str) -> None:
        data = await self.api.search_profiles(player_name)
        profiles: list[dict[str, Any]] = data.get("profiles", [])
        if not profiles:
            await ctx.followup.send(f"\u274c No players found matching '{player_name}'.")
            return
        view = ProfileSelectView(self.api, profiles)
        await ctx.followup.send(
            f"Found {len(profiles)} result(s) for **{player_name}**. Select a player:",
            view=view,
        )

    async def _handle_linked_account(self, ctx: discord.ApplicationContext) -> None:
        guild_id = ctx.guild_id
        member_id = ctx.author.id
        row = await self.db.fetch_one(
            "SELECT ga.account_identifier, gs.stats_json, gs.updated_at "
            "FROM game_accounts ga "
            "LEFT JOIN game_stats gs ON gs.game_account_id = ga.id "
            "WHERE ga.member_id = ? AND ga.guild_id = ? AND ga.game = 'aoe2' "
            "AND ga.status = 'approved' "
            "ORDER BY gs.updated_at DESC LIMIT 1",
            (member_id, guild_id),
        )
        if not row:
            await ctx.followup.send(
                "\u274c No linked AoE2 account found. "
                "Use `/link aoe2 <profile_id>` to link your account, "
                "or provide a `player_name` or `profile_id`."
            )
            return

        if row.get("stats_json"):
            profile = json.loads(row["stats_json"])
            updated_at = datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC)
            embeds = build_profile_embeds(profile, timestamp=updated_at)
        else:
            profile = await self.api.fetch_profile(row["account_identifier"])
            embeds = build_profile_embeds(profile)
        await ctx.followup.send(embeds=embeds)


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    db = cast(Database, bot.db)
    bot.add_cog(RankCommands(bot, api, db))
