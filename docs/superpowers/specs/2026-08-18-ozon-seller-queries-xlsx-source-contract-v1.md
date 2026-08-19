# Ozon `seller-queries` Own Product Queries XLSX — Source Contract v1

**Status:** Approved factual source contract v1

**Date:** 2026-08-18

**Scope:** only the verified Ozon `seller-queries` XLSX shape for the seller report «Запросы моего товара»; this contract covers the PR5 source for `ProductQuerySnapshot` only and does not cover market-level `QueryMetricSnapshot`

## 1. Authority, source scope, and evidence provenance

This contract freezes source facts established by direct inspection of one user-supplied Ozon workbook. The workbook is sensitive user input and is **not stored, copied into fixtures, or committed to this public repository**. Only the structural and semantic facts required for a deterministic adapter are documented here.

Canonical SCOZ report type for this source family: `OZON_OWN_PRODUCT_QUERIES`.

Future XLSX import kind: `ozon_seller_queries_xlsx`.

Evidence workbook:

- evidence filename: `seller-queries_18.07-14.08.2026_created_2026-08-17_06-56.xlsx`;
- SHA-256: `dedbd107466fb7a0ca742c0277dd5ef7253da6313fc2a0b8a4bd1f1b538e598b`;
- byte size: `73201`;
- one worksheet;
- semantic used range: A1:K572;
- no formula cells in A1:K572;
- no merged cells in the verified workbook;
- report-generation metadata in rows 1–4;
- exact header row at row 6;
- one own-product context row at row 8;
- 564 query observation rows at rows 9–572.

The worksheet name and filename are evidence metadata only. Detection must never depend on filename, worksheet name, `seller-queries`, date fragments embedded in the filename, or fuzzy similarity.

Public Ozon documentation corroborates the semantic purpose of this source: «Запросы моего товара» is analytics for queries by which the seller's own product was seen or bought, including users who searched/saw the product, average search position, and revenue. The XLSX evidence remains the authority for exact workbook structure and textual formats.

## 2. PR5 source boundary

PR5 intentionally has two different source families:

1. **Own-product query history** → `ProductQuerySnapshot` — this contract.
2. **Market-level query metrics** → `QueryMetricSnapshot` — a separate source contract that must be based on separate verified Ozon evidence.

This workbook must **not** create `QueryMetricSnapshot` merely because it contains `Человек искало`.

In particular:

- `searched_users` is preserved as a source fact of the own-product query report;
- it is not renamed to `query_demand`, `market_frequency`, or `market_popularity`;
- it does not become the canonical Query Demand input while the separate market-query source is absent;
- own-product conversion is never treated as market query CR;
- own-product conversion is never treated as competitor conversion.

This separation is required so PR10 Query Opportunity can later combine Demand/Quality with own visibility and position without confusing incompatible semantics.

## 3. Physical versus semantic columns

The verified workbook uses business columns A:K only.

The v1 semantic boundary is therefore A:K. Empty/style-only physical cells beyond K may be tolerated by a future implementation, but any non-empty business value in L onward makes the workbook incompatible with this exact v1 shape.

No business meaning is inferred from formatting, column width, style, or worksheet name.

## 4. Exact workbook structure

The sole worksheet has this semantic layout:

| Row | Contract |
|---|---|
| 1 | A1 matches `Дата: DD/MM/YYYY`; B:K semantically blank |
| 2 | A2 matches `Время: HH:MM +00`; B:K semantically blank |
| 3 | A3 matches `Дата начала: DD/MM/YYYY`; B:K semantically blank |
| 4 | A4 matches `Дата конца: DD/MM/YYYY`; B:K semantically blank |
| 5 | A:K semantically blank |
| 6 | A:K is the exact ordered header signature in section 5 |
| 7 | A:K semantically blank |
| 8 | A:C is own-product context; D:K semantically blank |
| 9 onward | query observation candidates; A:C semantically blank; D:K contain row facts |

Semantic blank means Excel `None` or exact zero-length text `""`. Whitespace-only text is not semantically blank.

The verified workbook contains no report-level declared row count. Therefore there is no PR4-style declared-count reconciliation. Every row at row 9 or later with any semantically non-blank D:K value is a query-row candidate. Completely semantically blank trailing rows are ignored.

## 5. Exact A:K ordered header signature

Row 6 A:K must equal, in order:

1. `SKU`
2. `Артикул`
3. `Название товара`
4. `Запросы товара`
5. `Человек\nискало`
6. `Человек увидело`
7. `Позиция товара`
8. `Конверсия из поиска в карточку`
9. `Конверсия из поиска в заказ`
10. `Заказано товаров по запросам`
11. `Заказано на сумму\nпо запросам`

Unicode is source-significant:

- header 5 contains LF U+000A between `Человек` and `искало`;
- headers 8 and 9 contain NBSP U+00A0 after `из`;
- header 10 contains NBSP U+00A0 after `по`;
- header 11 contains NBSP U+00A0 after `Заказано`, LF U+000A after `сумму`, and NBSP U+00A0 after `по`.

Aliases, generic whitespace normalization, replacing NBSP with ordinary spaces, fuzzy matching, reordered columns, translated aliases, and guessed optional columns are not part of v1.

## 6. Deterministic report detection

`report_type = OZON_OWN_PRODUCT_QUERIES` only when the workbook matches the expected structural family:

- exactly one worksheet;
- A1 has the exact `Дата:` marker and supported date format;
- A2 has the exact `Время:` marker and supported UTC format;
- A3 has the exact `Дата начала:` marker and supported date format;
- A4 has the exact `Дата конца:` marker and supported date format;
- row 5 A:K is semantically blank;
- row 6 A:K equals the exact header signature;
- row 7 A:K is semantically blank;
- row 8 has valid own-product context in A:C and D:K semantically blank;
- there are no merged cells;
- there are no non-empty business values in L onward.

Classification rule:

- a readable XLSX clearly representing another known report, including PR3 Products-shaped or PR4 Search Visibility-shaped input, is `WRONG_REPORT_TYPE`;
- expected seller-query markers with incompatible seller-query structure are `INCOMPATIBLE_SCHEMA`;
- unreadable/non-XLSX package is `UNSUPPORTED_WORKBOOK`.

Detection never guesses a near match and never uses filename or worksheet name.

## 7. Report generation time and analysis period

The source exposes two different time concepts and they must never be collapsed.

### generated_at

`generated_at` is formed from:

- `Дата: DD/MM/YYYY`;
- `Время: HH:MM +00`.

The verified evidence yields a timezone-aware UTC generation timestamp. V1 supports the observed `+00` offset only. Filename timestamps, filesystem mtime, upload time, GitHub time, and `imported_at` are not source generation time.

`generated_at` is report/import provenance and **is not part of the ProductQuerySnapshot logical observation key**.

### period_start / period_end

`period_start` is parsed only from `Дата начала: DD/MM/YYYY`.

`period_end` is parsed only from `Дата конца: DD/MM/YYYY`.

Both are calendar dates. Require `period_start <= period_end`.

Do not replace the pair with a single invented duration identity. A display duration may be derived later, but the exact source dates remain canonical and period compatibility must use them explicitly.

Overlapping but non-identical periods remain distinct observations. No automatic prorating, daily expansion, averaging, or period alignment is performed by ingestion.

## 8. Product identity, product context, and ownership

Row 8 is report-level own-product context.

### SKU

A8 is the Ozon product SKU/product ID for this report. V1 requires a positive decimal-digit value and maps it to the existing SCOZ external identity:

- `source = "ozon"`;
- `identity_type = "ozon_product_id"`;
- `identity_value = <digits>`;
- `source_account_scope = ""`.

Title, article, query text, report period, and row number are not Product identity.

### Ownership is positive source evidence

Unlike PR4 Search Visibility, this report is explicitly analytics for **the seller's own product**. Therefore a valid `seller-queries` import is positive source evidence of ownership:

- unknown Product → resolve/create the same Ozon identity and set `is_owned = True`;
- existing Product with `is_owned = False` → set `is_owned = True`;
- existing Product with `is_owned = True` → keep `True`.

Do not infer ownership from title/article heuristics; ownership follows from the verified source type itself.

This does not create a `ProductSnapshot` and does not bypass the existing PR3-backed product-catalog boundary. If a Product has no PR3 ProductSnapshot, existing catalog visibility rules still apply.

A later valid own-product-query import is new positive source evidence and may set ownership to true again after a prior manual false state.

### Article and title

B8 `Артикул` and C8 `Название товара` are required non-empty source context in v1. They must not become product identity and must not cause product duplication.

They are report-level provenance/context, not part of the eight-field query observation payload and not part of payload hashing. A title or article change alone therefore must not manufacture a corrected query-metric revision.

## 9. Shared SearchQuery identity

PR5 reuses the `SearchQuery` entity introduced by PR4. Do not create `ProductQueryText`, `OwnSearchQuery`, or another duplicate query-identity table.

The source query is D-column `Запросы товара`.

Canonical technical cleanup is exactly the same as PR4:

- remove leading/trailing U+0020 ordinary spaces;
- remove leading/trailing U+00A0 NBSP characters.

The resulting non-empty text is the exact `SearchQuery` identity.

Do not:

- lowercase or case-fold;
- convert `ё` to `е`;
- stem or lemmatize;
- remove punctuation, hashtags, keyboard-layout mistakes, or unusual spelling;
- collapse internal spaces;
- rewrite synonyms;
- use fuzzy matching.

The verified evidence includes unusual query forms, which confirms that ingestion must preserve source query identity rather than linguistically repair it.

If the exact canonical text already exists from PR4, PR5 must reuse the same `SearchQuery` row.

## 10. ProductQuerySnapshot logical grain

Canonical logical observation key:

> **Product × SearchQuery × period_start × period_end**

`generated_at` is not in the logical key.

The exact normalized observation payload contains only these eight source facts:

1. `searched_users`
2. `seen_users`
3. `position_state`
4. `average_position`
5. `search_to_card_conversion_pct`
6. `search_to_order_conversion_pct`
7. `ordered_units`
8. `ordered_revenue_rub`

Report-level article/title and generation time do not enter this payload hash.

Revision semantics:

- same logical key + same normalized payload → `DUPLICATE`, no new snapshot revision;
- same logical key + changed normalized payload → `CORRECTED`, append immutable revision and preserve supersession lineage;
- different `period_start` or `period_end` → different observation, revision 1;
- overlapping periods are not automatically merged or compared as if identical.

## 11. Localized numeric source policy

All eight query-row fields in the verified evidence are text cells, not Excel numeric cells.

Parsing rules are field-specific. There is no generic locale parser.

General rules:

- parse integer and decimal source values directly from exact documented textual forms;
- ordinary U+0020 grouping spaces may be removed only where a field contract explicitly allows them;
- decimal comma may be converted to decimal point only for percentage parsing;
- use `Decimal` for decimal/money values, never float;
- do not infer a value from another metric;
- do not repair internally inconsistent source facts.

The verified 564 observations contain no blank D:K metric cells and no formula cells.

## 12. Exact query-row field contracts

Rows 9 onward use D:K.

### Query text — D

Required non-empty text after the limited edge cleanup in section 9.

Invalid/empty query identity makes that candidate row invalid; it must never be replaced with row number, title, article, or another query.

### searched_users — E (`Человек\nискало`)

Required non-negative integer text.

Allow ordinary U+0020 digit grouping, for example the source family supports forms equivalent to `7 330` and ungrouped short values.

Normalize to `searched_users: int >= 0`.

This is preserved exactly as an own-product-report source fact. It is not automatically a market-level demand metric.

### seen_users — F (`Человек увидело`)

Required non-negative integer text with the same ordinary-space grouping policy.

Normalize to `seen_users: int >= 0`.

Do **not** impose `seen_users <= searched_users`. The verified workbook violates that relation in 15 rows, including rows where `searched_users = 0` and `seen_users > 0`. Both values are independent source facts.

`seen_users` is also not the same semantic metric as aggregate PR3 product impressions and must not be silently substituted for them.

### Position — G (`Позиция товара`)

Ozon's public description defines this report's position as the product's **average position in search for that query**. SCOZ therefore uses the canonical field name `average_position`, but preserves the exact XLSX source value semantics described below.

Supported source text is a non-negative integer with optional ordinary U+0020 grouping spaces.

Two evidenced states exist:

1. positive integer → `position_state = KNOWN`, `average_position = positive int`;
2. exact numeric zero → `position_state = SOURCE_ZERO`, `average_position = None`.

The verified workbook contains 11 `SOURCE_ZERO` rows and also contains positive positions greater than 1,000, so:

- zero is not a valid rank 0;
- position must not be bounded by row count or presumed TOP-N range;
- worksheet row number must never replace source position;
- `SOURCE_ZERO` must not silently collapse into ordinary `None` without state;
- `SOURCE_ZERO` must not be used numerically in ranking averages, TOP-N, gaps, or Ramp-up calculations.

The domain may reserve a third state `MISSING` for a genuinely absent position from a future verified source/adapter. **This XLSX v1 has no evidenced missing-position source form and therefore must not produce `MISSING` from blank text.** Blank or any unsupported position representation is an invalid metric for this source version.

### search_to_card_conversion_pct — H

Required percentage text with `%` suffix and source decimal comma when fractional.

Observed forms include integer percentages and one- or two-decimal percentages. Normalize to `Decimal` in **percentage points**:

- source `0%` → `Decimal("0")`;
- source form equivalent to `2,48%` → `Decimal("2.48")`;
- source form equivalent to `12,5%` → `Decimal("12.5")`;
- source `100%` → `Decimal("100")`.

Do not divide by 100. Do not recompute from `seen_users`, clicks, orders, or another denominator.

Require the normalized value to be within 0..100 inclusive.

### search_to_order_conversion_pct — I

Same textual and normalization rules as H.

It is the own product's source-reported search-to-order conversion for this query and period. It is **not** market query CR and not competitor CR.

Do not recompute it from `ordered_units`, `searched_users`, or `seen_users`.

### ordered_units — J

Required non-negative integer text with optional ordinary U+0020 grouping spaces.

Normalize to `ordered_units: int >= 0`.

Do not derive this value from either conversion percentage.

### ordered_revenue_rub — K

Required whole-ruble money text with exact trailing ` ₽` and optional ordinary U+0020 grouping spaces in the integer amount.

Normalize directly to non-negative `Decimal` representing RUB, for example a grouped whole-ruble source value becomes an integer-scale decimal value.

The verified evidence contains `0 ₽` and at least one non-zero grouped whole-ruble value. Decimal cents are not evidenced and therefore unsupported in this XLSX v1.

Do not infer revenue from product price × ordered units, and do not cross-check it against PR3 turnover as an equality constraint.

## 13. No cross-field repair or invented invariants

The parser/ingestion layer preserves source facts independently.

Forbidden validations/inferences include:

- `seen_users <= searched_users`;
- deriving conversion from counts;
- deriving ordered units from conversion;
- deriving revenue from units × price;
- converting `SOURCE_ZERO` into position 0;
- replacing `SOURCE_ZERO` with a guessed low rank;
- treating query-level users as product-level impressions;
- treating own-product query CR as market CR;
- treating a market query metric from another source as if it were measured for this ProductQuerySnapshot period without explicit period compatibility.

Internal source inconsistencies are data-quality context, not an invitation to rewrite Ozon facts.

## 14. In-file duplicate and conflict semantics

The verified evidence has 564 observation rows and 564 distinct exact query strings after the approved edge cleanup.

For a future same-file duplicate under the same Product + SearchQuery + period:

- identical normalized payload → warning + deduplicate within the import; write at most one observation;
- conflicting normalized payload → fatal `CONFLICTING_OBSERVATION_ROWS`; do not choose one by row order.

Similar-but-different query text remains different `SearchQuery` identity under section 9.

## 15. Structural versus row-level failure boundary

Source-contract classification for future implementation:

### Fatal structural/report failures

Examples:

- unsupported workbook package;
- more than one worksheet;
- malformed/unsupported report metadata;
- invalid generation timestamp or period;
- wrong report type;
- incompatible header/layout;
- merged cells;
- formula cells in structural rows;
- non-empty business values beyond K;
- invalid row-8 own-product identity/context;
- conflicting duplicate observation rows.

A fatal structural failure must not create ProductQuerySnapshot domain observations.

### Recoverable query-row failures

A structurally valid query candidate may be skipped with a bounded row error when its query identity or one of its D:K metrics has an unsupported value.

Formula cells in query observation rows are unsupported and should be treated as row-level invalid data rather than evaluated.

If the structurally valid report yields zero usable query observations, the import is a failed `NO_USABLE_ROWS` outcome and must not manufacture an empty successful history point.

Exact error-code names and API envelopes belong to the PR5 Implementation Spec, not this factual source contract.

## 16. Parser read mode and formula policy

A future parser must inspect formula presence rather than trusting cached results. It must not evaluate or accept formulas as source facts.

The evidence workbook contains zero formula cells in the used A:K range.

Synthetic fixtures must reproduce source strings/Unicode deliberately; real evidence workbook bytes must not be committed.

## 17. Market QueryMetricSnapshot remains a separate required contract

This source contract is intentionally insufficient to finish all of PR5.

Before the PR5 Implementation Spec is frozen, a second verified Ozon source contract is still required for the market-level `QueryMetricSnapshot` fields required by the master PR plan, including where available:

- frequency/popularity;
- market query CR;
- no-action share;
- market query orders/turnover;
- explicit source period/granularity.

The second source must not overwrite or reinterpret `ProductQuerySnapshot` facts. The two snapshot types join through the shared exact `SearchQuery` identity and only when period/granularity compatibility is explicit.

## 18. Downstream role and explicit non-goals

This source is intended to support later SCOZ flows without doing their analytics inside the parser:

- PR6: show imported queries for an own SKU so the user can include/exclude genuinely relevant queries;
- PR10: combine saved relevant queries with market Demand/Quality and position-history evidence;
- PR13: use own query-level conversion/position period facts only when compatible time/granularity evidence is sufficient.

Non-goals of this source contract:

- no Query Opportunity scoring/verdict;
- no benchmark selection;
- no cluster aggregation;
- no market-query quality calculation;
- no position-normalized CR model;
- no causality claim between average position and conversion;
- no daily position history reconstruction from a period average;
- no API sync implementation;
- no source-resolution framework;
- no linguistic query normalization.

A period-level average position plus period-level conversion does **not** establish the daily path `position → conversion`. Ramp-up must later return insufficient data unless compatible time-series evidence exists.

## 19. Frozen evidence facts for regression design

Synthetic tests may encode the following **structural/statistical facts** without copying sensitive workbook rows:

- exactly one verified worksheet;
- 564 verified query observations;
- zero formula cells in the used range;
- all verified D:K query cells are non-empty text values;
- 564 distinct exact query texts after approved edge cleanup;
- 15 verified rows have `seen_users > searched_users`;
- 11 verified rows contain source position `0` and therefore map to `SOURCE_ZERO`;
- verified positive positions exceed 1,000;
- search-to-card conversion includes 0%, fractional percentages, and 100%;
- search-to-order conversion evidence includes both 0% and 100%;
- ordered-units evidence includes zero and non-zero values;
- revenue evidence includes zero and non-zero whole-ruble grouped values.

Tests must use synthetic SKU/article/title/query text and synthetic metric values. Do not copy the real evidence workbook or its own-product identity into repository fixtures.

## 20. Acceptance conditions for this contract

This contract is considered correctly implemented only when a future PR5 parser/import path can demonstrate all of the following against synthetic fixtures:

1. exact report detection without filename/sheet-name heuristics;
2. exact metadata and header handling including LF/NBSP code points;
3. shared PR4 `SearchQuery` identity reuse;
4. Product ownership becomes true because the source itself is own-product evidence;
5. `generated_at` stays provenance while period dates define observation identity;
6. duplicate/corrected revision semantics use `Product × SearchQuery × period_start × period_end`;
7. `SOURCE_ZERO` remains distinct from a numeric position and from future `MISSING`;
8. no `seen_users <= searched_users` invariant is imposed;
9. percentages remain percentage points and use `Decimal`;
10. whole-ruble revenue remains `Decimal` without float conversion;
11. seller-query data does not create market `QueryMetricSnapshot`;
12. structural failures do not mutate observations and recoverable row failures remain bounded;
13. real evidence bytes and own-product identifying rows never enter the public repository.
