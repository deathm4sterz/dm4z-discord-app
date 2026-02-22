from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from dm4z_bot.commands.age import AgeCommands
from dm4z_bot.commands.leaderboard import LeaderboardCommands
from dm4z_bot.commands.match_info import MatchInfoCommands
from dm4z_bot.commands.rank import RankCommands
from dm4z_bot.commands.team_rank import TeamRankCommands
from dm4z_bot.services.aoe2_api import PlayerNotFoundError


class FakeContext:
    def __init__(self, author: object | None = None) -> None:
        self.author = author
        self.responses: list[tuple[str, object | None]] = []
        self.followup = self

    async def respond(self, content: str, view: object | None = None) -> None:
        self.responses.append((content, view))

    async def defer(self) -> None:
        pass

    async def send(self, content: str, view: object | None = None) -> None:
        self.responses.append((content, view))


class FakeApi:
    async def rank(self, player_name: str) -> str:
        return f"rank:{player_name}"

    async def team_rank(self, player_name: str) -> str:
        return f"team:{player_name}"

    async def leaderboard(self) -> str:
        return "leaderboard"


@pytest.mark.asyncio
async def test_age_uses_context_author_when_user_not_provided() -> None:
    author = SimpleNamespace(name="alice", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    ctx = FakeContext(author=author)
    cog = AgeCommands(bot=SimpleNamespace())
    await AgeCommands.age.callback(cog, ctx, None)
    assert ctx.responses[0][0] == "alice's account was created at 2024-01-01 00:00:00+00:00"


@pytest.mark.asyncio
async def test_age_uses_selected_user_when_provided() -> None:
    author = SimpleNamespace(name="author", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    user = SimpleNamespace(name="bob", created_at=datetime(2023, 1, 1, tzinfo=UTC))
    ctx = FakeContext(author=author)
    cog = AgeCommands(bot=SimpleNamespace())
    await AgeCommands.age.callback(cog, ctx, user)
    assert ctx.responses[0][0] == "bob's account was created at 2023-01-01 00:00:00+00:00"


@pytest.mark.asyncio
async def test_match_info_rejects_invalid_input() -> None:
    ctx = FakeContext()
    cog = MatchInfoCommands(bot=SimpleNamespace())
    await MatchInfoCommands.match_info.callback(cog, ctx, "invalid")
    assert ctx.responses == [("No 9-digit match ID found in the input.", None)]


@pytest.mark.asyncio
async def test_match_info_returns_buttons_for_valid_input() -> None:
    ctx = FakeContext()
    cog = MatchInfoCommands(bot=SimpleNamespace())
    await MatchInfoCommands.match_info.callback(cog, ctx, "aoe2de://0/123456789")
    assert ctx.responses[0][0] == "Extracted Match ID: **123456789**"
    assert ctx.responses[0][1] is not None


@pytest.mark.asyncio
async def test_rank_calls_api_and_responds() -> None:
    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FakeApi())
    await RankCommands.rank.callback(cog, ctx, "deadmeat")
    assert ctx.responses == [("rank:deadmeat", None)]


@pytest.mark.asyncio
async def test_team_rank_calls_api_and_responds() -> None:
    ctx = FakeContext()
    cog = TeamRankCommands(bot=SimpleNamespace(), api=FakeApi())
    await TeamRankCommands.team_rank.callback(cog, ctx, "deadmeat")
    assert ctx.responses == [("team:deadmeat", None)]


@pytest.mark.asyncio
async def test_leaderboard_calls_api_and_responds() -> None:
    ctx = FakeContext()
    cog = LeaderboardCommands(bot=SimpleNamespace(), api=FakeApi())
    await LeaderboardCommands.leaderboard.callback(cog, ctx)
    assert ctx.responses == [("leaderboard", None)]


@pytest.mark.asyncio
async def test_rank_handles_api_errors() -> None:
    class FailingApi:
        async def rank(self, player_name: str) -> str:
            raise Exception("API failed")

    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=FailingApi())
    await RankCommands.rank.callback(cog, ctx, "deadmeat")
    assert ctx.responses == [("❌ Failed to fetch rank details for 'deadmeat'. Try again later...", None)]


@pytest.mark.asyncio
async def test_team_rank_handles_api_errors() -> None:
    class FailingApi:
        async def team_rank(self, player_name: str) -> str:
            raise Exception("API failed")

    ctx = FakeContext()
    cog = TeamRankCommands(bot=SimpleNamespace(), api=FailingApi())
    await TeamRankCommands.team_rank.callback(cog, ctx, "deadmeat")
    assert ctx.responses == [("❌ Failed to fetch team rank details for 'deadmeat'. Try again later...", None)]


@pytest.mark.asyncio
async def test_leaderboard_handles_api_errors() -> None:
    class FailingApi:
        async def leaderboard(self) -> str:
            raise Exception("API failed")

    ctx = FakeContext()
    cog = LeaderboardCommands(bot=SimpleNamespace(), api=FailingApi())
    await LeaderboardCommands.leaderboard.callback(cog, ctx)
    assert ctx.responses == [("❌ Failed to fetch leaderboard data. Please try again later.", None)]


@pytest.mark.asyncio
async def test_rank_handles_player_not_found_error() -> None:
    class PlayerNotFoundApi:
        async def rank(self, player_name: str) -> str:
            raise PlayerNotFoundError(player_name, "Rank information")

    ctx = FakeContext()
    cog = RankCommands(bot=SimpleNamespace(), api=PlayerNotFoundApi())
    await RankCommands.rank.callback(cog, ctx, "nonexistent_player")
    assert ctx.responses == [("❌ Rank information for player 'nonexistent_player' not found", None)]


@pytest.mark.asyncio
async def test_team_rank_handles_player_not_found_error() -> None:
    class PlayerNotFoundApi:
        async def team_rank(self, player_name: str) -> str:
            raise PlayerNotFoundError(player_name, "Team rank information")

    ctx = FakeContext()
    cog = TeamRankCommands(bot=SimpleNamespace(), api=PlayerNotFoundApi())
    await TeamRankCommands.team_rank.callback(cog, ctx, "nonexistent_player")
    assert ctx.responses == [("❌ Team rank information for player 'nonexistent_player' not found", None)]

