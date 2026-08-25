from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Mapping

from backend.domain.lineage import ImportStatus, SourceArtifact, normalized_payload_sha256
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text


@dataclass(frozen=True)
class SearchQuery:
    id: int
    query_text: str
    created_at: datetime


@dataclass(frozen=True)
class Cluster:
    id: int
    name: str
    created_at: datetime


class CpoState(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"

class CpcState(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class SearchVisibilitySnapshot:
    id: int
    product_id: int
    search_query_id: int
    cluster_id: int
    observed_at: datetime
    revision: int
    supersedes_snapshot_id: int | None
    payload_sha256: str
    import_batch_id: int
    source_artifact_id: int
    imported_at: datetime
    source_title: str
    seller_name: str
    position: int
    overall_score: Decimal
    promotion_status: str
    cpc_state: CpcState
    cpc_rub: Decimal | None
    promotion_strategy: str
    cpo_state: CpoState
    cpo_pct: Decimal | None
    relevance_score: Decimal
    rating: Decimal | None
    reviews_count: int | None
    buyer_price_rub: Decimal
    popularity_score: Decimal
    ozon_promotion: bool
    delivery_label: str
    delivery_min_days: int
    delivery_max_days: int
    price_index_pct: Decimal


@dataclass(frozen=True)
class SearchVisibilityWriteResult:
    kind: SnapshotWriteKind
    snapshot: SearchVisibilitySnapshot


@dataclass(frozen=True)
class SearchVisibilityRowError:
    row: int
    code: str
    message: str


@dataclass(frozen=True)
class ParsedSearchVisibilityRow:
    source_row: int
    ozon_product_id: str
    snapshot_values: dict[str, object]
    payload_sha256: str


@dataclass(frozen=True)
class ParsedSearchVisibilityReport:
    observed_at: datetime
    query_text: str
    cluster_name: str
    declared_rows: int
    rows_seen: int
    rows: tuple[ParsedSearchVisibilityRow, ...]
    row_errors: tuple[SearchVisibilityRowError, ...]
    duplicate_input_rows: int
    warnings_count: int


@dataclass(frozen=True)
class OzonSearchVisibilityImportSummary:
    import_batch_id: int
    source: str
    import_kind: str
    status: ImportStatus
    observed_at: datetime | None
    query_text: str | None
    cluster_name: str | None
    declared_rows: int | None
    rows_seen: int
    rows_accepted: int
    rows_skipped: int
    duplicate_observations: int
    new_observations: int
    corrected_revisions: int
    warnings_count: int
    row_errors_total: int
    started_at: datetime
    finished_at: datetime | None
    source_artifact: SourceArtifact | None


@dataclass(frozen=True)
class OzonSearchVisibilityImportResult:
    import_batch_id: int
    report_type: Literal["OZON_SEARCH_VISIBILITY"]
    status: ImportStatus
    observed_at: datetime | None
    query_text: str | None
    cluster_name: str | None
    declared_rows: int | None
    rows_seen: int
    rows_accepted: int
    rows_skipped: int
    duplicate_observations: int
    new_observations: int
    corrected_revisions: int
    warnings_count: int
    row_errors_total: int
    row_errors: tuple[SearchVisibilityRowError, ...]
    row_errors_truncated: bool
    source_artifact: SourceArtifact
    imported_at: datetime


class OzonSearchVisibilityError(ValueError): pass
class SearchVisibilityUnsupportedWorkbook(OzonSearchVisibilityError): pass
class SearchVisibilityWrongReportType(OzonSearchVisibilityError): pass
class SearchVisibilityIncompatibleReportSchema(OzonSearchVisibilityError): pass
class SearchVisibilityInvalidObservedAt(OzonSearchVisibilityError): pass
class SearchVisibilityInvalidSearchContext(OzonSearchVisibilityError): pass
class SearchVisibilityInvalidProductIdentity(OzonSearchVisibilityError): pass
class SearchVisibilityInvalidMetricValue(OzonSearchVisibilityError): pass
class SearchVisibilityConflictingObservationRows(OzonSearchVisibilityError): pass
class SearchVisibilityNoUsableRows(OzonSearchVisibilityError): pass
class SearchVisibilityConcurrentImportConflict(OzonSearchVisibilityError): pass
class SearchVisibilityUploadTooLarge(OzonSearchVisibilityError): pass
class SearchVisibilityUnsupportedUploadMediaType(OzonSearchVisibilityError): pass
class SearchVisibilityImportPersistenceError(OzonSearchVisibilityError): pass


class OzonSearchVisibilityImportFailure(Exception):
    def __init__(self, *, error: OzonSearchVisibilityError,
                 result: OzonSearchVisibilityImportResult | None) -> None:
        super().__init__(str(error))
        self.error = error
        self.result = result


SEARCH_VISIBILITY_PAYLOAD_FIELDS = tuple(
    field.name for field in fields(SearchVisibilitySnapshot)[11:]
)


def search_visibility_snapshot_payload(values: Mapping[str, object]) -> dict[str, object]:
    if set(values) != set(SEARCH_VISIBILITY_PAYLOAD_FIELDS):
        raise ValueError("snapshot payload fields do not match frozen contract")
    result: dict[str, object] = {}
    for name in SEARCH_VISIBILITY_PAYLOAD_FIELDS:
        value = values[name]
        if isinstance(value, Decimal):
            value = canonical_decimal_text(value)
        elif isinstance(value, (CpcState, CpoState)):
            value = value.value
        result[name] = value
    return result


def search_visibility_payload_sha256(values: Mapping[str, object]) -> str:
    return normalized_payload_sha256(search_visibility_snapshot_payload(values))
