# SCOZ PR2 — Core Domain, SQLite Foundation & Lineage — Implementation Spec

**Статус:** Focused implementation specification for PR2 against current main.

## 1. Authority and scope

- Product Spec — frozen.
- Architecture — frozen.
- UI/UX / CJM / JTBD — frozen.
- Visual Design System — frozen.
- PR Development Plan — frozen на master-plan уровне.
- Данный документ уточняет только implementation contract PR2.

PR2 не инициирует общий redesign. При расхождении ранней целевой карты сущностей с актуальным PR Development Plan план управляет sequencing: feature-specific сущности появляются только в первом использующем их PR. Это устраняет, в частности, устаревшее упоминание раннего `BenchmarkSetRevision` в Preflight и не является блокирующим конфликтом.

## 2. Цель и граница результата

PR2 создаёт минимальный устойчивый data foundation SCOZ: project-local SQLite, schema migrations, `Product` и ownership, external identities, import lineage, source-artifact provenance, repository boundaries, общие conventions будущих immutable observations и period/granularity conventions. Последующие PR добавляют feature-specific migrations на этот фундамент.

PR2 не импортирует реальные отчёты Ozon, не создаёт аналитические verticals и не добавляет API/UI workflow. Канон хранения: Python stdlib `sqlite3` + лёгкий custom migration runner + versioned Python migration modules + explicit SQL внутри migration/repository modules. SQLAlchemy, Alembic, ORM, отдельные `.sql` migrations, migration DSL и новые runtime dependencies запрещены.

## 3. Current-main baseline и data flows

Фактический PR1 уже имеет `start.bat`, который валидирует/чинит disposable `runtime/` и вызывает `launcher.py`; `launcher.launch()` выполняет `preflight()`, exact-health/already-running и foreign-port guards, запускает `RUN_SERVER.cmd`, ждёт health и лишь затем открывает browser. `RUN_SERVER.cmd` остаётся единственным writer `server.pid`. PR2 расширяет этот lifecycle, не создавая второй launcher.

Startup flow:

```text
start.bat
→ portable runtime validation/repair
→ launcher.launch()
→ existing preflight
→ exact-health/already-running and foreign-port guards
→ database initialization / DB migrations
→ RUN_SERVER.cmd / server
→ exact health
→ browser
```

Точная integration point: в `launcher.launch()` вызвать `initialize_database()` после успешных existing health/port guards и непосредственно перед `write_status("server start", ...)` и `start_wrapper()`. До вызова записать stage `migration`; `initialize_database()` синхронно завершает все pending migrations. Это гарантирует migrations до запуска нового backend и не меняет уже работающую process/DB при already-running path.

Future-ingestion foundation flow:

```text
source operation
→ ImportBatch
→ optional SourceArtifact
→ normalized domain payload
→ future feature repository
→ immutable observation + provenance
```

В PR2 второй flow заканчивается контрактами `ImportBatch`, `SourceArtifact`, hash и revision; parser, ingestion service и production snapshot отсутствуют.

## 4. Project-local state and database path

Production DB path строго `data/scoz.db`, вычисляемый как `DATA_DIR / "scoz.db"`. `backend.config` добавляет `DB_PATH`: если environment variable `SCOZ_DB_PATH` задан, его значение преобразуется в `Path` и используется без привязки к `ROOT_DIR`; иначе используется production path. Override предназначен только для automated tests/process launch, не является UI setting и не сохраняется.

Минимальный user-owned layout:

```text
data/
├─ scoz.db
├─ imports/
├─ backups/
├─ startup_status.json
├─ launcher.log
├─ server_console.log
└─ server.pid
```

`initialize_database()` создаёт parent DB directory, `data/imports/` и `data/backups/`. `imports/` только резервируется для будущих source artifacts; PR2 не копирует XLSX. `backups/` резервируется для будущих рискованных migrations. Существующие PR1 startup files не переносятся и не переименовываются. Весь `data/` остаётся gitignored, не находится в `runtime/` и переживает repair/rebuild.

## 5. File-by-file implementation contract

| File | Action | Responsibility | Must not contain |
|---|---|---|---|
| `backend/config.py` | Modify | Add exact `SCOZ_DB_PATH`/`DB_PATH` contract | SQL, UI setting, DB connection |
| `backend/domain/__init__.py` | Add | Package marker and intentional public domain exports | SQL, persistence setup |
| `backend/domain/product.py` | Add | Frozen/simple dataclasses `Product`, `ProductExternalIdentity`; product exceptions | `sqlite3.Row`, SQL, API models, feature metrics |
| `backend/domain/lineage.py` | Add | `ImportStatus`, `ImportBatch`, `SourceArtifact`, lineage errors, UTC helper and `normalized_payload_sha256` | SQL, parser, jobs, content-addressable storage |
| `backend/persistence/__init__.py` | Add | Package marker | Business/domain logic |
| `backend/persistence/connection.py` | Add | Connection factory and transaction context manager | Pool, global connection, migrations registry |
| `backend/persistence/database.py` | Add | Create data directories and orchestrate runner for configured DB | Table SQL, repositories, launcher/UI logic |
| `backend/persistence/migrations/__init__.py` | Add | Package marker | Migration discovery magic |
| `backend/persistence/migrations/runner.py` | Add | Ordered registry, `schema_migrations`, atomic forward-only execution | Feature/application logic, backup platform, down migrations |
| `backend/persistence/migrations/migration_001_core_foundation.py` | Add | `up(conn)` and SQL for exactly four core business tables/indexes | `schema_migrations`, FastAPI/UI, future tables |
| `backend/persistence/repositories/__init__.py` | Add | Package marker and repository exports | SQL unrelated to repositories |
| `backend/persistence/repositories/products.py` | Add | `ProductRepository`, row mapping, product persistence error mapping | Name/photo matching, commits when externally transaction-managed |
| `backend/persistence/repositories/lineage.py` | Add | `LineageRepository`, row mapping, lineage persistence error mapping | Parser/import orchestration, job state |
| `launcher.py` | Modify | Run migrations at the exact integration point; reuse status/log/error handling | SQL, migration implementation, PID writing |
| `README.md` | Modify minimally | State that user-owned `data/scoz.db` exists and migrations run automatically | Schema documentation or new workflow |
| `tests/test_database.py` | Add | DB override, connection/foreign-key and directory contracts | Production feature schema |
| `tests/test_migrations.py` | Add | Clean/idempotent/failing migration and anti-scope schema tests | Dependence on user DB |
| `tests/test_product_repository.py` | Add | Product/ownership/identity repository contract | Name/photo matching implementation |
| `tests/test_lineage_repository.py` | Add | Batch/artifact/status/constraint contract | Real ingestion/parser |
| `tests/test_observation_revision_convention.py` | Add | Test-only snapshot repository/table and four revision cases; hash tests | Production snapshot abstraction or migration |
| `tests/test_launcher.py` | Modify | Ordering and migration failure tests; retain PR1 lifecycle tests | Real DB dependency in mocked ordering tests |
| `tests/test_runtime_contract.py` | Modify | Assert DB remains outside disposable runtime and requirements unchanged | Package/version changes |
| `tests/windows_smoke.ps1` | Modify | Extend authoritative smoke with DB/migration/rebuild preservation assertions | New generic smoke framework |

`backend/main.py`, `start.bat`, `RUN_SERVER.cmd`, frontend, requirements and CI workflow require no PR2 implementation change. Existing PR1 tests remain.

## 6. Domain contract

Domain objects are plain typed dataclasses/enums and never expose `sqlite3.Row`. Datetimes are timezone-aware UTC `datetime` values in domain objects and ISO-8601 `TEXT` in SQLite. System timestamps come from `datetime.now(timezone.utc)`; local Windows time has no domain meaning.

`Product(id: int, is_owned: bool, created_at: datetime, updated_at: datetime)` represents one logical SCOZ product. There are no `OwnProduct` or `CompetitorProduct` types. Ownership is mutable current product metadata, not a historical snapshot.

`ProductExternalIdentity(id, product_id, source, identity_type, identity_value, source_account_scope, created_at)` is explicit identity. Empty account scope means no scope is required. Products never merge by title, brand or photo; ambiguity never silently merges; one identity cannot belong to two products. `offer_id` uses account scope when seller/account determines uniqueness. Temporal identity history, confidence, aliases, `valid_from` and `valid_to` do not exist.

`ImportStatus` has exactly `RUNNING`, `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`. `ImportBatch(id, source, import_kind, status, started_at, finished_at)` is one import/sync operation and provenance root. Creation always produces `RUNNING` with `finished_at=None`. The only allowed transition is `RUNNING` to one terminal status. Re-finishing or finishing with `RUNNING` raises `InvalidImportStatusTransition`; no retry/state-machine platform is added.

`SourceArtifact(id, import_batch_id, artifact_kind, original_name, content_sha256, byte_size, stored_relpath, created_at)` describes a concrete input. `stored_relpath`, when present, must be a normalized relative path without `..`; absolute paths raise `InvalidStoredRelativePath`. Metadata may exist with `stored_relpath=None`, and PR2 archives no files.

Narrow errors are `ProductNotFound`, `ExternalIdentityConflict`, `ImportBatchNotFound`, `InvalidImportStatusTransition`, `InvalidStoredRelativePath`, plus `DatabaseMigrationError` at the runner boundary. Repositories catch constraint-specific `sqlite3.IntegrityError` and map it to these stable errors; unrelated DB errors propagate as database failures rather than masquerading as domain errors. Raw `IntegrityError` is not an application contract.

## 7. Exact schema

### `schema_migrations` (runner-owned)

| Column | SQLite type | Null/default | Keys/constraints | Meaning |
|---|---|---|---|---|
| `version` | `INTEGER` | NOT NULL, no default | PRIMARY KEY | Monotonic migration version |
| `name` | `TEXT` | NOT NULL, no default | — | Stable registry name |
| `applied_at` | `TEXT` | NOT NULL, no default | — | UTC ISO-8601 application timestamp |

### `products`

| Column | SQLite type | Null/default | Keys/constraints | Meaning |
|---|---|---|---|---|
| `id` | `INTEGER` | NOT NULL, generated | PRIMARY KEY AUTOINCREMENT | Internal product identity |
| `is_owned` | `INTEGER` | NOT NULL, DEFAULT `0` | CHECK (`is_owned IN (0, 1)`) | 1 company/user product; 0 external or unset |
| `created_at` | `TEXT` | NOT NULL | — | UTC creation timestamp |
| `updated_at` | `TEXT` | NOT NULL | — | UTC last ownership update timestamp |

### `product_external_identities`

| Column | SQLite type | Null/default | Keys/constraints | Meaning |
|---|---|---|---|---|
| `id` | `INTEGER` | NOT NULL, generated | PRIMARY KEY AUTOINCREMENT | Identity-row ID |
| `product_id` | `INTEGER` | NOT NULL | FK → `products.id` ON DELETE CASCADE; indexed | Owning Product |
| `source` | `TEXT` | NOT NULL | Composite UNIQUE | Source namespace |
| `identity_type` | `TEXT` | NOT NULL | Composite UNIQUE | Source ID kind |
| `identity_value` | `TEXT` | NOT NULL | Composite UNIQUE | Exact external value |
| `source_account_scope` | `TEXT` | NOT NULL, DEFAULT `''` | Composite UNIQUE | Seller/account scope or empty |
| `created_at` | `TEXT` | NOT NULL | — | UTC creation timestamp |

Composite `UNIQUE(source, identity_type, identity_value, source_account_scope)` prevents SQLite NULL semantics from admitting duplicates. A separate index exists on `product_id`.

### `import_batches`

| Column | SQLite type | Null/default | Keys/constraints | Meaning |
|---|---|---|---|---|
| `id` | `INTEGER` | NOT NULL, generated | PRIMARY KEY AUTOINCREMENT | Import operation ID/provenance root |
| `source` | `TEXT` | NOT NULL | — | Source namespace |
| `import_kind` | `TEXT` | NOT NULL | — | Operation/report kind |
| `status` | `TEXT` | NOT NULL | CHECK (`status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED')`) | Current operation outcome |
| `started_at` | `TEXT` | NOT NULL | — | UTC start timestamp |
| `finished_at` | `TEXT` | NULL, DEFAULT NULL | — | UTC terminal timestamp |

No additional index is created because PR2 interfaces query by primary key only.

### `source_artifacts`

| Column | SQLite type | Null/default | Keys/constraints | Meaning |
|---|---|---|---|---|
| `id` | `INTEGER` | NOT NULL, generated | PRIMARY KEY AUTOINCREMENT | Artifact metadata ID |
| `import_batch_id` | `INTEGER` | NOT NULL | FK → `import_batches.id` ON DELETE CASCADE; indexed | Provenance root |
| `artifact_kind` | `TEXT` | NOT NULL | — | Artifact type |
| `original_name` | `TEXT` | NULL, DEFAULT NULL | — | Source-visible filename |
| `content_sha256` | `TEXT` | NOT NULL | — | SHA-256 hex of artifact bytes |
| `byte_size` | `INTEGER` | NOT NULL | CHECK (`byte_size >= 0`) | Artifact byte count |
| `stored_relpath` | `TEXT` | NULL, DEFAULT NULL | — | Relative path inside user-owned data |
| `created_at` | `TEXT` | NOT NULL | — | UTC metadata timestamp |

`migration_001_core_foundation.up(conn)` creates only `products`, `product_external_identities`, `import_batches`, `source_artifacts`, their declared constraints, `product_id` index and `import_batch_id` index. `schema_migrations` is runner-owned. No other production table is permitted.

## 8. Connection, transaction and repository boundaries

`connect(db_path: Path = DB_PATH) -> sqlite3.Connection` creates one stdlib connection, sets `row_factory = sqlite3.Row`, executes `PRAGMA foreign_keys = ON`, verifies it reads back as `1`, and returns it. There is no pool or global connection. Lifecycle stays under `backend/persistence/**`.

`transaction(db_path: Path = DB_PATH)` is a persistence context manager: open connection, yield it, commit on success, rollback on exception, close always. Repository constructors require `sqlite3.Connection`. They never open connections and never commit/rollback. Consequently one simple application mutation uses `with transaction() as conn: Repository(conn).method(...)`; a future ingestion operation constructs both repositories with the same yielded connection and atomically stores related rows. This is the exact shared-transaction mechanism; no UnitOfWork abstraction is introduced.

SQL is permitted only in `backend/persistence/**`. Domain, application, routes, launcher and UI execute none. Production has no delete APIs in PR2. FK cascades protect explicit parent deletion but must never implement historical correction; no soft-delete framework is added.

Exact interfaces:

```python
class ProductRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def create_product(self, *, is_owned: bool) -> Product: ...
    def get_product(self, product_id: int) -> Product | None: ...
    def set_owned(self, product_id: int, is_owned: bool) -> Product: ...
    def add_external_identity(
        self, product_id: int, *, source: str, identity_type: str,
        identity_value: str, source_account_scope: str = ""
    ) -> ProductExternalIdentity: ...
    def find_by_external_identity(
        self, *, source: str, identity_type: str,
        identity_value: str, source_account_scope: str = ""
    ) -> Product | None: ...

class LineageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def create_import_batch(self, *, source: str, import_kind: str) -> ImportBatch: ...
    def get_import_batch(self, batch_id: int) -> ImportBatch | None: ...
    def finish_import_batch(
        self, batch_id: int, *, status: ImportStatus
    ) -> ImportBatch: ...
    def add_source_artifact(
        self, batch_id: int, *, artifact_kind: str,
        original_name: str | None, content_sha256: str, byte_size: int,
        stored_relpath: str | None = None
    ) -> SourceArtifact: ...
    def get_source_artifact(self, artifact_id: int) -> SourceArtifact | None: ...
```

`set_owned` and mutation against a missing batch raise the narrow not-found errors; nullable getters return `None`.

## 9. Migration runner, atomicity and backup

Runner registry is fixed and ordered:

```python
MIGRATIONS = [
    (1, "core_foundation", "backend.persistence.migrations.migration_001_core_foundation"),
]
```

Each module exports `up(conn: sqlite3.Connection) -> None`, knows neither FastAPI nor UI, and contains no application logic. Runner opens DB, creates `schema_migrations`, reads applied versions, validates that an applied version has the registry name, computes pending entries, and executes them in ascending version order. Unknown applied versions or name mismatch fail startup rather than guessing.

For every pending migration, runner explicitly begins one transaction; `up(conn)` and insertion of `(version, name, applied_at)` occur in that transaction. Success commits both. Any exception rolls back both, wraps with `DatabaseMigrationError` preserving the cause, and stops. The failed version is absent and partial changes are not accepted as applied. A second run is a no-op. Migrations are forward-only; PR2 has no `down`.

PR2 builds a new foundation, so migration 001 performs no backup and stage `database_backup` is not emitted. A future migration that can irreversibly affect existing user data must define and create a pre-migration copy under `data/backups/` in that PR's spec. PR2 adds neither a universal backup platform nor WB-specific version backup helper.

Migration failure propagates to existing `launcher.launch()` catch: backend is not started, browser is not opened, return code is non-zero, `startup_status.json` becomes `failed`, and `launcher.log` contains the `migration` stage and understandable error. Technical traceback may go to technical logging, while user status remains concise. No persistent operation/job table is created.

## 10. Provenance, payload hash and immutable revision convention

Every future source-derived observation stores directly in its feature table: non-null `import_batch_id`, nullable `source_artifact_id` when no artifact exists (including API sync), `imported_at`, and normalized payload hash. Import/sync batch remains the provenance root. There is no generic provenance table.

`normalized_payload_sha256(payload)` accepts an already normalized tree of JSON-safe primitives. Payload excludes DB IDs, revision, `imported_at`, ImportBatch/SourceArtifact IDs and transient processing metadata. It serializes exactly:

```python
json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
```

and returns lowercase SHA-256 hex. Non-finite numbers fail through `allow_nan=False`. This supports detection only; no content-addressable storage framework is created.

The first PR for every snapshot type defines its complete logical observation key. Then:

- same logical key + same hash → `DUPLICATE`; no row inserted;
- same logical key + different hash → corrected immutable revision;
- new period/date or any real key dimension → new observation.

Revision starts at 1. A correction inserts `previous.revision + 1`, sets `supersedes_snapshot_id` to the previous current row ID, and never mutates the previous row. Each future feature table contains the equivalent of `id`, all logical-key dimensions, `revision`, nullable `supersedes_snapshot_id`, `payload_sha256`, `import_batch_id`, nullable `source_artifact_id`, `imported_at`, available temporal metadata, and feature values. Analytics reads the current/latest revision while history remains. There is no generic snapshots or revisions table.

`tests/test_observation_revision_convention.py` creates its own test-only table and tiny repository, outside migration 001 and production packages. It proves: identical key/payload is duplicate without row growth; corrected payload creates revision 2 superseding unchanged revision 1; same product/new period creates revision 1 for a separate observation; same period/different real dimension creates a separate observation. It also proves dict-key-order-independent hash and changed-value hash inequality. The fixture is a contract test, not speculative production infrastructure.

## 11. Period and granularity conventions

PR2 creates no `ObservationGrain`, granularity registry, timezone engine or `AnalysisWindow`. Every future snapshot stores source-provided `observed_at`, `period_start`, `period_end`, `imported_at`, real dimension columns and explicit grain semantics.

- A point observation is not converted into a period aggregate.
- A period aggregate is not replicated across absent dimensions.
- Missing dimensions remain missing; dimensions are never invented.
- Incompatible periods/granularities must not silently merge.
- Logical key includes every dimension that truly defines the observation.
- UTC timestamps persist as ISO-8601 text; source calendar periods persist as canonical ISO date text when date semantics exist.

## 12. Verification contract

### Automated migration/database tests

1. Clean temp DB migrates to version 1 and contains exactly the four core production tables plus `schema_migrations`.
2. Second run is a no-op and version 1 appears once.
3. Injected synthetic failing registry migration rolls back its schema changes and version row.
4. Every factory connection reports `PRAGMA foreign_keys = 1`.
5. `SCOZ_DB_PATH` targets a temp DB without touching production data.
6. All PR3+ feature table names are absent.

### Product tests

Create owned and non-owned Product; get both; change ownership and `updated_at`; add/lookup identity; reject attaching the same scoped identity to two products with `ExternalIdentityConflict`; allow the same value under distinct account scopes. Assert the repository API/schema has no name, brand or photo matching mechanism.

### Lineage tests

Create RUNNING batches and independently finish fresh batches as SUCCESS, PARTIAL_SUCCESS and FAILED. Assert terminal/repeated/RUNNING finish is rejected. Attach artifact and round-trip SHA/name/size/path; verify correct parent; reject invalid FK, negative size and unsafe stored path. Database CHECK/FK failures are exercised without exposing raw integrity errors as the repository contract.

### Launcher regression tests

Record mock events to prove migration occurs before `start_wrapper()`. On migration failure assert `start_wrapper` not called, browser not opened, launch non-zero and final status `failed`. Preserve exact health identity, already-running, foreign-port, browser-after-health and sole-PID-writer tests.

### Authoritative post-push Windows acceptance

Extend the existing portable smoke minimally to verify: clean first run creates `data/scoz.db`; `schema_migrations` contains exactly version 1; second run preserves the same DB and does not reapply version 1; dependency repair and damaged-runtime rebuild preserve DB content; spaces + Cyrillic path still works; all existing PR1 eight scenarios remain green. GitHub Actions Windows is authoritative; no desktop testing request is part of handoff.

### README

Implementation PR2 minimally updates README with only the operational fact that SCOZ stores user-owned SQLite at `data/scoz.db` and applies migrations automatically. README does not document schema.

## 13. Non-goals and anti-scope gate

PR2 excludes real Ozon XLSX parsers; upload/import endpoint; `ProductSnapshot`; `SearchVisibilitySnapshot`; `QueryMetricSnapshot`; `ProductQuerySnapshot`; `SearchPositionSnapshot`; `AdvertisingSnapshot`; `SearchQuery`; `Cluster`; relevant-query workflow; benchmark and `BenchmarkSet`/`BenchmarkSetRevision`; analytics; diagnostics; Query Opportunity; Ramp-up; credentials/keystore; Ozon API; MPStats API; background jobs; scheduler; source capability framework; generic source resolver; ORM; SQLAlchemy; Alembic; frontend feature; auth/security redesign.

Migration 001 must not create any of those tables, `BenchmarkMember`, `RelevantQueryScope`, `Opportunity`, `RampUp`, or equivalents. Product has no benchmark membership, query state, sales, price, stock, rating, reviews, title/photo history or advertising fields. No Product CRUD API/UI, import UI, DB settings, migration/provenance/debug page or navigation item is added; current `Товары / Данные / Настройки` shell remains unchanged. Requirements and CI dependency setup remain unchanged.

## 14. Acceptance / Definition of Done

1. Clean `data/scoz.db` is created automatically through the configured production path.
2. Migration 001 applies exactly once; repeated startup is migration-safe.
3. Product creation, lookup and mutable ownership work through `ProductRepository`.
4. External identity is unique by source/type/value/account scope.
5. ImportBatch and optional SourceArtifact form an explicit provenance root.
6. SQL exists only under `backend/persistence/**`.
7. Migration 001 contains exactly four business tables; future snapshot/feature tables are absent.
8. Test-only fixture proves duplicate, corrected revision, new period and new dimension semantics without production snapshot infrastructure.
9. Normalized payload hash is deterministic and changes with normalized value.
10. Period/granularity conventions are explicit without a generic framework.
11. Migration failure prevents backend/browser startup and produces failed startup status.
12. Runtime repair/rebuild preserves DB.
13. Full existing and new Python test suite is green.
14. Requirements contain no DB framework and remain unchanged.
15. Authoritative Windows CI, including expanded portable smoke, is green after push.

## 15. Spec self-review gates

Before PR2 implementation handoff, reviewers verify: no unresolved placeholders; no production PR3+ entities; no SQL outside persistence; no DB dependency/ORM; migrations precede new server launch; lineage supports artifact and API provenance; duplicate/correction behavior is unambiguous; missing/incompatible grain is never invented or mixed; and every Definition-of-Done item maps to the automated or Windows verification above.
