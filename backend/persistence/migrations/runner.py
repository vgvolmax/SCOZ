import importlib
import sqlite3
from datetime import datetime, timezone


MIGRATIONS = [
    (
        1,
        "core_foundation",
        "backend.persistence.migrations.migration_001_core_foundation",
    ),
    (2, "ozon_products_import", "backend.persistence.migrations.migration_002_ozon_products_import"),
    (
        3,
        "ozon_search_visibility_import",
        "backend.persistence.migrations.migration_003_ozon_search_visibility_import",
    ),
]


class DatabaseMigrationError(RuntimeError):
    pass


def _create_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _pending_migrations(conn: sqlite3.Connection) -> list[tuple[int, str, str]]:
    applied = [
        (row["version"], row["name"])
        for row in conn.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        )
    ]
    registered = [(version, name) for version, name, _ in MIGRATIONS]
    if applied != registered[: len(applied)]:
        raise DatabaseMigrationError(
            "Applied database migrations are not a contiguous registry prefix"
        )
    return MIGRATIONS[len(applied) :]


def run_migrations(conn: sqlite3.Connection) -> None:
    _create_history_table(conn)
    pending = _pending_migrations(conn)
    for version, name, module_name in pending:
        try:
            migration = importlib.import_module(module_name)
            conn.execute("BEGIN")
            migration.up(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, datetime.now(timezone.utc).isoformat()),
            )
            conn.execute("COMMIT")
        except Exception as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise DatabaseMigrationError(
                f"Failed to apply database migration {version} ({name})"
            ) from exc
