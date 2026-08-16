from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from backend.domain.lineage import ImportStatus, SourceArtifact, normalized_payload_sha256


class SnapshotWriteStatus(str, Enum):
    NEW = "NEW"
    CORRECTED = "CORRECTED"
    DUPLICATE = "DUPLICATE"


@dataclass(frozen=True)
class ProductSnapshot:
    id: int
    product_id: int
    report_generated_on: date
    report_window_days: int
    revision: int
    supersedes_snapshot_id: int | None
    payload_sha256: str
    import_batch_id: int
    source_artifact_id: int
    imported_at: datetime
    product_url: str
    title: str
    seller_name: str
    brand: str
    category_level_1: str
    category_level_3: str
    product_badges: str | None
    ordered_amount_rub: Decimal
    turnover_change_pct: Decimal | None
    ordered_units: int
    average_price_rub: Decimal
    minimum_price_rub: Decimal
    buyout_share_pct: Decimal | None
    missed_sales_source_value: Decimal
    out_of_stock_days: int | None
    out_of_stock_window_days: int | None
    avg_daily_sales_rub: Decimal
    avg_daily_sales_units: int
    stock_end_units: int
    fulfillment_scheme: str
    volume_l: Decimal
    impressions_total: int
    search_catalog_views: int
    card_views: int
    impression_to_order_pct: Decimal
    search_catalog_to_cart_pct: Decimal
    card_to_cart_pct: Decimal
    promotion_discount_source_value: Decimal
    promotion_order_amount_share_pct: Decimal
    promotion_days: int
    promotion_window_days: int
    advertising_days: int
    advertising_window_days: int
    total_drr_pct: Decimal
    card_created_on: date


@dataclass(frozen=True)
class OzonProductsImportSummary:
    import_batch_id: int
    source: str
    import_kind: str
    status: ImportStatus
    report_generated_on: date | None
    report_window_days: int | None
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
class RowError:
    row_number: int
    code: str
    message: str


@dataclass(frozen=True)
class ParsedProductRow:
    ozon_product_id: str
    payload_sha256: str
    values: dict[str, object]


@dataclass(frozen=True)
class ParsedOzonProductsReport:
    report_generated_on: date
    report_window_days: int
    rows_seen: int
    rows: tuple[ParsedProductRow, ...]
    row_errors: tuple[RowError, ...]
    duplicate_observations: int
    warnings_count: int


@dataclass(frozen=True)
class ImportResult:
    import_batch_id: int
    report_type: str
    status: ImportStatus
    report_generated_on: date | None
    report_window_days: int | None
    rows_seen: int
    rows_accepted: int
    rows_skipped: int
    duplicate_observations: int
    new_observations: int
    corrected_revisions: int
    warnings_count: int
    row_errors_total: int
    row_errors: tuple[RowError, ...]
    row_errors_truncated: bool
    source_artifact: SourceArtifact
    imported_at: datetime
    readiness: str


class OzonProductsError(ValueError): pass
class UnsupportedWorkbook(OzonProductsError): pass
class WrongReportType(OzonProductsError): pass
class IncompatibleReportSchema(OzonProductsError): pass
class InvalidReportPeriod(OzonProductsError): pass
class InvalidProductIdentity(OzonProductsError): pass
class InvalidMetricValue(OzonProductsError): pass
class CategoryMismatch(OzonProductsError): pass
class ConflictingObservationRows(OzonProductsError): pass
class ConcurrentImportConflict(OzonProductsError): pass
class UploadTooLarge(OzonProductsError): pass
class UnsupportedUploadMediaType(OzonProductsError): pass
class ImportPersistenceError(OzonProductsError): pass


class OzonProductsImportFailure(Exception):
    def __init__(self, *, error: OzonProductsError, result: ImportResult | None) -> None:
        super().__init__(str(error))
        self.error = error
        self.result = result


PAYLOAD_FIELDS = tuple(field.name for field in fields(ProductSnapshot)[10:])


def canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise InvalidMetricValue("decimal must be finite")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if not text or Decimal(text) == 0 else text


def snapshot_payload(values: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in PAYLOAD_FIELDS:
        value = values[key]
        if isinstance(value, Decimal): value = canonical_decimal(value)
        elif isinstance(value, date): value = value.isoformat()
        result[key] = value
    return result


def snapshot_payload_sha256(values: dict[str, object]) -> str:
    return normalized_payload_sha256(snapshot_payload(values))
