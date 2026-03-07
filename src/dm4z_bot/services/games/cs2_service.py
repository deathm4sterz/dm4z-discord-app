from __future__ import annotations

import logging
from typing import Any

import httpx

from dm4z_bot.utils.constants import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

LEETIFY_PROFILE_URL = "https://api.leetify.com/api/profile/{steam_id}"


class Cs2Service:
    game_key: str = "cs2"
    display_name: str = "Counter-Strike 2"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def fetch_stats(self, account_identifier: str) -> dict[str, Any]:
        url = LEETIFY_PROFILE_URL.format(steam_id=account_identifier)
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return {
                    "leetify_rating": data.get("ratings", {}).get("leetifyRating"),
                    "games_played": data.get("gamesPlayed"),
                    "win_rate": data.get("winRate"),
                }
        except httpx.TimeoutException as e:
            raise Exception(f"CS2 API request timed out after {self.timeout_seconds}s") from e
        except httpx.HTTPStatusError as e:
            raise Exception(f"CS2 API HTTP error {e.response.status_code}") from e
        except Exception as e:
            if "CS2 API" in str(e):
                raise
            raise Exception(f"Failed to fetch CS2 stats: {e}") from e

    async def validate_account(self, account_identifier: str) -> str | None:
        url = LEETIFY_PROFILE_URL.format(steam_id=account_identifier)
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
                return data.get("name", account_identifier)
        except Exception:
            logger.warning("CS2 account validation failed for %s", account_identifier)
            return None
