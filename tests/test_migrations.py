import sqlite3
import sys
from types import ModuleType

import pytest

from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.migrations import runner
from backend.persistence.migrations.runner import DatabaseMigrationError, run_migrations


EXPECTED_MIGRATION_HISTORY = [
    (1, "core_foundation"),
    (2, "ozon_products_import"),
    (3, "ozon_search_visibility_import"),
]


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
        ).fetchall() == EXPECTED_MIGRATION_HISTORY
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


def test_migration_003_exact_schema_indexes_and_foreign_keys(tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        assert [tuple(row[1:6]) for row in connection.execute("PRAGMA table_info(search_queries)")] == [
            ("id", "INTEGER", 0, None, 1), ("query_text", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ]
        assert [tuple(row[1:6]) for row in connection.execute("PRAGMA table_info(clusters)")] == [
            ("id", "INTEGER", 0, None, 1), ("name", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ]
        assert [row[1] for row in connection.execute("PRAGMA table_info(search_visibility_snapshots)")] == [
            "id", "product_id", "search_query_id", "cluster_id", "observed_at", "revision",
            "supersedes_snapshot_id", "payload_sha256", "import_batch_id", "source_artifact_id",
            "imported_at", "source_title", "seller_name", "position", "overall_score",
            "promotion_status", "cpc_rub", "promotion_strategy", "cpo_state", "cpo_pct",
            "relevance_score", "rating", "reviews_count", "buyer_price_rub", "popularity_score",
            "ozon_promotion", "delivery_label", "delivery_min_days", "delivery_max_days", "price_index_pct",
        ]
        foreign_keys = {(row[3], row[2], row[4]) for row in connection.execute(
            "PRAGMA foreign_key_list(search_visibility_snapshots)"
        )}
        assert foreign_keys == {
            ("product_id", "products", "id"), ("search_query_id", "search_queries", "id"),
            ("cluster_id", "clusters", "id"),
            ("supersedes_snapshot_id", "search_visibility_snapshots", "id"),
            ("import_batch_id", "import_batches", "id"),
            ("source_artifact_id", "source_artifacts", "id"),
        }
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(search_visibility_snapshots)")}
        expected_indexes = {
            "idx_search_visibility_current": ["product_id", "search_query_id", "cluster_id", "observed_at", "revision"],
            "idx_search_visibility_context": ["search_query_id", "cluster_id", "observed_at", "product_id", "revision"],
            "idx_search_visibility_product": ["product_id", "search_query_id", "cluster_id", "observed_at", "revision"],
            "idx_search_visibility_import_batch_id": ["import_batch_id"],
            "idx_search_visibility_source_artifact_id": ["source_artifact_id"],
        }
        assert set(expected_indexes) < indexes
        for name, columns in expected_indexes.items():
            assert [row[2] for row in connection.execute(f"PRAGMA index_info({name})")] == columns
        sql = " ".join(connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='search_visibility_snapshots'"
        ).fetchone()[0].split())
        assert "UNIQUE (product_id, search_query_id, cluster_id, observed_at, revision)" in sql
        assert "CHECK (revision > 0)" in sql


def test_database_stopped_after_001_upgrades_through_002_and_003(tmp_path):
    from backend.persistence.migrations import migration_001_core_foundation

    connection = connect(tmp_path / "upgrade.db")
    connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    migration_001_core_foundation.up(connection)
    connection.execute("INSERT INTO schema_migrations VALUES (1, 'core_foundation', 'now')")
    connection.commit()
    run_migrations(connection)
    assert [tuple(row) for row in connection.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    )] == EXPECTED_MIGRATION_HISTORY
    connection.close()


def _insert_snapshot_context(connection):
    connection.execute("INSERT INTO products (is_owned, created_at, updated_at) VALUES (0, 'now', 'now')")
    connection.execute("INSERT INTO search_queries (query_text, created_at) VALUES ('Query', 'now')")
    connection.execute("INSERT INTO clusters (name, created_at) VALUES ('Cluster', 'now')")
    connection.execute("INSERT INTO import_batches (source, import_kind, status, started_at) VALUES ('ozon', 'kind', 'RUNNING', 'now')")
    connection.execute("INSERT INTO source_artifacts (import_batch_id, artifact_kind, content_sha256, byte_size, created_at) VALUES (1, 'xlsx', ?, 1, 'now')", ("a" * 64,))


def _snapshot_values(**overrides):
    values = dict(product_id=1, search_query_id=1, cluster_id=1, observed_at="2026-08-17T03:55:00+00:00",
                  revision=1, supersedes_snapshot_id=None, payload_sha256="b" * 64, import_batch_id=1,
                  source_artifact_id=1, imported_at="now", source_title="title", seller_name="seller",
                  position=1, overall_score="1", promotion_status="active", cpc_rub="2",
                  promotion_strategy="auto", cpo_state="ACTIVE", cpo_pct="10", relevance_score="3",
                  rating="4.8", reviews_count=2, buyer_price_rub="100", popularity_score="5",
                  ozon_promotion=1, delivery_label="1-2 days", delivery_min_days=1,
                  delivery_max_days=2, price_index_pct="5")
    values.update(overrides)
    return values


def _insert_snapshot(connection, values):
    columns = tuple(values)
    connection.execute(
        f"INSERT INTO search_visibility_snapshots ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        tuple(values.values()),
    )


def test_migration_003_direct_constraints(tmp_path):
    connection = connect(tmp_path / "constraints.db")
    run_migrations(connection)
    _insert_snapshot_context(connection)
    connection.execute("INSERT INTO search_queries (query_text, created_at) VALUES ('query', 'now')")
    connection.execute("INSERT INTO clusters (name, created_at) VALUES ('cluster', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO search_queries (query_text, created_at) VALUES ('Query', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO clusters (name, created_at) VALUES ('Cluster', 'now')")
    _insert_snapshot(connection, _snapshot_values())
    with pytest.raises(sqlite3.IntegrityError):
        _insert_snapshot(connection, _snapshot_values(payload_sha256="c" * 64))
    invalid = (
        {"revision": 0}, {"cpo_state": "ACTIVE", "cpo_pct": None},
        {"cpo_state": "DISABLED", "cpo_pct": "1"}, {"rating": None, "reviews_count": 2},
        {"rating": "4.8", "reviews_count": None}, {"reviews_count": -1},
        {"delivery_min_days": -1}, {"delivery_max_days": -1},
        {"delivery_min_days": 3, "delivery_max_days": 2},
    )
    for revision, overrides in enumerate(invalid, start=2):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_snapshot(connection, _snapshot_values(**({"revision": revision} | overrides)))
    connection.execute("INSERT INTO import_batches (source, import_kind, status, started_at, declared_rows) VALUES ('ozon', 'kind', 'RUNNING', 'now', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO import_batches (source, import_kind, status, started_at, declared_rows) VALUES ('ozon', 'kind', 'RUNNING', 'now', 0)")
    connection.close()


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
