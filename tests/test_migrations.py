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
        ).fetchall() == [(1, "core_foundation"), (2, "ozon_products_import"), (3, "ozon_search_visibility_import"), (4, "pr5_query_data"), (5, "benchmark_selection"), (6, "search_visibility_cpc_state")]
        assert _application_tables(connection) == {
            "schema_migrations",
            "products",
            "product_external_identities",
            "import_batches",
            "source_artifacts",
            "product_snapshots",
            "search_queries",
            "clusters",
            "search_visibility_snapshots",
            "product_query_snapshots",
            "query_metric_snapshots",
            "product_relevant_queries",
            "benchmark_sets",
            "benchmark_set_revisions",
            "benchmark_members",
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
                ("report_generated_on", "TEXT", 0, None, 0),
                ("report_window_days", "INTEGER", 0, None, 0),
                ("rows_seen", "INTEGER", 0, None, 0),
                ("rows_accepted", "INTEGER", 0, None, 0),
                ("rows_skipped", "INTEGER", 0, None, 0),
                ("duplicate_observations", "INTEGER", 0, None, 0),
                ("new_observations", "INTEGER", 0, None, 0),
                ("corrected_revisions", "INTEGER", 0, None, 0),
                ("warnings_count", "INTEGER", 0, None, 0),
                ("row_errors_total", "INTEGER", 0, None, 0),
                ("observed_at", "TEXT", 0, None, 0),
                ("search_query_text", "TEXT", 0, None, 0),
                ("cluster_name", "TEXT", 0, None, 0),
                    ("declared_rows", "INTEGER", 0, None, 0),
                    ("period_start", "TEXT", 0, None, 0),
                    ("period_end", "TEXT", 0, None, 0),
                    ("report_generated_at", "TEXT", 0, None, 0),
                    ("report_product_ozon_id", "TEXT", 0, None, 0),
                    ("sort_context", "TEXT", 0, None, 0),
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


def test_fresh_database_applies_all_migrations(tmp_path):
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()[-1] == (6, "search_visibility_cpc_state")


def test_migration_005_upgrades_populated_v4_without_changing_rows(monkeypatch):
    connection = connect(":memory:")
    monkeypatch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:4])
    run_migrations(connection)
    connection.execute(
        "INSERT INTO products (is_owned, created_at, updated_at) VALUES (1, 'created', 'updated')"
    )
    connection.execute("INSERT INTO search_queries (query_text, created_at) VALUES ('Exact  Query', 'created')")
    connection.commit()
    before = tuple(connection.execute("SELECT * FROM products").fetchone())
    monkeypatch.undo()
    run_migrations(connection)
    assert tuple(connection.execute("SELECT * FROM products").fetchone()) == before
    assert tuple(connection.execute("SELECT * FROM search_queries").fetchone())[1] == "Exact  Query"
    assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
    connection.close()


def test_migration_005_schema_is_exact(tmp_path):
    db_path = tmp_path / "schema.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        expected_columns = {
            "product_relevant_queries": [
                ("product_id", "INTEGER", 1, None, 1),
                ("search_query_id", "INTEGER", 1, None, 2),
                ("selected_at", "TEXT", 1, None, 0),
            ],
            "benchmark_sets": [
                ("id", "INTEGER", 0, None, 1),
                ("own_product_id", "INTEGER", 1, None, 0),
                ("created_at", "TEXT", 1, None, 0),
            ],
            "benchmark_set_revisions": [
                ("id", "INTEGER", 0, None, 1),
                ("benchmark_set_id", "INTEGER", 1, None, 0),
                ("revision", "INTEGER", 1, None, 0),
                ("created_at", "TEXT", 1, None, 0),
            ],
            "benchmark_members": [
                ("benchmark_set_revision_id", "INTEGER", 1, None, 1),
                ("product_id", "INTEGER", 1, None, 2),
            ],
        }
        for table, expected in expected_columns.items():
            assert [tuple(row[1:6]) for row in connection.execute(f"PRAGMA table_info({table})")] == expected

        indexes = {
            "idx_product_relevant_queries_query_product": ["search_query_id", "product_id"],
            "idx_benchmark_set_revisions_current": ["benchmark_set_id", "revision"],
            "idx_benchmark_members_product_revision": ["product_id", "benchmark_set_revision_id"],
        }
        for name, columns in indexes.items():
            assert [row[2] for row in connection.execute(f"PRAGMA index_info({name})")] == columns

        foreign_keys = {
            (row[2], row[3], row[4], row[6])
            for table in expected_columns
            for row in connection.execute(f"PRAGMA foreign_key_list({table})")
        }
        assert ("products", "product_id", "id", "CASCADE") in foreign_keys
        assert ("search_queries", "search_query_id", "id", "RESTRICT") in foreign_keys
        assert ("products", "own_product_id", "id", "RESTRICT") in foreign_keys
        assert ("benchmark_sets", "benchmark_set_id", "id", "CASCADE") in foreign_keys
        assert ("benchmark_set_revisions", "benchmark_set_revision_id", "id", "CASCADE") in foreign_keys
