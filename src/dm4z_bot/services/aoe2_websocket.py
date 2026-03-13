from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import websockets

logger = logging.getLogger(__name__)

AOE2_WS_BASE_URL = "wss://socket.aoe2companion.com/listen"

MIN_BACKOFF = 1.0
MAX_BACKOFF = 60.0


@dataclass
class MatchEvent:
    type: str
    data: dict[str, Any]

    @property
    def match_id(self) -> int:
        return self.data["matchId"]


@dataclass
class Aoe2WebSocket:
    profile_ids: list[str] = field(default_factory=list)
    _ws: Any = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def build_url(self) -> str:
        params = urlencode({
            "handler": "ongoing-matches",
            "profile_ids": ",".join(self.profile_ids),
        })
        url = f"{AOE2_WS_BASE_URL}?{params}"
        logger.debug("Built WebSocket URL: %s", url)
        return url

    async def listen(self) -> Any:
        """Yield MatchEvent objects from the websocket, reconnecting on failure."""
        backoff = MIN_BACKOFF
        while not self._closed:
            if not self.profile_ids:
                logger.info("No profile IDs to track, waiting...")
                await asyncio.sleep(5.0)
                continue

            url = self.build_url()
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    backoff = MIN_BACKOFF
                    logger.info("WebSocket connected, tracking %d profile(s)", len(self.profile_ids))
                    yield MatchEvent(type="__connected__", data={"profile_count": len(self.profile_ids)})

                    async for raw_message in ws:
                        logger.debug("WS raw message: %s", raw_message[:200] if len(raw_message) > 200 else raw_message)
                        try:
                            events = json.loads(raw_message)
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse WS message: %s", raw_message[:100])
                            continue

                        if not isinstance(events, list):
                            events = [events]

                        for event in events:
                            event_type = event.get("type")
                            event_data = event.get("data", {})
                            if event_type in ("matchAdded", "matchRemoved"):
                                logger.debug(
                            "Yielding event: type=%s matchId=%s",
                            event_type, event_data.get("matchId"),
                        )
                                yield MatchEvent(type=event_type, data=event_data)
                            else:
                                logger.debug("Ignoring WS event type: %s", event_type)

            except asyncio.CancelledError:
                logger.info("WebSocket listen cancelled")
                break
            except Exception:
                if self._closed:
                    break
                logger.exception("WebSocket connection error, reconnecting in %.1fs", backoff)
                yield MatchEvent(type="__disconnected__", data={})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

        logger.info("WebSocket listener stopped")

    async def close(self) -> None:
        self._closed = True
        if self._ws is not None:
            logger.debug("Closing WebSocket connection")
            await self._ws.close()
            self._ws = None
