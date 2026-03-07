from __future__ import annotations

import logging
from typing import Any

from dm4z_bot.services.aoe2_api import Aoe2Api

logger = logging.getLogger(__name__)


class Aoe2Service:
    game_key: str = "aoe2"
    display_name: str = "Age of Empires II"

    def __init__(self, api: Aoe2Api | None = None) -> None:
        self.api = api or Aoe2Api()

    async def fetch_stats(self, account_identifier: str) -> dict[str, Any]:
        logger.debug("Fetching AoE2 stats for account: %s", account_identifier)
        profile = await self.api.fetch_profile(account_identifier)
        logger.debug("AoE2 profile fetched for %s", account_identifier)
        return profile

    async def validate_account(self, account_identifier: str) -> str | None:
        logger.debug("Validating AoE2 account: %s", account_identifier)
        try:
            profile = await self.api.fetch_profile(account_identifier)
            name = profile.get("name")
            logger.debug("AoE2 account validated: %s (name=%s)", account_identifier, name)
            return name or account_identifier
        except Exception:
            logger.debug("AoE2 account validation failed: %s", account_identifier)
            return None
