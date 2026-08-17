# Ozon `explainer_report` Search Visibility XLSX — Source Contract v1

**Status:** Approved factual source contract v1

**Date:** 2026-08-17

**Scope:** only the verified Ozon `explainer_report` XLSX shape documented from the two supplied cluster exports

## 1. Authority, source scope, and evidence provenance

This contract freezes source facts established by direct inspection of two user-supplied Ozon `explainer_report` workbooks. The workbooks are sensitive user input and are **not stored, copied into fixtures, or committed to this repository**. In SCOZ this shape is the source for Search Visibility / Ranking Factors; `explainer_report` is not asserted to be the literal UI report name «Что влияет на место».

The canonical report type is `OZON_SEARCH_VISIBILITY`. The future implementation import kind is `ozon_search_visibility_xlsx`.

Evidence workbook 1:

- filename (evidence only): `explainer_report_17-08-2026_06-55-39.xlsx`;
- SHA-256: `e1fc09066a9462087364919bef94b938d2538a16434168c5a5faeffdcae168aa`;
- byte size: `69817`;
- one worksheet named `Результаты по запросу`;
- physical dimensions: 1,000 rows × 26 columns;
- no merged cells and no formula cells;
- 112 product data rows;
- `Дата: 17/08/2026`;
- `Запрос: смеситель для кухни гибкий`;
- `Время: 03:55 +00`;
- `Регион: г. Москва, Россия`;
- `Сколько позиций в выдаче: 112`.

Evidence workbook 2:

- filename (evidence only): `explainer_report_17-08-2026_06-55-22.xlsx`;
- SHA-256: `f52dc33ad8513bc6dd5746f7461b0f0362f8037c7af8f692af321069618dba68`;
- byte size: `69960`;
- one worksheet named `Результаты по запросу`;
- physical dimensions: 1,000 rows × 26 columns;
- no merged cells and no formula cells;
- 112 product data rows;
- `Дата: 17/08/2026`;
- `Запрос: смеситель для кухни гибкий`;
- `Время: 03:55 +00`;
- `Регион: г. Санкт-Петербург, Россия`;
- `Сколько позиций в выдаче: 112`.

Across the 224 verified product rows, 220 `Отзывы` values use the rating/count form and four use the exact missing sentinel `— ` (U+2014 EM DASH followed by U+0020 SPACE). The sentinel occurs for Product IDs `4218542117` and `4906881609` in both Cluster exports.

Filename and worksheet name are evidence metadata, not report-detection inputs. Detection never uses `explainer_report`, filename, worksheet name, or fuzzy similarity.

### Explicitly excluded evidence

`seller-queries_18.07-14.08.2026_created_2026-08-17_06-56.xlsx` (SHA-256 `dedbd107466fb7a0ca742c0277dd5ef7253da6313fc2a0b8a4bd1f1b538e598b`, byte size `73201`) proves a **different** source shape: own SKU × query × period. It is reserved as factual evidence for PR5 `ProductQuerySnapshot`; a PR4 parser must not support it. This contract does not cover `seller-queries` or implement PR5.

## 2. Physical versus semantic columns

`openpyxl` reports `max_column = 26` because formatting extends through column Z. Actual source structure and business data occupy only A:P. Q:Z contain no business values.

The contract therefore does **not** require exactly 16 physical XLSX columns and must not reject a workbook merely because `max_column == 26`. Style-only or empty formatted cells in Q:Z are allowed. Any non-empty business value outside A:P is incompatible.

## 3. Exact workbook structure

The sole worksheet has this semantic layout:

| Row | Contract |
|---|---|
| 1 | A1 matches exact v1 form `Дата: DD/MM/YYYY`; observed `Дата: 17/08/2026` |
| 2 | A2 is `Запрос: <query>` |
| 3 | A3 matches exact v1 form `Время: HH:MM +00`; observed `Время: 03:55 +00` |
| 4 | A4 is `Регион: <cluster>` |
| 5 | A5 is `Сколько позиций в выдаче: <positive integer>` |
| 6 | A:P is semantically blank |
| 7 | A:P is the exact ordered header signature in section 4 |
| 8 | A:P is semantically blank |
| 9 | source explanatory/help row; never an observation |
| 10 onward | product-row candidates; completely semantically blank trailing rows are ignored |

Semantic blank means Excel `None` or exact zero-length text `""`. Whitespace-only text is not blank. The evidence exposes zero-length strings in some row-8 cells.

Row 9 ordinary text is ignored: it is neither identity nor metrics and is not required as an exact-copy signature. Formula cells anywhere in structural rows 1–9 are unsupported.

## 4. Exact A:P ordered header signature

Row 7 A:P must equal, in order:

1. `Позиция`
2. `ID товара`
3. `Название товара`
4. `Имя селлера`
5. `Сводная оценка`
6. `Статус`
7. `Ставка\nОплата за клик`
8. `Стратегия`
9. `Ставка\nОплата за заказ`
10. `Соответствие запросу`
11. `Отзывы`
12. `Цена для покупателя`
13. `Популярность общая`
14. `Акции от Ozon`
15. `Срок доставки`
16. `Индекс цен`

The newline characters in headers 7 and 9 are source-significant. Aliases, normalization, fuzzy matching, spelling variants, reordering, and invented optional variants are forbidden.

## 5. Deterministic report detection

`report_type = OZON_SEARCH_VISIBILITY` only when all of these conditions hold:

- exactly one worksheet;
- A1 has the expected exact `Дата:` marker and format;
- A2 has the expected exact `Запрос:` marker;
- A3 has the expected exact `Время:` marker and format;
- A4 has the expected exact `Регион:` marker;
- A5 has the expected exact `Сколько позиций в выдаче:` marker;
- row 6 A:P is semantically blank;
- row 7 A:P equals the exact header signature;
- row 8 A:P is semantically blank;
- there are no merged cells;
- there are no non-empty business values in Q onward.

A readable XLSX clearly representing another report is `WRONG_REPORT_TYPE`. Expected markers with incompatible structure are `INCOMPATIBLE_SCHEMA`. An unreadable or non-XLSX package is `UNSUPPORTED_WORKBOOK`. Detection never guesses a near match.

## 6. Query and Cluster identity

### SearchQuery

The source query is the substring after the exact `Запрос:` marker. Its only canonical technical cleanup is removal of leading and trailing U+0020 spaces and U+00A0 NBSP characters. An empty result is fatal invalid metadata.

The resulting exact canonical source text is `SearchQuery` identity. Do not lowercase, case-fold, stem, lemmatize, collapse internal spaces, substitute synonyms, normalize morphology, or semantically/fuzzily match queries. Therefore `смеситель для кухни гибкий` and `смеситель для кухни с гибким изливом` are distinct identities. This exact identity permits PR5 later to reuse a `SearchQuery` when `seller-queries` supplies exactly the same text; PR4 does not implement PR5.

### Cluster

The source cluster is the substring after exact `Регион:`. `Регион` is source vocabulary and maps to the canonical SCOZ domain entity **`Cluster`**; it must not be renamed to Region, SearchRegion, or GeoRegion.

Apply only the same U+0020/U+00A0 edge cleanup. Do not apply fuzzy normalization or aliases. `г. Москва, Россия` and `г. Санкт-Петербург, Россия` are distinct `Cluster` identities. This contract introduces no Cluster aliases.

## 7. Observation time and declared coverage

`observed_at` is formed only from source `Дата` + `Время`. Exact v1 formats are `DD/MM/YYYY` and `HH:MM +00`. The evidence normalizes to the timezone-aware UTC datetime `2026-08-17T03:55:00+00:00`.

File modification, import, filename, and GitHub timestamps are never observation time. Future `imported_at` remains a separate application/provenance fact. Alternative offsets are unsupported.

`Сколько позиций в выдаче: N` is a declared source coverage/count fact. Every row at row 10 or later with any semantically non-blank A:P value is a product-row candidate. Candidate count must equal positive integer N; mismatch is fatal rather than silently corrected. Both evidence files declare 112 and contain 112 candidates.

Coverage means 112 source result rows / observed products, **not** “TOP-112.” Report-level coverage context is query, Cluster, `observed_at`, declared count, candidate count, and—later in import lineage—accepted/skipped/error counts.

## 8. Product identity and ownership boundary

`ID товара` is a real Excel integer cell in both workbooks. V1 requires a positive integer that is not boolean and normalizes it to a decimal digit string mapped to:

- `source = "ozon"`;
- `identity_type = "ozon_product_id"`;
- `identity_value = <digits>`;
- `source_account_scope = ""`.

Title, seller, position, query, Cluster, and worksheet row are not Product identity. A future implementation resolves or creates an unknown Ozon Product ID with `is_owned = False`; this source must never change existing ownership.

The file has no canonical own/competitor flag. Never infer ownership from seller name, title, position, row order, placement near the beginning/end, or known current-user seller text. Ownership remains only `Product.is_owned` from existing SCOZ state/manual selection.

`Название товара` and `Имя селлера` are required non-empty source text, preserved exactly as snapshot/context facts `source_title` and `seller_name`. They are not identity and must never merge Products.

## 9. Position semantics

`Позиция` is the only source position. Its source type is text digits matching `^[1-9][0-9]*$`, normalized to positive integer `position`. Zero, negative, decimal, blank, and em dash are invalid. Never substitute worksheet row number, import ordinal, or candidate-row index.

Both reports contain all positions 1..108 plus four positions above 108:

- Moscow: `1147`, `266`, `561`, `576`;
- Saint Petersburg: `1083`, `227`, `539`, `540`.

Thus a declared count of 112 does not imply positions 1..112 or a top-N cutoff. Rows must not be renumbered.

## 10. Localized source-number policy

Unlike the PR3 Ozon Products report, `explainer_report` numeric metrics are localized text cells. Do not require Excel int/float metric cells and do not reuse PR3 numeric assumptions.

Parsing may remove allowed grouping spaces only where a field format explicitly permits them, replace decimal comma with decimal point for `Decimal` construction, and remove an exact documented unit suffix. Parse directly with `Decimal`, never through float, and perform no generic locale guessing.

## 11. Exact product-row field contracts

All 16 source columns are populated in all 224 verified product rows.

### Overall score

`Сводная оценка` is a localized non-negative decimal string such as `0,052`, `1,000`, or `0,685`, normalized unchanged in scale to `overall_score: Decimal`. It is not a percentage and is not recomputed.

### Promotion status

`Статус` is required non-empty source text preserved exactly as `promotion_status`. `Продвигается` is observed, but v1 does not whitelist that single categorical label or derive a boolean.

### CPC

`Ставка\nОплата за клик` is required localized RUB money text such as `22,32 ₽`, `35,00 ₽`, or `19,19 ₽`. Remove the exact trailing ` ₽`; require comma decimal separator and exactly two fractional digits; normalize to non-negative `cpc_rub: Decimal`. Integer grouping may use only ordinary source RUB grouping spaces. There is no evidenced missing sentinel.

### Promotion strategy

`Стратегия` is required non-empty source text preserved exactly as `promotion_strategy`. Observed examples are `Средняя стоимость клика`, `Автостратегия`, `Целевой расход`, and `Вывод в топ`. V1 does not enumerate or limit future non-empty textual labels.

### CPO: three distinct states

`Ставка\nОплата за заказ` has exactly three evidenced semantic states:

| Source form | Normalized state | Normalized value |
|---|---|---|
| active percent such as `5%`, `9%`, `10%`, `12%` | `cpo_state = ACTIVE` | `cpo_pct = Decimal(value)` |
| exact `Выключено` | `cpo_state = DISABLED` | `cpo_pct = None` |
| exact em dash U+2014 `—` | `cpo_state = UNAVAILABLE` | `cpo_pct = None` |

The active source value is already percentage points: `10%` becomes `Decimal("10")`, not `0.10`. `DISABLED` and `UNAVAILABLE` must never collapse into one state; there is no generic null rule.

### Relevance

`Соответствие запросу` is localized non-negative decimal text such as `74,50`, `89,40`, or `84,10`, normalized unchanged in scale to `relevance_score: Decimal`. Do not append `%`, scale it, or calculate relevance independently.

### Reviews

`Отзывы` has exactly two evidenced source forms in v1:

1. Rating/count text exemplified by `4,8 (180 шт.)`, `4,8 (33 026 шт.)`, and `5,0 (11 шт.)`. Parse the decimal-comma rating and ordinary-space-grouped integer count into `rating: Decimal` and `reviews_count: int`. Thus `4,8 (33 026 шт.)` becomes `Decimal("4.8")` and `33026`. Do not leave count embedded only in source text.
2. The exact missing sentinel `— `, consisting of two Unicode code points: U+2014 EM DASH followed by U+0020 SPACE. Normalize it to `rating = None` and `reviews_count = None`.

The Reviews sentinel is distinct from the CPO sentinel `—`, which is U+2014 alone with no trailing space. Reviews parsing must not apply a generic `strip()` or a generic em-dash-to-null rule: `—`, `-`, ` — `, blank, and `Нет данных` are not accepted Reviews values. Any source form other than the two evidenced forms above is unsupported in v1.

### Buyer price

`Цена для покупателя` is localized whole-ruble money text such as `2 947 ₽`, `1 033 ₽`, or `17 338 ₽`, allowing standard ordinary-space grouping and normalizing to `buyer_price_rub: Decimal`. Decimal cents are not supported in v1. This is the current price without Ozon-card discount according to the source explanation; it must not be interpreted as Ozon Card price.

### Popularity

`Популярность общая` is localized non-negative decimal text such as `2,60`, `87,70`, or `100,00`, normalized unchanged in scale to `popularity_score: Decimal`. It is not labeled as a percentage, divided by 100, or recomputed.

### Ozon promotion

`Акции от Ozon` supports exactly `Да` → `ozon_promotion = True` and `Нет` → `ozon_promotion = False`. Other values are invalid in v1.

### Delivery

`Срок доставки` matches exact semantic pattern `^([0-9]+)-([0-9]+) (день|дня|дней)$`, with minimum no greater than maximum. Observed values include `0-1 день`, `1-2 дня`, `2-3 дня`, `3-4 дня`, `4-5 дней`, `6-7 дней`, and `15-36 дней`.

Preserve and split all three facts: exact source `delivery_label`, integer `delivery_min_days`, and integer `delivery_max_days`. Do not average the range or infer a single delivery day.

### Price index

`Индекс цен` is localized decimal percentage text such as `0,0%`, `5,0%`, `10,0%`, `12,5%`, `15,0%`, `17,5%`, or `20,0%`, normalized to `price_index_pct: Decimal`. The source is already percentage points: `5,0%` becomes `Decimal("5")`, not `0.05`. Do not recompute it.

## 12. Missing-value semantics

The evidence contains no generic blank metric fields. It proves exactly two field-specific semantic missing cases:

1. CPO accepts exact `—` (U+2014 alone) and normalizes it to `cpo_state = UNAVAILABLE` and `cpo_pct = None`, distinct from `Выключено`/`DISABLED`.
2. Reviews accepts exact `— ` (U+2014 followed by U+0020) and normalizes it to `rating = None` and `reviews_count = None`.

These forms are not interchangeable, and there is no generic em-dash-to-null rule. No other field has an evidenced missing sentinel.

There is no generic `blank → None`, `"-" → None`, `"Нет данных" → None`, or `0 → None` behavior. An unexpected blank, string, or sentinel in a required field is a row validation error. Explicit numeric zero remains zero.

## 13. Exact snapshot source-value payload

For duplicate/revision hashing, the normalized source-value payload contains exactly these 19 fields, in this order:

1. `source_title`
2. `seller_name`
3. `position`
4. `overall_score`
5. `promotion_status`
6. `cpc_rub`
7. `promotion_strategy`
8. `cpo_state`
9. `cpo_pct`
10. `relevance_score`
11. `rating`
12. `reviews_count`
13. `buyer_price_rub`
14. `popularity_score`
15. `ozon_promotion`
16. `delivery_label`
17. `delivery_min_days`
18. `delivery_max_days`
19. `price_index_pct`

When the exact Reviews sentinel `— ` is present, fields 11 and 12 remain in this canonical 19-field payload with `rating = None` and `reviews_count = None`; the payload composition and order do not change.

Do not include `product_id`, `search_query_id`, `cluster_id`, `observed_at`, `revision`, `supersedes_snapshot_id`, `payload_sha256`, `import_batch_id`, `source_artifact_id`, or `imported_at`: those are identity, logical-key, revision, or provenance fields. Decimal hashing must later reuse canonical deterministic decimal text and never float serialization.

## 14. Logical observation key and immutable revisions

The canonical logical key is:

> Product × SearchQuery × Cluster × `observed_at`

Its future implementation form is `product_id + search_query_id + cluster_id + observed_at`. `position` is payload, never logical-key material. A changed position or factor for the same Product/query/Cluster/time is a corrected revision.

Reuse the canonical SCOZ immutable convention:

- same logical key + same normalized payload → `DUPLICATE`, with no new snapshot row;
- same logical key + changed payload → `CORRECTED`, as a new immutable revision superseding the prior revision;
- different Cluster, SearchQuery, or `observed_at` → independent observation revision 1.

Historical rows are never updated in place.

## 15. In-file duplicate policy

Each verified workbook has 112 unique Product IDs and no duplicate Product ID. V1 remains deterministic if a variant contains duplicates:

- same Product ID twice with the same normalized payload → deduplicate as identical input duplicate with warning/count;
- same Product ID twice with different normalized payload → fatal conflicting observation report.

Position uniqueness is not Product identity.

## 16. Formula and merged-cell policy

The evidence contains zero formulas. A formula in structural rows 1–9 is fatal incompatible schema. A formula in any product-row A:P source cell is a recoverable invalid row. Formulas are never evaluated as trusted source data; a future parser must load with `data_only=False`.

Both evidence workbooks contain zero merged cells. Any merged cell is unsupported in Source Contract v1 and makes the workbook incompatible.

## 17. Fatal report errors versus recoverable row errors

Fatal report-level conditions are:

- unreadable XLSX;
- wrong report type;
- multiple worksheets;
- incompatible metadata structure;
- invalid observed date/time;
- empty query;
- empty Cluster;
- invalid declared row count;
- declared count different from candidate count;
- bad header signature;
- merged cells;
- non-empty business values in Q onward;
- structural formula;
- conflicting same-Product input observations.

Recoverable row-level conditions are:

- invalid Product ID;
- invalid position;
- invalid localized numeric source value;
- invalid CPO state;
- invalid reviews format;
- invalid delivery format;
- unexpected missing row value;
- product-row formula.

The exact Reviews sentinel `— ` is a valid source value. It is neither `invalid reviews format` nor `unexpected missing row value`, and it does not cause the row to be skipped. Any other unsupported Reviews format remains a recoverable row error.

If zero usable product rows remain, the import outcome is fatal. Exact application error classes/codes belong to a later PR4 Implementation Spec, not this factual contract.

## 18. Cross-Cluster factual evidence

The reports have the same SearchQuery and `observed_at`, but different Clusters. Of their Product IDs, 96 appear in both reports, 16 are Moscow-only, and 16 are Saint-Petersburg-only. Among the 96 shared Products, Cluster values differ materially, including position and ranking factors.

Therefore Cluster is mandatory logical-key material. Observations across Clusters must never collapse.

## 19. Source facts only

A parser may only extract identity, parse exact localized representations, split explicit composite fields, normalize source date/time, normalize specified technical edge whitespace, and preserve source categorical text.

It must not calculate ranking score, relevance, popularity, price index, delivery average, CPC/CPO conversion, overall ranking factor, or weighted Cluster score. These columns are source facts, not parser analytics.

## 20. Unsupported / not confirmed in v1

The following are explicitly unsupported rather than guessed:

- multiple worksheets;
- merged cells;
- shifted metadata, header, or data rows;
- header aliases or reordering;
- non-empty source columns beyond P;
- alternative date/time formats;
- non-UTC `Время` offsets;
- alternative query metadata marker;
- alternative Cluster metadata marker;
- formula exports;
- alternative Product ID cell types;
- missing/sentinel variants not evidenced;
- alternative reviews text format;
- decimal buyer prices;
- alternative CPO labels/states;
- alternative delivery representation;
- semantic/fuzzy query matching;
- Cluster aliases;
- multiple queries in one explainer workbook;
- multiple Clusters in one explainer workbook.

Any future source variant requires new factual evidence and a contract revision.

## 21. Compatibility and versioning policy

This is a strict Source Contract v1 for the evidenced `explainer_report` shape. Ozon changing its export does not authorize parser guessing. Unsupported variants must fail clearly.

Broadening support requires this sequence:

> new real source artifact → factual inspection → approved contract revision → implementation update

## 22. Explicit non-goals

This Source Contract does not design SQLite schema, migration 003, repositories, FastAPI routes, UI, import archive lifecycle, coverage UI, analytics, heatmap, benchmark, PR5 `seller-queries`, MPStats, or Ozon API sync. Those belong to later PR-specific Implementation Specs and implementation PRs.
