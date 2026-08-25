import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from types import ModuleType

import pytest

from backend.domain.product_snapshot import SnapshotWriteKind
from backend.domain.search_visibility import (
    CpcState,
    CpoState,
    search_visibility_payload_sha256,
)
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.migrations import runner
from backend.persistence.migrations.runner import DatabaseMigrationError, run_migrations
from backend.persistence.repositories.search_visibility_snapshots import (
    SearchVisibilitySnapshotRepository,
)


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


def test_migration_006_upgrades_populated_v5_search_visibility_without_data_loss(monkeypatch):
    connection = connect(":memory:")
    monkeypatch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:5])
    run_migrations(connection)

    created_at = "2026-08-17T03:50:00+00:00"
    observed_at = "2026-08-17T03:55:00+00:00"
    imported_at = "2026-08-17T04:00:00+00:00"
    product_id = connection.execute(
        "INSERT INTO products (is_owned, created_at, updated_at) VALUES (1, ?, ?)",
        (created_at, created_at),
    ).lastrowid
    connection.execute(
        """INSERT INTO product_external_identities
           (product_id, source, identity_type, identity_value, source_account_scope, created_at)
           VALUES (?, 'ozon', 'ozon_product_id', '700001', '', ?)""",
        (product_id, created_at),
    )
    query_id = connection.execute(
        "INSERT INTO search_queries (query_text, created_at) VALUES ('query', ?)",
        (created_at,),
    ).lastrowid
    cluster_id = connection.execute(
        "INSERT INTO clusters (name, created_at) VALUES ('cluster', ?)",
        (created_at,),
    ).lastrowid
    batch_id = connection.execute(
        """INSERT INTO import_batches (source, import_kind, status, started_at)
           VALUES ('ozon', 'ozon_search_visibility_xlsx', 'SUCCESS', ?)""",
        (created_at,),
    ).lastrowid
    artifact_id = connection.execute(
        """INSERT INTO source_artifacts
           (import_batch_id, artifact_kind, original_name, content_sha256, byte_size, created_at)
           VALUES (?, 'ozon_search_visibility_xlsx', 'visibility.xlsx', ?, 1, ?)""",
        (batch_id, "a" * 64, created_at),
    ).lastrowid

    payload = {
        "source_title": "Source title",
        "seller_name": "Seller",
        "position": 3,
        "overall_score": Decimal("98.50"),
        "promotion_status": "Promoted",
        "cpc_state": CpcState.ACTIVE,
        "cpc_rub": Decimal("9"),
        "promotion_strategy": "Automatic",
        "cpo_state": CpoState.ACTIVE,
        "cpo_pct": Decimal("7.25"),
        "relevance_score": Decimal("96.40"),
        "rating": Decimal("4.80"),
        "reviews_count": 321,
        "buyer_price_rub": Decimal("1499"),
        "popularity_score": Decimal("72.10"),
        "ozon_promotion": True,
        "delivery_label": "Tomorrow",
        "delivery_min_days": 1,
        "delivery_max_days": 2,
        "price_index_pct": Decimal("101.25"),
    }
    v5_payload_columns = tuple(name for name in payload if name != "cpc_state")
    insert_columns = (
        "product_id", "search_query_id", "cluster_id", "observed_at", "revision",
        "supersedes_snapshot_id", "payload_sha256", "import_batch_id",
        "source_artifact_id", "imported_at", *v5_payload_columns,
    )

    first_payload = {**payload, "source_title": "Earlier source title", "position": 4}

    def insert_revision(revision, supersedes_snapshot_id, digest, revision_payload):
        values = (
            product_id, query_id, cluster_id, observed_at, revision,
            supersedes_snapshot_id, digest, batch_id, artifact_id, imported_at,
            *(revision_payload[name].value if isinstance(revision_payload[name], CpoState) else
              int(revision_payload[name]) if name == "ozon_promotion" else
              str(revision_payload[name]) if isinstance(revision_payload[name], Decimal)
              else revision_payload[name]
              for name in v5_payload_columns),
        )
        placeholders = ",".join("?" for _ in values)
        return connection.execute(
            f"INSERT INTO search_visibility_snapshots ({','.join(insert_columns)}) "
            f"VALUES ({placeholders})",
            values,
        ).lastrowid

    first_id = insert_revision(1, None, "b" * 64, first_payload)
    second_id = insert_revision(2, first_id, "c" * 64, payload)
    connection.commit()
    before = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM search_visibility_snapshots ORDER BY revision"
        )
    ]

    monkeypatch.undo()
    run_migrations(connection)

    assert tuple(connection.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    ).fetchall()[-1]) == (6, "search_visibility_cpc_state")
    after = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM search_visibility_snapshots ORDER BY revision"
        )
    ]
    assert len(after) == len(before) == 2
    for old, migrated, expected_payload in zip(
        before, after, (first_payload, payload), strict=True
    ):
        expected_unchanged = {key: value for key, value in old.items() if key != "payload_sha256"}
        actual_unchanged = {
            key: value for key, value in migrated.items()
            if key not in {"payload_sha256", "cpc_state"}
        }
        assert actual_unchanged == expected_unchanged
        assert migrated["cpc_state"] == "ACTIVE"
        assert Decimal(migrated["cpc_rub"]) == Decimal("9")
        assert migrated["payload_sha256"] == search_visibility_payload_sha256(
            expected_payload
        )
    assert after[1]["supersedes_snapshot_id"] == first_id

    result = SearchVisibilitySnapshotRepository(connection).resolve_revision(
        product_id=product_id,
        search_query_id=query_id,
        cluster_id=cluster_id,
        observed_at=datetime.fromisoformat(observed_at),
        payload_sha256=search_visibility_payload_sha256(payload),
        import_batch_id=batch_id,
        source_artifact_id=artifact_id,
        imported_at=datetime(2026, 8, 17, 4, 5, tzinfo=timezone.utc),
        snapshot_values=payload,
    )
    assert result.kind is SnapshotWriteKind.DUPLICATE
    assert result.snapshot.id == second_id
    assert result.snapshot.revision == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM search_visibility_snapshots"
    ).fetchone()[0] == 2
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
