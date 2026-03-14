from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

from dm4z_bot.utils.constants import (
    AOE2_COMPANION_MATCH_URL,
    AOE2_INSIGHTS_MATCH_URL,
    PROFILE_URL,
    REPLAY_URL,
    SPECTATE_URL,
)

logger = logging.getLogger(__name__)

COLOR_ACTIVE = 0xFFA500
COLOR_WIN = 0x2ECC71
COLOR_LOSS = 0xE74C3C
COLOR_UNKNOWN = 0x95A5A6


def _iso_to_datetime(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


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


def _player_name(
    player: dict[str, Any],
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
) -> str:
    profile_id = str(player["profileId"])
    name = player.get("name", "Unknown")
    color = player.get("color", "")
    country = player.get("country", "")
    profile_link = f"[{name}]({PROFILE_URL.format(profile_id=profile_id)})"

    emoji = app_emojis.get(f"aoe2_player_{color}") if color else None
    prefix = f"{emoji} " if emoji else ""
    flag = f" :flag_{country}:" if country else ""

    if profile_id in tracked_profile_ids:
        member_id = member_map.get(profile_id)
        mention = f" (<@{member_id}>)" if member_id else ""
        return f"{prefix}**{profile_link}**{flag}{mention}"

    return f"{prefix}{profile_link}{flag}"


def _player_civ(
    player: dict[str, Any],
    app_emojis: dict[str, discord.Emoji],
) -> str:
    civ_name = player.get("civName", "Unknown")
    civ_key = player.get("civ", "")
    emoji = app_emojis.get(f"aoe2_civ_{civ_key}")
    return f"{emoji} {civ_name}" if emoji else civ_name


def _player_third_col(
    player: dict[str, Any],
    match_id: int,
    *,
    is_finished: bool,
) -> str:
    profile_id = str(player["profileId"])
    if is_finished:
        url = REPLAY_URL.format(match_id=match_id, profile_id=profile_id)
        return f"[⬇️]({url})"
    return str(player.get("rating", "?"))


def _build_team_fields(
    players: list[dict[str, Any]],
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
    match_id: int,
    *,
    team_results: dict[int, bool] | None = None,
    is_finished: bool = False,
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

        names = "\n".join(
            _player_name(p, tracked_profile_ids, member_map, app_emojis)
            for p in team_players
        )
        civs = "\n".join(_player_civ(p, app_emojis) for p in team_players)
        third = "\n".join(
            _player_third_col(p, match_id, is_finished=is_finished) for p in team_players
        )

        fields.append(discord.EmbedField(name=team_name, value=names, inline=True))
        fields.append(discord.EmbedField(name="Civilisation", value=civs, inline=True))
        third_heading = "Replay" if is_finished else "ELO"
        fields.append(discord.EmbedField(name=third_heading, value=third, inline=True))

    return fields


def build_active_match_embed(
    match_data: dict[str, Any],
    tracked_profile_ids: set[str],
    member_map: dict[str, int],
    app_emojis: dict[str, discord.Emoji],
) -> discord.Embed:
    map_name = match_data.get("mapName", "Unknown Map")
    leaderboard = match_data.get("leaderboardName", "Unknown")
    map_size = match_data.get("mapSizeName", "")
    server = match_data.get("server", "unknown")
    started = match_data.get("started", "")
    match_id = match_data.get("matchId", 0)
    map_image = match_data.get("mapImageUrl")
    players = match_data.get("players", [])

    desc_lines = [f"Map: {map_name}"]
    if map_size:
        desc_lines.append(f"Map Size: {map_size}")

    embed = discord.Embed(
        title=f"{leaderboard} on {map_name}",
        description="\n".join(desc_lines),
        color=COLOR_ACTIVE,
    )

    if started:
        embed.timestamp = _iso_to_datetime(started)

    if map_image:
        embed.set_thumbnail(url=map_image)

    for field in _build_team_fields(
        players, tracked_profile_ids, member_map, app_emojis, match_id,
    ):
        embed.add_field(name=field.name, value=field.value, inline=field.inline)

    embed.set_footer(text=f"Server: {server}")

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
    leaderboard = match_data.get("leaderboardName", "Unknown")
    map_size = match_data.get("mapSizeName", "")
    match_id = match_data.get("matchId", 0)
    server = match_data.get("server", "unknown")
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

    desc_lines = [f"Map: {map_name}"]
    if map_size:
        desc_lines.append(f"Map Size: {map_size}")
    if duration_str:
        desc_lines.append(f"Duration: {duration_str}")

    embed = discord.Embed(
        title=f"{leaderboard} on {map_name}",
        description="\n".join(desc_lines),
        color=color,
    )

    if started:
        embed.timestamp = _iso_to_datetime(started)

    map_image = match_data.get("mapImageUrl")
    if map_image:
        embed.set_thumbnail(url=map_image)

    for field in _build_team_fields(
        players, tracked_profile_ids, member_map, app_emojis, match_id,
        team_results=team_results, is_finished=True,
    ):
        embed.add_field(name=field.name, value=field.value, inline=field.inline)

    embed.set_footer(text=f"Server: {server}")

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
