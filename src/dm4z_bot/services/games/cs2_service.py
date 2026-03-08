from __future__ import annotations

import logging
from typing import Any

import httpx

from dm4z_bot.utils.constants import (
    DEFAULT_USER_AGENT,
    LEETIFY_API_KEY_HEADER,
    LEETIFY_BASE_URL,
    LEETIFY_PROFILE_PATH,
)

logger = logging.getLogger(__name__)


class Cs2Service:
    game_key: str = "cs2"
    display_name: str = "Counter-Strike 2"

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 10.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": DEFAULT_USER_AGENT}
        if self.api_key:
            headers[LEETIFY_API_KEY_HEADER] = self.api_key
        return headers

    async def fetch_stats(self, account_identifier: str) -> dict[str, Any]:
        url = f"{LEETIFY_BASE_URL}{LEETIFY_PROFILE_PATH}"
        params = {"steam64_id": account_identifier}
        headers = self._build_headers()
        logger.debug("HTTP GET %s (timeout=%.1fs)", url, self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                logger.debug("HTTP %d from Leetify for %s", response.status_code, account_identifier)
                return response.json()
        except httpx.TimeoutException as e:
            logger.warning("Leetify API timeout after %.1fs for %s", self.timeout_seconds, account_identifier)
            raise Exception(f"CS2 API request timed out after {self.timeout_seconds}s") from e
        except httpx.HTTPStatusError as e:
            logger.warning("Leetify API HTTP %d for %s", e.response.status_code, account_identifier)
            raise Exception(f"CS2 API HTTP error {e.response.status_code}") from e
        except Exception as e:
            if "CS2 API" in str(e):
                raise
            logger.error("Leetify API request failed for %s: %s", account_identifier, e)
            raise Exception(f"Failed to fetch CS2 stats: {e}") from e

    async def validate_account(self, account_identifier: str) -> str | None:
        url = f"{LEETIFY_BASE_URL}{LEETIFY_PROFILE_PATH}"
        params = {"steam64_id": account_identifier}
        headers = self._build_headers()
        logger.debug("Validating CS2 account: %s", account_identifier)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    logger.debug("CS2 account not found (404): %s", account_identifier)
                    return None
                response.raise_for_status()
                data = response.json()
                name = data.get("name", account_identifier)
                logger.debug("CS2 account validated: %s -> %s", account_identifier, name)
                return name
        except Exception:
            logger.warning("CS2 account validation failed for %s", account_identifier)
            return None
