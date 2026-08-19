# SCOZ PR5 — Query Metrics & Own Product Queries — Implementation Spec

**Status:** Approved implementation specification

**Date:** 2026-08-19

**PR:** PR5 only

**Base main:** `8e85410b9d818ef743c5d543b6c3f8f37b34097a`

**Source authorities:**

- [`2026-08-18-ozon-seller-queries-xlsx-source-contract-v1.md`](./2026-08-18-ozon-seller-queries-xlsx-source-contract-v1.md)
- [`2026-08-19-ozon-query-metrics-xlsx-source-contract-v1.md`](./2026-08-19-ozon-query-metrics-xlsx-source-contract-v1.md)

## 1. Purpose, authority, and result

PR5 completes the query-data part of the Foundation & Data Plane. It implements two verified Ozon XLSX source families in one implementation PR while preserving their different semantics:

1. Ozon «Запросы моего товара» (`seller-queries`) → immutable `ProductQuerySnapshot` history;
2. Ozon market-level search-query metrics (`queries_report`) → immutable `QueryMetricSnapshot` history.

The Source Contracts are authoritative for source structure, source values, source-specific sentinels, semantic meaning, duplicate rules, and unsupported shapes. This Implementation Spec defines how those facts enter the current SCOZ architecture.

The two source verticals are deliberately independent. They share only infrastructure and identities that are objectively shared: existing `SearchQuery`, existing `Product`, import lineage, source-artifact/archive conventions, the process-local import lock, and narrow mechanical file helpers. PR5 must not create a generic query-import framework.

Canonical report/import pairs:

- `OZON_OWN_PRODUCT_QUERIES` / `ozon_seller_queries_xlsx`;
- `OZON_QUERY_METRICS` / `ozon_query_metrics_xlsx`.

The PR5 result is a trustworthy query data plane. It does not implement Query Opportunity, relevant-query selection, benchmarks, diagnostics, heatmaps, MPStats position history, Ramp-up, or API sync.

## 2. Architectural decision

PR5 remains one PR with two isolated semantic verticals:

```text
seller-queries XLSX
  → ozon_seller_queries_xlsx parser
  → ProductQuery domain
  → ProductQuerySnapshotRepository
  → ozon_seller_queries_import service
  → POST /api/imports/ozon-seller-queries

queries_report XLSX
  → source-specific XLSX compatibility read-copy
  → ozon_query_metrics_xlsx parser
  → QueryMetric domain
  → QueryMetricSnapshotRepository
  → ozon_query_metrics_import service
  → POST /api/imports/ozon-query-metrics
```

Shared existing boundaries:

```text
SearchDimensionRepository.resolve_search_query()
ProductRepository
ImportBatch / SourceArtifact
IMPORT_LOCK
archive under data/imports
GET /api/imports
Data page
```

Shared code is allowed only for mechanical XLSX staging/archive behavior that is already duplicated by PR3/PR4. Semantic parsing, validation, domain objects, repositories, import results, and source-specific errors remain separate.

## 3. Explicit non-goals

PR5 does not implement:

- `RelevantQueryScope` or query include/exclude UI;
- benchmark candidate selection or `BenchmarkSet*`;
- competitor photos or MPStats;
- Query Opportunity, Query Demand verdicts, market-quality verdicts, or any score;
- Search Visibility heatmap;
- `SearchPositionSnapshot`;
- Diagnostics;
- advertising data or Ramp-up;
- Ozon public API sync;
- credentials/keystore;
- a generic import framework, source registry, plugin/callback report processor, or source-resolution framework;
- a universal nullable `QueryObservation` table;
- fuzzy, linguistic, stemmed, case-folded, synonym, keyboard-layout, or other query normalization;
- new runtime dependencies, pandas, npm, a frontend framework, a worker queue, or persistent jobs;
- refactoring working PR3/PR4 import services merely to make them use new PR5 helpers.

PR5 may add narrow reusable mechanical helpers to `backend/application/import_runtime.py`, but existing PR3/PR4 behavior must remain unchanged unless a regression test proves a necessary compatibility fix.

## 4. Shared SearchQuery identity

Reuse the PR4 `search_queries` table and `SearchDimensionRepository.resolve_search_query()` exactly as they exist on current `main`.

Canonical query identity for both PR5 sources is the exact source query text after only the Source Contract edge cleanup:

- remove leading/trailing U+0020 ordinary spaces;
- remove leading/trailing U+00A0 NBSP;
- resulting text must be non-empty.

Do not lowercase, case-fold, collapse internal spaces, replace `ё`, remove punctuation, stem, lemmatize, rewrite misspellings, interpret numeric-looking queries as Product IDs, or use fuzzy matching.

The same exact `SearchQuery` row must be reused across PR4 Search Visibility, PR5 seller-queries, and PR5 Query Metrics.

## 5. ProductQuery domain contract

Create `backend/domain/product_query.py`.

Freeze:

```python
class ProductQueryPositionState(str, Enum):
    KNOWN = "KNOWN"
    SOURCE_ZERO = "SOURCE_ZERO"

@dataclass(frozen=True)
class ProductQuerySnapshot:
    id: int
    product_id: int
    search_query_id: int
    period_start: date
    period_end: date
    revision: int
    supersedes_snapshot_id: int | None
    payload_sha256: str
    import_batch_id: int
    source_artifact_id: int
    imported_at: datetime
    searched_users: int
    seen_users: int
    position_state: ProductQueryPositionState
    average_position: int | None
    search_to_card_conversion_pct: Decimal
    search_to_order_conversion_pct: Decimal
    ordered_units: int
    ordered_revenue_rub: Decimal
```

Exact logical key:

> `Product × SearchQuery × period_start × period_end`

`generated_at`, source article, source title, import time, worksheet row, and filename are not part of the logical key.

The payload hash contains exactly these eight source facts in this field order:

```text
searched_users
seen_users
position_state
average_position
search_to_card_conversion_pct
search_to_order_conversion_pct
ordered_units
ordered_revenue_rub
```

`KNOWN` requires positive `average_position`; `SOURCE_ZERO` requires `average_position is None`. Do not create a `MISSING` enum value in PR5 because the verified XLSX v1 does not produce that state.

Percentages are `Decimal` percentage points. Revenue is `Decimal` RUB. No float enters the domain or payload hash.

Reuse the existing canonical plain-decimal text convention used by Product/Search Visibility payload hashing. Hash enum values as their string values and `None` as JSON null.

Revision semantics:

- no existing logical key → insert revision 1 / `NEW`;
- same key + same normalized payload hash → `DUPLICATE`, no insert;
- same key + changed payload hash → append immutable revision / `CORRECTED`, set `supersedes_snapshot_id` to previous current revision;
- different period pair → independent observation revision 1.

## 6. QueryMetric domain contract

Create `backend/domain/query_metric.py`.

Freeze:

```python
@dataclass(frozen=True)
class QueryMetricSnapshot:
    id: int
    search_query_id: int
    period_start: date
    period_end: date
    revision: int
    supersedes_snapshot_id: int | None
    payload_sha256: str
    import_batch_id: int
    source_artifact_id: int
    imported_at: datetime
    popularity_users: int
    dynamics_28d_pct: Decimal | None
    dynamics_7d_pct: Decimal | None
    cart_add_users: int
    market_cart_conversion_pct: Decimal
    unique_buyers_with_orders: int
    market_order_conversion_pct: Decimal
    ordered_revenue_rub: Decimal
    no_action_queries: int
    no_action_share_pct: Decimal
```

Exact logical key:

> `SearchQuery × period_start × period_end`

There is no Product dimension and no Cluster dimension in this source or table.

The payload hash contains exactly these ten source facts in this order:

```text
popularity_users
dynamics_28d_pct
dynamics_7d_pct
cart_add_users
market_cart_conversion_pct
unique_buyers_with_orders
market_order_conversion_pct
ordered_revenue_rub
no_action_queries
no_action_share_pct
```

`dynamics_*` is nullable only for the exact source `-` sentinel. Market conversion fields remain market/query-level facts and must never be renamed or exposed as own-product or competitor conversion. `no_action_share_pct` is not capped at 100; source-reported values above 100 percentage points remain valid. Revenue preserves source numeric precision.

Revision behavior is the same `NEW` / `DUPLICATE` / `CORRECTED` convention but uses the QueryMetric logical key only.

## 7. SnapshotWriteKind reuse

Reuse the existing `SnapshotWriteKind` values `NEW`, `DUPLICATE`, `CORRECTED` from current code. PR5 does not need a new write-status abstraction.

A neutral relocation of this enum is not required for PR5 and must not be done merely for naming cleanliness. If implementation cannot avoid a circular dependency without relocation, a mechanical move to a neutral domain module is permitted only with no behavior change and with PR3/PR4 regression coverage. Otherwise leave the current enum location unchanged.

Each new repository defines its own typed write-result dataclass containing the reused `SnapshotWriteKind` plus its own snapshot type.

## 8. Migration 004

Create one migration:

`backend/persistence/migrations/migration_004_pr5_query_data.py`

Register it as migration version 4 after current migration 003.

The migration creates two independent snapshot tables and adds only the report-level lineage context required for durable history of the two PR5 sources.

### 8.1. `product_query_snapshots`

Required columns:

```text
id INTEGER PRIMARY KEY AUTOINCREMENT
product_id INTEGER NOT NULL REFERENCES products(id)
search_query_id INTEGER NOT NULL REFERENCES search_queries(id)
period_start TEXT NOT NULL
period_end TEXT NOT NULL
revision INTEGER NOT NULL CHECK (revision > 0)
supersedes_snapshot_id INTEGER NULL REFERENCES product_query_snapshots(id)
payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64)
import_batch_id INTEGER NOT NULL REFERENCES import_batches(id)
source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id)
imported_at TEXT NOT NULL
searched_users INTEGER NOT NULL CHECK (searched_users >= 0)
seen_users INTEGER NOT NULL CHECK (seen_users >= 0)
position_state TEXT NOT NULL CHECK (position_state IN ('KNOWN','SOURCE_ZERO'))
average_position INTEGER NULL
search_to_card_conversion_pct TEXT NOT NULL
search_to_order_conversion_pct TEXT NOT NULL
ordered_units INTEGER NOT NULL CHECK (ordered_units >= 0)
ordered_revenue_rub TEXT NOT NULL
```

Checks:

- `period_start <= period_end` at domain/repository boundary; DB stores ISO dates;
- `KNOWN` iff `average_position` is non-null and positive;
- `SOURCE_ZERO` iff `average_position` is null;
- uniqueness: `(product_id, search_query_id, period_start, period_end, revision)`.

Indexes only for current/history access and lineage:

```text
(product_id, period_end DESC, search_query_id, revision DESC)
(search_query_id, product_id, period_end DESC, revision DESC)
(import_batch_id)
(source_artifact_id)
```

### 8.2. `query_metric_snapshots`

Required columns:

```text
id INTEGER PRIMARY KEY AUTOINCREMENT
search_query_id INTEGER NOT NULL REFERENCES search_queries(id)
period_start TEXT NOT NULL
period_end TEXT NOT NULL
revision INTEGER NOT NULL CHECK (revision > 0)
supersedes_snapshot_id INTEGER NULL REFERENCES query_metric_snapshots(id)
payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64)
import_batch_id INTEGER NOT NULL REFERENCES import_batches(id)
source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id)
imported_at TEXT NOT NULL
popularity_users INTEGER NOT NULL CHECK (popularity_users >= 0)
dynamics_28d_pct TEXT NULL
dynamics_7d_pct TEXT NULL
cart_add_users INTEGER NOT NULL CHECK (cart_add_users >= 0)
market_cart_conversion_pct TEXT NOT NULL
unique_buyers_with_orders INTEGER NOT NULL CHECK (unique_buyers_with_orders >= 0)
market_order_conversion_pct TEXT NOT NULL
ordered_revenue_rub TEXT NOT NULL
no_action_queries INTEGER NOT NULL CHECK (no_action_queries >= 0)
no_action_share_pct TEXT NOT NULL
```

Uniqueness: `(search_query_id, period_start, period_end, revision)`.

Indexes:

```text
(search_query_id, period_end DESC, revision DESC)
(period_end DESC, search_query_id, revision DESC)
(import_batch_id)
(source_artifact_id)
```

Do not add speculative Query Opportunity indexes in PR5.

### 8.3. PR5 import metadata on `import_batches`

Add nullable columns:

```text
period_start TEXT NULL
period_end TEXT NULL
report_generated_at TEXT NULL
report_product_ozon_id TEXT NULL
sort_context TEXT NULL
```

Meaning:

- `period_start` / `period_end`: PR5 source period for either PR5 report;
- `report_generated_at`: seller-queries only; source-generated timezone-aware UTC timestamp;
- `report_product_ozon_id`: seller-queries report-level Ozon Product ID only;
- `sort_context`: Query Metrics exact supported source sort line only.

These fields exist so FAILED/NO_USABLE_ROWS import history can retain known report context even when no snapshot rows were committed. Do not add seller article/title columns or a report-context table in PR5.

## 9. Repositories

Create:

- `backend/persistence/repositories/product_query_snapshots.py`;
- `backend/persistence/repositories/query_metric_snapshots.py`.

Each repository owns all SQL for its snapshot table and exposes at minimum:

- retrieval by snapshot ID for tests/domain reconstruction;
- current revision lookup by exact logical key;
- `resolve_revision(...)` implementing immutable `NEW` / `DUPLICATE` / `CORRECTED` semantics.

Repositories must validate canonical date/Decimal/state invariants before storage, store Decimal as canonical plain text, and reconstruct exact domain values without float conversion.

No SQL may enter parsers, application services, FastAPI routes, or frontend code.

Do not create a generic SnapshotRepository.

## 10. Seller-queries parser DTOs and errors

Freeze in `backend/domain/product_query.py`:

```python
@dataclass(frozen=True)
class ProductQueryRowError:
    row: int
    code: str
    message: str

@dataclass(frozen=True)
class ParsedProductQueryRow:
    source_row: int
    query_text: str
    snapshot_values: dict[str, object]
    payload_sha256: str

@dataclass(frozen=True)
class ParsedSellerQueriesReport:
    generated_at: datetime
    period_start: date
    period_end: date
    ozon_product_id: str
    article: str
    title: str
    rows_seen: int
    rows: tuple[ParsedProductQueryRow, ...]
    row_errors: tuple[ProductQueryRowError, ...]
    duplicate_input_rows: int
    warnings_count: int
```

Fatal error hierarchy:

```text
OzonSellerQueriesError
SellerQueriesUnsupportedWorkbook
SellerQueriesWrongReportType
SellerQueriesIncompatibleReportSchema
SellerQueriesInvalidGeneratedAt
SellerQueriesInvalidReportPeriod
SellerQueriesInvalidProductContext
SellerQueriesConflictingObservationRows
SellerQueriesNoUsableRows
SellerQueriesConcurrentImportConflict
SellerQueriesUploadTooLarge
SellerQueriesUnsupportedUploadMediaType
SellerQueriesImportPersistenceError
```

Recommended row error codes/messages:

| Condition | Code | User message |
|---|---|---|
| invalid/empty query | `INVALID_QUERY` | `Некорректный поисковый запрос.` |
| searched users | `INVALID_SEARCHED_USERS` | `Некорректно указано количество искавших.` |
| seen users | `INVALID_SEEN_USERS` | `Некорректно указано количество увидевших.` |
| position | `INVALID_POSITION` | `Некорректная позиция товара.` |
| either conversion | `INVALID_CONVERSION` | `Некорректное значение конверсии.` |
| ordered units | `INVALID_ORDERED_UNITS` | `Некорректно указано количество заказов.` |
| ordered revenue | `INVALID_REVENUE` | `Некорректная сумма заказов.` |

A formula in a query row maps to the most specific applicable row error and is never evaluated.

## 11. Seller-queries strict parser

Create `backend/ingestion/ozon_seller_queries_xlsx.py` with the sole public parser:

```python
parse_ozon_seller_queries_xlsx(path: Path) -> ParsedSellerQueriesReport
```

Use the approved seller-queries Source Contract exactly. Do not detect by filename or worksheet name and do not fuzzy-match headers. It must preserve exact LF/NBSP header code points.

Use `openpyxl` with `data_only=False` in normal workbook mode. Because application staging uses `.upload-<uuid>.part`, open the staged path as a binary file-like object and pass that stream to `openpyxl`; do not rely on the `.part` pathname extension. Keep the binary handle alive through `workbook.close()`. Normal mode is preferred because this verified source is small and PR5 needs deterministic merged-cell/formula inspection. No new dependency is permitted.

The parser must distinguish readable clearly different reports as `WRONG_REPORT_TYPE`; expected seller-queries markers with incompatible seller layout are `INCOMPATIBLE_REPORT_SCHEMA`; unreadable/non-XLSX remains `UNSUPPORTED_WORKBOOK`.

Parse `generated_at` only from source rows 1–2 and support the verified `+00` form. Parse `period_start` and `period_end` only from source rows 3–4. Filename/import/filesystem times are not substitutes.

Row 8 Ozon SKU is a positive decimal-digit identity. Article/title are required report context but are not Product identity, payload, or revision material.

For query rows D:K, implement only field-specific Source Contract parsing. Do not create a generic locale parser. Preserve surprising but field-valid source facts; in particular do not require `seen_users <= searched_users` and do not recompute any conversion/revenue/count relationship.

Source position `0` becomes `SOURCE_ZERO` + `average_position=None`; a positive integer becomes `KNOWN` + the exact positive value. Blank or unsupported position text is row-invalid.

Identical in-file duplicate canonical query + identical eight-field payload is warning/dedupe to one normalized row. Conflicting duplicate payload for the same logical in-file observation is fatal `SellerQueriesConflictingObservationRows`.

The parser may return zero valid rows plus row errors; the application service then produces `NO_USABLE_ROWS` and commits no SearchQuery/Product/snapshot mutation.

## 12. Query Metrics XLSX compatibility boundary

Create:

`backend/ingestion/ozon_query_metrics_xlsx_compat.py`

This is a source-specific compatibility helper, not a generic XLSX repair utility.

Public responsibility:

```python
prepare_query_metrics_read_copy(original_path: Path, read_copy_path: Path) -> None
```

The original staged upload remains untouched.

The compatibility copy may normalize only the two evidenced non-business style values in `xl/styles.xml`:

```text
horizontal="Left"  → horizontal="left"
horizontal="Right" → horizontal="right"
```

Do not lowercase arbitrary XML, rewrite styles generally, alter worksheet business values, repair unknown corruption, or change the original upload.

The verified `<dimension ref="A1">` metadata is not authoritative coverage. The preferred implementation must not rewrite worksheet dimension at all. Actual business bounds/candidate rows are determined from real worksheet cells/raw worksheet XML, not `Worksheet.calculate_dimension()`, stored `max_row`, or the package dimension declaration.

Only if an implementation test proves the chosen openpyxl mode physically cannot access cells because of the incorrect dimension may the read-copy helper rewrite that single dimension based on actual worksheet XML cell references. Such rewriting must be narrowly tested and must not alter business cells. The default design is to avoid it.

The compatibility copy is transient:

- filename pattern `.readcopy-<uuid>.xlsx` under `data/imports`;
- not a SourceArtifact;
- not archived;
- not hashed as the uploaded source;
- always removed after parsing, including failures;
- startup recovery removes stale `.readcopy-*` files.

If source-package ZIP/XML is unreadable even after the exact approved compatibility operation, classify as `UNSUPPORTED_WORKBOOK`. Filesystem failure while creating/removing the read-copy maps to import persistence failure, not source-schema failure.

## 13. Exact numeric extraction for Query Metrics

The Query Metrics source contains native Excel numeric cells and revenue can carry more precision than the rendered display. PR5 must not make binary float the canonical source representation when the exact XLSX `<v>` numeric text is available.

The query-metrics ingestion implementation therefore uses two views of the same read-compatible package:

1. `openpyxl(data_only=False)` for workbook structure, string resolution, formula/merged-cell inspection, and user-facing source text;
2. a narrow stdlib `zipfile` + XML reader for exact raw numeric `<v>` text by cell coordinate in the sole worksheet.

The XML reader must derive the actual worksheet package path from workbook relationships rather than assume `xl/worksheets/sheet1.xml`. It may be private to `ozon_query_metrics_xlsx.py` or the source-specific compatibility module; it is not a general spreadsheet framework.

For B:K numeric fields, parse the exact `<v>` text into `Decimal` first, then validate integral/count or field-specific fractional rules. Never use `Decimal(binary_float)` and do not derive source values from display formatting.

For percentage-fraction fields, multiply the exact Decimal source fraction by 100 to obtain canonical percentage points. For exact dynamics sentinel `-`, store `None`. Query text remains a string resolved from the workbook. Formula cells are rejected before any cached `<v>` value is considered.

## 14. Query Metrics parser DTOs and errors

Freeze in `backend/domain/query_metric.py`:

```python
@dataclass(frozen=True)
class QueryMetricRowError:
    row: int
    code: str
    message: str

@dataclass(frozen=True)
class ParsedQueryMetricRow:
    source_row: int
    query_text: str
    snapshot_values: dict[str, object]
    payload_sha256: str

@dataclass(frozen=True)
class ParsedQueryMetricsReport:
    period_start: date
    period_end: date
    sort_context: str
    rows_seen: int
    rows: tuple[ParsedQueryMetricRow, ...]
    row_errors: tuple[QueryMetricRowError, ...]
    duplicate_input_rows: int
    warnings_count: int
```

Fatal error hierarchy:

```text
OzonQueryMetricsError
QueryMetricsUnsupportedWorkbook
QueryMetricsWrongReportType
QueryMetricsIncompatibleReportSchema
QueryMetricsInvalidReportPeriod
QueryMetricsConflictingObservationRows
QueryMetricsNoUsableRows
QueryMetricsConcurrentImportConflict
QueryMetricsUploadTooLarge
QueryMetricsUnsupportedUploadMediaType
QueryMetricsImportPersistenceError
```

Unsupported/altered sort context is part of incompatible source structure and maps to `INCOMPATIBLE_REPORT_SCHEMA`; do not create a separate public sort error code.

Recommended row error codes:

```text
INVALID_QUERY
INVALID_POPULARITY
INVALID_DYNAMICS
INVALID_CART_ADD_USERS
INVALID_MARKET_CONVERSION
INVALID_UNIQUE_BUYERS
INVALID_REVENUE
INVALID_NO_ACTION_QUERIES
INVALID_NO_ACTION_SHARE
```

Messages must be human-readable Russian descriptions and must not expose raw traceback, local file paths, XML internals, or source-cell contents beyond the bounded row context required for the user to fix a row.

## 15. Query Metrics strict parser

Create `backend/ingestion/ozon_query_metrics_xlsx.py`:

```python
parse_ozon_query_metrics_xlsx(path: Path) -> ParsedQueryMetricsReport
```

It receives the transient `.readcopy-<uuid>.xlsx`, not the original archived artifact path, so normal openpyxl filename validation is valid. Use `data_only=False` and normal workbook mode to make formula/merged-cell inspection deterministic.

Implement the Query Metrics Source Contract exactly: one worksheet, period in A1, exact supported sort line in A2, exact A:K header row 3, row 4 help ignored as observations, data rows from 5 onward, no merged cells, no non-empty business values in L onward, and no requirement that the report contain exactly 10,000 rows.

Formula policy is exact: formulas in structural rows 1–4 are fatal incompatible schema; a formula in candidate row A:K makes that candidate row recoverably invalid. Cached formula values are never accepted as source literals.

Do not trust stored worksheet dimension `A1`. Determine candidate rows from actual cell references/content. Completely semantically blank trailing rows are ignored.

Report discrimination is deterministic. PR3 Products, PR4 Search Visibility, and PR5 seller-queries shapes are `WRONG_REPORT_TYPE`; damaged expected Query Metrics markers/schema are `INCOMPATIBLE_REPORT_SCHEMA`; unreadable packages are `UNSUPPORTED_WORKBOOK`.

There is no source `generated_at`. Do not infer one from filename or import time.

Field behavior follows the Source Contract exactly:

- `popularity_users`, `cart_add_users`, `unique_buyers_with_orders`, `no_action_queries`: exact non-negative native numeric integers; bool rejected;
- `dynamics_28d_pct` / `dynamics_7d_pct`: exact native numeric source value × 100 to Decimal percentage points, or exact string `-` → `None`; large positive/negative values are not clipped;
- market cart/order conversion: exact native numeric fraction in 0..1 inclusive × 100;
- revenue: exact non-negative native numeric Decimal preserving underlying precision;
- no-action share: exact non-negative source fraction × 100; values above 100 percentage points are valid when source-reported;
- no cross-field arithmetic repair or recomputation.

Numeric-looking query text remains `SearchQuery` text.

Identical duplicate canonical query + payload in one file warns/dedupes; conflicting payload for the same query/period is fatal.

A structurally valid report may produce zero usable rows; application handles `NO_USABLE_ROWS` without SearchQuery/snapshot mutation.

## 16. Narrow shared mechanical upload helpers

Extend `backend/application/import_runtime.py` only with mechanical helpers needed by both new PR5 import services.

Freeze a small immutable result shape, for example:

```python
@dataclass(frozen=True)
class StagedXlsxUpload:
    original_name: str
    staged_path: Path
    sha256: str
    byte_size: int
```

Required helper responsibilities:

```text
stage_xlsx_upload(...)
  validate safe .xlsx filename
  create .upload-<uuid>.part
  stream in bounded chunks
  enforce existing 25 MiB limit
  SHA-256 the ORIGINAL bytes
  flush + fsync
  return staged metadata

publish_staged_archive(...)
  reserve timestamp+sha .xlsx path exclusively
  move the ORIGINAL staged file
  return final path + imports/... stored_relpath
```

Internal mechanical exceptions may distinguish unsupported extension, size limit, and filesystem/archive collision so each source-specific application service can map them to its own domain errors.

These helpers must know nothing about report type, parser callbacks, SearchQuery, Product, ImportBatch, source-specific errors, snapshots, or analytics.

Do not rewrite PR3/PR4 application services in PR5 to use these helpers unless required by a test-proven bug.

## 17. Seller-queries application service

Create `backend/application/ozon_seller_queries_import.py`.

Canonical lifecycle:

```text
acquire shared IMPORT_LOCK nonblocking
→ stage ORIGINAL through shared mechanical helper
→ create RUNNING ImportBatch(kind=ozon_seller_queries_xlsx)
→ create SourceArtifact for ORIGINAL sha/size/name
→ parse staged ORIGINAL
→ if zero usable: durable FAILED, no domain mutation, remove staged
→ publish ORIGINAL archive
→ one transaction:
     set SourceArtifact stored_relpath
     resolve/create Product by exact Ozon identity
     set Product.is_owned=True
     resolve/reuse SearchQuery for each valid row
     resolve ProductQuerySnapshot revision per row
     finish batch SUCCESS/PARTIAL_SUCCESS with PR5 report context/counts
→ return result
```

Product resolution uses existing Ozon external identity semantics. Unknown Product is created/reused and becomes owned because this verified source is positive own-product evidence. Existing false ownership becomes true. Existing true stays true.

Ownership update, new SearchQuery creation, and ProductQuerySnapshot writes occur in the same transaction. A persistence failure must not leave ownership changed without the snapshots/import result.

This import does not create `ProductSnapshot`. The current `/api/products` catalog remains PR3-backed; a seller-queries-only Product may exist and be owned in storage but stays hidden from the normal Product catalog until a PR3 ProductSnapshot exists.

Seller article/title remain parser/report context only and are not persisted into ProductSnapshot or used as identity.

## 18. Query Metrics application service

Create `backend/application/ozon_query_metrics_import.py`.

Canonical lifecycle:

```text
acquire shared IMPORT_LOCK nonblocking
→ stage ORIGINAL through shared mechanical helper
→ create RUNNING ImportBatch(kind=ozon_query_metrics_xlsx)
→ create SourceArtifact for ORIGINAL sha/size/name
→ create .readcopy-<uuid>.xlsx from ORIGINAL with source-specific style compatibility
→ parse read-copy using exact raw numeric XML + openpyxl structure
→ delete read-copy
→ if zero usable: durable FAILED, no SearchQuery/snapshot mutation, remove staged
→ publish ORIGINAL archive
→ one transaction:
     set SourceArtifact stored_relpath
     resolve/reuse SearchQuery per valid row
     resolve QueryMetricSnapshot revision per row
     finish batch SUCCESS/PARTIAL_SUCCESS with period/sort/counts
→ return result
```

`ozon_query_metrics_import.py` must not import/use `ProductRepository` or Cluster persistence. A Product dependency in this service is an architectural failure unless the Source Contract is explicitly revised later.

The archived file is always the original staged upload, never the read-compatible copy.

## 19. Failure and compensation contract

Both PR5 imports follow the current PR4 lifecycle semantics.

Before ImportBatch exists:

- shared import lock busy → 409, `result=null`, no filesystem/DB side effects beyond harmless transient cleanup;
- wrong extension/non-multipart → 415, `result=null`;
- upload exceeds 25 MiB → 413, `result=null`, staged partial removed;
- staging filesystem failure → 500 persistence error, `result=null`.

After ImportBatch + SourceArtifact exist:

- fatal structural/parser error → durable FAILED result where possible; no domain observations; staged/read-copy removed; source-artifact metadata remains but `stored_relpath` may remain null because the failed source was not published;
- zero usable rows → durable FAILED with known report context and bounded row errors; no Product/SearchQuery/snapshot mutation; staged/read-copy removed;
- persistence failure after archive publication → rollback all domain/report-context changes in the active transaction, delete only the archive owned by this import, best-effort finish batch FAILED, never delete an archive referenced by another batch;
- unexpected programming exception is not converted into a misleading schema error; cleanup runs and the exception may propagate after best-effort failed-batch compensation.

No API response may expose traceback, absolute path, `.part`/read-copy internal path, SQL text, XML internals, or arbitrary exception text.

## 20. Startup recovery

Add:

- `recover_interrupted_ozon_seller_queries_imports(...)`;
- `recover_interrupted_ozon_query_metrics_imports(...)`.

FastAPI lifespan invokes PR3 recovery, PR4 recovery, seller-queries recovery, and Query Metrics recovery before serving requests.

Recovery requirements:

- RUNNING PR5 batches become FAILED with current UTC finished time;
- stale `.upload-*.part` is removable;
- stale `.readcopy-*.xlsx` is removable;
- orphan archive deletion uses the existing global set of all `SourceArtifact.stored_relpath` values across import kinds;
- referenced archives and unrelated/manual files are never deleted;
- recovery is idempotent.

Do not create a background cleanup service.

## 21. Import summary/result DTOs and unified history

Freeze source-specific summary/result/failure DTOs in their domain modules.

### 21.1. Seller summary/result

`OzonSellerQueriesImportSummary` contains exactly:

```text
import_batch_id
source
import_kind
status
generated_at | null
period_start | null
period_end | null
product_ozon_id | null
rows_seen
rows_accepted
rows_skipped
duplicate_observations
new_observations
corrected_revisions
warnings_count
row_errors_total
started_at
finished_at | null
source_artifact | null
```

`OzonSellerQueriesImportResult` contains exactly:

```text
import_batch_id
report_type = OZON_OWN_PRODUCT_QUERIES
status
generated_at | null
period_start | null
period_end | null
product_ozon_id | null
rows_seen
rows_accepted
rows_skipped
duplicate_observations
new_observations
corrected_revisions
warnings_count
row_errors_total
row_errors (first MAX_ROW_ERRORS)
row_errors_truncated
source_artifact
imported_at
```

`OzonSellerQueriesImportFailure` carries `error` plus `result | None`. Before a durable ImportBatch exists, `result=None`. Once a durable failed summary exists, return the FAILED result. `imported_at` in result follows the existing PR4 convention: `finished_at` when available, otherwise `started_at`.

Do not include the eight per-query metric values or query-row arrays in the import response.

### 21.2. Query Metrics summary/result

`OzonQueryMetricsImportSummary` contains exactly:

```text
import_batch_id
source
import_kind
status
period_start | null
period_end | null
sort_context | null
rows_seen
rows_accepted
rows_skipped
duplicate_observations
new_observations
corrected_revisions
warnings_count
row_errors_total
started_at
finished_at | null
source_artifact | null
```

`OzonQueryMetricsImportResult` contains exactly:

```text
import_batch_id
report_type = OZON_QUERY_METRICS
status
period_start | null
period_end | null
sort_context | null
rows_seen
rows_accepted
rows_skipped
duplicate_observations
new_observations
corrected_revisions
warnings_count
row_errors_total
row_errors (first MAX_ROW_ERRORS)
row_errors_truncated
source_artifact
imported_at
```

`OzonQueryMetricsImportFailure` follows the same failure/result rule. No `generated_at` is invented. Do not return the ten market metric payload fields in the import response.

### 21.3. Lineage repository methods

Extend `LineageRepository` with source-specific methods rather than a generic finish callback:

```text
finish_ozon_seller_queries_import(...)
finish_ozon_query_metrics_import(...)
fail_running_ozon_seller_queries_imports(...)
fail_running_ozon_query_metrics_imports(...)
```

Source-specific finish methods validate their expected `import_kind`, status transition, non-negative counters, canonical period/context, and return the corresponding summary DTO.

### 21.4. Unified `ImportHistoryItem`

Extend `ImportHistoryItem.report_type` to:

```text
OZON_PRODUCTS
OZON_SEARCH_VISIBILITY
OZON_OWN_PRODUCT_QUERIES
OZON_QUERY_METRICS
```

Extend history with nullable PR5 context fields:

```text
period_start
period_end
report_generated_at
report_product_ozon_id
sort_context
```

Existing PR3/PR4-specific fields remain and are null for non-applicable report types. PR5 fields are null for PR3/PR4 where not applicable.

`LineageRepository.list_import_history()` and count include all four import kinds, ordered newest-first by `started_at DESC, id DESC`, with existing pagination semantics.

## 22. FastAPI endpoints and error envelopes

Add thin routes:

```text
POST /api/imports/ozon-seller-queries
POST /api/imports/ozon-query-metrics
```

Keep existing `GET /api/imports`.

Routes only validate multipart transport, call the application service, serialize domain DTOs, map frozen source-specific failures, and close `UploadFile` in `finally`. No parser, persistence, revision, identity, or business logic enters routes.

Common public mappings where semantics match:

| Failure | HTTP | Code |
|---|---:|---|
| unreadable package | 422 | `UNSUPPORTED_WORKBOOK` |
| clearly wrong report | 422 | `WRONG_REPORT_TYPE` |
| expected report incompatible | 422 | `INCOMPATIBLE_REPORT_SCHEMA` |
| invalid period | 422 | `INVALID_REPORT_PERIOD` |
| conflicting duplicate observations | 422 | `CONFLICTING_OBSERVATION_ROWS` |
| zero usable rows | 422 | `NO_USABLE_ROWS` |
| shared import lock | 409 | `CONCURRENT_IMPORT_CONFLICT` |
| >25 MiB | 413 | `UPLOAD_TOO_LARGE` |
| wrong upload media/extension | 415 | `UNSUPPORTED_UPLOAD_MEDIA_TYPE` |
| persistence failure | 500 | `IMPORT_PERSISTENCE_ERROR` |

Seller-only fatal codes:

- invalid source generation timestamp → `INVALID_GENERATED_AT` / 422;
- invalid row-8 product context → `INVALID_PRODUCT_CONTEXT` / 422.

Frozen user guidance must name the required report specifically:

- seller wrong-report message: `Выберите отчёт Ozon «Запросы моего товара».`;
- Query Metrics wrong-report message: `Выберите отчёт Ozon с метриками поисковых запросов.`.

Other messages should follow existing concise Russian Data-page language. Never include raw exception text in a 500 response.

Missing/wrong multipart `file` field continues to use FastAPI/route 422 transport validation behavior.

## 23. Data UI

PR5 extends the existing `Данные` page only. Do not add a new global navigation section or Product Workspace analytics.

Add two upload cards/controls alongside PR3/PR4 imports:

- `Запросы моего товара`;
- `Метрики поисковых запросов`.

Each card provides:

- XLSX file selection;
- selected filename;
- disabled submit until file selected;
- visible loading stage text;
- success vs partial success vs error state;
- accepted/skipped/new/duplicate/corrected counts;
- source period and relevant report context;
- bounded row-error details when present.

After seller-queries success/partial success, refresh both import history and Product list because existing PR3-backed Products may have ownership updated. After Query Metrics success/partial success, refresh import history.

Extend history rendering for the two new report types:

- seller-queries: label `Запросы моего товара`; context includes Ozon product ID, exact source period, and accepted/skipped counts;
- Query Metrics: label `Метрики поисковых запросов`; context includes exact source period, sort context in detail, and accepted/skipped counts.

Minimal PR5 readiness is derived from unified import history rather than a new readiness service:

- most recent successful/partial `OZON_OWN_PRODUCT_QUERIES` import → `Запросы своего товара — данные есть`;
- most recent successful/partial `OZON_QUERY_METRICS` import → `Рыночные метрики запросов — данные есть`;
- otherwise show what report is missing.

A later failed import does not erase previously persisted source availability. This readiness is source availability only. Do not evaluate period compatibility, query relevance, demand quality, or analytical readiness in PR5.

Use the existing committed HTML/CSS/JavaScript model and canonical Visual Design System. No npm/build step or framework is introduced.

## 24. Synthetic fixture policy

Extend `tests/xlsx_factory.py` or add narrowly named fixture builders. Real user XLSX bytes and identifying source rows must never enter the public repository.

Synthetic seller-queries fixtures must deliberately reproduce exact structural Unicode, including LF/NBSP header characters, source metadata formats, `SOURCE_ZERO`, surprising `seen_users > searched_users`, percentage text, grouped whole-ruble revenue, duplicate/conflict cases, formulas, and malformed structures.

Synthetic Query Metrics fixtures must support:

- exact source period/sort/header/help layout;
- fewer than 10,000 rows as a valid report;
- native numeric cells and exact raw XML numeric values;
- exact `-` dynamics sentinel;
- large dynamics;
- revenue with 1–4 decimal places;
- no-action share above 1 raw / 100 percentage points;
- numeric-only query text;
- formula/merged/L+ invalid cases;
- conflicting duplicate query rows;
- package-level incorrect `<dimension ref="A1">`;
- `horizontal="Left"` / `horizontal="Right"` style values that reproduce the verified openpyxl compatibility problem.

The fixture factory may post-process its own synthetic XLSX ZIP package to create these exact package quirks. Do not copy the real evidence package.

## 25. Required test matrix — domain and parser

At minimum add tests for:

### ProductQuery domain/parser

- frozen dataclass fields and immutability;
- exact eight-field payload and deterministic Decimal hash;
- exact query edge cleanup/reuse semantics;
- exact metadata/header Unicode;
- generated_at UTC and explicit period pair;
- end-before-start and invalid metadata fatal;
- valid Product context vs invalid Product context;
- `KNOWN` and `SOURCE_ZERO` invariants;
- positive positions >1000 accepted;
- `seen_users > searched_users` accepted;
- 0/fractional/100% own conversions;
- whole-ruble Decimal revenue;
- formulas in structural rows fatal; formulas in data rows recoverable;
- wrong PR3/PR4/Query Metrics report → wrong report type;
- identical in-file query duplicate warning/dedupe;
- conflicting in-file duplicate fatal;
- zero usable rows returned by parser for application handling.

### QueryMetric domain/parser

- frozen ten-field payload and immutability;
- exact query identity including numeric-only strings;
- exact period + sort contract;
- no generated_at inferred from filename;
- incorrect worksheet dimension does not truncate rows;
- style capitalization compatibility permits the verified source shape;
- compatibility copy leaves original bytes/hash unchanged;
- unsupported package corruption remains unsupported;
- exact raw XML Decimal extraction, not binary-float canonicalization;
- integer count validation and bool rejection;
- dynamics positive/negative/zero/large and exact `-` sentinel;
- cart/order fraction to percentage points and 0..1 bounds;
- revenue underlying precision preserved;
- no-action share >100 percentage points accepted;
- no cross-field arithmetic constraints/recomputation;
- formulas in structural rows fatal and formulas in candidate rows recoverable;
- merged cells and L+ business values fatal;
- wrong PR3/PR4/seller report → wrong report type;
- identical duplicate query warning/dedupe;
- conflicting duplicate fatal;
- fewer than 10,000 rows valid;
- absent query creates no synthetic zero observation.

## 26. Required test matrix — repositories/import services

For each snapshot repository:

- revision 1 `NEW`;
- same logical key + same payload `DUPLICATE`, no insert;
- same key + changed payload `CORRECTED`, immutable prior row and correct supersession;
- changed period pair independent revision 1;
- provenance/import/source-artifact links retained;
- Decimal/state reconstruction exact.

Seller import service tests:

- valid import archive + snapshot writes;
- existing PR4/SearchQuery identity reused;
- unknown Product created with same Ozon external identity and ownership true;
- existing false-owned Product becomes true;
- ownership + SearchQuery + snapshots roll back together on persistence failure;
- seller-only Product remains absent from PR3-backed `/api/products` until ProductSnapshot exists;
- once PR3 ProductSnapshot exists for same Ozon ID, one reused Product becomes visible and owned;
- partial success;
- zero usable no Product/SearchQuery/snapshot mutation;
- duplicate/corrected/reperiod behavior;
- shared lock conflict with PR3/PR4/other PR5 import;
- staging size/extension/filesystem failures;
- archive compensation;
- recovery and global archive reference protection;
- first 50 row errors + total/truncated semantics.

Query Metrics import service tests:

- original artifact hash/archive preserved while parsing read-copy;
- read-copy removed on success and every failure path;
- valid/partial import;
- zero usable no SearchQuery/snapshot mutation;
- duplicate/corrected/reperiod behavior;
- no Product rows created or mutated;
- shared lock conflicts cross-kind;
- package compatibility failure classification;
- staging/archive/persistence compensation;
- recovery removes stale read-copy but preserves referenced archives/manual files;
- first 50 row errors + total/truncated semantics.

## 27. Required HTTP acceptance matrix

Use real `fastapi.testclient.TestClient` requests, not only route-source inspection.

For both POST endpoints cover:

- valid multipart → 200 SUCCESS with exact source-specific result contract;
- partial → 200 PARTIAL_SUCCESS;
- unreadable → 422 `UNSUPPORTED_WORKBOOK`;
- wrong report → 422 `WRONG_REPORT_TYPE`;
- incompatible expected schema → 422 `INCOMPATIBLE_REPORT_SCHEMA`;
- invalid period → 422;
- seller invalid generated_at/product context → 422 with source-specific code;
- conflicting rows → 422;
- no usable rows → 422 with durable FAILED result/context;
- shared lock → 409 and `result:null`;
- oversized → 413 and `result:null`;
- wrong content type/extension → 415;
- missing/wrong multipart file field → 422;
- injected persistence failure → 500 with durable FAILED result when possible and no partial domain mutation;
- `UploadFile.close()` on success and failure;
- response sanitization: no traceback/absolute path/internal transient path/arbitrary injected exception text;
- row error truncation first 50 + total + flag;
- import response does not include snapshot metric payload arrays/fields.

Additional HTTP integration:

- `GET /api/imports` contains mixed PR3/PR4/seller/Query Metrics history newest-first;
- pagination and total remain correct;
- non-applicable context fields are null, not cross-populated;
- seller ownership change is visible for an existing PR3-backed Product through `/api/products`;
- seller-only Product is not catalog-visible;
- TestClient lifespan recovers interrupted batches for all four import kinds and removes stale read-copy safely.

## 28. Frontend contract tests

Update static frontend contract tests to prove:

- four XLSX import controls exist with unique IDs/labels;
- seller and Query Metrics endpoints are wired correctly;
- selected filename, loading, success, partial, and error hooks exist for each;
- history renderer branches for all four `report_type` values;
- seller period/Product context and Query Metrics period/sort context are rendered through escaped text;
- successful seller import refreshes imports + products;
- Query Metrics import refreshes imports;
- minimal source readiness text is present;
- no Query Opportunity, relevant-query selection, benchmark, competitor, heatmap, or future analytics UI appears in PR5.

## 29. Windows portable acceptance

Extend existing `tests/windows_smoke.ps1` minimally after current PR3/PR4 probes:

- portable runtime imports the existing pinned dependencies; no dependency additions expected;
- synthetic seller-queries parser/import succeeds and persists at least one `product_query_snapshots` row;
- synthetic Query Metrics fixture exercising the source-compatible style/dimension quirks parses/imports and persists at least one `query_metric_snapshots` row;
- archived source artifact exists for each successful import;
- existing PR1–PR4 portable scenarios remain green.

Windows-specific acceptance is authoritative in GitHub Actions after push. Do not weaken existing smoke scenarios to make PR5 pass.

## 30. Files and scope guidance

Expected new production files:

```text
backend/domain/product_query.py
backend/domain/query_metric.py
backend/ingestion/ozon_seller_queries_xlsx.py
backend/ingestion/ozon_query_metrics_xlsx.py
backend/ingestion/ozon_query_metrics_xlsx_compat.py
backend/application/ozon_seller_queries_import.py
backend/application/ozon_query_metrics_import.py
backend/persistence/migrations/migration_004_pr5_query_data.py
backend/persistence/repositories/product_query_snapshots.py
backend/persistence/repositories/query_metric_snapshots.py
```

Expected modified production/integration files include only where needed:

```text
backend/application/import_runtime.py
backend/domain/lineage.py
backend/persistence/migrations/runner.py
backend/persistence/repositories/lineage.py
backend/main.py
frontend/index.html
frontend/assets/js/app.js
frontend/assets/css/app.css   # only if existing primitives cannot express the two cards/readiness
```

Tests may add source-specific parser/repository/import/API files and update existing migration/lineage/frontend/runtime/Windows regression files.

`requirements.txt`, portable runtime pinning, launcher bootstrap architecture, canonical Product/Architecture/UIUX/VDS documents, and existing migrations 001–003 are not modified.

Do not broaden scope merely to deduplicate old code.

## 31. Implementation discipline

PR5 implementation uses TDD by vertical and preserves dependency order:

```text
migration/domain
→ repository
→ parser/fixtures
→ import service
→ API/history
→ Data UI
→ Windows smoke
→ full regression
```

A practical implementation plan may interleave the two verticals where the shared migration/import-runtime work benefits both, but semantic tests remain source-specific.

Do not start PR6 work in the PR5 branch.

No implementation claim is valid without fresh verification evidence.

## 32. Definition of Done

PR5 is complete only when all of the following are true:

1. both approved Source Contracts are implemented without semantic reinterpretation;
2. `ProductQuerySnapshot` and `QueryMetricSnapshot` are separate immutable revisioned histories with exact logical keys/payloads;
3. PR4 `SearchQuery` identity is reused exactly across all three query-related sources;
4. seller-queries is positive ownership evidence but never manufactures ProductSnapshot/catalog data;
5. Query Metrics creates no Product/Cluster facts;
6. original Query Metrics upload remains the provenance/archive artifact and the compatibility read-copy is transient only;
7. verified `Left/Right` style quirk and false `dimension=A1` do not block valid Query Metrics import;
8. Query Metrics exact numeric values use raw XML Decimal text rather than binary-float canonicalization;
9. market conversion cannot be confused with own-product conversion in domain names, storage, API, or UI;
10. missing query coverage never becomes zero demand or zero conversion;
11. shared mechanical file helpers remain source-agnostic and do not become a generic import framework;
12. import history durably represents PR3/PR4/PR5 success, partial, and failure context;
13. API errors are actionable and sanitized;
14. Data UI exposes both new imports and source availability without implementing downstream analytics;
15. no real reports, credentials, user DBs, or sensitive logs are committed;
16. no new dependency/npm/framework/runtime requirement is introduced;
17. targeted parser/domain/repository/import/API/frontend tests pass;
18. full existing Python suite passes with no weakened regressions;
19. `python -m compileall -q backend launcher.py tests` succeeds;
20. `node --check frontend/assets/js/app.js` succeeds when Node is available in the dev/CI environment;
21. `git diff --check` succeeds;
22. GitHub Actions Windows job passes Python tests, JavaScript syntax, and full portable smoke on the final PR head;
23. independent post-push review finds no architecture/source-contract/lineage/secret/provenance violation.

## 33. Frozen decisions summary

The following decisions are frozen for PR5 unless the user explicitly reopens the design:

1. one PR5, not PR5A/PR5B;
2. two isolated source verticals, not a generic query importer;
3. one migration 004 with two separate snapshot tables;
4. existing exact `SearchQuery` identity is shared;
5. `ProductQuerySnapshot` grain is Product × SearchQuery × period pair;
6. `QueryMetricSnapshot` grain is SearchQuery × period pair;
7. seller position states are `KNOWN` and `SOURCE_ZERO` only;
8. seller source may set Product ownership true but does not create ProductSnapshot;
9. Query Metrics has no Product/Cluster dependency;
10. Query Metrics original bytes are the SourceArtifact/archive; compatibility copy is transient;
11. package compatibility fixes only evidenced `Left/Right` style capitalization by default; stored dimension is ignored rather than trusted;
12. exact Query Metrics numeric XML text is the canonical numeric source for Decimal/integer parsing;
13. shared file-lifecycle extraction is mechanical only and existing PR3/PR4 services are not refactored for cosmetic consistency;
14. import_batches stores only minimal PR5 period/generated/product/sort context needed for durable failed-history explanation;
15. two explicit POST endpoints plus unified GET history; no generic dispatcher;
16. readiness in PR5 means source availability only, derived from import history;
17. no PR6+ analytics or selection workflow enters PR5;
18. no new dependencies or frontend build system.
