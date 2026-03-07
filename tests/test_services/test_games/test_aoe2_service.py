from __future__ import annotations

import pytest

from dm4z_bot.services.aoe2_api import PlayerNotFoundError
from dm4z_bot.services.games.aoe2_service import Aoe2Service


class FakeAoe2Api:
    def __init__(self, rank_result: str = "rank info", team_result: str = "team info") -> None:
        self._rank_result = rank_result
        self._team_result = team_result

    async def rank(self, player_name: str) -> str:
        if self._rank_result == "__not_found__":
            raise PlayerNotFoundError(player_name, "Rank information")
        return self._rank_result

    async def team_rank(self, player_name: str) -> str:
        if self._team_result == "__not_found__":
            raise PlayerNotFoundError(player_name, "Team rank information")
        return self._team_result


@pytest.mark.asyncio
async def test_fetch_stats_returns_rank_and_team() -> None:
    svc = Aoe2Service(api=FakeAoe2Api())
    stats = await svc.fetch_stats("player1")
    assert stats == {"rank": "rank info", "team_rank": "team info"}


@pytest.mark.asyncio
async def test_fetch_stats_handles_not_found() -> None:
    svc = Aoe2Service(api=FakeAoe2Api(rank_result="__not_found__", team_result="__not_found__"))
    stats = await svc.fetch_stats("nobody")
    assert stats == {"rank": "N/A", "team_rank": "N/A"}


@pytest.mark.asyncio
async def test_validate_account_returns_name() -> None:
    svc = Aoe2Service(api=FakeAoe2Api())
    result = await svc.validate_account("player1")
    assert result == "player1"


@pytest.mark.asyncio
async def test_validate_account_returns_none_for_unknown() -> None:
    svc = Aoe2Service(api=FakeAoe2Api(rank_result="__not_found__"))
    result = await svc.validate_account("nobody")
    assert result is None


def test_game_key_and_display_name() -> None:
    svc = Aoe2Service()
    assert svc.game_key == "aoe2"
    assert svc.display_name == "Age of Empires II"


@pytest.mark.asyncio
async def test_default_api_created() -> None:
    svc = Aoe2Service()
    assert svc.api is not None
