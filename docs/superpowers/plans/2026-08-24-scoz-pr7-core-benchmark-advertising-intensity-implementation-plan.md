# SCOZ PR7 Core Benchmark & Advertising Intensity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PR7 Core Benchmark so an owned SKU can be compared transparently with its saved competitors across Result, Traffic, Conversion, Offer, and Advertising metrics.

**Architecture:** Read the owned product, current PR6 benchmark composition, one deterministic current own `ProductSnapshot` anchor, and current competitor snapshots at that exact date/window inside one read transaction. `CoreBenchmarkService` passes only resolved current domain objects to a feature-specific pure Decimal analytics module. A thin same-origin FastAPI GET serializes the frozen DTO, and the existing competitor workspace renders a grouped scan-first summary with expandable Benchmark Detail containing aggregate statistics, actual participating competitor values, and aggregate exclusions. The calculation is derived on request and is never persisted.

**Tech Stack:** Python 3.13, frozen dataclasses/enums, `Decimal`, SQLite repositories and transactions, FastAPI/Pydantic, committed framework-free HTML/CSS/JavaScript, pytest, Node syntax/contract checks, PowerShell portable smoke.

**Spec:** `docs/superpowers/specs/2026-08-24-scoz-pr7-core-benchmark-advertising-intensity-implementation-spec.md`

**Plan base:** `PR7_PLAN_BASE_SHA=9cf7da8f73a24a4cd31b467d8c8b1765f6390891`

## Global Constraints

The following constraints are copied from the approved spec and control every task:

- PR7 answers **“How does this SKU compare with the selected benchmark on compatible facts?”** It does not answer why the SKU performs that way or what the user should do.
- The result is calculated on request. It is neither persisted nor treated as source history.
- The sole numerical source is the current revision of `ProductSnapshot`, imported under Ozon Products Source Contract v1.
- One Core Benchmark response MUST use exactly one common own `ProductSnapshot` observation context for all 13 PR7 product-level source and derived metrics.
- Compatibility is a hard equality gate: equal `report_generated_on`, equal `report_window_days`, and ProductSnapshot product-level observations from Ozon Products v1.
- Missing values are unavailable and never zero. Equal values from distinct members remain separate sample observations. Own never enters the competitor sample.
- All calculation uses Python `Decimal`; binary float and intermediate quantization are prohibited.
- Only the current `BenchmarkSetRevision` is calculated. Availability filtering never changes or creates benchmark composition.
- Candidate/Search Visibility values, MPStats previews or estimates, and transient frontend state never enter Core Benchmark values or provide fallbacks.
- `Product.id` remains canonical internal identity; canonical Ozon `ProductExternalIdentity` remains authoritative external identity; presentation metadata never establishes identity.
- `BenchmarkSelectionService` remains PR6 composition orchestration. `CoreBenchmarkService` owns PR7 read orchestration.
- SQL remains in repositories, business logic remains outside routes and UI, and pure analytics has no FastAPI/SQLite/files/MPStats dependency.
- No migration, schema change, dependency, source adapter, result cache/history, generic analytics engine, `BenchmarkSnapshot`, or `AdvertisingSnapshot` is introduced.
- No PR8 diagnostics, causes, recommendations, verdicts, automatic competitor scoring/filtering/replacement, or favorable/unfavorable advertising semantics are introduced.
- The endpoint remains same-origin, read-only, and loopback-only under the existing trusted-local security profile.

### Frozen cross-task names

The implementation must use these names consistently:

```text
Domain: ObservationContext, BenchmarkRevisionContext, BenchmarkSampleValue, CoreBenchmarkMetric,
        CoreBenchmarkResult, CoreBenchmarkMetricId, MetricUnit,
        MetricDirection, ComparisonPosition, BenchmarkConfidence,
        CoreBenchmarkReadiness, MetricReadiness, MetricExclusionReason
Repository: ProductSnapshotRepository.find_latest_current_for_product
            ProductSnapshotRepository.list_current_for_products_at_context
Analytics: calculate_core_benchmark
Application: CoreBenchmarkService.get_core_benchmark
HTTP: GET /api/products/{product_id}/core-benchmark
Frontend: resetCoreBenchmarkState, openCoreBenchmark, loadCoreBenchmark,
          renderCoreBenchmark, renderCoreBenchmarkMetric,
          toggleCoreBenchmarkMetricDetail, formatBenchmarkValue,
          coreBenchmarkObservationPhrase
```

The API returns participating competitor values through each metric's `sample_values`; it does **not** return per-member exclusion records or exclusion history. “Benchmark Detail” means the approved metric disclosure: own, median, P25/P75, delta, N, confidence, actual participating competitor values, period/freshness, and the aggregate three-reason exclusion summary. Collapsed metric summaries remain compact, and the existing selected-competitor list is not used to reconstruct metric values.

## Actual `main` File Map and Existing Coverage

- `backend/domain/product_snapshot.py` defines immutable `ProductSnapshot` and canonical decimal text serialization.
- `backend/persistence/repositories/product_snapshots.py` owns current-revision SQL and already exposes `find_current(...)`; PR7 adds only the two approved reads.
- `backend/domain/benchmark_selection.py`, `backend/persistence/repositories/benchmark_selection.py`, and `backend/application/benchmark_selection.py` define/read/orchestrate the PR6 current composition and existing ownership errors.
- `backend/main.py` has `_json(...)`, `PR6_ERRORS`, `_pr6_error_response(...)`, and thin product routes; PR7 reuses their serialization/error style.
- `frontend/index.html` contains `#competitors-workspace`, `#benchmark-selected-panel`, and the saved composition UI. `frontend/assets/js/app.js` owns workspace loading and saving; `competitor_state.js` stays unchanged.
- `frontend/assets/css/app.css` contains the canonical tokens, cards, `.benchmark-layout`, status, disclosure, and responsive patterns.
- `tests/test_product_snapshot_repository.py`, `tests/test_benchmark_selection_repository.py`, and PR6 API tests already protect generic revisions, identity, and composition persistence; PR7 adds only feature-risk regressions.
- `tests/test_frontend_contract.py` and `tests/competitor_state_contract.mjs` protect committed UI contracts and PR6 race-safe composition state.
- `.github/workflows/ci.yml` runs pytest and Node checks on Windows; `tests/windows_smoke.ps1` is the actual portable smoke path (there is no `scripts/windows_smoke_test.ps1`).

---

### Task 1: Freeze Core Benchmark domain contracts and catalog order

**Files:**
- Create: `backend/domain/core_benchmark.py`
- Create: `tests/test_core_benchmark_analytics.py`

**Interfaces:**
- Consumes:
  - `datetime.date`, `datetime.datetime`, `decimal.Decimal`, immutable tuples/mappings.
- Produces:
  - the enums and frozen DTOs listed in “Frozen cross-task names” with the exact fields from spec section 21;
  - frozen `BenchmarkSampleValue(product_id, ozon_product_id, title, value)` and `CoreBenchmarkMetric.sample_values: tuple[BenchmarkSampleValue, ...]`;
  - `CORE_BENCHMARK_METRIC_ORDER: tuple[CoreBenchmarkMetricId, ...]` containing exactly 13 IDs in catalog order.

- [ ] Write the domain-contract section of `tests/test_core_benchmark_analytics.py` first. Include `test_metric_catalog_contains_exact_thirteen_ids_in_frozen_order`, `test_metric_unit_and_direction_members_are_exact`, `test_readiness_confidence_position_and_exclusion_members_are_exact`, and `test_core_benchmark_dtos_are_frozen`.

```python
def test_metric_catalog_contains_exact_thirteen_ids_in_frozen_order():
    assert tuple(item.value for item in CORE_BENCHMARK_METRIC_ORDER) == (
        "ordered_amount_rub", "ordered_units", "buyout_share_pct",
        "impressions_total", "search_catalog_views", "card_views",
        "impression_to_order_pct", "search_catalog_to_cart_pct",
        "card_to_cart_pct", "average_price_rub", "total_drr_pct",
        "estimated_ad_spend_rub",
        "advertising_support_per_ordered_unit_rub",
    )
```

Run from repository root:

```bash
python -m pytest tests/test_core_benchmark_analytics.py -q
```

Expected: FAIL during collection because `backend.domain.core_benchmark` does not exist.

- [ ] Add the exact enums and definitions. Use string enums and frozen dataclasses; copy all spec fields without presentation-only or diagnostic fields.

```python
class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    CONTEXTUAL = "CONTEXTUAL"

class ComparisonPosition(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    BELOW_MEDIAN = "BELOW_MEDIAN"
    AT_MEDIAN = "AT_MEDIAN"
    ABOVE_MEDIAN = "ABOVE_MEDIAN"

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
```

- [ ] Run the targeted test again; expect PASS. Then run `python -m pytest tests/test_observation_revision_convention.py tests/test_benchmark_selection_repository.py -q`; expect PASS.
- [ ] Commit: `git add backend/domain/core_benchmark.py tests/test_core_benchmark_analytics.py && git commit -m "feat(PR7): add core benchmark domain contracts"`.

---

### Task 2: Implement the pure Decimal statistical primitives

**Files:**
- Create: `backend/analytics/__init__.py`
- Create: `backend/analytics/core_benchmark.py`
- Modify: `tests/test_core_benchmark_analytics.py: Decimal statistics tests`

**Interfaces:**
- Consumes:
  - `Sequence[Decimal]`, own `Decimal | None`, competitor `sample_size: int`.
- Produces:
  - private pure helpers `_median(values: Sequence[Decimal]) -> Decimal | None`, `_type7_quantile(values: Sequence[Decimal], p: Decimal) -> Decimal`, `_confidence(sample_size: int) -> BenchmarkConfidence`, and `_comparison(own_value: Decimal | None, median: Decimal | None, sample_size: int) -> tuple[Decimal | None, ComparisonPosition]`.

- [ ] Write boundary tests before implementation: `test_median_even_sample_uses_decimal_average`, `test_median_keeps_equal_member_observations`, `test_type7_quartiles_interpolate_exactly_for_four_values`, `test_quartiles_are_withheld_below_four`, `test_confidence_boundaries_are_0_2_3_4_5_9_10`, `test_comparison_boundaries_are_exact_below_equal_above`, `test_comparison_is_unavailable_below_three`, and `test_zero_median_supports_absolute_delta`.

```python
def test_type7_quartiles_interpolate_exactly_for_four_values():
    values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("8")]
    assert _type7_quantile(values, Decimal("0.25")) == Decimal("1.75")
    assert _type7_quantile(values, Decimal("0.75")) == Decimal("4.25")
```

Run from repository root:

```bash
python -m pytest tests/test_core_benchmark_analytics.py -q
```

Expected: FAIL because the analytics helpers are absent.

- [ ] Implement numeric sorting, Decimal median, and Type-7 interpolation exactly. Do not round intermediates.

```python
def _type7_quantile(values: Sequence[Decimal], p: Decimal) -> Decimal:
    ordered = sorted(values)
    h = Decimal(len(ordered) - 1) * p
    j = int(h.to_integral_value(rounding=ROUND_FLOOR))
    g = h - Decimal(j)
    return ordered[j] if j == len(ordered) - 1 else ordered[j] + g * (ordered[j + 1] - ordered[j])
```

- [ ] Implement thresholds: N 0–2 `INSUFFICIENT`, 3–4 `LOW`, 5–9 `MEDIUM`, 10+ `HIGH`; comparison/delta only when own exists and N >= 3. Assert the exact comparison mapping `<` → `BELOW_MEDIAN`, `==` → `AT_MEDIAN`, and `>` → `ABOVE_MEDIAN`; otherwise assert `UNAVAILABLE`. Position is a factual Decimal comparison and is never direction-inverted. P25/P75 are descriptive distribution context only and do not affect `ComparisonPosition`.
- [ ] Run targeted tests; expect PASS. Run `python -m pytest tests/test_product_snapshot_repository.py -q`; expect PASS.
- [ ] Commit: `git add backend/analytics backend/domain/core_benchmark.py tests/test_core_benchmark_analytics.py && git commit -m "feat(PR7): add decimal benchmark statistics"`.

---

### Task 3: Extract the frozen 13 metrics and advertising derivatives

**Files:**
- Modify: `backend/analytics/core_benchmark.py: feature catalog and snapshot extraction helpers`
- Modify: `tests/test_core_benchmark_analytics.py: catalog, extraction, advertising, and unavailable-value tests`

**Interfaces:**
- Consumes:
  - `ProductSnapshot` only for numerical values.
- Produces:
  - private immutable `_MetricDefinition` catalog entries;
  - `_extract_metric(snapshot: ProductSnapshot, metric_id: CoreBenchmarkMetricId) -> tuple[Decimal | None, MetricExclusionReason | None]`.

- [ ] Add failing tests: `test_catalog_metadata_matches_exact_thirteen_metric_contract`, `test_source_metrics_extract_as_decimal_without_rounding`, `test_nullable_buyout_is_source_metric_unavailable`, `test_estimated_ad_spend_divides_drr_by_one_hundred_once`, `test_advertising_support_uses_ordered_units`, `test_zero_units_only_make_support_derived_value_unavailable`, `test_zero_drr_with_positive_units_derives_zeroes`, and `test_advertising_metrics_are_contextual_estimates_as_specified`.

```python
def test_zero_units_only_make_support_derived_value_unavailable(snapshot_factory):
    snapshot = snapshot_factory(ordered_units=0, ordered_amount_rub=Decimal("1000"), total_drr_pct=Decimal("7.7"))
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.ESTIMATED_AD_SPEND_RUB) == (Decimal("77"), None)
    assert _extract_metric(snapshot, CoreBenchmarkMetricId.ADVERTISING_SUPPORT_PER_ORDERED_UNIT_RUB) == (
        None, MetricExclusionReason.DERIVED_VALUE_UNAVAILABLE
    )
```

Run from repository root:

```bash
python -m pytest tests/test_core_benchmark_analytics.py -q
```

Expected: FAIL on absent catalog/extraction behavior.

- [ ] Implement the exact source-field mapping and formulas:

```python
spend = snapshot.ordered_amount_rub * snapshot.total_drr_pct / Decimal(100)
support = None if snapshot.ordered_units == 0 else spend / Decimal(snapshot.ordered_units)
```

Never read `minimum_price_rub`, `promotion_*`, Search Visibility, candidate, MPStats, or frontend state.
- [ ] Run targeted tests; expect PASS. Run `python -m pytest tests/test_ozon_products_parser.py tests/test_ozon_products_import.py -q`; expect PASS.
- [ ] Commit: `git add backend/analytics/core_benchmark.py tests/test_core_benchmark_analytics.py && git commit -m "feat(PR7): extract benchmark and advertising metrics"`.

---

### Task 4: Add deterministic ProductSnapshot context reads

**Files:**
- Modify: `backend/persistence/repositories/product_snapshots.py: ProductSnapshotRepository read methods`
- Modify: `tests/test_product_snapshot_repository.py: PR7 anchor and exact-context repository tests`

**Interfaces:**
- Consumes:
  - `product_id: int`;
  - `product_ids: Iterable[int]`, `report_generated_on: date`, `report_window_days: int`.
- Produces:
  - `find_latest_current_for_product(self, product_id: int) -> ProductSnapshot | None`;
  - `list_current_for_products_at_context(self, product_ids: Iterable[int], report_generated_on: date, report_window_days: int) -> dict[int, ProductSnapshot]`.

- [ ] Add failing repository tests named `test_find_latest_current_prefers_newest_generated_date`, `test_find_latest_current_prefers_longest_window_on_same_date`, `test_find_latest_current_returns_highest_revision_inside_selected_context`, `test_anchor_is_independent_of_imported_at_id_and_insert_order`, `test_list_context_returns_current_exact_compatible_snapshots_only`, `test_context_read_uses_older_exact_match_instead_of_newer_incompatible_snapshot`, `test_context_read_deduplicates_requested_ids_and_excludes_unrequested_products`, and `test_context_read_handles_empty_product_ids`.

Run from repository root:

```bash
python -m pytest tests/test_product_snapshot_repository.py -q
```

Expected: FAIL with missing repository methods.

- [ ] Implement repository-owned SQL with two semantic stages. The first query orders distinct own logical keys only by `report_generated_on DESC, report_window_days DESC`; `find_current(...)` then resolves maximum revision for that exact key. The batch query uses parameterized requested IDs and exact date/window, selecting max revision per product. Return `{}` before forming an `IN` clause for empty input.
- [ ] Run targeted repository tests; expect PASS. Run `python -m pytest tests/test_database.py tests/test_migrations.py tests/test_observation_revision_convention.py -q`; expect PASS.
- [ ] Commit: `git add backend/persistence/repositories/product_snapshots.py tests/test_product_snapshot_repository.py && git commit -m "feat(PR7): add exact benchmark snapshot reads"`.

---

### Task 5: Orchestrate product, composition, anchor, and readiness

**Files:**
- Create: `backend/application/core_benchmark.py`
- Create: `tests/test_core_benchmark_service.py`
- Modify: `backend/analytics/core_benchmark.py: public calculation entry point and empty-result construction`

**Interfaces:**
- Consumes:
  - `ProductRepository.get_product(product_id)`;
  - `BenchmarkSelectionRepository.get_benchmark(own_product_id)`;
  - both Task 4 ProductSnapshot reads;
  - `calculate_core_benchmark(*, product_id: int, composition: BenchmarkComposition, own_snapshot: ProductSnapshot, competitor_snapshots: Mapping[int, ProductSnapshot]) -> CoreBenchmarkResult`.
- Produces:
  - `CoreBenchmarkService(*, db_path: Path)`;
  - `CoreBenchmarkService.get_core_benchmark(product_id: int) -> CoreBenchmarkResult`.

- [ ] Write service tests first: `test_missing_product_raises_product_not_found`, `test_non_owned_product_raises_existing_product_not_owned_error`, `test_no_set_and_set_without_revision_return_no_benchmark`, `test_current_benchmark_without_own_snapshot_returns_no_own_source_data`, `test_service_selects_one_anchor_before_loading_competitors`, and `test_service_passes_only_current_exact_context_snapshots_to_analytics`.

```python
def test_current_benchmark_without_own_snapshot_returns_no_own_source_data(db_path, seeded_benchmark):
    result = CoreBenchmarkService(db_path=db_path).get_core_benchmark(seeded_benchmark.own_product_id)
    assert result.readiness is CoreBenchmarkReadiness.NO_OWN_SOURCE_DATA
    assert result.benchmark is not None
    assert result.observation is None
    assert result.metrics == ()
```

Run from repository root:

```bash
python -m pytest tests/test_core_benchmark_service.py -q
```

Expected: FAIL because `CoreBenchmarkService` is absent.

- [ ] Implement one `transaction(self._db_path)` boundary. Validate product existence/ownership, load composition, map `NO_BENCHMARK`, then load own anchor and map `NO_OWN_SOURCE_DATA`. Batch-load only `current_revision.members` at the exact anchor context and delegate. Let `ProductNotFound`, `ProductNotOwnedError`, SQLite errors, and programming errors propagate as specified.
- [ ] Run targeted tests; expect PASS. Run `python -m pytest tests/test_benchmark_selection_repository.py tests/test_benchmark_selection_api.py -q`; expect PASS.
- [ ] Commit: `git add backend/application/core_benchmark.py backend/analytics/core_benchmark.py tests/test_core_benchmark_service.py && git commit -m "feat(PR7): orchestrate core benchmark context"`.

---

### Task 6: Calculate independent metric samples and aggregate exclusions

**Files:**
- Modify: `backend/analytics/core_benchmark.py: sample construction and metric-result builder`
- Modify: `tests/test_core_benchmark_analytics.py: sampling and explainability tests`

**Interfaces:**
- Consumes:
  - resolved `BenchmarkComposition.current_revision.members`, own snapshot, and `Mapping[int, ProductSnapshot]` from Task 5.
- Produces:
  - `_build_metric_result(definition: _MetricDefinition, own_snapshot: ProductSnapshot, members: tuple[BenchmarkMember, ...], competitor_snapshots: Mapping[int, ProductSnapshot]) -> CoreBenchmarkMetric` (or an equivalent immutable member sequence from the current revision);
  - one ordered `sample_values` tuple per metric, carrying identity from `BenchmarkMember`, title from the exact-compatible persisted `ProductSnapshot`, and the extracted value;
  - exact three-key `exclusion_summary` for each metric.

- [ ] Add failing tests: `test_sample_values_contains_exactly_metric_participants`, `test_sample_size_equals_number_of_sample_values`, `test_sample_plus_exclusions_equals_benchmark_member_count`, `test_missing_compatible_observation_excludes_member_from_sample_values`, `test_nullable_metric_excludes_member_only_from_that_metric_sample`, `test_zero_ordered_units_keeps_spend_but_excludes_support`, `test_zero_source_value_enters_sample`, and `test_exclusion_summary_always_has_exact_three_keys`.
- [ ] Run `python -m pytest tests/test_core_benchmark_analytics.py -q` from repository root; expect FAIL on absent sample accounting.
- [ ] Implement one extraction attempt per member per metric. Count no snapshot first, nullable source absence second, invalid derivative third; otherwise append one Decimal. Do not mutate composition or source objects.

```python
summary = {reason: 0 for reason in MetricExclusionReason}
sample_values = []
for member in members:
    snapshot = competitor_snapshots.get(member.product_id)
    if snapshot is None:
        summary[MetricExclusionReason.NO_COMPATIBLE_OBSERVATION] += 1
        continue
    value, reason = _extract_metric(snapshot, definition.metric_id)
    if reason is not None:
        summary[reason] += 1
    else:
        sample_values.append(BenchmarkSampleValue(
            product_id=member.product_id,
            ozon_product_id=member.ozon_product_id,
            title=snapshot.title,
            value=value,
        ))

values = tuple(item.value for item in sample_values)
```

The single pass above is the only participant filter. Do not build an independent hidden values sample. Preserve the incoming PR6 `BenchmarkSetRevision.members` relative order (numeric Ozon ID ascending, then product ID ascending); analytics must not sort by identity or metric value. Identity comes from the member read model, not SQL or a `ProductExternalIdentityRepository` dependency in analytics. A missing title remains `None`.

- [ ] Run targeted tests; expect PASS. Run `python -m pytest tests/test_core_benchmark_service.py tests/test_product_snapshot_repository.py -q`; expect PASS.
- [ ] Commit: `git add backend/analytics/core_benchmark.py tests/test_core_benchmark_analytics.py && git commit -m "feat(PR7): add metric-specific benchmark samples"`.

---

### Task 7: Complete integrated Core Benchmark calculation

**Files:**
- Modify: `backend/analytics/core_benchmark.py: calculate_core_benchmark and result readiness`
- Modify: `tests/test_core_benchmark_analytics.py: full-result tests`
- Modify: `tests/test_core_benchmark_service.py: revision, purity, ordering, and immutability integration tests`

**Interfaces:**
- Consumes:
  - Task 1 DTOs, Task 2 statistics, Task 3 extraction, Task 6 samples.
- Produces:
  - the stable public `calculate_core_benchmark(...) -> CoreBenchmarkResult` used by `CoreBenchmarkService`.

- [ ] Add failing tests: `test_full_result_contains_all_thirteen_metrics_in_catalog_order`, `test_metric_readiness_and_top_level_readiness_follow_exact_matrix`, `test_own_unavailable_with_competitor_values_withholds_comparison`, `test_quartiles_appear_at_four_without_rounding`, `test_statistics_use_exact_sample_values`, `test_sample_values_preserve_benchmark_member_order`, `test_current_composition_revision_changes_next_result`, `test_superseded_snapshots_never_duplicate_sample_values`, `test_repeated_calculation_does_not_modify_snapshots_or_composition`, `test_presentation_metadata_change_does_not_change_member_identity_or_result_membership`, and `test_candidate_search_visibility_and_mpstats_types_are_absent_from_analytics_dependencies`.

Run from repository root:

```bash
python -m pytest tests/test_core_benchmark_analytics.py tests/test_core_benchmark_service.py -q
```

Expected: FAIL on incomplete result/readiness integration.

- [ ] Implement all 13 results in numeric catalog order. Median exists at N >= 1; P25/P75 at N >= 4; own/delta/position follow own availability and N >= 3. Integrated-result assertions use the exact `BELOW_MEDIAN`, `AT_MEDIAN`, `ABOVE_MEDIAN`, and `UNAVAILABLE` values. Top readiness is `NO_COMPATIBLE_SAMPLE` only when all 13 N values are zero, `INSUFFICIENT_SAMPLE` when at least one N is 1–2 but no metric is ready, and `READY` when any metric has own value plus N >= 3.
- [ ] Populate `ObservationContext` from the one own snapshot and `BenchmarkRevisionContext` from the current composition. Competitor member iteration uses persisted composition identities; statistical sorting uses only numeric Decimal values.
- [ ] Enforce for every metric: `sample_size == len(sample_values)`; `sample_size + sum(exclusion_summary.values()) == benchmark_member_count`; and median/P25/P75 receive exactly `tuple(item.value for item in sample_values)`. The member-order regression starts with differing DB insertion order, relies on the PR6 repository to return canonical members, and verifies that PR7 preserves that relative order rather than sorting shuffled members inside analytics.
- [ ] Run targeted tests; expect PASS. Run `python -m pytest tests/test_benchmark_selection_repository.py tests/test_observation_revision_convention.py tests/test_product_repository.py -q`; expect PASS.
- [ ] Commit: `git add backend/analytics/core_benchmark.py tests/test_core_benchmark_analytics.py tests/test_core_benchmark_service.py && git commit -m "feat(PR7): complete core benchmark calculation"`.

---

### Task 8: Expose the exact read-only FastAPI contract

**Files:**
- Modify: `backend/main.py: imports, CoreBenchmarkService factory, and product core-benchmark GET route`
- Create: `tests/test_core_benchmark_api.py`

**Interfaces:**
- Consumes:
  - `CoreBenchmarkService(db_path=resolve_db_path()).get_core_benchmark(product_id)`;
  - existing `_json`, `ProductNotFound`, `ProductNotOwnedError`, and PR6 error envelope.
- Produces:
  - `get_core_benchmark(product_id: Annotated[int, Path(gt=0)])` at `GET /api/products/{product_id}/core-benchmark`;
  - exact JSON keys and canonical non-exponent Decimal strings.

- [ ] Write API tests first: `test_core_benchmark_ready_response_has_exact_all_metric_shape_and_order`, `test_core_benchmark_serializes_decimal_strings_without_trailing_zeroes`, `test_api_serializes_sample_values_with_canonical_decimal_strings`, `test_core_benchmark_returns_each_normal_readiness_over_200`, `test_core_benchmark_partial_metrics_keep_nulls_and_exclusion_shape`, `test_core_benchmark_includes_current_benchmark_and_observation_revision_context`, `test_core_benchmark_missing_product_uses_exact_404_envelope`, `test_core_benchmark_non_owned_uses_exact_409_envelope`, `test_core_benchmark_invalid_id_uses_422`, and `test_repeated_get_creates_no_rows`.

Run from repository root:

```bash
python -m pytest tests/test_core_benchmark_api.py -q
```

Expected: FAIL with HTTP 404 because the route is absent.

- [ ] Add the thin route. Reuse `_json(...)` so enums, dates, datetimes, tuples, mappings, and Decimal values follow existing serialization, tightening only if the tests prove the helper does not meet canonical Decimal text.
- [ ] Serialize `sample_values` exactly as `product_id`, `ozon_product_id`, nullable `title`, and canonical Decimal-string `value`, preserving tuple order and without adding per-member exclusion fields. API assertions require the exact `comparison_position` strings `BELOW_MEDIAN`, `AT_MEDIAN`, `ABOVE_MEDIAN`, and `UNAVAILABLE`.

```python
@app.get("/api/products/{product_id}/core-benchmark")
def get_core_benchmark(product_id: Annotated[int, Path(gt=0)]):
    try:
        return _json(CoreBenchmarkService(db_path=resolve_db_path()).get_core_benchmark(product_id))
    except (ProductNotFound, ProductNotOwnedError) as error:
        return _pr6_error_response(error)
```

- [ ] Run targeted API tests; expect PASS. Run `python -m pytest tests/test_backend.py tests/test_benchmark_selection_api.py tests/test_ozon_products_api.py -q`; expect PASS.
- [ ] Commit: `git add backend/main.py tests/test_core_benchmark_api.py && git commit -m "feat(PR7): expose core benchmark API"`.

---

### Task 9: Add race-safe frontend endpoint integration

**Files:**
- Modify: `frontend/assets/js/app.js: competitorState, workspace reset/open, benchmark save, and PR7 fetch lifecycle`
- Modify: `tests/test_frontend_contract.py: JS endpoint and stale-selection guards`

**Interfaces:**
- Consumes:
  - `competitorState.activeProduct`, saved benchmark flow, and Task 8 endpoint.
- Produces:
  - `competitorState.coreBenchmark`, `competitorState.coreBenchmarkRequestId`;
  - `resetCoreBenchmarkState() -> void`;
  - `openCoreBenchmark() -> Promise<void>`;
  - `loadCoreBenchmark(productId: number, requestId: number) -> Promise<void>`.

- [ ] Add frontend contract assertions first for the exact endpoint, request token, active-product equality check, reset on workspace change, and refetch after a successful `saveBenchmark(...)`. Assert `competitor_state.js` is untouched by PR7 responsibilities.

Run from repository root:

```bash
python -m pytest tests/test_frontend_contract.py -q
```

Expected: FAIL because PR7 frontend functions/markers are absent.

- [ ] Extend `competitorState` with result plus monotonic request ID. `resetCompetitorState(product)` calls `resetCoreBenchmarkState()`. `openCoreBenchmark()` reveals the panel, increments the token, captures the active product ID, shows loading, and fetches. After awaiting, render only when both request token and active product ID still match; otherwise discard the stale response.
- [ ] In the successful existing `saveBenchmark(productId)` path, clear the old analytical result and, when the PR7 panel is open, call `openCoreBenchmark()` after composition reload so the displayed revision cannot lag.
- [ ] Run the targeted test and `node --check frontend/assets/js/app.js`; expect PASS. Run `node tests/competitor_state_contract.mjs`; expect PASS.
- [ ] Commit: `git add frontend/assets/js/app.js tests/test_frontend_contract.py && git commit -m "feat(PR7): load benchmark detail safely"`.

---

### Task 10: Build the grouped scan-first Core Benchmark summary

**Files:**
- Modify: `frontend/index.html: after #benchmark-selected-panel within #competitors-workspace`
- Modify: `frontend/assets/js/app.js: grouped summary rendering and value formatting`
- Modify: `frontend/assets/css/app.css: grouped benchmark summary using existing tokens`
- Modify: `tests/test_frontend_contract.py: summary structure, grouping, formatting, and semantic guards`

**Interfaces:**
- Consumes:
  - successful `CoreBenchmarkResult` JSON and backend-provided labels.
- Produces:
  - `#core-benchmark-open`, `#core-benchmark-panel`, `#core-benchmark-status`, `#core-benchmark-context`, `#core-benchmark-groups`;
  - `renderCoreBenchmark(result: object) -> void`;
  - `formatBenchmarkValue(value: string | null, unit: string, options?: object) -> string`;
  - `coreBenchmarkObservationPhrase(observation: object) -> string`.

- [ ] Add failing DOM/JS assertions for insertion after the saved benchmark summary, the five group headings in exact order, backend-label use, own/median/delta/N/confidence/position summary fields, estimate markers, neutral contextual classes, and absence of good/bad/win/problem/recommendation copy.
- [ ] Run `python -m pytest tests/test_frontend_contract.py -q` from repository root; expect FAIL on absent summary markup/functions.
- [ ] Add one `Benchmark details` button and one hidden card below `.benchmark-layout`, still inside `#competitors-workspace`; do not add navigation. Render five compact group sections (`Result`, `Traffic`, `Conversion`, `Offer`, `Advertising`) rather than one flat 13-row table. Each compact metric control exposes label, own, median, signed absolute delta, N, factual position, and confidence; detailed values stay collapsed. Render `BELOW_MEDIAN` as `Ниже медианы`, `AT_MEDIAN` as `На уровне медианы`, `ABOVE_MEDIAN` as `Выше медианы`, and keep the existing unavailable presentation for `UNAVAILABLE`; do not use “ниже benchmark”, “внутри benchmark”, or “выше benchmark” for this enum.
- [ ] Format canonical decimal strings only at display time with `Intl.NumberFormat("ru-RU", ...)`: whole RUB/count/unit, one decimal plus `%` for percentage points, `п.п.` for percentage deltas, and whole `₽/заказанную ед.` for support. Null is `—`, never zero. Use `coreBenchmarkObservationPhrase` to render exactly `7 дней · отчёт сформирован 23.08.2026`, never an inferred range.
- [ ] Add CSS with existing variables (`--color-*`, radii, spacing patterns), accessible focus/expanded states, and a responsive stacked group layout; no traffic-light meaning for contextual advertising.
- [ ] Run targeted frontend tests and `node --check frontend/assets/js/app.js`; expect PASS. Run `python -m pytest tests/test_frontend_contract.py tests/test_runtime_contract.py -q`; expect PASS.
- [ ] Commit: `git add frontend/index.html frontend/assets/js/app.js frontend/assets/css/app.css tests/test_frontend_contract.py && git commit -m "feat(PR7): add grouped benchmark summary UI"`.

---

### Task 11: Add expandable Benchmark Detail

**Files:**
- Modify: `frontend/assets/js/app.js: metric disclosure renderer and toggle handler`
- Modify: `frontend/assets/css/app.css: metric detail/disclosure layout`
- Modify: `tests/test_frontend_contract.py: detail content and accessibility contracts`

**Interfaces:**
- Consumes:
  - `CoreBenchmarkMetric`, its API-provided `sample_values`, top-level benchmark/observation context, and exact aggregate `exclusion_summary`.
- Produces:
  - `renderCoreBenchmarkMetric(metric: object, benchmark: object) -> string`;
  - `toggleCoreBenchmarkMetricDetail(button: HTMLButtonElement) -> void`;
  - `aria-expanded`/`aria-controls` disclosure linkage per metric.

- [ ] Add failing assertions, including `test_benchmark_detail_renders_sample_values_without_transient_candidate_lookup`, that every compact summary metric is a disclosure control and expanded detail includes own, median, nullable P25/P75, delta, metric N, confidence, benchmark revision/member count, period/freshness, actual participating competitor values, and the three exact human aggregate-exclusion labels. Assert the exact `BELOW_MEDIAN`/`AT_MEDIAN`/`ABOVE_MEDIAN` display labels and existing `UNAVAILABLE` presentation. Assert no per-member exclusion DTO/history or transient candidate lookup is used.
- [ ] Run `python -m pytest tests/test_frontend_contract.py -q` from repository root; expect FAIL on absent detail behavior.
- [ ] Render one hidden detail region per metric with escaped stable IDs based on `metric_id`. Show P25/P75/delta null as `—` plus “Недоступно для текущей выборки”, and show aggregate counts when N is below member count:

```text
NO_COMPATIBLE_OBSERVATION → Нет совместимого наблюдения
SOURCE_METRIC_UNAVAILABLE → Нет исходного значения показателя
DERIVED_VALUE_UNAVAILABLE → Нельзя вычислить производный показатель
```

Render competitor sample values directly from `metric.sample_values`, preserving API order. Use a non-null `title` as the single display label; otherwise use `Ozon SKU <ozon_product_id>` without duplicating the SKU on a second line. The saved `#benchmark-selected-list` remains a composition surface; the detail disclosure does not reconstruct values or metadata from that list, candidate state, Search Visibility, MPStats, or any frontend lookup. Aggregate exclusions remain counts only, with no per-member exclusion reason.
- [ ] Run targeted tests and `node --check frontend/assets/js/app.js`; expect PASS. Run `node tests/competitor_state_contract.mjs`; expect PASS.
- [ ] Commit: `git add frontend/assets/js/app.js frontend/assets/css/app.css tests/test_frontend_contract.py && git commit -m "feat(PR7): add benchmark metric disclosures"`.

---

### Task 12: Cover every frontend readiness, partial, and failure state

**Files:**
- Modify: `frontend/assets/js/app.js: readiness/state rendering and retry behavior`
- Modify: `frontend/index.html: live region and retry control inside #core-benchmark-panel`
- Modify: `frontend/assets/css/app.css: state presentation using existing status/card primitives`
- Modify: `tests/test_frontend_contract.py: seven-state and fake-zero guards`

**Interfaces:**
- Consumes:
  - top-level readiness `NO_BENCHMARK`, `NO_OWN_SOURCE_DATA`, `NO_COMPATIBLE_SAMPLE`, `INSUFFICIENT_SAMPLE`, `READY`, network/HTTP failure, and mixed metric readiness.
- Produces:
  - `renderCoreBenchmarkState(state: string, result: object | null) -> void`;
  - `#core-benchmark-retry` bound to `openCoreBenchmark()`.

- [ ] Add failing tests for exact visible copy: loading `Рассчитываем benchmark…`; no benchmark; no own Ozon data; no compatible sample; insufficient sample while retaining available medians/N; ready; partial `Часть показателей недоступна`; failed request plus retry. Assert unavailable values never render fake zero and stale data is cleared before each request.
- [ ] Run `python -m pytest tests/test_frontend_contract.py -q` from repository root; expect FAIL on incomplete state matrix.
- [ ] Implement state branching without throwing for successful analytical no-data responses. `READY` renders all 13 metrics and the partial banner when any metric is non-ready. `INSUFFICIENT_SAMPLE` renders available metric detail rather than replacing it with one empty message. Fetch failures clear result markup and expose retry; internal error detail is not displayed.
- [ ] Run targeted tests and `node --check frontend/assets/js/app.js`; expect PASS. Run `python -m pytest tests/test_frontend_contract.py tests/test_core_benchmark_api.py -q`; expect PASS.
- [ ] Commit: `git add frontend/index.html frontend/assets/js/app.js frontend/assets/css/app.css tests/test_frontend_contract.py && git commit -m "feat(PR7): handle benchmark readiness states"`.

---

### Task 13: Extend the Windows portable smoke minimally

**Files:**
- Modify: `tests/windows_smoke.ps1: synthetic PR7 seed and endpoint assertion near Assert-Pr6Workflow`

**Interfaces:**
- Consumes:
  - existing `Invoke-DbPython`, portable initialized DB, loopback server, and Task 8 endpoint.
- Produces:
  - `Assert-Pr7CoreBenchmark` that seeds one owned product plus at least three saved competitors with exact-context current ProductSnapshots/current benchmark revision and checks one exact source and advertising result.

- [ ] Add the smoke function before running it. Seed through the existing schema with synthetic values only; retain all current PR1–PR6 startup, missing-product, reuse, repair, path, and data-preservation checks. Assert HTTP 200, current revision ID, `READY`, 13 metrics, `ordered_amount_rub` expected median, and exact `estimated_ad_spend_rub` own value.
- [ ] Run the available static checks from repository root:

```bash
python -m pytest tests/test_runtime_contract.py tests/test_frontend_contract.py -q
```

Expected: PASS. The PowerShell workflow itself is authoritative on Windows.

- [ ] Run in PowerShell from repository root when executing in Windows CI:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Expected: PASS, including the new PR7 endpoint probe. On a non-Windows implementation host, record this exact check as pending authoritative GitHub Actions verification rather than replacing it with an analytical test.
- [ ] Commit: `git add tests/windows_smoke.ps1 && git commit -m "test(PR7): extend portable benchmark smoke"`.

---

### Task 14: Run full verification and perform scope self-review

**Files:**
- Verify only: `backend/domain/core_benchmark.py`
- Verify only: `backend/analytics/__init__.py`
- Verify only: `backend/analytics/core_benchmark.py`
- Verify only: `backend/application/core_benchmark.py`
- Verify only: `backend/persistence/repositories/product_snapshots.py`
- Verify only: `backend/main.py`
- Verify only: `frontend/index.html`
- Verify only: `frontend/assets/js/app.js`
- Verify only: `frontend/assets/css/app.css`
- Verify only: `tests/test_core_benchmark_analytics.py`
- Verify only: `tests/test_core_benchmark_service.py`
- Verify only: `tests/test_core_benchmark_api.py`
- Verify only: `tests/test_product_snapshot_repository.py`
- Verify only: `tests/test_frontend_contract.py`
- Verify only: `tests/windows_smoke.ps1`

**Interfaces:**
- Consumes:
  - every frozen interface and commit from Tasks 1–13.
- Produces:
  - no new interface or source change; only verified evidence for handoff.

- [ ] Run targeted PR7 tests from repository root:

```bash
python -m pytest tests/test_core_benchmark_analytics.py tests/test_product_snapshot_repository.py tests/test_core_benchmark_service.py tests/test_core_benchmark_api.py tests/test_frontend_contract.py -q
```

Expected: PASS.

- [ ] Run the full Python regression suite from repository root:

```bash
python -m pytest -q
```

Expected: PASS with PR1–PR7 meanings intact.

- [ ] Run JavaScript checks from repository root:

```bash
node --check frontend/assets/js/app.js
node --check frontend/assets/js/keystore.js
node --check frontend/assets/js/competitor_state.js
node tests/keystore_contract.mjs
node tests/competitor_state_contract.mjs
```

Expected: every command exits zero and each contract prints PASS.

- [ ] On Windows CI, run from repository root:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Expected: PASS. Record it as pending GitHub Actions if the implementation host is not Windows.

- [ ] Run architecture and scope scans from repository root:

```bash
rg -n "sqlite3|fastapi|mpstats|BenchmarkCandidate|SearchVisibility" backend/analytics backend/domain/core_benchmark.py
rg -n "BenchmarkSnapshot|AdvertisingSnapshot|benchmark_metric_results|analytics_cache" backend tests
git diff --check
git status --short
git diff --name-status HEAD~13..HEAD
```

Expected: the dependency scan has no infrastructure/source hits in pure analytics; forbidden persistence scan has no PR7 additions; diff check is clean; status is clean; changed paths are confined to the approved implementation file map.

- [ ] Review the approved spec section by section and record affirmative checks for: exact 13 metrics; one common anchor; newest-date/longest-window selection; current revisions; exact compatibility; Decimal median and Type-7 quartiles; N thresholds; exact `BELOW_MEDIAN`/`AT_MEDIAN`/`ABOVE_MEDIAN`/`UNAVAILABLE` values; P25/P75 excluded from position semantics; delta/position/direction/confidence; advertising formulas and terminology; independent `sample_values`; `sample_size == len(sample_values)`; sample plus aggregate exclusions equals member count; statistics use exactly `sample_values`; Benchmark Detail sample values present; aggregate exclusions preserved; no per-member exclusion DTO/history; API shapes/errors/order; grouped compact summary; all readiness states; exact freshness phrase; no fake zero; source/identity separation; deterministic member order; immutability; no migration/dependency; no PR8 behavior.
- [ ] Do not create a verification-only commit. If verification exposes a defect, return to the owning task, add a failing regression test, make the smallest correction, rerun that task and this full suite, and amend only that focused task commit before handoff.

## Implementation Commit Sequence

```text
feat(PR7): add core benchmark domain contracts
feat(PR7): add decimal benchmark statistics
feat(PR7): extract benchmark and advertising metrics
feat(PR7): add exact benchmark snapshot reads
feat(PR7): orchestrate core benchmark context
feat(PR7): add metric-specific benchmark samples
feat(PR7): complete core benchmark calculation
feat(PR7): expose core benchmark API
feat(PR7): load benchmark detail safely
feat(PR7): add grouped benchmark summary UI
feat(PR7): add benchmark metric disclosures
feat(PR7): handle benchmark readiness states
test(PR7): extend portable benchmark smoke
```

## Plan Completion Boundary

Executing this plan ends at the PR7 measurement layer: a stable machine-facing `metric_id`, `direction`, `comparison_position`, and `confidence`; exact current source/revision provenance; grouped user-facing comparison; and aggregate explainability. It does not create diagnostic reasons, causal analysis, recommendations, automatic competitor changes, future source/API work, or persistence for calculated benchmark results.
