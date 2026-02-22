import httpx
import pytest
import respx
from httpx import Response

from dm4z_bot.services.aoe2_api import Aoe2Api, PlayerNotFoundError


@pytest.mark.asyncio
async def test_rank_calls_nightbot_api() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        route = router.get(url__regex=r"https://data\.aoe2companion\.com/api/nightbot/rank.*").respond(
            200, text="rank response"
        )
        response = await api.rank("deadmeat")
    assert route.called
    assert response == "rank response"


@pytest.mark.asyncio
async def test_team_rank_calls_nightbot_api() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        route = router.get(url__regex=r"https://data\.aoe2companion\.com/api/nightbot/rank.*").respond(
            200, text="team response"
        )
        response = await api.team_rank("deadmeat")
    assert route.called
    assert response == "team response"


@pytest.mark.asyncio
async def test_leaderboard_formats_text() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get(
            "https://www.aoe2insights.com/nightbot/leaderboard/3/"
            "?user_ids=9997875,6903668,1489563,15625569,2543215,14257193,"
            "15144378,11959979,1228227,5968579&rank=global&limit=5"
        ).respond(200, text="a, b (by aoe2insights.com)")
        response = await api.leaderboard()
    assert response == "a\nb "


@pytest.mark.asyncio
async def test_fetch_text_raises_for_http_errors() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example.com/error").mock(return_value=Response(500))
        with pytest.raises(Exception, match="HTTP error 500 from https://example.com/error"):
            await api.fetch_text("https://example.com/error")


@pytest.mark.asyncio
async def test_fetch_text_raises_for_timeout() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example.com/timeout").mock(side_effect=httpx.TimeoutException("Timeout"))
        with pytest.raises(
            Exception, match="Request to https://example.com/timeout timed out after 10.0s"
        ):
            await api.fetch_text("https://example.com/timeout")


@pytest.mark.asyncio
async def test_fetch_text_raises_for_general_errors() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example.com/error").mock(side_effect=ValueError("Connection error"))
        with pytest.raises(Exception, match="Failed to fetch data from https://example.com/error"):
            await api.fetch_text("https://example.com/error")


@pytest.mark.asyncio
async def test_rank_raises_player_not_found_error() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get(url__regex=r"https://data\.aoe2companion\.com/api/nightbot/rank.*").respond(
            200, text="Player not found"
        )
        with pytest.raises(PlayerNotFoundError) as exc_info:
            await api.rank("nonexistent_player")
        assert exc_info.value.player_name == "nonexistent_player"
        assert exc_info.value.command_type == "Rank information"


@pytest.mark.asyncio
async def test_team_rank_raises_player_not_found_error() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get(url__regex=r"https://data\.aoe2companion\.com/api/nightbot/rank.*").respond(
            200, text="Player not found"
        )
        with pytest.raises(PlayerNotFoundError) as exc_info:
            await api.team_rank("nonexistent_player")
        assert exc_info.value.player_name == "nonexistent_player"
        assert exc_info.value.command_type == "Team rank information"


@pytest.mark.asyncio
async def test_rank_handles_player_not_found_with_whitespace() -> None:
    api = Aoe2Api()
    with respx.mock(assert_all_called=True) as router:
        router.get(url__regex=r"https://data\.aoe2companion\.com/api/nightbot/rank.*").respond(
            200, text="  Player not found  "
        )
        with pytest.raises(PlayerNotFoundError):
            await api.rank("nonexistent_player")

