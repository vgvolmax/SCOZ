import sqlite3
from pathlib import Path

import pytest

from backend.config import DEFAULT_DB_PATH, resolve_db_path
from backend.persistence.connection import connect, transaction
from backend.persistence.database import initialize_database


def test_resolve_db_path_uses_default_for_missing_or_blank_override(monkeypatch):
    monkeypatch.delenv("SCOZ_DB_PATH", raising=False)
    assert resolve_db_path() == DEFAULT_DB_PATH

    monkeypatch.setenv("SCOZ_DB_PATH", "   ")
    assert resolve_db_path() == DEFAULT_DB_PATH


def test_resolve_db_path_reads_successive_environment_overrides(monkeypatch, tmp_path):
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"

    monkeypatch.setenv("SCOZ_DB_PATH", f"  {first}  ")
    assert resolve_db_path() == first.resolve()

    monkeypatch.setenv("SCOZ_DB_PATH", str(second))
    assert resolve_db_path() == second.resolve()


def test_connect_explicit_path_overrides_environment(monkeypatch, tmp_path):
    environment_path = tmp_path / "environment.db"
    explicit_path = tmp_path / "explicit.db"
    monkeypatch.setenv("SCOZ_DB_PATH", str(environment_path))

    connection = connect(explicit_path)
    connection.execute("CREATE TABLE marker (value TEXT)")
    connection.commit()
    connection.close()

    assert explicit_path.exists()
    assert not environment_path.exists()


def test_connect_returns_rows_with_mapping_access_and_enables_foreign_keys(tmp_path):
    connection = connect(tmp_path / "database.db")
    try:
        row = connection.execute("SELECT 42 AS answer").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row["answer"] == 42
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_transaction_commits_and_closes_connection(tmp_path):
    db_path = tmp_path / "database.db"

    with transaction(db_path) as connection:
        yielded_connection = connection
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES ('persisted')")

    with sqlite3.connect(db_path) as verification:
        assert verification.execute("SELECT value FROM marker").fetchone() == ("persisted",)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        yielded_connection.execute("SELECT 1")


def test_transaction_rolls_back_and_closes_connection_on_exception(tmp_path):
    db_path = tmp_path / "database.db"
    with sqlite3.connect(db_path) as setup:
        setup.execute("CREATE TABLE marker (value TEXT)")

    with pytest.raises(RuntimeError, match="stop"):
        with transaction(db_path) as connection:
            yielded_connection = connection
            connection.execute("INSERT INTO marker VALUES ('discarded')")
            raise RuntimeError("stop")

    with sqlite3.connect(db_path) as verification:
        assert verification.execute("SELECT value FROM marker").fetchall() == []
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        yielded_connection.execute("SELECT 1")


def test_initialize_database_creates_only_parent_and_migrated_database(tmp_path):
    db_path = tmp_path / "state" / "scoz.db"

    initialize_database(db_path)

    assert db_path.is_file()
    assert not (db_path.parent / "imports").exists()
    assert not (db_path.parent / "backups").exists()
    with sqlite3.connect(db_path) as verification:
        assert verification.execute(
            "SELECT version, name FROM schema_migrations"
        ).fetchall() == [
            (1, "core_foundation"),
            (2, "ozon_products_import"),
            (3, "ozon_search_visibility_import"),
        ]


def test_initialize_database_is_idempotent_and_resolves_environment_late(
    monkeypatch, tmp_path
):
    first = tmp_path / "first" / "scoz.db"
    second = tmp_path / "second" / "scoz.db"

    monkeypatch.setenv("SCOZ_DB_PATH", str(first))
    initialize_database()
    initialize_database()
    monkeypatch.setenv("SCOZ_DB_PATH", str(second))
    initialize_database()

    for path in (first, second):
        with sqlite3.connect(path) as verification:
            assert verification.execute(
                "SELECT version, name FROM schema_migrations"
            ).fetchall() == [
                (1, "core_foundation"),
                (2, "ozon_products_import"),
                (3, "ozon_search_visibility_import"),
            ]
