from __future__ import annotations

import pytest

from dm4z_bot.utils.match_embeds import (
    COLOR_ACTIVE,
    COLOR_LOSS,
    COLOR_UNKNOWN,
    COLOR_WIN,
    _build_team_fields,
    _format_duration,
    _iso_to_unix,
    _player_line,
    build_active_match_embed,
    build_active_match_view,
    build_finished_match_embed,
    build_finished_match_view,
)

SAMPLE_PLAYERS = [
    {
        "profileId": 1228227,
        "name": "hjpotter92",
        "rating": 1315,
        "civ": "sicilians",
        "civName": "Sicilians",
        "civImageUrl": "https://example.com/sicilians.png",
        "color": 2,
        "colorHex": "#FF0000",
        "team": 1,
        "teamName": "Team 1",
        "country": "in",
        "games": 3065,
        "wins": 2036,
        "losses": 1029,
    },
    {
        "profileId": 17771111,
        "name": "OpponentPlayer",
        "rating": 1225,
        "civ": "mongols",
        "civName": "Mongols",
        "civImageUrl": "https://example.com/mongols.png",
        "color": 1,
        "colorHex": "#405BFF",
        "team": 2,
        "teamName": "Team 2",
        "country": "bd",
        "games": 334,
        "wins": 168,
        "losses": 166,
    },
]

SAMPLE_MATCH_DATA = {
    "matchId": 462419759,
    "started": "2026-03-12T08:19:43.000Z",
    "finished": None,
    "leaderboardName": "Team Random Map",
    "gameModeName": "Random Map",
    "mapName": "MegaRandom",
    "mapImageUrl": "https://example.com/megarandom.png",
    "server": "centralindia",
    "averageRating": 1255,
    "population": 200,
    "players": SAMPLE_PLAYERS,
}


def test_iso_to_unix() -> None:
    ts = _iso_to_unix("2026-03-12T08:19:43.000Z")
    assert isinstance(ts, int)
    assert ts > 0


def test_format_duration() -> None:
    result = _format_duration("2026-03-12T08:00:00.000Z", "2026-03-12T08:35:20.000Z")
    assert result == "35m 20s"


def test_format_duration_with_hours() -> None:
    result = _format_duration("2026-03-12T08:00:00.000Z", "2026-03-12T09:15:30.000Z")
    assert result == "1h 15m 30s"


def test_player_line_tracked() -> None:
    line = _player_line(
        SAMPLE_PLAYERS[0],
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert "**" in line
    assert "hjpotter92" in line
    assert "1315" in line
    assert "Sicilians" in line
    assert "<@100>" in line


def test_player_line_not_tracked() -> None:
    line = _player_line(
        SAMPLE_PLAYERS[1],
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert "**" not in line or "OpponentPlayer" in line
    assert "<@" not in line


def test_player_line_with_emoji() -> None:
    class FakeEmoji:
        def __str__(self) -> str:
            return "<:aoe2_civ_sicilians:123>"

    fake_emoji = FakeEmoji()
    line = _player_line(
        SAMPLE_PLAYERS[0],
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={"aoe2_civ_sicilians": fake_emoji},
    )
    assert "<:aoe2_civ_sicilians:123>" in line
    assert "Sicilians" in line


def test_player_line_tracked_no_member_map() -> None:
    line = _player_line(
        SAMPLE_PLAYERS[0],
        tracked_profile_ids={"1228227"},
        member_map={},
        app_emojis={},
    )
    assert "**" in line
    assert "<@" not in line


def test_build_team_fields() -> None:
    fields = _build_team_fields(
        SAMPLE_PLAYERS,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert len(fields) == 2
    assert "Team 1" in fields[0].name
    assert "Team 2" in fields[1].name


def test_build_team_fields_with_results() -> None:
    fields = _build_team_fields(
        SAMPLE_PLAYERS,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
        team_results={1: True, 2: False},
    )
    assert "🏆" in fields[0].name
    assert "💀" in fields[1].name


def test_build_active_match_embed() -> None:
    embed = build_active_match_embed(
        SAMPLE_MATCH_DATA,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert "Match in Progress" in embed.title
    assert "MegaRandom" in embed.title
    assert embed.color.value == COLOR_ACTIVE
    assert len(embed.fields) == 2
    assert embed.thumbnail.url == "https://example.com/megarandom.png"
    assert "centralindia" in embed.footer.text


def test_build_active_match_embed_no_map_image() -> None:
    data = {**SAMPLE_MATCH_DATA, "mapImageUrl": None}
    embed = build_active_match_embed(data, set(), {}, {})
    assert embed.thumbnail is None


@pytest.mark.asyncio
async def test_build_active_match_view() -> None:
    view = build_active_match_view(462419759)
    assert len(view.children) == 3
    labels = [btn.label for btn in view.children]
    assert "Spectate" in labels
    assert "AoE2Companion" in labels
    assert "AoE2Insights" in labels


def test_build_finished_match_embed_with_result() -> None:
    result_data = {
        "finished": "2026-03-12T08:55:00.000Z",
        "players": [
            {"profileId": 1228227, "team": 1, "won": True},
            {"profileId": 17771111, "team": 2, "won": False},
        ],
    }
    embed = build_finished_match_embed(
        SAMPLE_MATCH_DATA,
        result_data,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert "Match Ended" in embed.title
    assert embed.color.value == COLOR_WIN
    assert "Duration:" in embed.description
    assert "🏆" in embed.fields[0].name
    assert "💀" in embed.fields[1].name


def test_build_finished_match_embed_tracked_lost() -> None:
    result_data = {
        "finished": "2026-03-12T08:55:00.000Z",
        "players": [
            {"profileId": 1228227, "team": 1, "won": False},
            {"profileId": 17771111, "team": 2, "won": True},
        ],
    }
    embed = build_finished_match_embed(
        SAMPLE_MATCH_DATA,
        result_data,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert embed.color.value == COLOR_LOSS


def test_build_finished_match_embed_no_result() -> None:
    embed = build_finished_match_embed(
        SAMPLE_MATCH_DATA,
        None,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert embed.color.value == COLOR_UNKNOWN
    assert "Match Ended" in embed.title


def test_build_finished_match_embed_result_no_finished() -> None:
    result_data = {
        "finished": "",
        "players": [
            {"profileId": 1228227, "team": 1, "won": True},
        ],
    }
    embed = build_finished_match_embed(
        SAMPLE_MATCH_DATA,
        result_data,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert "Ended" in embed.footer.text


def test_build_finished_match_embed_no_tracked_teams() -> None:
    result_data = {
        "finished": "2026-03-12T08:55:00.000Z",
        "players": [
            {"profileId": 1228227, "team": 1, "won": True},
        ],
    }
    embed = build_finished_match_embed(
        SAMPLE_MATCH_DATA,
        result_data,
        tracked_profile_ids=set(),
        member_map={},
        app_emojis={},
    )
    assert embed.color.value == COLOR_UNKNOWN


def test_build_active_match_embed_no_started() -> None:
    data = {**SAMPLE_MATCH_DATA, "started": ""}
    embed = build_active_match_embed(data, set(), {}, {})
    assert "Server:" in embed.footer.text
    assert "<t:" not in embed.footer.text


def test_build_finished_match_embed_no_map_image() -> None:
    data = {**SAMPLE_MATCH_DATA, "mapImageUrl": None}
    embed = build_finished_match_embed(data, None, set(), {}, {})
    assert embed.thumbnail is None


def test_build_finished_match_embed_no_started() -> None:
    data = {**SAMPLE_MATCH_DATA, "started": ""}
    embed = build_finished_match_embed(data, None, set(), {}, {})
    assert "Started" not in (embed.footer.text if embed.footer else "")


def test_build_finished_match_embed_won_is_none() -> None:
    result_data = {
        "finished": "2026-03-12T08:55:00.000Z",
        "players": [
            {"profileId": 1228227, "team": 1, "won": None},
            {"profileId": 1228227, "team": 1, "won": True},
        ],
    }
    embed = build_finished_match_embed(
        SAMPLE_MATCH_DATA,
        result_data,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert embed.color.value == COLOR_WIN


def test_build_finished_match_embed_empty_footer() -> None:
    data = {**SAMPLE_MATCH_DATA, "started": ""}
    result_data = {
        "finished": "",
        "players": [],
    }
    embed = build_finished_match_embed(data, result_data, set(), {}, {})
    assert embed.footer is not None


@pytest.mark.asyncio
async def test_build_finished_match_view() -> None:
    view = build_finished_match_view(462419759)
    assert len(view.children) == 2
    labels = [btn.label for btn in view.children]
    assert "AoE2Insights" in labels
    assert "AoE2Companion" in labels
    assert "Spectate" not in labels
