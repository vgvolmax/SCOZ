# Ozon Search Queries Market Metrics XLSX — Source Contract v1

**Status:** Approved factual source contract v1

**Date:** 2026-08-19

**Scope:** only the verified Ozon market-level search-query XLSX shape supplied as `queries_report`; this contract covers the PR5 source for `QueryMetricSnapshot` only and does not replace or modify the already approved `seller-queries` contract for `ProductQuerySnapshot`

## 1. Authority, source scope, and evidence provenance

This contract freezes source facts established by direct inspection of one user-supplied Ozon workbook. The workbook is sensitive user input and is **not stored, copied into fixtures, or committed to this public repository**. Only structural, package-level, and semantic facts required for a deterministic adapter are documented here.

Canonical SCOZ report type for this source family:

`OZON_QUERY_METRICS`

Future XLSX import kind:

`ozon_query_metrics_xlsx`

Evidence workbook:

- evidence filename: `queries_report-2026-08-19_07_31.xlsx`;
- SHA-256: `34b00595a3eb96e62bd7d3ca5e1f88a2c004f1b9251fe0400889c5a12ea8500b`;
- byte size: `811405`;
- one worksheet named `Поисковые запросы`;
- actual populated business range: A1:K10004;
- 10,000 query observation rows at rows 5–10004;
- no formula cells;
- no merged cells;
- source period: `23.07.2026 - 19.08.2026`;
- source sort context: `По убыванию в Популярность запроса`;
- first observed popularity value: `867550`;
- last observed popularity value: `11845`;
- popularity is monotonically non-increasing across the 10,000 evidence rows;
- all 10,000 evidence query texts are distinct;
- 35 evidence queries consist only of decimal digits and are still query text, not Product/SKU identity.

Filename and worksheet name are evidence metadata only. Report detection must not depend on filename, date/time fragments embedded in the filename, worksheet name, or fuzzy similarity.

The workbook itself contains no trustworthy source-generated timestamp. `2026-08-19_07_31` from the filename must not be promoted to `generated_at` or observation time.

## 2. PR5 source boundary

PR5 intentionally has two different source families:

1. own-product query history → `ProductQuerySnapshot` — covered by `2026-08-18-ozon-seller-queries-xlsx-source-contract-v1.md`;
2. market-level query Demand/Quality → `QueryMetricSnapshot` — this contract.

This workbook contains **no Product/SKU dimension and no Cluster dimension**.

Therefore:

- it must not create `ProductQuerySnapshot`;
- it must not create `SearchVisibilitySnapshot`;
- it must not infer Product ownership;
- it must not attach a market query metric to a Product merely because a later own-product report contains the same query;
- market conversion from this report must never be exposed as own-product conversion or competitor conversion.

The shared link between source families is the canonical `SearchQuery` identity only.

## 3. Important package-level quirks in the verified Ozon export

The evidence workbook contains two non-business XLSX package quirks that a future adapter must tolerate.

### 3.1. Incorrect worksheet dimension metadata

`xl/worksheets/sheet1.xml` declares:

`<dimension ref="A1">`

despite actual business cells extending through K10004.

Therefore a parser must **not trust the stored worksheet dimension as authoritative coverage**. It must determine actual populated bounds from cells/rows or otherwise recalculate dimensions before applying row/column logic.

Rejecting this verified Ozon export merely because its stored dimension says `A1` is incorrect.

### 3.2. Non-canonical alignment values in styles.xml

The evidence `xl/styles.xml` contains alignment values:

- `horizontal="Right"` in 34 alignment definitions;
- `horizontal="Left"` in 12 alignment definitions.

These capitalized values are non-canonical for strict OOXML consumers. In the currently pinned `openpyxl 3.1.5`, loading this original workbook directly fails while parsing styles because the library expects lowercase alignment enum values such as `right` and `left`.

This is a **non-semantic style-package issue**, not invalid business data.

A future implementation must tolerate this verified Ozon-produced package shape without mutating business values. The exact remediation mechanism belongs to the PR5 Implementation Spec, but it must satisfy all of the following:

- never rewrite the user's original evidence/upload in place;
- only normalize or bypass non-business package metadata needed to read the workbook;
- preserve business cells exactly;
- preserve the original uploaded artifact for provenance/archive;
- do not classify this evidence file as `WRONG_REPORT_TYPE` or `UNSUPPORTED_WORKBOOK` solely because of the style capitalization;
- do not trust the incorrect stored dimension after package compatibility handling.

No generic "repair arbitrary corrupt XLSX" framework is implied. Support is limited to verified source-compatible handling required for this report family.

## 4. Physical versus semantic columns

Business columns are A:K only.

The evidence contains no business cells in L onward.

V1 semantic boundary is therefore A:K. Empty/style-only physical content outside K may be tolerated, but any non-empty business value in L onward is incompatible with this exact source shape.

No business meaning is inferred from formatting, color, alignment, width, row height, worksheet name, or sort styling.

## 5. Exact workbook structure

The sole worksheet has this semantic layout:

| Row | Contract |
|---|---|
| 1 | A1 matches `Период: DD.MM.YYYY - DD.MM.YYYY`; B:K semantically blank |
| 2 | A2 is the exact supported sort context `Сортировка: По убыванию в Популярность запроса`; B:K semantically blank |
| 3 | A:K is the exact ordered header signature in section 6 |
| 4 | source explanatory/help row; never an observation |
| 5 onward | market-query observation candidates |

Semantic blank means Excel `None` or exact zero-length text `""`. Whitespace-only text is not semantically blank.

The evidence contains no report-level declared row count. Therefore there is no declared-count reconciliation analogous to PR4 Search Visibility.

Every row at row 5 or later with any semantically non-blank A:K value is a query-row candidate. Completely semantically blank trailing rows are ignored.

The evidence contains exactly 10,000 candidate rows, but **10,000 is not a required v1 row count** because the workbook does not declare that count as a completeness contract.

## 6. Exact A:K ordered header signature

Row 3 A:K must equal, in order:

1. `Запрос`
2. `Популярность запроса`
3. `Динамика за 28 дней`
4. `Динамика за 7 дней`
5. `Добавлений в корзину`
6. `Конверсия в корзину`
7. `Уникальные покупатели с заказами`
8. `Конверсия в заказ`
9. `Заказано на сумму по запросам, ₽`
10. `Запросы без действий`
11. `Доля запросов без действий`

Aliases, generic whitespace normalization, translated aliases, fuzzy matching, reordered columns, invented optional columns, or semantic guessing are not part of v1.

## 7. Observed help-row semantics

Row 4 is explanatory source text and is not part of the exact report identity signature.

Observed values are:

1. A4: `—`
2. B4: `Количество покупателей, которые искали товар по этому запросу`
3. C4: `Динамика за 7 и 28 дней поможет быстрее отреагировать на спрос и увеличить продажи`
4. D4: `Динамика за 7 и 28 дней поможет быстрее отреагировать на спрос и увеличить продажи`
5. E4: `Количество покупателей, которые пришли по этому запросу из результатов поиска и добавили в корзину хотя бы один товар`
6. F4: `Процент покупателей, которые пришли по этому запросу из результатов поиска и добавили в корзину хотя бы один товар`
7. G4: `Количество покупателей, которые пришли по этому запросу из результатов поиска и заказали товар`
8. H4: `Процент покупателей, которые пришли по этому запросу из результатов поиска и заказали товар`
9. I4: `Суммарная стоимость заказанных товаров. Считаем по цене продажи`
10. J4: `Количество запросов, при которых покупатели не кликали на товары из выдачи`
11. K4: `Процент запросов, при которых покупатели не кликали на товары из выдачи`

Ordinary text changes in the explanatory row must not manufacture new metrics or identities. The parser ignores row 4 as data. Formula cells in structural rows 1–4 are unsupported.

The explanatory text is authoritative for source semantics where it is explicit, especially the difference between:

- popularity as a count of **buyers/users** who searched;
- no-action count as a count of **queries/search events** with no click.

These counts are not the same unit and must not be compared through a naive `no_action_queries <= popularity_users` invariant.

## 8. Deterministic report detection

`report_type = OZON_QUERY_METRICS` only for the verified structural family.

Minimum v1 detection conditions:

- exactly one worksheet;
- readable XLSX package after only approved source-compatible package handling described in section 3;
- A1 has exact `Период:` marker and supported date-range form;
- A2 equals the exact supported sort line;
- row 3 A:K equals the exact header signature;
- there are no merged cells;
- there are no non-empty business values in L onward;
- structural rows contain no formulas.

Classification rules:

- PR3 Products-shaped workbook → `WRONG_REPORT_TYPE`;
- PR4 Search Visibility-shaped workbook → `WRONG_REPORT_TYPE`;
- PR5 `seller-queries` Own Product Queries-shaped workbook → `WRONG_REPORT_TYPE`;
- another clearly different readable report → `WRONG_REPORT_TYPE`;
- expected Query Metrics markers with incompatible Query Metrics structure → `INCOMPATIBLE_SCHEMA`;
- package that remains unreadable after only the approved source-compatible handling → `UNSUPPORTED_WORKBOOK`.

Detection never uses filename, worksheet name, or fuzzy header similarity.

## 9. Period semantics

A1 has the exact v1 form:

`Период: DD.MM.YYYY - DD.MM.YYYY`

The evidence yields:

- `period_start = 2026-07-23`;
- `period_end = 2026-08-19`.

Both are calendar dates.

Require `period_start <= period_end`.

The exact pair is canonical. Do not replace it with a single invented duration identity.

A 28-day evidence interval does not authorize an adapter to assume that every future report is exactly 28 days. Period compatibility uses the explicit source dates.

Overlapping but non-identical periods remain distinct observations. Ingestion does not prorate, daily-expand, average, or align periods.

### No generated_at in the source workbook

This workbook exposes no source-generated date/time separate from the analysis period.

Therefore:

- filename timestamp is not `generated_at`;
- filesystem mtime is not `generated_at`;
- upload time is not `generated_at`;
- import time is stored separately as `imported_at`;
- source artifact filename remains provenance only.

## 10. Sort context and coverage semantics

A2 in the evidence is:

`Сортировка: По убыванию в Популярность запроса`

The evidence rows are in fact monotonically non-increasing by `Популярность запроса`.

V1 freezes this exact supported sort context because the selected sort can affect which queries appear in a bounded export.

The workbook does **not** state:

- that it is the complete universe of Ozon queries;
- that 10,000 is an official exhaustive limit;
- that a query absent from the file has zero demand;
- that the last popularity value is a global minimum;
- that all possible queries above or below a threshold are included.

Canonical coverage interpretation:

> the file contains an observed set of 10,000 market queries for the stated period under the stated sort context.

Consequences:

- absence from the report means **no market QueryMetricSnapshot observation from this source/period**;
- absence must never be normalized to `popularity = 0`;
- absence must never be normalized to zero conversion, zero orders, zero turnover, or 100% no-action;
- per-query Query Opportunity may return unavailable/insufficient market Demand/Quality when a relevant query is outside current source coverage.

This distinction is critical because a query can exist in PR4/own-product sources while being absent from this 10,000-row market export.

## 11. Shared SearchQuery identity

PR5 reuses the `SearchQuery` entity introduced by PR4 and already reused by the approved `seller-queries` contract.

Source query is column A `Запрос`.

Canonical technical cleanup is exactly the existing shared rule:

- remove leading/trailing U+0020 ordinary spaces;
- remove leading/trailing U+00A0 NBSP characters.

The resulting non-empty text is the exact `SearchQuery` identity.

Do not:

- lowercase or case-fold;
- convert `ё` to `е`;
- stem or lemmatize;
- remove punctuation;
- rewrite keyboard-layout mistakes;
- collapse internal spaces;
- rewrite synonyms;
- infer SKU/Product identity;
- use fuzzy matching.

The evidence contains:

- 10,000 distinct query strings;
- no leading/trailing U+0020/U+00A0 in those 10,000 strings;
- 35 numeric-only query strings, including long values that resemble Ozon product IDs.

Numeric-looking query text remains a `SearchQuery`. It must never be auto-resolved as Product identity.

If the exact canonical query text already exists from PR4 or `seller-queries`, this source reuses that same `SearchQuery` row.

## 12. QueryMetricSnapshot logical grain

Canonical logical observation key:

> **SearchQuery × period_start × period_end**

There is no Product dimension and no Cluster dimension in this source.

The normalized source payload contains exactly these ten facts:

1. `popularity_users`
2. `dynamics_28d_pct`
3. `dynamics_7d_pct`
4. `cart_add_users`
5. `market_cart_conversion_pct`
6. `unique_buyers_with_orders`
7. `market_order_conversion_pct`
8. `ordered_revenue_rub`
9. `no_action_queries`
10. `no_action_share_pct`

Sort context and source artifact information belong to import/report provenance and coverage, not to the per-query payload hash.

Revision semantics:

- same logical key + same normalized payload → `DUPLICATE`, no new snapshot revision;
- same logical key + changed normalized payload → `CORRECTED`, append immutable revision and preserve supersession lineage;
- different `period_start` or `period_end` → independent observation, revision 1;
- overlapping periods are not automatically merged.

## 13. Raw Excel type policy

Unlike PR4 localized text metrics and unlike the `seller-queries` localized text source, the evidence market metrics are primarily **native Excel numeric cells**.

V1 row facts use these source types:

- query text → Excel string/shared string;
- popularity/count fields → native numeric cells with integral values;
- conversion/share fields → native numeric cells stored as Excel fractional values and displayed as percentages;
- dynamics → native numeric percentage-fraction cell **or exact string sentinel `-`**;
- ordered revenue → native numeric cell;
- formulas → unsupported.

Do not add a generic locale-text-number parser for this source without new evidence.

Boolean cells are not valid substitutes for numeric `0/1`.

## 14. Percentage normalization policy

Percentage-like source numeric cells are stored as Excel fractions.

SCOZ canonical domain values use `Decimal` **percentage points**.

Therefore:

- raw `0.1612` → `Decimal("16.12")`;
- raw `0.403` → `Decimal("40.3")`;
- raw `0.26` dynamics → `Decimal("26")`;
- raw `-0.12` dynamics → `Decimal("-12")`;
- raw `-1` dynamics → `Decimal("-100")`;
- raw `12217` dynamics → `Decimal("1221700")`.

Never convert through a binary float as the canonical step when exact decimal cell text is available. Do not divide a percentage-point value by 100 again downstream.

The display format and the underlying numeric value are distinct source facts. Normalization is defined from the underlying numeric value plus the known field semantics.

## 15. Exact query-row field contracts

Rows 5 onward use A:K.

### A — query

Header: `Запрос`

Required non-empty source text after shared edge cleanup.

Unsupported/empty query identity makes that candidate row invalid.

Do not infer query from row number or another metric.

### B — popularity_users

Header: `Популярность запроса`

Help semantics: number of buyers/users who searched for a product using this query.

V1 requires a native numeric Excel cell whose value is an exact non-negative integer.

Normalize to:

`popularity_users: int >= 0`

Evidence:

- minimum: `11845`;
- maximum: `867550`;
- no missing or sentinel values.

Do not rename this to Product impressions or Product search views.

### C — dynamics_28d_pct

Header: `Динамика за 28 дней`

V1 supports exactly two source forms:

1. native numeric Excel value → multiply by 100 and normalize to signed `Decimal` percentage points;
2. exact string U+002D HYPHEN-MINUS `-` → `dynamics_28d_pct = None`.

Evidence contains seven exact `-` sentinels.

Numeric evidence range before percentage-point scaling:

- minimum `-0.88`;
- maximum `12217`.

Therefore no arbitrary `-100%..+100%` cap is valid. Large positive dynamics are source facts and must not be clipped.

The source does not define in this workbook the exact comparison baseline used to compute "dynamics". SCOZ stores the source-reported value and does not reverse-engineer it.

Blank, em dash `—`, textual percentages, or other sentinels are unsupported in v1.

### D — dynamics_7d_pct

Header: `Динамика за 7 дней`

Same normalization rules as `dynamics_28d_pct`.

Evidence contains two exact `-` sentinels.

Numeric evidence range before percentage-point scaling:

- minimum `-1`;
- maximum `15763`.

The exact `-` sentinel maps to `None`; it is not numeric minus one and is not silently replaced with zero.

### E — cart_add_users

Header: `Добавлений в корзину`

Help semantics: number of buyers/users who came from search results for the query and added at least one product to cart.

V1 requires a native numeric Excel cell with an exact non-negative integer.

Normalize to:

`cart_add_users: int >= 0`

Evidence range:

- minimum `0`;
- maximum `201906`.

Do not recompute from popularity × conversion.

### F — market_cart_conversion_pct

Header: `Конверсия в корзину`

Help semantics: percentage of buyers/users who came from search results for the query and added at least one product to cart.

V1 requires a native numeric Excel fractional value in `0..1` inclusive.

Normalize to percentage points by multiplying by 100.

Evidence raw range:

- minimum `0`;
- maximum `0.8047`.

Normalized evidence range is therefore `0..80.47` percentage points.

This is a **market/query-level conversion**, not `ProductQuerySnapshot.search_to_card_conversion_pct`.

Do not recompute it from `cart_add_users / popularity_users` or any other inferred denominator.

### G — unique_buyers_with_orders

Header: `Уникальные покупатели с заказами`

Help semantics: number of buyers/users who came from search results for the query and ordered a product.

V1 requires a native numeric Excel cell with an exact non-negative integer.

Normalize to:

`unique_buyers_with_orders: int >= 0`

Evidence range:

- minimum `0`;
- maximum `100320`.

Do not derive from conversion.

### H — market_order_conversion_pct

Header: `Конверсия в заказ`

Help semantics: percentage of buyers/users who came from search results for the query and ordered a product.

V1 requires a native numeric Excel fractional value in `0..1` inclusive.

Normalize to percentage points by multiplying by 100.

Evidence raw range:

- minimum `0`;
- maximum `0.6388`.

Normalized evidence range is therefore `0..63.88` percentage points.

This is the canonical PR5 **market query CR** signal.

It is not:

- own-product search-to-order conversion;
- competitor Product conversion;
- aggregate Product conversion;
- a value to be recomputed from `unique_buyers_with_orders / popularity_users`.

The source-provided value is preserved independently.

### I — ordered_revenue_rub

Header: `Заказано на сумму по запросам, ₽`

Help semantics: total price of ordered products, calculated by sale price.

V1 requires a native non-negative Excel numeric value.

Normalize directly to `Decimal` RUB without rounding through float and without forcing integer rubles or two decimal places.

Evidence:

- minimum raw value: `0`;
- maximum raw value: `153735140`;
- underlying source numeric values include 0, 1, 2, 3, and 4 fractional decimal places;
- an observed four-decimal example is `3055.8916`.

The workbook display number format rounds this field visually to whole rubles, but the underlying numeric cell carries more precision. SCOZ preserves the underlying source numeric fact and does not truncate it merely to mimic Excel display formatting.

### J — no_action_queries

Header: `Запросы без действий`

Help semantics: count of query/search events for which buyers did not click products in search results.

V1 requires a native numeric Excel cell with an exact non-negative integer.

Normalize to:

`no_action_queries: int >= 0`

Evidence range:

- minimum `427`;
- maximum `521969`.

This field counts **queries/search events**, while `popularity_users` counts buyers/users. Do not impose:

`no_action_queries <= popularity_users`

and do not divide these fields to invent `no_action_share_pct`.

### K — no_action_share_pct

Header: `Доля запросов без действий`

Help semantics: percentage of query/search events for which buyers did not click products in search results.

V1 requires a native non-negative Excel numeric fractional value.

Normalize to percentage points by multiplying by 100.

Evidence raw range:

- minimum `0.014`;
- maximum `1.002`.

The evidence contains two rows with raw `1.002`, i.e. **100.2 percentage points** after normalization.

Therefore:

- do not cap the value at 100;
- do not "repair" 100.2 to 100;
- do not reject a row merely because this source-reported share is greater than 100%;
- do not recompute it from `no_action_queries / popularity_users`;
- do not infer a denominator absent from the source.

The source fact is preserved as reported.

## 16. No cross-field repair or inferred constraints

The parser stores source facts; it does not enforce invented arithmetic identities.

Specifically do not require:

- `cart_add_users <= popularity_users`;
- `unique_buyers_with_orders <= popularity_users`;
- `no_action_queries <= popularity_users`;
- `market_cart_conversion_pct == cart_add_users / popularity_users`;
- `market_order_conversion_pct == unique_buyers_with_orders / popularity_users`;
- `no_action_share_pct == no_action_queries / popularity_users`;
- `no_action_share_pct <= 100`;
- dynamics to fit a conventional bounded percentage range.

Do not derive one supplied metric from another merely because a relationship looks plausible.

Only field-local type/range rules explicitly established by this contract are allowed at ingestion.

## 17. Formulas and row validity

The evidence contains zero formula cells.

V1 does not accept formulas as source business values.

Rules:

- a formula in structural rows 1–4 → fatal incompatible schema;
- a formula in a candidate row A:K → that candidate row is invalid/recoverable;
- formula result cached value must not be accepted in place of a source literal.

A candidate row with one or more unsupported field values is skipped with a row error; valid rows remain importable unless the report becomes unusable under the future import-result contract.

## 18. In-file duplicate query policy

The evidence contains 10,000 distinct query texts and no duplicate canonical `SearchQuery` identity inside the file.

Future deterministic handling:

- same canonical query repeated within the same workbook with identical normalized payload → warning + dedupe to one candidate observation;
- same canonical query repeated within the same workbook with conflicting normalized payload → fatal conflicting report.

Because the report-level period is common to all rows, two conflicting rows for the same canonical query would claim two different payloads for the same logical key.

Do not silently choose first/last/highest-popularity row.

## 19. Coverage is not zero-fill

This report is a bounded observed query set, not evidence about every possible `SearchQuery`.

A `SearchQuery` existing elsewhere in SCOZ but absent here produces:

- no `QueryMetricSnapshot` for this source/period;
- market Demand/Quality unavailable for that query/period unless another compatible source exists.

It must **not** produce a synthetic zero-filled snapshot.

Examples of forbidden inference for an absent query:

- `popularity_users = 0`;
- `market_order_conversion_pct = 0`;
- `ordered_revenue_rub = 0`;
- `no_action_share_pct = 100`;
- "query has no demand".

This rule is required for correct Query Opportunity readiness and confidence.

## 20. Market Demand / Query Quality interpretation boundary

This source supplies raw market-level inputs needed by later Query Opportunity analytics.

It does **not** itself compute a score or verdict.

Potential later use:

- `popularity_users` → Query Demand;
- `market_order_conversion_pct` → market commercial-intent/Quality signal;
- `no_action_share_pct` → Quality/friction signal;
- `unique_buyers_with_orders` and `ordered_revenue_rub` → commercial context;
- dynamics → source-reported trend context.

Forbidden at ingestion:

- Opportunity Score 0–100;
- "good/bad query" verdict;
- ranking query importance;
- joining a query to a Product without explicit Product context from another source;
- treating own Product conversion as market conversion;
- treating market conversion as competitor conversion.

Analytics remain downstream.

## 21. Provenance and source-artifact boundary

The uploaded original remains the provenance artifact.

Future ingestion must retain at least:

- original filename;
- SHA-256;
- byte size;
- source report type;
- `period_start`;
- `period_end`;
- supported sort context;
- observed candidate-row count;
- accepted/skipped/error counts;
- import time;
- archive/reference lineage consistent with the shared import runtime.

Any temporary package-normalized copy needed to tolerate section 3 quirks is **not** a new source artifact and must not replace the archived original.

## 22. Zero-usable-row behavior

A structurally valid Query Metrics workbook can still contain zero usable candidate rows after row-level validation.

In that case:

- no `SearchQuery` or `QueryMetricSnapshot` mutation is committed from this report;
- import is FAILED under the future PR5 import-result contract;
- source artifact/provenance and failure reason remain traceable according to shared lineage rules;
- ingestion must not manufacture empty/zero snapshots.

Exact API error names belong to the PR5 Implementation Spec.

## 23. Synthetic fixture and parser acceptance matrix

Implementation tests must use synthetic fixtures and must not commit the real evidence XLSX.

At minimum cover:

### Valid structure

- one-sheet valid fixture;
- exact period parsing;
- exact sort line;
- exact A:K header order;
- help row ignored as data;
- at least one valid query row;
- query identity reused with existing `SearchQuery`.

### Report-type discrimination

- PR3 Products-shaped workbook → wrong report type;
- PR4 Search Visibility-shaped workbook → wrong report type;
- PR5 `seller-queries`-shaped workbook → wrong report type;
- unrelated readable workbook → wrong report type;
- partial Query Metrics markers/header damage → incompatible schema.

### Package compatibility

- stored worksheet dimension `A1` despite cells beyond A1 does not truncate import;
- verified-style capitalization `Left`/`Right` can be tolerated without changing business cells;
- unrecognized/unrecoverable package corruption remains unsupported;
- merged cells rejected;
- non-empty L+ business value rejected.

### Query identity

- ordinary text query;
- numeric-only query remains query text;
- U+0020 edge cleanup;
- U+00A0 edge cleanup;
- internal whitespace preserved;
- empty-after-edge-cleanup row invalid.

### Period

- valid `DD.MM.YYYY - DD.MM.YYYY`;
- invalid calendar date;
- end before start;
- altered/unsupported period marker;
- no generated_at inferred from filename.

### Numeric types

- integral popularity/count fields;
- zero count accepted where allowed;
- bool rejected as numeric;
- localized text number rejected without evidence;
- formulas rejected.

### Dynamics

- positive;
- negative;
- zero;
- very large positive;
- exact `-` sentinel;
- blank unsupported;
- em dash `—` unsupported.

### Conversions/shares

- Excel fraction → Decimal percentage points;
- cart/order conversion boundaries 0 and 1;
- cart/order conversion outside 0..1 rejected;
- no-action share above 1 accepted and preserved;
- no artificial no-action <= 100% cap.

### Revenue

- integer raw value;
- one/two/three/four-decimal raw values;
- preserve underlying precision;
- negative rejected.

### Cross-field independence

- no-action count greater than popularity remains valid;
- source no-action share above 100 percentage points remains valid;
- conversion not recomputed from counts;
- internally surprising but field-valid source facts preserved.

### Duplicates/revisions

- identical duplicate query row warns/dedupes;
- conflicting duplicate query row fatal;
- same key/same payload → duplicate on repeated import;
- same key/changed payload → corrected immutable revision;
- changed period → independent observation.

### Coverage

- fixture with fewer than 10,000 rows remains structurally valid;
- 10,000 is observed evidence, not required completeness;
- absent query does not receive zero snapshot.

## 24. Explicit non-goals

This contract does not define:

- PR5 database migration layout;
- exact repository class names;
- exact FastAPI endpoint;
- UI upload-card wording;
- complete import summary DTO;
- final shared import runtime implementation;
- Query Opportunity analytics;
- relevant-query selection UI;
- MPStats position history;
- Ramp-up;
- automatic Ozon cabinet scraping;
- undocumented/internal Ozon APIs.

Those belong to later approved PR-specific design/specification work.

## 25. Frozen v1 decisions summary

The following are frozen factual/design-boundary decisions for this source:

1. canonical source family is market-level Ozon Query Metrics, not own-product queries;
2. one shared `SearchQuery` identity is reused across PR4/PR5 sources;
3. logical grain is `SearchQuery × period_start × period_end`;
4. no Product and no Cluster dimension are invented;
5. period comes only from A1; filename timestamp is not generated_at;
6. sort context is preserved and v1 supports the exact verified popularity-descending sort;
7. 10,000 rows are observed coverage, not proof of a complete universe or mandatory row count;
8. absent query means unavailable source coverage, never zero demand;
9. payload contains exactly ten source facts listed in section 12;
10. market cart/order conversion fields are explicitly distinct from Product conversion;
11. percentage fractions normalize to Decimal percentage points;
12. dynamics exact `-` sentinel maps to unavailable/None, not zero;
13. large dynamics are preserved and not clipped;
14. no-action share above 100 percentage points is preserved and not repaired;
15. no cross-field arithmetic is recomputed at ingestion;
16. revenue preserves underlying Excel numeric precision, including more than two fractional digits;
17. numeric-looking query text remains SearchQuery text;
18. duplicate/corrected observations use immutable revision semantics;
19. the real Ozon workbook's incorrect dimension metadata and capitalized style alignments are source-compatibility facts that the implementation must tolerate without altering business data;
20. original uploaded XLSX remains the provenance artifact even if a temporary read-compatible representation is used internally.

Any newly observed workbook shape or metric representation outside these rules requires new evidence and an explicit source-contract revision before implementation support.
