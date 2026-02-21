from dm4z_bot.commands import age, leaderboard, match_info, rank, team_rank
from dm4z_bot.services.aoe2_api import Aoe2Api


class FakeBot:
    def __init__(self) -> None:
        self.cogs: list[str] = []
        self.aoe2_api = Aoe2Api()

    def add_cog(self, cog: object) -> None:
        self.cogs.append(type(cog).__name__)


def test_setup_registers_all_command_cogs() -> None:
    bot = FakeBot()
    age.setup(bot)  # type: ignore[arg-type]
    match_info.setup(bot)  # type: ignore[arg-type]
    rank.setup(bot)  # type: ignore[arg-type]
    team_rank.setup(bot)  # type: ignore[arg-type]
    leaderboard.setup(bot)  # type: ignore[arg-type]
    assert bot.cogs == [
        "AgeCommands",
        "MatchInfoCommands",
        "RankCommands",
        "TeamRankCommands",
        "LeaderboardCommands",
    ]

