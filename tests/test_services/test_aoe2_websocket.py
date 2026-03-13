from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dm4z_bot.services.aoe2_websocket import (
    AOE2_WS_BASE_URL,
    Aoe2WebSocket,
    MatchEvent,
)


def test_match_event_match_id() -> None:
    event = MatchEvent(type="matchAdded", data={"matchId": 123})
    assert event.match_id == 123


def test_build_url_with_profiles() -> None:
    ws = Aoe2WebSocket(profile_ids=["111", "222", "333"])
    url = ws.build_url()
    assert AOE2_WS_BASE_URL in url
    assert "handler=ongoing-matches" in url
    assert "profile_ids=111%2C222%2C333" in url


def test_build_url_empty_profiles() -> None:
    ws = Aoe2WebSocket(profile_ids=[])
    url = ws.build_url()
    assert "profile_ids=" in url


@pytest.mark.asyncio
async def test_listen_yields_connected_event() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])

    match_added = json.dumps([{"type": "matchAdded", "data": {"matchId": 42}}])

    mock_ws_connection = AsyncMock()
    mock_ws_connection.__aiter__ = lambda self: self
    mock_ws_connection.__anext__ = AsyncMock(side_effect=[match_added, StopAsyncIteration()])

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_ws_connection)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.websockets.connect", return_value=mock_cm):
        async for event in ws.listen():
            events.append(event)
            if event.type == "matchAdded":
                ws._closed = True
                break

    assert any(e.type == "__connected__" for e in events)
    assert any(e.type == "matchAdded" and e.match_id == 42 for e in events)


@pytest.mark.asyncio
async def test_listen_yields_match_removed() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])

    match_removed = json.dumps([{"type": "matchRemoved", "data": {"matchId": 99}}])

    mock_ws_connection = AsyncMock()
    mock_ws_connection.__aiter__ = lambda self: self
    mock_ws_connection.__anext__ = AsyncMock(side_effect=[match_removed, StopAsyncIteration()])

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_ws_connection)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.websockets.connect", return_value=mock_cm):
        async for event in ws.listen():
            events.append(event)
            if event.type == "matchRemoved":
                ws._closed = True
                break

    assert any(e.type == "matchRemoved" and e.match_id == 99 for e in events)


@pytest.mark.asyncio
async def test_listen_ignores_unknown_event_types() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])

    unknown_event = json.dumps([{"type": "somethingElse", "data": {}}])

    mock_ws_connection = AsyncMock()
    mock_ws_connection.__aiter__ = lambda self: self
    mock_ws_connection.__anext__ = AsyncMock(side_effect=[unknown_event, StopAsyncIteration()])

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_ws_connection)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.websockets.connect", return_value=mock_cm):
        async for event in ws.listen():
            events.append(event)
            if event.type == "__connected__":
                ws._closed = True

    assert not any(e.type == "somethingElse" for e in events)


@pytest.mark.asyncio
async def test_listen_handles_invalid_json() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])

    mock_ws_connection = AsyncMock()
    mock_ws_connection.__aiter__ = lambda self: self
    mock_ws_connection.__anext__ = AsyncMock(side_effect=["not json", StopAsyncIteration()])

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_ws_connection)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.websockets.connect", return_value=mock_cm):
        async for event in ws.listen():
            events.append(event)
            if event.type == "__connected__":
                ws._closed = True

    assert all(e.type in ("__connected__",) for e in events)


@pytest.mark.asyncio
async def test_listen_handles_non_list_json() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])

    single_event = json.dumps({"type": "matchAdded", "data": {"matchId": 7}})

    mock_ws_connection = AsyncMock()
    mock_ws_connection.__aiter__ = lambda self: self
    mock_ws_connection.__anext__ = AsyncMock(side_effect=[single_event, StopAsyncIteration()])

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_ws_connection)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.websockets.connect", return_value=mock_cm):
        async for event in ws.listen():
            events.append(event)
            if event.type == "matchAdded":
                ws._closed = True
                break

    assert any(e.type == "matchAdded" and e.match_id == 7 for e in events)


@pytest.mark.asyncio
async def test_listen_no_profiles_waits() -> None:
    ws = Aoe2WebSocket(profile_ids=[])

    async def stop_after_delay():
        await asyncio.sleep(0.1)
        ws._closed = True

    asyncio.create_task(stop_after_delay())

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.side_effect = [None, asyncio.CancelledError()]
        try:
            async for event in ws.listen():
                events.append(event)
        except asyncio.CancelledError:
            pass

    assert events == []


@pytest.mark.asyncio
async def test_listen_reconnects_on_error() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])
    call_count = 0

    def connect_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("fail")
        mock_ws_connection = AsyncMock()
        mock_ws_connection.__aiter__ = lambda self: self
        mock_ws_connection.__anext__ = AsyncMock(side_effect=[StopAsyncIteration()])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_ws_connection)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        return mock_cm

    events: list[MatchEvent] = []
    with (
        patch("dm4z_bot.services.aoe2_websocket.websockets.connect", side_effect=connect_side_effect),
        patch("dm4z_bot.services.aoe2_websocket.asyncio.sleep", new_callable=AsyncMock),
    ):
        async for event in ws.listen():
            events.append(event)
            if event.type == "__connected__":
                ws._closed = True
                break

    assert any(e.type == "__disconnected__" for e in events)


@pytest.mark.asyncio
async def test_close() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])
    mock_ws = MagicMock()
    mock_ws.close = AsyncMock()
    ws._ws = mock_ws

    await ws.close()
    assert ws._closed is True
    mock_ws.close.assert_awaited_once()
    assert ws._ws is None


@pytest.mark.asyncio
async def test_listen_breaks_on_closed_during_exception() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])

    def connect_side_effect(*args, **kwargs):
        ws._closed = True
        raise ConnectionError("fail while closed")

    events: list[MatchEvent] = []
    with patch("dm4z_bot.services.aoe2_websocket.websockets.connect", side_effect=connect_side_effect):
        async for event in ws.listen():
            events.append(event)

    assert not any(e.type == "__disconnected__" for e in events)


@pytest.mark.asyncio
async def test_close_without_active_connection() -> None:
    ws = Aoe2WebSocket(profile_ids=["111"])
    await ws.close()
    assert ws._closed is True
