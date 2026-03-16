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
from dm4z_bot.commands.profile import (
    ProfileCommands,
    ProfileSelectView,
    _build_chart_url,
    _fmt,
    _last_match_description,
    _peak_label,
    _signed,
    build_aoe2_profile_embeds,
    build_cs2_profile_embeds,
)

SAMPLE_AOE2_PROFILE: dict[str, Any] = {
    "name": "hjpotter92",
    "clan": "dm4z",
    "profileId": 1228227,
    "country": "in",
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

SAMPLE_CS2_PROFILE: dict[str, Any] = {
    "name": "CVS",
    "steam64_id": "76561198044837598",
    "total_matches": 465,
    "winrate": 0.2593,
    "bans": [],
    "ranks": {"leetify": -5.83, "premier": None, "faceit_elo": None},
    "rating": {
        "aim": 1.3903,
        "positioning": 20.3269,
        "utility": 33.5656,
        "clutch": 0.0755,
        "opening": -0.0839,
        "ct_leetify": -0.0603,
        "t_leetify": -0.0561,
    },
    "stats": {
        "ct_opening_duel_success_percentage": 19.7074,
        "t_opening_duel_success_percentage": 13.3102,
        "flashbang_hit_foe_per_flashbang": 0.6655,
        "he_foes_damage_avg": 7.959,
        "he_friends_damage_avg": 0.4223,
        "traded_deaths_success_percentage": 43.9395,
        "trade_kills_success_percentage": 38.6428,
        "preaim": 16.6821,
        "reaction_time_ms": 835.6902,
    },
    "recent_matches": [
        {
            "finished_at": "2025-11-09T13:11:26.000Z",
            "outcome": "tie",
            "map_name": "de_dust2",
            "score": [12, 12],
        },
    ],
}


class FakeContext:
    def __init__(
        self,
        author: object | None = None,
        guild_id: int | None = 12345,
        channel_id: int | None = None,
    ) -> None:
        self.author = author or SimpleNamespace(id=999, name="test_user", mention="<@999>")
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.responses: list[dict[str, Any]] = []
        self.followup = self

    async def respond(self, content: str, view: object | None = None, **kwargs: object) -> None:
        self.responses.append({"content": content, "view": view, **kwargs})

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
        return SAMPLE_AOE2_PROFILE

    async def search_profiles(self, player_name: str) -> dict[str, Any]:
        return {"profiles": [SAMPLE_AOE2_PROFILE]}

    async def leaderboard(self) -> str:
        return "leaderboard"


class FakeRegistry:
    def keys(self) -> list[str]:
        return ["cs2", "aoe2"]

    def get(self, game_key: str) -> object | None:
        if game_key == "cs2":
            return FakeCs2Service()
        return None


class FakeCs2Service:
    game_key = "cs2"
    display_name = "Counter-Strike 2"

    async def fetch_stats(self, account_identifier: str) -> dict[str, Any]:
        return SAMPLE_CS2_PROFILE


class FakeDb:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return self._row


# -- Age tests --


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


# -- Help tests --


@pytest.mark.asyncio
async def test_help_returns_command_reference() -> None:
    ctx = FakeContext()
    cog = HelpCommands(bot=SimpleNamespace(), registry=FakeRegistry())
    await HelpCommands.help.callback(cog, ctx)
    assert "**DM4Z Bot Help**" in ctx.responses[0]["content"]
    assert "/link <game> <account_id>" in ctx.responses[0]["content"]
    assert "`aoe2`" in ctx.responses[0]["content"]
    assert "`cs2`" in ctx.responses[0]["content"]


# -- MatchInfo tests --


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


# -- Profile command: channel resolution --


def _make_cog(db: object | None = None, api: object | None = None, registry: object | None = None) -> ProfileCommands:
    return ProfileCommands(
        bot=SimpleNamespace(),
        db=db or FakeDb(),
        api=api or FakeApi(),
        registry=registry or FakeRegistry(),
    )


@pytest.mark.asyncio
async def test_profile_rejects_non_game_channel() -> None:
    ctx = FakeContext(channel_id=999)
    cog = _make_cog()
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    assert ctx.responses[0]["content"].startswith("\u274c")
    assert ctx.responses[0].get("ephemeral") is True


# -- Profile command: AoE2 via profile_id --


@pytest.mark.asyncio
async def test_profile_aoe2_by_id_responds_with_embeds() -> None:
    db = FakeDb(row={"game": "aoe2"})
    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=db)
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id="1228227")
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1


@pytest.mark.asyncio
async def test_profile_aoe2_by_id_not_found() -> None:
    class FailingApi(FakeApi):
        async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
            raise Exception("HTTP error 404")

    db = FakeDb(row={"game": "aoe2"})
    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=db, api=FailingApi())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id="99999")
    resp = ctx.responses[0]
    assert "\u274c No player found with profile ID 99999" in resp["content"]


# -- Profile command: AoE2 via search --


@pytest.mark.asyncio
async def test_profile_aoe2_search_responds_with_select_view() -> None:
    db = FakeDb(row={"game": "aoe2"})
    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=db)
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name="hjpotter92", profile_id=None)
    resp = ctx.responses[0]
    assert "Found 1 result(s)" in resp["content"]
    assert resp["view"] is not None


@pytest.mark.asyncio
async def test_profile_aoe2_search_no_results() -> None:
    class EmptySearchApi(FakeApi):
        async def search_profiles(self, player_name: str) -> dict[str, Any]:
            return {"profiles": []}

    db = FakeDb(row={"game": "aoe2"})
    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=db, api=EmptySearchApi())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name="nobody", profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No players found matching 'nobody'" in resp["content"]


# -- Profile command: AoE2 via linked account --


@pytest.mark.asyncio
async def test_profile_aoe2_linked_account_responds_with_embeds() -> None:
    class LinkedDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "aoe2"}
            return {"account_identifier": "1228227", "stats_json": None, "updated_at": None}

    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=LinkedDb())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1


@pytest.mark.asyncio
async def test_profile_aoe2_no_linked_account() -> None:
    class NoLinkedDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "aoe2"}
            return None

    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=NoLinkedDb())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No linked AoE2 account found" in resp["content"]


# -- Profile command: AoE2 cached stats --


class NoCallApi(FakeApi):
    async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
        raise AssertionError("API should not be called when cached stats exist")


@pytest.mark.asyncio
async def test_profile_aoe2_by_id_uses_cached_stats() -> None:
    class CachedDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "aoe2"}
            return {"stats_json": json.dumps(SAMPLE_AOE2_PROFILE), "updated_at": "2025-06-01 12:00:00"}

    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=CachedDb(), api=NoCallApi())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id="1228227")
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert resp["embeds"][0].timestamp == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_profile_aoe2_linked_uses_cached_stats() -> None:
    class CachedLinkedDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "aoe2"}
            return {
                "account_identifier": "1228227",
                "stats_json": json.dumps(SAMPLE_AOE2_PROFILE),
                "updated_at": "2025-06-01 12:00:00",
            }

    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=CachedLinkedDb(), api=NoCallApi())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert resp["embeds"][0].timestamp == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


# -- Profile command: general error --


@pytest.mark.asyncio
async def test_profile_general_api_error() -> None:
    class FailingSearchApi(FakeApi):
        async def search_profiles(self, player_name: str) -> dict[str, Any]:
            raise Exception("Network error")

    db = FakeDb(row={"game": "aoe2"})
    ctx = FakeContext(channel_id=100)
    cog = _make_cog(db=db, api=FailingSearchApi())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name="test", profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c Failed to fetch profile details" in resp["content"]


# -- Profile command: CS2 via profile_id --


@pytest.mark.asyncio
async def test_profile_cs2_by_id_responds_with_embeds() -> None:
    db = FakeDb(row={"game": "cs2"})
    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=db)
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id="76561198044837598")
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert len(resp["embeds"]) == 1
    assert resp["embeds"][0].color.value == 0xF84982


@pytest.mark.asyncio
async def test_profile_cs2_by_id_not_found() -> None:
    class FailingCs2Service:
        game_key = "cs2"
        display_name = "Counter-Strike 2"

        async def fetch_stats(self, account_identifier: str) -> dict[str, Any]:
            raise Exception("Not found")

    class FailingRegistry:
        def keys(self) -> list[str]:
            return ["cs2"]

        def get(self, game_key: str) -> object | None:
            return FailingCs2Service() if game_key == "cs2" else None

    db = FakeDb(row={"game": "cs2"})
    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=db, registry=FailingRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id="invalid")
    resp = ctx.responses[0]
    assert "\u274c No CS2 profile found" in resp["content"]


@pytest.mark.asyncio
async def test_profile_cs2_service_unavailable() -> None:
    class EmptyRegistry:
        def keys(self) -> list[str]:
            return []

        def get(self, game_key: str) -> object | None:
            return None

    db = FakeDb(row={"game": "cs2"})
    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=db, registry=EmptyRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id="123")
    resp = ctx.responses[0]
    assert "\u274c CS2 service is not available" in resp["content"]


# -- Profile command: CS2 via linked account --


@pytest.mark.asyncio
async def test_profile_cs2_linked_account_responds_with_embeds() -> None:
    class LinkedCs2Db:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "cs2"}
            return {
                "account_identifier": "76561198044837598",
                "stats_json": json.dumps(SAMPLE_CS2_PROFILE),
                "updated_at": "2025-11-10 10:00:00",
            }

    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=LinkedCs2Db())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None
    assert resp["embeds"][0].timestamp == datetime(2025, 11, 10, 10, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_profile_cs2_linked_no_cached_stats_fetches_live() -> None:
    class NoStatsCs2Db:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "cs2"}
            return {
                "account_identifier": "76561198044837598",
                "stats_json": None,
                "updated_at": None,
            }

    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=NoStatsCs2Db())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert resp["embeds"] is not None


@pytest.mark.asyncio
async def test_profile_cs2_linked_no_stats_service_unavailable() -> None:
    class NoStatsDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "cs2"}
            return {"account_identifier": "123", "stats_json": None, "updated_at": None}

    class EmptyRegistry:
        def keys(self) -> list[str]:
            return []

        def get(self, game_key: str) -> object | None:
            return None

    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=NoStatsDb(), registry=EmptyRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c CS2 service is not available" in resp["content"]


@pytest.mark.asyncio
async def test_profile_cs2_no_linked_account() -> None:
    class NoLinkedCs2Db:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "cs2"}
            return None

    ctx = FakeContext(channel_id=200)
    cog = _make_cog(db=NoLinkedCs2Db())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No linked CS2 account found" in resp["content"]


# -- Profile command: generic game fallback --


@pytest.mark.asyncio
async def test_profile_generic_no_service() -> None:
    class EmptyRegistry:
        def keys(self) -> list[str]:
            return []

        def get(self, game_key: str) -> object | None:
            return None

    db = FakeDb(row={"game": "unknown_game"})
    ctx = FakeContext(channel_id=300)
    cog = _make_cog(db=db, registry=EmptyRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No service configured" in resp["content"]


@pytest.mark.asyncio
async def test_profile_generic_no_linked_account() -> None:
    class FakeGenericService:
        game_key = "newgame"
        display_name = "New Game"

    class GenericRegistry:
        def keys(self) -> list[str]:
            return ["newgame"]

        def get(self, game_key: str) -> object | None:
            return FakeGenericService() if game_key == "newgame" else None

    class GenericDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "newgame"}
            return None

    ctx = FakeContext(channel_id=400)
    cog = _make_cog(db=GenericDb(), registry=GenericRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "\u274c No linked New Game account found" in resp["content"]


@pytest.mark.asyncio
async def test_profile_generic_with_cached_stats() -> None:
    class FakeGenericService:
        game_key = "newgame"
        display_name = "New Game"

    class GenericRegistry:
        def keys(self) -> list[str]:
            return ["newgame"]

        def get(self, game_key: str) -> object | None:
            return FakeGenericService() if game_key == "newgame" else None

    class GenericDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "newgame"}
            return {"account_identifier": "acc1", "stats_json": '{"score": 42}'}

    ctx = FakeContext(channel_id=400)
    cog = _make_cog(db=GenericDb(), registry=GenericRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "score: 42" in resp["content"]


@pytest.mark.asyncio
async def test_profile_generic_no_cached_stats() -> None:
    class FakeGenericService:
        game_key = "newgame"
        display_name = "New Game"

    class GenericRegistry:
        def keys(self) -> list[str]:
            return ["newgame"]

        def get(self, game_key: str) -> object | None:
            return FakeGenericService() if game_key == "newgame" else None

    class GenericDb:
        _call = 0

        async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
            self._call += 1
            if self._call == 1:
                return {"game": "newgame"}
            return {"account_identifier": "acc1", "stats_json": None}

    ctx = FakeContext(channel_id=400)
    cog = _make_cog(db=GenericDb(), registry=GenericRegistry())
    await ProfileCommands.profile.callback(cog, ctx, member=None, player_name=None, profile_id=None)
    resp = ctx.responses[0]
    assert "No cached stats" in resp["content"]


# -- build_aoe2_profile_embeds unit tests --


def test_build_aoe2_profile_embeds_header() -> None:
    embeds = build_aoe2_profile_embeds(SAMPLE_AOE2_PROFILE)
    header = embeds[0]
    assert header.author.name == "[dm4z] hjpotter92 \U0001f1e9\U0001f1ea"
    assert "Profile ID: 1228227" in header.footer.text


def test_build_aoe2_profile_embeds_active_and_inactive() -> None:
    embeds = build_aoe2_profile_embeds(SAMPLE_AOE2_PROFILE)
    assert len(embeds) == 1
    fields = embeds[0].fields
    assert len(fields) == 2
    assert ":green_circle:" in fields[0].name
    assert ":red_circle:" in fields[1].name


def test_build_aoe2_profile_embeds_no_clan() -> None:
    profile = {**SAMPLE_AOE2_PROFILE, "clan": None}
    embeds = build_aoe2_profile_embeds(profile)
    assert embeds[0].author.name == "hjpotter92 \U0001f1e9\U0001f1ea"


def test_build_aoe2_profile_embeds_country_flag_fallback() -> None:
    profile = {**SAMPLE_AOE2_PROFILE, "countryIcon": None, "country": "de"}
    embeds = build_aoe2_profile_embeds(profile)
    assert ":flag_de:" in embeds[0].author.name


def test_build_aoe2_profile_embeds_no_country() -> None:
    profile = {**SAMPLE_AOE2_PROFILE, "countryIcon": None, "country": None}
    embeds = build_aoe2_profile_embeds(profile)
    assert embeds[0].author.name == "[dm4z] hjpotter92"


def test_build_aoe2_profile_embeds_skips_zero_games() -> None:
    profile = {
        **SAMPLE_AOE2_PROFILE,
        "leaderboards": [
            {"abbreviation": "EW", "active": True, "games": 0, "rating": 0},
        ],
    }
    embeds = build_aoe2_profile_embeds(profile)
    assert len(embeds) == 1


def test_build_aoe2_profile_embeds_only_active() -> None:
    profile = {
        **SAMPLE_AOE2_PROFILE,
        "leaderboards": [lb for lb in SAMPLE_AOE2_PROFILE["leaderboards"] if lb["active"]],
    }
    embeds = build_aoe2_profile_embeds(profile)
    assert len(embeds) == 1
    assert len(embeds[0].fields) == 1
    assert ":green_circle:" in embeds[0].fields[0].name


def test_build_aoe2_profile_embeds_only_inactive() -> None:
    profile = {
        **SAMPLE_AOE2_PROFILE,
        "leaderboards": [lb for lb in SAMPLE_AOE2_PROFILE["leaderboards"] if not lb["active"]],
    }
    embeds = build_aoe2_profile_embeds(profile)
    assert len(embeds) == 1
    assert len(embeds[0].fields) == 1
    assert ":red_circle:" in embeds[0].fields[0].name


def test_build_aoe2_profile_embeds_no_avatar() -> None:
    profile = {**SAMPLE_AOE2_PROFILE, "avatarMediumUrl": None}
    embeds = build_aoe2_profile_embeds(profile)
    assert embeds[0].thumbnail is None
    assert embeds[0].author.icon_url is None


def test_build_aoe2_profile_embeds_timestamp_default() -> None:
    embeds = build_aoe2_profile_embeds(SAMPLE_AOE2_PROFILE)
    assert embeds[0].timestamp is not None


def test_build_aoe2_profile_embeds_timestamp_custom() -> None:
    ts = datetime(2025, 1, 1, tzinfo=UTC)
    embeds = build_aoe2_profile_embeds(SAMPLE_AOE2_PROFILE, timestamp=ts)
    assert embeds[0].timestamp == ts


def test_build_aoe2_profile_embeds_has_chart_image() -> None:
    embeds = build_aoe2_profile_embeds(SAMPLE_AOE2_PROFILE)
    assert embeds[0].image is not None
    assert "quickchart.io/chart" in embeds[0].image.url


def test_build_aoe2_profile_embeds_no_chart_when_no_leaderboards() -> None:
    profile = {**SAMPLE_AOE2_PROFILE, "leaderboards": []}
    embeds = build_aoe2_profile_embeds(profile)
    assert embeds[0].image is None


def test_build_chart_url_empty_for_zero_games() -> None:
    leaderboards = [{"abbreviation": "EW", "games": 0, "wins": 0, "losses": 0}]
    assert _build_chart_url(leaderboards) == ""


def test_build_chart_url_contains_labels_and_data() -> None:
    url = _build_chart_url(SAMPLE_AOE2_PROFILE["leaderboards"])
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


# -- build_cs2_profile_embeds unit tests --


def test_build_cs2_profile_embeds_fields() -> None:
    embeds = build_cs2_profile_embeds(SAMPLE_CS2_PROFILE)
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.color.value == 0xF84982
    assert embed.author.name == "CVS"
    assert "leetify.com" in embed.author.url
    assert len(embed.fields) == 15
    assert "Steam64: 76561198044837598" in embed.footer.text


def test_build_cs2_profile_embeds_timestamp_custom() -> None:
    ts = datetime(2025, 11, 10, tzinfo=UTC)
    embeds = build_cs2_profile_embeds(SAMPLE_CS2_PROFILE, timestamp=ts)
    assert embeds[0].timestamp == ts


def test_build_cs2_profile_embeds_timestamp_default() -> None:
    embeds = build_cs2_profile_embeds(SAMPLE_CS2_PROFILE)
    assert embeds[0].timestamp is not None


def test_build_cs2_profile_embeds_kd_na_when_zero_deaths() -> None:
    data = {**SAMPLE_CS2_PROFILE, "stats": {**SAMPLE_CS2_PROFILE["stats"], "traded_deaths_success_percentage": 0}}
    embeds = build_cs2_profile_embeds(data)
    kd_field = next(f for f in embeds[0].fields if "KD" in f.name)
    assert kd_field.value == "N/A"


def test_build_cs2_last_match_description() -> None:
    embeds = build_cs2_profile_embeds(SAMPLE_CS2_PROFILE)
    assert "de_dust2" in embeds[0].description
    assert "Tie" in embeds[0].description
    assert "12-12" in embeds[0].description


def test_build_cs2_no_recent_matches() -> None:
    data = {**SAMPLE_CS2_PROFILE, "recent_matches": []}
    embeds = build_cs2_profile_embeds(data)
    assert embeds[0].description == ""


def test_build_cs2_zero_total_matches() -> None:
    data = {**SAMPLE_CS2_PROFILE, "total_matches": 0}
    embeds = build_cs2_profile_embeds(data)
    matches_field = next(f for f in embeds[0].fields if "MATCHES" in f.name)
    assert "__0__" in matches_field.value
    assert "0.0%" in matches_field.value


# -- peak label tests --


def test_peak_label_premier() -> None:
    assert "\U0001f537" in _peak_label({"premier": 15000})


def test_peak_label_faceit_elo() -> None:
    assert "\u26a1" in _peak_label({"premier": None, "faceit_elo": 1800})


def test_peak_label_leetify_fallback() -> None:
    label = _peak_label({"premier": None, "faceit_elo": None, "leetify": -5.83})
    assert "5.83" in label
    assert "Leetify" in label


# -- formatting helper tests --


def test_fmt_none() -> None:
    assert _fmt(None) == "N/A"


def test_fmt_value() -> None:
    assert _fmt(1.3903) == "1.4"
    assert _fmt(1.3903, 2) == "1.39"


def test_signed_none() -> None:
    assert _signed(None) == "N/A"


def test_signed_positive() -> None:
    assert _signed(0.08) == "+0.08"


def test_signed_negative() -> None:
    assert _signed(-0.08) == "-0.08"


# -- _last_match_description tests --


def test_last_match_description_empty() -> None:
    assert _last_match_description([]) == ""


def test_last_match_description_bad_date() -> None:
    desc = _last_match_description([{"map_name": "de_dust2", "outcome": "win", "score": [13, 7], "finished_at": "bad"}])
    assert "de_dust2" in desc
    assert "Win" in desc


def test_last_match_description_no_finished_at() -> None:
    desc = _last_match_description([{"map_name": "de_dust2", "outcome": "loss", "score": [3, 13], "finished_at": ""}])
    assert "de_dust2" in desc
    assert "Loss" in desc


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
    view = ProfileSelectView(api=FakeApi(), profiles=[SAMPLE_AOE2_PROFILE])
    interaction = FakeInteraction()
    view.select._interaction = SimpleNamespace(data={"values": [str(SAMPLE_AOE2_PROFILE["profileId"])]})
    view.select._selected_values = [str(SAMPLE_AOE2_PROFILE["profileId"])]
    await view._on_select(interaction)
    assert interaction.response.edited is not None
    assert interaction.response.edited["embeds"] is not None
    assert interaction.response.edited["view"] is None


@pytest.mark.asyncio
async def test_profile_select_view_on_select_error() -> None:
    class FailingApi(FakeApi):
        async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
            raise Exception("API down")

    view = ProfileSelectView(api=FailingApi(), profiles=[SAMPLE_AOE2_PROFILE])
    interaction = FakeInteraction()
    view.select._interaction = SimpleNamespace(data={"values": [str(SAMPLE_AOE2_PROFILE["profileId"])]})
    view.select._selected_values = [str(SAMPLE_AOE2_PROFILE["profileId"])]
    await view._on_select(interaction)
    assert "\u274c Failed to fetch profile" in interaction.response.edited["content"]
