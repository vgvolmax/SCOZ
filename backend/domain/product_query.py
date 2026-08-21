from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Mapping

from backend.domain.lineage import ImportStatus, SourceArtifact, normalized_payload_sha256
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text


class ProductQueryPositionState(str, Enum):
    KNOWN = "KNOWN"
    SOURCE_ZERO = "SOURCE_ZERO"


@dataclass(frozen=True)
class ProductQuerySnapshot:
    id: int
    product_id: int
    search_query_id: int
    period_start: date
    period_end: date
    revision: int
    supersedes_snapshot_id: int | None
    payload_sha256: str
    import_batch_id: int
    source_artifact_id: int
    imported_at: datetime
    searched_users: int
    seen_users: int
    position_state: ProductQueryPositionState
    average_position: int | None
    search_to_card_conversion_pct: Decimal
    search_to_order_conversion_pct: Decimal
    ordered_units: int
    ordered_revenue_rub: Decimal


@dataclass(frozen=True)
class ProductQueryWriteResult:
    kind: SnapshotWriteKind
    snapshot: ProductQuerySnapshot


@dataclass(frozen=True)
class ProductQueryRowError:
    row: int
    code: str
    message: str


@dataclass(frozen=True)
class ParsedProductQueryRow:
    source_row: int
    query_text: str
    snapshot_values: dict[str, object]
    payload_sha256: str


@dataclass(frozen=True)
class ParsedSellerQueriesReport:
    generated_at: datetime
    period_start: date
    period_end: date
    ozon_product_id: str
    article: str
    title: str
    rows_seen: int
    rows: tuple[ParsedProductQueryRow, ...]
    row_errors: tuple[ProductQueryRowError, ...]
    duplicate_input_rows: int
    warnings_count: int


@dataclass(frozen=True)
class OzonSellerQueriesImportSummary:
    import_batch_id: int; source: str; import_kind: str; status: ImportStatus
    generated_at: datetime | None; period_start: date | None; period_end: date | None
    product_ozon_id: str | None; rows_seen: int; rows_accepted: int; rows_skipped: int
    duplicate_observations: int; new_observations: int; corrected_revisions: int
    warnings_count: int; row_errors_total: int; started_at: datetime
    finished_at: datetime | None; source_artifact: SourceArtifact | None


@dataclass(frozen=True)
class OzonSellerQueriesImportResult:
    import_batch_id: int
    report_type: Literal["OZON_OWN_PRODUCT_QUERIES"]
    status: ImportStatus
    generated_at: datetime | None; period_start: date | None; period_end: date | None
    product_ozon_id: str | None; rows_seen: int; rows_accepted: int; rows_skipped: int
    duplicate_observations: int; new_observations: int; corrected_revisions: int
    warnings_count: int; row_errors_total: int; row_errors: tuple[ProductQueryRowError, ...]
    row_errors_truncated: bool; source_artifact: SourceArtifact; imported_at: datetime


class OzonSellerQueriesError(ValueError): pass
class SellerQueriesUnsupportedWorkbook(OzonSellerQueriesError): pass
class SellerQueriesWrongReportType(OzonSellerQueriesError): pass
class SellerQueriesIncompatibleReportSchema(OzonSellerQueriesError): pass
class SellerQueriesInvalidGeneratedAt(OzonSellerQueriesError): pass
class SellerQueriesInvalidReportPeriod(OzonSellerQueriesError): pass
class SellerQueriesInvalidProductContext(OzonSellerQueriesError): pass
class SellerQueriesConflictingObservationRows(OzonSellerQueriesError): pass
class SellerQueriesNoUsableRows(OzonSellerQueriesError): pass
class SellerQueriesConcurrentImportConflict(OzonSellerQueriesError): pass
class SellerQueriesUploadTooLarge(OzonSellerQueriesError): pass
class SellerQueriesUnsupportedUploadMediaType(OzonSellerQueriesError): pass
class SellerQueriesImportPersistenceError(OzonSellerQueriesError): pass


class OzonSellerQueriesImportFailure(Exception):
    def __init__(self, *, error: OzonSellerQueriesError, result: OzonSellerQueriesImportResult | None):
        super().__init__(str(error)); self.error = error; self.result = result


PRODUCT_QUERY_PAYLOAD_FIELDS = ("searched_users", "seen_users", "position_state", "average_position", "search_to_card_conversion_pct", "search_to_order_conversion_pct", "ordered_units", "ordered_revenue_rub")


def product_query_payload_sha256(values: Mapping[str, object]) -> str:
    if set(values) != set(PRODUCT_QUERY_PAYLOAD_FIELDS):
        raise ValueError("snapshot payload fields do not match frozen contract")
    payload = {}
    for name in PRODUCT_QUERY_PAYLOAD_FIELDS:
        value = values[name]
        if isinstance(value, Decimal): value = canonical_decimal_text(value)
        elif isinstance(value, Enum): value = value.value
        elif isinstance(value, float): raise TypeError("float is not a canonical payload value")
        payload[name] = value
    return normalized_payload_sha256(payload)
