import re
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from backend.domain.lineage import datetime_from_db, datetime_to_db
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text
from backend.domain.search_visibility import (
    CpoState,
    SEARCH_VISIBILITY_PAYLOAD_FIELDS,
    SearchVisibilitySnapshot,
    SearchVisibilityWriteResult,
)


_DECIMAL_FIELDS = {
    "overall_score",
    "cpc_rub",
    "cpo_pct",
    "relevance_score",
    "rating",
    "buyer_price_rub",
    "popularity_score",
    "price_index_pct",
}


def _optional_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _snapshot_from_row(row: sqlite3.Row) -> SearchVisibilitySnapshot:
    ozon_promotion = row["ozon_promotion"]
    if ozon_promotion not in (0, 1):
        raise ValueError("stored ozon_promotion must be 0 or 1")
    return SearchVisibilitySnapshot(
        id=row["id"],
        product_id=row["product_id"],
        search_query_id=row["search_query_id"],
        cluster_id=row["cluster_id"],
        observed_at=datetime_from_db(row["observed_at"]),
        revision=row["revision"],
        supersedes_snapshot_id=row["supersedes_snapshot_id"],
        payload_sha256=row["payload_sha256"],
        import_batch_id=row["import_batch_id"],
        source_artifact_id=row["source_artifact_id"],
        imported_at=datetime_from_db(row["imported_at"]),
        source_title=row["source_title"],
        seller_name=row["seller_name"],
        position=row["position"],
        overall_score=Decimal(row["overall_score"]),
        promotion_status=row["promotion_status"],
        cpc_rub=Decimal(row["cpc_rub"]),
        promotion_strategy=row["promotion_strategy"],
        cpo_state=CpoState(row["cpo_state"]),
        cpo_pct=_optional_decimal(row["cpo_pct"]),
        relevance_score=Decimal(row["relevance_score"]),
        rating=_optional_decimal(row["rating"]),
        reviews_count=row["reviews_count"],
        buyer_price_rub=Decimal(row["buyer_price_rub"]),
        popularity_score=Decimal(row["popularity_score"]),
        ozon_promotion=bool(ozon_promotion),
        delivery_label=row["delivery_label"],
        delivery_min_days=row["delivery_min_days"],
        delivery_max_days=row["delivery_max_days"],
        price_index_pct=Decimal(row["price_index_pct"]),
    )


def _encode_snapshot_values(values: Mapping[str, object]) -> tuple[object, ...]:
    if set(values) != set(SEARCH_VISIBILITY_PAYLOAD_FIELDS):
        raise ValueError("snapshot payload fields do not match frozen contract")
    encoded: list[object] = []
    for field in SEARCH_VISIBILITY_PAYLOAD_FIELDS:
        value = values[field]
        if field in _DECIMAL_FIELDS and value is not None:
            value = canonical_decimal_text(value)  # type: ignore[arg-type]
        elif field == "cpo_state":
            value = value.value if isinstance(value, CpoState) else CpoState(value).value
        elif field == "ozon_promotion":
            value = int(value)  # type: ignore[arg-type]
        encoded.append(value)
    return tuple(encoded)


class SearchVisibilitySnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def find_current(
        self,
        *,
        product_id: int,
        search_query_id: int,
        cluster_id: int,
        observed_at: datetime,
    ) -> SearchVisibilitySnapshot | None:
        observed_at_db = datetime_to_db(observed_at)
        row = self._conn.execute(
            """SELECT * FROM search_visibility_snapshots
               WHERE product_id = ? AND search_query_id = ? AND cluster_id = ?
                 AND observed_at = ?
               ORDER BY revision DESC LIMIT 1""",
            (product_id, search_query_id, cluster_id, observed_at_db),
        ).fetchone()
        return None if row is None else _snapshot_from_row(row)

    def resolve_revision(
        self,
        *,
        product_id: int,
        search_query_id: int,
        cluster_id: int,
        observed_at: datetime,
        payload_sha256: str,
        import_batch_id: int,
        source_artifact_id: int,
        imported_at: datetime,
        snapshot_values: Mapping[str, object],
    ) -> SearchVisibilityWriteResult:
        if re.fullmatch(r"[0-9a-f]{64}", payload_sha256) is None:
            raise ValueError("invalid payload hash")
        encoded_values = _encode_snapshot_values(snapshot_values)
        observed_at_db = datetime_to_db(observed_at)
        imported_at_db = datetime_to_db(imported_at)
        current = self.find_current(
            product_id=product_id,
            search_query_id=search_query_id,
            cluster_id=cluster_id,
            observed_at=observed_at,
        )
        if current is not None and current.payload_sha256 == payload_sha256:
            return SearchVisibilityWriteResult(SnapshotWriteKind.DUPLICATE, current)

        revision = 1 if current is None else current.revision + 1
        supersedes_id = None if current is None else current.id
        columns = ", ".join(SEARCH_VISIBILITY_PAYLOAD_FIELDS)
        placeholders = ", ".join("?" for _ in SEARCH_VISIBILITY_PAYLOAD_FIELDS)
        cursor = self._conn.execute(
            f"""INSERT INTO search_visibility_snapshots
                (product_id, search_query_id, cluster_id, observed_at, revision,
                 supersedes_snapshot_id, payload_sha256, import_batch_id,
                 source_artifact_id, imported_at, {columns})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {placeholders})""",
            (
                product_id, search_query_id, cluster_id, observed_at_db, revision,
                supersedes_id, payload_sha256, import_batch_id, source_artifact_id,
                imported_at_db, *encoded_values,
            ),
        )
        row = self._conn.execute(
            "SELECT * FROM search_visibility_snapshots WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        assert row is not None
        snapshot = _snapshot_from_row(row)
        kind = SnapshotWriteKind.NEW if current is None else SnapshotWriteKind.CORRECTED
        return SearchVisibilityWriteResult(kind, snapshot)
