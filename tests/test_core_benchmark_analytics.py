from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.domain.core_benchmark import (
    CORE_BENCHMARK_METRIC_ORDER, BenchmarkConfidence, BenchmarkRevisionContext,
    BenchmarkSampleValue, ComparisonPosition, CoreBenchmarkMetricId,
    CoreBenchmarkReadiness, MetricDirection, MetricExclusionReason,
    MetricReadiness, MetricUnit, ObservationContext,
)
from backend.analytics.core_benchmark import (
    _METRIC_DEFINITIONS, _build_metric_result, _comparison, _confidence, _extract_metric, _median,
    _type7_quantile,
)
from backend.domain.benchmark_selection import BenchmarkComposition, BenchmarkMember, BenchmarkSet, BenchmarkSetRevision
from backend.analytics.core_benchmark import calculate_core_benchmark


def test_metric_catalog_contains_exact_thirteen_ids_in_frozen_order():
    assert tuple(item.value for item in CORE_BENCHMARK_METRIC_ORDER) == (
        "ordered_amount_rub", "ordered_units", "buyout_share_pct",
        "impressions_total", "search_catalog_views", "card_views",
        "impression_to_order_pct", "search_catalog_to_cart_pct",
        "card_to_cart_pct", "average_price_rub", "total_drr_pct",
        "estimated_ad_spend_rub", "advertising_support_per_ordered_unit_rub",
    )


def test_metric_unit_and_direction_members_are_exact():
    assert {x.value for x in MetricUnit} == {"RUB", "UNITS", "COUNT", "PERCENTAGE_POINTS", "RUB_PER_ORDERED_UNIT"}
    assert {x.value for x in MetricDirection} == {"HIGHER_IS_BETTER", "CONTEXTUAL"}


def test_readiness_confidence_position_and_exclusion_members_are_exact():
    assert {x.value for x in ComparisonPosition} == {"UNAVAILABLE", "BELOW_MEDIAN", "AT_MEDIAN", "ABOVE_MEDIAN"}
    assert {x.value for x in BenchmarkConfidence} == {"INSUFFICIENT", "LOW", "MEDIUM", "HIGH"}
    assert {x.value for x in CoreBenchmarkReadiness} == {"NO_BENCHMARK", "NO_OWN_SOURCE_DATA", "NO_COMPATIBLE_SAMPLE", "INSUFFICIENT_SAMPLE", "READY"}
    assert {x.value for x in MetricReadiness} == {"READY", "INSUFFICIENT_SAMPLE", "OWN_VALUE_UNAVAILABLE"}
    assert {x.value for x in MetricExclusionReason} == {"NO_COMPATIBLE_OBSERVATION", "SOURCE_METRIC_UNAVAILABLE", "DERIVED_VALUE_UNAVAILABLE"}


def test_core_benchmark_dtos_are_frozen():
    item = BenchmarkSampleValue(1, "2", None, Decimal("3"))
    with pytest.raises(FrozenInstanceError): item.value = Decimal("4")
    observation = ObservationContext(date.today(), 7, 1, 1, datetime.now(timezone.utc))
    with pytest.raises(FrozenInstanceError): observation.snapshot_id = 2
    revision = BenchmarkRevisionContext(1, 2, 3, 4)
    with pytest.raises(FrozenInstanceError): revision.benchmark_member_count = 5


def test_median_even_sample_uses_decimal_average():
    assert _median([Decimal("1"), Decimal("4")]) == Decimal("2.5")


def test_median_keeps_equal_member_observations():
    assert _median([Decimal("1"), Decimal("2"), Decimal("2"), Decimal("9")]) == Decimal("2")


def test_type7_quartiles_interpolate_exactly_for_four_values():
    values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("8")]
    assert _type7_quantile(values, Decimal("0.25")) == Decimal("1.75")
    assert _type7_quantile(values, Decimal("0.75")) == Decimal("4.25")


def test_quartiles_are_withheld_below_four():
    assert _median([]) is None


@pytest.mark.parametrize("size, expected", [(0,"INSUFFICIENT"),(2,"INSUFFICIENT"),(3,"LOW"),(4,"LOW"),(5,"MEDIUM"),(9,"MEDIUM"),(10,"HIGH")])
def test_confidence_boundaries_are_0_2_3_4_5_9_10(size, expected):
    assert _confidence(size).value == expected


@pytest.mark.parametrize("own, expected", [(Decimal("1"),"BELOW_MEDIAN"),(Decimal("2"),"AT_MEDIAN"),(Decimal("3"),"ABOVE_MEDIAN")])
def test_comparison_boundaries_are_exact_below_equal_above(own, expected):
    delta, position = _comparison(own, Decimal("2"), 3)
    assert delta == own - Decimal("2") and position.value == expected


def test_comparison_is_unavailable_below_three():
    assert _comparison(Decimal("1"), Decimal("1"), 2) == (None, ComparisonPosition.UNAVAILABLE)


def test_zero_median_supports_absolute_delta():
    assert _comparison(Decimal("2"), Decimal("0"), 3) == (Decimal("2"), ComparisonPosition.ABOVE_MEDIAN)


class _Snapshot:
    title = "Title"
    ordered_amount_rub = Decimal("1000")
    ordered_units = 4
    buyout_share_pct = Decimal("92.25")
    impressions_total = 101
    search_catalog_views = 51
    card_views = 31
    impression_to_order_pct = Decimal("1.2345")
    search_catalog_to_cart_pct = Decimal("2.3")
    card_to_cart_pct = Decimal("3.4")
    average_price_rub = Decimal("250")
    total_drr_pct = Decimal("7.7")


def test_catalog_metadata_matches_exact_thirteen_metric_contract():
    assert tuple(x.metric_id for x in _METRIC_DEFINITIONS) == CORE_BENCHMARK_METRIC_ORDER
    assert len(_METRIC_DEFINITIONS) == 13


def test_source_metrics_extract_as_decimal_without_rounding():
    assert _extract_metric(_Snapshot(), CoreBenchmarkMetricId.IMPRESSION_TO_ORDER_PCT) == (Decimal("1.2345"), None)
    assert _extract_metric(_Snapshot(), CoreBenchmarkMetricId.IMPRESSIONS_TOTAL) == (Decimal(101), None)


def test_nullable_buyout_is_source_metric_unavailable():
    snapshot = _Snapshot(); snapshot.buyout_share_pct = None
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.BUYOUT_SHARE_PCT) == (None, MetricExclusionReason.SOURCE_METRIC_UNAVAILABLE)


def test_estimated_ad_spend_divides_drr_by_one_hundred_once():
    assert _extract_metric(_Snapshot(), CoreBenchmarkMetricId.ESTIMATED_AD_SPEND_RUB) == (Decimal("77"), None)


def test_advertising_support_uses_ordered_units():
    assert _extract_metric(_Snapshot(), CoreBenchmarkMetricId.ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB) == (Decimal("19.25"), None)


def test_zero_units_only_make_support_derived_value_unavailable():
    snapshot = _Snapshot(); snapshot.ordered_units = 0
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.ESTIMATED_AD_SPEND_RUB) == (Decimal("77"), None)
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB) == (None, MetricExclusionReason.DERIVED_VALUE_UNAVAILABLE)


def test_zero_drr_with_positive_units_derives_zeroes():
    snapshot = _Snapshot(); snapshot.total_drr_pct = Decimal(0)
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.ESTIMATED_AD_SPEND_RUB)[0] == 0
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB)[0] == 0


def test_advertising_metrics_are_contextual_estimates_as_specified():
    advertising = _METRIC_DEFINITIONS[-3:]
    assert all(x.direction is MetricDirection.CONTEXTUAL for x in advertising)
    assert [x.is_estimate for x in advertising] == [False, True, True]


def test_sample_values_contains_exactly_metric_participants():
    members = (BenchmarkMember(1, 2, "20"), BenchmarkMember(1, 3, "30"))
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _Snapshot(), members, {2: _Snapshot()})
    assert [(x.product_id, x.ozon_product_id, x.title, x.value) for x in metric.sample_values] == [(2, "20", "Title", Decimal("1000"))]
    assert metric.sample_size == len(metric.sample_values) == 1
    assert metric.sample_size + sum(metric.exclusion_summary.values()) == len(members)


def test_nullable_metric_excludes_member_only_from_that_metric_sample():
    missing = _Snapshot(); missing.buyout_share_pct = None
    member = BenchmarkMember(1, 2, "20")
    buyout = _build_metric_result(_METRIC_DEFINITIONS[2], _Snapshot(), (member,), {2: missing})
    amount = _build_metric_result(_METRIC_DEFINITIONS[0], _Snapshot(), (member,), {2: missing})
    assert buyout.sample_size == 0 and amount.sample_size == 1
    assert buyout.exclusion_summary[MetricExclusionReason.SOURCE_METRIC_UNAVAILABLE] == 1


def test_zero_ordered_units_keeps_spend_but_excludes_support():
    zero = _Snapshot(); zero.ordered_units = 0
    member = BenchmarkMember(1, 2, "20")
    spend = _build_metric_result(_METRIC_DEFINITIONS[-2], _Snapshot(), (member,), {2: zero})
    support = _build_metric_result(_METRIC_DEFINITIONS[-1], _Snapshot(), (member,), {2: zero})
    assert spend.sample_size == 1 and support.sample_size == 0
    assert support.exclusion_summary[MetricExclusionReason.DERIVED_VALUE_UNAVAILABLE] == 1


def test_exclusion_summary_always_has_exact_three_keys():
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _Snapshot(), (), {})
    assert tuple(metric.exclusion_summary) == tuple(MetricExclusionReason)
    with pytest.raises(TypeError):
        metric.exclusion_summary[MetricExclusionReason.NO_COMPATIBLE_OBSERVATION] = 1


def _calculation_snapshot(**changes):
    from types import SimpleNamespace
    values = {name: getattr(_Snapshot(), name) for name in (
        "title", "ordered_amount_rub", "ordered_units", "buyout_share_pct",
        "impressions_total", "search_catalog_views", "card_views",
        "impression_to_order_pct", "search_catalog_to_cart_pct",
        "card_to_cart_pct", "average_price_rub", "total_drr_pct",
    )}
    values.update(id=1, revision=2, report_generated_on=date(2026, 8, 23),
                  report_window_days=7, imported_at=datetime(2026, 8, 24, tzinfo=timezone.utc))
    values.update(changes)
    return SimpleNamespace(**values)


def test_full_result_contains_all_thirteen_metrics_in_catalog_order():
    members = tuple(BenchmarkMember(2, index, str(index)) for index in range(10, 13))
    composition = BenchmarkComposition(
        BenchmarkSet(1, 9, datetime.now(timezone.utc)),
        BenchmarkSetRevision(2, 1, 1, datetime.now(timezone.utc), members),
    )
    result = calculate_core_benchmark(product_id=9, composition=composition,
        own_snapshot=_calculation_snapshot(),
        competitor_snapshots={member.product_id: _calculation_snapshot(id=member.product_id) for member in members})
    assert result.readiness is CoreBenchmarkReadiness.READY
    assert tuple(metric.metric_id for metric in result.metrics) == CORE_BENCHMARK_METRIC_ORDER
    assert all(metric.readiness is MetricReadiness.READY for metric in result.metrics)
    assert all(metric.comparison_position is ComparisonPosition.AT_MEDIAN for metric in result.metrics)


def test_metric_readiness_and_top_level_readiness_follow_exact_matrix():
    composition = BenchmarkComposition(
        BenchmarkSet(1, 9, datetime.now(timezone.utc)),
        BenchmarkSetRevision(2, 1, 1, datetime.now(timezone.utc), (BenchmarkMember(2, 10, "10"),)),
    )
    result = calculate_core_benchmark(product_id=9, composition=composition,
        own_snapshot=_calculation_snapshot(), competitor_snapshots={10: _calculation_snapshot(id=10)})
    assert result.readiness is CoreBenchmarkReadiness.INSUFFICIENT_SAMPLE
    assert all(metric.readiness is MetricReadiness.INSUFFICIENT_SAMPLE for metric in result.metrics)


def test_sample_values_preserve_benchmark_member_order():
    members = (BenchmarkMember(2, 20, "20"), BenchmarkMember(2, 10, "10"))
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), members,
                                  {10: _calculation_snapshot(id=10), 20: _calculation_snapshot(id=20)})
    assert [item.product_id for item in metric.sample_values] == [20, 10]


def test_quartiles_are_withheld_below_four_in_metric_result():
    members = tuple(BenchmarkMember(2, i, str(i)) for i in range(1, 4))
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), members,
                                  {i: _calculation_snapshot(id=i, ordered_amount_rub=Decimal(i)) for i in range(1, 4)})
    assert metric.median == Decimal("2") and metric.p25 is None and metric.p75 is None


def test_quartiles_appear_at_four_without_rounding():
    members = tuple(BenchmarkMember(2, i, str(i)) for i in range(1, 5))
    values = ("1", "2", "3", "8")
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), members,
        {i: _calculation_snapshot(id=i, ordered_amount_rub=Decimal(value)) for i, value in zip(range(1, 5), values)})
    assert (metric.p25, metric.p75) == (Decimal("1.75"), Decimal("4.25"))


def test_missing_compatible_observation_excludes_member_from_sample_values():
    member = BenchmarkMember(2, 10, "10")
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), (member,), {})
    assert metric.sample_values == ()
    assert metric.exclusion_summary[MetricExclusionReason.NO_COMPATIBLE_OBSERVATION] == 1


def test_zero_source_value_enters_sample():
    member = BenchmarkMember(2, 10, "10")
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), (member,),
                                  {10: _calculation_snapshot(ordered_amount_rub=Decimal(0))})
    assert metric.sample_values[0].value == 0 and metric.sample_size == 1


def test_statistics_use_exact_sample_values():
    members = tuple(BenchmarkMember(2, i, str(i)) for i in range(1, 5))
    snapshots = {i: _calculation_snapshot(ordered_amount_rub=Decimal(value))
                 for i, value in enumerate(("1.1", "2.2", "3.3", "9.9"), 1)}
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), members, snapshots)
    values = tuple(item.value for item in metric.sample_values)
    assert metric.sample_size == len(values)
    assert metric.median == _median(values)
    assert metric.p25 == _type7_quantile(values, Decimal("0.25"))
    assert metric.p75 == _type7_quantile(values, Decimal("0.75"))


def test_own_unavailable_with_competitor_values_withholds_comparison():
    own = _calculation_snapshot(buyout_share_pct=None)
    members = tuple(BenchmarkMember(2, i, str(i)) for i in range(1, 4))
    metric = _build_metric_result(_METRIC_DEFINITIONS[2], own, members,
                                  {i: _calculation_snapshot(id=i) for i in range(1, 4)})
    assert metric.readiness is MetricReadiness.OWN_VALUE_UNAVAILABLE
    assert metric.absolute_delta is None and metric.comparison_position is ComparisonPosition.UNAVAILABLE
    assert metric.sample_size == 3


def test_no_compatible_sample_top_readiness():
    composition = BenchmarkComposition(BenchmarkSet(1, 9, datetime.now(timezone.utc)),
        BenchmarkSetRevision(2, 1, 1, datetime.now(timezone.utc), (BenchmarkMember(2, 10, "10"),)))
    result = calculate_core_benchmark(product_id=9, composition=composition,
                                      own_snapshot=_calculation_snapshot(), competitor_snapshots={})
    assert result.readiness is CoreBenchmarkReadiness.NO_COMPATIBLE_SAMPLE
    assert all(metric.sample_size == 0 for metric in result.metrics)


def test_repeated_calculation_does_not_modify_snapshots_or_composition():
    member = BenchmarkMember(2, 10, "10")
    composition = BenchmarkComposition(BenchmarkSet(1, 9, datetime.now(timezone.utc)),
        BenchmarkSetRevision(2, 1, 1, datetime.now(timezone.utc), (member,)))
    own = _calculation_snapshot(); competitor = _calculation_snapshot(id=10)
    before = (dict(vars(own)), dict(vars(competitor)), composition)
    first = calculate_core_benchmark(product_id=9, composition=composition, own_snapshot=own, competitor_snapshots={10: competitor})
    second = calculate_core_benchmark(product_id=9, composition=composition, own_snapshot=own, competitor_snapshots={10: competitor})
    assert first == second and before == (dict(vars(own)), dict(vars(competitor)), composition)


def test_current_composition_revision_changes_next_result():
    first_member = BenchmarkMember(2, 10, "10")
    second_member = BenchmarkMember(3, 20, "20")
    benchmark = BenchmarkSet(1, 9, datetime.now(timezone.utc))
    first = BenchmarkComposition(benchmark, BenchmarkSetRevision(2, 1, 1, datetime.now(timezone.utc), (first_member,)))
    second = BenchmarkComposition(benchmark, BenchmarkSetRevision(3, 1, 2, datetime.now(timezone.utc), (second_member,)))
    first_result = calculate_core_benchmark(product_id=9, composition=first, own_snapshot=_calculation_snapshot(), competitor_snapshots={10: _calculation_snapshot(id=10)})
    second_result = calculate_core_benchmark(product_id=9, composition=second, own_snapshot=_calculation_snapshot(), competitor_snapshots={20: _calculation_snapshot(id=20)})
    assert first_result.benchmark.benchmark_set_revision_id == 2
    assert second_result.benchmark.benchmark_set_revision_id == 3
    assert first_result.metrics[0].sample_values[0].product_id == 10
    assert second_result.metrics[0].sample_values[0].product_id == 20


def test_superseded_snapshots_never_duplicate_sample_values():
    member = BenchmarkMember(2, 10, "10")
    current = _calculation_snapshot(id=102, revision=2, ordered_amount_rub=Decimal("22"))
    metric = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), (member,), {10: current})
    assert metric.sample_size == 1
    assert tuple(item.value for item in metric.sample_values) == (Decimal("22"),)


def test_presentation_metadata_change_does_not_change_member_identity_or_result_membership():
    member = BenchmarkMember(2, 10, "987654")
    first = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), (member,), {10: _calculation_snapshot(title="Old")})
    second = _build_metric_result(_METRIC_DEFINITIONS[0], _calculation_snapshot(), (member,), {10: _calculation_snapshot(title="New")})
    assert (first.sample_values[0].product_id, first.sample_values[0].ozon_product_id) == (10, "987654")
    assert (second.sample_values[0].product_id, second.sample_values[0].ozon_product_id) == (10, "987654")
    assert first.sample_size == second.sample_size == 1


def test_candidate_search_visibility_and_mpstats_types_are_absent_from_analytics_dependencies():
    import inspect
    import backend.analytics.core_benchmark as module
    source = inspect.getsource(module).lower()
    assert "benchmarkcandidate" not in source
    assert "searchvisibility" not in source
    assert "mpstats" not in source
    assert "sqlite3" not in source and "fastapi" not in source
