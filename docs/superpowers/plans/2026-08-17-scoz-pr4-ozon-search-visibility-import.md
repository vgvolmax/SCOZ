# SCOZ PR4 — Ozon Search Visibility Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import verified Ozon `explainer_report` XLSX files into immutable `Product × SearchQuery × Cluster × observed_at` history with strict source semantics, provenance, unified import history, safe competitor Product handling, and portable Windows support.

**Architecture:** Reuse the existing PR3 ingestion/provenance/revision architecture rather than creating a generic import framework. PR4 adds SearchQuery, Cluster and SearchVisibilitySnapshot, introduces only the minimal shared import runtime justified by the second XLSX importer, and preserves thin FastAPI/static UI boundaries.

**Tech Stack:** Python 3.13, stdlib sqlite3, FastAPI 0.139.2, openpyxl 3.1.5, committed HTML/CSS/JavaScript, pytest 8.4.2, Windows PowerShell smoke.

## Global Constraints

- No dependency changes.
- No pandas.
- No httpx2.
- No npm/frontend framework.
- No real XLSX committed; every workbook fixture is synthetic and generated in memory.
- No seller-queries / PR5.
- No heatmap/analytics.
- `Cluster` remains the canonical entity and key dimension; do not introduce Region aliases.
- Query identity is exact after only U+0020/U+00A0 edge cleanup; no case-folding, fuzzy matching, stemming, or internal-space normalization.
- Revisions are immutable: duplicate payloads do not insert, corrections append and supersede.
- No SQL outside persistence repositories/migrations.
- No business logic in routes/UI.
- Use one shared process-local import lock only; do not add jobs, queues, or cross-process locking.
- Archive provenance stays under `data/imports` with global cross-kind reference protection.
- The Product page must not be polluted by SearchVisibility-only competitors.
- Protected files remain unchanged: `launcher.py`, `RUN_SERVER.cmd`, `start.bat`, `backend/config.py`, `backend/persistence/connection.py`, `requirements.txt`, `requirements-dev.txt`, `.github/workflows/ci.yml`, and `.gitignore`.
- Full planned implementation scope is at most 31 tracked files: 12 create + 19 allowed modify. An allowed modification may be omitted; a 32nd file requires explicit approval.

## Execution Rules

- Execute the 11 tasks in order. Each task is deliberately self-contained enough to hand to one agent, but consumes only interfaces produced by earlier tasks or already present on main.
- Start every behavioral change with the named RED test, observe the stated failure, add only the named implementation, then rerun targeted and adjacent tests.
- Run commands from the repository root. Do not weaken PR3 assertions to make PR4 pass.
- End each task with `git diff --check`, review only that task's intended paths, and make the focused local commit shown in the task.
- Keep the complete future file map within the 12-create/19-modify boundary recorded in Task 11.

## Task 1: Freeze the domain contract and synthetic workbook primitives

**Files**

- Create: `backend/domain/search_visibility.py`
- Modify: `tests/xlsx_factory.py`
- Create: `tests/test_ozon_search_visibility_parser.py` (domain/factory tests only in this task)

**Consumed interfaces**

- `SnapshotWriteKind` and `canonical_decimal_text` from `backend.domain.product_snapshot`.
- `ImportStatus`, `SourceArtifact`, and `normalized_payload_sha256` from `backend.domain.lineage`.
- Existing in-memory `openpyxl` workbook-building conventions in `tests/xlsx_factory.py`.

**Produced interfaces**

- Frozen dataclasses with exactly the Implementation Spec field order: `SearchQuery`, `Cluster`, `SearchVisibilitySnapshot`, `SearchVisibilityWriteResult`, `SearchVisibilityRowError`, `ParsedSearchVisibilityRow`, `ParsedSearchVisibilityReport`, `OzonSearchVisibilityImportResult`, and `OzonSearchVisibilityImportSummary`.
- `CpoState(str, Enum)` with values `ACTIVE`, `DISABLED`, `UNAVAILABLE`.
- `OzonSearchVisibilityImportFailure(error=..., result=...)` and the complete frozen hierarchy: `OzonSearchVisibilityError`, `SearchVisibilityUnsupportedWorkbook`, `SearchVisibilityWrongReportType`, `SearchVisibilityIncompatibleReportSchema`, `SearchVisibilityInvalidObservedAt`, `SearchVisibilityInvalidSearchContext`, `SearchVisibilityInvalidProductIdentity`, `SearchVisibilityInvalidMetricValue`, `SearchVisibilityConflictingObservationRows`, `SearchVisibilityNoUsableRows`, `SearchVisibilityConcurrentImportConflict`, `SearchVisibilityUploadTooLarge`, `SearchVisibilityUnsupportedUploadMediaType`, `SearchVisibilityImportPersistenceError`.
- `SEARCH_VISIBILITY_PAYLOAD_FIELDS`, `search_visibility_snapshot_payload(values)`, and `search_visibility_payload_sha256(values)`.
- `build_ozon_search_visibility_workbook(...) -> bytes` synthetic fixture primitive.

**Steps**

- [ ] Write RED tests that compare `dataclasses.fields()` against every exact field sequence in Implementation Spec sections 3, 5, and 7; assert all dataclasses are frozen; assert the failure stores the typed `error` and nullable `result`; and assert all named error classes derive from `OzonSearchVisibilityError`.
- [ ] Assert `tuple(state.value for state in CpoState) == ("ACTIVE", "DISABLED", "UNAVAILABLE")` and assert `SearchVisibilityWriteResult.kind` accepts the reused `SnapshotWriteKind` rather than a new enum.
- [ ] Assert `SEARCH_VISIBILITY_PAYLOAD_FIELDS` equals exactly `(source_title, seller_name, position, overall_score, promotion_status, cpc_rub, promotion_strategy, cpo_state, cpo_pct, relevance_score, rating, reviews_count, buyer_price_rub, popularity_score, ozon_promotion, delivery_label, delivery_min_days, delivery_max_days, price_index_pct)` in that order.
- [ ] Build a complete payload and assert canonical output turns `Decimal("52.600")` into `"52.6"`, turns `CpoState.ACTIVE` into `"ACTIVE"`, preserves `True` as a JSON boolean and `None` as JSON null, rejects missing/extra fields, and hashes equal Decimal spellings identically through `normalized_payload_sha256()`.
- [ ] Add a structural factory test that opens generated bytes and checks one worksheet, rows 1–5 exact metadata, blank row 6, exact 16 headers on row 7 including newlines in headers 7 and 9, row 8 variants, ignored help row 9, and product data at row 10. Exercise arguments for `query`, `cluster`, `date`, `time`, `declared_rows`, `headers`, `rows`, `extra_sheet`, merged cells, formula cells, Q:Z values, row-6/row-8 variants, and row-9 variants.
- [ ] Run the RED command:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_parser.py -q
  ```

  Expected initial failure: import error for missing `backend.domain.search_visibility`, followed (as symbols are introduced) by missing builder/payload assertions.
- [ ] Implement the frozen declarations exactly. Derive `SEARCH_VISIBILITY_PAYLOAD_FIELDS` from `fields(SearchVisibilitySnapshot)[11:]` and assert/retain the explicit 19-field contract. In `search_visibility_snapshot_payload`, require exact key-set equality, iterate canonical field order, encode `Decimal` with imported `canonical_decimal_text`, encode `CpoState` with `.value`, and otherwise preserve strings, integers, booleans, and `None`; pass that dict to `normalized_payload_sha256`.
- [ ] Implement `build_ozon_search_visibility_workbook` as a keyword-configurable in-memory workbook. Default metadata is synthetic (`Дата: 17/08/2026`, `Запрос: тестовый запрос`, `Время: 03:55 +00`, `Регион: г. Тестоград, Россия`, declared count matching default rows); default A:P headers are the exact source signature; mutations write explicit cell values/styles/formulas/merges without loading evidence files.
- [ ] Rerun the targeted command and require all Task 1 tests pass:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] Run adjacent domain/factory regressions:

  ```bash
  python -m pytest tests/test_ozon_products_parser.py tests/test_ozon_products_import.py -q
  ```

- [ ] Run `git diff --check`, inspect `git diff -- backend/domain/search_visibility.py tests/xlsx_factory.py tests/test_ozon_search_visibility_parser.py`, then commit:

  ```bash
  git add backend/domain/search_visibility.py tests/xlsx_factory.py tests/test_ozon_search_visibility_parser.py
  git commit -m "test/domain: add search visibility domain and XLSX fixtures"
  ```

## Task 2: Add migration 003 with exact constraints

**Files**

- Create: `backend/persistence/migrations/migration_003_ozon_search_visibility_import.py`
- Modify: `backend/persistence/migrations/runner.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_migrations.py`

**Consumed interfaces**

- Migration runner transaction/registration convention and migrations 001/002.
- Exact DDL in Implementation Spec section 8.

**Produced interfaces**

- Migration registry entry `(3, "ozon_search_visibility_import", "backend.persistence.migrations.migration_003_ozon_search_visibility_import")`.
- Tables `search_queries`, `clusters`, `search_visibility_snapshots` and exactly four nullable `import_batches` columns: `observed_at`, `search_query_text`, `cluster_name`, `declared_rows`.

**Steps**

- [ ] Write RED tests for fresh initialization and a database stopped after migration 001 then upgraded through 002/003. Assert migration history is exactly `[(1, "core_foundation"), (2, "ozon_products_import"), (3, "ozon_search_visibility_import")]`.
- [ ] Inspect `PRAGMA table_info`, `foreign_key_list`, `index_list`, `index_info`, and normalized `sqlite_master.sql`. Assert exact columns only; UNIQUE exact query and Cluster identity under default BINARY collation; logical revision uniqueness; `revision > 0`; Product/query/Cluster/import/artifact/self-supersedes FKs; all five named indexes and column orders.
- [ ] Add direct constraint tests: query/Cluster case variants coexist but exact duplicates fail; duplicate `(product, query, cluster, observed_at, revision)` fails; `ACTIVE` requires `cpo_pct`, disabled/unavailable require null; rating/reviews are both null or both non-null; review count is nonnegative; delivery endpoints are nonnegative and min ≤ max; `declared_rows` is null or positive.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_database.py tests/test_migrations.py -q
  ```

  Expected initial failure: schema version remains `[1, 2]`, new tables/columns/indexes do not exist, and constraint inserts fail with `no such table/column`.
- [ ] Implement `up(conn)` with individual `conn.execute(...)` statements only—never `executescript`. Create the two exact dimension tables, the exact snapshot table, the five exact indexes, then add only the four specified nullable columns to `import_batches`.
- [ ] Append the exact registry tuple after migration 002; do not renumber or change earlier migrations.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_database.py tests/test_migrations.py -q
  ```

- [ ] Run adjacent persistence regressions:

  ```bash
  python -m pytest tests/test_product_repository.py tests/test_product_snapshot_repository.py tests/test_lineage_repository.py -q
  ```

- [ ] Run `git diff --check`, inspect only the four task paths, then commit:

  ```bash
  git add backend/persistence/migrations/migration_003_ozon_search_visibility_import.py backend/persistence/migrations/runner.py tests/test_database.py tests/test_migrations.py
  git commit -m "feat: add search visibility migration"
  ```

## Task 3: Persist exact SearchQuery and Cluster identities

**Files**

- Create: `backend/persistence/repositories/search_dimensions.py`
- Create: `tests/test_search_dimensions_repository.py`

**Consumed interfaces**

- `SearchQuery` and `Cluster` from Task 1.
- Migration 003 tables from Task 2.
- `utc_now()` and `datetime_from_db()` from `backend.domain.lineage`.

**Produced interfaces**

```python
class SearchDimensionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def get_search_query(self, query_id: int) -> SearchQuery | None: ...
    def resolve_search_query(self, query_text: str) -> SearchQuery: ...
    def get_cluster(self, cluster_id: int) -> Cluster | None: ...
    def resolve_cluster(self, name: str) -> Cluster: ...
```

**Steps**

- [ ] Write RED tests proving exact query reuse, while similar wording, case differences, and internal-space differences create separate identities. Prove exact Cluster reuse, Moscow/Petersburg separation, case separation, and absence of aliasing.
- [ ] Parameterize invalid canonical callers: empty string, U+0020 at either edge, U+00A0 at either edge, and strings consisting only of either edge character. Define canonical validation precisely: input must equal its own Source-Contract edge-normalized form, where only leading/trailing characters in `{U+0020, U+00A0}` are removed. The repository rejects invalid caller data; the parser performs normalization.
- [ ] Assert getters return `None` for absent IDs, mapped values are domain dataclasses rather than `sqlite3.Row`, and `created_at` is timezone-aware UTC.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_search_dimensions_repository.py -q
  ```

  Expected initial failure: module `backend.persistence.repositories.search_dimensions` is absent.
- [ ] Implement two small mappers using `datetime_from_db`. Add one private predicate that computes `value.strip(" \u00a0")` and requires nonempty equality without returning a changed identity. For each resolver, validate first, select by exact `=`, insert with `datetime_to_db(utc_now())` if absent, and retrieve by inserted ID. Do not use `LOWER`, `COLLATE NOCASE`, aliases, or `INSERT OR REPLACE`.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_search_dimensions_repository.py -q
  ```

- [ ] Run adjacent migration/domain regressions:

  ```bash
  python -m pytest tests/test_migrations.py tests/test_database.py tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] Run `git diff --check`, inspect the two task paths, then commit:

  ```bash
  git add backend/persistence/repositories/search_dimensions.py tests/test_search_dimensions_repository.py
  git commit -m "feat: add search query and cluster persistence"
  ```

## Task 4: Persist immutable SearchVisibility revisions

**Files**

- Create: `backend/persistence/repositories/search_visibility_snapshots.py`
- Create: `tests/test_search_visibility_snapshot_repository.py`

**Consumed interfaces**

- `SearchVisibilitySnapshot`, `SearchVisibilityWriteResult`, `CpoState`, `SEARCH_VISIBILITY_PAYLOAD_FIELDS` from Task 1.
- `SnapshotWriteKind`, `canonical_decimal_text`; `datetime_to_db()`/`datetime_from_db()`.
- Migration 003 snapshot table and valid Product/query/Cluster/batch/artifact fixture IDs.

**Produced interfaces**

```python
class SearchVisibilitySnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def find_current(self, *, product_id: int, search_query_id: int,
                     cluster_id: int, observed_at: datetime) -> SearchVisibilitySnapshot | None: ...
    def resolve_revision(self, *, product_id: int, search_query_id: int,
                         cluster_id: int, observed_at: datetime,
                         payload_sha256: str, import_batch_id: int,
                         source_artifact_id: int, imported_at: datetime,
                         snapshot_values: Mapping[str, object]) -> SearchVisibilityWriteResult: ...
```

**Steps**

- [ ] Write RED tests for revision 1 `NEW`; same hash `DUPLICATE` with unchanged row count; changed position/hash `CORRECTED` revision 2 with `supersedes_snapshot_id`; and proof that revision 1 remains byte-for-byte immutable.
- [ ] Assert different Cluster, query, or `observed_at` each yields independent `NEW`. Assert `find_current` uses the exact four-part key and returns highest `revision DESC`.
- [ ] Cover Reviews `(None, None)`, all three CPO states, Decimal canonical TEXT round-trip (including trailing zeros), bool SQLite `0/1` round-trip, and preservation of every `None`.
- [ ] Reject naive `observed_at` and `imported_at`, non-lowercase/non-64-hex hashes, and any missing/extra `snapshot_values` field before SQL. Directly attempt duplicate revision insertion and require SQLite's unique defense.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_search_visibility_snapshot_repository.py -q
  ```

  Expected initial failure: repository module is absent.
- [ ] Implement a row mapper with explicit conversions: Decimal fields from stored TEXT via `Decimal`; `cpo_state` via `CpoState(value)`; `ozon_promotion` via `bool(integer)` after requiring 0/1; datetimes via `datetime_from_db`; nullable rating/CPO/reviews remain `None`.
- [ ] Implement an encoder with the inverse mapping: Decimal via `canonical_decimal_text`, enum via `.value`, bool via `int`, aware datetimes via `datetime_to_db`, and `None` unchanged. Validate hash with `re.fullmatch(r"[0-9a-f]{64}", value)` and exact payload field set.
- [ ] `resolve_revision` calls `find_current`; equal hash returns `DUPLICATE` and current row; otherwise insert revision `1`/null supersedes or current+1/current ID, and return `NEW` or `CORRECTED`. Expose no update/delete/history mutation API.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_search_visibility_snapshot_repository.py -q
  ```

- [ ] Run adjacent persistence regressions:

  ```bash
  python -m pytest tests/test_product_snapshot_repository.py tests/test_search_dimensions_repository.py tests/test_migrations.py -q
  ```

- [ ] Run `git diff --check`, inspect the two task paths, then commit:

  ```bash
  git add backend/persistence/repositories/search_visibility_snapshots.py tests/test_search_visibility_snapshot_repository.py
  git commit -m "feat: persist search visibility revisions"
  ```

## Task 5: Parse the verified XLSX source contract strictly

**Files**

- Create: `backend/ingestion/ozon_search_visibility_xlsx.py`
- Modify: `tests/test_ozon_search_visibility_parser.py`

**Consumed interfaces**

- Task 1 DTOs, errors, payload hashing, and synthetic workbook builder.
- Exact Source Contract v1 metadata, headers, sentinel, localized number, structural, and detection rules.

**Produced interfaces**

```python
def parse_ozon_search_visibility_xlsx(path: Path) -> ParsedSearchVisibilityReport: ...
```

**Steps**

- [ ] Expand RED tests into the complete parser matrix: valid exact UTC context; U+0020/U+00A0 edge cleanup and preserved internal differences; exact Cluster text; style/empty Q:Z accepted and any business value rejected; row 6 blank only; row 8 `None` and exact `""` accepted while whitespace is rejected; row-9 ordinary text ignored and formula fatal; exact headers including newline; extra sheet and merged cells fatal.
- [ ] Add detection tests for unreadable bytes → `SearchVisibilityUnsupportedWorkbook`; readable unrelated, PR3 Products-shaped, and synthetic seller-queries-shaped workbook → `SearchVisibilityWrongReportType`; expected markers with shifted/bad structure → `SearchVisibilityIncompatibleReportSchema`. Do not use filename or worksheet name in expectations.
- [ ] Cover exact date/time formats, invalid calendar date/time, any non-`+00` offset, empty query/Cluster after edge cleanup, positive integer declared count, and candidate/declared mismatch.
- [ ] Cover every product field: position positive and above 108 unchanged; Product ID positive non-bool integer only (reject float/text/bool); required title/seller; all specified comma decimals and grouping; CPC exactly supported precision; CPO ACTIVE/DISABLED/UNAVAILABLE including exact `—`; Reviews rating/count and exact `— ` accepted while `—`, ` — `, blank, hyphen, and `Нет данных` are rejected; grouped review count/buyer price; Ozon promotion exact `Да`/`Нет`; delivery grammar and min/max range; price index grammar/value.
- [ ] Cover product-row formula/required blank as recoverable specific row errors; exact row codes/messages; all rows invalid returns a report with `rows=()` and ordered errors; identical repeated Product keeps first row and increments duplicate/warning; conflicting normalized payload raises `SearchVisibilityConflictingObservationRows`.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_parser.py -q
  ```

  Expected initial failure: parser module is absent and parser-specific imports cannot collect.
- [ ] Implement small private helpers in the same file: `_edge_cleanup_identity`, `_parse_observed_at`, `_semantically_blank`, `_formula_cell`, `_parse_position`, `_parse_product_id`, `_parse_decimal_comma`, `_parse_cpc`, `_parse_cpo`, `_parse_reviews`, `_parse_buyer_price`, `_parse_delivery`, `_parse_price_index`, and `_parse_product_row`. Each helper owns exactly one source grammar and raises the frozen specific domain error.
- [ ] Open `.part` safely with exactly:

  ```python
  source = path.open("rb")
  workbook = load_workbook(filename=source, read_only=True, data_only=False)
  ```

  Keep both alive during parsing and close `workbook` then `source` in `finally`, including all errors. Preflight merged-cell XML if read-only mode cannot expose merges, while classifying bad ZIP/package as unsupported.
- [ ] Validate one sheet, rows 1–9, exact A:P headers, no merged cells, and no semantically nonblank Q onward. Classify clear foreign shape before exact expected-shape incompatibilities. Count every nonblank A:P row from 10 onward as a candidate and require it equals declared count.
- [ ] Parse rows directly to `Decimal` from textual forms without float or generic locale conversion. Normalize/have payload hash through Task 1 helpers, deduplicate by Product ID, accumulate recoverable errors in source order, and return zero valid rows rather than raising solely for zero usability.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] Run adjacent parser/domain regressions:

  ```bash
  python -m pytest tests/test_ozon_products_parser.py tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] Run `git diff --check`, inspect only parser and its test, then commit:

  ```bash
  git add backend/ingestion/ozon_search_visibility_xlsx.py tests/test_ozon_search_visibility_parser.py
  git commit -m "feat: parse Ozon search visibility XLSX"
  ```

## Task 6: Add PR4 lineage and unified import history

**Files**

- Modify: `backend/domain/lineage.py`
- Modify: `backend/persistence/repositories/lineage.py`
- Modify: `tests/test_lineage_repository.py`

**Consumed interfaces**

- Existing PR3 `ImportBatch`/`SourceArtifact` repository methods and Task 1 `OzonSearchVisibilityImportSummary`.
- Migration 003 nullable context columns.

**Produced interfaces**

- Exact frozen `ImportHistoryItem` dataclass from Implementation Spec section 7.
- `finish_ozon_search_visibility_import(batch_id, *, status, observed_at, query_text, cluster_name, declared_rows, rows_seen, rows_accepted, rows_skipped, duplicate_observations, new_observations, corrected_revisions, warnings_count, row_errors_total) -> OzonSearchVisibilityImportSummary` with no public `finished_at`.
- `list_ozon_search_visibility_imports(*, limit: int, offset: int)`, `count_ozon_search_visibility_imports()`, `fail_running_ozon_search_visibility_imports(*, finished_at: datetime) -> int`.
- `list_referenced_archive_paths() -> set[str]`, `list_import_history(*, limit: int, offset: int) -> list[ImportHistoryItem]`, `count_import_history()`.

**Steps**

- [ ] Write RED tests asserting the exact `ImportHistoryItem` fields, PR3 summary/result fields remain unchanged, and PR4 summary maps observed/query/Cluster/declared/counters/artifact correctly with aware UTC datetimes.
- [ ] Use `inspect.signature` to prove PR4 finish has the exact parameters above and no public `finished_at`. Assert negative counters, nonpositive declared count, inconsistent terminal transitions, and finishing a batch twice are rejected.
- [ ] Seed mixed PR3/PR4/unknown kinds. Assert unified methods include exactly `ozon_products_xlsx` and `ozon_search_visibility_xlsx`, exclude unknown/future kinds, order by `started_at DESC, id DESC`, paginate deterministically, and count the same filtered set. Assert report type mapping is exactly `OZON_PRODUCTS`/`OZON_SEARCH_VISIBILITY` and unused context fields are `None`.
- [ ] Assert `list_referenced_archive_paths()` selects every non-null `stored_relpath LIKE 'imports/%'`, independent of import kind; returns PR3 and PR4 references; excludes null and non-generated-area paths.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_lineage_repository.py -q
  ```

  Expected initial failure: missing `ImportHistoryItem` and new repository methods/signature.
- [ ] Add the typed DTO and explicit row mappers. Factor only genuinely shared counter/status validation and artifact mapping; preserve PR3 public methods and result fields.
- [ ] Implement terminal PR4 update guarded by `WHERE id=? AND import_kind='ozon_search_visibility_xlsx' AND status='RUNNING'`, set repository-generated finish time, then select/map the durable summary. Implement recovery update limited to RUNNING PR4 rows and using the supplied aware `finished_at`.
- [ ] Implement global reference SQL exactly with `stored_relpath IS NOT NULL AND stored_relpath LIKE 'imports/%'`. Implement unified history with an explicit two-kind `IN (?, ?)` filter, `ORDER BY started_at DESC, id DESC`, and SQL limit/offset; do not build a registry or merge lists in UI.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_lineage_repository.py -q
  ```

- [ ] Run adjacent regressions:

  ```bash
  python -m pytest tests/test_ozon_products_import.py tests/test_ozon_products_api.py tests/test_migrations.py -q
  ```

- [ ] Run `git diff --check`, inspect the three task paths, then commit:

  ```bash
  git add backend/domain/lineage.py backend/persistence/repositories/lineage.py tests/test_lineage_repository.py
  git commit -m "feat: add search visibility lineage and unified history"
  ```

## Task 7: Share only the proven import runtime and preserve PR3

**Files**

- Create: `backend/application/import_runtime.py`
- Modify: `backend/application/ozon_products_import.py`
- Modify if regression requires an assertion update: `tests/test_ozon_products_import.py`
- Modify only if actual API regression requires it: `tests/test_ozon_products_api.py`

**Consumed interfaces**

- Existing PR3 constants, archive regex, basename algorithm, staging/recovery flow.
- Task 6 `LineageRepository.list_referenced_archive_paths()`.

**Produced interfaces**

- `MAX_UPLOAD_BYTES = 25 * 1024 * 1024`, `MAX_ROW_ERRORS = 50`, `IMPORT_LOCK = threading.Lock()`, `ARCHIVE_RE = re.compile(r"\d{8}T\d{12}Z-[0-9a-f]{64}\.xlsx")`, and `safe_original_basename(original_name)` in `backend.application.import_runtime`.
- PR3 module continues exposing imports of those five names for callers/tests; module-local `_IMPORT_LOCK` is removed unless a demonstrated compatibility test requires an alias.

**Steps**

- [ ] Write/adjust RED tests asserting safe basename behavior for POSIX/Windows traversal names and empty/dot names, exact 25 MiB boundary, `MAX_ROW_ERRORS == 50`, and the existing archive regex acceptance/rejection set.
- [ ] Add a lock test that acquires shared `IMPORT_LOCK`, calls PR3 import, and expects unchanged `ConcurrentImportConflict`; add recovery data with a referenced PR4 archive plus an unreferenced generated archive and prove PR3 recovery preserves the former and removes only the latter.
- [ ] Retain assertions for PR3 success, partial result, duplicate/corrected/new revisions, generated archive, and error mapping.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_ozon_products_import.py tests/test_ozon_products_api.py -q
  ```

  Expected initial failure: missing shared module/`IMPORT_LOCK`, PR3 still uses `_IMPORT_LOCK`, and recovery calls the removed PR3-only reference method.
- [ ] Move the five exact names into `import_runtime.py` without changing values or algorithms. This module contains no SQL, parser, source registry, workflow class, jobs, or generic engine.
- [ ] Import all five names into PR3 so its public module namespace remains compatible, replace acquire/release sites with `IMPORT_LOCK`, and make recovery call `list_referenced_archive_paths()`. Do not otherwise redesign its lifecycle.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_ozon_products_import.py tests/test_ozon_products_api.py -q
  ```

- [ ] Run the complete PR3 parser/import/API regression:

  ```bash
  python -m pytest tests/test_ozon_products_parser.py tests/test_ozon_products_import.py tests/test_ozon_products_api.py tests/test_product_snapshot_repository.py -q
  ```

- [ ] Run `git diff --check`, verify `tests/test_ozon_products_api.py` is unchanged unless a real shared-lock/history assertion required it, then commit:

  ```bash
  git add backend/application/import_runtime.py backend/application/ozon_products_import.py tests/test_ozon_products_import.py tests/test_ozon_products_api.py
  git commit -m "refactor: share import runtime across Ozon XLSX imports"
  ```

## Task 8: Implement the atomic PR4 import lifecycle and recovery

**Files**

- Create: `backend/application/ozon_search_visibility_import.py`
- Create/expand: `tests/test_ozon_search_visibility_import.py`

**Consumed interfaces**

- Task 3 `SearchDimensionRepository`; Task 4 `SearchVisibilitySnapshotRepository`; Task 5 parser; Task 6 lineage/history/reference methods; Task 7 shared runtime names; existing `ProductRepository.resolve_or_create_ozon_product()` and `transaction()`.

**Produced interfaces**

```python
def import_ozon_search_visibility_xlsx(*, upload: BinaryIO, original_name: str,
    db_path: Path | None = None, data_dir: Path = DATA_DIR
) -> OzonSearchVisibilityImportResult: ...

def recover_interrupted_ozon_search_visibility_imports(*,
    db_path: Path | None = None, data_dir: Path = DATA_DIR
) -> None: ...
```

**Steps**

- [ ] Write RED tests for exact and +1-byte upload bounds, safe basename, computed SHA/size, fsync/staging, successful archive/result, partial success, zero-usable durable FAILED context, parser-fatal FAILED result, duplicate/correction, and independent Cluster/query/time revisions.
- [ ] Assert unknown Product becomes non-owned; existing owned Product remains owned; in-file identical duplicate is only warning/SUCCESS; conflict is fatal; row detail is first 50 in source order while durable total/truncated remain correct.
- [ ] Test shared PR3/PR4 lock in both directions. Test generated-name collision preserves pre-existing target. Inject failure after exclusive final reservation and assert rollback, deletion only of this attempt's final file, null artifact path, compensated FAILED batch, and no SearchQuery/Cluster/Product/snapshot mutation.
- [ ] Seed PR3 and PR4 RUNNING batches and archives. Assert PR4 recovery fails only PR4 RUNNING batches, deletes stale `.upload-*.part`, preserves referenced archives of both kinds, deletes only unreferenced filenames matching `ARCHIVE_RE`, and preserves manual/unrelated files.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_import.py -q
  ```

  Expected initial failure: application service module is absent.
- [ ] Implement explicit ownership variables initialized independently: `staged_path: Path | None`, `final_path: Path | None`, `final_owned = False`, `batch_id: int | None`, `artifact_id: int | None`. Never infer ownership merely from path existence.
- [ ] Lifecycle A: acquire shared nonblocking lock; validate `.xlsx`; stream at most 25 MiB to `.upload-<uuid>.part`, hash/write/fsync. Extension/size failure removes owned stage and raises typed failure with `result=None` because no batch exists.
- [ ] Lifecycle B/C: transactionally create RUNNING batch and artifact (`source="ozon"`, both kinds `ozon_search_visibility_xlsx`, null stored path), retain IDs, then fully parse before any dimension/Product/snapshot mutation.
- [ ] Lifecycle D: on fatal parser domain error, delete stage, finish FAILED with null/known safe context as applicable and zero domain counters, map durable summary to result, and raise typed failure. No domain repository is invoked.
- [ ] Lifecycle E: for parsed `rows=()`, delete stage; finish FAILED with observed/query/Cluster/declared/seen/skipped/error values; keep artifact metadata with null path; raise `SearchVisibilityNoUsableRows` with FAILED result; assert no dimensions/Products/snapshots.
- [ ] Lifecycle F/G: reserve `<UTC YYYYMMDDTHHMMSSffffffZ>-<sha256>.xlsx` via exclusive `open("xb")`; set `final_owned=True` only after successful reservation; atomically replace reservation with stage; in one transaction set stored path, resolve exact dimensions, resolve/create Products, resolve snapshots, count kinds, finish SUCCESS unless row errors make PARTIAL_SUCCESS, then commit once.
- [ ] Lifecycle H: on persistence/collision failure, rollback transaction, unlink `final_path` only when `final_owned`, delete remaining owned stage, finish FAILED in a separate compensation transaction with artifact path still null, and raise `SearchVisibilityImportPersistenceError` with durable result. Always release shared lock.
- [ ] Implement recovery using Task 6 global references and exact archive regex; no deletion outside `data/imports`, no arbitrary filename deletion, no persistent worker.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_import.py -q
  ```

- [ ] Run adjacent regressions:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_parser.py tests/test_search_dimensions_repository.py tests/test_search_visibility_snapshot_repository.py tests/test_ozon_products_import.py tests/test_lineage_repository.py -q
  ```

- [ ] Run `git diff --check`, inspect the two task paths, then commit:

  ```bash
  git add backend/application/ozon_search_visibility_import.py tests/test_ozon_search_visibility_import.py
  git commit -m "feat: import Ozon search visibility observations"
  ```

## Task 9: Keep visibility-only identities outside the Product catalog

**Files**

- Modify: `backend/persistence/repositories/products.py`
- Modify: `tests/test_product_repository.py`
- Modify: `tests/test_ozon_products_api.py`

**Consumed interfaces**

- Existing Product identity/ownership resolution and PR3 list/count ordering.
- Existing `product_snapshots` table as the current catalog membership fact.

**Produced interfaces**

- Existing `count_ozon_products()` and `list_ozon_products()` now include only Ozon identities whose Product has at least one `product_snapshots` row, without changing signatures or return DTOs.

**Steps**

- [ ] Write RED repository/API tests: PR3-only Product visible; SearchVisibility-only Product hidden and excluded from total; hidden Product and external identity remain stored/resolvable; marking it owned still does not expose it without a ProductSnapshot.
- [ ] Add a later PR3 ProductSnapshot for the same external identity and assert it becomes visible, reuses the same Product ID, and creates no duplicate identity/Product. Preserve owned-first ordering, then latest PR3 title/snapshot ordering, and boolean `is_owned` mapping.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_product_repository.py tests/test_ozon_products_api.py -q
  ```

  Expected initial failure: visibility-only identities appear in list/total because current queries filter only external identity source/type.
- [ ] Add correlated `EXISTS (SELECT 1 FROM product_snapshots ps WHERE ps.product_id = p.id)` to both count and list catalog queries. Do not JOIN `product_snapshots` into the outer result, because multiple revisions/periods would multiply Products. Preserve existing latest-snapshot/title subquery and ordering verbatim otherwise.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_product_repository.py tests/test_ozon_products_api.py -q
  ```

- [ ] Run adjacent regressions:

  ```bash
  python -m pytest tests/test_ozon_products_import.py tests/test_product_snapshot_repository.py tests/test_ozon_search_visibility_import.py -q
  ```

- [ ] Run `git diff --check`, inspect the three task paths, then commit:

  ```bash
  git add backend/persistence/repositories/products.py tests/test_product_repository.py tests/test_ozon_products_api.py
  git commit -m "fix: keep visibility competitors out of product catalog"
  ```

## Task 10: Expose PR4 through thin FastAPI and the static Data UI

**Files**

- Modify: `backend/main.py`
- Modify: `frontend/index.html`
- Modify: `frontend/assets/css/app.css`
- Modify: `frontend/assets/js/app.js`
- Create/expand: `tests/test_ozon_search_visibility_api.py`
- Modify: `tests/test_frontend_contract.py`

**Consumed interfaces**

- Task 8 import/recovery functions and frozen failure/result types.
- Task 6 unified history methods and `ImportHistoryItem`.
- Task 9 Product catalog boundary; existing PR3 route/UI patterns and visual tokens.

**Produced interfaces**

- `POST /api/imports/ozon-search-visibility` with exact multipart field `file`.
- Existing `GET /api/imports` backed by unified history and existing `{items, total}` envelope.
- Existing `GET /api/products` reflects Task 9 boundary.
- Second accessible upload card and report-type-aware unified history in the existing Data screen.

**Steps**

- [ ] Write RED API tests for valid and partial POST HTTP 200; unreadable/wrong/schema/time/context/conflict/zero-usable 422; shared lock 409 with null result; oversized 413; wrong content type/extension 415; missing or wrong multipart field 422; persistence 500 with durable FAILED result. Assert `UploadFile.close()` in success and failure paths and no trace, filesystem path, or workbook cell content in responses.
- [ ] Freeze and assert every error triple exactly: `UNSUPPORTED_WORKBOOK`/422/`Не удалось прочитать XLSX-файл.`; `WRONG_REPORT_TYPE`/422/`Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи.`; `INCOMPATIBLE_REPORT_SCHEMA`/422/`Версия или структура отчёта не поддерживается.`; `INVALID_OBSERVED_AT`/422/`Не удалось прочитать дату или время наблюдения.`; `INVALID_SEARCH_CONTEXT`/422/`Не удалось прочитать поисковый запрос или кластер.`; `CONFLICTING_OBSERVATION_ROWS`/422/`В отчёте есть противоречивые строки одного товара.`; `NO_USABLE_ROWS`/422/`В отчёте нет пригодных строк товаров.`; `CONCURRENT_IMPORT_CONFLICT`/409/`Другой импорт уже выполняется. Дождитесь его завершения.`; `UPLOAD_TOO_LARGE`/413/`Размер файла превышает 25 МиБ.`; `UNSUPPORTED_UPLOAD_MEDIA_TYPE`/415/`Выберите XLSX-файл.`; `IMPORT_PERSISTENCE_ERROR`/500/`Не удалось сохранить импорт. Данные не изменены.`
- [ ] Test unified mixed newest-first history with exact PR3/PR4 nullable context and pagination, Product API non-pollution, first-50 row errors and truncation, decimal metrics absent from import response, and TestClient lifespan invoking both PR3/PR4 recovery.
- [ ] Write RED frontend contract tests for two upload controls/cards, unchanged `Товары` navigation/Products label, labels `Отчёт «Товары на Ozon»` and `Поисковая видимость Ozon`, filename/loading/success/partial/error hooks, bounded row details, and history refresh.
- [ ] Assert JavaScript branches explicitly on `item.report_type` with `OZON_PRODUCTS` and `OZON_SEARCH_VISIBILITY`, renders PR3 generated/window context and PR4 query/Cluster/UTC observed/declared/accepted/skipped context, and contains none of heatmap, query analysis, benchmark, competitor cards, Query Opportunity, or aggregate Cluster scores.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_api.py tests/test_frontend_contract.py -q
  ```

  Expected initial failure: route and second upload controls are absent; history is PR3-only.
- [ ] Add a thin route that verifies multipart content type, delegates once to Task 8, serializes DTOs/errors with the exact mapping, and closes `UploadFile` in `finally`. Do not parse, validate rows, execute SQL, or compute counters in the route. Add PR4 recovery beside PR3 recovery in lifespan.
- [ ] Change history endpoint to call `count_import_history()`/`list_import_history()` and serialize typed fields. Retain response envelope. Do not merge histories client-side. Product endpoint remains a thin caller of Task 9 repository behavior.
- [ ] Add the second card using existing visual tokens/components and no new navigation. JavaScript immediately displays selected filename, disables submit while active, uses honest stage/loading text without fake percentages, renders success/partial/error in a live/status region, limits displayed row details to response detail, and refreshes unified history after completion.
- [ ] Implement report-type render branches: Products → `Товары на Ozon` plus generated/window; Search Visibility → `Поисковая видимость Ozon` plus query, Cluster, UTC `observed_at`, declared/accepted/skipped and duplicate/new/corrected. Unknown values receive a neutral safe label without being inferred from nullable fields.
- [ ] Rerun targeted tests:

  ```bash
  python -m pytest tests/test_ozon_search_visibility_api.py tests/test_frontend_contract.py -q
  ```

- [ ] Run adjacent regressions:

  ```bash
  python -m pytest tests/test_ozon_products_api.py tests/test_ozon_products_import.py tests/test_product_repository.py tests/test_lineage_repository.py -q
  ```

- [ ] Run `git diff --check`, inspect only the six task paths, then commit:

  ```bash
  git add backend/main.py frontend/index.html frontend/assets/css/app.css frontend/assets/js/app.js tests/test_ozon_search_visibility_api.py tests/test_frontend_contract.py
  git commit -m "feat: expose search visibility import in API and data UI"
  ```

## Task 11: Harden portable acceptance and perform full PR4 verification

**Files**

- Modify only if required by integration: `tests/test_runtime_contract.py`
- Modify: `tests/windows_smoke.ps1`
- No other file; an adjacent allowed-modify test may change only when an observed integration failure proves it necessary.

**Consumed interfaces**

- Complete Tasks 1–10 and existing eight baseline Windows scenarios.
- Existing portable Python/openpyxl/bootstrap and ASCII-safe Cyrillic construction patterns.

**Produced interfaces**

- Runtime contract and Windows smoke coverage for migrations 1/2/3, PR3 and synthetic PR4 imports, archive/recovery safety, restart/repair/rebuild persistence, and spaces/Cyrillic paths.
- Audited PR4 implementation constrained to the frozen 31-file maximum.

**Steps**

- [ ] Write RED contract assertions for unchanged dependency pins/protected launcher contract and the new portable PR4 imports. Extend `tests/windows_smoke.ps1` with an ASCII-only synthetic PR4 parser/import probe, migration `[1,2,3]` assertion, PR4 archive existence and restart survival, runtime repair/rebuild survival, and bidirectional PR3/PR4 recovery reference survival. Preserve the eight existing baseline scenarios and their behavior.
- [ ] Ensure all Cyrillic test values are assembled with numeric `[char]` sequences or otherwise remain ASCII source bytes; run scenarios from the existing app path containing spaces and Cyrillic.
- [ ] Run RED:

  ```bash
  python -m pytest tests/test_runtime_contract.py -q
  ```

  Expected initial failure: runtime/portable contract does not yet mention migration 003 or the PR4 smoke probe. Windows PowerShell execution itself may remain pending when unavailable in Codex Cloud.
- [ ] Make only test-harness changes required for the frozen portable scenario. Do not modify `requirements.txt`, `requirements-dev.txt`, `start.bat`, `launcher.py`, `RUN_SERVER.cmd`, CI workflow, `backend/config.py`, or `backend/persistence/connection.py`. Keep `tests/windows_smoke.ps1` ASCII-only and retain PR3 dependency/import checks.
- [ ] Rerun targeted portable contract:

  ```bash
  python -m pytest tests/test_runtime_contract.py -q
  ```

- [ ] Run the focused PR4 suite from repository root:

  ```bash
  python -m pytest \
  tests/test_ozon_search_visibility_parser.py \
  tests/test_search_dimensions_repository.py \
  tests/test_search_visibility_snapshot_repository.py \
  tests/test_ozon_search_visibility_import.py \
  tests/test_ozon_search_visibility_api.py -q
  ```

  Expected: 0 failed.
- [ ] Run adjacent PR3/persistence/frontend/runtime regressions:

  ```bash
  python -m pytest \
  tests/test_ozon_products_parser.py \
  tests/test_ozon_products_import.py \
  tests/test_ozon_products_api.py \
  tests/test_product_snapshot_repository.py \
  tests/test_product_repository.py \
  tests/test_lineage_repository.py \
  tests/test_migrations.py \
  tests/test_database.py \
  tests/test_frontend_contract.py \
  tests/test_runtime_contract.py -q
  ```

  Expected: 0 failed.
- [ ] Run the complete Python suite:

  ```bash
  python -m pytest -q
  ```

  Expected: 0 failed.
- [ ] Compile Python sources:

  ```bash
  python -m compileall -q backend launcher.py tests
  ```

- [ ] If `node` exists, run:

  ```bash
  node --check frontend/assets/js/app.js
  ```

- [ ] Audit PowerShell ASCII bytes:

  ```bash
  python -c "from pathlib import Path; p=Path('tests/windows_smoke.ps1'); b=p.read_bytes(); assert all(x < 128 for x in b)"
  ```

- [ ] If Windows PowerShell is available, run `powershell -NoProfile -ExecutionPolicy Bypass -File tests/windows_smoke.ps1 -Mode Full`; otherwise record it as not executed in Codex Cloud. Authoritative Windows acceptance occurs in GitHub Actions after push.
- [ ] Audit production SQL and review every hit:

  ```bash
  rg -n \
  "execute\(|executemany\(|executescript\(" \
  backend
  ```

  Allowed hits are persistence repositories/migrations only. There must be no production SQL in application, ingestion, routes, or frontend.
- [ ] Audit dependency files:

  ```bash
  git diff main...HEAD -- \
  requirements.txt \
  requirements-dev.txt
  ```

  Expected: empty. If local `main` is unavailable, use the verified required-base SHA `3d82e22cc17f26ea7ebcaea211e9f4da64c28e32...HEAD` and record that substitution.
- [ ] Audit protected paths:

  ```bash
  git diff --name-only main...HEAD
  ```

  It must not contain `launcher.py`, `RUN_SERVER.cmd`, `start.bat`, `backend/config.py`, `backend/persistence/connection.py`, `requirements.txt`, `requirements-dev.txt`, `.github/workflows/ci.yml`, or `.gitignore`.
- [ ] Audit the full implementation scope. The only 12 created paths may be:

  ```text
  backend/domain/search_visibility.py
  backend/ingestion/ozon_search_visibility_xlsx.py
  backend/application/import_runtime.py
  backend/application/ozon_search_visibility_import.py
  backend/persistence/migrations/migration_003_ozon_search_visibility_import.py
  backend/persistence/repositories/search_dimensions.py
  backend/persistence/repositories/search_visibility_snapshots.py
  tests/test_ozon_search_visibility_parser.py
  tests/test_search_dimensions_repository.py
  tests/test_search_visibility_snapshot_repository.py
  tests/test_ozon_search_visibility_import.py
  tests/test_ozon_search_visibility_api.py
  ```

  The only 19 allowed modified paths are:

  ```text
  backend/domain/lineage.py
  backend/application/ozon_products_import.py
  backend/persistence/migrations/runner.py
  backend/persistence/repositories/lineage.py
  backend/persistence/repositories/products.py
  backend/main.py
  frontend/index.html
  frontend/assets/css/app.css
  frontend/assets/js/app.js
  tests/xlsx_factory.py
  tests/test_database.py
  tests/test_migrations.py
  tests/test_lineage_repository.py
  tests/test_product_repository.py
  tests/test_ozon_products_import.py
  tests/test_ozon_products_api.py
  tests/test_frontend_contract.py
  tests/test_runtime_contract.py
  tests/windows_smoke.ps1
  ```

  Maximum: 31 files. Leave an allowed-modify file unchanged when unnecessary; stop for explicit approval before any 32nd path.
- [ ] Perform the final architecture review against Product, Architecture, UI/UX, Visual Design System, Preflight, Source Contract, Implementation Spec, and current PR Plan: Cluster and exact query remain key material; observation time comes only from source; payload is exactly 19 fields; Reviews `— ` differs from CPO `—`; revisions/provenance are immutable; catalog is unpolluted; history/recovery are cross-kind safe; no seller-queries/analytics/dependency additions exist.
- [ ] Run `git diff --check`, inspect `git status --short` and the complete `git diff --stat`, then commit only actual Task 11 test changes:

  ```bash
  git add tests/test_runtime_contract.py tests/windows_smoke.ps1
  git commit -m "test: harden PR4 portable acceptance"
  ```

  If `tests/test_runtime_contract.py` required no edit, omit it from `git add`; do not create an empty commit.
