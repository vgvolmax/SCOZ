# SCOZ PR2 — Core Domain, SQLite Foundation & Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved PR2 project-local SQLite foundation, linear migrations, Product and lineage domain/repository contracts, immutable-observation conventions, and pre-server migration lifecycle without adding an import, API, analytics, or UI feature.

**Architecture:** Keep domain values independent from SQLite, confine production SQL to `backend/persistence/**`, inject a caller-owned `sqlite3.Connection` into focused repositories, and let the launcher synchronously initialize the late-resolved database immediately before starting a new backend process. Migration 001 creates only the four approved business tables; future observation behavior is proved by an isolated test-only fixture rather than generalized production infrastructure.

**Tech Stack:** Python 3.13, Python stdlib sqlite3, pytest, FastAPI startup integration, PowerShell Windows smoke.

If this Implementation Plan conflicts with `2026-08-16-scoz-pr2-core-domain-sqlite-foundation-lineage-implementation-spec.md`, the Implementation Spec wins and the plan must be corrected.

## Global Constraints

- Use Python stdlib `sqlite3` only: no SQLAlchemy, Alembic, ORM, async SQLite wrapper, or new runtime dependency.
- Keep `requirements.txt` and `requirements-dev.txt` unchanged.
- Use versioned Python migration modules; do not create separate `.sql` migrations, a migration DSL, checksums, repair, down migrations, dependency graphs, or discovery magic.
- The runner alone owns migration `BEGIN`/`COMMIT`/`ROLLBACK`. Migration modules must not call transaction methods or `sqlite3.Connection.executescript()`.
- Put all production SQL under `backend/persistence/**`. Permit isolated synthetic SQL only under `tests/**` for contract verification, never imported by production.
- The production DB is `data/scoz.db`. Resolve `SCOZ_DB_PATH` at operation time; do not define an environment-resolved global `DB_PATH`.
- Do not add a connection pool, global connection, repository base class, generic CRUD layer, UnitOfWork, generic entity, or schema-reflection layer.
- PR2 creates only the resolved DB parent. It does not eagerly create `data/imports/` or `data/backups/` and does not archive source files.
- Model Product as one common entity with mutable ownership. Do not create `OwnProduct`, `CompetitorProduct`, name/brand/photo matching, or silent identity merging.
- Do not create `ProductSnapshot` or any other future feature, snapshot, benchmark, query, analytics, ingestion, adapter, parser, job, scheduler, API, or UI table/framework.
- Add no API route, frontend behavior, navigation item, DB settings, or admin/debug UI. Keep the current frontend unchanged.
- Run migrations only before a new backend process starts: after exact-health/already-running and foreign-port guards, before `start_wrapper()`.
- Preserve the existing already-running process path: do not migrate or start a second backend, and retain browser behavior.
- Keep `runtime/` disposable and `data/` user-owned. Runtime dependency repair/rebuild must never delete or replace the DB.
- Treat GitHub Actions `windows-latest` as authoritative for Windows acceptance. The user desktop is not a development or testing environment.
- All implementation-time commands below run from the repository root in the Codex terminal unless a step explicitly identifies authoritative GitHub Actions Windows execution.
- All task commits are reviewable local units within the single PR2; they are not separate pull requests.

---

## Implementation Run Baseline

Before Task 1, from the repository root in the Codex terminal, capture the commit from which PR2 implementation starts and verify that the working tree is clean:

```bash
PR2_BASE_SHA="$(git rev-parse HEAD)"
export PR2_BASE_SHA
git status --short
```

Expected: `git status --short` has no output. Capturing `PR2_BASE_SHA` neither creates nor switches a branch; it only gives the final audit a stable PR-wide comparison base. If shell state does not persist between task sessions, keep the SHA in a local temporary execution note or otherwise retain the value captured by the implementer at the start of the run. Do not commit a base-SHA file to the repository.

The dependency order is contiguous: Task 1 establishes config and connections; Task 2 adds the database orchestrator, migrations, and schema; Task 3 establishes shared time helpers and Product persistence; Task 4 adds the remaining lineage domain and repository; Task 5 adds hashing and the revision fixture; Task 6 integrates the launcher; Task 7 verifies Windows persistence; Task 8 performs full verification.

---

## File Map

### Modify

- `backend/config.py` — add `DEFAULT_DB_PATH` and operation-time `resolve_db_path()`.
- `launcher.py` — initialize/migrate the DB at the approved new-process integration point.
- `README.md` — document only `data/scoz.db` and automatic migrations operationally.
- `tests/test_launcher.py` — add ordering, already-running, and failure-path migration tests.
- `tests/test_runtime_contract.py` — lock unchanged dependencies and DB-outside-runtime preservation contracts.
- `tests/windows_smoke.ps1` — extend the existing eight-scenario portable smoke with persistent DB assertions.

### Create

- `backend/domain/__init__.py` — intentional domain exports.
- `backend/domain/product.py` — Product domain dataclasses and errors.
- `backend/domain/lineage.py` — created in Task 3 with shared UTC/ISO helpers; extended in Task 4 with the lineage domain; extended in Task 5 with the normalized payload hash.
- `backend/persistence/__init__.py` — persistence package marker.
- `backend/persistence/connection.py` — connection factory and transaction context manager.
- `backend/persistence/database.py` — resolved-directory creation and migration orchestration.
- `backend/persistence/migrations/__init__.py` — migration package marker.
- `backend/persistence/migrations/runner.py` — fixed registry, history validation, and atomic forward runner.
- `backend/persistence/migrations/migration_001_core_foundation.py` — exact PR2 core DDL.
- `backend/persistence/repositories/__init__.py` — focused repository exports.
- `backend/persistence/repositories/products.py` — Product persistence and row mapping.
- `backend/persistence/repositories/lineage.py` — import lineage persistence, validation, and row mapping.
- `tests/test_database.py` — late path, connection, directory, and transaction contracts.
- `tests/test_migrations.py` — schema, history, idempotence, atomicity, and anti-scope contracts.
- `tests/test_product_repository.py` — Product and external identity repository contracts.
- `tests/test_lineage_repository.py` — ImportBatch and SourceArtifact repository contracts.
- `tests/test_observation_revision_convention.py` — hash tests and isolated immutable-revision fixture.

### Explicitly unchanged

- `backend/main.py`
- `start.bat`
- `RUN_SERVER.cmd`
- `requirements.txt`
- `requirements-dev.txt`
- `frontend/**`
- `.github/workflows/ci.yml`
- `.gitignore`

---

## Task 1: Database Path and Connection Foundation

**Files:**
- Modify: `backend/config.py`
- Create: `backend/persistence/__init__.py`
- Create: `backend/persistence/connection.py`
- Create: `tests/test_database.py`

**Interfaces:**

```python
# backend/config.py
DEFAULT_DB_PATH = DATA_DIR / "scoz.db"

def resolve_db_path() -> Path:
    ...

# backend/persistence/connection.py
def connect(
    db_path: Path | None = None,
) -> sqlite3.Connection:
    ...

@contextmanager
def transaction(
    db_path: Path | None = None,
) -> Iterator[sqlite3.Connection]:
    ...
```

`resolve_db_path()` reads and strips `SCOZ_DB_PATH` on every call; a non-empty override becomes `Path(override).expanduser().resolve()`, otherwise it returns `DEFAULT_DB_PATH`. `connect()` gives an explicit argument precedence over the environment, sets `sqlite3.Row`, enables and verifies foreign keys, and returns an open connection. `transaction()` commits on normal exit, rolls back on exceptional exit, and always closes.

- [ ] **Step 1: Write the failing connection-foundation tests.** In `tests/test_database.py`, add only tests for default resolution; two successive environment overrides without module reload (including an environment change between calls); explicit `db_path` overriding the environment; `sqlite3.Row` mapping; `PRAGMA foreign_keys == 1`; persisted commit; rolled-back mutation; and connection closure after both context-manager outcomes. Do not import or test `initialize_database()` in Task 1.
- [ ] **Step 2: Confirm RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_database.py -q`. Expected RED: collection/import failures for the missing persistence modules and config interfaces.
- [ ] **Step 3: Add the minimum path and connection code.** Add `os` to `backend/config.py`; define exactly `DEFAULT_DB_PATH` and `resolve_db_path()`. Create the package marker and implement `connect()`/`transaction()` without global connection state or SQL beyond connection setup. Use the resolved/explicit path independently in each operational entry point.
- [ ] **Step 4: Confirm GREEN independently.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_database.py -q`. Expected GREEN before any migration runner or `database.py` exists: every late-resolution, connection, commit, rollback, and close assertion passes.
- [ ] **Step 5: Run adjacent regressions.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_backend.py tests/test_runtime_contract.py -q`. Expected GREEN: health remains non-mutating and existing runtime contracts remain intact.
- [ ] **Step 6: Commit the reviewable foundation.** Working directory: repository root. Execution environment: Codex terminal. Run `git add backend/config.py backend/persistence/__init__.py backend/persistence/connection.py tests/test_database.py && git commit -m "feat: add SQLite connection foundation"`.

---

## Task 2: Migration Runner and Exact Migration 001

**Files:**
- Create: `backend/persistence/database.py`
- Create: `backend/persistence/migrations/__init__.py`
- Create: `backend/persistence/migrations/runner.py`
- Create: `backend/persistence/migrations/migration_001_core_foundation.py`
- Create: `tests/test_migrations.py`
- Modify: `tests/test_database.py`

**Interfaces and registry:**

```python
# backend/persistence/database.py
def initialize_database(
    db_path: Path | None = None,
) -> None:
    ...

# backend/persistence/migrations/runner.py
MIGRATIONS = [
    (
        1,
        "core_foundation",
        "backend.persistence.migrations.migration_001_core_foundation",
    ),
]

class DatabaseMigrationError(RuntimeError):
    pass

def run_migrations(conn: sqlite3.Connection) -> None:
    ...

# backend/persistence/migrations/migration_001_core_foundation.py
def up(conn: sqlite3.Connection) -> None:
    ...
```

`initialize_database()` resolves its concrete path once per call (with an explicit path overriding the environment), creates only `path.parent`, opens that concrete DB, runs the migration runner, and closes the connection. Task 2 appends its initialization integration tests to `tests/test_database.py`, after `database.py` and the runner exist: parent creation, concrete DB creation/migration, idempotent initialization, and absence of eager `imports/` or `backups/` creation. Task 1's earlier targeted GREEN therefore has no dependency on migration code.

### Exact migration 001 schema contract

`schema_migrations` is runner-owned, not created by migration 001:

```text
version INTEGER PRIMARY KEY
name TEXT NOT NULL
applied_at TEXT NOT NULL
```

Migration 001 creates exactly these four business tables and two indexes, using one separate `conn.execute(...)` call per DDL statement:

```text
products
  id INTEGER PRIMARY KEY AUTOINCREMENT
  is_owned INTEGER NOT NULL DEFAULT 0 CHECK (is_owned IN (0,1))
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL

product_external_identities
  id INTEGER PRIMARY KEY AUTOINCREMENT
  product_id INTEGER NOT NULL
  source TEXT NOT NULL
  identity_type TEXT NOT NULL
  identity_value TEXT NOT NULL
  source_account_scope TEXT NOT NULL DEFAULT ''
  created_at TEXT NOT NULL
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
  UNIQUE (source, identity_type, identity_value, source_account_scope)
  INDEX on product_id

import_batches
  id INTEGER PRIMARY KEY AUTOINCREMENT
  source TEXT NOT NULL
  import_kind TEXT NOT NULL
  status TEXT NOT NULL
    CHECK (status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED'))
  started_at TEXT NOT NULL
  finished_at TEXT NULL DEFAULT NULL

source_artifacts
  id INTEGER PRIMARY KEY AUTOINCREMENT
  import_batch_id INTEGER NOT NULL
  artifact_kind TEXT NOT NULL
  original_name TEXT NULL DEFAULT NULL
  content_sha256 TEXT NOT NULL
  byte_size INTEGER NOT NULL CHECK (byte_size >= 0)
  stored_relpath TEXT NULL DEFAULT NULL
  created_at TEXT NOT NULL
  FOREIGN KEY (import_batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
  INDEX on import_batch_id
```

There are no other business tables and no production migrations 002 or 003. Application-owned tables mean `sqlite_master` tables with `type = 'table' AND name NOT LIKE 'sqlite_%'`; therefore SQLite's `sqlite_sequence` is excluded.

- [ ] **Step 1: Write initialization, clean-schema, and idempotence tests.** Append `initialize_database()` integration tests to `tests/test_database.py` for parent creation, creation/migration of the concrete DB, idempotence, and absence of `imports/` and `backups/`. In `tests/test_migrations.py`, initialize a temp DB and assert one `(1, "core_foundation")` row, exactly the five application-owned tables, exact columns/defaults/checks/FKs/unique constraint/indexes, and the absence of every PR3+ table. Run initialization twice and assert the same metadata row and schema remain.
- [ ] **Step 2: Write migration-history tests.** Inject a test-only registry `[1, 2, 3]` and synthetic modules/functions. Assert prefix `[1, 2]` is accepted and applies pending `3`; `[2]`, `[1, 3]`, wrong name for `1`, and unknown `99` each raise `DatabaseMigrationError` before pending code runs. Keep all synthetic registry entries and SQL in this test file.
- [ ] **Step 3: Write atomic DDL rollback test.** Inject a synthetic pending migration that executes `CREATE TABLE synthetic_first (...)` and then raises. Assert `DatabaseMigrationError` preserves the original cause, `synthetic_first` is absent, and no metadata row exists for the failed version.
- [ ] **Step 4: Confirm RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_database.py tests/test_migrations.py -q`. Expected RED: missing runner, registry, exception, and migration module.
- [ ] **Step 5: Implement the database orchestrator.** Create `backend/persistence/database.py`; resolve the concrete path once, create only `path.parent`, open that path through `connect(path)`, call `run_migrations(conn)`, and close in `finally`. Do not create `imports/` or `backups/`.
- [ ] **Step 6: Implement history planning.** Create `schema_migrations`, import the fixed ordered registry, load rows ordered by version, reject unknown versions, reject name mismatches, compare applied `(version, name)` rows with the registry's exact leading prefix, and derive only the pending suffix. Do not repair or rewrite history.
- [ ] **Step 7: Implement atomic forward execution.** For each pending entry, import its module, explicitly `BEGIN`, call `up(conn)`, insert `(version, name, UTC ISO timestamp)`, and `COMMIT`. On any exception, `ROLLBACK` and raise `DatabaseMigrationError` from the cause. The runner is the only migration transaction owner.
- [ ] **Step 8: Implement migration 001.** Add the exact four-table/two-index schema above through individual `conn.execute(...)` statements. Do not call `executescript()`, `BEGIN`, `commit()`, or `rollback()` and do not create `schema_migrations` or backup/import directories.
- [ ] **Step 9: Confirm GREEN.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_migrations.py tests/test_database.py -q`. Expected GREEN: schema, history validation, idempotence, and DDL/metadata atomicity all pass.
- [ ] **Step 10: Run a production migration boundary scan.** Working directory: repository root. Execution environment: Codex terminal. Run `rg -n 'executescript\(|\.commit\(|\.rollback\(|\bBEGIN\b' backend/persistence/migrations/migration_*.py`. Expected GREEN: no matches.
- [ ] **Step 11: Commit the migration unit.** Working directory: repository root. Execution environment: Codex terminal. Run `git add backend/persistence/migrations backend/persistence/database.py tests/test_database.py tests/test_migrations.py && git commit -m "feat: add SQLite migration foundation"`.

---

## Task 3: Product Domain and Repository

**Files:**
- Create: `backend/domain/__init__.py`
- Create: `backend/domain/product.py`
- Create: `backend/domain/lineage.py`
- Create: `backend/persistence/repositories/__init__.py`
- Create: `backend/persistence/repositories/products.py`
- Create: `tests/test_product_repository.py`

**Domain and repository interfaces:**

```python
# backend/domain/lineage.py
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def datetime_to_db(value: datetime) -> str:
    ...

def datetime_from_db(value: str) -> datetime:
    ...

# backend/domain/product.py
@dataclass(frozen=True)
class Product:
    id: int
    is_owned: bool
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class ProductExternalIdentity:
    id: int
    product_id: int
    source: str
    identity_type: str
    identity_value: str
    source_account_scope: str
    created_at: datetime

class ProductNotFound(LookupError): ...
class ExternalIdentityConflict(ValueError): ...

class ProductRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def create_product(self, *, is_owned: bool) -> Product: ...
    def get_product(self, product_id: int) -> Product | None: ...
    def set_owned(self, product_id: int, is_owned: bool) -> Product: ...
    def add_external_identity(
        self,
        product_id: int,
        *,
        source: str,
        identity_type: str,
        identity_value: str,
        source_account_scope: str = "",
    ) -> ProductExternalIdentity: ...
    def find_by_external_identity(
        self,
        *,
        source: str,
        identity_type: str,
        identity_value: str,
        source_account_scope: str = "",
    ) -> Product | None: ...
```

Task 3 creates only the shared temporal foundation in `backend/domain/lineage.py`: `utc_now()` returns an aware UTC value without local Windows time; `datetime_to_db()` normalizes an aware value to UTC ISO-8601 `TEXT`; and `datetime_from_db()` parses stored text and returns an aware UTC value. ProductRepository uses these helpers rather than duplicating timestamp logic. Task 3 does not yet add `ImportStatus`, `ImportBatch`, `SourceArtifact`, lineage errors, or hashing.

Map SQLite ISO-8601 text to timezone-aware UTC `datetime` and integer ownership to `bool`; domain objects never retain `sqlite3.Row`. Repository methods use the injected connection and never open, commit, or roll back it. `set_owned()` updates `updated_at`; a missing Product raises `ProductNotFound`. `add_external_identity()` follows this exact order: (1) explicitly verify the Product exists; (2) raise `ProductNotFound` before mutation when it does not; (3) insert the identity; (4) map only the identity composite UNIQUE violation to `ExternalIdentityConflict`; and (5) let unrelated database errors propagate. This avoids parsing SQLite error text and prevents raw `sqlite3.IntegrityError` from becoming the missing-parent application contract.

- [ ] **Step 1: Write failing Product tests.** Create a migrated temp DB fixture with one caller-managed connection. Cover owned and non-owned creation, retrieval, boolean conversion, UTC-aware timestamps, ownership update and changed `updated_at`, missing lookup returning `None`, missing update raising `ProductNotFound`, identity insertion and lookup, an identity for a nonexistent `product_id` raising `ProductNotFound` with no identity row created, duplicate scoped identity across two products raising `ExternalIdentityConflict`, and identical value in distinct account scopes succeeding.
- [ ] **Step 2: Add boundary assertions.** Assert returned values are the declared dataclasses rather than `sqlite3.Row`; inspect public repository/domain signatures and schema to prove there is no name, brand, photo, alias, temporal identity, or matching API. Patch/spy connection transaction methods as needed to prove repository methods neither commit nor roll back.
- [ ] **Step 3: Confirm RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_product_repository.py -q`. Expected RED: missing domain types, errors, and repository.
- [ ] **Step 4: Implement temporal helpers and Product domain types.** Create `backend/domain/lineage.py` with exactly `utc_now()`, `datetime_to_db()`, and `datetime_from_db()` under the UTC/ISO contract above. Add exactly the two frozen Product dataclasses and two narrow Product errors, with intentional exports from `backend/domain/__init__.py`.
- [ ] **Step 5: Implement minimum Product persistence.** Add private row-to-domain conversion using the shared temporal helpers, explicit insert/select/update SQL, the explicit Product existence check before identity INSERT, and constraint-specific duplicate mapping. Use `cursor.lastrowid` plus a readback to return stored domain values. Do not add generic repository helpers.
- [ ] **Step 6: Confirm GREEN.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_product_repository.py -q`. Expected GREEN: Product, ownership, identity, error mapping, and connection-ownership contracts pass.
- [ ] **Step 7: Run adjacent database regressions.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_database.py tests/test_migrations.py tests/test_product_repository.py -q`. Expected GREEN: repository work respects the established connection/schema contracts.
- [ ] **Step 8: Commit the Product unit.** Working directory: repository root. Execution environment: Codex terminal. Run `git add backend/domain/__init__.py backend/domain/product.py backend/domain/lineage.py backend/persistence/repositories/__init__.py backend/persistence/repositories/products.py tests/test_product_repository.py && git commit -m "feat: add product persistence"`.

---

## Task 4: Lineage Domain and Repository

**Files:**
- Modify: `backend/domain/lineage.py`
- Create: `backend/persistence/repositories/lineage.py`
- Modify: `backend/domain/__init__.py`
- Modify: `backend/persistence/repositories/__init__.py`
- Create: `tests/test_lineage_repository.py`

**Domain and repository interfaces:**

```python
class ImportStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"

@dataclass(frozen=True)
class ImportBatch:
    id: int
    source: str
    import_kind: str
    status: ImportStatus
    started_at: datetime
    finished_at: datetime | None

@dataclass(frozen=True)
class SourceArtifact:
    id: int
    import_batch_id: int
    artifact_kind: str
    original_name: str | None
    content_sha256: str
    byte_size: int
    stored_relpath: str | None
    created_at: datetime

class ImportBatchNotFound(LookupError): ...
class InvalidImportStatusTransition(ValueError): ...
class InvalidSourceArtifactMetadata(ValueError): ...
class InvalidStoredRelativePath(ValueError): ...

class LineageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def create_import_batch(self, *, source: str, import_kind: str) -> ImportBatch: ...
    def get_import_batch(self, batch_id: int) -> ImportBatch | None: ...
    def finish_import_batch(
        self, batch_id: int, *, status: ImportStatus
    ) -> ImportBatch: ...
    def add_source_artifact(
        self,
        batch_id: int,
        *,
        artifact_kind: str,
        original_name: str | None,
        content_sha256: str,
        byte_size: int,
        stored_relpath: str | None = None,
    ) -> SourceArtifact: ...
    def get_source_artifact(self, artifact_id: int) -> SourceArtifact | None: ...
```

Use the Task 3 `utc_now()`, `datetime_to_db()`, and `datetime_from_db()` helpers so Product and lineage values consistently round-trip aware UTC timestamps as ISO-8601 text; do not duplicate temporal helpers. `add_source_artifact()` has this deterministic observable validation order: (1) reject negative `byte_size` or a hash other than exactly 64 lowercase hex characters with `InvalidSourceArtifactMetadata`; (2) reject a non-normalized/empty, absolute, Windows drive-qualified, UNC, or parent-traversing non-null path with `InvalidStoredRelativePath`; (3) establish that the batch exists or raise `ImportBatchNotFound`; (4) insert; (5) map and return the artifact. `stored_relpath=None` is valid. A non-null `stored_relpath` must be relative, and after path-component parsing it must contain no component exactly equal to `..`; two dots within an otherwise ordinary component name are valid.

- [ ] **Step 1: Write failing batch lifecycle tests.** Cover creation as `RUNNING` with `finished_at=None`; nullable get; missing finish raising `ImportBatchNotFound`; independent fresh transitions to `SUCCESS`, `PARTIAL_SUCCESS`, and `FAILED`; and rejection of `RUNNING -> RUNNING`, a second finish, and every terminal-to-any transition with `InvalidImportStatusTransition`.
- [ ] **Step 2: Write failing artifact and validation tests.** Cover full artifact round trip, nullable `original_name`/`stored_relpath`, correct parent, missing artifact returning `None`, missing batch, negative size, uppercase/short/non-hex hash, empty path, absolute POSIX and Windows paths, Windows drive-qualified paths, UNC paths, and path components exactly equal to `..`. Include `../file.xlsx`, `reports/../file.xlsx`, and `reports/a/../../file.xlsx` as invalid parent-traversal cases; include `reports/report..final.xlsx` and `reports/version..2/file.xlsx` as valid regression cases. Assert validation errors occur before row growth and verify the declared metadata/path/batch validation precedence with inputs invalid in multiple ways.
- [ ] **Step 3: Add defense-in-depth tests.** Use isolated direct SQL in the test to prove the DB rejects a negative size and nonexistent batch, while repository callers receive named errors rather than raw `sqlite3.IntegrityError` for contract-covered cases. Prove returned objects and timestamps contain no `sqlite3.Row`.
- [ ] **Step 4: Confirm RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_lineage_repository.py -q`. Expected RED: missing lineage types, errors, validation, and repository.
- [ ] **Step 5: Extend the lineage domain.** Add exactly the enum, two frozen dataclasses, four errors, and intentional package exports to the existing `backend/domain/lineage.py`; reuse its Task 3 UTC generation/ISO conversion helpers. Keep SQL and parsing orchestration out of the domain.
- [ ] **Step 6: Implement the repository lifecycle.** Add explicit insert/select/update SQL, typed row conversion, one-way terminal transition validation, validation in the fixed order above, and targeted integrity-error mapping. Never commit, roll back, or open another connection.
- [ ] **Step 7: Confirm GREEN.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_lineage_repository.py -q`. Expected GREEN: lifecycle, metadata/path validation, FK/check defense, row mapping, and error contracts pass.
- [ ] **Step 8: Run repository regressions together.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_product_repository.py tests/test_lineage_repository.py tests/test_migrations.py -q`. Expected GREEN: both focused repositories share the same caller-owned transaction/schema foundation.
- [ ] **Step 9: Commit the lineage unit.** Working directory: repository root. Execution environment: Codex terminal. Run `git add backend/domain backend/persistence/repositories tests/test_lineage_repository.py && git commit -m "feat: add lineage persistence"`.

---

## Task 5: Normalized Payload Hash and Immutable Revision Convention

**Files:**
- Modify: `backend/domain/lineage.py`
- Create: `tests/test_observation_revision_convention.py`

**Production interface:**

```python
type JSONPrimitive = None | bool | int | float | str
type JSONValue = (
    JSONPrimitive
    | list[JSONValue]
    | dict[str, JSONValue]
)

def normalized_payload_sha256(payload: JSONValue) -> str:
    ...
```

The implementation hashes UTF-8 bytes from exactly:

```python
json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
```

and returns `hashlib.sha256(serialized).hexdigest()`. The payload is already normalized and excludes DB IDs, revision, imported/provenance IDs, and transient processing metadata.

- [ ] **Step 1: Write failing hash tests.** Assert dict insertion order and non-ASCII text serialize deterministically, a changed normalized value changes the lowercase 64-character hash, and `NaN`, positive infinity, and negative infinity are rejected through `allow_nan=False`.
- [ ] **Step 2: Build the isolated test-only revision fixture.** In the test file only, create a synthetic observation table and tiny repository function with logical key `(product_id, period_start, period_end, real_dimension)`, revision, nullable superseded row ID, payload hash, provenance IDs, imported timestamp, and normalized value. This fixture must not be imported by production or migration 001.
- [ ] **Step 3: Specify and test the four immutable cases.** Prove: same logical key plus same hash reports duplicate and inserts nothing; same key plus different hash inserts revision 2 pointing to unchanged revision 1; new period inserts a distinct revision 1; same period plus a different real dimension inserts a distinct revision 1. Also assert no update statement mutates revision 1.
- [ ] **Step 4: Encode period/granularity conventions in test names/assertions.** Make the fixture demonstrate that the real dimension belongs to the logical key, missing dimensions are not invented, and periods are exact key data rather than silently merged or expanded. Do not create a production grain type or compatibility engine.
- [ ] **Step 5: Confirm RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_observation_revision_convention.py -q`. Expected RED: missing `normalized_payload_sha256`; fixture contract then guides the minimum implementation.
- [ ] **Step 6: Implement only the reusable hash.** Add the exact canonical serialization and SHA-256 helper to `backend/domain/lineage.py`. Do not move the synthetic repository/table into production.
- [ ] **Step 7: Confirm GREEN.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_observation_revision_convention.py -q`. Expected GREEN: deterministic hashing and all four immutable-revision conventions pass.
- [ ] **Step 8: Run adjacent domain/repository regressions.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_lineage_repository.py tests/test_observation_revision_convention.py -q`. Expected GREEN: hash additions do not change lineage persistence behavior.
- [ ] **Step 9: Commit the convention test unit.** Working directory: repository root. Execution environment: Codex terminal. Run `git add backend/domain/lineage.py tests/test_observation_revision_convention.py && git commit -m "test: codify observation revision convention"`.

---

## Task 6: Launcher Migration Integration

**Files:**
- Modify: `launcher.py`
- Modify: `tests/test_launcher.py`

**Required new-backend sequence:**

```text
preflight
→ exact-health/already-running guard
→ foreign-port guard
→ write_status("migration", ...)
→ initialize_database()
→ write_status("server start", ...)
→ start_wrapper()
→ health
→ browser
```

The exact production launcher import is `from backend.persistence.database import initialize_database`. Production `launcher.py` does not import `DatabaseMigrationError`: its existing broad `except Exception as exc:` top-level launch failure path remains the final error boundary, so a migration-specific error raised by `initialize_database()` naturally reaches that boundary with understandable context and its cause preserved. Tests import `DatabaseMigrationError` directly from its defining module with `from backend.persistence.migrations.runner import DatabaseMigrationError` to simulate a migration failure. Do not create a `backend.persistence` public facade, add re-exports or a new launcher exception hierarchy, or add SQL, PID writing, or FastAPI startup hooks to `launcher.py`.

- [ ] **Step 1: Add failing event-order tests.** Extend `tests/test_launcher.py` with mocks that record preflight, health guard, port guard, migration status, `initialize_database`, server status, wrapper, ready health, and browser. Assert the exact sequence above for a new backend.
- [ ] **Step 2: Strengthen already-running regression.** Mock `initialize_database` and assert it is not called when exact health identifies an existing SCOZ process; also retain no second wrapper, unchanged PID, successful return, ready status, and the existing browser action.
- [ ] **Step 3: Add migration failure test.** Make `initialize_database()` raise `DatabaseMigrationError("migration 1 failed")`. Assert `launch() == 1`, no wrapper, no health wait, no browser, final JSON stage `failed` with `ok=False`, and launcher log includes understandable migration failure context. Preserve foreign-port behavior and assert it also never migrates.
- [ ] **Step 4: Confirm RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_launcher.py -q`. Expected RED: migration event/import is absent and ordering/failure assertions fail.
- [ ] **Step 5: Implement the exact integration point.** After the existing successful health and foreign-port guards, write the `migration` status, log the migration stage, call `initialize_database()` synchronously, then continue with the unchanged `server start` status and wrapper lifecycle.
- [ ] **Step 6: Confirm GREEN.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_launcher.py -q`. Expected GREEN: new-process ordering, already-running bypass, foreign-port bypass, failure handling, browser order, health identity, and sole PID writer all pass.
- [ ] **Step 7: Run launcher/backend regressions.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_launcher.py tests/test_backend.py tests/test_database.py tests/test_migrations.py -q`. Expected GREEN: launcher integration does not move initialization into FastAPI or alter health/static behavior.
- [ ] **Step 8: Verify forbidden lifecycle files are untouched.** Working directory: repository root. Execution environment: Codex terminal. Run `git diff --exit-code -- backend/main.py start.bat RUN_SERVER.cmd`. Expected GREEN: no diff.
- [ ] **Step 9: Commit the lifecycle unit.** Working directory: repository root. Execution environment: Codex terminal. Run `git add launcher.py tests/test_launcher.py && git commit -m "feat: run migrations before server startup"`.

---

## Task 7: Portable Windows DB Persistence, Runtime Contract, and README

**Files:**
- Modify: `tests/windows_smoke.ps1`
- Modify: `tests/test_runtime_contract.py`
- Modify: `README.md`

Extend rather than replace the existing eight-scenario smoke. Use one exact DB sentinel strategy: after the clean first run, invoke the copied portable `runtime/python.exe` with stdlib `sqlite3` to insert a test-owned non-owned Product row whose `created_at` and `updated_at` are the fixed value `2000-01-01T00:00:00+00:00`; capture its `lastrowid`; after dependency repair and damaged-runtime rebuild, query that same row ID and assert both fixed timestamp values remain. This is isolated verification SQL in `tests/windows_smoke.ps1`; create no smoke-only production table.

`tests/windows_smoke.ps1` MUST remain ASCII-only. Do not add literal Cyrillic characters to the PowerShell source. Preserve the existing runtime construction of `$cyrillicTest` and `$cyrillicApp` path components through Unicode code points such as `[char]0x....`; the filesystem path at execution therefore still contains spaces and real Cyrillic characters. All PR2 DB smoke SQL snippets, assertion messages, helper names, and fixed timestamps must use ASCII source text.

- [ ] **Step 1: Add failing runtime contract assertions.** In `tests/test_runtime_contract.py`, assert requirements remain exactly the existing direct packages with no DB dependency; `DEFAULT_DB_PATH` is under `data/` rather than `runtime/`; `start.bat` deletes only `runtime/` during repair/rebuild and never deletes `data/` or `scoz.db`; and the documented DB path is user-owned.
- [ ] **Step 2: Confirm runtime-contract RED.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_runtime_contract.py -q`. Expected RED: operational DB documentation and/or newly asserted config contract is not yet represented.
- [ ] **Step 3: Extend clean-run and second-run smoke assertions.** After scenario 1, assert `data/scoz.db` exists and query `schema_migrations` for exactly one row `(1, 'core_foundation')`. Insert the fixed Product sentinel and save its ID. After scenario 2, assert the same DB path exists, migration 1 still appears exactly once, and the sentinel is unchanged.
- [ ] **Step 4: Extend repair/rebuild and path smoke assertions.** After dependency repair and after damaged-runtime rebuild, query the sentinel by saved ID and assert both timestamps and ownership remain unchanged. In the existing spaces+Cyrillic copied path, reassert the DB and migration metadata. Retain all PR1 runtime reuse, already-running, foreign-port, health, PID, data-file sentinel, and path assertions.
- [ ] **Step 5: Update README minimally.** Under local folders, state that `data/scoz.db` is user-owned persistent SQLite and that pending schema migrations apply automatically before a new local server starts. Do not describe tables, developer DB commands, a UI workflow, or recovery platform.
- [ ] **Step 6: Confirm Python GREEN.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest tests/test_runtime_contract.py tests/test_launcher.py tests/test_migrations.py -q`. Expected GREEN: dependency, lifecycle, persistence-location, and operational documentation contracts pass.
- [ ] **Step 7: Verify byte-level ASCII safety.** Working directory: repository root. Execution environment: Codex terminal. Run `python -c "from pathlib import Path; data=Path('tests/windows_smoke.ps1').read_bytes(); bad=[(i,b) for i,b in enumerate(data) if b >= 128]; print(bad[:20]); raise SystemExit(bool(bad))"`. Expected GREEN: `[]` and exit code 0. This mandatory regression check runs before the authoritative Windows smoke.
- [ ] **Step 8: Validate PowerShell syntax where available.** Working directory: repository root. Execution environment: Codex terminal. Run `if command -v pwsh >/dev/null 2>&1; then pwsh -NoLogo -NoProfile -Command '$null = [scriptblock]::Create((Get-Content -Raw tests/windows_smoke.ps1)); "PASS"'; else printf '%s\n' 'SKIP: PowerShell unavailable; authoritative Windows smoke remains pending'; fi`. Expected result: PASS when PowerShell exists; otherwise a non-blocking skip.
- [ ] **Step 9: Record authoritative Windows verification.** Execution environment: GitHub Actions `windows-latest`, after user push. The existing CI command `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full` must pass all original eight scenarios plus DB creation, one-time migration, DB sentinel preservation through repair/rebuild, and spaces+Cyrillic assertions. Until that workflow runs, record: `Pending authoritative GitHub Actions verification after user push.` Do not request desktop testing.
- [ ] **Step 10: Commit the portable persistence unit.** Working directory: repository root. Execution environment: Codex terminal. Run `git add tests/windows_smoke.ps1 tests/test_runtime_contract.py README.md && git commit -m "test: extend portable DB smoke"`.

---

## Task 8: Full Verification, Spec Review, and Scope Audit

**Files:** Review every path in the File Map; change production behavior only if a preceding contract test exposes a defect within the frozen PR2 scope.

- [ ] **Step 1: Compile all Python.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m compileall -q backend launcher.py tests`. Expected GREEN: exit code 0 and no output.
- [ ] **Step 2: Run the full Python suite.** Working directory: repository root. Execution environment: Codex terminal. Run `python -m pytest -q`. Expected GREEN: all PR1 and PR2 tests pass.
- [ ] **Step 3: Run the optional JavaScript syntax check without changing frontend.** Working directory: repository root. Execution environment: Codex terminal. Run `if command -v node >/dev/null 2>&1; then node --check frontend/assets/js/app.js; else printf '%s\n' 'SKIP: optional Node syntax check is unavailable'; fi`. Expected result: exit 0 when Node exists; otherwise non-blocking skip.
- [ ] **Step 4: Scan forbidden dependencies and future production entities.** Working directory: repository root. Execution environment: Codex terminal. Run `rg -ni 'sqlalchemy|alembic|aiosqlite|peewee|apsw|ProductSnapshot|SearchVisibilitySnapshot|QueryMetricSnapshot|ProductQuerySnapshot|SearchPositionSnapshot|AdvertisingSnapshot|BenchmarkSet' backend launcher.py requirements.txt requirements-dev.txt`. Expected GREEN: no matches.
- [ ] **Step 5: Scan migration transaction ownership.** Working directory: repository root. Execution environment: Codex terminal. Run `rg -n 'executescript\(|\.commit\(|\.rollback\(|\bBEGIN\b' backend/persistence/migrations/migration_*.py`. Expected GREEN: no matches; runner transaction calls are deliberately outside this scan.
- [ ] **Step 6: Audit SQL placement.** Working directory: repository root. Execution environment: Codex terminal. Run `rg -n -i '\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|CREATE INDEX|PRAGMA)\b' backend launcher.py`. Expected GREEN: production SQL matches occur only below `backend/persistence/**`; domain, launcher, routes, and UI have none.
- [ ] **Step 7: Prove protected files are unchanged across the PR.** Working directory: repository root. Execution environment: Codex terminal. Run:

  ```bash
  git diff --exit-code "$PR2_BASE_SHA"..HEAD -- \
    requirements.txt \
    requirements-dev.txt \
    frontend \
    backend/main.py \
    start.bat \
    RUN_SERVER.cmd \
    .github/workflows/ci.yml
  ```

  Expected GREEN: no diff. Always use the captured base; never infer it from a commit count.
- [ ] **Step 8: Inspect PR-wide patch hygiene and scope.** Working directory: repository root. Execution environment: Codex terminal. Run `git diff --check "$PR2_BASE_SHA"..HEAD`, `git diff --stat "$PR2_BASE_SHA"..HEAD`, `git diff "$PR2_BASE_SHA"..HEAD`, and `git diff --name-status "$PR2_BASE_SHA"..HEAD`. Then run `git diff --name-only "$PR2_BASE_SHA"..HEAD` and compare every result with this allowed implementation path set: `backend/config.py`, `backend/domain/**`, `backend/persistence/**`, `launcher.py`, `README.md`, `tests/test_database.py`, `tests/test_migrations.py`, `tests/test_product_repository.py`, `tests/test_lineage_repository.py`, `tests/test_observation_revision_convention.py`, `tests/test_launcher.py`, `tests/test_runtime_contract.py`, and `tests/windows_smoke.ps1`. The Implementation Plan is already on main when implementation starts and must not change again. Expected GREEN: clean whitespace, no path outside that set, no generated DB/runtime/cache files, and one PR2. Separately run `git status --short`; this checks only working-tree cleanliness and must have no output. Both the committed PR-wide diff audit and working-tree check are required.
- [ ] **Step 9: Perform full frozen-spec coverage review.** Re-read `docs/superpowers/specs/2026-08-16-scoz-pr2-core-domain-sqlite-foundation-lineage-implementation-spec.md` from start to finish and map every requirement/Definition-of-Done item to the matrix below and an automated or Windows assertion. Correct plan-conforming implementation gaps only; do not revise the spec.
- [ ] **Step 10: Perform placeholder and signature scans.** Working directory: repository root. Execution environment: Codex terminal. Run `python -c "from pathlib import Path; terms=['T'+'BD','T'+'ODO','implement '+'later','fill '+'in','appropriate '+'handling','similar '+'to above']; files=[*Path('backend').rglob('*.py'),*Path('tests').rglob('*'),Path('launcher.py'),Path('README.md')]; hits=[(str(p),t) for p in files if p.is_file() for t in terms if t.lower() in p.read_text(encoding='utf-8',errors='ignore').lower()]; print(hits); raise SystemExit(bool(hits))"` and expect `[]` with exit code 0. Then use `python -m pytest tests/test_database.py tests/test_product_repository.py tests/test_lineage_repository.py tests/test_migrations.py -q` to verify the exact interfaces, enums, exceptions, and migration signature exercised by typed calls. Also manually or with a focused extraction check confirm that every snippet declared as literal production Python compiles under Python 3.13, especially the PEP 695 `type JSONPrimitive` and recursive `type JSONValue` statements; scan the plan to ensure the invalid runtime-assignment form is absent. Do not execute the whole Markdown as Python.
- [ ] **Step 11: Perform dependency-order and anti-scope review.** Confirm each production interface is introduced before its first consumer; no application-service layer, generic persistence abstraction, snapshot framework, source/ingestion work, API, or UI was introduced; and migration 001 still owns exactly four business tables.
- [ ] **Step 12: Record Windows acceptance state.** If the implementation has not yet been pushed, report `Pending authoritative GitHub Actions verification after user push.` After push, GitHub Actions must run the full Python suite and `tests/windows_smoke.ps1 -Mode Full` on `windows-latest`; do not substitute desktop testing.
- [ ] **Step 13: Commit any verification-only corrections.** If and only if review required in-scope corrections, stage only those files and run `git commit -m "test: complete PR2 verification"`. If no correction was required, do not create an empty commit.

---

## Spec Coverage Matrix

| Spec requirement | Implementation task | Verification |
|---|---|---|
| DB path and operation-time environment resolution | Task 1 | Default, changed-env-between-calls, and explicit-override tests in `test_database.py` |
| SQLite connection factory | Task 1 | Explicit path, `sqlite3.Row`, foreign keys, commit/rollback, and close tests |
| Foreign-key enforcement | Tasks 1, 4 | `PRAGMA foreign_keys == 1`; SourceArtifact FK defense test |
| Caller-owned transactions | Tasks 1, 3, 4 | Commit/rollback tests; repository no-commit/no-rollback assertions |
| DB orchestration and `schema_migrations` | Task 2 | Initialization parent/concrete-DB tests plus Exact schema and version/name row assertions |
| Known names and contiguous migration history | Task 2 | Synthetic prefix `[1,2]`, gaps `[2]`/`[1,3]`, wrong name, and unknown `99` tests |
| Atomic migrations | Task 2 | Synthetic DDL failure removes table and metadata row while preserving cause |
| Exact migration 001 schema | Task 2 | Five application-owned tables, exact columns/FKs/checks/uniques/indexes |
| Migration idempotence | Tasks 2, 7 | Second initialization and second portable start retain one version-1 row |
| Product as one common entity | Task 3 | Owned/non-owned Product dataclass tests and anti-matching inspection |
| External identity and account scope | Task 3 | Add/lookup, missing parent maps to `ProductNotFound` with no row, scoped conflict, and different-scope allowance tests |
| ImportBatch provenance root | Task 4 | RUNNING creation, nullable get, and all terminal lifecycle tests |
| SourceArtifact provenance metadata | Task 4 | Full/nullable artifact round trips and correct batch parent |
| Metadata/path validation and stable errors | Task 4 | Negative size, invalid SHA, unsafe path, missing batch, precedence, and no-row-growth tests |
| Datetime semantics | Task 3 establishes helpers; Tasks 3–4 use them | Timezone-aware UTC domain values and ISO-8601 round trips through shared helpers |
| Deterministic normalized payload hash | Task 5 | Key-order equality, changed-value inequality, non-ASCII, and non-finite rejection |
| Immutable revision fixture | Task 5 | Duplicate, correction/revision 2, unchanged prior row, new period, and new dimension tests |
| Period/granularity convention | Task 5 | Exact period and real dimension in logical key; no invented/mixed dimension behavior |
| Production SQL boundary | Tasks 2–4, 8 | SQL placement scan; isolated test fixture remains under `tests/**` |
| Startup migration ordering | Task 6 | Mock event sequence before wrapper/health/browser |
| Existing-process path unchanged | Task 6 | No migration/no second wrapper and preserved PID test |
| Migration failure prevents startup | Task 6 | Named error leads to failed status/log, nonzero result, no wrapper/browser |
| DB creation without eager imports/backups | Tasks 2, 7 | `initialize_database` parent/concrete DB tests with no eager imports/backups, and clean portable first-run `data/scoz.db` assertion |
| DB preservation through runtime repair/rebuild | Task 7 | Fixed Product sentinel survives dependency repair and damaged-runtime rebuild |
| Spaces and Cyrillic portability | Task 7 | Extended existing copied-path smoke assertion |
| Authoritative Windows acceptance | Tasks 7, 8 | ASCII byte scan followed by GitHub Actions `windows-latest` full smoke after user push |
| No new dependencies | Tasks 7, 8 | Exact requirements/runtime dependency contract and final forbidden dependency scan |
| No API/UI/frontend changes | Tasks 6, 8 | Protected-file diff and full PR1 regressions |
| No PR3+ tables/entities or generic frameworks | Tasks 2, 5, 8 | Exact application-owned table set and forbidden production entity scan |
| Minimal operational README | Task 7 | Runtime contract verifies only DB location and automatic migration facts |
| PR-wide scope verification | Task 8 | All committed diff, protected-file, and allowed-path audits use `PR2_BASE_SHA..HEAD`; working-tree cleanliness is checked separately |

## Final Self-Review Checklist

- [ ] Re-read the full frozen PR2 Implementation Spec and confirm every normative statement has a task and verification row; the spec remains unchanged.
- [ ] Confirm the plan and implementation contain no unresolved placeholder language.
- [ ] Confirm type/signature consistency for `resolve_db_path`, `connect`, `transaction`, `initialize_database`, `run_migrations`, migration `up`, both repository classes, all dataclasses, `ImportStatus`, and every named exception.
- [ ] Confirm Task 1 is independently GREEN before `database.py` or the migration runner exists.
- [ ] Confirm dependency order is Task 1 config/connection → Task 2 database orchestrator/migrations/schema → Task 3 time helpers/Product → Task 4 remaining lineage domain/repository → Task 5 hash/revision fixture → Task 6 launcher → Task 7 Windows persistence → Task 8 verification.
- [ ] Confirm Task 3 establishes `utc_now()`, `datetime_to_db()`, and `datetime_from_db()` before Product persistence uses them, and Task 4 reuses rather than duplicates them.
- [ ] Confirm Task 5's PEP 695 JSON aliases compile under Python 3.13 and no invalid runtime-assignment alias remains.
- [ ] Confirm `add_external_identity()` explicitly maps a missing parent Product to `ProductNotFound` before INSERT, while UNIQUE conflicts retain their distinct named error.
- [ ] Confirm production SQL exists only under `backend/persistence/**`; test-only synthetic SQL does not leak into production.
- [ ] Confirm migration modules contain no transaction control or `executescript()` and the runner owns one transaction per pending migration.
- [ ] Confirm migration 001 has exactly four business tables and no PR3+ entity, snapshot, benchmark, query, import parser, analytics, API, or UI implementation.
- [ ] Confirm `requirements*`, frontend, `backend/main.py`, `start.bat`, `RUN_SERVER.cmd`, and CI remain unchanged.
- [ ] Confirm final scope and protected-file audits compare `PR2_BASE_SHA..HEAD`, not only the working tree, and contain no `HEAD~N` assumptions.
- [ ] Confirm Codex terminal results and pending authoritative GitHub Actions Windows verification are reported separately, with no desktop testing request.
