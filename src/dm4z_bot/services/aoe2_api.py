from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from dm4z_bot.utils.constants import (
    DEFAULT_USER_AGENT,
    LEADERBOARD_URL_TEMPLATE,
    NIGHTBOT_API_URL,
    PLAYER_IDS,
)


class PlayerNotFoundError(Exception):
    """Raised when a player is not found in the AoE2 Companion API."""

    def __init__(self, player_name: str, command_type: str) -> None:
        self.player_name = player_name
        self.command_type = command_type
        super().__init__(f"{command_type} for player '{player_name}' not found")


@dataclass(frozen=True)
class Aoe2Api:
    timeout_seconds: float = 10.0

    async def fetch_text(self, url: str) -> str:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException as e:
            raise Exception(f"Request to {url} timed out after {self.timeout_seconds}s") from e
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error {e.response.status_code} from {url}") from e
        except Exception as e:
            raise Exception(f"Failed to fetch data from {url}: {e}") from e

    async def rank(self, player_name: str) -> str:
        response = await self.fetch_text(
            self._build_rank_url(player_name=player_name, leaderboard_id=3)
        )
        if response.strip() == "Player not found":
            raise PlayerNotFoundError(player_name, "Rank information")
        return response

    async def team_rank(self, player_name: str) -> str:
        response = await self.fetch_text(
            self._build_rank_url(player_name=player_name, leaderboard_id=4)
        )
        if response.strip() == "Player not found":
            raise PlayerNotFoundError(player_name, "Team rank information")
        return response

    async def leaderboard(self) -> str:
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

