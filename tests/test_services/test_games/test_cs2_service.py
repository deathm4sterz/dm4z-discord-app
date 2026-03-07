from __future__ import annotations

import json

import httpx
import pytest
import respx
from httpx import Response

from dm4z_bot.services.games.cs2_service import LEETIFY_PROFILE_URL, Cs2Service


@pytest.mark.asyncio
async def test_fetch_stats_success() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="76561198000000000")
    body = json.dumps({"ratings": {"leetifyRating": 1.5}, "gamesPlayed": 100, "winRate": 0.55})
    with respx.mock(assert_all_called=True) as router:
        router.get(url).respond(200, text=body)
        stats = await svc.fetch_stats("76561198000000000")
    assert stats == {"leetify_rating": 1.5, "games_played": 100, "win_rate": 0.55}


@pytest.mark.asyncio
async def test_fetch_stats_timeout() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="123")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(side_effect=httpx.TimeoutException("Timeout"))
        with pytest.raises(Exception, match="CS2 API request timed out"):
            await svc.fetch_stats("123")


@pytest.mark.asyncio
async def test_fetch_stats_http_error() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="123")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=Response(500))
        with pytest.raises(Exception, match="CS2 API HTTP error 500"):
            await svc.fetch_stats("123")


@pytest.mark.asyncio
async def test_fetch_stats_general_error() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="123")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(side_effect=ValueError("bad"))
        with pytest.raises(Exception, match="Failed to fetch CS2 stats"):
            await svc.fetch_stats("123")


@pytest.mark.asyncio
async def test_validate_account_success() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="76561198000000000")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).respond(200, json={"name": "PlayerOne"})
        result = await svc.validate_account("76561198000000000")
    assert result == "PlayerOne"


@pytest.mark.asyncio
async def test_validate_account_404() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="bad")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).respond(404)
        result = await svc.validate_account("bad")
    assert result is None


@pytest.mark.asyncio
async def test_validate_account_error() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="err")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(side_effect=httpx.TimeoutException("t"))
        result = await svc.validate_account("err")
    assert result is None


@pytest.mark.asyncio
async def test_validate_account_missing_name_field() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="x")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).respond(200, json={})
        result = await svc.validate_account("x")
    assert result == "x"


@pytest.mark.asyncio
async def test_fetch_stats_reraises_cs2_api_exception() -> None:
    svc = Cs2Service()
    url = LEETIFY_PROFILE_URL.format(steam_id="123")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(side_effect=Exception("CS2 API custom error"))
        with pytest.raises(Exception, match="CS2 API custom error"):
            await svc.fetch_stats("123")


def test_game_key_and_display_name() -> None:
    svc = Cs2Service()
    assert svc.game_key == "cs2"
    assert svc.display_name == "Counter-Strike 2"
