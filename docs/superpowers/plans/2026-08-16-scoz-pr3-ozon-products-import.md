# SCOZ PR3 — Ozon «Товары на Ozon» Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver SCOZ's first end-to-end Ozon «Товары на Ozon» import: XLSX → strict parser → Product identity → ProductSnapshot → immutable revisions → provenance → local API → import history → own-product selection → UI.

**Architecture:** Preserve the current adapter/ingestion → domain → caller-transaction-owned repositories → focused application service → thin FastAPI → committed static frontend flow. Parse the single frozen XLSX shape completely before mutation, serialize the whole import with one process-local non-blocking lock, retain accepted source bytes under user-owned `data/imports/`, and use PR2's `transaction()` for atomic Product/identity/snapshot/lineage writes. Keep parsing independent of SQLite/FastAPI, SQL inside persistence, and business decisions out of routes and JavaScript.

**Tech Stack:** Python 3.13 portable runtime; FastAPI 0.139.2 and Uvicorn 0.51.0; stdlib `sqlite3`; `openpyxl==3.1.5`; `python-multipart==0.0.32`; pytest 8.4.2/httpx 0.28.1 for tests; committed HTML/CSS/JavaScript; Windows batch and PowerShell smoke coverage.

## Global Constraints

- Python 3.13 project-local portable runtime; preserve ZIP → extract → `start.bat` → browser and loopback same-origin behavior.
- Extend the existing FastAPI stack; use stdlib `sqlite3`, `openpyxl==3.1.5`, and `python-multipart==0.0.32`; add no other direct PR3 runtime dependency and no pandas.
- No ORM/Alembic, npm/frontend build, React/Vue/Vite, DataFrame contract, or generic ingestion/source/job/snapshot/revision framework.
- Static HTML/CSS/JavaScript only; retain the existing shell, three navigation items, visual tokens, visible focus, and accessible non-color feedback.
- Production SQL lives only under `backend/persistence/**`. Repositories receive a connection and never open, commit, or roll it back. Existing PR2 `transaction()` owns every transaction boundary; no `BEGIN IMMEDIATE`.
- Use one process-local non-blocking import lock. Do not add a lock table, queue, worker, background job, or persistent job state.
- Implement exact Source Contract v1 only: no fuzzy XLSX detection, source header aliases, reordered headers, inferred variants, or generic locale-number parser.
- Never create, infer, store, hash, return, or display `period_start` / `period_end`. Percentage source values remain percentage points.
- Decimal conversion and canonicalization are exact: accepted Excel `int` → `Decimal(value)`, accepted finite `float` → `Decimal(str(value))`; plain base-10 text, no exponent/leading plus/trailing fractional zeros, and `-0` → `0`.
- Product identity is only `ozon_product_id` extracted from the strict Ozon URL. `Product.is_owned` is manual only; import never changes existing ownership and multiple owned products are allowed.
- `ProductSnapshot` is immutable. Corrections insert revision N+1 and reference revision N; never `UPDATE` or delete an old revision.
- Preserve ImportBatch/SourceArtifact provenance and archived accepted bytes. Never commit a real XLSX; generate synthetic workbooks in tests only.
- `data/` is user-owned. Create `data/imports/` lazily; runtime repair/rebuild must preserve both it and `data/scoz.db`.
- `tests/windows_smoke.ps1` remains byte-for-byte ASCII-only; encode Cyrillic through the existing `[char]` construction.
- No PR4+ entities, schema, routes, UI, or production behavior.
- Protected in PR3: `launcher.py`, `RUN_SERVER.cmd`, `backend/config.py`, `backend/persistence/connection.py`, `requirements-dev.txt`, `.github/workflows/ci.yml`, `.gitignore`. If implementation requires changing one, stop with `BLOCKING SPEC CONFLICT` rather than expanding scope.
- Work only on the selected branch. Do not create/switch/delete branches or worktrees; do not push, create/merge a PR, or modify frozen documents.

---

## Implementation Base Capture

- [ ] Before Task 1, capture the selected implementation baseline rather than hard-coding this planning commit:
  ```bash
  PR3_BASE_SHA="$(git rev-parse HEAD)"
  export PR3_BASE_SHA
  git status --short
  echo "$PR3_BASE_SHA"
  ```
  Require a clean tree, retain the value in the executing shell, and use `"$PR3_BASE_SHA"..HEAD` for every final PR-wide diff/scope assertion.

## Complete File Map (12 created, 13 modified)

**Create (12):**

- `backend/domain/product_snapshot.py` — frozen domain/result/parser DTOs, normalization helpers, and narrow PR3 errors.
- `backend/ingestion/__init__.py` — package marker only.
- `backend/ingestion/ozon_products_xlsx.py` — strict Source Contract v1 parser.
- `backend/application/__init__.py` — package marker only.
- `backend/application/ozon_products_import.py` — lock, staging/archive, import orchestration, compensation, and startup recovery.
- `backend/persistence/migrations/migration_002_ozon_products_import.py` — exact migration 002.
- `backend/persistence/repositories/product_snapshots.py` — ProductSnapshot revision/read persistence.
- `tests/xlsx_factory.py` — generated strict-contract workbook factory.
- `tests/test_ozon_products_parser.py` — parser/domain normalization cases.
- `tests/test_product_snapshot_repository.py` — logical-key/revision/provenance cases.
- `tests/test_ozon_products_import.py` — service/archive/recovery/atomicity cases.
- `tests/test_ozon_products_api.py` — four endpoint/error/readiness cases.

**Modify (13):**

- `requirements.txt`, `start.bat`.
- `backend/persistence/migrations/runner.py`.
- `backend/persistence/repositories/lineage.py`, `backend/persistence/repositories/products.py`.
- `backend/main.py`.
- `frontend/index.html`, `frontend/assets/css/app.css`, `frontend/assets/js/app.js`.
- `tests/test_frontend_contract.py`, `tests/test_migrations.py`, `tests/test_runtime_contract.py`, `tests/windows_smoke.ps1`.

No adjacent file is necessary: current PR2 exposes `transaction()`, Product/identity primitives, lineage roots, migration registry, static shell, and runtime smoke in the frozen map. In particular, reuse `ProductRepository.add_external_identity()` inside the new focused resolver rather than adding another identity-write API.

## Frozen Cross-Task Types and Signatures

Use these names unchanged in every task:

```python
# backend/domain/product_snapshot.py
@dataclass(frozen=True)
class ProductSnapshot: ...  # exact 45-field order from the frozen spec

@dataclass(frozen=True)
class ParsedOzonProductRow:
    source_row: int
    ozon_product_id: str
    snapshot_values: dict[str, object]
    payload_sha256: str

@dataclass(frozen=True)
class RowError:
    row: int
    code: str
    message: str

@dataclass(frozen=True)
class ParsedOzonProductsReport:
    report_generated_on: date
    report_window_days: int
    rows_seen: int
    rows: tuple[ParsedOzonProductRow, ...]
    row_errors: tuple[RowError, ...]
    duplicate_input_rows: int
    warnings_count: int

@dataclass(frozen=True)
class OzonProductsImportSummary: ...  # exact 18-field DTO from spec §3.4

class SnapshotWriteKind(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    CORRECTED = "CORRECTED"

@dataclass(frozen=True)
class SnapshotWriteResult:
    kind: SnapshotWriteKind
    snapshot: ProductSnapshot

@dataclass(frozen=True)
class ImportResult:
    import_batch_id: int
    report_type: Literal["OZON_PRODUCTS"]
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
    row_errors: tuple[RowError, ...]
    row_errors_truncated: bool
    source_artifact: SourceArtifact
    imported_at: datetime
    readiness: Literal["SELECT_OWN_PRODUCTS", "READY"]

def decimal_from_excel_number(value: object) -> Decimal: ...
def canonical_decimal_text(value: Decimal) -> str: ...
def product_snapshot_payload(snapshot_values: Mapping[str, object]) -> dict[str, JSONValue]: ...
def parse_ozon_products_xlsx(path: Path) -> ParsedOzonProductsReport: ...
def import_ozon_products_xlsx(*, upload: BinaryIO, original_name: str, db_path: Path | None = None, data_dir: Path = DATA_DIR) -> ImportResult: ...
def recover_interrupted_ozon_products_imports(*, db_path: Path | None = None, data_dir: Path = DATA_DIR) -> None: ...
```

Errors are concrete and narrow: `UnsupportedWorkbook`, `WrongReportType`, `IncompatibleReportSchema`, `InvalidReportPeriod`, `InvalidProductIdentity`, `InvalidMetricValue`, `CategoryMismatch`, `ConflictingObservationRows`, `ConcurrentImportConflict`, `UploadTooLarge`, `UnsupportedUploadMediaType`, and `ImportPersistenceError`. Parser fatal errors expose no local path/content; recoverable errors become `RowError` with frozen user messages.

### Task 1: Runtime Dependencies & Synthetic XLSX Test Foundation

**Files:**

- Create: `tests/xlsx_factory.py`
- Modify: `requirements.txt`, `start.bat`, `tests/test_runtime_contract.py`
- Test: `tests/test_runtime_contract.py`, import-only validation of `tests/xlsx_factory.py`

**Interfaces:**

- Consumes: current `requirements.txt` two pins; `start.bat` label `:validate_dependencies`; openpyxl Workbook API.
- Produces: `build_ozon_products_workbook(*, rows: Sequence[Mapping[str, object]] | None = None, generated_on: str = "08.16.26", window_label: str = "7 дней", category_level_3: str = "Синтетическая категория", marker_overrides: Mapping[str, object] | None = None, headers: Sequence[str] = OZON_PRODUCTS_HEADERS, extra_sheet: bool = False) -> bytes`; exact new pins and runtime validation.

- [ ] Add RED tests `test_runtime_inputs_include_exact_pr3_dependencies_and_no_pandas` and `test_bootstrap_validates_pr3_imports_and_distribution_versions`. Assert `requirements.txt` is exactly existing lines plus `openpyxl==3.1.5`, `python-multipart==0.0.32`; reject `pandas`; assert `:validate_dependencies` imports `openpyxl,multipart` and checks metadata names `openpyxl`/`python-multipart` at `3.1.5`/`0.0.32` alongside existing FastAPI/Uvicorn checks.
- [ ] Run targeted RED: `python -m pytest tests/test_runtime_contract.py -q`; expect the two new assertions to fail because pins/imports/version strings are absent, not because existing PR1/PR2 assertions regress.
- [ ] Append exactly the two pins. Extend the current single Python command beneath `:validate_dependencies` to `import fastapi,uvicorn,openpyxl,multipart` and one conjunction checking `m.version('fastapi')`, `m.version('uvicorn')`, `m.version('openpyxl')`, and `m.version('python-multipart')`; preserve repair/rebuild flow so import or metadata mismatch returns 1, invokes ordinary `pip install -r requirements.txt`, then rebuilds only `runtime/` if repair remains invalid.
- [ ] Create `OZON_PRODUCTS_HEADERS` as the exact ordered 32 strings and the factory above. It must create one sheet, A1/B1–A3/B3, blank A4:AF4, exact row 5, summary marker only at A6, rows at 7+, save to `BytesIO`, and return bytes—never write a fixture file. Default row must be fully synthetic and contract-valid, with numeric percentage `1.31`, explicit zero values, and exact window strings.
- [ ] Add `test_strict_xlsx_factory_emits_contract_rows_in_memory` which loads returned bytes with `load_workbook(BytesIO(data), read_only=True, data_only=False)` and asserts sheet count, rows 1–6, 32 headers, row 7 identity URL, and no repository `.xlsx` output.
- [ ] Run targeted GREEN: `python -m pytest tests/test_runtime_contract.py -q`; expect all runtime/factory contract tests to pass.
- [ ] Run adjacent regression: `python -m pytest tests/test_launcher.py tests/test_runtime_contract.py -q`; expect PR1 launcher/runtime tests to pass.
- [ ] Commit only Task 1: `git add requirements.txt start.bat tests/test_runtime_contract.py tests/xlsx_factory.py && git commit -m "chore: add PR3 XLSX runtime foundation"`.

### Task 2: ProductSnapshot Domain & Canonical Normalization

**Files:**

- Create: `backend/domain/product_snapshot.py`, `tests/test_ozon_products_parser.py`
- Modify: none
- Test: `tests/test_ozon_products_parser.py`

**Interfaces:**

- Consumes: `ImportStatus`, `SourceArtifact`, `JSONValue`, and existing `normalized_payload_sha256()` from `backend.domain.lineage`.
- Produces: all frozen cross-task domain DTOs/errors plus `decimal_from_excel_number()`, `canonical_decimal_text()`, and `product_snapshot_payload()` signatures above.

- [ ] Write RED tests `test_product_snapshot_has_exact_frozen_field_order`, `test_decimal_from_excel_number_accepts_int_and_finite_float_only`, `test_canonical_decimal_text_is_plain_and_stable`, and `test_product_snapshot_payload_has_exact_keys_and_json_types`. Instantiate all exact ProductSnapshot fields and compare `dataclasses.fields()` to the spec list.
- [ ] Test exact inputs: `1`, `1.0`, `-0.0`, `Decimal("12.3400")`, `None`, numeric zero, `date(2026,8,16)`, and percentage `Decimal("1.31")`. Expect canonical `"1"`, `"0"`, `"12.34"`, JSON null, JSON integer 0, ISO date, and `"1.31"`; reject bool, strings including `"1 234,56"`, NaN, infinities, and nonnumeric objects.
- [ ] Run RED: `python -m pytest tests/test_ozon_products_parser.py -q`; expect import failure for absent domain module.
- [ ] Implement the exact ProductSnapshot 42-field order and exact OzonProductsImportSummary 18-field order. Add the report/row/error/write/result dataclasses and narrow exceptions without SQL, filesystem, or FastAPI imports.
- [ ] Implement decimal conversion using `type(value) is int` and `type(value) is float` plus `math.isfinite`; canonicalize with fixed-point formatting and trimming while normalizing every signed zero. Build exactly the 35 payload keys listed in frozen spec §4, rejecting missing/extra keys; canonicalize Decimal/date and preserve int/text/None. Call existing `normalized_payload_sha256()` elsewhere—do not duplicate it.
- [ ] Run GREEN: `python -m pytest tests/test_ozon_products_parser.py -q`; expect domain/normalization tests to pass.
- [ ] Run adjacent regression: `python -m pytest tests/test_observation_revision_convention.py tests/test_lineage_repository.py -q`; expect PR2 hashing/lineage behavior unchanged.
- [ ] Commit: `git add backend/domain/product_snapshot.py tests/test_ozon_products_parser.py && git commit -m "feat: define Ozon product snapshot domain"`.

### Task 3: Migration 002 & PR3 Persistence Schema

**Files:**

- Create: `backend/persistence/migrations/migration_002_ozon_products_import.py`
- Modify: `backend/persistence/migrations/runner.py`, `tests/test_migrations.py`
- Test: `tests/test_migrations.py`

**Interfaces:**

- Consumes: current `up(conn: sqlite3.Connection) -> None` convention and runner-owned migration transaction.
- Produces: registry tuple `(2, "ozon_products_import", "backend.persistence.migrations.migration_002_ozon_products_import")`; `up(conn: sqlite3.Connection) -> None`.

- [ ] Add RED tests: `test_migrations_001_to_002_create_exact_pr3_schema`, `test_existing_001_database_upgrades_without_data_loss`, `test_migration_002_registry_and_rerun_are_idempotent`, and `test_migration_002_uses_runner_transaction_without_executescript_or_backup`.
- [ ] Assert history exactly `[(1,"core_foundation"),(2,"ozon_products_import")]`; application-owned tables exactly `schema_migrations`, `products`, `product_external_identities`, `import_batches`, `source_artifacts`, `product_snapshots`; no PR4+ table.
- [ ] Assert the ten appended nullable ImportBatch columns in frozen order and the complete ProductSnapshot DDL: every column/type/null/default/PK; four FKs; UNIQUE `(product_id,report_generated_on,report_window_days,revision)`; hash/window/revision/count/day-pair/day-bound CHECKs; exactly four named indexes and their ordered columns.
- [ ] Seed Product, external identity, RUNNING batch, and artifact under a 001-only registry, restore current registry, migrate, and prove every seeded value/FK survives; call initialization twice and prove no repeated column/table creation. Inspect source to assert no `executescript`, backup call, `commit`, or `rollback` in migration 002.
- [ ] Run RED: `python -m pytest tests/test_migrations.py -q`; expect missing registry/table/columns.
- [ ] Append only the registry entry. In migration `up`, issue ten separate `ALTER TABLE import_batches ADD COLUMN ...` calls, one exact `CREATE TABLE product_snapshots (...)`, and four separate `CREATE INDEX` calls. Do not use `IF NOT EXISTS`; idempotence belongs to the applied-history runner.
- [ ] Run GREEN: `python -m pytest tests/test_migrations.py -q`; expect clean 001→002, existing 001→002, rerun, schema, preservation, and runner ownership tests to pass.
- [ ] Run adjacent regression: `python -m pytest tests/test_database.py tests/test_migrations.py -q`; expect PR2 migration/connection tests to pass.
- [ ] Commit: `git add backend/persistence/migrations/migration_002_ozon_products_import.py backend/persistence/migrations/runner.py tests/test_migrations.py && git commit -m "feat: add Ozon products import migration"`.

### Task 4: ProductSnapshot Repository & Immutable Revisions

**Files:**

- Create: `backend/persistence/repositories/product_snapshots.py`, `tests/test_product_snapshot_repository.py`
- Modify: none
- Test: `tests/test_product_snapshot_repository.py`

**Interfaces:**

- Consumes: caller-owned `sqlite3.Connection`, ProductSnapshot, SnapshotWriteResult/Kind, canonical helpers, and migration 002.
- Produces: `ProductSnapshotRepository(conn: sqlite3.Connection)` with `find_current(*, product_id: int, report_generated_on: date, report_window_days: int) -> ProductSnapshot | None`; `resolve_revision(*, product_id: int, report_generated_on: date, report_window_days: int, payload_sha256: str, import_batch_id: int, source_artifact_id: int, imported_at: datetime, snapshot_values: Mapping[str, object]) -> SnapshotWriteResult`; `list_latest_current_for_products(*, limit: int, offset: int) -> list[ProductSnapshot]`; `count_products_with_snapshots() -> int`.

- [ ] Write RED tests `test_first_logical_key_inserts_revision_one`, `test_equal_hash_returns_duplicate_without_insert`, `test_changed_payload_inserts_revision_two_and_preserves_revision_one`, `test_new_date_and_new_window_each_start_revision_one`, `test_revision_keeps_exact_batch_and_artifact_provenance`, and `test_unique_constraint_defends_revision_allocation`.
- [ ] Assert correction's `supersedes_snapshot_id == rev1.id`, rev1 row bytes/fields remain unchanged, current lookup returns rev2, and duplicate result returns existing snapshot. Assert latest read chooses max date then current max revision; DB FK IDs equal supplied provenance.
- [ ] Add validation cases for lowercase 64-hex hash, aware imported_at, ISO dates, canonical decimal text, same-key immediately preceding supersession, positive window/revision, and DB uniqueness error on forced duplicate allocation.
- [ ] Run RED: `python -m pytest tests/test_product_snapshot_repository.py -q`; expect missing repository.
- [ ] Implement one focused mapper and parameterized SQL. `resolve_revision()` reads current, returns DUPLICATE on equal hash, otherwise inserts revision 1 or `current.revision + 1`; it never issues UPDATE/DELETE and never commits/rolls back/opens a connection. Map SQLite decimal TEXT back to Decimal and dates/datetimes to typed values.
- [ ] Run GREEN: `python -m pytest tests/test_product_snapshot_repository.py -q`; expect all revision/provenance/constraint cases to pass.
- [ ] Run adjacent regression: `python -m pytest tests/test_observation_revision_convention.py tests/test_product_repository.py -q`; expect PR2 conventions/products unchanged.
- [ ] Commit: `git add backend/persistence/repositories/product_snapshots.py tests/test_product_snapshot_repository.py && git commit -m "feat: persist immutable product snapshot revisions"`.

### Task 5: Lineage and Product Repository PR3 Extensions

**Files:**

- Create: none
- Modify: `backend/persistence/repositories/lineage.py`, `backend/persistence/repositories/products.py`, `tests/test_ozon_products_import.py`
- Test: `tests/test_ozon_products_import.py`, existing repository tests

**Interfaces:**

- Consumes: PR2 repository connection ownership; existing `create_product()`, `add_external_identity()`, `find_by_external_identity()`, and `set_owned()`.
- Produces: exact spec signatures `finish_ozon_products_import(...) -> OzonProductsImportSummary`, `list_ozon_products_imports(*, limit: int, offset: int) -> list[OzonProductsImportSummary]`, `set_source_artifact_stored_relpath(artifact_id: int, stored_relpath: str) -> SourceArtifact`; plus `count_ozon_products_imports() -> int`, `list_referenced_pr3_archive_paths() -> set[str]`, `fail_running_ozon_products_imports(*, finished_at: datetime) -> int`; `ProductRepository.resolve_or_create_ozon_product(ozon_product_id: str) -> Product`; `ProductRepository.list_ozon_products(*, limit: int, offset: int) -> list[dict[str, object]]`; `ProductRepository.count_ozon_products() -> int`; `ProductRepository.any_owned() -> bool`.

- [ ] Add RED repository tests for all exact lineage signatures: terminal fields preserved, FAILED null period and unavailable NULL counters map to None/0, newest `started_at,id` descending, limit/offset validation (`1..100`, offset ≥0), total via separate count query, one artifact per summary, and stored path reuses `_valid_stored_relpath`/raises `InvalidStoredRelativePath`.
- [ ] Add recovery query tests proving only RUNNING `ozon_products_xlsx` batches become FAILED at supplied aware time, known metadata/counters remain, other kinds/statuses remain untouched, and referenced archive path query returns only non-null paths for PR3 artifacts.
- [ ] Add product RED cases: existing exact tuple `("ozon","ozon_product_id",id,"")` resolves without insert/ownership change; absent ID creates false-owned Product then calls existing `add_external_identity()` in caller transaction; invalid non-digit ID rejected; list returns Ozon identity and latest-current snapshot, owned first then case-insensitive latest title then Product ID; count and `any_owned`; existing `set_owned` toggles true/false and permits multiple owned.
- [ ] Run RED: `python -m pytest tests/test_ozon_products_import.py tests/test_lineage_repository.py tests/test_product_repository.py -q`; expect absent focused methods.
- [ ] Implement typed mappings and SQL only in the two repositories. Keep GET imports pagination as `limit=50, offset=0` at API, max 100 in repository, with a separate `count_ozon_products_imports()` for `{total}`. Use existing `add_external_identity()`—do not add a second identity insertion method or generic resolver.
- [ ] Implement product listing query with a correlated/windowed persistence-only latest-current selection; return already selected freshness inputs, not computed UI prose. Do not mutate on reads.
- [ ] Run GREEN: `python -m pytest tests/test_ozon_products_import.py tests/test_lineage_repository.py tests/test_product_repository.py -q`.
- [ ] Run adjacent regression: `python -m pytest tests/test_database.py tests/test_lineage_repository.py tests/test_product_repository.py -q`.
- [ ] Commit: `git add backend/persistence/repositories/lineage.py backend/persistence/repositories/products.py tests/test_ozon_products_import.py && git commit -m "feat: extend PR3 product and lineage repositories"`.

### Task 6: Strict Ozon Products XLSX Parser

**Files:**

- Create: `backend/ingestion/__init__.py`, `backend/ingestion/ozon_products_xlsx.py`
- Modify: `tests/test_ozon_products_parser.py`, `tests/xlsx_factory.py`
- Test: `tests/test_ozon_products_parser.py`

**Interfaces:**

- Consumes: workbook factory; domain normalization/DTO/errors; existing `normalized_payload_sha256()`.
- Produces: `parse_ozon_products_xlsx(path: Path) -> ParsedOzonProductsReport` using `load_workbook(filename=path, read_only=True, data_only=False)`.

- [ ] Add named RED structural cases: `test_minimal_valid_workbook`, `test_full_valid_workbook_maps_all_32_columns`, `test_wrong_marker_is_wrong_report_type`, `test_wrong_header_is_incompatible_schema`, `test_reordered_header_is_incompatible_schema`, `test_multiple_sheets_are_incompatible`, `test_bad_generated_date_is_invalid_period`, `test_bad_window_label_is_invalid_period`, and `test_structural_formula_is_incompatible`. Assert exactly one sheet; A1/A2/A3 markers; blank A4:AF4; exact A5:AF5; exactly 32 columns; A6 summary marker; formula detection with `data_only=False`; filename/sheet name ignored.
- [ ] Add identity/row RED cases: `test_malformed_url_is_recoverable_identity_error`, `test_missing_identity_is_recoverable_identity_error`, `test_category_mismatch_is_recoverable_row_error`, `test_summary_row_never_creates_product`, `test_blank_trailing_row_is_ignored`, and `test_nonblank_trailing_candidate_counts_as_seen`. Strictly accept only `^https://www\.ozon\.ru/product/(\d+)/?$`, preserve captured digits, reconstruct no-trailing-slash URL.
- [ ] Add numeric/sentinel RED cases: exact `Нет данных` accepted only for turnover/buyout; exact `-` accepted only for out-of-stock; explicit numeric zero preserved; None/zero-length badge → None; non-empty badge exact; numeric-zero badge produces InvalidMetricValue; `1.31` remains Decimal `1.31`; formula metric produces row error; localized `"1 234,56"` rejected; bool/NaN/infinity rejected; counts integral/nonnegative; exact `N из D` keeps denominator and enforces `N<=D`; invalid card date/Excel datetime rejected.
- [ ] Add duplicate RED cases: `test_identical_duplicate_logical_rows_increment_duplicate_and_warning`, and `test_conflicting_duplicate_logical_rows_are_fatal_before_mutation`. First key/payload wins; identical later row not returned twice; changed payload raises `ConflictingObservationRows`, never last-row-wins.
- [ ] Run RED: `python -m pytest tests/test_ozon_products_parser.py -q`; expect parser import failure/new cases failing while Task 2 helpers remain green.
- [ ] Implement constants and small strict helpers for required text, formula detection, count, decimal, sentinel, day window, date, URL, and structural cells. Iterate row 7 onward; a fully blank row is ignored, any other row increments `rows_seen`; collect recoverable errors in source-row order without a parser-side 50 cap; reject no usable rows fatally.
- [ ] Construct the exact 35-key normalized payload, hash via existing PR2 function, and return typed rows/report. Parser imports no sqlite/repository/FastAPI and knows no artifact lifecycle.
- [ ] Run GREEN: `python -m pytest tests/test_ozon_products_parser.py -q`; expect every listed synthetic case to pass.
- [ ] Run adjacent regression: `python -m pytest tests/test_observation_revision_convention.py tests/test_migrations.py -q`.
- [ ] Commit: `git add backend/ingestion/__init__.py backend/ingestion/ozon_products_xlsx.py tests/xlsx_factory.py tests/test_ozon_products_parser.py && git commit -m "feat: parse strict Ozon products workbooks"`.

### Task 7: Import Service, SourceArtifact Archive & Interrupted Recovery

**Files:**

- Create: `backend/application/__init__.py`, `backend/application/ozon_products_import.py`
- Modify: `tests/test_ozon_products_import.py`
- Test: `tests/test_ozon_products_import.py`

**Interfaces:**

- Consumes: `transaction(db_path)`, focused repositories/parser, `DATA_DIR`, BinaryIO upload.
- Produces: `import_ozon_products_xlsx(...) -> ImportResult` and `recover_interrupted_ozon_products_imports(...) -> None` exact signatures above; module `_IMPORT_LOCK = threading.Lock()`; constants `MAX_UPLOAD_BYTES = 25 * 1024 * 1024`, `MAX_ROW_ERRORS = 50`.

- [ ] Add streaming RED tests: exclusive `.upload-<uuid4>.part` creation; exactly 25 MiB accepted; next byte raises `UploadTooLarge`; SHA-256/size calculated while copying chunks; `Path(PurePath(original_name).name).name` semantics store basename only for Windows/POSIX hostile paths; fsync occurs; generated final name matches `^\d{8}T\d{12}Z-[0-9a-f]{64}\.xlsx$`; `stored_relpath` is POSIX `imports/<name>`; generated collision fails without overwrite; `data/imports` is lazy.
- [ ] Add lifecycle RED tests: initial short transaction commits RUNNING batch/artifact with null path; fatal parser error deletes `.part`, writes FAILED, and creates no Product/ProductSnapshot; successful/partial rename retains archive and exact hash bytes; mutation failure rolls back Product/identity/snapshot/path/result writes, deletes final file, then separate compensation transaction leaves null artifact path and FAILED; failure after rename follows same compensation; persistence failures surface `ImportPersistenceError`.
- [ ] Add orchestration RED tests for SUCCESS, PARTIAL_SUCCESS, zero usable rows FAILED, database duplicate/new/corrected counters, identical in-file duplicate warning without PARTIAL_SUCCESS, 50 sorted row-error cap with total/truncated flag, existing ownership preservation, new products false-owned, and readiness SELECT_OWN_PRODUCTS/READY.
- [ ] Add lock RED test: hold `_IMPORT_LOCK`, call import, expect immediate `ConcurrentImportConflict`, no staging/batch mutation; prove lock releases after each success/failure.
- [ ] Add recovery RED tests: mark every prior RUNNING Ozon-products batch FAILED while preserving known fields; no snapshot changes; delete all `.upload-*.part`; delete only unreferenced files matching exact generated pattern; retain referenced generated archive, arbitrary `.xlsx`, near-match generated names, subdirectories, and unknown files. Assert invocation is one-shot function behavior, not a worker.
- [ ] Run RED: `python -m pytest tests/test_ozon_products_import.py -q`; expect missing application functions.
- [ ] Implement import in the frozen eight-phase lifecycle. Acquire lock before staging; stream/hash/limit/fsync; commit batch/artifact metadata; parse and finish all duplicate-conflict checks before Product mutation; rename exclusively; perform one mutation `transaction()`; compensate only after rollback/close. Never issue SQL, open connections directly, use CAS, or retain a failed path.
- [ ] Build ImportResult from durable summary/artifact and first 50 errors; statuses exactly SUCCESS/PARTIAL_SUCCESS/FAILED. Identical input duplicates affect duplicate/warnings only; database duplicates affect duplicate only; at least one skipped recoverable row makes partial; no accepted row is fatal.
- [ ] Implement recovery using repository methods in one `transaction()` plus narrowly bounded filesystem deletion. Invoke no snapshot repository mutation.
- [ ] Run GREEN: `python -m pytest tests/test_ozon_products_import.py -q`.
- [ ] Run adjacent regression: `python -m pytest tests/test_product_snapshot_repository.py tests/test_lineage_repository.py tests/test_product_repository.py -q`.
- [ ] Commit: `git add backend/application/__init__.py backend/application/ozon_products_import.py tests/test_ozon_products_import.py && git commit -m "feat: orchestrate atomic Ozon products imports"`.

### Task 8: FastAPI PR3 API

**Files:**

- Create: `tests/test_ozon_products_api.py`
- Modify: `backend/main.py`
- Test: `tests/test_ozon_products_api.py`, `tests/test_backend.py`

**Interfaces:**

- Consumes: application functions/errors; repository read methods; existing FastAPI app/static mount.
- Produces: `async def post_ozon_products_import(file: Annotated[UploadFile, File(...)]) -> dict[str, object]`; `def get_imports(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict[str, object]`; `def get_products(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict[str, object]`; Pydantic `OwnershipUpdate(is_owned: bool)` and `def patch_product_ownership(product_id: int, request: OwnershipUpdate) -> dict[str, object]`; FastAPI lifespan startup recovery before yielding.

- [ ] Add POST RED cases: valid synthetic upload returns HTTP 200 SUCCESS; recoverable row returns HTTP 200 PARTIAL_SUCCESS and never 207; missing/wrong multipart field 422; bad schema/wrong report/invalid period/conflicting rows 422 with exact Russian message; wrong request content type or non-`.xlsx` upload 415; >25 MiB 413; held lock 409; persistence failure 500. Assert structured response has no traceback, absolute path, upload content, or internal exception; fatal response includes failed ImportResult when batch exists.
- [ ] Add GET imports RED cases: `{items,total}`, newest first, exact counters/artifact, FAILED nullable period, unavailable counters as zero, limit/offset behavior, and before/after DB equality proving GET does not mutate.
- [ ] Add GET products RED cases: owned first; exact Ozon identity; only current revision of latest generated date/window; title/seller/brand; `report_generated_on`, `report_window_days`, `imported_at`; readiness; decimal values (where emitted) JSON strings; no invented boundaries.
- [ ] Add PATCH RED cases: exact JSON true then false, response `{id,is_owned,updated_at}`, unknown 404, invalid/missing/nonboolean 422, and two separate products simultaneously owned.
- [ ] Add startup RED case using app lifespan: recovery runs after migrated test DB exists and before request handling; legacy health/root/assets remain available.
- [ ] Run RED: `python -m pytest tests/test_ozon_products_api.py -q`; expect absent routes/startup behavior.
- [ ] Keep `backend/main.py` thin: adapt upload to the service, serialize typed values (Decimal strings, dates ISO, datetimes UTC ISO), map exact taxonomy/status codes/messages, and use repositories inside `transaction()` for read/PATCH operations. Do not parse XLSX, decide revisions/readiness, calculate freshness, or add SQL/routes package.
- [ ] Ensure multipart route accepts exactly required `file`; inspect Content-Type before service; close UploadFile; use HTTP 200 for partial. Register lifespan recovery before HTTP handling and retain current static mount ordering.
- [ ] Run GREEN: `python -m pytest tests/test_ozon_products_api.py -q`.
- [ ] Run adjacent regression: `python -m pytest tests/test_backend.py tests/test_database.py -q`.
- [ ] Commit: `git add backend/main.py tests/test_ozon_products_api.py && git commit -m "feat: expose Ozon products import API"`.

### Task 9: Static Frontend Import, Products & History UX

**Files:**

- Create: none
- Modify: `frontend/index.html`, `frontend/assets/css/app.css`, `frontend/assets/js/app.js`, `tests/test_frontend_contract.py`
- Test: `tests/test_frontend_contract.py`

**Interfaces:**

- Consumes: four same-origin JSON APIs and current `.app-shell`, `.sidebar`, `.nav-item`, `.content`, header/empty-state DOM; visual tokens already in `app.css`.
- Produces: semantic `#products-view`, `#data-view`, `#settings-view`; `#ozon-products-file`, `#selected-file-name`, `#import-submit`, `#import-status` (`aria-live`), `#import-history`, `#products-list`; JS `loadImports()`, `submitOzonProductsImport(file)`, `loadProducts()`, `setProductOwned(productId, isOwned)`, render/state/format functions.

- [ ] Expand static RED tests with exact selectors/labels and retained navigation count/order `Товары`, `Данные`, `Настройки`. Assert existing shell/tokens are extended rather than replaced, all controls have labels, statuses use text plus visual treatment, live region exists, and no remote asset/toolchain/framework.
- [ ] Add Data-state contract assertions for file input `.xlsx`, immediate basename, disabled duplicate submit, indeterminate `Проверяем файл` then `Читаем данные · Нормализуем · Сохраняем` (no `%`/fake progress), empty/loading/success/partial/error, bounded row details, and history fields: status/type/generated date/window/import time/original basename/accepted/skipped/duplicates/new/corrected/warnings/errors.
- [ ] Add Product-state assertions for empty/loading/error/list, Ozon ID, title/seller/brand, exact `Данные загружены. Выберите свои товары.`, report phrase, separate import freshness, accessible checkbox, and multiple selection semantics.
- [ ] Add business-boundary test scanning JS for prohibited parser/domain decisions: no XLSX/openpyxl logic, DRR/conversion arithmetic, revision/duplicate/correction decisions, ownership inference, `period_start`/`period_end`, or derived report boundaries. Permit only fetch, state, formatting, rendering, and actions.
- [ ] Run RED: `python -m pytest tests/test_frontend_contract.py -q`; expect absent sections/states/functions.
- [ ] Modify the current single content region into three semantic views while retaining sidebar/header hierarchy. Reuse canonical colors/radii/spacing; add cards, status banners, table/list, control/button, spinner, and responsive rules without new visual semantics.
- [ ] Replace the current copy-only click handler with same-origin fetch/state/render code. On file change show `file.name` basename immediately; upload FormData key `file`; switch indeterminate copy by request stage without percentages; reload history/products after success/partial; render server decisions verbatim; PATCH exact boolean.
- [ ] Format generated date/window and imported time only from API inputs. Never calculate analytics, revisions, identity, ownership, or period boundaries in JS.
- [ ] Run GREEN: `python -m pytest tests/test_frontend_contract.py -q`.
- [ ] Run adjacent regression: `python -m pytest tests/test_backend.py tests/test_frontend_contract.py -q`.
- [ ] Commit: `git add frontend/index.html frontend/assets/css/app.css frontend/assets/js/app.js tests/test_frontend_contract.py && git commit -m "feat: add Ozon import and product selection UI"`.

### Task 10: Portable Windows Integration & PR-wide Verification

**Files:**

- Create: none
- Modify: `tests/windows_smoke.ps1` (and only verify, do not further alter, `tests/test_runtime_contract.py`/`start.bat` unless Task 1's exact assertions reveal an omission)
- Test: `tests/windows_smoke.ps1`, full repository suite

**Interfaces:**

- Consumes: current Windows smoke's PR1 first/second launch, damaged-runtime repair, PR2 DB survival, spaces/Cyrillic `[char]` path construction; Task 1 `:validate_dependencies` exact four-import/four-metadata conjunction.
- Produces: additive ASCII-only portable dependency and synthetic parser/import smoke; final audits/report.

- [ ] Add RED static assertions before editing smoke: require `openpyxl`, metadata distribution `openpyxl`/`3.1.5`, import `multipart`, metadata distribution `python-multipart`/`0.0.32`, parser/import synthetic invocation, `data\imports` sentinel survival, and all existing PR1/PR2 scenario markers. Run `python -m pytest tests/test_runtime_contract.py -q`; expect new smoke-text assertions to fail.
- [ ] Extend—not replace—the PowerShell flow: after clean start query portable Python metadata/imports for exact versions; second start proves same runtime reuse; damage/remove an openpyxl or multipart installed file/metadata and prove ordinary pip repair restores both; generate the workbook in-process through `tests.xlsx_factory`, invoke parser/import against a temp DB/data root, and assert accepted snapshot/archive; retain `data/scoz.db` and a `data/imports` sentinel across repair/rebuild; repeat under existing spaces/Cyrillic path. Use ASCII source only and preserve `[char]` construction.
- [ ] Run targeted GREEN: `python -m pytest tests/test_runtime_contract.py -q`; expect runtime and smoke contracts green.
- [ ] Run adjacent regression: `python -m pytest tests/test_launcher.py tests/test_database.py tests/test_migrations.py -q`; expect PR1/PR2 portable/database scenarios green.
- [ ] Run syntax/full checks:
  ```bash
  python -m compileall -q backend launcher.py tests
  python -m pytest -q
  if command -v node >/dev/null 2>&1; then
    node --check frontend/assets/js/app.js
  else
    printf '%s\n' 'SKIP: optional Node syntax check unavailable'
  fi
  if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoLogo -NoProfile -Command \
      '$null = [scriptblock]::Create((Get-Content -Raw tests/windows_smoke.ps1)); "PASS"'
  else
    printf '%s\n' \
      'SKIP: PowerShell unavailable; authoritative Windows smoke pending GitHub Actions'
  fi
  ```
- [ ] Prove ASCII (expected `[]`, exit 0):
  ```bash
  python -c "from pathlib import Path; data=Path('tests/windows_smoke.ps1').read_bytes(); bad=[(i,b) for i,b in enumerate(data) if b >= 128]; print(bad[:20]); raise SystemExit(bool(bad))"
  ```
- [ ] Audit SQL and review every production match; expected only `backend/persistence/**`, with none in application/ingestion/domain/main:
  ```bash
  rg -n -i '\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|CREATE INDEX|ALTER TABLE|PRAGMA)\b' backend
  rg -n 'BEGIN IMMEDIATE|\.commit\(|\.rollback\(|sqlite3\.connect' backend/application backend/ingestion backend/domain backend/main.py
  ```
  The second command must return no transaction-control/connection ownership matches.
- [ ] Audit future/forbidden scope and dependencies:
  ```bash
  rg -n 'SearchQuery|Cluster|SearchVisibilitySnapshot|QueryMetricSnapshot|ProductQuerySnapshot|SearchPositionSnapshot|AdvertisingSnapshot|BenchmarkSet|RelevantQueryScope|MPStats|RampUp' backend frontend tests
  rg -ni 'sqlalchemy|alembic|pandas|aiosqlite|peewee|apsw' backend requirements.txt
  cat requirements.txt
  ```
  Review test-only anti-scope strings; require no PR4+ production implementation, no forbidden dependency, and exactly existing pins plus the two PR3 pins.
- [ ] Audit source/data leakage and clean generated state:
  ```bash
  find . -type f \( -iname '*.xlsx' -o -iname '*.xls' \) -not -path './.git/*'
  find data runtime -type f 2>/dev/null || true
  find . -type f -name '*.part' -not -path './.git/*'
  git status --short
  ```
  Expect no real `analytics_report_2026-08-16_16_27.xlsx`, no synthetic binary fixture, and no committed/generated `data/scoz.db`, `data/imports/**`, `runtime/**`, or `.part`; clean test artifacts before continuing.
- [ ] Commit Task 10 after targeted checks: `git add tests/windows_smoke.ps1 && git commit -m "test: extend portable PR3 Windows smoke"`.
- [ ] Perform PR-wide protected/frozen/scope assertions using captured implementation base:
  ```bash
  git diff --check "$PR3_BASE_SHA"..HEAD
  git diff --stat "$PR3_BASE_SHA"..HEAD
  git diff --name-status "$PR3_BASE_SHA"..HEAD
  git diff --name-only "$PR3_BASE_SHA"..HEAD
  git diff "$PR3_BASE_SHA"..HEAD
  git status --short

  git diff --exit-code "$PR3_BASE_SHA"..HEAD -- \
    launcher.py \
    RUN_SERVER.cmd \
    backend/config.py \
    backend/persistence/connection.py \
    requirements-dev.txt \
    .github/workflows/ci.yml \
    .gitignore

  git diff --exit-code "$PR3_BASE_SHA"..HEAD -- \
    docs/superpowers/specs/2026-08-16-ozon-products-xlsx-source-contract-v1.md \
    docs/superpowers/specs/2026-08-16-scoz-pr3-ozon-products-import-implementation-spec.md \
    docs/superpowers/plans/2026-08-16-scoz-pr3-ozon-products-import.md
  ```
  Require exact 12-created/13-modified allowed File Map, no protected/frozen diff, no other file, and clean tree.

## Coverage Matrix and Final Self-Review

| Frozen section / invariant | Task | Concrete evidence | File |
|---|---:|---|---|
| Rows 1–6, one sheet, 32 headers, report detection | 1, 6 | structural parser tests and generated factory | `tests/xlsx_factory.py`, `tests/test_ozon_products_parser.py` |
| Strict URL/Product identity; ownership manual | 5, 6, 8 | malformed/missing URL, resolver, PATCH/multiple-owned tests | parser/import/API tests |
| Decimal, zero, null, percentage points, dates/windows | 2, 6 | canonical/helper and all cell semantic tests | domain/parser tests |
| Exact ProductSnapshot/payload | 2 | field-order and 35-key payload tests | `backend/domain/product_snapshot.py` |
| Migration 002 exact schema/anti-scope | 3 | clean/upgrade/idempotence/DDL/index/FK/table tests | migration files/tests |
| Logical key, duplicate, immutable correction | 4, 6, 7 | rev1/duplicate/rev2/new date/window/in-file conflict tests | repository/parser/service tests |
| SourceArtifact and ImportBatch durable summary | 5, 7 | FK, counts, nullable failure, history mapping tests | lineage/service tests |
| Archive lifecycle/compensation | 7 | boundary/hash/name/rename/rollback/retention tests | service tests |
| Interrupted recovery | 5, 7, 8 | RUNNING and precise deletion boundary/startup tests | repositories/service/API tests |
| Non-blocking concurrency | 7, 8 | held-lock service/API 409 tests | service/API tests |
| Four APIs, history/readiness/freshness | 8 | exact status/error/nonmutation/serialization tests | API tests |
| UI states and business-logic boundary | 9 | selectors/copy/accessibility/static forbidden logic scan | frontend contract test |
| Runtime dependencies and portable Windows | 1, 10 | pins/import/metadata/repair/reuse/import smoke/ASCII | runtime and Windows smoke |
| SQL/transaction/protected/PR4+ boundaries | 3–10 | final `rg` and Git diff assertions | whole PR |

- [ ] Re-read in full Source Contract v1, frozen PR3 Implementation Spec, and this plan. Walk every matrix row and manually verify exact ProductSnapshot/OzonProductsImportSummary fields; parser DTO names; repository/result enum and methods; ImportResult; error names; service/recovery signatures; and API mappings are identical across Tasks 2–9.
- [ ] Verify source structure, identity, Decimal, snapshot, migration, key/payload, duplicate/revision, provenance, summary, archive, recovery, concurrency, API, ownership, history, freshness, frontend, dependencies, portable Windows, and anti-scope each has a Task + named test + exact file above.
- [ ] Scan placeholders and unresolved choices; the bracketed first letters prevent the audit commands from matching themselves, and both commands must return no matches:
  ```bash
  rg -n -i '[T]BD|[T]ODO|[i]mplement later|[s]imilar to task|[a]ppropriate error handling|[w]rite tests for|[f]ill in details' docs/superpowers/plans/2026-08-16-scoz-pr3-ozon-products-import.md
  rg -n -i '\b([m]aybe|[c]ould use|[o]ne option)\b' docs/superpowers/plans/2026-08-16-scoz-pr3-ozon-products-import.md
  ```
- [ ] Verify exact dependency agreement in Task 1, Task 10, requirements, batch validation, runtime tests, and Windows smoke: only `openpyxl==3.1.5` and `python-multipart==0.0.32`; verify application has no SQL/transaction ownership and no parser/frontend business logic.

## Completion and Handoff Report

- [ ] Future execution must report and then stop, with: **A. Status** (`CODEX IMPLEMENTATION COMPLETE` only if all Tasks/cloud checks/scope audits passed); **B. PR3_BASE_SHA / final HEAD**; **C. Tasks 1–10 statuses**; **D. exact changed files**; **E. every test command, exit code, pass count**; **F. parser/source-contract evidence**; **G. revision/provenance evidence**; **H. dependency/runtime evidence**; **I. SQL/transaction/scope audit results**; **J. ASCII output**; **K. local commits**; **L. Windows checks complete or pending authoritative GitHub Actions**; **M. unresolved concerns**.
- [ ] Distinguish statuses: `CODEX IMPLEMENTATION COMPLETE` means Tasks 1–10, all cloud-available tests, and scope audit completed. It does **not** mean `PR READY TO MERGE`. Only user push → user-created PR → authoritative GitHub Actions (including Windows) → independent external diff/spec review can support a merge decision. Codex must never declare this PR ready to merge.
- [ ] Do not ask the user to run development commands on a Windows desktop. If cloud lacks PowerShell/Windows, record the exact skipped check as pending GitHub Actions. Stop after the implementation report: no push, PR creation, merge, PR4 work, or next task.
