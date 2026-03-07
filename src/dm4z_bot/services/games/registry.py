from __future__ import annotations

from dm4z_bot.services.games.base import GameService


class GameRegistry:
    def __init__(self) -> None:
        self._services: dict[str, GameService] = {}

    def register(self, service: GameService) -> None:
        self._services[service.game_key] = service

    def get(self, game_key: str) -> GameService | None:
        return self._services.get(game_key)

    def keys(self) -> list[str]:
        return list(self._services.keys())

    def __contains__(self, game_key: str) -> bool:
        return game_key in self._services
