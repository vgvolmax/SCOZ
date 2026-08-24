# SCOZ — PR7 Core Benchmark & Advertising Intensity Implementation Spec

## 1. Status, authority, and analysis base

**Status:** Proposed, awaiting independent review and approval. This document is the PR-specific authority for the future implementation of **PR7 — Core Benchmark & Advertising Intensity**. It is not an Implementation Plan and does not authorize PR8 work.

```text
PR7_SPEC_BASE_SHA=3cedb9e9b9f3a3769a37b1e22c1f58d0ff84faff
```

The repository was inspected on branch `work`, whose clean HEAD was the SHA above. The SHA records the factual analysis base; it is not a request to reset a later branch.

This spec is subordinate to the approved product contracts, Architecture Design, Preflight Decisions, UI/UX Design, Visual Design System, and latest PR Development Plan. For PR7 scope and sequencing, the latest plan controls. No conflict was found among those sources or the inspected PR6 implementation.

## 2. Context after PR6

PR6 has already implemented product-specific relevant-query selection, manually confirmed benchmark composition, stable `BenchmarkSet`, immutable `BenchmarkSetRevision`, and `BenchmarkMember`. The current composition is read by `BenchmarkSelectionRepository.get_benchmark()`. A member is a canonical `Product` with an Ozon product identity; membership does not assert that product-level Ozon facts exist.

PR3 already persists immutable `ProductSnapshot` observations. Their logical key is `(product_id, report_generated_on, report_window_days)`. A corrected import creates a higher `revision` and points to the superseded row. `ProductSnapshotRepository.find_current()` already resolves the highest revision for one exact logical key. Its existing list method chooses one latest current observation per product, but PR7 needs exact-context reads rather than “latest competitor” reads.

The current application style is dataclass/enum domain contracts, repositories owning SQL, application services owning transaction/orchestration boundaries, thin FastAPI handlers, and committed framework-free HTML/CSS/JavaScript. PR7 preserves that style.

## 3. Goal

For one owned SKU, calculate a transparent, current, derived comparison against the members of its current benchmark revision using only metric-specific, period-compatible current Ozon ProductSnapshot facts. Return own value, median, optional quartiles, absolute delta, sample size, factual performance status (position relative to the median), metric direction, confidence, and an aggregate explanation of sample reduction. Include the required derived advertising-intensity metrics.

PR7 answers **“How does this SKU compare with the selected benchmark on compatible facts?”** It does not answer why the SKU performs that way or what the user should do.

## 4. Scope

PR7 comprises exactly:

- a feature-specific pure Core Benchmark analytics module;
- read-only orchestration over the selected owned product, current benchmark revision, and current ProductSnapshot revisions;
- the exact 13-metric catalog in section 10;
- one read endpoint, `GET /api/products/{product_id}/core-benchmark`;
- a Benchmark Detail section within the existing selected-SKU/competitor workflow;
- deterministic statistical, readiness, provenance, API, UI, and test contracts below;
- a minimal Windows smoke extension that proves the packaged app can reach the new endpoint with synthetic persisted facts.

The result is calculated on request. It is neither persisted nor treated as source history.

## 5. Exhaustive non-goals

PR7 does not include:

- PR8 Diagnostics, diagnostic reason codes, top-3 causes, recommendations, business verdicts, or OOS diagnostic/confounder logic;
- PR9 Search Visibility Heatmap or query × cluster benchmark;
- PR10 Query Opportunity, MPStats position history, or `SearchPositionSnapshot`;
- PR11 Ozon public API sync;
- PR12 `AdvertisingSnapshot`, actual Ozon Performance API spend, advertising attribution, CPC/CPO, or ad/organic sales reconstruction;
- PR13/PR14 Ramp-up, position-normalized conversion, scenarios, or organic-support conclusions;
- ML, universal card score, Opportunity Score, or any 0–100 confidence/quality score;
- a universal metric engine, configurable metric DSL, generic analytics repository, generic source resolver, or generic analytics configuration;
- `BenchmarkSnapshot`, materialized benchmark history/cache, saved analytical results, or any generic analytical-history table;
- historical-revision analytics endpoint or benchmark-history UI;
- a migration, new table/entity, new dependency, new source adapter, or changes to source ingestion contracts;
- MPStats sales estimates or any MPStats input in calculations;
- `missed_sales_source_value`, `promotion_discount_source_value`, turnover change, daily averages, stock, OOS days, promotion share/days, advertising days, or fields not listed in section 10;
- minimum price: it was explicitly considered as a contextual metric, but is excluded because average price is the single compact, comparable PR7 offer context and a second price row adds no required PR8 input; exclusion does not imply that lower or higher minimum price would be good or bad;
- silent period alignment, nearest-date matching, date tolerance, overlap estimation, averaging periods, extrapolation, interpolation, invented dimensions, invented dates, missing-to-zero conversion, clamping, or source-fact correction;
- a separate advertising dashboard or a new Product Workspace/navigation model.

## 6. Existing source facts and dependencies

The sole numerical source is the current revision of `ProductSnapshot`, imported under Ozon Products Source Contract v1. It supplies the report context `report_generated_on` and `report_window_days`; it does **not** supply `period_start` or `period_end`.

All catalog metrics exist with the same ProductSnapshot semantics for own products and competitors because ownership is a relation on the same `Product` entity. `buyout_share_pct` alone is nullable under the approved missing sentinel. Numeric zero is an observed fact. Other catalog source metrics are required by the source contract, although a competitor may have no compatible snapshot at all.

The benchmark dependency is the current `BenchmarkSetRevision` and its immutable ordered-by-product-id repository representation. The calculation must report its identity and member count. Relevant-query evidence and MPStats photos justify composition upstream but are not calculation inputs.

### 6.1 Hard boundary from PR6 candidate evidence

PR6 candidate data is selection evidence, not a PR7 analytical source fact. `BenchmarkCandidate.contextual_price_rub`, `best_position`, `representative_observed_at`, `source_title`, `seller_name`, matched-query/cluster counts, photos, MPStats preview data, frontend state, and transient manual-candidate metadata **must never** be used as a metric input or fallback by Core Benchmark. In particular, candidate price cannot fill a missing `ProductSnapshot.average_price_rub` or a missing compatible snapshot.

The only handoff from selection to measurement is persisted composition:

```text
BenchmarkSet -> current BenchmarkSetRevision -> BenchmarkMember.product_id
                                                  |
                                                  v
                             compatible canonical ProductSnapshot history
```

Every saved member is authoritative even when its brand, category, title, seller, photo, candidate rank, price similarity, query count, cluster count, or Search Visibility position looks unusual. PR7 does not rerank or remove it. Availability filtering is runtime, metric-specific analysis only: it neither changes nor creates a `BenchmarkSetRevision` and never changes source facts.

Presentation metadata is a separate concern. The canonical internal Product identity is `Product.id`; SCOZ relationships including `BenchmarkMember.product_id`, `ProductSnapshot.product_id`, and `BenchmarkSet.own_product_id` refer to that stable internal identifier. The authoritative Ozon external identity for the corresponding internal Product is the canonical `ProductExternalIdentity` carrying `source = "ozon"`, `identity_type = "ozon_product_id"`, `identity_value = <canonical Ozon product ID>`, and `source_account_scope = ""`. Raw `ozon_product_id` must not be described as the overall canonical Product identity.

For a benchmark member, `BenchmarkMember.product_id -> Product.id` is its persisted internal identity. **`BenchmarkMember.ozon_product_id` in the current domain/read model is a projection resolved from the existing canonical `ProductExternalIdentity`; it is not a second persisted benchmark identity and not a second source of truth.** The existing repository join may expose both IDs in a read DTO for usability and deterministic display ordering, but `benchmark_members` continues to persist only `benchmark_set_revision_id` and `product_id`. Benchmark composition remains stable through `product_id`; whenever API/UI presentation or deterministic ordering needs the external Ozon ID, it is resolved through the existing Product identity model. PR7 must not add an `ozon_product_id` benchmark column, copy Ozon identity into composition, create `BenchmarkMemberExternalIdentity` or another identity table, or introduce a parallel identity-resolution mechanism.

`ProductSnapshot.title`, `seller_name`, `brand`, `product_url`, price, photo, and category are persisted source-observation/presentation facts, **not identity**. If Benchmark Detail displays title, seller, brand, or product URL, it may read them from a real source observation solely for display; none identifies or merges a Product, replaces `Product.id` or canonical `ProductExternalIdentity`, changes `BenchmarkMember.product_id` or benchmark composition, or participates in benchmark mathematics. Equal titles never merge Products, and seller/brand changes in a new source revision never create a new Product. No fallback may match or merge by title, brand plus seller, similar URL text, or any other presentation field. When persisted presentation metadata is absent, the stable display fallback is canonical `ozon_product_id` and, if needed, internal `product_id`. The UI must not reconstruct title, price, seller, identity, or detail from transient PR6 candidate/frontend state. A manually saved member that has `Product`, `ProductExternalIdentity`, and `BenchmarkMember` but no `ProductSnapshot` remains in the revision, is excluded from ProductSnapshot-based metric samples, and may still be labeled by Ozon product ID; PR7 never deletes it automatically.

Source lineage remains on each snapshot through `id`, `revision`, `source_artifact_id`, `import_batch_id`, and `imported_at`. `imported_at` remains valid provenance/application metadata and a technical import/update timestamp; it may be exposed separately where useful. It is not business freshness and must not participate in business observation-context or business-freshness selection. For Ozon Product XLSX, business freshness is `report_generated_on`, while `report_window_days` describes the source report window. PR7 exposes these distinct observation and import contexts without exposing local artifact paths or raw files.

## 7. Benchmark analytical context

One request has exactly one analytical context:

```text
owned Product
+ current BenchmarkSetRevision
+ own anchor ProductSnapshot current revision
+ current competitor ProductSnapshot revisions at the anchor's exact context
```

The benchmark member count is composition size. Every metric independently derives its `sample_size` after availability/derivation checks; no metric may reuse member count or another metric's sample size.

The own anchor is selected before and independently of the benchmark composition. `BenchmarkSetRevision`, competitor observations, compatible-member count, metric availability, sample size, confidence, median/quantiles, or any attempt to maximize N **must not influence it**. **One Core Benchmark response MUST use exactly one common own `ProductSnapshot` observation context for all 13 PR7 product-level source and derived metrics.** PR7 v1 does not support metric-specific own observation contexts. Metric-specific availability may change only that metric's sample size, confidence, quantile availability, readiness, and statistics; it must never select another own date or window. The advertising derivatives use `ordered_amount_rub`, `ordered_units`, and `total_drr_pct` from this same selected own snapshot and receive no separate temporal context. Any future relaxation is a separately approved design change, not PR7 implementation discretion.

Only the current benchmark revision is calculated. After PR6 saves a new composition revision, the next request uses it. Old composition and source rows remain immutable, but PR7 offers no query parameter or endpoint for recalculating an old revision. The response revision identity is sufficient for current-result provenance; a historical CJM is not established.

## 8. Exact source-observation selection

The candidate set for own analytical anchor selection consists semantically of distinct logical `ProductSnapshot` observation contexts, not individual snapshot revision rows. In PR7 v1 one logical context is exactly `(product_id, report_generated_on, report_window_days)`. Revision is not an observation-context dimension: multiple revisions neither create additional anchor candidates nor influence anchor policy as separate observations nor increase the context count. Anchor selection therefore operates semantically over distinct logical contexts and then uses the current revision of the selected context. This does **not** require the analytics layer to load, group, inspect, or resolve historical revision rows.

Persistence owns source-history/current-revision resolution; the application service orchestrates the required reads; pure Core Benchmark analytics receives only clean feature-specific current analytical inputs. Persistence must expose the smallest PR7-specific read contract needed to (1) select the eligible current logical observation context for the own Product, (2) return the current revision for that selected context, and (3) return current exact-compatible competitor observations for the same context. Superseded revisions remain immutable source evidence for audit, provenance, and repository-level source-history verification, but they must not be passed into Core Benchmark calculation merely so analytics can decide which revision is current. PR7 introduces no `GenericObservationResolver`, `SnapshotHistoryEngine`, `RevisionResolverFramework`, `TemporalAnalyticsRepository`, `ObservationContextRegistry`, or equivalent generic temporal infrastructure.

For example, own history `2026-08-23 / 7 days / revision 1`, `2026-08-23 / 7 days / revision 2`, and `2026-08-23 / 28 days / revision 1` contains exactly two anchor candidates, not three. Correcting `D / 7 days / revision 1` to revision 2 preserves the same analytical observation context and merely changes its current revision.

The application service executes the following deterministic algorithm in one read transaction:

1. Load `Product` by path ID. Missing is an error; non-owned is an error.
2. Perform **observation selection** using only the business/source observation key. From the own ProductSnapshot logical keys, order the distinct `(report_generated_on, report_window_days)` contexts by `report_generated_on DESC`, then `report_window_days DESC`, and select the first context. Thus the newest report-generation date wins, and a same-date tie deterministically prefers the longer reported window.
3. Perform **revision selection** only after the logical observation is fixed: select the greatest current `revision` inside that exact `(product_id, report_generated_on, report_window_days)` key. No `imported_at`, snapshot database `id`, INSERT order, import-batch order, file-import order, repository return order, or SQLite natural row order may select or break a tie between analytical contexts. A correction imported later changes the current revision of its logical observation; it does not make the observation's business date later.
4. Load the PR6 `BenchmarkComposition` for that own product.
   - no `BenchmarkSet` or no `current_revision` returns `NO_BENCHMARK`;
   - a persisted set without a current revision is treated as the same normal readiness state, not repaired by analytics.
5. If no own anchor exists, return `NO_OWN_SOURCE_DATA`, with benchmark context present and no metrics.
6. For every member, resolve only `find_current(product_id=member.product_id, report_generated_on=anchor.report_generated_on, report_window_days=anchor.report_window_days)`. The greatest revision at that exact key is the current fact.
7. A member without that exact observation is excluded from every metric as `NO_COMPATIBLE_OBSERVATION`, even if an earlier/later or differently windowed snapshot is the member's latest snapshot.
8. From each compatible snapshot, extract or derive each metric independently. A missing nullable source field excludes that member only from that metric as `SOURCE_METRIC_UNAVAILABLE`; source facts that cannot yield a valid derived value exclude it as `DERIVED_VALUE_UNAVAILABLE`.
9. Corrections take effect naturally: a higher revision at the own anchor key replaces the superseded own payload; a higher revision at a competitor's exact compatible key replaces its superseded payload. Superseded rows are never additional sample members.

The own-anchor policy is analytical policy, not an accidental reuse of repository ordering. Its semantic basis is: use the freshest source-generated observation; where that source date exposes multiple valid report windows, use the longest window because PR7 has no user-selected window and the longer observation is the least volatile comparison context. `report_generated_on` and `report_window_days` are the only business facts that choose the observation context. `imported_at` may identify when SCOZ technically imported or updated the chosen revision, but it must not define business freshness, substitute for `report_generated_on`, or appear as `ORDER BY imported_at DESC` anchor policy. Repository SQL must implement this declared rule and tests must prove `imported_at`, database IDs, row/insertion/import order, benchmark revision/composition, compatible sample size, metric availability, and confidence cannot change it.

Normative examples:

| Case | Current own observations | Required anchor |
|---|---|---|
| A | `2026-08-23 / 7 days` only | `2026-08-23 / 7 days` |
| B | `2026-08-23 / 28 days` only | `2026-08-23 / 28 days` |
| C | `2026-08-23 / 7 days` and `2026-08-23 / 28 days` | `2026-08-23 / 28 days` (same-date longest-window rule) |
| D | `2026-08-23 / 28 days` and `2026-08-22 / 7 days` | `2026-08-23 / 28 days` (freshest generated date wins before window length) |
| E | revisions 1 and 2 for the chosen `2026-08-23 / 28 days` key | revision 2 of `2026-08-23 / 28 days`; revision 1 is superseded, not a sample row |

These keys remain source context only. None of the examples creates or implies `period_start` or `period_end`.

Observation-context selection and revision selection are two distinct steps for the own product and every member. First select the logical context by business/source observation semantics; for members, compatibility fixes that context to `(product_id, anchor.report_generated_on, anchor.report_window_days)`, so an overall newer but incompatible observation is irrelevant. Then select only the current (greatest) revision inside that exact context. An older exact-compatible member context may therefore be selected instead of a newer incompatible context, but a superseded revision of the selected logical observation may never be selected or added to the sample. A later-imported correction at the same date/window is selected as current revision without changing the anchor context.

The own metric may itself be unavailable (`buyout_share_pct`, or advertising support with zero ordered units). That metric returns an unavailable own/comparison result while other metrics remain independent. Competitor availability is still summarized for transparency, but no median/delta/status is presented for a metric whose own value is unavailable.

## 9. Period and grain compatibility

Compatibility is a hard equality gate:

```text
competitor.report_generated_on == own_anchor.report_generated_on
AND competitor.report_window_days == own_anchor.report_window_days
AND both are ProductSnapshot product-level observations from Ozon Products v1
```

There are no additional dimensions in PR7. Exact equality is necessary because the source does not identify period boundaries. `report_generated_on + report_window_days` must never be transformed into an inferred start/end range. Different dates with equal window, equal dates with different window, and merely overlapping conceptual windows are incompatible, not low-confidence inputs. There is no fallback to the latest, nearest, or averaged observation.

Canonical display is `{window} дней · отчёт сформирован {DD.MM.YYYY}`, for example `7 дней · отчёт сформирован 23.08.2026`. It must never become `17.08–23.08` without source evidence.

## 10. Exact Core Benchmark metric catalog

The ordered API/UI catalog is frozen below. `metric_id` is the stable machine/API identity and is independent of mutable Russian display wording. The table itself is the feature-specific PR7 catalog, not a generic Metric Registry. PR8 may refer to these IDs without parsing labels.

`nullable` describes whether own/member extraction can be unavailable (`ProductSnapshot` absence is handled before extraction). `comparison=YES` means relative comparison is permitted when sample rules are met. `delta` freezes the only returned delta. `quantiles=YES (N>=4)` means Type-7 P25/P75 under section 14.

| Order/group | `metric_id` | Source or exact formula | Russian UI label | API `unit` | Nullable | Direction | Comparison | Delta | Quantiles | Semantic notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 / Result | `ordered_amount_rub` | `ProductSnapshot.ordered_amount_rub` | Заказано на сумму | `RUB` | NO | `HIGHER_IS_BETTER` | YES | absolute RUB | YES (N>=4) | Ordered amount, not verified buyout revenue. |
| 2 / Result | `ordered_units` | `ProductSnapshot.ordered_units` | Заказано, шт. | `UNITS` | NO | `HIGHER_IS_BETTER` | YES | absolute units | YES (N>=4) | Ordered units, never “sold units”. |
| 3 / Result | `buyout_share_pct` | `ProductSnapshot.buyout_share_pct` | Доля выкупа | `PERCENTAGE_POINTS` | YES | `HIGHER_IS_BETTER` | YES | percentage points | YES (N>=4) | Missing sentinel is unavailable, never zero. |
| 4 / Traffic | `impressions_total` | `ProductSnapshot.impressions_total` | Показы всего | `COUNT` | NO | `HIGHER_IS_BETTER` | YES | absolute count | YES (N>=4) | Product-level exposure. |
| 5 / Traffic | `search_catalog_views` | `ProductSnapshot.search_catalog_views` | Просмотры в поиске и каталоге | `COUNT` | NO | `HIGHER_IS_BETTER` | YES | absolute count | YES (N>=4) | No query/cluster grain is invented. |
| 6 / Traffic | `card_views` | `ProductSnapshot.card_views` | Просмотры карточки | `COUNT` | NO | `HIGHER_IS_BETTER` | YES | absolute count | YES (N>=4) | Product-level card views. |
| 7 / Conversion | `impression_to_order_pct` | `ProductSnapshot.impression_to_order_pct` | Конверсия из показа в заказ | `PERCENTAGE_POINTS` | NO | `HIGHER_IS_BETTER` | YES | percentage points | YES (N>=4) | Source value is already in percentage points. |
| 8 / Conversion | `search_catalog_to_cart_pct` | `ProductSnapshot.search_catalog_to_cart_pct` | В корзину из поиска и каталога | `PERCENTAGE_POINTS` | NO | `HIGHER_IS_BETTER` | YES | percentage points | YES (N>=4) | Source value is already in percentage points. |
| 9 / Conversion | `card_to_cart_pct` | `ProductSnapshot.card_to_cart_pct` | В корзину из карточки | `PERCENTAGE_POINTS` | NO | `HIGHER_IS_BETTER` | YES | percentage points | YES (N>=4) | Source value is already in percentage points. |
| 10 / Offer | `average_price_rub` | `ProductSnapshot.average_price_rub` | Средняя цена | `RUB` | NO | `CONTEXTUAL` | YES | absolute RUB | YES (N>=4) | Relative position only; no price verdict. Candidate price is forbidden. |
| 11 / Advertising | `total_drr_pct` | `ProductSnapshot.total_drr_pct` | Общая ДРР | `PERCENTAGE_POINTS` | NO | `CONTEXTUAL` | YES | percentage points | YES (N>=4) | Advertising, not `promotion_*`; no automatic efficiency verdict. |
| 12 / Advertising | `estimated_ad_spend_rub` | `ordered_amount_rub * total_drr_pct / 100` | Оценка рекламных расходов | `RUB` | NO | `CONTEXTUAL` | YES | absolute RUB | YES (N>=4) | Derived estimate, not observed advertising spend. |
| 13 / Advertising | `advertising_support_per_ordered_unit_rub` | `estimated_ad_spend_rub / ordered_units`, only when `ordered_units > 0` | Рекламная поддержка на заказанную единицу | `RUB_PER_ORDERED_UNIT` | YES | `CONTEXTUAL` | YES | absolute RUB/ordered unit | YES (N>=4) | Denominator is ordered units, never sold/bought-out units. |

The canonical response/display group sequence is exactly Result, Traffic, Conversion, Offer, Advertising as represented by the numeric `Order` column; the numeric order, not group iteration, controls `metrics[]`. Labels may later change without changing `metric_id`.

Display precision is also frozen: RUB and RUB-per-ordered-unit rows render whole rubles; `UNITS` and `COUNT` render integers; `PERCENTAGE_POINTS` renders one decimal plus `%`. Both derived advertising rows carry an explicit “Оценка” marker. Display rounding follows section 12 and never changes analytical values.

Sales measures result; traffic measures exposure/engagement; conversion measures funnel effectiveness; average price supplies compact commercial context; buyout supplies post-order realization context; advertising rows show support rather than quality. All are product-level, same-source, same-context facts or deterministic derivatives and are useful inputs for later diagnostics without performing diagnosis here.

No percentage-point source value is converted on extraction: source `7.7` means `7.7%`. Conversion by `/100` occurs only inside the spend formula.

## 11. Metric direction semantics

`MetricDirection` has exactly:

- `HIGHER_IS_BETTER`: higher values can be favorable for later diagnostic interpretation, but PR7 still reports only relative position;
- `CONTEXTUAL`: neither lower nor higher is intrinsically good.

`LOWER_IS_BETTER` is deliberately not included because no PR7 metric has that unconditional meaning. Average price, DRR, estimated spend, and support per unit are contextual. In particular, lower advertising intensity must never map to good/win/green semantics.

Direction is metadata semantically separate from factual relative position. The smallest PR7 DTO represents those two required concepts as `direction` plus `comparison_position`; it does not add a third performance-interpretation field or enum. The frontend may label “ниже/на уровне/выше медианы”; it must not label PR7 outputs “good”, “bad”, “win”, “loss”, “problem”, or “recommendation”.

The three contracts are frozen separately:

| Concept | PR7 contract | What it may mean |
|---|---|---|
| relative comparison | `ComparisonPosition` | only where own lies against the competitor median |
| metric direction | `MetricDirection` | stable semantic metadata for possible later interpretation |
| performance interpretation | **not calculated and not present in PR7 DTO/API** | PR8+ may combine multiple facts into a verdict under a separately approved contract |

Consequently `ABOVE_BENCHMARK` is not `GOOD`, `BELOW_BENCHMARK` is not `BAD`, and direction does not invert or decorate comparison position. A `CONTEXTUAL` metric can have an available comparison and delta but can never receive an automatic business/performance verdict. The latest plan's generic phrase “performance status” is satisfied by the factual `comparison_position`, while `direction` supplies the separately required metric direction; a third DTO field would add no PR7 information. Diagnostic judgment remains explicitly sequenced to PR8.

## 12. Statistical contract

All values enter analytics as Python `Decimal`; integer source values become `Decimal(integer)`. Binary float is prohibited. Sorting uses exact Decimal ordering. Intermediate median, quantile, derived-advertising, and delta values are not rounded or quantized. API serialization uses canonical non-exponent decimal strings with insignificant trailing fractional zeroes removed (`0` for any decimal zero). Display formatting is a presentation-only `ROUND_HALF_UP` quantization to the precision in section 10 and never feeds calculations.

The competitor sample is a multiset: equal values from distinct members remain separate observations. Exactly one value per member can enter a metric sample. Own value never enters the competitor sample.

## 13. Median contract

For sorted exact values `x[0] <= ... <= x[n-1]`, median is available for `n >= 1`:

```text
odd n:  x[(n - 1) / 2]
even n: (x[n/2 - 1] + x[n/2]) / Decimal(2)
```

The indices above are integer indices. Division is Decimal division. Median at `n=1` is technically valid but does not authorize a comparison/status because section 15 requires three competitors.

## 14. P25/P75 contract

Quartiles use the deterministic Hyndman–Fan **Type 7 linear interpolation** algorithm and are available only for `n >= 4`.

For quantile `p` (`Decimal("0.25")` or `Decimal("0.75")`) and zero-based sorted values:

```text
h = (n - 1) * p
j = floor(h)
g = h - j
Q(p) = x[j] + g * (x[j + 1] - x[j])  when j < n - 1
Q(p) = x[n - 1]                        otherwise
```

`h`, `g`, and interpolation are Decimal operations. Below four observations both `p25` and `p75` are JSON `null`; neither is replaced by median, endpoints, or zero.

## 15. Metric sample size and sufficiency

Thresholds are exact and metric-specific:

| Valid competitor `sample_size` | Median | Delta/position shown | P25/P75 | Confidence |
|---:|---|---|---|---|
| 0 | unavailable | unavailable | unavailable | `INSUFFICIENT` |
| 1–2 | calculated for detail | unavailable | unavailable | `INSUFFICIENT` |
| 3 | calculated | available | unavailable | `LOW` |
| 4 | calculated | available | available | `LOW` |
| 5–9 | calculated | available | available | `MEDIUM` |
| 10+ | calculated | available | available | `HIGH` |

The minimum comparison sample is 3; this prevents one or two selected competitors from looking conclusive while retaining their transparent median in detail. Quartiles require 4 because smaller samples make the interpolated band especially uninformative. There is no hidden global group N.

If own value is unavailable, comparison readiness is unavailable regardless of competitor N. If own is available but N is 1–2, median is returned and the metric state is `INSUFFICIENT_SAMPLE`; delta and position remain `null`.

## 16. Delta contract

PR7 returns one delta only:

```text
absolute_delta = own_value - median
```

It is present only when own value is available and `sample_size >= 3`. Its unit equals the metric unit. For `PERCENTAGE_POINTS`, it is explicitly a percentage-point delta: `4.8 - 6.2 = -1.4` p.p. It is not a relative percent.

No relative delta is calculated or returned for any metric. Therefore no relative zero-denominator behavior exists. A zero median is valid for absolute delta and comparison position.

## 17. Comparison position

`ComparisonPosition` has exactly `BELOW_BENCHMARK`, `WITHIN_BENCHMARK`, `ABOVE_BENCHMARK`, and `UNAVAILABLE`. In PR7 the comparison reference is exactly the median, so these names communicate relative benchmark position without encoding the implementation statistic or a business verdict.

When own value exists and `sample_size >= 3`, compare exact, unrounded Decimal values:

- own `< median` → `BELOW_BENCHMARK`;
- own `== median` → `WITHIN_BENCHMARK`;
- own `> median` → `ABOVE_BENCHMARK`.

Otherwise it is `UNAVAILABLE`. Quartiles are descriptive distribution context and do not alter status. There are no tolerances, color-based success semantics, or thresholds hidden in UI. Direction remains a separate field, so `BELOW_BENCHMARK + CONTEXTUAL` is never interpreted as good.

## 18. Confidence algorithm

`BenchmarkConfidence` is exactly `INSUFFICIENT`, `LOW`, `MEDIUM`, `HIGH`. It is determined solely by the metric-specific compatible, available competitor N according to section 15. This small rule is explainable and avoids a magic score.

Confidence is not a compatibility adjustment. Incompatible observations are removed before N is counted and can never be legalized by `LOW`. Own-value absence forces the metric state to `OWN_VALUE_UNAVAILABLE`, but the response may still expose sample N and its N-derived confidence for transparency; no comparison is shown.

## 19. Advertising Intensity Addendum

PR7 freezes the implementation/API/UI identifiers as `estimated_ad_spend_rub` and `advertising_support_per_ordered_unit_rub`. **PR7 implementation-level advertising names refine the earlier architecture wording. This does not change the underlying analytical formula or layer boundaries.** The earlier descriptive “estimated promotion spend” is not used because existing `ProductSnapshot.promotion_discount_source_value`, `promotion_order_amount_share_pct`, `promotion_days`, and `promotion_window_days` describe promotions/actions, whereas this derivative uses `total_drr_pct` and concerns advertising. Likewise, “sold unit” is not used because the verified denominator source fact is `ordered_units` (“Заказано, штуки”), not bought-out or actually sold units.

The exact Russian UI labels are **`Оценка рекламных расходов`** and **`Рекламная поддержка на заказанную единицу`**. The first label and its estimate marker explicitly disclose derived nature. These identifiers and labels must be used consistently in domain DTOs, analytics, API, tests, frontend, and PR7 documentation; do not mix “promotion spend”, “ad spend”, and “advertising spend” names for this one metric.

For each own or compatible competitor snapshot, use exact existing facts:

```text
estimated_ad_spend_rub
    = ordered_amount_rub * total_drr_pct / Decimal(100)

advertising_support_per_ordered_unit_rub
    = estimated_ad_spend_rub / Decimal(ordered_units)
```

`total_drr_pct` is stored in percentage points, so `7.7` is divided by 100 exactly once in the spend formula. Spend is an **estimate**, not actual Performance advertising spend. The API/UI names and estimate marker are mandatory.

Both derivatives use source facts from the single common own/competitor observation context already selected under sections 7–9. Neither derivative may select a separate generated date or report window because another context has better metric availability.

Support per unit exists only when `ordered_units > 0`. At zero units it is unavailable; there is no division, infinity, denominator substitution, or fake zero. Zero DRR with positive units produces observed derived zero spend and zero support. Negative inputs are not repaired by analytics; current source contract validation prevents them.

Calculations use Decimal without intermediate quantization. Canonical decimal strings are returned by the API; UI rounds both RUB estimates to whole rubles with `ROUND_HALF_UP`. This display rounding never changes samples, medians, quartiles, deltas, or positions.

All three advertising metrics are `CONTEXTUAL`. PR7 provides comparison only. Interpretation alongside position, popularity, traffic, and result belongs to PR8 or later.

## 20. Readiness and result-state model

Top-level `CoreBenchmarkReadiness` has exactly:

- `NO_BENCHMARK`: no set or no current benchmark revision;
- `NO_OWN_SOURCE_DATA`: a current benchmark exists but own has no ProductSnapshot anchor;
- `NO_COMPATIBLE_SAMPLE`: own anchor exists, but all 13 metric competitor sample sizes are zero;
- `INSUFFICIENT_SAMPLE`: at least one metric has N 1–2, but no metric has an available own value and N >= 3;
- `READY`: at least one metric has an available own value and N >= 3. Other metrics may independently be unavailable or insufficient.

Per-metric `MetricReadiness` has exactly:

- `READY`: own exists and N >= 3;
- `INSUFFICIENT_SAMPLE`: own exists and N is 0–2;
- `OWN_VALUE_UNAVAILABLE`: own extraction/derivation is unavailable, regardless of competitor N.

These are successful HTTP 200 analytical states, not exceptions. A `READY` top-level result may contain partial metric readiness. The UI labels that case “частично доступны” without discarding ready metrics.

## 21. Domain DTOs and enums

Create frozen dataclasses/enums in `backend/domain/core_benchmark.py`. Exact logical fields are:

```text
ObservationContext
  report_generated_on: date
  report_window_days: int
  snapshot_id: int
  snapshot_revision: int
  imported_at: datetime

BenchmarkRevisionContext
  benchmark_set_id: int
  benchmark_set_revision_id: int
  benchmark_revision_number: int
  benchmark_member_count: int

CoreBenchmarkMetric
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
  comparison_position: ComparisonPosition
  confidence: BenchmarkConfidence
  exclusion_summary: mapping[
    NO_COMPATIBLE_OBSERVATION | SOURCE_METRIC_UNAVAILABLE | DERIVED_VALUE_UNAVAILABLE,
    int
  ]

CoreBenchmarkResult
  product_id: int
  readiness: CoreBenchmarkReadiness
  benchmark: BenchmarkRevisionContext | None
  observation: ObservationContext | None
  metrics: tuple[CoreBenchmarkMetric, ...]
```

`CoreBenchmarkMetricId` is exactly the ordered 13 keys in section 10. `MetricUnit` is exactly `RUB`, `UNITS`, `COUNT`, `PERCENTAGE_POINTS`, `RUB_PER_ORDERED_UNIT`. `MetricExclusionReason` has exactly the three keys shown above. Other enums are exactly those defined in sections 11 and 15–20. Labels are returned by the backend contract rather than independently redefined in UI.

For `NO_BENCHMARK`, `benchmark`, `observation`, and `metrics` are respectively `null`, `null`, and `[]`. For `NO_OWN_SOURCE_DATA`, benchmark is present, observation is `null`, and metrics is `[]`. Once an own anchor exists, all 13 metrics are returned in catalog order even when unavailable.

`exclusion_summary` is an aggregate analytical explanation, not per-member exclusion history. It always contains the three stable reason keys with non-negative integer counts, including zero counts. For every metric, `sample_size + sum(exclusion_summary.values()) == benchmark_member_count`. `NO_COMPATIBLE_OBSERVATION` means no snapshot at the exact anchor context; `SOURCE_METRIC_UNAVAILABLE` means that observation exists but its nullable source field is absent; `DERIVED_VALUE_UNAVAILABLE` means compatible source facts exist but the derived value is invalid (for example support per unit when `ordered_units == 0`). Exclusion never creates a zero, removes a member from the revision, creates a new revision, or changes a source snapshot. PR7 deliberately does not add per-member exclusion DTO/history: aggregate counts explain why composition N differs from metric N and the approved Benchmark Detail CJM does not require a second member-by-metric audit product.

## 22. Persistence read requirements

No migration is required. Modify `ProductSnapshotRepository` with two PR7-needed reads:

```text
find_latest_current_for_product(product_id) -> ProductSnapshot | None
list_current_for_products_at_context(
    product_ids,
    report_generated_on,
    report_window_days,
) -> dict[int, ProductSnapshot]
```

The first implements section 8's explicit two-step rule: select the logical observation context using only `report_generated_on DESC, report_window_days DESC`, then select the maximum revision inside that key. It must not use `imported_at`, database `id`, INSERT/import order, or SQLite natural order to select the anchor. The second returns at most one maximum-revision row per requested product at exact equality context. It must safely handle an empty input without malformed SQL, parameterize every value, deduplicate requested IDs, and not return unrequested products. Chunking is unnecessary for current benchmark sizes unless existing SQLite parameter limits require a small repository-local implementation detail; this does not justify a generic repository.

These methods resolve revision history inside persistence and return only current domain observations. Neither the application service nor `backend/analytics/core_benchmark.py` receives all historical rows, groups revisions, inspects `supersedes_snapshot_id`, or decides which revision is current. Repository tests own detailed `rev1 -> rev2` resolution coverage; service/analytics tests consume the resolved current inputs at their own layer.

Reuse `BenchmarkSelectionRepository.get_benchmark()` and `ProductRepository.get_product()`. The existing benchmark read model continues to resolve `BenchmarkMember.ozon_product_id` by joining the member's `product_id` to canonical `ProductExternalIdentity`; no benchmark identity value is newly persisted. Analytics receives mapped domain objects, never a SQLite connection, raw rows, or superseded revision history. No SQL is added to application, analytics, route, or frontend code.

## 23. Analytics module boundary

A new `backend/analytics/` package is justified now because PR7 is the first derived analytical feature and must not live in routes, repositories, or UI:

```text
backend/analytics/__init__.py
backend/analytics/core_benchmark.py
```

`core_benchmark.py` is one feature-specific pure module. It accepts the already-resolved current own snapshot, benchmark revision/member identities, and a mapping of already-resolved current exact-context competitor snapshots; it returns the domain result/metrics. It owns the frozen catalog, extraction/derivation, median, Type-7 quartiles, sample formation, delta, position, and confidence. It does not load or resolve snapshot history. Small private pure helpers are allowed. It must not know FastAPI, SQLite, files, HTML, MPStats, credentials, or transaction management.

This package is not a generic analytics framework. No public generic metric definition, registry, engine, repository, configuration DSL, or universal result is introduced.

## 24. Application service contract

Create `CoreBenchmarkService(db_path)` in `backend/application/core_benchmark.py` with one public method:

```text
get_core_benchmark(product_id: int) -> CoreBenchmarkResult
```

It opens one ordinary read transaction, validates product existence/ownership, loads current composition, resolves the own anchor and exact-context competitor observations, and delegates calculation to pure analytics. It maps normal missing analytical inputs to readiness results and does not mutate state. `ProductNotFound` and the existing `ProductNotOwnedError` propagate for route mapping. Unexpected database/programming failures remain exceptional and must not be sanitized into no-data readiness.

## 25. REST API contract

### Request

```http
GET /api/products/{product_id}/core-benchmark
```

`product_id` is FastAPI `Path(gt=0)`. There are no query parameters, request body, credentials, historical-revision selector, pagination, or per-metric endpoints. GET performs no mutation.

### Successful analytical response

HTTP 200, JSON keys exactly:

```json
{
  "product_id": 41,
  "readiness": "READY",
  "benchmark": {
    "benchmark_set_id": 7,
    "benchmark_set_revision_id": 12,
    "benchmark_revision_number": 3,
    "benchmark_member_count": 10
  },
  "observation": {
    "report_generated_on": "2026-08-23",
    "report_window_days": 7,
    "snapshot_id": 101,
    "snapshot_revision": 2,
    "imported_at": "2026-08-24T10:15:00+00:00"
  },
  "metrics": [
    {
      "metric_id": "impression_to_order_pct",
      "label": "Конверсия из показа в заказ",
      "unit": "PERCENTAGE_POINTS",
      "direction": "HIGHER_IS_BETTER",
      "is_estimate": false,
      "readiness": "READY",
      "own_value": "4.8",
      "median": "6.2",
      "p25": "5.1",
      "p75": "7.4",
      "absolute_delta": "-1.4",
      "sample_size": 7,
      "comparison_position": "BELOW_BENCHMARK",
      "confidence": "MEDIUM",
      "exclusion_summary": {
        "NO_COMPATIBLE_OBSERVATION": 2,
        "SOURCE_METRIC_UNAVAILABLE": 1,
        "DERIVED_VALUE_UNAVAILABLE": 0
      }
    }
  ]
}
```

The example abbreviates `metrics`; an actual anchored response contains all 13 metrics. It does not return per-member values or exclusions. Every Decimal, including integer-valued metric values and statistics, is a canonical JSON string. IDs, revisions, windows, sample sizes, member counts, and exclusion counts are JSON integers. Dates/datetimes are ISO 8601; datetimes retain timezone offset. Unavailable numeric fields are JSON `null`, never `""`, zero, `NaN`, or infinity.

Readiness response shapes follow section 21 with the same top-level keys. HTTP 200 is used for all five analytical readiness values.

## 26. Error taxonomy

Only exceptional product boundary errors are PR7-specific route mappings:

| Condition | HTTP | Exact envelope |
|---|---:|---|
| product absent | 404 | `{"error":{"code":"PRODUCT_NOT_FOUND","message":"Товар не найден."}}` |
| product exists but is not owned | 409 | `{"error":{"code":"PRODUCT_NOT_OWNED","message":"Выберите свой товар из каталога."}}` |
| `product_id <= 0` or malformed | 422 | existing FastAPI validation `detail` envelope |

The first two reuse current PR6 exception types/messages. There is no `NO_BENCHMARK` HTTP error. Unexpected persistence or programming errors remain HTTP 500 through the current application policy; stack traces and database details must not be added to the JSON response or UI message.

## 27. Frontend / Benchmark Detail CJM

The future PR7 UI extends the existing competitor workspace, using the established visual tokens and classic committed assets. For the currently selected owned SKU:

1. A `Benchmark details` control is visible near the current saved benchmark summary.
2. Opening it starts a visible loading state and fetches the single endpoint.
3. The panel shows the exact observation phrase and benchmark revision/member context.
4. In catalog order, every anchored metric row shows label, own, median, P25/P75 when non-null, absolute delta, metric-specific `N`, comparison position, confidence, and unit-correct formatting.
5. When `N` is smaller than benchmark member count, an accessible disclosure shows aggregate exclusion counts with human labels `Нет совместимого наблюдения`, `Нет исходного значения показателя`, and `Нельзя вычислить производный показатель`. It does not require a per-member exclusion list.
6. Reload after composition save refetches; no stale result is retained against a new revision.

The existing composition UI remains the member-identity surface. If this panel also displays competitor presentation metadata, it may use only persisted ProductSnapshot source-observation title/seller/brand/URL and must fall back to canonical Ozon product ID (then internal `product_id`) when absent. Those presentation values are not canonical identity, never enter matching, merging, membership, or metric calculation, and no transient candidate state is used to rebuild them.

Required visible states:

- loading: `Рассчитываем benchmark…`;
- `NO_BENCHMARK`: `Сначала сохраните benchmark-группу.` plus the existing composition action;
- `NO_OWN_SOURCE_DATA`: `Нет товарных данных Ozon для собственного SKU. Импортируйте отчёт «Товары на Ozon».`;
- `NO_COMPATIBLE_SAMPLE`: `У конкурентов нет данных за тот же контекст отчёта.`;
- `INSUFFICIENT_SAMPLE`: `Совместимых конкурентов недостаточно для сравнения.` while transparently showing available N/median details;
- `READY`: metrics, with `Часть показателей недоступна` when any metric is non-ready;
- failed request: `Не удалось загрузить benchmark. Повторите попытку.` and a retry control.

Null quartiles/delta render as em dash with an explanatory unavailable label, never `0`. Confidence and N are textual, not color-only. Estimates carry `Оценка`; p.p. deltas carry `п.п.`. Contextual rows use neutral visual semantics. No diagnostic phrase such as “problem”, “weak card”, “improve offer”, or recommendation is introduced.

## 28. Freshness and period display

The own observation header uses exactly:

```text
{report_window_days} дней · отчёт сформирован {DD.MM.YYYY}
```

Competitor detail uses the same business context and may separately say `импортировано {DD.MM.YYYY HH:mm}` from `imported_at`. Import time never substitutes for freshness. Snapshot revision may be shown as technical detail, not as a period. No start/end date is calculated or displayed.

## 29. Exact proposed implementation file map

Only the future implementation PR may touch these files:

| Change | File | Responsibility / reason |
|---|---|---|
| NEW | `backend/domain/core_benchmark.py` | Frozen PR7 DTOs/enums; keeps analytics/API contract out of routes. |
| NEW | `backend/analytics/__init__.py` | Marks the first feature-specific derived analytics package; contains no framework. |
| NEW | `backend/analytics/core_benchmark.py` | Pure catalog, sample, statistics, advertising derivation, status, and confidence. |
| NEW | `backend/application/core_benchmark.py` | Read-only orchestration and analytical readiness. |
| MODIFY | `backend/persistence/repositories/product_snapshots.py` | Add latest-own and exact-context current-revision reads; SQL stays in persistence. |
| MODIFY | `backend/main.py` | One thin GET route and existing error mapping/serialization style. |
| MODIFY | `frontend/index.html` | Benchmark Detail control/panel and semantic state containers. |
| MODIFY | `frontend/assets/js/app.js` | Fetch, render, formatting, disclosures, state transitions, revision refresh. |
| MODIFY | `frontend/assets/css/app.css` | Benchmark Detail layout using existing tokens; no new design language. |
| NEW | `tests/test_core_benchmark_analytics.py` | Pure metric/statistical/advertising contracts. |
| NEW | `tests/test_core_benchmark_service.py` | Selection, compatibility, revision, readiness, and immutability orchestration. |
| NEW | `tests/test_core_benchmark_api.py` | Exact endpoint JSON/enums/errors/Decimal serialization. |
| MODIFY | `tests/test_product_snapshot_repository.py` | Exact repository current-revision/context read behavior. |
| MODIFY | `tests/test_frontend_contract.py` | Committed UI controls, states, labels, null handling, and no-diagnostics guards. |
| MODIFY | `tests/windows_smoke.ps1` | Minimal synthetic PR7 endpoint reachability in the portable runtime. |

`competitor_state.js` is not modified: its responsibility is race-safe PR6 relevance/composition loading, while PR7 benchmark detail is a downstream view coordinated by `app.js`. No migration/migration test, dependency, source adapter, or Implementation Plan file is part of the map.

## 30. Migration decision

**No migration and no schema change.** ProductSnapshot facts and revisions already exist; benchmark composition and revisions already exist; the PR7 result is derived on request. Persisting it would duplicate source history and create an unsupported historical-results product. No cache need is demonstrated.

## 31. Required automated-test matrix

### Existing invariant coverage

Keep the existing PR1–PR6 CI coverage for general `Product` identity, canonical `ProductExternalIdentity` uniqueness, ProductSnapshot revision semantics, and benchmark-membership integrity. If those tests already prove a general invariant (for example that equal presentation metadata does not establish Product identity), PR7 reuses that guarantee instead of mechanically duplicating the same scenario under a PR7 test filename. New tests below must add PR7 feature or layer-boundary value.

### Statistics

- median odd N and even N, including exact fractional even median;
- N=1 median exists but comparison is unavailable;
- Decimal inputs and outputs never instantiate/use binary float;
- Type-7 P25/P75 exact examples for N=4, N=5, and repeated/boundary values;
- quartiles null at N=0–3 and available at N=4;
- canonical decimal serialization and display-independent precision/no drift.

### Metric samples

- benchmark member count greater than each metric N;
- nullable buyout removes only that member from buyout;
- zero ordered units removes only support-per-unit, not spend/DRR/sales;
- missing one metric never removes a competitor from other metrics;
- own value is never included in competitor sample;
- equal competitor values remain distinct observations;
- sample size plus all aggregate exclusion counts exactly equals revision composition for every metric;
- compatible nullable source absence is counted as `SOURCE_METRIC_UNAVAILABLE`, while a zero denominator for support per unit is counted as `DERIVED_VALUE_UNAVAILABLE`; neither becomes zero.

### Compatibility and selection

- exact equal generated date + report window accepted;
- different generated date rejected;
- different report window rejected;
- latest incompatible competitor snapshot not silently selected;
- when a competitor's overall latest snapshot is incompatible but an older-date logical key exactly matches the own anchor, the current revision at that exact matching key is used; the newer incompatible key neither replaces nor suppresses it;
- competitor `2026-08-23 / 7 days / revision 1` and revision 2 at the exact own `2026-08-23 / 7 days` context uses only revision 2; revision 1 is superseded, not an “older compatible observation” fallback;
- competitor observations `2026-08-24 / 7 days` and `2026-08-23 / 28 days` against own `2026-08-23 / 7 days` yield `NO_COMPATIBLE_OBSERVATION`, never nearest/latest fallback;
- latest own current observation ordering includes deterministic same-date window tie;
- own-anchor cases A–E in section 8, including same-date 7/28-day choice and freshest-date-before-window precedence;
- with own `D / 7 days` and `D / 28 days`, revision A having more compatible 7-day members and revision B having more compatible 28-day members both select the same own-only anchor required by section 8;
- when the 7-day context has more sales availability and the 28-day context has more conversion availability, every metric still uses the one common own anchor; metric availability cannot select per-metric contexts;
- import-order independence: importing the same source-observation set in different file, batch, and INSERT orders produces the same analytical anchor;
- database-ID independence: different insertion orders that assign different snapshot IDs produce the same analytical anchor;
- shuffled repository return order and different `imported_at` values cannot change the declared own-anchor policy;
- correction semantics: a later-imported higher revision with the same `report_generated_on` and `report_window_days` is used as current while the anchor date/window remains unchanged;
- multiple revisions do not multiply anchors: `D / 7 days / revision 1`, `D / 7 days / revision 2`, and `D / 28 days / revision 1` form exactly two logical anchor candidates;
- correction does not create a new observation context: correcting `D / 7 days / revision 1` to revision 2 preserves one logical context and changes only its current revision;
- import timestamp independence: identical logical observation histories with different `imported_at` values select the same analytical context and produce the same benchmark semantics;
- late correction changes the selected current revision but does not change business context or derive a new `report_generated_on` from its later `imported_at`;
- no inferred `period_start`/`period_end` fields or date range in DTO/API/UI;
- empty member lookup is valid and no nearest-date/tolerance/averaging path exists.

### Revisions and source purity

- repository tests prove the highest current ProductSnapshot correction is returned for own and competitor exact logical contexts;
- service/integration coverage proves the repository-resolved current revision is used and a superseded revision never reaches calculation as current or a second sample value;
- pure Core Benchmark unit tests use clean current inputs and do not recreate persistence revision-history resolution;
- saving a new current benchmark revision changes composition and calculated result;
- old benchmark revision/member rows remain unchanged;
- calculation leaves all snapshot payload/revision/lineage rows byte-for-byte unchanged;
- repeated GET creates no database rows.

### Own source and readiness

- no benchmark set and set-without-current-revision → `NO_BENCHMARK`;
- current benchmark but no own ProductSnapshot → `NO_OWN_SOURCE_DATA`;
- own nullable buyout unavailable while other metrics calculate;
- own zero units makes only support own value unavailable;
- own context with all members incompatible → `NO_COMPATIBLE_SAMPLE`;
- some N=1/2 and no ready metric → `INSUFFICIENT_SAMPLE`;
- one ready metric plus partial metrics → top-level `READY`.

### Advertising intensity

- DRR `7.7` uses `7.7 / 100`, not `7.7` or `0.077 / 100`;
- exact spend formula and support-per-unit formula;
- `estimated_ad_spend_rub` uses `total_drr_pct`; no `promotion_*` field participates or acts as fallback;
- the frozen identifiers and Russian labels are consistent across domain DTO, analytics, API, tests, frontend, and documentation, without `promotion spend`/`sold unit` aliases;
- support denominator is `ordered_units`, with no sold/bought-out-unit substitute or terminology;
- zero units unavailable without exception/infinity/fake zero;
- with `ordered_units == 0` and `total_drr_pct > 0`, estimated spend remains derivable while support per unit is unavailable and its exclusion reason is `DERIVED_VALUE_UNAVAILABLE`;
- zero DRR with positive units yields exact zeros;
- repeating Decimal division retains internal precision and canonical API text;
- all advertising direction values are `CONTEXTUAL` and never produce GOOD/BAD/WIN labels.

### Candidate/source separation and membership authority

- `BenchmarkCandidate.contextual_price_rub`, Search Visibility rank/date/title/seller evidence, frontend candidate state, and MPStats previews never enter analytics dependencies or values;
- absent compatible `ProductSnapshot` has no candidate/Search Visibility fallback;
- a manually added saved member without any ProductSnapshot remains in composition and is reported as `NO_COMPATIBLE_OBSERVATION` for every metric;
- that manual member is not deleted and does not enter any ProductSnapshot metric sample; its stable presentation fallback is Ozon product ID when the UI shows it;
- brand/category/title/price/photo/seller mismatch never removes or reranks a saved member;
- persisted ProductSnapshot title/seller/brand/URL may be used only as presentation labels, while candidate metadata remains forbidden as an analytical fallback;
- one PR7-specific regression changes a saved member's title, seller, and brand presentation metadata and proves its `BenchmarkMember.product_id`, benchmark composition, and resolved Product remain unchanged, with no merge or reselection;
- `BenchmarkMember.ozon_product_id` is resolved through the Product's canonical Ozon `ProductExternalIdentity`, while schema/repository assertions prove no external ID is duplicated in benchmark persistence;
- Core Benchmark contains no matching fallback based on title, brand plus seller, URL similarity, or other presentation metadata;
- runtime metric exclusion neither changes current `BenchmarkSetRevision` nor creates a new revision;
- `benchmark_member_count` may exceed each independently calculated `sample_size`, and the three aggregate exclusion counts explain the difference without a per-member exclusion DTO.

### Confidence, position, delta, and boundaries

- N=0,1,2 → `INSUFFICIENT`; N=3,4 → `LOW`; N=5,9 → `MEDIUM`; N=10 → `HIGH`;
- comparison boundary at N=2/3 and quartile boundary at N=3/4;
- exact own below/equal/above median yields `BELOW_BENCHMARK`/`WITHIN_BENCHMARK`/`ABOVE_BENCHMARK`;
- unavailable own or N<3 yields `UNAVAILABLE` position/null delta;
- percentage-point absolute delta is p.p.; zero median works;
- no relative-delta field and no direction-based status inversion.
- `ABOVE_BENCHMARK` does not create positive performance interpretation;
- every `CONTEXTUAL` metric can return relative position but never automatic GOOD/BAD interpretation.

### Stable catalog and ordering

- the exact 13 `metric_id` strings and numeric catalog order are stable in analytics, DTO, API, and UI;
- changing a Russian label cannot change metric identity or result lookup;
- `metrics[]` order is independent of dict/set/SQLite order;
- statistical median/quantiles use numeric Decimal sort, so identity ordering and equal-value ties cannot change results.

### Repository and application service

- repository methods parameterize and restrict requested product IDs/context;
- current revision per exact logical key and stable latest-own ordering;
- repositories, not analytics, resolve current revisions; analytics is not passed superseded history;
- application uses one read boundary, never mutates, and passes domain objects to analytics;
- product missing/non-owned exceptions remain distinct;
- unexpected SQLite error is not mapped to analytical no-data.

### API

- exact all-13-metric success JSON, ordering, enum strings, labels, units, estimate flags, and canonical Decimal strings;
- exact response for every readiness state and benchmark revision context fields;
- exact three-key aggregate exclusion-summary shape and member-count accounting;
- invalid path 422, missing 404 exact envelope, non-owned 409 exact envelope;
- GET has no body/query mutation and repeated requests are stable.

### Frontend contract

- detail control/panel and all seven visible states exist;
- N, confidence, revision, period phrase, direction-neutral comparison, and aggregate exclusion disclosures render;
- unavailable quartiles/delta render no fake zero;
- partial metrics render independently;
- percentage points, RUB, counts, units, and RUB/unit format correctly;
- estimates are marked and contextual advertising has no favorable/unfavorable color claim;
- no PR8 diagnostic/recommendation wording, framework/npm asset, or invented period range is introduced.

### Architecture guards

- static/import tests keep SQLite out of analytics/routes and FastAPI/SQLite/MPStats out of pure analytics;
- calculation dependency graph contains ProductSnapshot + current BenchmarkSetRevision only, not MPStats sales estimates, query/search-position facts, or future AdvertisingSnapshot;
- repository/schema assertions prove no `BenchmarkSnapshot`, benchmark-result table, generic benchmark persistence, or migration was added;
- source snapshots remain immutable and missing values are never normalized to zero.

Existing PR1–PR6 tests remain mandatory and unchanged in meaning.

## 32. Windows and CI acceptance

Extend the existing Windows smoke minimally. Its synthetic DB setup creates an owned product and one competitor with exact-context current ProductSnapshot facts plus a current benchmark revision, starts the existing portable app, calls `GET /api/products/{id}/core-benchmark`, and asserts HTTP 200, the expected revision ID, `READY`, and one known exact metric/advertising value. It also retains the existing missing-product/portable startup checks.

The Windows smoke must not test median/quantile/confidence matrices; those belong to Python unit/integration tests. Linux CI runs the full Python suite, frontend contract tests, JavaScript syntax/contracts already present, `git diff --check`, and any existing architecture/runtime checks. GitHub Actions remains authoritative for Windows portable acceptance.

## 33. Security and provenance invariants

- Backend remains bound to `127.0.0.1`; endpoint is same-origin read-only GET with no permissive CORS.
- No credentials, tokens, URLs carrying secrets, source files, raw workbook content, or local artifact paths enter request/response/logs.
- Existing trusted-local no-auth profile is unchanged; no login/session/CSRF/TLS/LAN layer is added.
- Response identifies concrete benchmark revision and current snapshot observation/revision/import context.
- Analytics never mutates, clamps, corrects, interpolates, or persists source facts/results.
- Ozon ProductSnapshot is the only metric source. MPStats remains absent from numerical benchmark calculation.
- Decimal calculation and explicit units preserve factual semantics; estimate labels preserve derived-fact provenance.

## 34. Mandatory pre-commit self-review

Before an implementation commit, review the diff and answer all of these affirmatively:

- **Layer contamination:** no `BenchmarkCandidate`, Search Visibility candidate value, frontend selection metadata, or MPStats preview is used as a Core Benchmark source fact.
- **Common anchor:** one response uses exactly one own ProductSnapshot context for every PR7 product-level source and derived metric, with no `SHOULD`, optional fallback, or metric-specific escape hatch.
- **Anchor purity / technical-order independence:** own-anchor selection reads only own ProductSnapshot business observation keys and cannot change with benchmark composition, competitor sample, metric availability, confidence, result statistics, `imported_at`, database ID, INSERT/import order, or SQLite/repository return order.
- **Revision purity:** exact observation-context selection is completed before choosing its current revision; a later correction changes the current revision but not the business observation context, and an older compatible logical context is not confused with a superseded revision of that context.
- **Revision responsibility:** `ProductSnapshotRepository` resolves current revisions and supplies only current feature inputs; Core Benchmark analytics never loads, groups, or inspects superseded revision history.
- **Semantic contamination:** no mapping equates above with good, below with bad, or lower DRR/ad support with good; PR7 exposes no performance-verdict field.
- **DTO YAGNI:** `comparison_position` plus `direction` preserve the required distinction without a redundant performance-interpretation field/enum.
- **Explainability YAGNI:** the aggregate three-reason exclusion summary accounts for member count versus sample size without per-member exclusion history.
- **Presentation/identity/source separation:** candidate/transient metadata is never a metric input; persisted ProductSnapshot title/seller/brand/URL is presentation metadata only; `Product.id` is canonical internal identity, and canonical `ProductExternalIdentity` carrying `ozon_product_id` is authoritative Ozon external identity. Title/brand/seller neither establish nor change identity, while presentation values may still be displayed.
- **Identity persistence:** `benchmark_members` still persists membership only through `product_id`; read-model `BenchmarkMember.ozon_product_id` is resolved from canonical `ProductExternalIdentity`, with no duplicate benchmark column, identity table, or source of truth.
- **Identity regression/coverage:** changing title, seller, or brand leaves saved `product_id` membership and Core Benchmark resolution unchanged, while general identity invariants already covered by PR1–PR6 are not duplicated without PR7-specific value.
- **Temporal ambiguity:** same-date multiple windows deterministically select the longest current window after selecting the freshest generated date, exactly as section 8 cases A–E require.
- **Naming ambiguity:** advertising is not called promotion; the estimate is `estimated_ad_spend_rub`; ordered units are never called sold units.
- **Responsibility boundary:** `BenchmarkSelectionService` remains PR6 composition orchestration; derived analytics lives in the separate `CoreBenchmarkService` and pure feature module.
- **User-context integrity:** analytics respects every saved member and filters only at runtime for exact observation compatibility or metric availability without mutating composition.
- **Ordering:** metric response order and numeric statistical order follow their separate explicit contracts; aggregate exclusion counts do not depend on member insertion order.
- **Scope:** no PR8 diagnostics, automatic competitor scoring, generic framework, query/cluster benchmark, new adapter, historical UI/result persistence, `BenchmarkSnapshot`, `AdvertisingSnapshot`, or MPStats sales benchmark appears.

## 35. Implementation acceptance criteria / Definition of Done

PR7 implementation is complete only when:

- all 13 catalog metrics and no others follow their frozen source, unit, direction, estimate, and display contracts;
- exact own-anchor/current-revision/exact-context selection is implemented without invented periods or fallback;
- metric-specific samples, Decimal median, Type-7 quartiles, thresholds, absolute delta, comparison position, and confidence exactly match this spec;
- advertising calculations and zero-denominator semantics exactly match section 19 and remain contextual;
- every normal no-data case returns the exact first-class readiness shape over HTTP 200, while product errors match section 26;
- every response retains concrete benchmark and observation revision context and aggregate exclusion counts account for every member per metric;
- the endpoint, UI states, disclosure details, labels, precision, neutral semantics, and freshness phrase match this spec and the Visual Design System;
- SQL exists only in repositories, pure analytics has no infrastructure dependency, handlers contain no business logic, and no generic engine is introduced;
- no migration, result persistence, dependency, source adapter, PR8+ behavior, or implementation-plan document appears;
- the complete matrix in section 31 and all existing PR1–PR6 checks pass in applicable CI environments; the minimal Windows smoke passes in authoritative Windows CI;
- diff/self-review confirms no source fact is changed and no real reports, database, credentials, or sensitive logs are committed.

## 36. Implementation-plan handoff boundary

This document freezes what PR7 must build; it intentionally contains no task/commit sequence. After independent review and explicit approval, a **separate PR7 Implementation Plan** may translate these contracts into dependency-ordered TDD work. That plan must not reopen metric selection, compatibility, formulas, statistics, thresholds, DTO/API shapes, UI states, or file boundaries without a separately approved spec amendment.

The plan author must treat these answers as closed:

| Question | Frozen answer |
|---|---|
| Can `BenchmarkSetRevision`, compatible N, metric availability, confidence, or benchmark result influence the own anchor? | **No.** The anchor is selected from own ProductSnapshot history only. |
| Can each metric select a different own observation window? | **No.** One response has one common own anchor. |
| How many own ProductSnapshot contexts can one Core Benchmark response use? | **Exactly one.** |
| Can `imported_at`, database ID, INSERT/import order, or SQLite natural order select the analytical anchor? | **No.** Only `report_generated_on` and `report_window_days` select the logical observation. |
| Are revision 1 and revision 2 of the same date/window two anchor candidates? | **No.** Candidates are distinct logical ProductSnapshot observation contexts, not revision rows. |
| When is revision selected, and which revision is used? | **After** logical observation-context selection; use the current revision of the selected context. |
| Can `imported_at` define business freshness? Can it remain visible? | **No** to business freshness; **yes** as separate provenance/application metadata and technical import/update time. |
| Is a later correction selected? Does it change the business context? | **Yes**, as the current revision of the same logical observation; **no**, it does not change its date/window context. |
| Can a late correction change `report_generated_on` by itself? | **No.** A later `imported_at` changes neither the source-provided report date nor window. |
| Can Search Visibility/candidate price enter Core Benchmark? | **No.** |
| Can persisted ProductSnapshot title/seller/brand/URL label a competitor in the UI? | **Yes, for presentation only**, never as a mathematical input. |
| What is canonical internal Product identity? | `Product.id`. Relationships such as `BenchmarkMember.product_id` refer to it. |
| What is authoritative Ozon external identity? | The canonical `ProductExternalIdentity` carrying `ozon_product_id` for the corresponding internal Product. |
| Is `BenchmarkMember.ozon_product_id` persisted in benchmark composition? | **No.** It is a read-model projection resolved from canonical `ProductExternalIdentity`; `benchmark_members` persists `product_id`. |
| Can title, brand, or seller establish Product identity? Can they appear in Benchmark Detail? | **No** to identity; **yes** as persisted source presentation metadata when available. |
| Can presentation metadata changes alter membership or cause Core Benchmark reselection/merge? | **No.** Membership remains the saved `product_id`, and matching never falls back to title, seller, brand, or URL. |
| Can PR7 remove a saved member for brand/category/title or other similarity concerns? | **No.** |
| Is a manual member without ProductSnapshot removed or sampled? | **Neither:** it remains in composition, is excluded from ProductSnapshot samples, and may display by Ozon ID. |
| What is the product-level metric source? | The current revision of an exact-context canonical `ProductSnapshot`. |
| Can generic latest competitor snapshot be used? | Only when its logical key happens to equal the exact anchor; lookup is by exact context, never by generic latest/fallback. |
| If a newer incompatible competitor context and an older exact-compatible context exist? | Use the **current revision of the exact-compatible context**. |
| Can a superseded revision at that exact-compatible context be used? | **No.** |
| Does Core Benchmark analytics load or resolve superseded revision history? | **No.** Persistence resolves the current revision and analytics receives clean current inputs. |
| Same generated date has 7- and 28-day own observations? | Choose the current 28-day observation under the same-date longest-window rule. |
| Does `ABOVE_BENCHMARK` mean `GOOD`? | **No.** It states position only. |
| Can a contextual metric receive an automatic business verdict? | **No.** |
| Are three fields for relative position, direction, and interpretation mandatory? | **No.** PR7 uses factual `comparison_position` plus `direction` and has no interpretation field. |
| Is estimated ad spend observed spend? | **No.** It is the labeled estimate `ordered_amount_rub * total_drr_pct / 100`. |
| Why not `estimated_promotion_spend`? | It would conflate advertising derived from `total_drr_pct` with ProductSnapshot promotions/actions. |
| Advertising-support denominator? | `ordered_units`, only when greater than zero. |
| Why “ordered unit” rather than “sold unit”? | The verified source fact is `ordered_units`; PR7 has no verified sold-unit denominator. |
| Does `BenchmarkSelectionService` calculate analytics? | **No.** Separate `CoreBenchmarkService` owns orchestration. |
| Can metric sample N be smaller than saved member count? | **Yes, independently per metric**, with aggregate reason counts explaining every exclusion. |
| Is a per-member exclusion list mandatory? | **No.** The PR7 MVP returns only the aggregate three-reason summary. |

Work stops at this spec in the current task. PR7 production implementation and PR8 design/implementation must not begin here.
