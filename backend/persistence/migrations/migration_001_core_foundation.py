import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_owned INTEGER NOT NULL DEFAULT 0 CHECK (is_owned IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE product_external_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            identity_type TEXT NOT NULL,
            identity_value TEXT NOT NULL,
            source_account_scope TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE (source, identity_type, identity_value, source_account_scope)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_product_external_identities_product_id "
        "ON product_external_identities(product_id)"
    )
    conn.execute(
        """
        CREATE TABLE import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            import_kind TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED')
            ),
            started_at TEXT NOT NULL,
            finished_at TEXT NULL DEFAULT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE source_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id INTEGER NOT NULL,
            artifact_kind TEXT NOT NULL,
            original_name TEXT NULL DEFAULT NULL,
            content_sha256 TEXT NOT NULL,
            byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
            stored_relpath TEXT NULL DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (import_batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_source_artifacts_import_batch_id "
        "ON source_artifacts(import_batch_id)"
    )
