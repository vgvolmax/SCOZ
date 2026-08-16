# SCOZ PR3 — Ozon «Товары на Ozon» Import — Implementation Spec

**Status:** Approved implementation specification

**Date:** 2026-08-16

**PR:** PR3 only; first end-to-end SCOZ data import

**Source authority:** [`2026-08-16-ozon-products-xlsx-source-contract-v1.md`](./2026-08-16-ozon-products-xlsx-source-contract-v1.md)

## 1. Purpose and authority boundary

PR3 implements the strict input shape, types, units, sentinels, identity, and temporal semantics defined by the authoritative Source Contract v1 linked above. This document defines the SCOZ domain, persistence, ingestion, API, provenance, and UI behavior around that source. It does not broaden or reinterpret the source contract.

PR3 delivers ProductSnapshot, migration 002, direct `openpyxl` parsing, focused ingestion/application services, immutable revisions, ImportBatch/SourceArtifact provenance, local FastAPI upload/read endpoints, import history, product list, manual ownership, period/freshness presentation, committed static frontend states, and synthetic XLSX tests.

## 2. Scope and non-goals

The implementation remains a local, same-origin, loopback-only Windows application. It adds no auth, CORS framework, background jobs, persistent job system, source registry, generic ingestion framework, generic snapshot/revision table, pandas/DataFrame contract, Node/npm, frontend framework, or network service.

The following are explicitly outside PR3: SearchQuery, Cluster, SearchVisibilitySnapshot, QueryMetricSnapshot, ProductQuerySnapshot, SearchPositionSnapshot, AdvertisingSnapshot, RelevantQueryScope, BenchmarkSet, BenchmarkSetRevision, BenchmarkMember, Diagnostics, benchmark analytics, Query Opportunity, Ramp-up, MPStats, Ozon public API sync, Ozon Performance API, credentials/keystore, and every associated schema, file, route, or UI workflow. Their mention here is an anti-scope boundary only.

## 3. Frozen domain model and normalization

### 3.1 `ProductSnapshot`

Add `backend/domain/product_snapshot.py` with the frozen `ProductSnapshot` dataclass whose exact fields are:

```text
id: int
product_id: int
report_generated_on: date
report_window_days: int
revision: int
supersedes_snapshot_id: int | None
payload_sha256: str
import_batch_id: int
source_artifact_id: int
imported_at: datetime
product_url: str
title: str
seller_name: str
brand: str
category_level_1: str
category_level_3: str
product_badges: str | None
ordered_amount_rub: Decimal
turnover_change_pct: Decimal | None
ordered_units: int
average_price_rub: Decimal
minimum_price_rub: Decimal
buyout_share_pct: Decimal | None
missed_sales_source_value: Decimal
out_of_stock_days: int | None
out_of_stock_window_days: int | None
avg_daily_sales_rub: Decimal
avg_daily_sales_units: int
stock_end_units: int
fulfillment_scheme: str
volume_l: Decimal
impressions_total: int
search_catalog_views: int
card_views: int
impression_to_order_pct: Decimal
search_catalog_to_cart_pct: Decimal
card_to_cart_pct: Decimal
promotion_discount_source_value: Decimal
promotion_order_amount_share_pct: Decimal
promotion_days: int
promotion_window_days: int
advertising_days: int
advertising_window_days: int
total_drr_pct: Decimal
card_created_on: date
```

The two `*_source_value` names are mandatory because Source Contract v1 does not establish their display/analytical units. PR3 does not call them RUB or percentage, display a unit, or use them in analytics. `product_url` is retained as a useful auditable source fact and canonical clickable product context; identity remains the extracted ID.

### 3.2 Exact decimal policy

Money, percentage points, litres, and unconfirmed-unit numeric source values use `Decimal` from parsing through domain boundaries. Convert an accepted Excel integer through `Decimal(value)` and an accepted finite float through `Decimal(str(value))`; reject booleans, NaN, infinity, strings, and formulas except exact documented sentinels/window strings. Canonical decimal serialization is plain base-10 notation with no exponent, no leading plus, no insignificant trailing fractional zeros, `-0` normalized to `0`, and at least `0` for zero. SQLite stores that canonical form in `TEXT` columns. API emits decimal values as JSON strings; UI localizes them only for display.

Counts are Python/SQLite integers with the source-contract non-negative/integral checks. Dates are `date`, stored and hashed as ISO `YYYY-MM-DD`. UTC aware datetimes retain the PR2 ISO convention.

### 3.3 Source mapping

Every snapshot source value maps one-to-one from the same-named Source Contract mapping: the seven `*_pct` columns remain percentage points; day strings split into their explicit numerator and denominator; report metadata supplies only `report_generated_on` and `report_window_days`; the URL supplies product identity and `product_url`. No `period_start`/`period_end` exists. No conversion, DRR, turnover, daily-sales, or other derived metric is calculated.

Category metadata mismatch is a recoverable row error. A formula or invalid cell in an individual product row is `InvalidMetricValue` for that row. A formula in metadata/structure is fatal `IncompatibleReportSchema`.

For `Признак товара`, Excel `None` and a zero-length text value `""` normalize to `product_badges = None`, while non-empty text is preserved. Numeric `0` is not missing: it is handled by text-field validation and must not silently become `None`. The parser checks cell type and value, never Python truthiness.

### 3.4 `OzonProductsImportSummary`

The generic PR2 `ImportBatch` dataclass remains the lineage root and is not extended with feature-specific fields. Add this exact PR3-specific frozen read/result DTO to `backend/domain/product_snapshot.py`:

```python
@dataclass(frozen=True)
class OzonProductsImportSummary:
    import_batch_id: int
    source: str
    import_kind: str
    status: ImportStatus
    report_generated_on: date | None
    report_window_days: int | None
    rows_seen: int
    rows_accepted: int
    rows_skipped: int
    duplicate_observations: int
    new_observations: int
    corrected_revisions: int
    warnings_count: int
    row_errors_total: int
    started_at: datetime
    finished_at: datetime | None
    source_artifact: SourceArtifact | None
```

`source` and `import_kind` are included so import history returns the exact import type without duplicating the generic lineage model. No generic import metadata JSON or generic lineage extension is introduced.

## 4. Logical key, payload, and immutable revisions

The exact logical key is `(product_id, report_generated_on, report_window_days)`. Category, seller, title, source row, and filename are not key dimensions.

The normalized payload passed to existing `normalized_payload_sha256()` is a dictionary with exactly these alphabetically serialized keys:

```text
advertising_days, advertising_window_days, average_price_rub,
avg_daily_sales_rub, avg_daily_sales_units, brand, buyout_share_pct,
card_created_on, card_to_cart_pct, card_views, category_level_1,
category_level_3, fulfillment_scheme, impression_to_order_pct,
impressions_total, minimum_price_rub, missed_sales_source_value,
ordered_amount_rub, ordered_units, out_of_stock_days,
out_of_stock_window_days, product_badges, product_url,
promotion_days, promotion_discount_source_value,
promotion_order_amount_share_pct, promotion_window_days,
search_catalog_to_cart_pct, search_catalog_views, seller_name,
stock_end_units, title, total_drr_pct, turnover_change_pct, volume_l
```

Before hashing, every Decimal is its canonical string, `date` is ISO text, integers remain JSON integers, text remains text, and missing values remain JSON null. The payload excludes `id`, `product_id`, logical-key temporal fields, `revision`, `supersedes_snapshot_id`, `payload_sha256`, `import_batch_id`, `source_artifact_id`, `imported_at`, parser row, filename, and warnings.

Repository behavior is exact:

- no prior key → insert revision 1;
- same key and same current payload hash → `DUPLICATE`, no snapshot insert;
- same key and changed payload hash → insert immutable `current.revision + 1`, set `supersedes_snapshot_id = current.id`;
- different generated date or window → independent revision 1 observation;
- never update or delete an earlier snapshot revision.

Within one workbook, the first normalized row establishes the key/payload. A later identical key/payload is a duplicate input: it increments `duplicate_observations` and `warnings_count` and is not processed twice. A later same-key/different-payload row raises fatal `ConflictingObservationRows`; the entire import performs no Product/ProductSnapshot mutation. Last-row-wins is forbidden.

## 5. Migration 002 and exact schema

Register exactly `(2, "ozon_products_import", "backend.persistence.migrations.migration_002_ozon_products_import")` after migration 001. The filename is `backend/persistence/migrations/migration_002_ozon_products_import.py`, matching the current `migration_NNN_name.py`, `up(conn)`, linear registry convention. The runner remains transaction owner and the migration uses separate `conn.execute()` calls, never `executescript()`.

Migration 002 creates only `product_snapshots`, its indexes, and the PR3 result columns on `import_batches`. It creates no import-history table and no future-feature table. Adding nullable columns to an existing empty/used lineage table is non-destructive and does not require a pre-migration backup.

Add these nullable columns to `import_batches`: `report_generated_on TEXT`, `report_window_days INTEGER`, `rows_seen INTEGER`, `rows_accepted INTEGER`, `rows_skipped INTEGER`, `duplicate_observations INTEGER`, `new_observations INTEGER`, `corrected_revisions INTEGER`, `warnings_count INTEGER`, `row_errors_total INTEGER`. They are null while RUNNING and may remain null for failure before report metadata or result counters are measurable; terminal application writes every available field. Non-null counts are non-negative by repository validation. When mapping a terminal FAILED row to `OzonProductsImportSummary` or an API DTO, a NULL result counter maps to integer `0` only when structural failure made measuring that counter objectively impossible; known counter values are preserved. NULL `report_generated_on` and `report_window_days` always remain `None`, so an unreadable source period never becomes a fabricated period. `GET /api/imports` uses these durable fields rather than a JSON blob or inference from only inserted snapshots.

Exact `product_snapshots` DDL contract:

```sql
CREATE TABLE product_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    report_generated_on TEXT NOT NULL,
    report_window_days INTEGER NOT NULL CHECK (report_window_days > 0),
    revision INTEGER NOT NULL CHECK (revision > 0),
    supersedes_snapshot_id INTEGER NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    import_batch_id INTEGER NOT NULL,
    source_artifact_id INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    product_url TEXT NOT NULL,
    title TEXT NOT NULL,
    seller_name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category_level_1 TEXT NOT NULL,
    category_level_3 TEXT NOT NULL,
    product_badges TEXT NULL,
    ordered_amount_rub TEXT NOT NULL,
    turnover_change_pct TEXT NULL,
    ordered_units INTEGER NOT NULL CHECK (ordered_units >= 0),
    average_price_rub TEXT NOT NULL,
    minimum_price_rub TEXT NOT NULL,
    buyout_share_pct TEXT NULL,
    missed_sales_source_value TEXT NOT NULL,
    out_of_stock_days INTEGER NULL CHECK (out_of_stock_days IS NULL OR out_of_stock_days >= 0),
    out_of_stock_window_days INTEGER NULL CHECK (out_of_stock_window_days IS NULL OR out_of_stock_window_days > 0),
    avg_daily_sales_rub TEXT NOT NULL,
    avg_daily_sales_units INTEGER NOT NULL CHECK (avg_daily_sales_units >= 0),
    stock_end_units INTEGER NOT NULL CHECK (stock_end_units >= 0),
    fulfillment_scheme TEXT NOT NULL,
    volume_l TEXT NOT NULL,
    impressions_total INTEGER NOT NULL CHECK (impressions_total >= 0),
    search_catalog_views INTEGER NOT NULL CHECK (search_catalog_views >= 0),
    card_views INTEGER NOT NULL CHECK (card_views >= 0),
    impression_to_order_pct TEXT NOT NULL,
    search_catalog_to_cart_pct TEXT NOT NULL,
    card_to_cart_pct TEXT NOT NULL,
    promotion_discount_source_value TEXT NOT NULL,
    promotion_order_amount_share_pct TEXT NOT NULL,
    promotion_days INTEGER NOT NULL CHECK (promotion_days >= 0),
    promotion_window_days INTEGER NOT NULL CHECK (promotion_window_days > 0),
    advertising_days INTEGER NOT NULL CHECK (advertising_days >= 0),
    advertising_window_days INTEGER NOT NULL CHECK (advertising_window_days > 0),
    total_drr_pct TEXT NOT NULL,
    card_created_on TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (supersedes_snapshot_id) REFERENCES product_snapshots(id),
    FOREIGN KEY (import_batch_id) REFERENCES import_batches(id),
    FOREIGN KEY (source_artifact_id) REFERENCES source_artifacts(id),
    UNIQUE (product_id, report_generated_on, report_window_days, revision),
    CHECK ((out_of_stock_days IS NULL) = (out_of_stock_window_days IS NULL)),
    CHECK (out_of_stock_days IS NULL OR out_of_stock_days <= out_of_stock_window_days),
    CHECK (promotion_days <= promotion_window_days),
    CHECK (advertising_days <= advertising_window_days)
)
```

Repository validation enforces 64 lowercase hexadecimal hash characters, ISO dates, canonical decimal text, and that a superseded row has the same logical key and exactly `revision - 1`; SQLite constraints are defense-in-depth. Create indexes:

```sql
CREATE INDEX idx_product_snapshots_current
ON product_snapshots(product_id, report_generated_on, report_window_days, revision DESC);
CREATE INDEX idx_product_snapshots_latest_product
ON product_snapshots(product_id, report_generated_on DESC, report_window_days, revision DESC);
CREATE INDEX idx_product_snapshots_import_batch_id ON product_snapshots(import_batch_id);
CREATE INDEX idx_product_snapshots_source_artifact_id ON product_snapshots(source_artifact_id);
```

Current revision is the maximum revision for the logical key; there is no `is_current`. Allocation occurs inside the existing PR2 `transaction()` boundary while the process-local import lock is held, after reading the current row. The unique constraint rejects any accidental competing allocation as defense-in-depth.

## 6. Focused parser and application boundary

`backend/ingestion/ozon_products_xlsx.py` uses `openpyxl` directly in read-only, `data_only=False` mode so formulas can be detected rather than silently evaluated. It validates the exact single-sheet structure, exact signature, metadata, summary row, product cell types, sentinels, identity, and row consistency. It returns a typed normalized report plus bounded row defects; it executes no SQL and knows no FastAPI.

`backend/application/ozon_products_import.py` is the single focused application service. It owns one non-blocking process-local `threading.Lock` covering the complete mutation operation. Failure to acquire it raises `ConcurrentImportConflict`; no lock table, distributed lock, queue, or persistent job is introduced.

The application service acquires that lock before the mutation workflow and opens the existing PR2 `transaction()` boundary for atomic Product/ProductSnapshot mutation. Repositories use the caller-owned connection. The service executes no SQL, and PR3 does not extend the persistence transaction API or add a transaction mode.

The service validates upload extension `.xlsx`, a 25 MiB exact maximum, ZIP/XLSX readability, and the Source Contract. The HTTP layer streams to a generated temporary file and never loads an unbounded upload into memory. Original filename is display metadata only and is reduced to its basename before persistence.

## 7. SourceArtifact archive and atomic lifecycle

Accepted upload bytes are preserved for reproducible provenance under user-owned, gitignored `data/imports/`. The directory is created lazily. While streaming, compute SHA-256 and byte size and write `data/imports/.upload-<uuid4>.part` with exclusive creation. The final generated name is `<UTC YYYYMMDDTHHMMSSffffffZ>-<sha256>.xlsx`; it contains no original path. Exclusive creation makes an impossible generated collision a persistence failure rather than overwrite. `stored_relpath` is POSIX `imports/<generated-name>` relative to `data/`.

The exact lifecycle is:

1. acquire the import lock; stream, size-limit, hash, and fsync the `.part` file;
2. commit a RUNNING ImportBatch (`source="ozon"`, `import_kind="ozon_products_xlsx"`) plus SourceArtifact metadata with `stored_relpath = NULL`;
3. parse and normalize completely, including within-file conflict detection, before Product mutation;
4. on fatal validation, delete `.part`, atomically finish the batch FAILED with available counters/metadata, and insert no ProductSnapshot;
5. after at least one usable row, atomically rename `.part` to its generated final path;
6. open one existing PR2 `transaction()` boundary; set artifact `stored_relpath`; resolve identities/products; allocate duplicate/new/corrected revisions; write all accepted snapshots and durable result counts; set ImportBatch SUCCESS or PARTIAL_SUCCESS with `finished_at`; commit once through `transaction()`;
7. on any failure before DB commit, let the existing `transaction()` roll back and close, delete the staged or final generated file, then use a separate explicit PR2 `transaction()` to leave the artifact metadata with null path and finish the batch FAILED; expose `ImportPersistenceError` if persistence caused failure;
8. release the lock in every terminal path.

SUCCESS means at least one accepted row and no rejected recoverable row. PARTIAL_SUCCESS means at least one accepted row and at least one recoverable rejected row. FAILED means fatal validation/persistence prevented accepted mutation. A report with no usable product rows is fatal. Identical in-file duplicate rows are warnings, not rejected rows, and do not alone produce PARTIAL_SUCCESS.

Repositories never commit, roll back, or open a second connection; they operate on the connection owned by the calling `transaction()` boundary. The separate failure-status compensation transaction begins only after the mutation transaction has rolled back and closed.

FastAPI application startup performs one-shot PR3 interrupted-import cleanup after the launcher has applied DB migrations and before the new backend process begins handling HTTP requests. This cleanup is not a migration, persistent job runner, or change to launcher migration responsibility. The launcher already-running path starts no backend process, so it does not run cleanup separately.

At that startup boundary, every ImportBatch with `import_kind = "ozon_products_xlsx"` and `status = RUNNING` is an interrupted previous-process import because no persistent worker can survive process restart. Recovery marks every such batch FAILED, preserves already known metadata and counters, sets `finished_at` to the recovery time, and performs no ProductSnapshot mutation.

Filesystem recovery is equally deterministic and narrow. Every file matching `data/imports/.upload-*.part` is an interrupted staging file from the previous process and is deleted. A generated archive XLSX file is deleted only when its path matches the PR3 generated archive pattern and no SourceArtifact references that path through `stored_relpath`. Recovery never deletes unknown files, manually placed files, arbitrary `.xlsx` files, or referenced source artifacts.

## 8. Product resolution and ownership

For each valid row, resolve exactly the Source Contract identity tuple. If absent, create Product with `is_owned = false` and attach the identity in the same import transaction. Existing Product ownership is never changed by import. Title/seller/brand are snapshot facts, not Product merge keys. Ownership supports multiple products and is changed only through the ownership endpoint. Active UI selection is not persisted ownership.

## 9. Error taxonomy

| Error | Level | HTTP | User message |
|---|---|---:|---|
| `UnsupportedWorkbook` | fatal | 422 | `Не удалось прочитать XLSX-файл.` |
| `WrongReportType` | fatal | 422 | `Выберите отчёт Ozon «Товары на Ozon».` |
| `IncompatibleReportSchema` | fatal | 422 | `Версия или структура отчёта не поддерживается.` |
| `InvalidReportPeriod` | fatal | 422 | `Не удалось прочитать дату формирования или период отчёта.` |
| `InvalidProductIdentity` | recoverable row | 200 (`PARTIAL_SUCCESS` when at least one row is accepted) | `Некорректная ссылка на товар.` |
| `InvalidMetricValue` | recoverable row | 200 (`PARTIAL_SUCCESS` when at least one row is accepted) | `Некорректное значение показателя.` |
| `CategoryMismatch` | recoverable row | 200 (`PARTIAL_SUCCESS` when at least one row is accepted) | `Категория товара не совпадает с категорией отчёта.` |
| `ConflictingObservationRows` | fatal | 422 | `В отчёте есть противоречивые строки одного товара.` |
| `ConcurrentImportConflict` | request conflict | 409 | `Другой импорт уже выполняется. Дождитесь его завершения.` |
| `ImportPersistenceError` | fatal | 500 | `Не удалось сохранить импорт. Данные не изменены.` |

Malformed isolated row values are accumulated. Formula metric cells use `InvalidMetricValue`; wrong structural formulas use `IncompatibleReportSchema`. Responses never include a traceback, local absolute path, or uploaded content. For a completed partial import, HTTP 200 is used and status in the DTO is authoritative. HTTP 207 is not used. Fatal 422/500 responses include the failed batch result when a batch was created.

## 10. Exact API contract

Routes remain thin and same-origin; business logic is in the application service and SQL only in repositories.

### `POST /api/imports/ozon-products`

Accept `multipart/form-data` with exactly one required field `file`. Success/partial returns the ImportResult DTO. A missing/wrong field is FastAPI 422; wrong media type is 415; size limit is 413; taxonomy mappings are section 9. No credential or filename appears in a URL.

### `GET /api/imports`

Returns `{ "items": [...], "total": <int> }`, newest `started_at` first, with no mutation. Each item includes the same durable summary fields available from ImportBatch and its single SourceArtifact; `row_errors` is not reconstructed in history.

`LineageRepository` maps each item to `OzonProductsImportSummary`. Its exact PR3 extensions are:

```python
finish_ozon_products_import(
    batch_id: int,
    *,
    status: ImportStatus,
    report_generated_on: date | None,
    report_window_days: int | None,
    rows_seen: int,
    rows_accepted: int,
    rows_skipped: int,
    duplicate_observations: int,
    new_observations: int,
    corrected_revisions: int,
    warnings_count: int,
    row_errors_total: int,
) -> OzonProductsImportSummary

list_ozon_products_imports(
    *,
    limit: int,
    offset: int,
) -> list[OzonProductsImportSummary]

set_source_artifact_stored_relpath(
    artifact_id: int,
    stored_relpath: str,
) -> SourceArtifact
```

`set_source_artifact_stored_relpath()` reuses the existing `InvalidStoredRelativePath` validation contract. These are focused typed operations; arbitrary keyword metadata and JSON metadata are forbidden.

### `GET /api/products`

Returns `{ "items": [...], "total": <int>, "readiness": ... }`, sorted owned first then latest title and Product ID. Each product includes Product ID, Ozon identity value, `is_owned`, latest-current snapshot title/seller/brand, `report_generated_on`, `report_window_days`, `imported_at`, and freshness label inputs. Only the maximum revision of the latest `(report_generated_on, report_window_days)` observation is presented; historical rows remain stored.

### `PATCH /api/products/{product_id}/ownership`

Accepts exact JSON `{ "is_owned": true|false }`, returns `{ "id": <int>, "is_owned": <bool>, "updated_at": <UTC ISO> }`; unknown product is 404. No own-products table is introduced.

### ImportResult DTO

```text
import_batch_id: int
report_type: "OZON_PRODUCTS"
status: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED"
report_generated_on: "YYYY-MM-DD" | null
report_window_days: int | null
rows_seen: int
rows_accepted: int
rows_skipped: int
duplicate_observations: int
new_observations: int
corrected_revisions: int
warnings_count: int
row_errors_total: int
row_errors: [{row: int, code: str, message: str}]
row_errors_truncated: bool
source_artifact: {id, original_name, content_sha256, byte_size, stored_relpath}
imported_at: UTC ISO datetime
readiness: "SELECT_OWN_PRODUCTS" | "READY"
```

`row_errors` contains the first 50 errors in ascending source-row order; `row_errors_total` includes all errors and `row_errors_truncated = row_errors_total > 50`. `rows_seen` counts nonblank candidate rows from row 7; `rows_accepted` counts valid unique input rows admitted to revision resolution; `rows_skipped` counts rejected recoverable rows; identical in-file duplicates count only in `duplicate_observations`. Database duplicates also increment `duplicate_observations`; new revision-1 observations increment `new_observations`; corrections increment `corrected_revisions`. `warnings_count` includes identical in-file duplicates plus explicit non-row warnings. `readiness` is SELECT_OWN_PRODUCTS when no Product is owned after commit, otherwise READY.

## 11. Static frontend UX

Keep the existing global `Товары / Данные / Настройки` navigation and visual tokens; do not redesign or add navigation. Use committed HTML/CSS/JavaScript only, desktop-first, same-origin fetch, semantic controls, visible focus, text/icon labels in addition to color, and `aria-live` result feedback.

`Данные` provides a labelled XLSX file control and upload action. The selected basename appears immediately. During the request disable duplicate submission and show understandable indeterminate stage copy (`Проверяем файл`, then `Читаем данные · Нормализуем · Сохраняем`) without fake percentages or persisted job stages. Render empty, loading, success, partial, and error states; partial includes accepted/skipped counts and bounded row details. Import history displays status, report type, business generated date/window, separate import time, original filename, accepted/skipped and duplicate/revision counts, and warning/error text.

`Товары` renders empty/loading/error/list states, Ozon product ID/context, title, seller, brand, latest report phrase, separate import freshness, and an accessible owned checkbox/action. After first import with no owned Product, show exactly `Данные загружены. Выберите свои товары.` Multiple owned products are allowed. No Diagnostics action is started.

Freshness is based on `report_generated_on` plus `imported_at`, never workbook metadata. The UI expresses, for example, `7 дней · отчёт сформирован 16.08.2026 · импортирован сегодня 17:10`; it never invents period boundaries.

## 12. Dependency and portable runtime contract

PR3 adds exactly two direct runtime dependencies: `openpyxl==3.1.5` for XLSX parsing and `python-multipart==0.0.32` for FastAPI `multipart/form-data` upload parsing. Pandas is forbidden, and PR3 adds no other runtime dependency. Both versions support the Python 3.13 portable runtime selected by PR1. Update the exact runtime validation in `start.bat` to import `openpyxl` and require installed distribution metadata version `3.1.5`, and to verify the `multipart` import/package is present and installed `python-multipart` distribution metadata version is `0.0.32`. Ordinary `python -m pip install -r requirements.txt` remains the only install/repair mechanism.

Windows acceptance proves: a clean runtime installs both direct dependencies; second start reuses the runtime with both imports and metadata versions valid; dependency corruption or mismatch is restored by the ordinary existing pip repair mechanism; a synthetic parser/import smoke succeeds under that runtime; repair/rebuild preserves `data/scoz.db` and `data/imports`; spaces and Cyrillic paths remain valid. `tests/windows_smoke.ps1` remains ASCII-only, expressing any Cyrillic through character codes.

## 13. Exact implementation file map

| File | Change | Exact responsibility |
|---|---|---|
| `backend/domain/product_snapshot.py` | add | frozen ProductSnapshot/normalized report DTOs, exact `OzonProductsImportSummary`, and narrow validation errors; no SQL |
| `backend/ingestion/__init__.py` | add | package marker only |
| `backend/ingestion/ozon_products_xlsx.py` | add | strict Source Contract parser and normalizer only |
| `backend/application/__init__.py` | add | package marker only |
| `backend/application/ozon_products_import.py` | add | focused lock, file/archive lifecycle, existing-transaction orchestration, and summary-to-result orchestration; no SQL |
| `backend/persistence/migrations/migration_002_ozon_products_import.py` | add | exact migration 002 DDL |
| `backend/persistence/migrations/runner.py` | modify | append stable migration registry entry only |
| `backend/persistence/repositories/lineage.py` | modify | exact focused summary finish/list and stored-path operations; maps rows to `OzonProductsImportSummary` |
| `backend/persistence/repositories/products.py` | modify | identity resolve-or-create and ownership/list support |
| `backend/persistence/repositories/product_snapshots.py` | add | snapshot revision/current/latest SQL and mapping |
| `backend/main.py` | modify | thin four-endpoint HTTP adapters, startup recovery hook, multipart limits/errors, and summary/result response mapping |
| `frontend/index.html` | modify | existing-shell Data/Product semantic regions and controls |
| `frontend/assets/css/app.css` | modify | existing-token states/components only |
| `frontend/assets/js/app.js` | modify | same-origin import/history/products/ownership presentation only |
| `requirements.txt` | modify | exact `openpyxl==3.1.5` and `python-multipart==0.0.32` runtime pins |
| `start.bat` | modify | exact import and installed-distribution metadata validation for both new direct dependencies |
| `tests/xlsx_factory.py` | add | generated exact-contract synthetic workbooks |
| `tests/test_ozon_products_parser.py` | add | source/normalization cases |
| `tests/test_product_snapshot_repository.py` | add | key/hash/revision/provenance cases |
| `tests/test_ozon_products_import.py` | add | service, atomicity, archive, statuses, lock cases |
| `tests/test_ozon_products_api.py` | add | upload/read/ownership/error API cases |
| `tests/test_frontend_contract.py` | modify | all required visible states and no-framework contract |
| `tests/test_migrations.py` | modify | migration 002 schema/registry/idempotence/anti-scope |
| `tests/test_runtime_contract.py` | modify | exact two PR3 dependency pins plus import/version validation and repair expectations |
| `tests/windows_smoke.ps1` | modify | portable dependency/import and state-preservation smoke, ASCII-only |

No route package or larger speculative package tree is created. `backend/main.py` remains thin at this scale.

## 14. Synthetic fixture and verification contract

The real evidence workbook is never committed. `tests/xlsx_factory.py` builds workbooks with openpyxl and exact rows 1–6, all 32 ordered headers, and synthetic product rows. Fixtures cover minimal valid, full valid, wrong marker, wrong headers/order, multiple sheets, missing identity, malformed URL, bad generated date/window, bad percentage, localized numeric string rejection, formula rejection, bad windowed-day value, exact `Нет данных`, exact `-`, explicit zero, `None` badge, zero-length text badge, non-empty badge, numeric-zero badge validation without truthiness-to-null conversion, card-date text, summary-row exclusion, category mismatch, identical duplicate row, and conflicting same-key row.

Automated tests must prove:

1. parser detection, identity tuple, types, Decimal canonicalization, percentage points without scaling, sentinels without truthiness bugs, separate day denominators, date parsing, summary exclusion, and recoverable category mismatch;
2. exact logical key; revision 1; duplicate without insert; corrected revision 2 superseding unchanged revision 1; new generated date and new window each start revision 1; deterministic payload independent of dictionary order;
3. Product/identity resolution, source-artifact FK, batch provenance, archive hash/size/path, no original-path trust, collision failure, cleanup/compensation, and no snapshot mutation after fatal validation/persistence;
4. SUCCESS, PARTIAL_SUCCESS, FAILED and durable history counts; identical in-file duplicate warning; conflicting rows fatal; 50-error cap; process-local concurrent request receives 409;
5. all four API contracts, GET non-mutation, structured errors without traces, product latest-current selection, multiple ownership toggles, readiness states, and freshness inputs;
6. frontend empty/loading/success/partial/error/freshness states, immediate filename, no fake progress, unchanged navigation, accessible non-color status, and no npm/framework;
7. clean/idempotent migration 002, constraints/indexes/registry identity, no future tables, PR1/PR2 migration/product/lineage/launcher regressions, runtime exact dependency checks, and authoritative Windows smoke.

Linux/cloud verification runs the full Python suite, frontend contract tests, `git diff --check`, and source/spec audits. GitHub Actions Windows is authoritative for clean portable install/reuse, paths, dependency repair, import smoke, and database/archive preservation. Codex does not ask for desktop commands.

## 15. Source-contract consistency gate

Before implementation handoff reviewers verify all of the following as a single gate:

- parser constants contain exactly the 32 documented headers in exact order;
- every ProductSnapshot payload field maps to a documented header, identity URL, or allowed temporal metadata;
- all seven percentage fields remain canonical percentage points, especially `total_drr_pct`;
- only the explicit `Нет данных`, `-`, and blank-badge contracts produce missing values;
- numeric zero survives normalization;
- each windowed metric stores its explicit denominator and never receives `report_window_days` by substitution;
- no period start/end is created, stored, hashed, returned, or displayed;
- identity is `ozon_product_id` extracted from the strict URL and ownership is never inferred;
- raw unconfirmed units remain `*_source_value` and are excluded from analytics/unit labels;
- logical-key, payload exclusions, unique constraint, duplicate behavior, revision allocation, and immutable supersession agree;
- archive compensation makes terminal ImportBatch state agree with committed ProductSnapshot data;
- no transaction-control SQL appears in the PR3 application contract or application service; the existing PR2 `transaction()` owns commit/rollback, repositories remain caller-connection-owned, the process-local import lock serializes imports, and the database UNIQUE constraint remains defense-in-depth;
- the multipart endpoint includes `python-multipart`; the dependency contract, requirements File Map, runtime validation, contract tests, and Windows smoke all name the same two pins, `openpyxl==3.1.5` and `python-multipart==0.0.32`;
- anti-scope search finds future concepts only in section 2's non-goal statement.

## 16. Acceptance / Definition of Done

PR3 is complete when strict synthetic XLSX import works end-to-end; invalid schema fails clearly without data mutation; recoverable defects produce partial success; products resolve only through Ozon ID; same payload is a duplicate; changed same-key payload is a new immutable revision; different date/window is a new observation; provenance and archived source bytes are reproducible; concurrent import is rejected; history and ownership endpoints/UI work; business period and import freshness are visibly distinct; portable dependency checks and regressions pass; and no PR4+ schema, behavior, or implementation enters the diff.

This specification is the complete PR3 implementation contract. It is not an Implementation Plan and does not authorize implementation before approval.
