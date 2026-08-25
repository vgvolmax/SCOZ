from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from collections.abc import Iterator
from typing import Generic, Mapping, Sequence, TypeVar

from backend.domain.core_benchmark import (
    BenchmarkConfidence, ComparisonPosition, CoreBenchmarkMetricId,
    MetricDirection, MetricExclusionReason, MetricUnit,
)
from backend.domain.product_snapshot import ProductSnapshot
from backend.domain.benchmark_selection import BenchmarkComposition
from backend.domain.core_benchmark import (
    BenchmarkRevisionContext, BenchmarkSampleValue, CoreBenchmarkMetric,
    CoreBenchmarkReadiness, CoreBenchmarkResult, MetricReadiness,
    ObservationContext,
)
from backend.domain.benchmark_selection import BenchmarkMember

K = TypeVar("K")
V = TypeVar("V")


class _FrozenMapping(Mapping[K, V], Generic[K, V]):
    def __init__(self, values: Mapping[K, V]) -> None:
        self._values = dict(values)

    def __getitem__(self, key: K) -> V:
        return self._values[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


@dataclass(frozen=True)
class _MetricDefinition:
    metric_id: CoreBenchmarkMetricId
    label: str
    unit: MetricUnit
    direction: MetricDirection
    is_estimate: bool = False


_METRIC_DEFINITIONS = (
    _MetricDefinition(CoreBenchmarkMetricId.ORDERED_AMOUNT_RUB, "Заказано на сумму", MetricUnit.RUB, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.ORDERED_UNITS, "Заказано, шт.", MetricUnit.UNITS, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.BUYOUT_SHARE_PCT, "Доля выкупа", MetricUnit.PERCENTAGE_POINTS, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.IMPRESSIONS_TOTAL, "Показы всего", MetricUnit.COUNT, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.SEARCH_CATALOG_VIEWS, "Просмотры в поиске и каталоге", MetricUnit.COUNT, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.CARD_VIEWS, "Просмотры карточки", MetricUnit.COUNT, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.IMPRESSION_TO_ORDER_PCT, "Конверсия из показа в заказ", MetricUnit.PERCENTAGE_POINTS, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.SEARCH_CATALOG_TO_CART_PCT, "В корзину из поиска и каталога", MetricUnit.PERCENTAGE_POINTS, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.CARD_TO_CART_PCT, "В корзину из карточки", MetricUnit.PERCENTAGE_POINTS, MetricDirection.HIGHER_IS_BETTER),
    _MetricDefinition(CoreBenchmarkMetricId.AVERAGE_PRICE_RUB, "Средняя цена", MetricUnit.RUB, MetricDirection.CONTEXTUAL),
    _MetricDefinition(CoreBenchmarkMetricId.TOTAL_DRR_PCT, "Общая ДРР", MetricUnit.PERCENTAGE_POINTS, MetricDirection.CONTEXTUAL),
    _MetricDefinition(CoreBenchmarkMetricId.ESTIMATED_AD_SPEND_RUB, "Оценка рекламных расходов", MetricUnit.RUB, MetricDirection.CONTEXTUAL, True),
    _MetricDefinition(CoreBenchmarkMetricId.ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB, "Рекламная поддержка на заказанную единицу", MetricUnit.RUB_PER_ORDERED_UNIT, MetricDirection.CONTEXTUAL, True),
)


def _extract_metric(snapshot: ProductSnapshot, metric_id: CoreBenchmarkMetricId) -> tuple[Decimal | None, MetricExclusionReason | None]:
    source_fields = {
        CoreBenchmarkMetricId.ORDERED_AMOUNT_RUB: "ordered_amount_rub",
        CoreBenchmarkMetricId.ORDERED_UNITS: "ordered_units",
        CoreBenchmarkMetricId.BUYOUT_SHARE_PCT: "buyout_share_pct",
        CoreBenchmarkMetricId.IMPRESSIONS_TOTAL: "impressions_total",
        CoreBenchmarkMetricId.SEARCH_CATALOG_VIEWS: "search_catalog_views",
        CoreBenchmarkMetricId.CARD_VIEWS: "card_views",
        CoreBenchmarkMetricId.IMPRESSION_TO_ORDER_PCT: "impression_to_order_pct",
        CoreBenchmarkMetricId.SEARCH_CATALOG_TO_CART_PCT: "search_catalog_to_cart_pct",
        CoreBenchmarkMetricId.CARD_TO_CART_PCT: "card_to_cart_pct",
        CoreBenchmarkMetricId.AVERAGE_PRICE_RUB: "average_price_rub",
        CoreBenchmarkMetricId.TOTAL_DRR_PCT: "total_drr_pct",
    }
    if metric_id in source_fields:
        value = getattr(snapshot, source_fields[metric_id])
        if value is None:
            return None, MetricExclusionReason.SOURCE_METRIC_UNAVAILABLE
        return Decimal(value), None
    spend = snapshot.ordered_amount_rub * snapshot.total_drr_pct / Decimal(100)
    if metric_id is CoreBenchmarkMetricId.ESTIMATED_AD_SPEND_RUB:
        return spend, None
    if metric_id is CoreBenchmarkMetricId.ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB:
        if snapshot.ordered_units == 0:
            return None, MetricExclusionReason.DERIVED_VALUE_UNAVAILABLE
        return spend / Decimal(snapshot.ordered_units), None
    raise ValueError(f"unknown core benchmark metric: {metric_id}")


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _type7_quantile(values: Sequence[Decimal], p: Decimal) -> Decimal:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(values)
    h = Decimal(len(ordered) - 1) * p
    j = int(h.to_integral_value(rounding=ROUND_FLOOR))
    g = h - Decimal(j)
    return ordered[j] if j == len(ordered) - 1 else ordered[j] + g * (ordered[j + 1] - ordered[j])


def _confidence(sample_size: int) -> BenchmarkConfidence:
    if sample_size < 3:
        return BenchmarkConfidence.INSUFFICIENT
    if sample_size < 5:
        return BenchmarkConfidence.LOW
    if sample_size < 10:
        return BenchmarkConfidence.MEDIUM
    return BenchmarkConfidence.HIGH


def _comparison(own_value: Decimal | None, median: Decimal | None, sample_size: int) -> tuple[Decimal | None, ComparisonPosition]:
    if own_value is None or median is None or sample_size < 3:
        return None, ComparisonPosition.UNAVAILABLE
    position = (ComparisonPosition.BELOW_MEDIAN if own_value < median else
                ComparisonPosition.ABOVE_MEDIAN if own_value > median else
                ComparisonPosition.AT_MEDIAN)
    return own_value - median, position


def _build_metric_result(definition: _MetricDefinition, own_snapshot: ProductSnapshot,
                         members: tuple[BenchmarkMember, ...],
                         competitor_snapshots: Mapping[int, ProductSnapshot]) -> CoreBenchmarkMetric:
    summary = {reason: 0 for reason in MetricExclusionReason}
    sample_values: list[BenchmarkSampleValue] = []
    for member in members:
        snapshot = competitor_snapshots.get(member.product_id)
        if snapshot is None:
            summary[MetricExclusionReason.NO_COMPATIBLE_OBSERVATION] += 1
            continue
        value, reason = _extract_metric(snapshot, definition.metric_id)
        if reason is not None:
            summary[reason] += 1
            continue
        assert value is not None
        sample_values.append(BenchmarkSampleValue(member.product_id, member.ozon_product_id, snapshot.title, value))
    sample = tuple(sample_values)
    values = tuple(item.value for item in sample)
    own_value, _ = _extract_metric(own_snapshot, definition.metric_id)
    median = _median(values)
    size = len(sample)
    delta, position = _comparison(own_value, median, size)
    readiness = (MetricReadiness.OWN_VALUE_UNAVAILABLE if own_value is None else
                 MetricReadiness.READY if size >= 3 else MetricReadiness.INSUFFICIENT_SAMPLE)
    result = CoreBenchmarkMetric(
        definition.metric_id, definition.label, definition.unit,
        definition.direction, definition.is_estimate, readiness, own_value,
        median,
        _type7_quantile(values, Decimal("0.25")) if size >= 4 else None,
        _type7_quantile(values, Decimal("0.75")) if size >= 4 else None,
        delta, size, sample, position, _confidence(size), _FrozenMapping(summary),
    )
    if result.sample_size != len(result.sample_values):
        raise AssertionError("sample_size must equal the exposed statistical sample")
    if result.sample_size + sum(result.exclusion_summary.values()) != len(members):
        raise AssertionError("sample and exclusions must account for every benchmark member")
    return result


def calculate_core_benchmark(*, product_id: int, composition: BenchmarkComposition,
                             own_snapshot: ProductSnapshot,
                             competitor_snapshots: Mapping[int, ProductSnapshot]) -> CoreBenchmarkResult:
    """Calculate PR7 metrics from already-resolved current domain observations."""
    revision = composition.current_revision
    benchmark_set = composition.benchmark_set
    assert revision is not None and benchmark_set is not None
    metrics = tuple(_build_metric_result(item, own_snapshot, revision.members, competitor_snapshots)
                    for item in _METRIC_DEFINITIONS)
    if all(metric.sample_size == 0 for metric in metrics):
        readiness = CoreBenchmarkReadiness.NO_COMPATIBLE_SAMPLE
    elif any(metric.readiness is MetricReadiness.READY for metric in metrics):
        readiness = CoreBenchmarkReadiness.READY
    else:
        readiness = CoreBenchmarkReadiness.INSUFFICIENT_SAMPLE
    return CoreBenchmarkResult(
        product_id=product_id,
        readiness=readiness,
        benchmark=BenchmarkRevisionContext(benchmark_set.id, revision.id, revision.revision, len(revision.members)),
        observation=ObservationContext(
            own_snapshot.report_generated_on, own_snapshot.report_window_days,
            own_snapshot.id, own_snapshot.revision, own_snapshot.imported_at,
        ),
        metrics=metrics,
    )
