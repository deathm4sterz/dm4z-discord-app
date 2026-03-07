from __future__ import annotations

from dm4z_bot.services.games.registry import GameRegistry


class FakeService:
    game_key = "test"
    display_name = "Test Game"

    async def fetch_stats(self, account_identifier: str) -> dict:
        return {}

    async def validate_account(self, account_identifier: str) -> str | None:
        return account_identifier


def test_register_and_get() -> None:
    registry = GameRegistry()
    svc = FakeService()
    registry.register(svc)
    assert registry.get("test") is svc


def test_get_returns_none_for_unknown() -> None:
    registry = GameRegistry()
    assert registry.get("nope") is None


def test_keys() -> None:
    registry = GameRegistry()
    registry.register(FakeService())
    assert registry.keys() == ["test"]


def test_contains() -> None:
    registry = GameRegistry()
    registry.register(FakeService())
    assert "test" in registry
    assert "nope" not in registry
