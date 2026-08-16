import sqlite3
import sys
from types import ModuleType

import pytest

from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.migrations import runner
from backend.persistence.migrations.runner import DatabaseMigrationError, run_migrations


def _application_tables(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def test_migration_001_creates_exact_schema_once(tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1, "core_foundation")]
        assert _application_tables(connection) == {
            "schema_migrations",
            "products",
            "product_external_identities",
            "import_batches",
            "source_artifacts",
        }
        columns = {
            table: [tuple(row[1:6]) for row in connection.execute(f"PRAGMA table_info({table})")]
            for table in _application_tables(connection)
        }
        assert columns["schema_migrations"] == [
            ("version", "INTEGER", 0, None, 1),
            ("name", "TEXT", 1, None, 0),
            ("applied_at", "TEXT", 1, None, 0),
        ]
        assert columns["products"] == [
            ("id", "INTEGER", 0, None, 1),
            ("is_owned", "INTEGER", 1, "0", 0),
            ("created_at", "TEXT", 1, None, 0),
            ("updated_at", "TEXT", 1, None, 0),
        ]
        assert columns["product_external_identities"] == [
            ("id", "INTEGER", 0, None, 1),
            ("product_id", "INTEGER", 1, None, 0),
            ("source", "TEXT", 1, None, 0),
            ("identity_type", "TEXT", 1, None, 0),
            ("identity_value", "TEXT", 1, None, 0),
            ("source_account_scope", "TEXT", 1, "''", 0),
            ("created_at", "TEXT", 1, None, 0),
        ]
        assert columns["import_batches"] == [
            ("id", "INTEGER", 0, None, 1),
            ("source", "TEXT", 1, None, 0),
            ("import_kind", "TEXT", 1, None, 0),
            ("status", "TEXT", 1, None, 0),
            ("started_at", "TEXT", 1, None, 0),
            ("finished_at", "TEXT", 0, "NULL", 0),
        ]
        assert columns["source_artifacts"] == [
            ("id", "INTEGER", 0, None, 1),
            ("import_batch_id", "INTEGER", 1, None, 0),
            ("artifact_kind", "TEXT", 1, None, 0),
            ("original_name", "TEXT", 0, "NULL", 0),
            ("content_sha256", "TEXT", 1, None, 0),
            ("byte_size", "INTEGER", 1, None, 0),
            ("stored_relpath", "TEXT", 0, "NULL", 0),
            ("created_at", "TEXT", 1, None, 0),
        ]
        table_sql = {
            row[0]: " ".join(row[1].split())
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert "CHECK (is_owned IN (0,1))" in table_sql["products"]
        assert (
            "CHECK ( status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED') )"
            in table_sql["import_batches"]
        )
        assert "CHECK (byte_size >= 0)" in table_sql["source_artifacts"]
        assert connection.execute("PRAGMA foreign_key_list(product_external_identities)").fetchall()[0][2:7] == (
            "products", "product_id", "id", "NO ACTION", "CASCADE"
        )
        assert connection.execute("PRAGMA foreign_key_list(source_artifacts)").fetchall()[0][2:7] == (
            "import_batches", "import_batch_id", "id", "NO ACTION", "CASCADE"
        )
        identity_indexes = {
            row[1]: (row[2], row[3])
            for row in connection.execute(
                "PRAGMA index_list(product_external_identities)"
            )
        }
        assert identity_indexes == {
            "idx_product_external_identities_product_id": (0, "c"),
            "sqlite_autoindex_product_external_identities_1": (1, "u"),
        }
        assert [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info(idx_product_external_identities_product_id)"
            )
        ] == ["product_id"]
        assert [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info(sqlite_autoindex_product_external_identities_1)"
            )
        ] == [
            "source",
            "identity_type",
            "identity_value",
            "source_account_scope",
        ]
        artifact_indexes = {
            row[1]: (row[2], row[3])
            for row in connection.execute("PRAGMA index_list(source_artifacts)")
        }
        assert artifact_indexes == {"idx_source_artifacts_import_batch_id": (0, "c")}
        assert [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info(idx_source_artifacts_import_batch_id)"
            )
        ] == ["import_batch_id"]


def _module(monkeypatch, name, action):
    module = ModuleType(name)
    module.up = action
    monkeypatch.setitem(sys.modules, name, module)
    return name


def test_history_prefix_applies_only_pending_suffix(monkeypatch):
    connection = connect(":memory:")
    calls = []
    names = [
        _module(
            monkeypatch,
            f"synthetic_migration_{n}",
            lambda conn, n=n: calls.append(n),
        )
        for n in (1, 2, 3)
    ]
    monkeypatch.setattr(runner, "MIGRATIONS", [(1, "one", names[0]), (2, "two", names[1]), (3, "three", names[2])])
    connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    connection.executemany("INSERT INTO schema_migrations VALUES (?, ?, 'now')", [(1, "one"), (2, "two")])
    connection.commit()
    run_migrations(connection)
    assert calls == [3]
    assert [
        tuple(row)
        for row in connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        )
    ] == [(1, "one"), (2, "two"), (3, "three")]
    connection.close()


@pytest.mark.parametrize("history", [[(2, "two")], [(1, "one"), (3, "three")], [(1, "wrong")], [(99, "unknown")]])
def test_invalid_history_is_rejected_before_pending_code(monkeypatch, history):
    connection = connect(":memory:")
    calls = []
    names = [
        _module(
            monkeypatch,
            f"invalid_history_migration_{n}",
            lambda conn, n=n: calls.append(n),
        )
        for n in (1, 2, 3)
    ]
    monkeypatch.setattr(runner, "MIGRATIONS", [(1, "one", names[0]), (2, "two", names[1]), (3, "three", names[2])])
    connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    connection.executemany("INSERT INTO schema_migrations VALUES (?, ?, 'now')", history)
    connection.commit()
    with pytest.raises(DatabaseMigrationError):
        run_migrations(connection)
    assert calls == []
    connection.close()


def test_failed_migration_rolls_back_ddl_and_metadata_and_preserves_cause(monkeypatch):
    connection = connect(":memory:")
    original = ValueError("synthetic failure")

    def fail(conn):
        conn.execute("CREATE TABLE synthetic_first (id INTEGER)")
        raise original

    name = _module(monkeypatch, "synthetic_failing_migration", fail)
    monkeypatch.setattr(runner, "MIGRATIONS", [(1, "failing", name)])
    with pytest.raises(DatabaseMigrationError) as error:
        run_migrations(connection)
    assert error.value.__cause__ is original
    assert "synthetic_first" not in _application_tables(connection)
    assert connection.execute("SELECT * FROM schema_migrations").fetchall() == []
    connection.close()
