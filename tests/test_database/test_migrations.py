from __future__ import annotations

from dm4z_bot.database.migrations import MIGRATIONS


def test_migrations_list_is_not_empty() -> None:
    assert len(MIGRATIONS) > 0


def test_migration_versions_are_sequential() -> None:
    for i, (version, _sql) in enumerate(MIGRATIONS):
        assert version == i + 1


def test_migration_sql_is_not_empty() -> None:
    for _version, sql in MIGRATIONS:
        assert len(sql.strip()) > 0
