import sqlite3

RESULT_COLUMNS = ("report_generated_on TEXT", "report_window_days INTEGER", "rows_seen INTEGER", "rows_accepted INTEGER", "rows_skipped INTEGER", "duplicate_observations INTEGER", "new_observations INTEGER", "corrected_revisions INTEGER", "warnings_count INTEGER", "row_errors_total INTEGER")

def up(conn: sqlite3.Connection) -> None:
    for definition in RESULT_COLUMNS:
        conn.execute(f"ALTER TABLE import_batches ADD COLUMN {definition}")
    conn.execute("""CREATE TABLE product_snapshots (
id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
report_generated_on TEXT NOT NULL, report_window_days INTEGER NOT NULL CHECK (report_window_days > 0), revision INTEGER NOT NULL CHECK (revision > 0),
supersedes_snapshot_id INTEGER NULL, payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64), import_batch_id INTEGER NOT NULL, source_artifact_id INTEGER NOT NULL,
imported_at TEXT NOT NULL, product_url TEXT NOT NULL, title TEXT NOT NULL, seller_name TEXT NOT NULL, brand TEXT NOT NULL, category_level_1 TEXT NOT NULL,
category_level_3 TEXT NOT NULL, product_badges TEXT NULL, ordered_amount_rub TEXT NOT NULL, turnover_change_pct TEXT NULL,
ordered_units INTEGER NOT NULL CHECK (ordered_units >= 0), average_price_rub TEXT NOT NULL, minimum_price_rub TEXT NOT NULL, buyout_share_pct TEXT NULL,
missed_sales_source_value TEXT NOT NULL, out_of_stock_days INTEGER NULL CHECK (out_of_stock_days IS NULL OR out_of_stock_days >= 0),
out_of_stock_window_days INTEGER NULL CHECK (out_of_stock_window_days IS NULL OR out_of_stock_window_days > 0), avg_daily_sales_rub TEXT NOT NULL,
avg_daily_sales_units INTEGER NOT NULL CHECK (avg_daily_sales_units >= 0), stock_end_units INTEGER NOT NULL CHECK (stock_end_units >= 0), fulfillment_scheme TEXT NOT NULL,
volume_l TEXT NOT NULL, impressions_total INTEGER NOT NULL CHECK (impressions_total >= 0), search_catalog_views INTEGER NOT NULL CHECK (search_catalog_views >= 0),
card_views INTEGER NOT NULL CHECK (card_views >= 0), impression_to_order_pct TEXT NOT NULL, search_catalog_to_cart_pct TEXT NOT NULL, card_to_cart_pct TEXT NOT NULL,
promotion_discount_source_value TEXT NOT NULL, promotion_order_amount_share_pct TEXT NOT NULL, promotion_days INTEGER NOT NULL CHECK (promotion_days >= 0),
promotion_window_days INTEGER NOT NULL CHECK (promotion_window_days > 0), advertising_days INTEGER NOT NULL CHECK (advertising_days >= 0),
advertising_window_days INTEGER NOT NULL CHECK (advertising_window_days > 0), total_drr_pct TEXT NOT NULL, card_created_on TEXT NOT NULL,
FOREIGN KEY (product_id) REFERENCES products(id), FOREIGN KEY (supersedes_snapshot_id) REFERENCES product_snapshots(id), FOREIGN KEY (import_batch_id) REFERENCES import_batches(id),
FOREIGN KEY (source_artifact_id) REFERENCES source_artifacts(id), UNIQUE (product_id, report_generated_on, report_window_days, revision),
CHECK ((out_of_stock_days IS NULL) = (out_of_stock_window_days IS NULL)), CHECK (out_of_stock_days IS NULL OR out_of_stock_days <= out_of_stock_window_days),
CHECK (promotion_days <= promotion_window_days), CHECK (advertising_days <= advertising_window_days))""")
    conn.execute("CREATE INDEX idx_product_snapshots_current ON product_snapshots(product_id, report_generated_on, report_window_days, revision DESC)")
    conn.execute("CREATE INDEX idx_product_snapshots_latest_product ON product_snapshots(product_id, report_generated_on DESC, report_window_days, revision DESC)")
    conn.execute("CREATE INDEX idx_product_snapshots_import_batch_id ON product_snapshots(import_batch_id)")
    conn.execute("CREATE INDEX idx_product_snapshots_source_artifact_id ON product_snapshots(source_artifact_id)")
