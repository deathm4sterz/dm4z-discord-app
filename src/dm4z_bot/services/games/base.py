from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GameService(Protocol):
    game_key: str
    display_name: str

    async def fetch_stats(self, account_identifier: str) -> dict[str, Any]: ...

    async def validate_account(self, account_identifier: str) -> str | None:
        """Return a display name if the account is valid, None otherwise."""
        ...
