from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from backend.domain.benchmark_selection import RelevantQueryReadiness, SourcePeriod


class ProductDataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"


@dataclass(frozen=True)
class ProductEntry:
    product_id: int
    ozon_product_id: str
    is_owned: bool
    title: str | None
    seller_name: str | None
    brand: str | None
    product_data_status: ProductDataStatus
    report_generated_on: date | None
    report_window_days: int | None
    imported_at: datetime | None


@dataclass(frozen=True)
class ProductWorkspaceQueryContext:
    readiness: RelevantQueryReadiness
    latest_period: SourcePeriod | None
    selected_count: int


class WorkspaceBenchmarkStatus(str, Enum):
    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True)
class ProductWorkspaceBenchmarkContext:
    status: WorkspaceBenchmarkStatus
    revision_id: int | None
    revision: int | None
    member_count: int


@dataclass(frozen=True)
class ProductWorkspaceContext:
    product: ProductEntry
    queries: ProductWorkspaceQueryContext
    benchmark: ProductWorkspaceBenchmarkContext


@dataclass(frozen=True)
class ProductCatalogPage:
    items: tuple[ProductEntry, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class OwnedProductList:
    items: tuple[ProductEntry, ...]
    total: int
