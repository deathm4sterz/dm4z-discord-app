from __future__ import annotations

from typing import Any

from dm4z_bot.services.aoe2_api import Aoe2Api, PlayerNotFoundError


class Aoe2Service:
    game_key: str = "aoe2"
    display_name: str = "Age of Empires II"

    def __init__(self, api: Aoe2Api | None = None) -> None:
        self.api = api or Aoe2Api()

    async def fetch_stats(self, account_identifier: str) -> dict[str, Any]:
        try:
            rank_text = await self.api.rank(account_identifier)
        except PlayerNotFoundError:
            rank_text = "N/A"
        try:
            team_text = await self.api.team_rank(account_identifier)
        except PlayerNotFoundError:
            team_text = "N/A"
        return {"rank": rank_text, "team_rank": team_text}

    async def validate_account(self, account_identifier: str) -> str | None:
        try:
            await self.api.rank(account_identifier)
            return account_identifier
        except (PlayerNotFoundError, Exception):
            return None
