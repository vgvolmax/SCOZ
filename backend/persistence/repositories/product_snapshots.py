import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal

from backend.domain.lineage import datetime_from_db, datetime_to_db
from backend.domain.product_snapshot import (
    PAYLOAD_FIELDS, ProductSnapshot, SnapshotWriteKind, SnapshotWriteResult,
    canonical_decimal_text,
)


class ProductSnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: self._conn = conn

    def get(self, snapshot_id: int) -> ProductSnapshot | None:
        row = self._conn.execute("SELECT * FROM product_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        return None if row is None else self._map(row)

    def current_for_key(self, product_id: int, report_generated_on: date, report_window_days: int) -> ProductSnapshot | None:
        row = self._conn.execute("SELECT * FROM product_snapshots WHERE product_id=? AND report_generated_on=? AND report_window_days=? ORDER BY revision DESC LIMIT 1", (product_id, report_generated_on.isoformat(), report_window_days)).fetchone()
        return None if row is None else self._map(row)

    def latest_for_product(self, product_id: int) -> ProductSnapshot | None:
        row = self._conn.execute("SELECT * FROM product_snapshots WHERE product_id=? ORDER BY report_generated_on DESC, report_window_days DESC, revision DESC LIMIT 1", (product_id,)).fetchone()
        return None if row is None else self._map(row)

    def resolve_revision(self, *, product_id: int, report_generated_on: date, report_window_days: int, payload_sha256: str, import_batch_id: int, source_artifact_id: int, imported_at: datetime, values: dict[str, object]) -> SnapshotWriteResult:
        if not re.fullmatch(r"[0-9a-f]{64}", payload_sha256): raise ValueError("invalid payload hash")
        if report_window_days <= 0 or imported_at.tzinfo is None: raise ValueError("invalid snapshot metadata")
        current = self.current_for_key(product_id, report_generated_on, report_window_days)
        if current is not None and current.payload_sha256 == payload_sha256:
            return SnapshotWriteResult(SnapshotWriteKind.DUPLICATE, current)
        revision = 1 if current is None else current.revision + 1
        supersedes = None if current is None else current.id
        columns = PAYLOAD_FIELDS
        encoded = [self._encode(values[name]) for name in columns]
        cursor = self._conn.execute(f"INSERT INTO product_snapshots (product_id,report_generated_on,report_window_days,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,{','.join(columns)}) VALUES ({','.join('?' for _ in range(9 + len(columns)))})", (product_id, report_generated_on.isoformat(), report_window_days, revision, supersedes, payload_sha256, import_batch_id, source_artifact_id, datetime_to_db(imported_at), *encoded))
        snapshot = self.get(cursor.lastrowid)
        assert snapshot is not None
        return SnapshotWriteResult(SnapshotWriteKind.NEW if current is None else SnapshotWriteKind.CORRECTED, snapshot)

    @staticmethod
    def _encode(value: object) -> object:
        if isinstance(value, Decimal): return canonical_decimal_text(value)
        if isinstance(value, date): return value.isoformat()
        return value

    @staticmethod
    def _map(row: sqlite3.Row) -> ProductSnapshot:
        decimal_names = {"ordered_amount_rub","turnover_change_pct","average_price_rub","minimum_price_rub","buyout_share_pct","missed_sales_source_value","avg_daily_sales_rub","volume_l","impression_to_order_pct","search_catalog_to_cart_pct","card_to_cart_pct","promotion_discount_source_value","promotion_order_amount_share_pct","total_drr_pct"}
        values = dict(row)
        for name in decimal_names:
            if values[name] is not None: values[name] = Decimal(values[name])
        values["report_generated_on"] = date.fromisoformat(values["report_generated_on"])
        values["card_created_on"] = date.fromisoformat(values["card_created_on"])
        values["imported_at"] = datetime_from_db(values["imported_at"])
        return ProductSnapshot(**values)
