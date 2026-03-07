from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from dm4z_bot.database.migrations import MIGRATIONS

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._apply_migrations()
        logger.info("Database connected: %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        logger.debug("SQL execute: %s | params: %s", sql.strip(), params)
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        logger.debug("SQL fetch_one: %s | params: %s", sql.strip(), params)
        self.conn.row_factory = aiosqlite.Row
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            logger.debug("SQL fetch_one returned no rows")
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        logger.debug("SQL fetch_all: %s | params: %s", sql.strip(), params)
        self.conn.row_factory = aiosqlite.Row
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        logger.debug("SQL fetch_all returned %d row(s)", len(rows))
        return [dict(r) for r in rows]

    async def _apply_migrations(self) -> None:
        await self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        cursor = await self.conn.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        current = row[0] if row and row[0] is not None else 0

        for version, sql in MIGRATIONS:
            if version > current:
                logger.info("Applying migration %d", version)
                await self.conn.executescript(sql)
                await self.conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (version,)
                )
                await self.conn.commit()

        logger.info("Database schema at version %d", len(MIGRATIONS))
