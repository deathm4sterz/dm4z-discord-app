from __future__ import annotations

import logging
from typing import Any, cast

import discord
from discord import option

from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api

logger = logging.getLogger(__name__)

COLOR_ACTIVE = 0x3498DB
COLOR_INACTIVE = 0x95A5A6


def _country_flag(profile: dict[str, Any]) -> str:
    if icon := profile.get("countryIcon"):
        return str(icon)
    code = profile.get("country")
    if code and len(code) == 2:
        return f":flag_{code}:"
    return ""


def build_profile_embeds(profile: dict[str, Any]) -> list[discord.Embed]:
    name = profile.get("name", "Unknown")
    clan = profile.get("clan")
    flag = _country_flag(profile)
    avatar = profile.get("avatarMediumUrl")
    platform = profile.get("platformName", "Unknown")
    profile_id = profile.get("profileId", "?")

    author_text = f"[{clan}] {name}" if clan else name
    if flag:
        author_text = f"{author_text} {flag}"

    header = discord.Embed(description="\U0001f535 Blue = active season \u2502 \u26aa Gray = inactive season")
    if avatar:
        header.set_author(name=author_text, icon_url=avatar)
    else:
        header.set_author(name=author_text)
    if avatar:
        header.set_thumbnail(url=avatar)
    header.set_footer(text=f"Platform: {platform} | Profile ID: {profile_id}")

    leaderboards: list[dict[str, Any]] = profile.get("leaderboards", [])
    active_fields: list[tuple[str, str]] = []
    inactive_fields: list[tuple[str, str]] = []

    for lb in leaderboards:
        if lb.get("games", 0) == 0:
            continue
        abbr = lb.get("abbreviation", lb.get("leaderboardId", "?"))
        rating = lb.get("rating", "?")
        peak = lb.get("maxRating", "?")
        rank = lb.get("rank", "?")
        country_rank = lb.get("rankCountry", "?")
        wins = lb.get("wins", 0)
        losses = lb.get("losses", 0)
        streak = lb.get("streak", 0)

        value = (
            f"Rating: {rating} | Peak: {peak}\n"
            f"Rank: #{rank} | Country: #{country_rank}\n"
            f"{wins}W-{losses}L | Streak: {streak}"
        )

        if lb.get("active"):
            active_fields.append((abbr, value))
        else:
            inactive_fields.append((abbr, value))

    embeds = [header]

    if active_fields:
        active_embed = discord.Embed(title="Active Leaderboards", color=COLOR_ACTIVE)
        for field_name, field_value in active_fields:
            active_embed.add_field(name=field_name, value=field_value, inline=True)
        embeds.append(active_embed)

    if inactive_fields:
        inactive_embed = discord.Embed(title="Inactive Leaderboards", color=COLOR_INACTIVE)
        for field_name, field_value in inactive_fields:
            inactive_embed.add_field(name=field_name, value=field_value, inline=True)
        embeds.append(inactive_embed)

    return embeds


class ProfileSelectView(discord.ui.View):
    def __init__(self, api: Aoe2Api, profiles: list[dict[str, Any]]) -> None:
        super().__init__(timeout=60)
        self.api = api
        options = []
        for p in profiles[:25]:
            clan = p.get("clan")
            name = p.get("name", "Unknown")
            label = f"[{clan}] {name}" if clan else name
            code = p.get("country")
            flag = f":flag_{code}:" if code and len(code) == 2 else ""
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
            "SELECT account_identifier FROM game_accounts "
            "WHERE member_id = ? AND guild_id = ? AND game = 'aoe2' AND status = 'approved'",
            (member_id, guild_id),
        )
        if not row:
            await ctx.followup.send(
                "\u274c No linked AoE2 account found. "
                "Use `/link aoe2 <profile_id>` to link your account, "
                "or provide a `player_name` or `profile_id`."
            )
            return
        profile = await self.api.fetch_profile(row["account_identifier"])
        embeds = build_profile_embeds(profile)
        await ctx.followup.send(embeds=embeds)


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    db = cast(Database, bot.db)
    bot.add_cog(RankCommands(bot, api, db))
