import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE product_query_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id),
        search_query_id INTEGER NOT NULL REFERENCES search_queries(id),
        period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision > 0),
        supersedes_snapshot_id INTEGER NULL REFERENCES product_query_snapshots(id),
        payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
        import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id),
        imported_at TEXT NOT NULL,
        searched_users INTEGER NOT NULL CHECK (searched_users >= 0),
        seen_users INTEGER NOT NULL CHECK (seen_users >= 0),
        position_state TEXT NOT NULL CHECK (position_state IN ('KNOWN','SOURCE_ZERO')),
        average_position INTEGER NULL,
        search_to_card_conversion_pct TEXT NOT NULL,
        search_to_order_conversion_pct TEXT NOT NULL,
        ordered_units INTEGER NOT NULL CHECK (ordered_units >= 0),
        ordered_revenue_rub TEXT NOT NULL,
        UNIQUE (product_id, search_query_id, period_start, period_end, revision),
        CHECK ((position_state = 'KNOWN' AND average_position > 0) OR
               (position_state = 'SOURCE_ZERO' AND average_position IS NULL)))""")
    conn.execute("CREATE INDEX idx_product_query_current ON product_query_snapshots(product_id, period_end DESC, search_query_id, revision DESC)")
    conn.execute("CREATE INDEX idx_product_query_history ON product_query_snapshots(search_query_id, product_id, period_end DESC, revision DESC)")
    conn.execute("CREATE INDEX idx_product_query_import_batch_id ON product_query_snapshots(import_batch_id)")
    conn.execute("CREATE INDEX idx_product_query_source_artifact_id ON product_query_snapshots(source_artifact_id)")
    conn.execute("""CREATE TABLE query_metric_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_query_id INTEGER NOT NULL REFERENCES search_queries(id),
        period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision > 0),
        supersedes_snapshot_id INTEGER NULL REFERENCES query_metric_snapshots(id),
        payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
        import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id),
        imported_at TEXT NOT NULL,
        popularity_users INTEGER NOT NULL CHECK (popularity_users >= 0),
        dynamics_28d_pct TEXT NULL, dynamics_7d_pct TEXT NULL,
        cart_add_users INTEGER NOT NULL CHECK (cart_add_users >= 0),
        market_cart_conversion_pct TEXT NOT NULL,
        unique_buyers_with_orders INTEGER NOT NULL CHECK (unique_buyers_with_orders >= 0),
        market_order_conversion_pct TEXT NOT NULL,
        ordered_revenue_rub TEXT NOT NULL,
        no_action_queries INTEGER NOT NULL CHECK (no_action_queries >= 0),
        no_action_share_pct TEXT NOT NULL,
        UNIQUE (search_query_id, period_start, period_end, revision))""")
    conn.execute("CREATE INDEX idx_query_metric_current ON query_metric_snapshots(search_query_id, period_end DESC, revision DESC)")
    conn.execute("CREATE INDEX idx_query_metric_history ON query_metric_snapshots(period_end DESC, search_query_id, revision DESC)")
    conn.execute("CREATE INDEX idx_query_metric_import_batch_id ON query_metric_snapshots(import_batch_id)")
    conn.execute("CREATE INDEX idx_query_metric_source_artifact_id ON query_metric_snapshots(source_artifact_id)")
    conn.execute("ALTER TABLE import_batches ADD COLUMN period_start TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN period_end TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN report_generated_at TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN report_product_ozon_id TEXT NULL")
    conn.execute("ALTER TABLE import_batches ADD COLUMN sort_context TEXT NULL")
