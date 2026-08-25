"""Preserve numeric CPC observations while adding the explicit disabled state."""

import sqlite3
from decimal import Decimal

from backend.domain.search_visibility import CpcState, CpoState, search_visibility_payload_sha256

_DECIMALS = {"overall_score", "cpc_rub", "cpo_pct", "relevance_score", "rating",
             "buyer_price_rub", "popularity_score", "price_index_pct"}
_PAYLOAD = ("source_title", "seller_name", "position", "overall_score", "promotion_status",
            "cpc_state", "cpc_rub", "promotion_strategy", "cpo_state", "cpo_pct",
            "relevance_score", "rating", "reviews_count", "buyer_price_rub",
            "popularity_score", "ozon_promotion", "delivery_label", "delivery_min_days",
            "delivery_max_days", "price_index_pct")


def up(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE search_visibility_snapshots RENAME TO search_visibility_snapshots_v5")
    conn.execute("""CREATE TABLE search_visibility_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id),
        search_query_id INTEGER NOT NULL REFERENCES search_queries(id),
        cluster_id INTEGER NOT NULL REFERENCES clusters(id), observed_at TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision > 0),
        supersedes_snapshot_id INTEGER NULL REFERENCES search_visibility_snapshots(id),
        payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
        import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
        source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id),
        imported_at TEXT NOT NULL, source_title TEXT NOT NULL, seller_name TEXT NOT NULL,
        position INTEGER NOT NULL CHECK (position > 0), overall_score TEXT NOT NULL,
        promotion_status TEXT NOT NULL,
        cpc_state TEXT NOT NULL CHECK (cpc_state IN ('ACTIVE', 'DISABLED')),
        cpc_rub TEXT NULL, promotion_strategy TEXT NOT NULL,
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
        CHECK ((cpc_state = 'ACTIVE' AND cpc_rub IS NOT NULL) OR
               (cpc_state = 'DISABLED' AND cpc_rub IS NULL)),
        CHECK ((cpo_state = 'ACTIVE' AND cpo_pct IS NOT NULL) OR
               (cpo_state IN ('DISABLED', 'UNAVAILABLE') AND cpo_pct IS NULL)))""")
    new_columns = [row[1] for row in conn.execute("PRAGMA table_info(search_visibility_snapshots)")]
    select = ["'ACTIVE'" if column == "cpc_state" else column for column in new_columns]
    conn.execute(f"INSERT INTO search_visibility_snapshots ({','.join(new_columns)}) SELECT {','.join(select)} FROM search_visibility_snapshots_v5")
    # Payload hashes are normalized source payloads, so add ACTIVE canonically as
    # part of the migration.  A later re-import of identical numeric evidence
    # remains a duplicate rather than creating a synthetic correction revision.
    for row in conn.execute(f"SELECT id,{','.join(_PAYLOAD)} FROM search_visibility_snapshots").fetchall():
        values = dict(zip(_PAYLOAD, row[1:], strict=True))
        for name in _DECIMALS:
            if values[name] is not None: values[name] = Decimal(values[name])
        values["cpc_state"] = CpcState(values["cpc_state"])
        values["cpo_state"] = CpoState(values["cpo_state"])
        values["ozon_promotion"] = bool(values["ozon_promotion"])
        conn.execute("UPDATE search_visibility_snapshots SET payload_sha256=? WHERE id=?",
                     (search_visibility_payload_sha256(values), row[0]))
    conn.execute("DROP TABLE search_visibility_snapshots_v5")
    conn.execute("CREATE INDEX idx_search_visibility_current ON search_visibility_snapshots(product_id, search_query_id, cluster_id, observed_at, revision DESC)")
    conn.execute("CREATE INDEX idx_search_visibility_context ON search_visibility_snapshots(search_query_id, cluster_id, observed_at DESC, product_id, revision DESC)")
    conn.execute("CREATE INDEX idx_search_visibility_product ON search_visibility_snapshots(product_id, search_query_id, cluster_id, observed_at DESC, revision DESC)")
    conn.execute("CREATE INDEX idx_search_visibility_import_batch_id ON search_visibility_snapshots(import_batch_id)")
    conn.execute("CREATE INDEX idx_search_visibility_source_artifact_id ON search_visibility_snapshots(source_artifact_id)")
