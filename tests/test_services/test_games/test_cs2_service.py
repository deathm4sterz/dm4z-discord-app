from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from dm4z_bot.services.games.cs2_service import Cs2Service
from dm4z_bot.utils.constants import LEETIFY_BASE_URL, LEETIFY_PROFILE_PATH

PROFILE_URL = f"{LEETIFY_BASE_URL}{LEETIFY_PROFILE_PATH}"

SAMPLE_PROFILE = {
    "name": "PlayerOne",
    "winrate": 0.55,
    "total_matches": 100,
    "ranks": {"leetify": 1.5, "premier": 18000},
    "rating": {"aim": 0.7, "positioning": 0.6, "utility": 0.5},
}


@pytest.mark.asyncio
async def test_fetch_stats_success() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).respond(200, json=SAMPLE_PROFILE)
        stats = await svc.fetch_stats("76561198000000000")
    assert stats == SAMPLE_PROFILE


@pytest.mark.asyncio
async def test_fetch_stats_timeout() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).mock(side_effect=httpx.TimeoutException("Timeout"))
        with pytest.raises(Exception, match="CS2 API request timed out"):
            await svc.fetch_stats("123")


@pytest.mark.asyncio
async def test_fetch_stats_http_error() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).mock(return_value=Response(500))
        with pytest.raises(Exception, match="CS2 API HTTP error 500"):
            await svc.fetch_stats("123")


@pytest.mark.asyncio
async def test_fetch_stats_general_error() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).mock(side_effect=ValueError("bad"))
        with pytest.raises(Exception, match="Failed to fetch CS2 stats"):
            await svc.fetch_stats("123")


@pytest.mark.asyncio
async def test_validate_account_success() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).respond(200, json={"name": "PlayerOne"})
        result = await svc.validate_account("76561198000000000")
    assert result == "PlayerOne"


@pytest.mark.asyncio
async def test_validate_account_404() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).respond(404)
        result = await svc.validate_account("bad")
    assert result is None


@pytest.mark.asyncio
async def test_validate_account_error() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).mock(side_effect=httpx.TimeoutException("t"))
        result = await svc.validate_account("err")
    assert result is None


@pytest.mark.asyncio
async def test_validate_account_missing_name_field() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).respond(200, json={})
        result = await svc.validate_account("x")
    assert result == "x"


@pytest.mark.asyncio
async def test_fetch_stats_reraises_cs2_api_exception() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        router.get(PROFILE_URL).mock(side_effect=Exception("CS2 API custom error"))
        with pytest.raises(Exception, match="CS2 API custom error"):
            await svc.fetch_stats("123")


def test_game_key_and_display_name() -> None:
    svc = Cs2Service()
    assert svc.game_key == "cs2"
    assert svc.display_name == "Counter-Strike 2"


@pytest.mark.asyncio
async def test_api_key_sent_in_header() -> None:
    svc = Cs2Service(api_key="test-key-123")
    with respx.mock(assert_all_called=True) as router:
        route = router.get(PROFILE_URL).respond(200, json=SAMPLE_PROFILE)
        await svc.fetch_stats("76561198000000000")
    request = route.calls[0].request
    assert request.headers["_leetify_key"] == "test-key-123"


@pytest.mark.asyncio
async def test_no_api_key_header_when_none() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        route = router.get(PROFILE_URL).respond(200, json=SAMPLE_PROFILE)
        await svc.fetch_stats("76561198000000000")
    request = route.calls[0].request
    assert "_leetify_key" not in request.headers


@pytest.mark.asyncio
async def test_steam64_id_query_param() -> None:
    svc = Cs2Service()
    with respx.mock(assert_all_called=True) as router:
        route = router.get(PROFILE_URL).respond(200, json=SAMPLE_PROFILE)
        await svc.fetch_stats("76561198000000000")
    request = route.calls[0].request
    assert b"steam64_id=76561198000000000" in request.url.raw_path
