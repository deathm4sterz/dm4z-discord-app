from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote

import discord
from discord import option

from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api
from dm4z_bot.services.games.base import GameService
from dm4z_bot.services.games.registry import GameRegistry
from dm4z_bot.utils.constants import (
    LEETIFY_LOGO,
    LEETIFY_PINK,
    LEETIFY_PROFILE_URL,
    PLATFORM_ICONS,
    PROFILE_URL,
)

logger = logging.getLogger(__name__)

_CHART_COLORS = [
    "rgb(54,162,235)",
    "rgb(255,99,132)",
    "rgb(75,192,192)",
    "rgb(255,206,86)",
    "rgb(153,102,255)",
    "rgb(255,159,64)",
]


def _fmt(val: float | int | None, decimals: int = 1) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


def _signed(val: float | int | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:+.2f}"


# ---------------------------------------------------------------------------
# AoE2 embed helpers (moved from rank.py)
# ---------------------------------------------------------------------------


def _build_chart_url(leaderboards: list[dict[str, Any]]) -> str:
    active = [lb for lb in leaderboards if lb.get("games", 0) > 0]
    if not active:
        return ""
    datasets = []
    for i, lb in enumerate(active):
        abbr = lb.get("abbreviation", lb.get("leaderboardId", "?"))
        wins = lb.get("wins", 0)
        losses = lb.get("losses", 0)
        drops = lb.get("games", 0) - wins - losses
        color = _CHART_COLORS[i % len(_CHART_COLORS)]
        datasets.append(
            f"{{label:'{abbr}',data:[{wins},{losses},{drops}],backgroundColor:'{color}'}}"
        )
    ds = ",".join(datasets)
    config = (
        f"{{type:'bar',data:{{labels:['Wins','Losses','Drops'],datasets:[{ds}]}},"
        f"options:{{scales:{{xAxes:[{{stacked:true,ticks:{{fontColor:'#fff'}}}}],"
        f"yAxes:[{{stacked:true,ticks:{{fontColor:'#fff'}}}}]}},"
        f"legend:{{labels:{{fontColor:'#fff'}}}}}}}}"
    )
    return f"https://quickchart.io/chart?c={quote(config)}&w=500&h=200&bkg=%232b2d31"


def _country_flag(profile: dict[str, Any]) -> str:
    if icon := profile.get("countryIcon"):
        return str(icon)
    code = profile.get("country")
    if code and len(code) == 2:
        return f":flag_{code}:"
    return ""


def build_aoe2_profile_embeds(
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

    embed = discord.Embed(description=f"[View on AoE2 Companion]({PROFILE_URL.format(profile_id=profile_id)})")
    if avatar:
        embed.set_author(name=author_text, icon_url=avatar, url=PROFILE_URL.format(profile_id=profile_id))
        embed.set_thumbnail(url=avatar)
    else:
        embed.set_author(name=author_text, url=PROFILE_URL.format(profile_id=profile_id))

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

    chart_url = _build_chart_url(profile.get("leaderboards", []))
    if chart_url:
        embed.set_image(url=chart_url)

    footer_icon = PLATFORM_ICONS.get(platform.lower())
    embed.set_footer(
        text=f"Platform: {platform} | Profile ID: {profile_id}",
        icon_url=footer_icon,
    )
    embed.timestamp = timestamp or datetime.now(UTC)
    return [embed]


# ---------------------------------------------------------------------------
# CS2 embed helpers
# ---------------------------------------------------------------------------


def _peak_label(ranks: dict[str, Any]) -> str:
    premier = ranks.get("premier")
    if premier:
        return f"\U0001f537 {premier:,}"
    faceit_elo = ranks.get("faceit_elo")
    if faceit_elo:
        return f"\u26a1 {faceit_elo}"
    leetify = ranks.get("leetify", 0)
    return f"~{abs(leetify):.2f} (Leetify)"


def _last_match_description(recent_matches: list[dict[str, Any]]) -> str:
    if not recent_matches:
        return ""
    m = recent_matches[0]
    map_name = m.get("map_name", "unknown")
    outcome = (m.get("outcome") or "unknown").capitalize()
    score = m.get("score", [0, 0])
    finished = m.get("finished_at", "")
    date_str = ""
    if finished:
        try:
            dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            date_str = f" ({dt.strftime('%b %d, %Y')})"
        except (ValueError, TypeError):
            pass
    return f"Last match: **{map_name}** \u2014 {outcome} {score[0]}-{score[1]}{date_str}"


def build_cs2_profile_embeds(
    data: dict[str, Any], *, timestamp: datetime | None = None
) -> list[discord.Embed]:
    name = data.get("name", "Unknown")
    steam64_id = data.get("steam64_id", "")
    rating = data.get("rating", {})
    stats = data.get("stats", {})
    ranks = data.get("ranks", {})
    bans = data.get("bans", [])
    total_matches = data.get("total_matches", 0)
    recent_matches = data.get("recent_matches", [])

    avg_rating = (rating.get("ct_leetify", 0) + rating.get("t_leetify", 0)) / 2
    ct_win = round(stats.get("ct_opening_duel_success_percentage", 0))
    t_win = round(stats.get("t_opening_duel_success_percentage", 0))
    party_score = _fmt(stats.get("flashbang_hit_foe_per_flashbang"), 2)
    he_foe = _fmt(stats.get("he_foes_damage_avg"), 1)
    he_friend = _fmt(stats.get("he_friends_damage_avg"), 1)
    he_dmg = f"{he_foe} / {he_friend}"

    ban_count = len(bans) if isinstance(bans, list) else 0
    ban_pct = f"{(ban_count / total_matches * 100):.1f}" if total_matches > 0 else "0.0"

    traded_deaths = stats.get("traded_deaths_success_percentage", 0)
    trade_kills = stats.get("trade_kills_success_percentage", 0)
    kd_ratio = _fmt(trade_kills / traded_deaths, 2) if traded_deaths > 0 else "N/A"

    banned_mates_pct = f"{(ban_count / max(total_matches, 1) * 100):.2f}%"

    leetify_url = LEETIFY_PROFILE_URL.format(steam64_id=steam64_id)
    description = _last_match_description(recent_matches)

    embed = discord.Embed(description=description, color=LEETIFY_PINK)
    embed.set_author(name=name, icon_url=LEETIFY_LOGO, url=leetify_url)

    embed.add_field(name="\U0001f4c8 RATING", value=_signed(avg_rating), inline=True)
    embed.add_field(name="\U0001f3d4\ufe0f PEAK RATING", value=_peak_label(ranks), inline=True)
    embed.add_field(name="\U0001f3c6 WINRATE", value=f"{ct_win}% / {t_win}%", inline=True)

    embed.add_field(name="\U0001f3af AIM", value=_fmt(rating.get("aim")), inline=True)
    embed.add_field(name="\U0001f4cd POSITIONING", value=_fmt(rating.get("positioning")), inline=True)
    embed.add_field(name="\U0001f4d0 PREAIM", value=f"{_fmt(stats.get('preaim'), 2)}\u00b0", inline=True)

    embed.add_field(name="\u2694\ufe0f OPENING", value=_signed(rating.get("opening")), inline=True)
    embed.add_field(name="\U0001f9ca CLUTCH", value=_signed(rating.get("clutch")), inline=True)
    embed.add_field(name="\U0001f480 KD", value=kd_ratio, inline=True)

    embed.add_field(name="\U0001f4a3 UTILITY", value=_fmt(rating.get("utility")), inline=True)
    embed.add_field(name="\U0001f389 PARTY", value=party_score, inline=True)
    embed.add_field(name="\U0001f4a5 AVG HE DMG", value=he_dmg, inline=True)

    embed.add_field(name="\U0001f3ae MATCHES", value=f"__{total_matches}__ / {ban_pct}%", inline=True)
    embed.add_field(name="\u26a1 TIME TO DMG", value=f"{round(stats.get('reaction_time_ms', 0))}ms", inline=True)
    embed.add_field(name="\U0001f6ab BANNED MATES", value=banned_mates_pct, inline=True)

    embed.set_footer(text=f"Steam64: {steam64_id}")
    embed.timestamp = timestamp or datetime.now(UTC)
    return [embed]


# ---------------------------------------------------------------------------
# AoE2 player search select view
# ---------------------------------------------------------------------------


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
            embeds = build_aoe2_profile_embeds(profile)
            await interaction.response.edit_message(content=None, embeds=embeds, view=None)
        except Exception:
            logger.exception("Error fetching profile %s from select", selected_id)
            await interaction.response.edit_message(
                content=f"\u274c Failed to fetch profile for ID {selected_id}.",
                view=None,
            )


# ---------------------------------------------------------------------------
# Profile command cog
# ---------------------------------------------------------------------------


class ProfileCommands(discord.Cog):
    def __init__(
        self,
        bot: discord.Bot,
        db: Database,
        api: Aoe2Api,
        registry: GameRegistry,
    ) -> None:
        self.bot = bot
        self.db = db
        self.api = api
        self.registry = registry

    @discord.slash_command(description="Show game profile for the current channel")
    @option("member", discord.Member, description="Member to look up", required=False)
    @option("player_name", str, description="Player name to search (AoE2 only)", required=False, default=None)
    @option("profile_id", str, description="Profile ID or Steam64 ID to look up", required=False, default=None)
    async def profile(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member | None = None,
        player_name: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        target = member or ctx.author
        logger.debug(
            "/profile invoked by %s for %s (player_name=%s, profile_id=%s)",
            ctx.author, target, player_name, profile_id,
        )

        game_key = await self._resolve_game(ctx)
        if game_key is None:
            return

        logger.debug("Channel %s resolved to game %s", ctx.channel_id, game_key)
        await ctx.defer()

        try:
            if game_key == "aoe2":
                await self._handle_aoe2(ctx, target, player_name, profile_id)
            elif game_key == "cs2":
                await self._handle_cs2(ctx, target, profile_id)
            else:
                await self._handle_generic(ctx, target, game_key)
        except Exception:
            logger.exception("Error in /profile for game %s", game_key)
            await ctx.followup.send("\u274c Failed to fetch profile details. Try again later...")

    async def _resolve_game(self, ctx: discord.ApplicationContext) -> str | None:
        row = await self.db.fetch_one(
            "SELECT game FROM guild_games "
            "WHERE guild_id = ? AND channel_id = ? AND enabled = 1",
            (ctx.guild_id, ctx.channel_id),
        )
        if not row:
            logger.debug("No game channel registered for channel %s in guild %s", ctx.channel_id, ctx.guild_id)
            await ctx.respond(
                "\u274c This command can only be used in a registered game channel. "
                "Use `/register_game` to set one up.",
                ephemeral=True,
            )
            return None
        return row["game"]

    # -- AoE2 handlers -------------------------------------------------------

    async def _handle_aoe2(
        self,
        ctx: discord.ApplicationContext,
        target: discord.Member | Any,
        player_name: str | None,
        profile_id: str | None,
    ) -> None:
        if profile_id is not None:
            await self._aoe2_by_id(ctx, profile_id)
        elif player_name is not None:
            await self._aoe2_search(ctx, player_name)
        else:
            await self._aoe2_linked(ctx, target)

    async def _aoe2_by_id(self, ctx: discord.ApplicationContext, profile_id: str) -> None:
        logger.debug("AoE2 lookup by profile_id=%s", profile_id)
        row = await self.db.fetch_one(
            "SELECT gs.stats_json, gs.updated_at "
            "FROM game_accounts ga "
            "JOIN game_stats gs ON gs.game_account_id = ga.id "
            "WHERE ga.account_identifier = ? AND ga.game = 'aoe2' AND ga.status = 'approved' "
            "ORDER BY gs.updated_at DESC LIMIT 1",
            (profile_id,),
        )
        if row and row.get("stats_json"):
            profile = json.loads(row["stats_json"])
            updated_at = datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC)
            embeds = build_aoe2_profile_embeds(profile, timestamp=updated_at)
            await ctx.followup.send(embeds=embeds)
            return

        try:
            profile = await self.api.fetch_profile(profile_id)
        except Exception:
            logger.debug("AoE2 profile not found for ID: %s", profile_id)
            await ctx.followup.send(f"\u274c No player found with profile ID {profile_id}.")
            return
        embeds = build_aoe2_profile_embeds(profile)
        await ctx.followup.send(embeds=embeds)

    async def _aoe2_search(self, ctx: discord.ApplicationContext, player_name: str) -> None:
        logger.debug("AoE2 search for player_name=%s", player_name)
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

    async def _aoe2_linked(self, ctx: discord.ApplicationContext, target: discord.Member | Any) -> None:
        logger.debug("AoE2 linked account lookup for member %s in guild %s", target.id, ctx.guild_id)
        row = await self.db.fetch_one(
            "SELECT ga.account_identifier, gs.stats_json, gs.updated_at "
            "FROM game_accounts ga "
            "LEFT JOIN game_stats gs ON gs.game_account_id = ga.id "
            "WHERE ga.member_id = ? AND ga.guild_id = ? AND ga.game = 'aoe2' "
            "AND ga.status = 'approved' "
            "ORDER BY gs.updated_at DESC LIMIT 1",
            (target.id, ctx.guild_id),
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
            embeds = build_aoe2_profile_embeds(profile, timestamp=updated_at)
        else:
            profile = await self.api.fetch_profile(row["account_identifier"])
            embeds = build_aoe2_profile_embeds(profile)
        await ctx.followup.send(embeds=embeds)

    # -- CS2 handlers ---------------------------------------------------------

    async def _handle_cs2(
        self,
        ctx: discord.ApplicationContext,
        target: discord.Member | Any,
        profile_id: str | None,
    ) -> None:
        if profile_id is not None:
            await self._cs2_by_id(ctx, profile_id)
        else:
            await self._cs2_linked(ctx, target)

    async def _cs2_by_id(self, ctx: discord.ApplicationContext, steam64_id: str) -> None:
        logger.debug("CS2 lookup by steam64_id=%s", steam64_id)
        service = self.registry.get("cs2")
        if not service:
            await ctx.followup.send("\u274c CS2 service is not available.")
            return
        try:
            data = await service.fetch_stats(steam64_id)
        except Exception:
            logger.debug("CS2 profile not found for Steam64 ID: %s", steam64_id)
            await ctx.followup.send(f"\u274c No CS2 profile found for Steam64 ID {steam64_id}.")
            return
        embeds = build_cs2_profile_embeds(data)
        await ctx.followup.send(embeds=embeds)

    async def _cs2_linked(self, ctx: discord.ApplicationContext, target: discord.Member | Any) -> None:
        logger.debug("CS2 linked account lookup for member %s in guild %s", target.id, ctx.guild_id)
        row = await self.db.fetch_one(
            "SELECT ga.account_identifier, gs.stats_json, gs.updated_at "
            "FROM game_accounts ga "
            "LEFT JOIN game_stats gs ON gs.game_account_id = ga.id "
            "WHERE ga.member_id = ? AND ga.guild_id = ? AND ga.game = 'cs2' "
            "AND ga.status = 'approved' "
            "ORDER BY gs.updated_at DESC LIMIT 1",
            (target.id, ctx.guild_id),
        )
        if not row:
            await ctx.followup.send(
                "\u274c No linked CS2 account found. "
                "Use `/link cs2 <steam64_id>` to link your account, "
                "or provide a `profile_id` (Steam64 ID)."
            )
            return

        if row.get("stats_json"):
            data = json.loads(row["stats_json"])
            updated_at = datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC)
            embeds = build_cs2_profile_embeds(data, timestamp=updated_at)
        else:
            service = self.registry.get("cs2")
            if not service:
                await ctx.followup.send("\u274c CS2 service is not available.")
                return
            data = await service.fetch_stats(row["account_identifier"])
            embeds = build_cs2_profile_embeds(data)
        await ctx.followup.send(embeds=embeds)

    # -- Generic fallback for future games ------------------------------------

    async def _handle_generic(
        self, ctx: discord.ApplicationContext, target: discord.Member | Any, game_key: str,
    ) -> None:
        logger.debug("Generic profile lookup for game %s, member %s", game_key, target.id)
        service: GameService | None = self.registry.get(game_key)
        if not service:
            await ctx.followup.send(f"\u274c No service configured for game `{game_key}`.")
            return

        row = await self.db.fetch_one(
            "SELECT ga.account_identifier, gs.stats_json "
            "FROM game_accounts ga "
            "LEFT JOIN game_stats gs ON gs.game_account_id = ga.id "
            "WHERE ga.member_id = ? AND ga.guild_id = ? AND ga.game = ? "
            "AND ga.status = 'approved' "
            "ORDER BY gs.updated_at DESC LIMIT 1",
            (target.id, ctx.guild_id, game_key),
        )
        if not row:
            await ctx.followup.send(
                f"\u274c No linked {service.display_name} account found for {target.mention}."
            )
            return

        if row.get("stats_json"):
            stats = json.loads(row["stats_json"])
            summary = ", ".join(f"{k}: {v}" for k, v in stats.items() if v is not None)
            await ctx.followup.send(f"**{service.display_name}** stats for {target.mention}:\n{summary or 'No data'}")
        else:
            await ctx.followup.send(f"No cached stats for {target.mention} in {service.display_name}.")


def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    db = cast(Database, bot.db)
    registry = cast(GameRegistry, bot.game_registry)
    bot.add_cog(ProfileCommands(bot, db, api, registry))
