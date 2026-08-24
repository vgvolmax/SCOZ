from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal


class RelevantQueryReadiness(str, Enum):
    READY = "READY"
    EMPTY_SELECTION = "EMPTY_SELECTION"
    NO_OWN_QUERY_DATA = "NO_OWN_QUERY_DATA"


@dataclass(frozen=True)
class SourcePeriod:
    period_start: date
    period_end: date


@dataclass(frozen=True)
class RelevantQueryOption:
    search_query_id: int
    query_text: str
    selected: bool
    selected_at: datetime | None
    in_latest_period: bool
    evidence_period: SourcePeriod
    searched_users: int | None
    seen_users: int | None
    average_position: int | None
    ordered_units: int | None
    ordered_revenue_rub: Decimal | None


@dataclass(frozen=True)
class RelevantQuerySelection:
    product_id: int
    readiness: RelevantQueryReadiness
    latest_period: SourcePeriod | None
    items: tuple[RelevantQueryOption, ...]
    selected_count: int


@dataclass(frozen=True)
class RelevantQueryWriteResult:
    selection: RelevantQuerySelection
    changed: bool


class PhotoStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"


class CandidateReadiness(str, Enum):
    READY = "READY"
    NO_CANDIDATE_EVIDENCE = "NO_CANDIDATE_EVIDENCE"


@dataclass(frozen=True)
class BenchmarkCandidate:
    product_id: int
    ozon_product_id: str
    source_title: str | None
    seller_name: str | None
    contextual_price_rub: Decimal | None
    representative_observed_at: datetime | None
    matched_relevant_query_count: int
    matched_cluster_count: int
    best_position: int | None
    photo_status: PhotoStatus
    photo_url: str | None
    already_selected_in_current_benchmark: bool
    origin: Literal["SEARCH_VISIBILITY", "MANUAL"]


@dataclass(frozen=True)
class CandidatePage:
    product_id: int
    readiness: CandidateReadiness
    items: tuple[BenchmarkCandidate, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class ManualCandidateWriteResult:
    created: bool
    candidate: BenchmarkCandidate


@dataclass(frozen=True)
class BenchmarkSet:
    id: int
    own_product_id: int
    created_at: datetime


@dataclass(frozen=True)
class BenchmarkMember:
    benchmark_set_revision_id: int
    product_id: int
    ozon_product_id: str


@dataclass(frozen=True)
class BenchmarkSetRevision:
    id: int
    benchmark_set_id: int
    revision: int
    created_at: datetime
    members: tuple[BenchmarkMember, ...]


@dataclass(frozen=True)
class BenchmarkComposition:
    benchmark_set: BenchmarkSet | None
    current_revision: BenchmarkSetRevision | None


class BenchmarkWriteKind(str, Enum):
    CREATED = "CREATED"
    CHANGED = "CHANGED"
    NO_CHANGE = "NO_CHANGE"


@dataclass(frozen=True)
class BenchmarkCompositionWriteResult:
    kind: BenchmarkWriteKind
    benchmark_set: BenchmarkSet
    revision: BenchmarkSetRevision


@dataclass(frozen=True)
class MPStatsProductPreview:
    ozon_product_id: str
    photo_status: PhotoStatus
    photo_url: str | None


class MPStatsConnectionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"


@dataclass(frozen=True)
class MPStatsConnectionResult:
    status: MPStatsConnectionStatus


class BenchmarkSelectionError(Exception):
    pass


class ProductNotOwnedError(BenchmarkSelectionError): pass
class NoOwnQueryDataError(BenchmarkSelectionError): pass
class RelevantQuerySelectionInvalidError(BenchmarkSelectionError): pass
class RelevantQuerySelectionEmptyError(BenchmarkSelectionError): pass
class ManualOzonSkuInvalidError(BenchmarkSelectionError): pass
class OwnProductCannotBeCompetitorError(BenchmarkSelectionError): pass
class BenchmarkEmptyError(BenchmarkSelectionError): pass
class BenchmarkMemberInvalidError(BenchmarkSelectionError): pass
class BenchmarkConcurrentWriteError(BenchmarkSelectionError): pass


class MPStatsError(Exception):
    pass


class MPStatsAuthError(MPStatsError): pass


class MPStatsRateLimitError(MPStatsError):
    def __init__(self, retry_after_seconds: int | None):
        super().__init__()
        self.retry_after_seconds = retry_after_seconds


class MPStatsPendingError(MPStatsError): pass
class MPStatsTimeoutError(MPStatsError): pass
class MPStatsNetworkError(MPStatsError): pass
class MPStatsMalformedResponseError(MPStatsError): pass
class MPStatsUpstreamError(MPStatsError): pass
