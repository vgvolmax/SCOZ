import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal


type JSONPrimitive = None | bool | int | float | str
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]


class ImportStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ImportBatch:
    id: int
    source: str
    import_kind: str
    status: ImportStatus
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class SourceArtifact:
    id: int
    import_batch_id: int
    artifact_kind: str
    original_name: str | None
    content_sha256: str
    byte_size: int
    stored_relpath: str | None
    created_at: datetime


@dataclass(frozen=True)
class ImportHistoryItem:
    import_batch_id: int
    source: str
    import_kind: str
    report_type: Literal[
        "OZON_PRODUCTS", "OZON_SEARCH_VISIBILITY",
        "OZON_OWN_PRODUCT_QUERIES", "OZON_QUERY_METRICS",
    ]
    status: ImportStatus
    report_generated_on: date | None
    report_window_days: int | None
    observed_at: datetime | None
    query_text: str | None
    cluster_name: str | None
    declared_rows: int | None
    period_start: date | None
    period_end: date | None
    report_generated_at: datetime | None
    report_product_ozon_id: str | None
    sort_context: str | None
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


class ImportBatchNotFound(LookupError):
    pass


class InvalidImportStatusTransition(ValueError):
    pass


class InvalidSourceArtifactMetadata(ValueError):
    pass


class InvalidStoredRelativePath(ValueError):
    pass


__all__ = [
    "ImportBatch", "ImportBatchNotFound", "ImportStatus",
    "InvalidImportStatusTransition", "InvalidSourceArtifactMetadata",
    "InvalidStoredRelativePath", "SourceArtifact", "ImportHistoryItem", "utc_now",
    "datetime_to_db", "datetime_from_db", "normalized_payload_sha256",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def datetime_to_db(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def datetime_from_db(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("stored datetime must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def normalized_payload_sha256(payload: JSONValue) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
