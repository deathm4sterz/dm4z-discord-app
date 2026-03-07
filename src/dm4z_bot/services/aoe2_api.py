from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from dm4z_bot.utils.constants import (
    DEFAULT_USER_AGENT,
    LEADERBOARD_URL_TEMPLATE,
    NIGHTBOT_API_URL,
    PLAYER_IDS,
    PROFILE_API_URL,
)

logger = logging.getLogger(__name__)


class PlayerNotFoundError(Exception):
    """Raised when a player is not found in the AoE2 Companion API."""

    def __init__(self, player_name: str, command_type: str) -> None:
        self.player_name = player_name
        self.command_type = command_type
        super().__init__(f"{command_type} for player '{player_name}' not found")


@dataclass(frozen=True)
class Aoe2Api:
    timeout_seconds: float = 10.0

    async def _request(self, url: str) -> httpx.Response:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        logger.debug("HTTP GET %s (timeout=%.1fs)", url, self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                logger.debug(
                    "HTTP %d from %s (%d bytes)",
                    response.status_code,
                    url,
                    len(response.content),
                )
                return response
        except httpx.TimeoutException as e:
            logger.warning("HTTP timeout after %.1fs: %s", self.timeout_seconds, url)
            raise Exception(f"Request to {url} timed out after {self.timeout_seconds}s") from e
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d from %s", e.response.status_code, url)
            raise Exception(f"HTTP error {e.response.status_code} from {url}") from e
        except Exception as e:
            logger.error("HTTP request failed for %s: %s", url, e)
            raise Exception(f"Failed to fetch data from {url}: {e}") from e

    async def fetch_text(self, url: str) -> str:
        response = await self._request(url)
        return response.text

    async def fetch_json(self, url: str) -> dict[str, Any]:
        response = await self._request(url)
        return response.json()

    async def fetch_profile(self, profile_id: str) -> dict[str, Any]:
        logger.debug("Fetching profile for ID: %s", profile_id)
        query = urlencode({
            "language": "en",
            "extend": "avatar_medium_url,avatar_full_url,last_10_matches_won",
            "page": 1,
        })
        url = f"{PROFILE_API_URL}/{profile_id}?{query}"
        return await self.fetch_json(url)

    async def rank(self, player_name: str) -> str:
        logger.debug("Fetching rank for player: %s", player_name)
        response = await self.fetch_text(
            self._build_rank_url(player_name=player_name, leaderboard_id=3)
        )
        if response.strip() == "Player not found":
            logger.debug("Player not found for rank lookup: %s", player_name)
            raise PlayerNotFoundError(player_name, "Rank information")
        return response

    async def team_rank(self, player_name: str) -> str:
        logger.debug("Fetching team rank for player: %s", player_name)
        response = await self.fetch_text(
            self._build_rank_url(player_name=player_name, leaderboard_id=4)
        )
        if response.strip() == "Player not found":
            logger.debug("Player not found for team rank lookup: %s", player_name)
            raise PlayerNotFoundError(player_name, "Team rank information")
        return response

    async def leaderboard(self) -> str:
        logger.debug("Fetching leaderboard for %d players", len(PLAYER_IDS))
        user_ids = ",".join(PLAYER_IDS)
        text = await self.fetch_text(LEADERBOARD_URL_TEMPLATE.format(user_ids=user_ids))
        return text.replace("(by aoe2insights.com)", "").replace(", ", "\n")

    @staticmethod
    def _build_rank_url(player_name: str, leaderboard_id: int) -> str:
        query = urlencode(
            {
                "leaderboard_id": leaderboard_id,
                "search": player_name,
                "profile_id": 12348548,
                "flag": "true",
            }
        )
        return f"{NIGHTBOT_API_URL}?{query}"

