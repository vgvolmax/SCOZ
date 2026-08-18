import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE search_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, query_text TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE (query_text))""")
    conn.execute("""CREATE TABLE clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE (name))""")
    conn.execute("""CREATE TABLE search_visibility_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id),
        search_query_id INTEGER NOT NULL REFERENCES search_queries(id),
        cluster_id INTEGER NOT NULL REFERENCES clusters(id),
        observed_at TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision > 0),
        supersedes_snapshot_id INTEGER NULL REFERENCES search_visibility_snapshots(id),
        payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
        import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id),
        imported_at TEXT NOT NULL, source_title TEXT NOT NULL, seller_name TEXT NOT NULL,
        position INTEGER NOT NULL CHECK (position > 0), overall_score TEXT NOT NULL,
        promotion_status TEXT NOT NULL, cpc_rub TEXT NOT NULL, promotion_strategy TEXT NOT NULL,
        cpo_state TEXT NOT NULL CHECK (cpo_state IN ('ACTIVE', 'DISABLED', 'UNAVAILABLE')),
        cpo_pct TEXT NULL, relevance_score TEXT NOT NULL, rating TEXT NULL,
        reviews_count INTEGER NULL CHECK (reviews_count IS NULL OR reviews_count >= 0),
        buyer_price_rub TEXT NOT NULL, popularity_score TEXT NOT NULL,
        ozon_promotion INTEGER NOT NULL CHECK (ozon_promotion IN (0, 1)),
        delivery_label TEXT NOT NULL, delivery_min_days INTEGER NOT NULL CHECK (delivery_min_days >= 0),
        delivery_max_days INTEGER NOT NULL CHECK (delivery_max_days >= 0), price_index_pct TEXT NOT NULL,
        UNIQUE (product_id, search_query_id, cluster_id, observed_at, revision),
        CHECK (delivery_min_days <= delivery_max_days),
        CHECK ((rating IS NULL) = (reviews_count IS NULL)),
        CHECK ((cpo_state = 'ACTIVE' AND cpo_pct IS NOT NULL) OR
               (cpo_state IN ('DISABLED', 'UNAVAILABLE') AND cpo_pct IS NULL)))""")
    conn.execute("CREATE INDEX idx_search_visibility_current ON search_visibility_snapshots(product_id, search_query_id, cluster_id, observed_at, revision DESC)")
    conn.execute("CREATE INDEX idx_search_visibility_context ON search_visibility_snapshots(search_query_id, cluster_id, observed_at DESC, product_id, revision DESC)")
    conn.execute("CREATE INDEX idx_search_visibility_product ON search_visibility_snapshots(product_id, search_query_id, cluster_id, observed_at DESC, revision DESC)")
    conn.execute("CREATE INDEX idx_search_visibility_import_batch_id ON search_visibility_snapshots(import_batch_id)")
    conn.execute("CREATE INDEX idx_search_visibility_source_artifact_id ON search_visibility_snapshots(source_artifact_id)")
    conn.execute("ALTER TABLE import_batches ADD COLUMN observed_at TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN search_query_text TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN cluster_name TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN declared_rows INTEGER NULL CHECK (declared_rows IS NULL OR declared_rows > 0)")
