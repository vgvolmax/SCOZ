# SCOZ PR4 — Ozon Search Visibility Import — Implementation Spec

**Status:** Approved implementation specification

**Date:** 2026-08-17

**PR:** PR4 only

**Source authority:** [`2026-08-17-ozon-search-visibility-xlsx-source-contract-v1.md`](./2026-08-17-ozon-search-visibility-xlsx-source-contract-v1.md)

## 1. Purpose, authority, and result

PR4 implements the verified Ozon `explainer_report` source shape. The Source Contract is authoritative for source semantics; this specification does not reinterpret or broaden it. The canonical report type is `OZON_SEARCH_VISIBILITY`, and the canonical import kind is `ozon_search_visibility_xlsx`.

PR4 produces immutable historical observations at grain:

> Product × SearchQuery × Cluster × `observed_at`

with the exact source factors and provenance. It introduces `SearchQuery`, `Cluster`, and `SearchVisibilitySnapshot`, and delivers XLSX → parser → normalized domain → SQLite → import history/coverage → FastAPI → Data UI. It does not implement the analytical Search Visibility UI or heatmap; those belong to PR9.

## 2. Explicit non-goals

PR4 does not implement `seller-queries`, `QueryMetricSnapshot`, `ProductQuerySnapshot`, `RelevantQueryScope`, `BenchmarkSet`, `BenchmarkSetRevision`, `BenchmarkMember`, competitor selection, MPStats, photos, benchmark analytics, Diagnostics, heatmap, Query Opportunity, `SearchPositionSnapshot`, `AdvertisingSnapshot`, Ramp-up, Ozon public API sync, credentials/keystore, a generic source registry, a generic source-resolution framework, persistent jobs, a background queue, pandas, a frontend framework, npm, or new runtime dependencies. `seller-queries` remains PR5 evidence only.

## 3. Frozen domain model

Create `backend/domain/search_visibility.py`.

```python
@dataclass(frozen=True)
class SearchQuery:
    id: int
    query_text: str
    created_at: datetime

@dataclass(frozen=True)
class Cluster:
    id: int
    name: str
    created_at: datetime

class CpoState(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"

@dataclass(frozen=True)
class SearchVisibilitySnapshot:
    id: int
    product_id: int
    search_query_id: int
    cluster_id: int
    observed_at: datetime
    revision: int
    supersedes_snapshot_id: int | None
    payload_sha256: str
    import_batch_id: int
    source_artifact_id: int
    imported_at: datetime
    source_title: str
    seller_name: str
    position: int
    overall_score: Decimal
    promotion_status: str
    cpc_rub: Decimal
    promotion_strategy: str
    cpo_state: CpoState
    cpo_pct: Decimal | None
    relevance_score: Decimal
    rating: Decimal | None
    reviews_count: int | None
    buyer_price_rub: Decimal
    popularity_score: Decimal
    ozon_promotion: bool
    delivery_label: str
    delivery_min_days: int
    delivery_max_days: int
    price_index_pct: Decimal
```

`SearchQuery` identity is the exact canonical source query text after only the Source Contract edge cleanup. No lowercase, case-folding, stemming, lemmatization, internal-space normalization, synonyms, or fuzzy matching is permitted, and repositories must not silently normalize identity.

The canonical entity is exactly `Cluster`. Source metadata `Регион:` maps to `Cluster.name`; do not introduce Region, SearchRegion, GeoRegion, or ClusterAlias. Cluster identity is exact source text after the same edge cleanup.

For CPO, `ACTIVE` requires non-null `cpo_pct`; `DISABLED` and `UNAVAILABLE` both require null `cpo_pct` but remain distinct states. A snapshot contains no raw worksheet row, duplicated query/Cluster text, `is_current`, or derived ranking metric.

## 4. Exact payload and immutable revisions

The payload passed to existing `normalized_payload_sha256()` contains exactly these 19 fields in canonical field order:

```text
source_title
seller_name
position
overall_score
promotion_status
cpc_rub
promotion_strategy
cpo_state
cpo_pct
relevance_score
rating
reviews_count
buyer_price_rub
popularity_score
ozon_promotion
delivery_label
delivery_min_days
delivery_max_days
price_index_pct
```

It excludes `id`, `product_id`, `search_query_id`, `cluster_id`, `observed_at`, `revision`, `supersedes_snapshot_id`, `payload_sha256`, `import_batch_id`, `source_artifact_id`, and `imported_at`. `CpoState` hashes as its string value; Decimal uses the existing deterministic plain-decimal canonicalization; `None` remains JSON null and bool remains JSON boolean. Float serialization and a second decimal convention are forbidden.

Reuse canonical `SnapshotWriteKind` values `NEW`, `DUPLICATE`, and `CORRECTED`, and add:

```python
@dataclass(frozen=True)
class SearchVisibilityWriteResult:
    kind: SnapshotWriteKind
    snapshot: SearchVisibilitySnapshot
```

The exact logical key is `(product_id, search_query_id, cluster_id, observed_at)`. Position is payload, not key material. No existing key inserts revision 1/`NEW`; the same key and payload hash is `DUPLICATE` with no insert; a changed payload inserts current revision + 1/`CORRECTED` and supersedes current. A different query, Cluster, or `observed_at` starts an independent revision 1. History is immutable.

## 5. Parser DTOs and errors

Freeze in `backend/domain/search_visibility.py`:

```python
@dataclass(frozen=True)
class SearchVisibilityRowError:
    row: int
    code: str
    message: str

@dataclass(frozen=True)
class ParsedSearchVisibilityRow:
    source_row: int
    ozon_product_id: str
    snapshot_values: dict[str, object]
    payload_sha256: str

@dataclass(frozen=True)
class ParsedSearchVisibilityReport:
    observed_at: datetime
    query_text: str
    cluster_name: str
    declared_rows: int
    rows_seen: int
    rows: tuple[ParsedSearchVisibilityRow, ...]
    row_errors: tuple[SearchVisibilityRowError, ...]
    duplicate_input_rows: int
    warnings_count: int
```

`rows_seen` is the actual product-row candidate count. A structurally valid report has `rows_seen == declared_rows`.

Freeze base `OzonSearchVisibilityError(ValueError)` and specific errors: `SearchVisibilityUnsupportedWorkbook`, `SearchVisibilityWrongReportType`, `SearchVisibilityIncompatibleReportSchema`, `SearchVisibilityInvalidObservedAt`, `SearchVisibilityInvalidSearchContext`, `SearchVisibilityInvalidProductIdentity`, `SearchVisibilityInvalidMetricValue`, `SearchVisibilityConflictingObservationRows`, `SearchVisibilityNoUsableRows`, `SearchVisibilityConcurrentImportConflict`, `SearchVisibilityUploadTooLarge`, `SearchVisibilityUnsupportedUploadMediaType`, and `SearchVisibilityImportPersistenceError`. Do not reuse the PR3 wrong-report class because the guidance differs.

Row errors are frozen as:

| Condition | Code | Message |
|---|---|---|
| invalid Product ID | `INVALID_PRODUCT_IDENTITY` | `Некорректный ID товара.` |
| invalid position | `INVALID_POSITION` | `Некорректная позиция товара.` |
| malformed numeric/required metric | `INVALID_METRIC_VALUE` | `Некорректное значение показателя.` |
| invalid CPO form | `INVALID_CPO_STATE` | `Некорректное значение оплаты за заказ.` |
| invalid Reviews form | `INVALID_REVIEWS` | `Некорректное значение отзывов.` |
| invalid delivery form | `INVALID_DELIVERY` | `Некорректный срок доставки.` |

A product-row formula maps to `INVALID_METRIC_VALUE`. An unexpected missing value uses the most specific applicable code, otherwise `INVALID_METRIC_VALUE`. These rows remain recoverable unless the Source Contract declares fatal structure.

## 6. Strict parser contract

Create `backend/ingestion/ozon_search_visibility_xlsx.py` with the sole public parser:

```python
parse_ozon_search_visibility_xlsx(path: Path) -> ParsedSearchVisibilityReport
```

Use `openpyxl` directly with `read_only=True` and `data_only=False`. Because application staging uses `.upload-<uuid>.part`, open `path` as a binary file-like object and pass that stream to `openpyxl`; do not pass the `.part` pathname into filename-extension validation. Keep the binary handle alive through `workbook.close()`.

Implement the Source Contract exactly: one worksheet; worksheet name ignored; metadata rows 1–5; semantic-blank A:P rows 6 and 8; exact A:P headers on row 7; ordinary row-9 help text ignored; data begins row 10; trailing semantically blank rows ignored; merged cells unsupported; structural formulas fatal; empty/style-only Q:Z accepted; any non-empty business value Q onward fatal; shifted rows unsupported. Do not require `max_column == 16`; physical 26 columns are evidenced.

Classification is deterministic:

- `SearchVisibilityUnsupportedWorkbook`: unreadable/non-XLSX package;
- `SearchVisibilityWrongReportType`: readable XLSX clearly not matching the expected `explainer_report` shape;
- `SearchVisibilityIncompatibleReportSchema`: expected markers exist but schema/structure is incompatible.

Never detect by filename or sheet name, and never fuzzy-match headers. PR3 Products-shaped and PR5 `seller-queries`-shaped workbooks are `WRONG_REPORT_TYPE` here.

For `query_text` and `cluster_name`, remove only U+0020 and U+00A0 at edges; do not use generic `.strip()`. Compose timezone-aware UTC `observed_at` only from exact source `Дата DD/MM/YYYY` plus `Время HH:MM +00`; never use filename or import timestamps. `declared_rows` is a positive integer, and candidate mismatch is fatal incompatible schema.

`ID товара` must be a positive, non-bool Excel integer and becomes a digit string. Resolve it with existing `ProductRepository.resolve_or_create_ozon_product()`. Unknown Products use `is_owned=False`; existing ownership is never modified. Title, seller, source row, and order never define identity.

All localized metrics follow field-specific Source Contract forms, parse directly to Decimal without float, and do not use a generic locale parser. Freeze exact behavior for overall score, two-decimal CPC, three-state CPO, relevance, Reviews, buyer price, popularity, Ozon promotion, delivery, and price index.

Reviews accepts only rating/count or exact `— ` (U+2014 followed by U+0020), which becomes `(rating=None, reviews_count=None)`. Match before stripping; reject `—`, `-`, ` — `, blank, and `Нет данных`. CPO separately accepts exact `—` (U+2014 only) as `UNAVAILABLE`.

The first normalized Product ID establishes its in-file observation. An identical normalized payload keeps one row and increments both `duplicate_input_rows` and `warnings_count`; a differing payload is fatal `SearchVisibilityConflictingObservationRows`. No last-row-wins, and position is not duplicate identity.

The parser may return zero valid rows with row errors and valid metadata. It must not throw merely because every candidate was recoverably invalid. The application then raises `SearchVisibilityNoUsableRows` (`NO_USABLE_ROWS`, 422, `В отчёте нет пригодных строк товаров.`), retaining known context and making no SearchQuery, Cluster, Product, or snapshot mutation.

## 7. Result, failure, summary, and unified history DTOs

Freeze:

```python
@dataclass(frozen=True)
class OzonSearchVisibilityImportResult:
    import_batch_id: int
    report_type: Literal["OZON_SEARCH_VISIBILITY"]
    status: ImportStatus
    observed_at: datetime | None
    query_text: str | None
    cluster_name: str | None
    declared_rows: int | None
    rows_seen: int
    rows_accepted: int
    rows_skipped: int
    duplicate_observations: int
    new_observations: int
    corrected_revisions: int
    warnings_count: int
    row_errors_total: int
    row_errors: tuple[SearchVisibilityRowError, ...]
    row_errors_truncated: bool
    source_artifact: SourceArtifact
    imported_at: datetime

class OzonSearchVisibilityImportFailure(Exception):
    error: OzonSearchVisibilityError
    result: OzonSearchVisibilityImportResult | None

@dataclass(frozen=True)
class OzonSearchVisibilityImportSummary:
    import_batch_id: int
    source: str
    import_kind: str
    status: ImportStatus
    observed_at: datetime | None
    query_text: str | None
    cluster_name: str | None
    declared_rows: int | None
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

The result has no analytical-readiness status. Before an ImportBatch exists failure has `result=None`; after it exists, failure returns a FAILED result whenever a durable batch result exists.

Add to `backend/domain/lineage.py` the typed read model:

```python
@dataclass(frozen=True)
class ImportHistoryItem:
    import_batch_id: int
    source: str
    import_kind: str
    report_type: Literal["OZON_PRODUCTS", "OZON_SEARCH_VISIBILITY"]
    status: ImportStatus
    report_generated_on: date | None
    report_window_days: int | None
    observed_at: datetime | None
    query_text: str | None
    cluster_name: str | None
    declared_rows: int | None
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

This is only a typed history read DTO, not generic metadata JSON, a registry, or a plugin system.

## 8. Migration 003 and schema

Create `backend/persistence/migrations/migration_003_ozon_search_visibility_import.py` and append exactly `(3, "ozon_search_visibility_import", "backend.persistence.migrations.migration_003_ozon_search_visibility_import")` after migration 002. Do not renumber migrations. This additive-tables/nullable-columns migration requires no backup.

Exact dimension DDL:

```sql
CREATE TABLE search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (query_text)
)

CREATE TABLE clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (name)
)
```

Default SQLite BINARY equality is required: no `COLLATE NOCASE`, aliases, or alias tables.

Exact snapshot DDL:

```sql
CREATE TABLE search_visibility_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    search_query_id INTEGER NOT NULL REFERENCES search_queries(id),
    cluster_id INTEGER NOT NULL REFERENCES clusters(id),
    observed_at TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    supersedes_snapshot_id INTEGER NULL REFERENCES search_visibility_snapshots(id),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
    source_artifact_id INTEGER NOT NULL REFERENCES source_artifacts(id),
    imported_at TEXT NOT NULL,
    source_title TEXT NOT NULL,
    seller_name TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    overall_score TEXT NOT NULL,
    promotion_status TEXT NOT NULL,
    cpc_rub TEXT NOT NULL,
    promotion_strategy TEXT NOT NULL,
    cpo_state TEXT NOT NULL CHECK (cpo_state IN ('ACTIVE', 'DISABLED', 'UNAVAILABLE')),
    cpo_pct TEXT NULL,
    relevance_score TEXT NOT NULL,
    rating TEXT NULL,
    reviews_count INTEGER NULL CHECK (reviews_count IS NULL OR reviews_count >= 0),
    buyer_price_rub TEXT NOT NULL,
    popularity_score TEXT NOT NULL,
    ozon_promotion INTEGER NOT NULL CHECK (ozon_promotion IN (0, 1)),
    delivery_label TEXT NOT NULL,
    delivery_min_days INTEGER NOT NULL CHECK (delivery_min_days >= 0),
    delivery_max_days INTEGER NOT NULL CHECK (delivery_max_days >= 0),
    price_index_pct TEXT NOT NULL,
    UNIQUE (product_id, search_query_id, cluster_id, observed_at, revision),
    CHECK (delivery_min_days <= delivery_max_days),
    CHECK ((rating IS NULL) = (reviews_count IS NULL)),
    CHECK (
        (cpo_state = 'ACTIVE' AND cpo_pct IS NOT NULL)
        OR (cpo_state IN ('DISABLED', 'UNAVAILABLE') AND cpo_pct IS NULL)
    )
)
```

Application/repository layers validate canonical decimals and hashes. Create indexes:

```text
idx_search_visibility_current(product_id, search_query_id, cluster_id, observed_at, revision DESC)
idx_search_visibility_context(search_query_id, cluster_id, observed_at DESC, product_id, revision DESC)
idx_search_visibility_product(product_id, search_query_id, cluster_id, observed_at DESC, revision DESC)
idx_search_visibility_import_batch_id(import_batch_id)
idx_search_visibility_source_artifact_id(source_artifact_id)
```

Create no analytics or materialized tables.

Migration 003 adds nullable `import_batches` columns `observed_at TEXT`, `search_query_text TEXT`, `cluster_name TEXT`, and `declared_rows INTEGER CHECK (declared_rows IS NULL OR declared_rows > 0)`. Reuse all PR3 counter columns. Do not duplicate counters; PR3 `report_generated_on` and `report_window_days` remain unchanged.

## 9. Repository contracts

Create `backend/persistence/repositories/search_dimensions.py`:

```python
class SearchDimensionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None
    def get_search_query(self, query_id: int) -> SearchQuery | None
    def resolve_search_query(self, query_text: str) -> SearchQuery
    def get_cluster(self, cluster_id: int) -> Cluster | None
    def resolve_cluster(self, name: str) -> Cluster
```

Resolve exact identity only. Reject empty/non-canonical input rather than changing it, and use `utc_now()` for `created_at`.

Create `backend/persistence/repositories/search_visibility_snapshots.py`:

```python
class SearchVisibilitySnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None
    def find_current(
        self, *, product_id: int, search_query_id: int, cluster_id: int,
        observed_at: datetime,
    ) -> SearchVisibilitySnapshot | None
    def resolve_revision(
        self, *, product_id: int, search_query_id: int, cluster_id: int,
        observed_at: datetime, payload_sha256: str, import_batch_id: int,
        source_artifact_id: int, imported_at: datetime,
        snapshot_values: Mapping[str, object],
    ) -> SearchVisibilityWriteResult
```

Expose no competing aliases or historical update/delete method.

Extend `LineageRepository` with exact terminal method:

```python
finish_ozon_search_visibility_import(
    batch_id: int, *, status: ImportStatus, observed_at: datetime | None,
    query_text: str | None, cluster_name: str | None,
    declared_rows: int | None, rows_seen: int, rows_accepted: int,
    rows_skipped: int, duplicate_observations: int, new_observations: int,
    corrected_revisions: int, warnings_count: int, row_errors_total: int,
) -> OzonSearchVisibilityImportSummary
```

It has no public `finished_at`. Also add `list_ozon_search_visibility_imports(*, limit: int, offset: int)`, `count_ozon_search_visibility_imports()`, and `fail_running_ozon_search_visibility_imports(*, finished_at: datetime) -> int`.

Replace the PR3-specific archive-reference read with `list_referenced_archive_paths() -> set[str]`. It returns every non-null `SourceArtifact.stored_relpath` in the generated import archive area, independent of supported import kind. PR3 recovery must use it, so neither PR3 nor PR4 can delete the other kind’s referenced archive. This does not create a source registry.

Add `list_import_history(*, limit: int, offset: int) -> list[ImportHistoryItem]` and `count_import_history()`. Include exactly `ozon_products_xlsx` and `ozon_search_visibility_xlsx`, ordered `started_at DESC, id DESC`; map them respectively to `OZON_PRODUCTS` and `OZON_SEARCH_VISIBILITY`, with unused type-specific context fields as `None`. Preserve PR3-specific methods.

## 10. Product catalog boundary

PR4 may create many competitor Product records, but they must not enter the current own-product selection merely because an Ozon ID is known. Narrow `ProductRepository.list_ozon_products()` and `count_ozon_products()` to Ozon Products having at least one `product_snapshots` row—the current v1 PR3 product-report catalog.

Search-Visibility-only competitors remain canonical Products, remain in `product_external_identities`, are not deleted or marked owned, and do not require a separate CompetitorProduct. They are hidden from `/api/products` and its total. If PR3 later imports one, the same identity is reused and it becomes visible. Regression tests are mandatory.

## 11. Shared import runtime and PR3 refactor

Create `backend/application/import_runtime.py` containing only:

- `MAX_UPLOAD_BYTES = 25 * 1024 * 1024`;
- `MAX_ROW_ERRORS = 50`;
- `IMPORT_LOCK = threading.Lock()`;
- `ARCHIVE_RE`, using the generated archive filename regex already proven by PR3;
- `safe_original_basename()`.

It contains no SQL, parsing, source registry, generic import engine, jobs, or workflow objects.

Modify `backend/application/ozon_products_import.py` only to import those five names, preserving them in its module namespace for existing callers/tests, and replace module-local `_IMPORT_LOCK` with shared `IMPORT_LOCK`. Preserve all other PR3 behavior. PR3 and PR4 imports cannot run simultaneously.

## 12. PR4 application lifecycle

Create `backend/application/ozon_search_visibility_import.py` with:

```python
import_ozon_search_visibility_xlsx(
    *, upload: BinaryIO, original_name: str,
    db_path: Path | None = None, data_dir: Path = DATA_DIR,
) -> OzonSearchVisibilityImportResult

recover_interrupted_ozon_search_visibility_imports(
    *, db_path: Path | None = None, data_dir: Path = DATA_DIR,
) -> None
```

Use shared `IMPORT_LOCK`, exact 25 MiB limit, and require `.xlsx`.

Reuse the PR3 archive lifecycle under `data/imports/`: stage `.upload-<uuid4>.part`, compute SHA-256/byte size and fsync, then commit a RUNNING batch/artifact with source `ozon`, import/artifact kind `ozon_search_visibility_xlsx`, and null `stored_relpath`. Fully parse before any SearchQuery, Cluster, Product, or snapshot mutation.

If there are zero usable rows: delete `.part`; finish the batch FAILED; persist known observed time, query, Cluster, declared/candidate count, and skipped/error counters; keep SourceArtifact metadata with null `stored_relpath`; mutate no dimension/Product/snapshot; raise `OzonSearchVisibilityImportFailure` containing `SearchVisibilityNoUsableRows` and the FAILED result.

With at least one usable row, reserve a final generated archive without overwrite using `<UTC YYYYMMDDTHHMMSSffffffZ>-<sha256>.xlsx`, atomically move the stage, then perform one transaction: set artifact stored path; resolve SearchQuery and Cluster; resolve/create Products; resolve revisions; compute counters; finish batch; commit once. No row errors means SUCCESS; any row errors means PARTIAL_SUCCESS. An identical in-file duplicate alone is a warning, not partial success.

If persistence fails after archive creation, roll back the database transaction; delete only the final archive created by this attempt and never a pre-existing collision target; finish the batch FAILED in a separate compensation transaction; retain null artifact path; allow no partial SearchQuery/Cluster/Product/snapshot mutation; expose `SearchVisibilityImportPersistenceError`.

PR4 startup recovery changes only RUNNING `ozon_search_visibility_xlsx` batches to FAILED while preserving durable known columns, removes stale `.upload-*.part`, and deletes only exact generated archive names that are unreferenced according to `list_referenced_archive_paths()`. It never deletes arbitrary/manual files or any referenced PR3/PR4 archive. Lifespan invokes PR3 and PR4 recovery; no persistent job system is added.

## 13. FastAPI contracts and errors

Add `POST /api/imports/ozon-search-visibility`, accepting multipart exact field `file`. Wrong content type is 415; missing/wrong multipart field is 422. Always close `UploadFile`. SUCCESS and PARTIAL_SUCCESS return HTTP 200—not 207—and the exact result DTO. Decimal snapshot metrics are not exposed by this endpoint.

Freeze error mapping:

| Error | HTTP | Code | Message |
|---|---:|---|---|
| `SearchVisibilityUnsupportedWorkbook` | 422 | `UNSUPPORTED_WORKBOOK` | `Не удалось прочитать XLSX-файл.` |
| `SearchVisibilityWrongReportType` | 422 | `WRONG_REPORT_TYPE` | `Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи.` |
| `SearchVisibilityIncompatibleReportSchema` | 422 | `INCOMPATIBLE_REPORT_SCHEMA` | `Версия или структура отчёта не поддерживается.` |
| `SearchVisibilityInvalidObservedAt` | 422 | `INVALID_OBSERVED_AT` | `Не удалось прочитать дату или время наблюдения.` |
| `SearchVisibilityInvalidSearchContext` | 422 | `INVALID_SEARCH_CONTEXT` | `Не удалось прочитать поисковый запрос или кластер.` |
| `SearchVisibilityConflictingObservationRows` | 422 | `CONFLICTING_OBSERVATION_ROWS` | `В отчёте есть противоречивые строки одного товара.` |
| `SearchVisibilityNoUsableRows` | 422 | `NO_USABLE_ROWS` | `В отчёте нет пригодных строк товаров.` |
| `SearchVisibilityConcurrentImportConflict` | 409 | `CONCURRENT_IMPORT_CONFLICT` | `Другой импорт уже выполняется. Дождитесь его завершения.` |
| `SearchVisibilityUploadTooLarge` | 413 | `UPLOAD_TOO_LARGE` | `Размер файла превышает 25 МиБ.` |
| `SearchVisibilityUnsupportedUploadMediaType` | 415 | `UNSUPPORTED_UPLOAD_MEDIA_TYPE` | `Выберите XLSX-файл.` |
| `SearchVisibilityImportPersistenceError` | 500 | `IMPORT_PERSISTENCE_ERROR` | `Не удалось сохранить импорт. Данные не изменены.` |

Responses expose no stack trace, filesystem path, or workbook content. Return the first 50 row errors in source order, plus durable `row_errors_total` and `row_errors_truncated`; truncation affects response detail only.

Make existing `GET /api/imports` genuinely unified while preserving `{ "items": [...], "total": N }`. Use unified repository methods and serialize `ImportHistoryItem`, newest first. Do not merge separate histories in the frontend.

PR4 history entries satisfy the master-plan coverage summary by exposing query, Cluster, `observed_at`, declared/seen/accepted/skipped counts, duplicate/new/corrected counts, warnings/errors, import time, and artifact filename. Do not add coverage/analytics tables, heatmap endpoints, or aggregate Cluster scores.

`GET /api/products` continues to represent the PR3 product-data catalog, not every identity discovered through Search Visibility, as specified in section 10.

## 14. Static Data UI

Keep global navigation `Товары / Данные / Настройки`; add no navigation. In `Данные`, show two explicit upload cards: `Отчёт «Товары на Ozon»` and `Поисковая видимость Ozon`. The latter may say `XLSX-файл explainer_report с факторами поисковой выдачи.`

The second uploader must show selected filename immediately; loading text; success, partial success, and error; row-error detail for partial results; disabled submit during request; and refreshed unified history after completion. Its summary shows query, Cluster, UTC observation date/time, accepted/skipped, and useful duplicate/new/corrected counts. Never show fake percentage progress.

History distinguishes `OZON_PRODUCTS` (`Товары на Ozon`) and `OZON_SEARCH_VISIBILITY` (`Поисковая видимость Ozon`). PR3 displays generated date/window; PR4 displays query, Cluster, `observed_at`, and declared/accepted/skipped counts. Never hardcode every item as Products.

PR4 UI proves import/history/coverage only. It contains no heatmap, ranking-factor comparison, Cluster score, Query Opportunity, benchmark, competitor workflow, or own-vs-competitor analytics.

## 15. Synthetic fixtures and test contract

Extend `tests/xlsx_factory.py`; never commit real evidence XLSX. Add an exact synthetic `OZON_SEARCH_VISIBILITY` builder supporting mutations of metadata, headers, rows, extra sheets, Q:Z business values, formulas, merged cells, and blank/style trailing rows, using only synthetic names/IDs.

Create `tests/test_ozon_search_visibility_parser.py` covering: valid fixture and exact UTC metadata; U+0020/U+00A0 query-edge cleanup; preserved internal query differences; Cluster identity; Q:Z style/empty acceptance and business-value rejection; row 6; row 8 `None`/exact `""` acceptance and whitespace rejection; ignored row-9 ordinary text and fatal formula; exact headers/newlines; extra sheet; merged cells; wrong report plus Products- and `seller-queries`-shaped wrong types; bad time/date and non-UTC; declared mismatch; positions above 108 and failures; integer Product ID plus bool/text rejection; all localized decimal forms and CPC precision; all CPO states/exact sentinel; Reviews normal/exact `— ` plus rejection of `—` and ` — `; grouped review count/buyer price; Ozon Да/Нет; delivery grammar/range; price index; recoverable row formula/required blank; identical/conflicting duplicates; and zero usable returned with errors.

Create `tests/test_search_dimensions_repository.py` covering exact reuse; similar/case/internal-space query separation; canonical input requirement; exact Cluster reuse; Moscow/Petersburg separation; no aliases; and UTC creation.

Create `tests/test_search_visibility_snapshot_repository.py` covering NEW revision 1, DUPLICATE without insert, CORRECTED revision 2, independent Cluster/time/query observations, position correction, null Reviews pair, all CPO states, Decimal/bool round trips, invalid hash, timezone validation, immutability, and unique constraint.

Create `tests/test_ozon_search_visibility_import.py` covering shared safe basename; exact/+1 upload limits; hash/size/fsync/staging; SUCCESS/PARTIAL_SUCCESS; zero-usable durable failure context; duplicate/corrected and changed Cluster/query/time; unknown non-owned/existing owned Products; hidden visibility-only Products; in-file duplicate/conflict; >50 error cap; cross-import lock; collision preservation; rollback/compensation after reservation; startup recovery; cross-kind referenced archive safety; and unrelated file preservation.

Create `tests/test_ozon_search_visibility_api.py` covering valid/partial POST 200; wrong/schema/time/context/zero-usable 422; content type 415; missing file 422; oversized 413; lock 409 with null result; persistence 500 with FAILED result; no trace/path leakage; unified mixed newest-first history with exact PR4 context; unpolluted Products API; and TestClient lifespan recovery.

Existing integration tests may change only for real PR4 integration/regression: `tests/test_database.py`, `tests/test_migrations.py`, `tests/test_lineage_repository.py`, `tests/test_product_repository.py`, `tests/test_ozon_products_import.py`, `tests/test_ozon_products_api.py`, `tests/test_frontend_contract.py`, `tests/test_runtime_contract.py`, and `tests/windows_smoke.ps1`. PR3 expectations must not be weakened.

Use TDD—RED → minimal GREEN → refactor → adjacent regression—especially for query/Cluster identity, revisions, the Reviews sentinel, Product-list pollution, shared archive recovery, cross-import locking, and API taxonomy.

## 16. Portable acceptance and dependencies

No dependency changes are allowed: `requirements.txt` and `requirements-dev.txt` remain unchanged; pandas and httpx2 are forbidden; existing `openpyxl==3.1.5` is sufficient.

Windows smoke must verify migrations 1/2/3; unchanged PR3 portable import; synthetic PR4 import inside the portable runtime; PR4 archive under `data/imports`; referenced archive survival through restart/repair; data survival through runtime rebuild; and spaces/Cyrillic paths. `tests/windows_smoke.ps1` stays ASCII-only and uses the existing ASCII-safe technique for runtime Cyrillic strings.

## 17. Exact implementation file map

The future implementation is expected to create exactly these 12 files:

1. `backend/domain/search_visibility.py`
2. `backend/ingestion/ozon_search_visibility_xlsx.py`
3. `backend/application/import_runtime.py`
4. `backend/application/ozon_search_visibility_import.py`
5. `backend/persistence/migrations/migration_003_ozon_search_visibility_import.py`
6. `backend/persistence/repositories/search_dimensions.py`
7. `backend/persistence/repositories/search_visibility_snapshots.py`
8. `tests/test_ozon_search_visibility_parser.py`
9. `tests/test_search_dimensions_repository.py`
10. `tests/test_search_visibility_snapshot_repository.py`
11. `tests/test_ozon_search_visibility_import.py`
12. `tests/test_ozon_search_visibility_api.py`

No adjacent new file is allowed without a concrete blocker and explicit approval.

Expected modifications are exactly these 19 files:

1. `backend/domain/lineage.py`
2. `backend/application/ozon_products_import.py`
3. `backend/persistence/migrations/runner.py`
4. `backend/persistence/repositories/lineage.py`
5. `backend/persistence/repositories/products.py`
6. `backend/main.py`
7. `frontend/index.html`
8. `frontend/assets/css/app.css`
9. `frontend/assets/js/app.js`
10. `tests/xlsx_factory.py`
11. `tests/test_database.py`
12. `tests/test_migrations.py`
13. `tests/test_lineage_repository.py`
14. `tests/test_product_repository.py`
15. `tests/test_ozon_products_import.py`
16. `tests/test_ozon_products_api.py`
17. `tests/test_frontend_contract.py`
18. `tests/test_runtime_contract.py`
19. `tests/windows_smoke.ps1`

The full planned implementation scope is 31 tracked files: 12 created + 19 modified. A listed modification may remain unchanged if unnecessary, but no extra tracked file may be added without explicit review.

Absent a proven blocker, protect `launcher.py`, `RUN_SERVER.cmd`, `start.bat`, `backend/config.py`, `backend/persistence/connection.py`, `requirements.txt`, `requirements-dev.txt`, `.github/workflows/ci.yml`, and `.gitignore`. Do not modify frozen prior specs/plans.

## 18. Sequencing guidance for the later plan

The later PR4 Implementation Plan should sequence approximately: (1) synthetic XLSX factory/domain normalization; (2) migration 003; (3) SearchQuery/Cluster repository; (4) snapshot repository; (5) strict parser; (6) lineage/history; (7) shared runtime/lock plus PR3 regression; (8) PR4 lifecycle/recovery; (9) FastAPI; (10) static Data UI/history; (11) Windows/full verification.

This is sequencing guidance only. This docs PR does not create an Implementation Plan and does not implement PR4.

## 19. Definition of Done for future implementation

Future PR4 is complete only when strict real-source semantics are implemented; Cluster remains key material; exact query identity and exact Reviews/CPO sentinels are preserved; normalized metrics have correct types; dimension/Product mutations are atomic; history is immutable; duplicate/correction behavior is proven; fatal imports cannot partially mutate domain; competitor discoveries do not pollute Products; PR3 behavior remains intact; cross-kind archives survive recovery; unified history shows both types; synthetic parser/service/API tests and full pytest pass; JS syntax passes; full Windows portable smoke passes; no real XLSX or dependency change enters the diff; and the diff matches approved scope.

## 20. Specification consistency gate

Reviewers must confirm: no unresolved placeholder; `seller-queries` remains PR5-only; Cluster is canonical and in the logical key; `observed_at` comes exactly from source date/time; the payload has exactly 19 fields; Reviews `— ` is distinct from CPO `—`; query identity has no fuzzy normalization; visibility-only Products are hidden from the own-product page; history is unified; archive recovery is cross-kind safe; PR4 has no heatmap/analytics or dependency addition; and the exact 12-create/19-modify file map is recorded.

This specification is the complete approved PR4 implementation contract. It is not an Implementation Plan and does not authorize any PR4 implementation in this docs-only change.
