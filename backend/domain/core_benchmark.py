from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping


class CoreBenchmarkMetricId(str, Enum):
    ORDERED_AMOUNT_RUB = "ordered_amount_rub"
    ORDERED_UNITS = "ordered_units"
    BUYOUT_SHARE_PCT = "buyout_share_pct"
    IMPRESSIONS_TOTAL = "impressions_total"
    SEARCH_CATALOG_VIEWS = "search_catalog_views"
    CARD_VIEWS = "card_views"
    IMPRESSION_TO_ORDER_PCT = "impression_to_order_pct"
    SEARCH_CATALOG_TO_CART_PCT = "search_catalog_to_cart_pct"
    CARD_TO_CART_PCT = "card_to_cart_pct"
    AVERAGE_PRICE_RUB = "average_price_rub"
    TOTAL_DRR_PCT = "total_drr_pct"
    ESTIMATED_AD_SPEND_RUB = "estimated_ad_spend_rub"
    ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB = "advertising_support_per_ordered_unit_rub"


CORE_BENCHMARK_METRIC_ORDER = tuple(CoreBenchmarkMetricId)


class MetricUnit(str, Enum):
    RUB = "RUB"
    UNITS = "UNITS"
    COUNT = "COUNT"
    PERCENTAGE_POINTS = "PERCENTAGE_POINTS"
    RUB_PER_ORDERED_UNIT = "RUB_PER_ORDERED_UNIT"


class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    CONTEXTUAL = "CONTEXTUAL"


class ComparisonPosition(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    BELOW_MEDIAN = "BELOW_MEDIAN"
    AT_MEDIAN = "AT_MEDIAN"
    ABOVE_MEDIAN = "ABOVE_MEDIAN"


class BenchmarkConfidence(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CoreBenchmarkReadiness(str, Enum):
    NO_BENCHMARK = "NO_BENCHMARK"
    NO_OWN_SOURCE_DATA = "NO_OWN_SOURCE_DATA"
    NO_COMPATIBLE_SAMPLE = "NO_COMPATIBLE_SAMPLE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    READY = "READY"


class MetricReadiness(str, Enum):
    READY = "READY"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    OWN_VALUE_UNAVAILABLE = "OWN_VALUE_UNAVAILABLE"


class MetricExclusionReason(str, Enum):
    NO_COMPATIBLE_OBSERVATION = "NO_COMPATIBLE_OBSERVATION"
    SOURCE_METRIC_UNAVAILABLE = "SOURCE_METRIC_UNAVAILABLE"
    DERIVED_VALUE_UNAVAILABLE = "DERIVED_VALUE_UNAVAILABLE"


@dataclass(frozen=True)
class ObservationContext:
    report_generated_on: date
    report_window_days: int
    snapshot_id: int
    snapshot_revision: int
    imported_at: datetime


@dataclass(frozen=True)
class BenchmarkRevisionContext:
    benchmark_set_id: int
    benchmark_set_revision_id: int
    benchmark_revision_number: int
    benchmark_member_count: int


@dataclass(frozen=True)
class BenchmarkSampleValue:
    product_id: int
    ozon_product_id: str
    title: str | None
    value: Decimal


@dataclass(frozen=True)
class CoreBenchmarkMetric:
    metric_id: CoreBenchmarkMetricId
    label: str
    unit: MetricUnit
    direction: MetricDirection
    is_estimate: bool
    readiness: MetricReadiness
    own_value: Decimal | None
    median: Decimal | None
    p25: Decimal | None
    p75: Decimal | None
    absolute_delta: Decimal | None
    sample_size: int
    sample_values: tuple[BenchmarkSampleValue, ...]
    comparison_position: ComparisonPosition
    confidence: BenchmarkConfidence
    exclusion_summary: Mapping[MetricExclusionReason, int]


@dataclass(frozen=True)
class CoreBenchmarkResult:
    product_id: int
    readiness: CoreBenchmarkReadiness
    benchmark: BenchmarkRevisionContext | None
    observation: ObservationContext | None
    metrics: tuple[CoreBenchmarkMetric, ...]
