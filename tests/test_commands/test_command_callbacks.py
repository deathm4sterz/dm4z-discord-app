from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import discord
import pytest

from dm4z_bot.commands.age import AgeCommands
from dm4z_bot.commands.help import HelpCommands
from dm4z_bot.commands.leaderboard import LeaderboardCommands
from dm4z_bot.commands.match_info import MatchInfoCommands
from dm4z_bot.commands.rank import (
    ProfileSelectView,
    RankCommands,
    _build_chart_url,
    build_profile_embeds,
)

SAMPLE_PROFILE: dict[str, Any] = {
    "name": "hjpotter92",
    "clan": "dm4z",
    "profileId": 1228227,
    "country": "de",
    "countryIcon": "\U0001f1e9\U0001f1ea",
    "platformName": "Steam",
    "avatarMediumUrl": "https://example.com/avatar.jpg",
    "leaderboards": [
        {
            "abbreviation": "RM Team",
            "leaderboardId": "rm_team",
            "active": True,
            "games": 632,
            "rating": 1331,
            "maxRating": 1335,
            "rank": 10532,
            "rankCountry": 143,
            "wins": 370,
            "losses": 262,
            "streak": 3,
        },
        {
            "abbreviation": "RM 1v1",
            "leaderboardId": "rm_solo",
            "active": False,
            "games": 10,
            "rating": 1050,
            "maxRating": 1100,
            "rank": 50000,
            "rankCountry": 800,
            "wins": 6,
            "losses": 4,
            "streak": 1,
        },
    ],
}


class FakeContext:
    def __init__(
        self,
        author: object | None = None,
        guild_id: int | None = 12345,
    ) -> None:
        self.author = author or SimpleNamespace(id=999, name="test_user")
        self.guild_id = guild_id
        self.responses: list[dict[str, Any]] = []
        self.followup = self

    async def respond(self, content: str, view: object | None = None) -> None:
        self.responses.append({"content": content, "view": view})

    async def defer(self) -> None:
        pass

    async def send(
        self,
        content: str | None = None,
        *,
        embeds: list[discord.Embed] | None = None,
        view: object | None = None,
    ) -> None:
        self.responses.append({"content": content, "embeds": embeds, "view": view})


class FakeApi:
    async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
        return SAMPLE_PROFILE

    async def search_profiles(self, player_name: str) -> dict[str, Any]:
        return {"profiles": [SAMPLE_PROFILE]}

    async def leaderboard(self) -> str:
        return "leaderboard"


class FakeRegistry:
    def keys(self) -> list[str]:
        return ["cs2", "aoe2"]


class FakeDb:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return self._row


# -- Age tests (unchanged) --


@pytest.mark.asyncio
async def test_age_uses_context_author_when_user_not_provided() -> None:
    author = SimpleNamespace(name="alice", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    ctx = FakeContext(author=author)
    cog = AgeCommands(bot=SimpleNamespace())
    await AgeCommands.age.callback(cog, ctx, None)
    assert ctx.responses[0]["content"] == "alice's account was created at 2024-01-01 00:00:00+00:00"


@pytest.mark.asyncio
async def test_age_uses_selected_user_when_provided() -> None:
    author = SimpleNamespace(name="author", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    user = SimpleNamespace(name="bob", created_at=datetime(2023, 1, 1, tzinfo=UTC))
    ctx = FakeContext(author=author)
    cog = AgeCommands(bot=SimpleNamespace())
    await AgeCommands.age.callback(cog, ctx, user)
    assert ctx.responses[0]["content"] == "bob's account was created at 2023-01-01 00:00:00+00:00"


# -- MatchInfo tests (unchanged) --


@pytest.mark.asyncio
async def test_help_returns_command_reference() -> None:
    ctx = FakeContext()
    cog = HelpCommands(bot=SimpleNamespace(), registry=FakeRegistry())
    await HelpCommands.help.callback(cog, ctx)
    assert "**DM4Z Bot Help**" in ctx.responses[0]["content"]
    assert "/link <game> <account_id>" in ctx.responses[0]["content"]
    assert "`aoe2`" in ctx.responses[0]["content"]
    assert "`cs2`" in ctx.responses[0]["content"]


@pytest.mark.asyncio
async def test_match_info_rejects_invalid_input() -> None:
    ctx = FakeContext()
    cog = MatchInfoCommands(bot=SimpleNamespace())
    await MatchInfoCommands.match_info.callback(cog, ctx, "invalid")
    assert ctx.responses == [{"content": "No 9-digit match ID found in the input.", "view": None}]


@pytest.mark.asyncio
async def test_match_info_returns_buttons_for_valid_input() -> None:
    ctx = FakeContext()
    cog = MatchInfoCommands(bot=SimpleNamespace())
    await MatchInfoCommands.match_info.callback(cog, ctx, "aoe2de://0/123456789")
    assert ctx.responses[0]["content"] == "Extracted Match ID: **123456789**"
    assert ctx.responses[0]["view"] is not None


# -- Leaderboard tests --


@pytest.mark.asyncio
async def test_leaderboard_calls_api_and_responds() -> None:
    ctx = FakeContext()
    cog = LeaderboardCommands(bot=SimpleNamespace(), api=FakeApi())
    await LeaderboardCommands.leaderboard.callback(cog, ctx)
    assert ctx.responses[0]["content"] == "leaderboard"


@pytest.mark.asyncio
async def test_leaderboard_handles_api_errors() -> None:
    class FailingApi:
        async def leaderboard(self) -> str:
            raise Exception("API failed")

    ctx = FakeContext()
    cog = LeaderboardCommands(bot=SimpleNamespace(), api=FailingApi())
    await LeaderboardCommands.leaderboard.callback(cog, ctx)
    assert ctx.responses[0]["content"] == "\u274c Failed to fetch leaderboard data. Please try again later."


# -- Rank command: Case 1 (profile_id lookup) --


@pytest.mark.asyncio
async def test_rank_profile_id_responds_with_embeds() -> None:
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FakeApi(), db=FakeDb())
    await RankCommands.rank.callback(cog, ctx, player_name=None, profile_id=1228227)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1


@pytest.mark.asyncio
async def test_rank_profile_id_not_found() -> None:
    class FailingApi(FakeApi):
        async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
            raise Exception("HTTP error 404")

    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FailingApi(), db=FakeDb())
    await RankCommands.rank.callback(cog, ctx, player_name=None, profile_id=99999)
    resp = ctx.responses[0]
    assert "\u274c No player found with profile ID 99999" in resp["content"]


# -- Rank command: Case 2 (search by player_name) --


@pytest.mark.asyncio
async def test_rank_search_responds_with_select_view() -> None:
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FakeApi(), db=FakeDb())
    await RankCommands.rank.callback(cog, ctx, player_name="hjpotter92", profile_id=None)
    resp = ctx.responses[0]
    assert "Found 1 result(s)" in resp["content"]
    assert resp["view"] is not None


@pytest.mark.asyncio
async def test_rank_search_no_results() -> None:
    class EmptySearchApi(FakeApi):
        async def search_profiles(self, player_name: str) -> dict[str, Any]:
            return {"profiles": []}

    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=EmptySearchApi(), db=FakeDb())
    await RankCommands.rank.callback(cog, ctx, player_name="nobody", profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No players found matching 'nobody'" in resp["content"]


# -- Rank command: Case 3 (linked account) --


@pytest.mark.asyncio
async def test_rank_linked_account_responds_with_embeds() -> None:
    db = FakeDb(row={"account_identifier": "1228227"})
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FakeApi(), db=db)
    await RankCommands.rank.callback(cog, ctx, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1


@pytest.mark.asyncio
async def test_rank_no_linked_account() -> None:
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FakeApi(), db=FakeDb())
    await RankCommands.rank.callback(cog, ctx, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No linked AoE2 account found" in resp["content"]


# -- Rank command: Case 4 (cached stats from DB) --


class NoCallApi(FakeApi):
    async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
        raise AssertionError("API should not be called when cached stats exist")


@pytest.mark.asyncio
async def test_rank_profile_id_uses_cached_stats() -> None:
    cached_row = {"stats_json": json.dumps(SAMPLE_PROFILE), "updated_at": "2025-06-01 12:00:00"}
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=NoCallApi(), db=FakeDb(row=cached_row))
    await RankCommands.rank.callback(cog, ctx, player_name=None, profile_id=1228227)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1
    assert resp["embeds"][0].timestamp == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_rank_linked_account_uses_cached_stats() -> None:
    cached_row = {
        "account_identifier": "1228227",
        "stats_json": json.dumps(SAMPLE_PROFILE),
        "updated_at": "2025-06-01 12:00:00",
    }
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=NoCallApi(), db=FakeDb(row=cached_row))
    await RankCommands.rank.callback(cog, ctx, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1
    assert resp["embeds"][0].timestamp == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


# -- Rank command: Case 5 (general errors) --


@pytest.mark.asyncio
async def test_rank_general_api_error() -> None:
    class FailingSearchApi(FakeApi):
        async def search_profiles(self, player_name: str) -> dict[str, Any]:
            raise Exception("Network error")

    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FailingSearchApi(), db=FakeDb())
    await RankCommands.rank.callback(cog, ctx, player_name="test", profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c Failed to fetch rank details" in resp["content"]


# -- build_profile_embeds unit tests --


def test_build_profile_embeds_header() -> None:
    embeds = build_profile_embeds(SAMPLE_PROFILE)
    header = embeds[0]
    assert header.author.name == "[dm4z] hjpotter92 \U0001f1e9\U0001f1ea"
    assert "Profile ID: 1228227" in header.footer.text


def test_build_profile_embeds_active_and_inactive() -> None:
    embeds = build_profile_embeds(SAMPLE_PROFILE)
    assert len(embeds) == 1
    fields = embeds[0].fields
    assert len(fields) == 2
    assert ":green_circle:" in fields[0].name
    assert ":red_circle:" in fields[1].name


def test_build_profile_embeds_no_clan() -> None:
    profile = {**SAMPLE_PROFILE, "clan": None}
    embeds = build_profile_embeds(profile)
    assert embeds[0].author.name == "hjpotter92 \U0001f1e9\U0001f1ea"


def test_build_profile_embeds_country_flag_fallback() -> None:
    profile = {**SAMPLE_PROFILE, "countryIcon": None, "country": "de"}
    embeds = build_profile_embeds(profile)
    assert ":flag_de:" in embeds[0].author.name


def test_build_profile_embeds_no_country() -> None:
    profile = {**SAMPLE_PROFILE, "countryIcon": None, "country": None}
    embeds = build_profile_embeds(profile)
    assert embeds[0].author.name == "[dm4z] hjpotter92"


def test_build_profile_embeds_skips_zero_games() -> None:
    profile = {
        **SAMPLE_PROFILE,
        "leaderboards": [
            {"abbreviation": "EW", "active": True, "games": 0, "rating": 0},
        ],
    }
    embeds = build_profile_embeds(profile)
    assert len(embeds) == 1


def test_build_profile_embeds_only_active() -> None:
    profile = {
        **SAMPLE_PROFILE,
        "leaderboards": [lb for lb in SAMPLE_PROFILE["leaderboards"] if lb["active"]],
    }
    embeds = build_profile_embeds(profile)
    assert len(embeds) == 1
    assert len(embeds[0].fields) == 1
    assert ":green_circle:" in embeds[0].fields[0].name


def test_build_profile_embeds_only_inactive() -> None:
    profile = {
        **SAMPLE_PROFILE,
        "leaderboards": [lb for lb in SAMPLE_PROFILE["leaderboards"] if not lb["active"]],
    }
    embeds = build_profile_embeds(profile)
    assert len(embeds) == 1
    assert len(embeds[0].fields) == 1
    assert ":red_circle:" in embeds[0].fields[0].name


def test_build_profile_embeds_no_avatar() -> None:
    profile = {**SAMPLE_PROFILE, "avatarMediumUrl": None}
    embeds = build_profile_embeds(profile)
    assert embeds[0].thumbnail is None
    assert embeds[0].author.icon_url is None


def test_build_profile_embeds_timestamp_default() -> None:
    embeds = build_profile_embeds(SAMPLE_PROFILE)
    assert embeds[0].timestamp is not None


def test_build_profile_embeds_timestamp_custom() -> None:
    ts = datetime(2025, 1, 1, tzinfo=UTC)
    embeds = build_profile_embeds(SAMPLE_PROFILE, timestamp=ts)
    assert embeds[0].timestamp == ts


def test_build_profile_embeds_has_chart_image() -> None:
    embeds = build_profile_embeds(SAMPLE_PROFILE)
    assert embeds[0].image is not None
    assert "quickchart.io/chart" in embeds[0].image.url


def test_build_profile_embeds_no_chart_when_no_leaderboards() -> None:
    profile = {**SAMPLE_PROFILE, "leaderboards": []}
    embeds = build_profile_embeds(profile)
    assert embeds[0].image is None


def test_build_chart_url_empty_for_zero_games() -> None:
    leaderboards = [{"abbreviation": "EW", "games": 0, "wins": 0, "losses": 0}]
    assert _build_chart_url(leaderboards) == ""


def test_build_chart_url_contains_labels_and_data() -> None:
    url = _build_chart_url(SAMPLE_PROFILE["leaderboards"])
    assert "quickchart.io/chart" in url
    assert "Wins" in url
    assert "Losses" in url
    assert "Drops" in url
    assert "RM%20Team" in url or "RM+Team" in url


def test_build_chart_url_calculates_drops() -> None:
    leaderboards = [{"abbreviation": "Test", "games": 100, "wins": 60, "losses": 30}]
    url = _build_chart_url(leaderboards)
    assert "60" in url
    assert "30" in url
    assert "10" in url


# -- ProfileSelectView._on_select tests --


class FakeInteractionResponse:
    def __init__(self) -> None:
        self.edited: dict[str, Any] | None = None

    async def edit_message(self, **kwargs: Any) -> None:
        self.edited = kwargs


class FakeInteraction:
    def __init__(self) -> None:
        self.response = FakeInteractionResponse()


@pytest.mark.asyncio
async def test_profile_select_view_on_select_success() -> None:
    view = ProfileSelectView(api=FakeApi(), profiles=[SAMPLE_PROFILE])
    interaction = FakeInteraction()
    view.select._interaction = SimpleNamespace(data={"values": [str(SAMPLE_PROFILE["profileId"])]})
    view.select._selected_values = [str(SAMPLE_PROFILE["profileId"])]
    await view._on_select(interaction)
    assert interaction.response.edited is not None
    assert interaction.response.edited["embeds"] is not None
    assert interaction.response.edited["view"] is None


@pytest.mark.asyncio
async def test_profile_select_view_on_select_error() -> None:
    class FailingApi(FakeApi):
        async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
            raise Exception("API down")

    view = ProfileSelectView(api=FailingApi(), profiles=[SAMPLE_PROFILE])
    interaction = FakeInteraction()
    view.select._interaction = SimpleNamespace(data={"values": [str(SAMPLE_PROFILE["profileId"])]})
    view.select._selected_values = [str(SAMPLE_PROFILE["profileId"])]
    await view._on_select(interaction)
    assert "\u274c Failed to fetch profile" in interaction.response.edited["content"]
