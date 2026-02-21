import pytest

from dm4z_bot.utils.match_reply import build_match_response_text, build_match_view


def test_match_response_text() -> None:
    assert build_match_response_text("123456789") == "Extracted Match ID: **123456789**"


@pytest.mark.asyncio
async def test_match_view_contains_expected_buttons() -> None:
    view = build_match_view("123456789")
    assert len(view.children) == 3
    urls = [button.url for button in view.children]
    assert urls == [
        "https://httpbin.org/redirect-to?url=aoe2de://0/123456789",
        "https://httpbin.org/redirect-to?url=aoe2de://1/123456789",
        "https://www.aoe2insights.com/match/123456789/",
    ]

