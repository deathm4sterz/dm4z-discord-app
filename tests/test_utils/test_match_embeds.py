from __future__ import annotations

import pytest

from dm4z_bot.utils.match_embeds import (
    COLOR_ACTIVE,
    COLOR_LOSS,
    COLOR_UNKNOWN,
    COLOR_WIN,
    _build_team_fields,
    _format_duration,
    _iso_to_datetime,
    _player_civ,
    _player_name,
    _player_third_col,
    build_active_match_embed,
    build_active_match_view,
    build_finished_match_embed,
    build_finished_match_view,
)

AI_PLAYER = {
    "profileId": -1,
    "name": "AI Hardest",
    "rating": None,
    "civ": "mongols",
    "civName": "Mongols",
    "civImageUrl": "https://example.com/mongols.png",
    "color": 3,
    "colorHex": "#00FF00",
    "team": 2,
    "teamName": "Team 2",
    "country": "",
    "games": 0,
    "wins": 0,
    "losses": 0,
}

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
    "mapSizeName": "Large",
    "population": 200,
    "players": SAMPLE_PLAYERS,
}


def test_iso_to_datetime() -> None:
    dt = _iso_to_datetime("2026-03-12T08:19:43.000Z")
    assert dt.year == 2026
    assert dt.month == 3
    assert dt.day == 12


def test_format_duration() -> None:
    result = _format_duration("2026-03-12T08:00:00.000Z", "2026-03-12T08:35:20.000Z")
    assert result == "35m 20s"


def test_format_duration_with_hours() -> None:
    result = _format_duration("2026-03-12T08:00:00.000Z", "2026-03-12T09:15:30.000Z")
    assert result == "1h 15m 30s"


def test_player_name_tracked() -> None:
    name = _player_name(SAMPLE_PLAYERS[0], {"1228227"}, {"1228227": 100}, {})
    assert "**" in name
    assert "hjpotter92" in name
    assert "<@100>" in name
    assert ":flag_in:" in name


def test_player_name_not_tracked() -> None:
    name = _player_name(SAMPLE_PLAYERS[1], {"1228227"}, {"1228227": 100}, {})
    assert "**" not in name
    assert "OpponentPlayer" in name
    assert "<@" not in name
    assert ":flag_bd:" in name


def test_player_name_tracked_no_member_map() -> None:
    name = _player_name(SAMPLE_PLAYERS[0], {"1228227"}, {}, {})
    assert "**" in name
    assert "<@" not in name
    assert ":flag_in:" in name


def test_player_name_with_color_emoji() -> None:
    class FakeEmoji:
        def __str__(self) -> str:
            return "<:aoe2_player_2:456>"

    emojis = {"aoe2_player_2": FakeEmoji()}
    name = _player_name(SAMPLE_PLAYERS[0], {"1228227"}, {"1228227": 100}, emojis)
    assert "<:aoe2_player_2:456>" in name
    assert "hjpotter92" in name


def test_player_name_no_color() -> None:
    player = {**SAMPLE_PLAYERS[0], "color": ""}
    name = _player_name(player, {"1228227"}, {"1228227": 100}, {})
    assert "hjpotter92" in name
    assert ":flag_in:" in name


def test_player_name_no_country() -> None:
    player = {**SAMPLE_PLAYERS[0], "country": ""}
    name = _player_name(player, {"1228227"}, {"1228227": 100}, {})
    assert "hjpotter92" in name
    assert ":flag_" not in name


def test_player_civ_with_emoji() -> None:
    class FakeEmoji:
        def __str__(self) -> str:
            return "<:aoe2_civ_sicilians:123>"

    civ = _player_civ(SAMPLE_PLAYERS[0], {"aoe2_civ_sicilians": FakeEmoji()})
    assert "<:aoe2_civ_sicilians:123>" in civ
    assert "[Sicilians](https://aoe2techtree.net/#Sicilians)" in civ


def test_player_civ_no_emoji() -> None:
    civ = _player_civ(SAMPLE_PLAYERS[0], {})
    assert civ == "[Sicilians](https://aoe2techtree.net/#Sicilians)"


def test_player_third_col_active() -> None:
    val = _player_third_col(SAMPLE_PLAYERS[0], 462419759, is_finished=False)
    assert val == "1315"


def test_player_third_col_finished() -> None:
    val = _player_third_col(SAMPLE_PLAYERS[0], 462419759, is_finished=True)
    assert "⬇️" in val
    assert "gameId=462419759" in val
    assert "profileId=1228227" in val


def test_build_team_fields_active() -> None:
    fields = _build_team_fields(
        SAMPLE_PLAYERS, {"1228227"}, {"1228227": 100}, {}, 462419759,
    )
    assert len(fields) == 6
    assert "Team 1" in fields[0].name
    assert fields[1].name == "Civilisation"
    assert fields[2].name == "ELO"
    assert "Team 2" in fields[3].name
    assert all(f.inline for f in fields)


def test_build_team_fields_finished_with_results() -> None:
    fields = _build_team_fields(
        SAMPLE_PLAYERS, {"1228227"}, {"1228227": 100}, {}, 462419759,
        team_results={1: True, 2: False}, is_finished=True,
    )
    assert len(fields) == 6
    assert "🏆" in fields[0].name
    assert fields[2].name == "Replay"
    assert "⬇️" in fields[2].value
    assert "💀" in fields[3].name


def test_build_active_match_embed() -> None:
    embed = build_active_match_embed(
        SAMPLE_MATCH_DATA,
        tracked_profile_ids={"1228227"},
        member_map={"1228227": 100},
        app_emojis={},
    )
    assert embed.title == "Team Random Map on MegaRandom"
    assert "Map: MegaRandom" in embed.description
    assert "Map Size: Large" in embed.description
    assert embed.color.value == COLOR_ACTIVE
    assert len(embed.fields) == 6
    assert embed.fields[0].name == "Team 1"
    assert embed.fields[1].name == "Civilisation"
    assert embed.fields[2].name == "ELO"
    assert embed.thumbnail.url == "https://example.com/megarandom.png"
    assert embed.footer.text == "Server: centralindia"
    assert embed.timestamp is not None


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
    assert embed.title == "Team Random Map on MegaRandom"
    assert embed.color.value == COLOR_WIN
    assert "Map: MegaRandom" in embed.description
    assert "Map Size: Large" in embed.description
    assert "Duration:" in embed.description
    assert embed.footer.text == "Server: centralindia"
    assert embed.timestamp is not None
    assert len(embed.fields) == 6
    assert "🏆" in embed.fields[0].name
    assert embed.fields[2].name == "Replay"
    assert "⬇️" in embed.fields[2].value
    assert "💀" in embed.fields[3].name


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
    assert embed.title == "Team Random Map on MegaRandom"


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
    assert "Duration" not in embed.description
    assert "Server:" in embed.footer.text


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
    assert embed.timestamp is None


def test_build_finished_match_embed_no_map_image() -> None:
    data = {**SAMPLE_MATCH_DATA, "mapImageUrl": None}
    embed = build_finished_match_embed(data, None, set(), {}, {})
    assert embed.thumbnail is None


def test_build_finished_match_embed_no_started() -> None:
    data = {**SAMPLE_MATCH_DATA, "started": ""}
    embed = build_finished_match_embed(data, None, set(), {}, {})
    assert embed.timestamp is None
    assert "Server:" in embed.footer.text


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
    assert "Server:" in embed.footer.text


def test_player_name_ai() -> None:
    name = _player_name(AI_PLAYER, set(), {}, {})
    assert "AI Hardest" in name
    assert "aoe2companion.com" not in name
    assert "[" not in name


def test_player_third_col_finished_ai() -> None:
    val = _player_third_col(AI_PLAYER, 462419759, is_finished=True)
    assert val == "—"
    assert "replay" not in val.lower()


def test_player_third_col_active_ai() -> None:
    val = _player_third_col(AI_PLAYER, 462419759, is_finished=False)
    assert val == "None"


@pytest.mark.asyncio
async def test_build_finished_match_view() -> None:
    view = build_finished_match_view(462419759)
    assert len(view.children) == 2
    labels = [btn.label for btn in view.children]
    assert "AoE2Insights" in labels
    assert "AoE2Companion" in labels
    assert "Spectate" not in labels
