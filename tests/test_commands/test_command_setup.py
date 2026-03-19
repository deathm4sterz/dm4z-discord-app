from __future__ import annotations

from dm4z_bot.commands import (
    age,
    approve,
    guild_config,
    help,
    leaderboard,
    link,
    match_info,
    profile,
    tracking,
)
from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api
from dm4z_bot.services.games.aoe2_service import Aoe2Service
from dm4z_bot.services.games.cs2_service import Cs2Service
from dm4z_bot.services.games.registry import GameRegistry
from dm4z_bot.tasks.match_tracker import MatchTracker


class FakeBot:
    def __init__(self) -> None:
        self.cogs: list[str] = []
        self.aoe2_api = Aoe2Api()
        self.db = Database(":memory:")
        self.game_registry = GameRegistry()
        self.game_registry.register(Aoe2Service(self.aoe2_api))
        self.game_registry.register(Cs2Service())
        self.match_tracker = MatchTracker(self, self.db, self.aoe2_api)

    def add_cog(self, cog: object) -> None:
        self.cogs.append(type(cog).__name__)


def test_setup_registers_all_command_cogs() -> None:
    bot = FakeBot()
    age.setup(bot)  # type: ignore[arg-type]
    help.setup(bot)  # type: ignore[arg-type]
    match_info.setup(bot)  # type: ignore[arg-type]
    leaderboard.setup(bot)  # type: ignore[arg-type]
    link.setup(bot)  # type: ignore[arg-type]
    approve.setup(bot)  # type: ignore[arg-type]
    profile.setup(bot)  # type: ignore[arg-type]
    guild_config.setup(bot)  # type: ignore[arg-type]
    tracking.setup(bot)  # type: ignore[arg-type]
    assert bot.cogs == [
        "AgeCommands",
        "HelpCommands",
        "MatchInfoCommands",
        "LeaderboardCommands",
        "LinkCommands",
        "ApproveCommands",
        "ProfileCommands",
        "GuildConfigCommands",
        "TrackingCommands",
    ]
