from __future__ import annotations

from typing import Any

import pytest

from dm4z_bot.services.games.aoe2_service import Aoe2Service

SAMPLE_PROFILE: dict[str, Any] = {
    "name": "hjpotter92",
    "profileId": 1228227,
    "country": "in",
    "games": "3046",
    "leaderboards": [
        {
            "leaderboardId": "rm_1v1",
            "rating": 1251,
            "rank": 9565,
            "wins": 66,
            "losses": 47,
        },
        {
            "leaderboardId": "rm_team",
            "rating": 1331,
            "rank": 10599,
            "wins": 370,
            "losses": 262,
        },
    ],
}


class FakeAoe2Api:
    def __init__(self, profile: dict[str, Any] | None = None, *, fail: bool = False) -> None:
        self._profile = profile if profile is not None else SAMPLE_PROFILE
        self._fail = fail

    async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
        if self._fail:
            raise Exception("HTTP error 404")
        return self._profile


@pytest.mark.asyncio
async def test_fetch_stats_returns_full_profile() -> None:
    svc = Aoe2Service(api=FakeAoe2Api())
    stats = await svc.fetch_stats("1228227")
    assert stats is SAMPLE_PROFILE
    assert stats["name"] == "hjpotter92"
    assert len(stats["leaderboards"]) == 2


@pytest.mark.asyncio
async def test_validate_account_returns_name() -> None:
    svc = Aoe2Service(api=FakeAoe2Api())
    result = await svc.validate_account("1228227")
    assert result == "hjpotter92"


@pytest.mark.asyncio
async def test_validate_account_returns_none_on_failure() -> None:
    svc = Aoe2Service(api=FakeAoe2Api(fail=True))
    result = await svc.validate_account("0000")
    assert result is None


@pytest.mark.asyncio
async def test_validate_account_falls_back_to_identifier() -> None:
    profile: dict[str, Any] = {"leaderboards": []}
    svc = Aoe2Service(api=FakeAoe2Api(profile=profile))
    result = await svc.validate_account("12345")
    assert result == "12345"


def test_game_key_and_display_name() -> None:
    svc = Aoe2Service()
    assert svc.game_key == "aoe2"
    assert svc.display_name == "Age of Empires II"


@pytest.mark.asyncio
async def test_default_api_created() -> None:
    svc = Aoe2Service()
    assert svc.api is not None
