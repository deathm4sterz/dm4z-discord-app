from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import discord

from dm4z_bot.utils.constants import (
    AOE2_COMPANION_MATCH_URL,
    AOE2_INSIGHTS_MATCH_URL,
    PROFILE_URL,
    SPECTATE_URL,
)

logger = logging.getLogger(__name__)

COLOR_ACTIVE = 0xFFA500
COLOR_WIN = 0x2ECC71
COLOR_LOSS = 0xE74C3C
COLOR_UNKNOWN = 0x95A5A6


def _iso_to_unix(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp())


def _format_duration(started: str, finished: str) -> str:
    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    delta = end_dt - start_dt
    total_seconds = int(delta.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def _player_line(
    player: dict[str, Any],
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
) -> str:
    profile_id = str(player["profileId"])
    name = player.get("name", "Unknown")
    rating = player.get("rating", "?")
    civ_name = player.get("civName", "Unknown")
    civ_key = player.get("civ", "")

    emoji_key = f"aoe2_civ_{civ_key}"
    emoji = app_emojis.get(emoji_key)
    emoji_str = f"{emoji} " if emoji else ""

    profile_link = f"[{name}]({PROFILE_URL.format(profile_id=profile_id)})"

    if profile_id in tracked_profile_ids:
        member_id = member_map.get(profile_id)
        mention = f" (<@{member_id}>)" if member_id else ""
        return f"{emoji_str}{civ_name} **{profile_link}** ({rating}){mention}"

    return f"{emoji_str}{civ_name} {profile_link} ({rating})"


def _build_team_fields(
    players: list[dict[str, Any]],
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
    team_results: dict[int, bool] | None = None,
) -> list[discord.EmbedField]:
    teams: dict[int, list[dict[str, Any]]] = {}
    for player in players:
        team = player.get("team", 0)
        teams.setdefault(team, []).append(player)

    fields = []
    for team_num in sorted(teams):
        team_players = teams[team_num]
        team_name = team_players[0].get("teamName", f"Team {team_num}")

        if team_results is not None:
            won = team_results.get(team_num)
            if won is True:
                team_name = f"🏆 {team_name}"
            elif won is False:
                team_name = f"💀 {team_name}"

        lines = [
            _player_line(p, tracked_profile_ids, member_map, app_emojis)
            for p in team_players
        ]
        fields.append(discord.EmbedField(
            name=team_name,
            value="\n".join(lines),
            inline=False,
        ))

    return fields


def build_active_match_embed(
    match_data: dict[str, Any],
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
) -> discord.Embed:
    map_name = match_data.get("mapName", "Unknown Map")
    leaderboard = match_data.get("leaderboardName", "")
    game_mode = match_data.get("gameModeName", "")
    avg_rating = match_data.get("averageRating", "?")
    server = match_data.get("server", "unknown")
    started = match_data.get("started", "")
    map_image = match_data.get("mapImageUrl")
    players = match_data.get("players", [])

    desc_parts = [p for p in [leaderboard, game_mode, f"Avg Rating: {avg_rating}"] if p]

    embed = discord.Embed(
        title=f"Match in Progress \u2014 {map_name}",
        description=" | ".join(desc_parts),
        color=COLOR_ACTIVE,
    )

    if map_image:
        embed.set_thumbnail(url=map_image)

    for field in _build_team_fields(players, tracked_profile_ids, member_map, app_emojis):
        embed.add_field(name=field.name, value=field.value, inline=field.inline)

    footer_parts = [f"Server: {server}"]
    if started:
        unix_ts = _iso_to_unix(started)
        footer_parts.append(f"Started <t:{unix_ts}:R>")
    embed.set_footer(text=" | ".join(footer_parts))

    return embed


def build_active_match_view(match_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="Spectate",
        style=discord.ButtonStyle.link,
        url=SPECTATE_URL.format(match_id=match_id),
    ))
    view.add_item(discord.ui.Button(
        label="AoE2Companion",
        style=discord.ButtonStyle.link,
        url=AOE2_COMPANION_MATCH_URL.format(match_id=match_id),
    ))
    view.add_item(discord.ui.Button(
        label="AoE2Insights",
        style=discord.ButtonStyle.link,
        url=AOE2_INSIGHTS_MATCH_URL.format(match_id=match_id),
    ))
    return view


def build_finished_match_embed(
    match_data: dict[str, Any],
    result_data: dict[str, Any] | None,
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
) -> discord.Embed:
    map_name = match_data.get("mapName", "Unknown Map")
    leaderboard = match_data.get("leaderboardName", "")
    avg_rating = match_data.get("averageRating", "?")
    started = match_data.get("started", "")
    players = match_data.get("players", [])

    team_results: dict[int, bool] | None = None
    finished = ""
    duration_str = ""
    color = COLOR_UNKNOWN

    if result_data:
        finished = result_data.get("finished", "")
        result_players = result_data.get("players", [])

        if result_players:
            team_results = {}
            for rp in result_players:
                team = rp.get("team", 0)
                won = rp.get("won")
                if won is not None and team not in team_results:
                    team_results[team] = bool(won)

            tracked_teams = set()
            for p in players:
                if str(p["profileId"]) in tracked_profile_ids:
                    tracked_teams.add(p.get("team", 0))

            if tracked_teams:
                tracked_won = any(team_results.get(t) for t in tracked_teams)
                color = COLOR_WIN if tracked_won else COLOR_LOSS

        if finished and started:
            duration_str = _format_duration(started, finished)

    desc_parts = [p for p in [leaderboard] if p]
    if duration_str:
        desc_parts.append(f"Duration: {duration_str}")
    desc_parts.append(f"Avg Rating: {avg_rating}")

    embed = discord.Embed(
        title=f"Match Ended \u2014 {map_name}",
        description=" | ".join(desc_parts),
        color=color,
    )

    map_image = match_data.get("mapImageUrl")
    if map_image:
        embed.set_thumbnail(url=map_image)

    for field in _build_team_fields(players, tracked_profile_ids, member_map, app_emojis, team_results):
        embed.add_field(name=field.name, value=field.value, inline=field.inline)

    footer_parts = []
    if started:
        footer_parts.append(f"Started <t:{_iso_to_unix(started)}:R>")
    if finished:
        footer_parts.append(f"Ended <t:{_iso_to_unix(finished)}:R>")
    else:
        now_ts = int(datetime.now(UTC).timestamp())
        footer_parts.append(f"Ended <t:{now_ts}:R>")
    embed.set_footer(text=" | ".join(footer_parts))

    return embed


def build_finished_match_view(match_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="AoE2Insights",
        style=discord.ButtonStyle.link,
        url=AOE2_INSIGHTS_MATCH_URL.format(match_id=match_id),
    ))
    view.add_item(discord.ui.Button(
        label="AoE2Companion",
        style=discord.ButtonStyle.link,
        url=AOE2_COMPANION_MATCH_URL.format(match_id=match_id),
    ))
    return view
