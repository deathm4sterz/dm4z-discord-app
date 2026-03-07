from __future__ import annotations

import json
import logging

from discord.ext import tasks

from dm4z_bot.database.db import Database
from dm4z_bot.services.games.registry import GameRegistry

logger = logging.getLogger(__name__)


class StatFetcher:
    def __init__(self, db: Database, registry: GameRegistry) -> None:
        self.db = db
        self.registry = registry

    @tasks.loop(minutes=30)
    async def fetch_loop(self) -> None:
        await self._run()

    async def _run(self) -> None:
        accounts = await self.db.fetch_all(
            "SELECT id, game, account_identifier FROM game_accounts WHERE status = 'approved'"
        )
        logger.info("Fetching stats for %d approved accounts", len(accounts))

        for account in accounts:
            service = self.registry.get(account["game"])
            if service is None:
                continue
            try:
                stats = await service.fetch_stats(account["account_identifier"])
                stats_json = json.dumps(stats)
                existing = await self.db.fetch_one(
                    "SELECT id FROM game_stats WHERE game_account_id = ?",
                    (account["id"],),
                )
                if existing:
                    await self.db.execute(
                        "UPDATE game_stats SET stats_json = ?, updated_at = datetime('now') WHERE id = ?",
                        (stats_json, existing["id"]),
                    )
                else:
                    await self.db.execute(
                        "INSERT INTO game_stats (game_account_id, stats_json) VALUES (?, ?)",
                        (account["id"], stats_json),
                    )
            except Exception:
                logger.exception("Failed to fetch stats for account %d (%s)", account["id"], account["game"])

    def start(self) -> None:
        if not self.fetch_loop.is_running():
            self.fetch_loop.start()

    def stop(self) -> None:
        if self.fetch_loop.is_running():
            self.fetch_loop.cancel()
