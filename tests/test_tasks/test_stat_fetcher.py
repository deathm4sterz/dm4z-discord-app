from __future__ import annotations

import json

import pytest

from dm4z_bot.database.db import Database
from dm4z_bot.services.games.registry import GameRegistry
from dm4z_bot.tasks.stat_fetcher import StatFetcher


class FakeGameService:
    game_key = "testgame"
    display_name = "Test Game"

    async def fetch_stats(self, account_identifier: str) -> dict:
        return {"score": 100, "wins": 5}

    async def validate_account(self, account_identifier: str) -> str | None:
        return account_identifier


class FailingGameService:
    game_key = "failgame"
    display_name = "Fail Game"

    async def fetch_stats(self, account_identifier: str) -> dict:
        raise RuntimeError("API down")

    async def validate_account(self, account_identifier: str) -> str | None:
        return account_identifier


async def _seed_approved_account(db: Database, game: str = "testgame") -> int:
    await db.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (1,))
    await db.execute("INSERT OR IGNORE INTO members (member_id, guild_id) VALUES (?, ?)", (100, 1))
    cursor = await db.execute(
        "INSERT INTO game_accounts (member_id, guild_id, game, account_identifier, display_name, status) "
        "VALUES (?, ?, ?, ?, ?, 'approved')",
        (100, 1, game, "acc1", "Player1"),
    )
    return cursor.lastrowid


@pytest.mark.asyncio
async def test_run_fetches_and_inserts_stats(memory_db: Database) -> None:
    account_id = await _seed_approved_account(memory_db)
    registry = GameRegistry()
    registry.register(FakeGameService())
    fetcher = StatFetcher(memory_db, registry)
    await fetcher._run()

    row = await memory_db.fetch_one("SELECT stats_json FROM game_stats WHERE game_account_id = ?", (account_id,))
    assert row is not None
    stats = json.loads(row["stats_json"])
    assert stats["score"] == 100


@pytest.mark.asyncio
async def test_run_updates_existing_stats(memory_db: Database) -> None:
    account_id = await _seed_approved_account(memory_db)
    await memory_db.execute(
        "INSERT INTO game_stats (game_account_id, stats_json) VALUES (?, ?)",
        (account_id, '{"score": 1}'),
    )
    registry = GameRegistry()
    registry.register(FakeGameService())
    fetcher = StatFetcher(memory_db, registry)
    await fetcher._run()

    rows = await memory_db.fetch_all("SELECT stats_json FROM game_stats WHERE game_account_id = ?", (account_id,))
    assert len(rows) == 1
    assert json.loads(rows[0]["stats_json"])["score"] == 100


@pytest.mark.asyncio
async def test_run_skips_unknown_game(memory_db: Database) -> None:
    await _seed_approved_account(memory_db, game="unknown")
    registry = GameRegistry()
    registry.register(FakeGameService())
    fetcher = StatFetcher(memory_db, registry)
    await fetcher._run()

    rows = await memory_db.fetch_all("SELECT * FROM game_stats")
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_run_handles_service_error(memory_db: Database) -> None:
    await _seed_approved_account(memory_db, game="failgame")
    registry = GameRegistry()
    registry.register(FailingGameService())
    fetcher = StatFetcher(memory_db, registry)
    await fetcher._run()

    rows = await memory_db.fetch_all("SELECT * FROM game_stats")
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_run_no_accounts(memory_db: Database) -> None:
    registry = GameRegistry()
    fetcher = StatFetcher(memory_db, registry)
    await fetcher._run()


@pytest.mark.asyncio
async def test_fetch_loop_delegates_to_run(memory_db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = GameRegistry()
    fetcher = StatFetcher(memory_db, registry)
    called: list[bool] = []

    async def mock_run() -> None:
        called.append(True)

    monkeypatch.setattr(fetcher, "_run", mock_run)
    await fetcher.fetch_loop.coro(fetcher)
    assert called == [True]


@pytest.mark.asyncio
async def test_start_and_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = GameRegistry()
    db = Database(":memory:")
    fetcher = StatFetcher(db, registry)

    started = []
    cancelled = []
    monkeypatch.setattr(fetcher.fetch_loop, "start", lambda: started.append(True))
    monkeypatch.setattr(fetcher.fetch_loop, "cancel", lambda: cancelled.append(True))
    monkeypatch.setattr(fetcher.fetch_loop, "is_running", lambda: len(started) > len(cancelled))

    fetcher.start()
    assert started == [True]

    fetcher.stop()
    assert cancelled == [True]


@pytest.mark.asyncio
async def test_stop_when_not_running() -> None:
    registry = GameRegistry()
    db = Database(":memory:")
    fetcher = StatFetcher(db, registry)
    fetcher.stop()


@pytest.mark.asyncio
async def test_start_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = GameRegistry()
    db = Database(":memory:")
    fetcher = StatFetcher(db, registry)

    started = []
    monkeypatch.setattr(fetcher.fetch_loop, "start", lambda: started.append(True))
    monkeypatch.setattr(fetcher.fetch_loop, "is_running", lambda: len(started) > 0)

    fetcher.start()
    fetcher.start()
    assert len(started) == 1
