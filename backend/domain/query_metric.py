from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Mapping

from backend.domain.lineage import ImportStatus, SourceArtifact, normalized_payload_sha256
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text

@dataclass(frozen=True)
class QueryMetricSnapshot:
    id: int; search_query_id: int; period_start: date; period_end: date; revision: int
    supersedes_snapshot_id: int | None; payload_sha256: str; import_batch_id: int
    source_artifact_id: int; imported_at: datetime; popularity_users: int
    dynamics_28d_pct: Decimal | None; dynamics_7d_pct: Decimal | None; cart_add_users: int
    market_cart_conversion_pct: Decimal; unique_buyers_with_orders: int
    market_order_conversion_pct: Decimal; ordered_revenue_rub: Decimal
    no_action_queries: int; no_action_share_pct: Decimal

@dataclass(frozen=True)
class QueryMetricWriteResult:
    kind: SnapshotWriteKind; snapshot: QueryMetricSnapshot

@dataclass(frozen=True)
class QueryMetricRowError:
    row: int; code: str; message: str

@dataclass(frozen=True)
class ParsedQueryMetricRow:
    source_row: int; query_text: str; snapshot_values: dict[str, object]; payload_sha256: str

@dataclass(frozen=True)
class ParsedQueryMetricsReport:
    period_start: date; period_end: date; sort_context: str; rows_seen: int
    rows: tuple[ParsedQueryMetricRow, ...]; row_errors: tuple[QueryMetricRowError, ...]
    duplicate_input_rows: int; warnings_count: int

@dataclass(frozen=True)
class OzonQueryMetricsImportSummary:
    import_batch_id: int; source: str; import_kind: str; status: ImportStatus
    period_start: date | None; period_end: date | None; sort_context: str | None
    rows_seen: int; rows_accepted: int; rows_skipped: int; duplicate_observations: int
    new_observations: int; corrected_revisions: int; warnings_count: int
    row_errors_total: int; started_at: datetime; finished_at: datetime | None
    source_artifact: SourceArtifact | None

@dataclass(frozen=True)
class OzonQueryMetricsImportResult:
    import_batch_id: int; report_type: Literal["OZON_QUERY_METRICS"]; status: ImportStatus
    period_start: date | None; period_end: date | None; sort_context: str | None
    rows_seen: int; rows_accepted: int; rows_skipped: int; duplicate_observations: int
    new_observations: int; corrected_revisions: int; warnings_count: int
    row_errors_total: int; row_errors: tuple[QueryMetricRowError, ...]
    row_errors_truncated: bool; source_artifact: SourceArtifact; imported_at: datetime

class OzonQueryMetricsError(ValueError): pass
class QueryMetricsUnsupportedWorkbook(OzonQueryMetricsError): pass
class QueryMetricsWrongReportType(OzonQueryMetricsError): pass
class QueryMetricsIncompatibleReportSchema(OzonQueryMetricsError): pass
class QueryMetricsInvalidReportPeriod(OzonQueryMetricsError): pass
class QueryMetricsConflictingObservationRows(OzonQueryMetricsError): pass
class QueryMetricsNoUsableRows(OzonQueryMetricsError): pass
class QueryMetricsConcurrentImportConflict(OzonQueryMetricsError): pass
class QueryMetricsUploadTooLarge(OzonQueryMetricsError): pass
class QueryMetricsUnsupportedUploadMediaType(OzonQueryMetricsError): pass
class QueryMetricsImportPersistenceError(OzonQueryMetricsError): pass

class OzonQueryMetricsImportFailure(Exception):
    def __init__(self, *, error: OzonQueryMetricsError, result: OzonQueryMetricsImportResult | None):
        super().__init__(str(error)); self.error = error; self.result = result

QUERY_METRIC_PAYLOAD_FIELDS = ("popularity_users", "dynamics_28d_pct", "dynamics_7d_pct", "cart_add_users", "market_cart_conversion_pct", "unique_buyers_with_orders", "market_order_conversion_pct", "ordered_revenue_rub", "no_action_queries", "no_action_share_pct")

def query_metric_payload_sha256(values: Mapping[str, object]) -> str:
    if set(values) != set(QUERY_METRIC_PAYLOAD_FIELDS): raise ValueError("snapshot payload fields do not match frozen contract")
    payload = {}
    for name in QUERY_METRIC_PAYLOAD_FIELDS:
        value = values[name]
        if isinstance(value, Decimal): value = canonical_decimal_text(value)
        elif isinstance(value, float): raise TypeError("float is not a canonical payload value")
        payload[name] = value
    return normalized_payload_sha256(payload)
