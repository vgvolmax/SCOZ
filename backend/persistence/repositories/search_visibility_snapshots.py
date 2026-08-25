import re
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from backend.domain.lineage import datetime_from_db, datetime_to_db
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text
from backend.domain.search_visibility import (
    CpcState, CpoState, SEARCH_VISIBILITY_PAYLOAD_FIELDS, SearchVisibilitySnapshot,
    SearchVisibilityWriteResult,
)


_DECIMAL_FIELDS = {
    "overall_score", "cpc_rub", "cpo_pct", "relevance_score", "rating",
    "buyer_price_rub", "popularity_score", "price_index_pct",
}


class SearchVisibilitySnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def find_current(self, *, product_id: int, search_query_id: int,
                     cluster_id: int, observed_at: datetime) -> SearchVisibilitySnapshot | None:
        observed = datetime_to_db(observed_at)
        row = self._conn.execute(
            """SELECT * FROM search_visibility_snapshots
               WHERE product_id=? AND search_query_id=? AND cluster_id=? AND observed_at=?
               ORDER BY revision DESC LIMIT 1""",
            (product_id, search_query_id, cluster_id, observed),
        ).fetchone()
        return None if row is None else self._map(row)

    def resolve_revision(self, *, product_id: int, search_query_id: int,
                         cluster_id: int, observed_at: datetime,
                         payload_sha256: str, import_batch_id: int,
                         source_artifact_id: int, imported_at: datetime,
                         snapshot_values: Mapping[str, object]) -> SearchVisibilityWriteResult:
        if not re.fullmatch(r"[0-9a-f]{64}", payload_sha256):
            raise ValueError("invalid payload hash")
        observed = datetime_to_db(observed_at)
        imported = datetime_to_db(imported_at)
        if set(snapshot_values) != set(SEARCH_VISIBILITY_PAYLOAD_FIELDS):
            raise ValueError("snapshot payload fields do not match frozen contract")
        current = self.find_current(product_id=product_id, search_query_id=search_query_id,
                                    cluster_id=cluster_id, observed_at=observed_at)
        if current is not None and current.payload_sha256 == payload_sha256:
            return SearchVisibilityWriteResult(SnapshotWriteKind.DUPLICATE, current)
        revision = 1 if current is None else current.revision + 1
        supersedes = None if current is None else current.id
        encoded = [self._encode(name, snapshot_values[name]) for name in SEARCH_VISIBILITY_PAYLOAD_FIELDS]
        columns = ",".join(SEARCH_VISIBILITY_PAYLOAD_FIELDS)
        placeholders = ",".join("?" for _ in range(10 + len(encoded)))
        cursor = self._conn.execute(
            f"""INSERT INTO search_visibility_snapshots
            (product_id,search_query_id,cluster_id,observed_at,revision,supersedes_snapshot_id,
             payload_sha256,import_batch_id,source_artifact_id,imported_at,{columns})
            VALUES ({placeholders})""",
            (product_id, search_query_id, cluster_id, observed, revision, supersedes,
             payload_sha256, import_batch_id, source_artifact_id, imported, *encoded),
        )
        row = self._conn.execute("SELECT * FROM search_visibility_snapshots WHERE id=?", (cursor.lastrowid,)).fetchone()
        assert row is not None
        return SearchVisibilityWriteResult(
            SnapshotWriteKind.NEW if current is None else SnapshotWriteKind.CORRECTED,
            self._map(row),
        )

    @staticmethod
    def _encode(name: str, value: object) -> object:
        if isinstance(value, Decimal):
            return canonical_decimal_text(value)
        if name == "cpc_state" and isinstance(value, CpcState):
            return value.value
        if name == "cpo_state" and isinstance(value, CpoState):
            return value.value
        if name == "ozon_promotion" and isinstance(value, bool):
            return int(value)
        return value

    @staticmethod
    def _map(row: sqlite3.Row) -> SearchVisibilitySnapshot:
        values = dict(row)
        for name in _DECIMAL_FIELDS:
            if values[name] is not None:
                values[name] = Decimal(values[name])
        values["cpo_state"] = CpoState(values["cpo_state"])
        values["cpc_state"] = CpcState(values["cpc_state"])
        if values["ozon_promotion"] not in (0, 1):
            raise ValueError("stored boolean must be 0 or 1")
        values["ozon_promotion"] = bool(values["ozon_promotion"])
        values["observed_at"] = datetime_from_db(values["observed_at"])
        values["imported_at"] = datetime_from_db(values["imported_at"])
        return SearchVisibilitySnapshot(**values)
