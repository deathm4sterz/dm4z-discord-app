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


@dataclass(frozen=True)
class Aoe2Api:
    timeout_seconds: float = 10.0

    async def fetch_text(self, url: str) -> str:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def rank(self, player_name: str) -> str:
        return await self.fetch_text(
            self._build_rank_url(player_name=player_name, leaderboard_id=3)
        )

    async def team_rank(self, player_name: str) -> str:
        return await self.fetch_text(
            self._build_rank_url(player_name=player_name, leaderboard_id=4)
        )

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

