from __future__ import annotations

from dm4z_bot.services.games.base import GameService


class ConcreteService:
    game_key = "test"
    display_name = "Test"

    async def fetch_stats(self, account_identifier: str) -> dict:
        return {}

    async def validate_account(self, account_identifier: str) -> str | None:
        return account_identifier


def test_protocol_isinstance_check() -> None:
    svc = ConcreteService()
    assert isinstance(svc, GameService)


def test_protocol_rejects_non_conforming() -> None:
    class BadService:
        pass

    assert not isinstance(BadService(), GameService)
