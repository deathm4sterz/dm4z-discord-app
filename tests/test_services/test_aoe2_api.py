import httpx
import pytest
import respx
from httpx import Response

from dm4z_bot.services.aoe2_api import Aoe2Api


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
        with pytest.raises(httpx.HTTPStatusError):
            await api.fetch_text("https://example.com/error")

