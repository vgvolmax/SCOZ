# SCOZ PR5 — Query Metrics & Own Product Queries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the two verified Ozon PR5 query-data XLSX sources as separate immutable histories: own-product query performance in `ProductQuerySnapshot` and market query Demand/Quality facts in `QueryMetricSnapshot`, with exact source semantics, provenance, source availability, API/UI import flows, and portable Windows support.

**Architecture:** PR5 remains one implementation PR with two isolated semantic verticals. Both reuse the existing exact `SearchQuery` identity, lineage/archive infrastructure, shared process-local import lock, and narrow mechanical upload helpers; seller-queries alone touches `Product` ownership, while market Query Metrics has no Product/Cluster dependency. The market XLSX path uses a transient source-specific compatibility copy plus raw OOXML numeric text so the verified Ozon package quirks and Decimal precision do not corrupt provenance or business values.

**Tech Stack:** Python 3.13, stdlib `sqlite3`/`zipfile`/`xml.etree.ElementTree`, FastAPI 0.139.2, openpyxl 3.1.5, committed HTML/CSS/JavaScript, pytest 8.4.2, Windows PowerShell smoke.

**Spec:** `docs/superpowers/specs/2026-08-19-scoz-pr5-query-data-import-implementation-spec.md`

**Source Contracts:**

- `docs/superpowers/specs/2026-08-18-ozon-seller-queries-xlsx-source-contract-v1.md`
- `docs/superpowers/specs/2026-08-19-ozon-query-metrics-xlsx-source-contract-v1.md`

## Global Constraints

- The approved PR5 Implementation Spec and both Source Contracts are authoritative. If this plan conflicts with them, stop and surface the conflict instead of inventing behavior.
- One PR5 implementation branch only; do not split production delivery into PR5A/PR5B.
- No Query Opportunity, relevant-query selection, benchmark composition, heatmap, SearchPositionSnapshot, diagnostics, advertising/Ramp-up, Ozon API sync, credentials, or PR6+ UI.
- No generic query-import framework, source registry, callback/plugin dispatcher, universal nullable query-observation table, generic XLSX repair framework, ORM, pandas, DataFrame domain contract, worker queue, or persistent jobs.
- No dependency changes. `requirements.txt`, `requirements-dev.txt`, portable runtime pins, and `.github/workflows/ci.yml` stay unchanged.
- No npm/frontend framework. Frontend remains committed HTML/CSS/JavaScript; Node is optional syntax validation only.
- No real user XLSX, source query lists, SKUs, titles, user DBs, credentials, or sensitive logs are committed. Fixtures are synthetic.
- Existing `SearchDimensionRepository.resolve_search_query()` is the sole shared `SearchQuery` resolver. Query identity remains source-exact after only U+0020/U+00A0 edge cleanup.
- Do not lowercase, case-fold, convert `ё`, stem, lemmatize, collapse internal spaces, remove punctuation, rewrite misspellings, infer SKU from numeric query text, or use fuzzy matching.
- `ProductQuerySnapshot` grain is exactly Product × SearchQuery × `period_start` × `period_end`.
- `QueryMetricSnapshot` grain is exactly SearchQuery × `period_start` × `period_end`; there is no Product or Cluster dimension.
- Historical observations are immutable. Same key/same payload is `DUPLICATE`; same key/changed payload appends `CORRECTED`; a different period pair starts revision 1.
- Seller-queries is positive ownership evidence and may set the resolved Product `is_owned=True`, but it never creates ProductSnapshot or bypasses the current PR3-backed catalog boundary.
- Market Query Metrics must not import/use `ProductRepository`, Product identity, Cluster persistence, or own-product conversions.
- Original uploaded bytes are the SourceArtifact/archive. Query Metrics compatibility copies are transient and never become provenance.
- Query Metrics exact numeric `<v>` text is parsed to `Decimal` before normalization. Never use binary float as canonical source representation when raw OOXML numeric text exists.
- `no_action_share_pct` may exceed 100 percentage points; dynamics may be large/negative; absence from market export never becomes zero demand or zero conversion.
- No SQL outside `backend/persistence/**` in production code. Tests may use isolated SQL to assert schema/data contracts.
- No business logic in FastAPI routes or frontend.
- Shared `IMPORT_LOCK` remains the only import concurrency mechanism.
- Staging/archive behavior uses the existing 25 MiB limit and `data/imports`; referenced archives are protected globally across all import kinds.
- A later FAILED import never erases already true PR5 source availability.
- `GET /api/imports` history remains paginated; global `source_availability` is computed by backend lineage over complete durable history and is independent of `items`, `offset`, and `limit`.
- Do not weaken PR1–PR4 assertions to make PR5 pass.
- Existing migrations 001–003 are immutable. Migration 004 is additive only. If implementation starts rewriting existing user rows/schema rather than adding the approved tables/columns, stop because that changes the risk profile and backup requirement.
- `tests/windows_smoke.ps1` must remain byte-level ASCII-safe; encode Russian synthetic strings through Python escapes rather than inserting non-ASCII PowerShell bytes.

## Execution Ownership

The repository `AGENTS.md` execution model controls:

1. the user selects the implementation branch;
2. Codex works only inside that selected branch;
3. Codex does not create/switch/delete branches, push, create PRs, or merge;
4. user push + PR creation comes after Codex handoff;
5. GitHub Actions is authoritative for post-push CI/Windows acceptance;
6. independent review is required before merge.

`Codex implementation complete` is not `PR merge-ready`.

## Implementation Run Baseline

Run these commands **from the repository root in the Codex terminal before Task 1 changes anything**:

```bash
git status --short
git rev-parse HEAD
PR5_BASE_SHA="$(git rev-parse HEAD)"
printf 'PR5_BASE_SHA=%s\n' "$PR5_BASE_SHA"
python -c "from pathlib import Path; p=Path('docs/superpowers/specs/2026-08-19-scoz-pr5-query-data-import-implementation-spec.md'); t=p.read_text(encoding='utf-8'); assert '**Status:** Approved implementation specification' in t; print('PR5 spec approved')"
```

Require a clean starting tree. Record the printed initial implementation-branch SHA as `PR5_BASE_SHA` in the task log and preserve the variable in the current execution shell session. Task 13 must use `$PR5_BASE_SHA`. If the execution environment loses shell state between tasks, restore `PR5_BASE_SHA` from that recorded factual SHA before running the audits. All PR-wide scope audits at the end compare `$PR5_BASE_SHA..HEAD`; never replace the recorded base with a fragile `HEAD~N` assumption.

## File Map

### Expected new production files

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

### Expected new test files

```text
tests/test_product_query_snapshot_repository.py
tests/test_query_metric_snapshot_repository.py
tests/test_ozon_seller_queries_parser.py
tests/test_ozon_query_metrics_parser.py
tests/test_import_runtime.py
tests/test_ozon_seller_queries_import.py
tests/test_ozon_query_metrics_import.py
tests/test_ozon_seller_queries_api.py
tests/test_ozon_query_metrics_api.py
```

### Allowed modified production/integration files

```text
backend/application/import_runtime.py
backend/domain/lineage.py
backend/persistence/migrations/runner.py
backend/persistence/repositories/lineage.py
backend/main.py
frontend/index.html
frontend/assets/js/app.js
frontend/assets/css/app.css        # only if existing layout primitives are insufficient
```

### Allowed modified test files

```text
tests/xlsx_factory.py
tests/test_database.py
tests/test_migrations.py
tests/test_lineage_repository.py
tests/test_product_repository.py
tests/test_observation_revision_convention.py
tests/test_frontend_contract.py
tests/windows_smoke.ps1
```

A listed modification may be unnecessary and omitted. Any production file outside this map requires a concrete spec-driven reason and explicit review before proceeding. Protected runtime/dependency files remain unchanged.

## Task Order

Execute Tasks 1–13 in order. Each task ends with a fresh targeted GREEN run, adjacent regression run, `git diff --check`, intended-path review, and a focused local commit. Do not batch multiple tasks into one unreviewable change.

---

### Task 1: Freeze PR5 domain contracts and synthetic workbook primitives

**Files:**

- Create: `backend/domain/product_query.py`
- Create: `backend/domain/query_metric.py`
- Modify: `tests/xlsx_factory.py`
- Create: `tests/test_ozon_seller_queries_parser.py` (domain/factory tests only in this task)
- Create: `tests/test_ozon_query_metrics_parser.py` (domain/factory tests only in this task)

**Interfaces — Consumes:**

- `SnapshotWriteKind` and `canonical_decimal_text` from `backend.domain.product_snapshot`.
- `ImportStatus`, `SourceArtifact`, and `normalized_payload_sha256` from `backend.domain.lineage`.
- Existing `SearchQuery` identity from `backend.domain.search_visibility` / `SearchDimensionRepository` is reused later; do not define another query entity.

**Interfaces — Produces:**

`backend/domain/product_query.py`:

```python
class ProductQueryPositionState(str, Enum):
    KNOWN = "KNOWN"
    SOURCE_ZERO = "SOURCE_ZERO"

@dataclass(frozen=True)
class ProductQuerySnapshot: ...
@dataclass(frozen=True)
class ProductQueryWriteResult:
    kind: SnapshotWriteKind
    snapshot: ProductQuerySnapshot

@dataclass(frozen=True)
class ProductQueryRowError: ...
@dataclass(frozen=True)
class ParsedProductQueryRow: ...
@dataclass(frozen=True)
class ParsedSellerQueriesReport: ...
@dataclass(frozen=True)
class OzonSellerQueriesImportSummary: ...
@dataclass(frozen=True)
class OzonSellerQueriesImportResult: ...

PRODUCT_QUERY_PAYLOAD_FIELDS = (
    "searched_users", "seen_users", "position_state", "average_position",
    "search_to_card_conversion_pct", "search_to_order_conversion_pct",
    "ordered_units", "ordered_revenue_rub",
)

def product_query_payload_sha256(values: Mapping[str, object]) -> str: ...
```

Freeze the full seller error hierarchy named in Implementation Spec §10, including `OzonSellerQueriesImportFailure(error=..., result=...)` with public `.error` and nullable `.result`.

`backend/domain/query_metric.py`:

```python
@dataclass(frozen=True)
class QueryMetricSnapshot: ...
@dataclass(frozen=True)
class QueryMetricWriteResult:
    kind: SnapshotWriteKind
    snapshot: QueryMetricSnapshot

@dataclass(frozen=True)
class QueryMetricRowError: ...
@dataclass(frozen=True)
class ParsedQueryMetricRow: ...
@dataclass(frozen=True)
class ParsedQueryMetricsReport: ...
@dataclass(frozen=True)
class OzonQueryMetricsImportSummary: ...
@dataclass(frozen=True)
class OzonQueryMetricsImportResult: ...

QUERY_METRIC_PAYLOAD_FIELDS = (
    "popularity_users", "dynamics_28d_pct", "dynamics_7d_pct",
    "cart_add_users", "market_cart_conversion_pct",
    "unique_buyers_with_orders", "market_order_conversion_pct",
    "ordered_revenue_rub", "no_action_queries", "no_action_share_pct",
)

def query_metric_payload_sha256(values: Mapping[str, object]) -> str: ...
```

Freeze the full Query Metrics error hierarchy named in Implementation Spec §14, including `OzonQueryMetricsImportFailure(error=..., result=...)`.

Synthetic fixture primitives:

```python
def build_ozon_seller_queries_workbook(...) -> bytes: ...
def build_ozon_query_metrics_workbook(...) -> bytes: ...
```

The Query Metrics builder must support package mutation arguments sufficient to synthesize exact raw numeric `<v>` overrides, stored `<dimension ref="A1">`, `horizontal="Left"`/`"Right"`, formulas, merges, extra sheets, L+ business values, sort/header mutations, and fewer-than-10,000 valid rows without copying real evidence bytes.

**Steps:**

- [ ] **Step 1: Write RED dataclass/field-order tests.** Assert `dataclasses.fields()` exactly matches Implementation Spec §§5, 6, 10, 14, and 21 for snapshots, parsed report DTOs, summaries, and results. Assert all DTOs are frozen and the two failure carriers preserve typed error + nullable result.
- [ ] **Step 2: Write RED payload tests.** Assert exact field tuple order; missing/extra keys fail; `Decimal("2.480")` canonicalizes as `"2.48"`; `SOURCE_ZERO` hashes its enum string with `average_position=None`; equal Decimal spellings hash identically; Query Metrics nullable dynamics hash JSON null; no float enters canonical payloads.
- [ ] **Step 3: Write seller synthetic structure tests.** Generated workbook must have one sheet, exact rows 1–8, exact A:K row-6 Unicode headers including LF/NBSP, row 5/7 blanks, row-8 A:C product context, row 9+ D:K observations, and configurable formula/merge/L+ mutations.
- [ ] **Step 4: Write market synthetic structure/package tests.** Generated workbook must have exact A1 period, exact A2 sort, exact row-3 headers, ignored row 4, row 5+ observations; optional package post-processing must produce exact raw `<v>` text, false `dimension=A1`, and capitalized alignment values while keeping the workbook synthetic.
- [ ] **Step 5: Run RED.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_parser.py tests/test_ozon_query_metrics_parser.py -q
  ```

  Expected initial failures: missing PR5 domain modules/builders and missing payload helpers.

- [ ] **Step 6: Implement minimal domain declarations and payload helpers.** Use `canonical_decimal_text`, enum `.value`, JSON null for `None`, and `normalized_payload_sha256`; do not add cross-field arithmetic validation in hash helpers.
- [ ] **Step 7: Implement both synthetic builders.** Keep real identifiers/text out of defaults. For Query Metrics raw numeric precision, post-process only the synthetic ZIP worksheet XML by cell coordinate rather than relying on Python float serialization.
- [ ] **Step 8: Rerun targeted GREEN.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_parser.py tests/test_ozon_query_metrics_parser.py -q
  ```

- [ ] **Step 9: Run adjacent domain/factory regressions.**

  ```bash
  python -m pytest tests/test_ozon_products_parser.py tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] **Step 10: Hygiene + commit.**

  ```bash
  git diff --check
  git diff -- backend/domain/product_query.py backend/domain/query_metric.py tests/xlsx_factory.py tests/test_ozon_seller_queries_parser.py tests/test_ozon_query_metrics_parser.py
  git add backend/domain/product_query.py backend/domain/query_metric.py tests/xlsx_factory.py tests/test_ozon_seller_queries_parser.py tests/test_ozon_query_metrics_parser.py
  git commit -m "test/domain: add PR5 query domains and XLSX fixtures"
  ```

---

### Task 2: Add migration 004 for both immutable query histories and PR5 lineage context

**Files:**

- Create: `backend/persistence/migrations/migration_004_pr5_query_data.py`
- Modify: `backend/persistence/migrations/runner.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_migrations.py`

**Interfaces — Consumes:** migrations 001–003 and exact DDL contracts from Implementation Spec §8.

**Interfaces — Produces:** migration registry tuple:

```python
(4, "pr5_query_data", "backend.persistence.migrations.migration_004_pr5_query_data")
```

and tables `product_query_snapshots`, `query_metric_snapshots` plus five nullable `import_batches` columns:

```text
period_start
period_end
report_generated_at
report_product_ozon_id
sort_context
```

**Steps:**

- [ ] **Step 1: Write RED migration-history tests.** Fresh DB and 001/002/003 upgrade paths must end with versions 1–4 as a contiguous registry prefix without changing prior migration names.
- [ ] **Step 2: Write RED exact-schema tests for `product_query_snapshots`.** Assert exact columns/FKs, revision uniqueness `(product_id, search_query_id, period_start, period_end, revision)`, SHA length, nonnegative counts, state constraint, and `KNOWN` iff positive average position / `SOURCE_ZERO` iff null.
- [ ] **Step 3: Write RED exact-schema tests for `query_metric_snapshots`.** Assert exact columns/FKs, revision uniqueness `(search_query_id, period_start, period_end, revision)`, SHA length, nonnegative count columns, nullable dynamics only at schema level, and TEXT Decimal storage fields.
- [ ] **Step 4: Write RED index tests.** Assert only the spec-required current/history + lineage indexes and exact column order; do not add Query Opportunity indexes.
- [ ] **Step 5: Write RED lineage-column tests.** Existing PR3/PR4 columns stay unchanged; exactly five PR5 nullable columns are appended. No seller article/title columns or report-context table.
- [ ] **Step 6: Run RED.**

  ```bash
  python -m pytest tests/test_database.py tests/test_migrations.py -q
  ```

  Expected: registry stops at 3 and PR5 tables/columns are absent.

- [ ] **Step 7: Implement additive migration with individual `conn.execute(...)`.** Do not use `executescript`, `BEGIN`, `COMMIT`, or `ROLLBACK` inside the migration module. Store date/datetime values as TEXT; date-order validation remains domain/repository responsibility.
- [ ] **Step 8: Register version 4 after migration 003.** Do not renumber or edit prior migrations.
- [ ] **Step 9: Rerun targeted GREEN and adjacent migration regressions.**

  ```bash
  python -m pytest tests/test_database.py tests/test_migrations.py -q
  python -m pytest tests/test_product_snapshot_repository.py tests/test_search_visibility_snapshot_repository.py tests/test_lineage_repository.py -q
  ```

- [ ] **Step 10: Hygiene + commit.**

  ```bash
  git diff --check
  git diff -- backend/persistence/migrations/migration_004_pr5_query_data.py backend/persistence/migrations/runner.py tests/test_database.py tests/test_migrations.py
  git add backend/persistence/migrations/migration_004_pr5_query_data.py backend/persistence/migrations/runner.py tests/test_database.py tests/test_migrations.py
  git commit -m "feat: add PR5 query data migration"
  ```

---

### Task 3: Persist immutable ProductQuerySnapshot revisions

**Files:**

- Create: `backend/persistence/repositories/product_query_snapshots.py`
- Create: `tests/test_product_query_snapshot_repository.py`
- Modify: `tests/test_observation_revision_convention.py`

**Interfaces — Consumes:** `ProductQuerySnapshot`, `ProductQueryWriteResult`, `ProductQueryPositionState`, `SnapshotWriteKind`, migration 004, canonical Decimal/date/datetime helpers.

**Interfaces — Produces:**

```python
class ProductQuerySnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def get(self, snapshot_id: int) -> ProductQuerySnapshot | None: ...
    def find_current(
        self, *, product_id: int, search_query_id: int,
        period_start: date, period_end: date,
    ) -> ProductQuerySnapshot | None: ...
    def resolve_revision(
        self, *, product_id: int, search_query_id: int,
        period_start: date, period_end: date,
        payload_sha256: str, import_batch_id: int,
        source_artifact_id: int, imported_at: datetime,
        snapshot_values: Mapping[str, object],
    ) -> ProductQueryWriteResult: ...
```

**Steps:**

- [ ] **Step 1: Write RED NEW/DUPLICATE/CORRECTED tests.** Revision 1 NEW inserts once; same key/hash returns DUPLICATE with no insert; changed payload/hash appends revision 2 and points `supersedes_snapshot_id` to prior current row; prior row remains immutable.
- [ ] **Step 2: Write RED key-independence tests.** Changing Product, SearchQuery, `period_start`, or `period_end` yields an independent revision-1 observation.
- [ ] **Step 3: Write RED state/Decimal tests.** `KNOWN` requires positive integer position; `SOURCE_ZERO` requires null position; Decimal percentage points/revenue round-trip as canonical text with no float.
- [ ] **Step 4: Write RED validation tests.** Reject end-before-start, naive `imported_at`, invalid SHA, missing/extra payload keys, negative counts, invalid state/position combination, `search_to_card_conversion_pct` or `search_to_order_conversion_pct` below 0 or above 100, `ordered_revenue_rub` below 0, and NaN/Infinity/-Infinity for every Decimal field. Preserve valid boundary values: both conversions may equal 0 or 100, and revenue may equal 0. Assert every rejection occurs before SQL mutation.
- [ ] **Step 5: Run RED.**

  ```bash
  python -m pytest tests/test_product_query_snapshot_repository.py tests/test_observation_revision_convention.py -q
  ```

- [ ] **Step 6: Implement repository mapping and revision resolution.** `find_current` orders `revision DESC LIMIT 1`; compare canonical payload SHA only; store Decimal with `canonical_decimal_text`; reconstruct enum/Decimal/date/datetime exactly. Validate the canonical domain invariants from Step 4 before any SQL mutation.
- [ ] **Step 7: Rerun GREEN + adjacent repositories.**

  ```bash
  python -m pytest tests/test_product_query_snapshot_repository.py tests/test_observation_revision_convention.py -q
  python -m pytest tests/test_product_snapshot_repository.py tests/test_search_visibility_snapshot_repository.py -q
  ```

- [ ] **Step 8: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/persistence/repositories/product_query_snapshots.py tests/test_product_query_snapshot_repository.py tests/test_observation_revision_convention.py
  git commit -m "feat: persist own-product query revisions"
  ```

---

### Task 4: Persist immutable QueryMetricSnapshot revisions

**Files:**

- Create: `backend/persistence/repositories/query_metric_snapshots.py`
- Create: `tests/test_query_metric_snapshot_repository.py`
- Modify: `tests/test_observation_revision_convention.py`

**Interfaces — Consumes:** `QueryMetricSnapshot`, `QueryMetricWriteResult`, migration 004, `SnapshotWriteKind`, canonical Decimal/date/datetime helpers.

**Interfaces — Produces:**

```python
class QueryMetricSnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def get(self, snapshot_id: int) -> QueryMetricSnapshot | None: ...
    def find_current(
        self, *, search_query_id: int, period_start: date, period_end: date,
    ) -> QueryMetricSnapshot | None: ...
    def resolve_revision(
        self, *, search_query_id: int, period_start: date, period_end: date,
        payload_sha256: str, import_batch_id: int,
        source_artifact_id: int, imported_at: datetime,
        snapshot_values: Mapping[str, object],
    ) -> QueryMetricWriteResult: ...
```

**Steps:**

- [ ] **Step 1: Write RED revision tests.** NEW/DUPLICATE/CORRECTED behavior mirrors the frozen convention but uses only SearchQuery + period pair as logical key.
- [ ] **Step 2: Write RED exact value tests.** Nullable dynamics round-trip as `None`; very large/negative dynamics persist; market conversions/revenue/no-action share retain exact Decimal text, including share >100 percentage points.
- [ ] **Step 3: Write RED anti-dimension tests.** Repository signature/table has no Product or Cluster argument/column; numeric query identity is only `search_query_id`.
- [ ] **Step 4: Write RED validation tests.** Reject invalid SHA, end-before-start, naive imported time, negative count fields, missing/extra payload fields; `market_cart_conversion_pct` or `market_order_conversion_pct` below 0 or above 100; `ordered_revenue_rub` below 0; `no_action_share_pct` below 0; and NaN/Infinity/-Infinity for every Decimal field. Preserve as valid: market conversions equal to 0 or 100, revenue equal to 0, no-action share equal to 0 or above 100, large positive or negative dynamics, and `None` dynamics. Do not impose an artificial upper bound on `dynamics_28d_pct`, `dynamics_7d_pct`, or `no_action_share_pct`.
- [ ] **Step 5: Run RED.**

  ```bash
  python -m pytest tests/test_query_metric_snapshot_repository.py tests/test_observation_revision_convention.py -q
  ```

- [ ] **Step 6: Implement minimal repository and exact reconstruction.** Enforce the canonical Decimal bounds from Step 4 before any SQL mutation. No cross-field recomputation or relationship checks.
- [ ] **Step 7: Rerun GREEN + adjacent repositories.**

  ```bash
  python -m pytest tests/test_query_metric_snapshot_repository.py tests/test_observation_revision_convention.py -q
  python -m pytest tests/test_product_query_snapshot_repository.py tests/test_search_visibility_snapshot_repository.py -q
  ```

- [ ] **Step 8: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/persistence/repositories/query_metric_snapshots.py tests/test_query_metric_snapshot_repository.py tests/test_observation_revision_convention.py
  git commit -m "feat: persist market query metric revisions"
  ```

---

### Task 5: Implement strict seller-queries parser

**Files:**

- Create: `backend/ingestion/ozon_seller_queries_xlsx.py`
- Modify: `tests/test_ozon_seller_queries_parser.py`

**Interfaces — Consumes:** Task 1 seller domain DTOs/payload hash, synthetic seller builder, Source Contract v1.

**Interfaces — Produces:**

```python
def parse_ozon_seller_queries_xlsx(path: Path) -> ParsedSellerQueriesReport: ...
```

**Steps:**

- [ ] **Step 1: Write RED exact-structure tests.** One worksheet; rows 1–4 exact markers/formats; row 5 blank; row 6 exact 11 headers including source LF/NBSP code points; row 7 blank; row 8 A:C required/D:K blank; no merges; nonempty L+ incompatible. For row 9 onward, require A:C to be semantically blank whenever D:K contains observation facts: a valid D:K observation with nonblank A, B, or C is `SellerQueriesIncompatibleReportSchema`; blank D:K with nonblank A, B, or C is not an ordinary trailing blank and is also incompatible with exact v1 schema; a wholly semantically blank trailing A:K row is ignored. “Semantically blank” remains exactly `None` or exact `""`; whitespace-only strings are not semantically blank.
- [ ] **Step 2: Write RED deterministic report-classification tests.** PR3 Products, PR4 Search Visibility, and Query Metrics fixtures are `SellerQueriesWrongReportType`; partial seller markers/schema are `SellerQueriesIncompatibleReportSchema`; unreadable/non-XLSX is `SellerQueriesUnsupportedWorkbook`.
- [ ] **Step 3: Write RED metadata/product-context tests.** Parse generated UTC from rows 1–2 only (`+00`), period dates from rows 3–4 only, require start ≤ end, require positive decimal-digit A8 Ozon ID and nonempty B8 article/C8 title. Filename/mtime must not substitute.
- [ ] **Step 4: Write RED field tests for D:K.** Query edge cleanup only; grouped nonnegative integer text; `seen_users > searched_users` remains accepted; position 0 → `SOURCE_ZERO`+None, positive positions including >1000 → `KNOWN`; blank position invalid. For H/I percentages, 0% and 100% are valid, while negative and >100% values make the row invalid. Ordered units remain integer. For K revenue, 0 ₽ and positive grouped whole-ruble values are valid; negative revenue and fractional rubles/cents make the row invalid.
- [ ] **Step 5: Write RED formula/error tests.** Formula in structural/product-context cells is fatal incompatible schema; formula in query metric row yields the most specific recoverable row error and is never evaluated.
- [ ] **Step 6: Write RED duplicate/counter tests.** Identical canonical query + identical eight-field payload warns/dedupes; conflicting payload is fatal; enforce `rows_seen = len(rows)+len(row_errors)+duplicate_input_rows` for structurally valid reports.
- [ ] **Step 7: Run RED.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_parser.py -q
  ```

- [ ] **Step 8: Implement parser using binary file handle + openpyxl normal mode.** Open staged `.part` as `path.open('rb')`, pass the live stream to `openpyxl.load_workbook(..., data_only=False, read_only=False)`, keep handle alive until `workbook.close()`. Do not depend on pathname extension.
- [ ] **Step 9: Implement field-specific source helpers only inside this module.** No generic locale parser; no arithmetic repairs; preserve source facts exactly.
- [ ] **Step 10: Rerun GREEN + wrong-report regressions.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_parser.py -q
  python -m pytest tests/test_ozon_products_parser.py tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] **Step 11: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/ingestion/ozon_seller_queries_xlsx.py tests/test_ozon_seller_queries_parser.py
  git commit -m "feat: parse Ozon own-product query reports"
  ```

---

### Task 6: Implement Query Metrics compatibility copy and exact raw-OOXML parser

**Files:**

- Create: `backend/ingestion/ozon_query_metrics_xlsx_compat.py`
- Create: `backend/ingestion/ozon_query_metrics_xlsx.py`
- Modify: `tests/test_ozon_query_metrics_parser.py`

**Interfaces — Consumes:** Task 1 QueryMetric DTO/payload helpers, synthetic market builder, Query Metrics Source Contract v1.

**Interfaces — Produces:**

```python
def prepare_query_metrics_read_copy(original_path: Path, read_copy_path: Path) -> None: ...
def parse_ozon_query_metrics_xlsx(path: Path) -> ParsedQueryMetricsReport: ...
```

**Steps:**

- [ ] **Step 1: Write RED compatibility-copy tests.** A synthetic source with `horizontal="Left"`/`"Right"` fails direct pinned openpyxl load, but the prepared read-copy loads; original bytes/SHA remain unchanged; read-copy business cell XML/value text is unchanged except exact style-attribute capitalization replacements.
- [ ] **Step 2: Write RED false-dimension tests.** Source declares `<dimension ref="A1">` while actual cells extend below/right; parser still sees all actual candidate rows and K-column values. Do not require rewriting dimension if normal mode can access raw cells.
- [ ] **Step 3: Write RED worksheet relationship test.** Synthetic ZIP with worksheet package path resolved through `xl/workbook.xml` + `xl/_rels/workbook.xml.rels` must parse; code must not assume `xl/worksheets/sheet1.xml`.
- [ ] **Step 4: Write RED exact raw numeric tests.** Override underlying `<v>` text for B:K with values such as `0.1612`, `0.403`, `1234.5678`; assert canonical domain receives Decimal percentage points/revenue from exact text, not a binary float rendering.
- [ ] **Step 5: Write RED structural/detection tests.** Exact A1 `Период: DD.MM.YYYY - DD.MM.YYYY`, exact A2 sort, exact row-3 A:K headers, row 4 ignored, one sheet, no merges, no L+ business values, structural formula fatal; PR3/PR4/seller fixtures → wrong report type; damaged expected shape → incompatible; unreadable ZIP/XML → unsupported.
- [ ] **Step 6: Write RED candidate-row tests.** Row 5+ with any nonblank A:K is candidate; semantic blank trailing rows ignored; fewer than 10,000 rows valid; absent query creates no synthetic observation.
- [ ] **Step 7: Write RED field and boundary tests.** Nonnegative integer native numerics with bool rejected; numeric-only query remains query text. For market cart/order conversion raw XLSX fractions, 0 is valid and becomes `Decimal("0")`, 1 is valid and becomes `Decimal("100")`, and values below 0 or above 1 make the row invalid. Revenue 0 is valid; a positive Decimal with 1–4 or more source decimal places is valid with its precision preserved; a negative value makes the row invalid. No-action share 0 is valid, 1 is valid and becomes 100 percentage points, values above 1 remain valid and are preserved above 100 percentage points, and negative values make the row invalid. Dynamics exact numeric values are multiplied by 100: exact string `"-"` becomes `None`, while negative numeric, zero, large positive, and large negative values remain valid; any non-finite numeric representation is invalid. Do not introduce cross-field arithmetic constraints.
- [ ] **Step 8: Write RED formulas/duplicates/counters.** Candidate-row formula is recoverably invalid even if cached `<v>` exists; identical query+payload dedupes; conflicting duplicate fatal; parser counter invariant matches Task 1 semantics.
- [ ] **Step 9: Run RED.**

  ```bash
  python -m pytest tests/test_ozon_query_metrics_parser.py -q
  ```

- [ ] **Step 10: Implement compatibility helper with stdlib ZIP copy.** Create `read_copy_path` exclusively, copy every member, and for `xl/styles.xml` only replace exact ASCII attribute values `horizontal="Left"`→`horizontal="left"` and `horizontal="Right"`→`horizontal="right"`. Do not rewrite arbitrary XML or the original file.
- [ ] **Step 11: Implement a narrow raw-cell reader.** Resolve sole worksheet target from workbook relationships, parse actual cell references from worksheet XML, expose exact `<v>` text by coordinate, and derive actual candidate row numbers from those references. Do not trust worksheet dimension/max_row for coverage.
- [ ] **Step 12: Implement parser with two synchronized views.** openpyxl (`data_only=False`, normal mode) handles strings, merges, formulas, structure; raw OOXML provides numeric lexical text. Reject formula before considering cached numeric `<v>`.
- [ ] **Step 13: Rerun GREEN + adjacent parser regressions.**

  ```bash
  python -m pytest tests/test_ozon_query_metrics_parser.py -q
  python -m pytest tests/test_ozon_seller_queries_parser.py tests/test_ozon_products_parser.py tests/test_ozon_search_visibility_parser.py -q
  ```

- [ ] **Step 14: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/ingestion/ozon_query_metrics_xlsx.py backend/ingestion/ozon_query_metrics_xlsx_compat.py tests/test_ozon_query_metrics_parser.py
  git commit -m "feat: parse Ozon market query metrics exactly"
  ```

---

### Task 7: Extract narrow shared XLSX staging/archive mechanics

**Files:**

- Modify: `backend/application/import_runtime.py`
- Create: `tests/test_import_runtime.py`

**Interfaces — Consumes:** existing `MAX_UPLOAD_BYTES`, `MAX_ROW_ERRORS`, `IMPORT_LOCK`, `ARCHIVE_RE`, `safe_original_basename`.

**Interfaces — Produces:**

```python
@dataclass(frozen=True)
class StagedXlsxUpload:
    original_name: str
    staged_path: Path
    sha256: str
    byte_size: int

class XlsxUploadUnsupportedMediaType(ValueError): ...
class XlsxUploadTooLarge(ValueError): ...

def stage_xlsx_upload(
    *, upload: BinaryIO, original_name: str, data_dir: Path,
) -> StagedXlsxUpload: ...

def publish_staged_archive(
    staged: StagedXlsxUpload, *, data_dir: Path, imported_at: datetime,
) -> tuple[Path, str]: ...
```

Filesystem `OSError`/`FileExistsError` remain mechanical errors for source-specific services to map; the helper does not know report/domain error classes.

**Steps:**

- [ ] **Step 1: Write RED safe staging tests.** `.xlsx` accepted case-insensitively, non-XLSX rejected before durable DB work; safe basename handles POSIX/Windows/UNC names; stream writes `.upload-<uuid>.part`, hashes ORIGINAL bytes, records exact size, flushes/fsyncs.
- [ ] **Step 2: Write RED size/error cleanup tests.** >25 MiB raises `XlsxUploadTooLarge` and removes partial stage; staging filesystem error surfaces without a fake source-schema error.
- [ ] **Step 3: Write RED archive tests.** Filename matches existing `ARCHIVE_RE`; exact SHA is embedded; path is reserved exclusively; returned relative path is `imports/<name>`; staged original bytes become final archive; collision raises filesystem/persistence failure rather than overwrite ambiguity. Also cover failure after successful archive-path reservation: when move/replace raises `OSError`, the helper propagates the error, best-effort removes the helper-owned reserved final archive, leaves staged ownership unambiguous, and never deletes another pre-existing archive.
- [ ] **Step 4: Run RED.**

  ```bash
  python -m pytest tests/test_import_runtime.py -q
  ```

- [ ] **Step 5: Implement only mechanical helpers.** `publish_staged_archive()` owns any final path it successfully created/reserved until successful staged-file publication. If publication fails, it must best-effort remove only that helper-owned reservation before propagating the mechanical error. Keep staged ownership unambiguous and never remove another existing archive. No parser callbacks, report registry, Product/SearchQuery access, ImportBatch creation, source-specific exceptions, analytics, or source-specific lifecycle management.
- [ ] **Step 6: Keep PR3/PR4 application services untouched.** Run their regressions to prove helper extraction did not alter existing flows.

  ```bash
  python -m pytest tests/test_import_runtime.py tests/test_ozon_products_import.py tests/test_ozon_search_visibility_import.py -q
  ```

- [ ] **Step 7: Hygiene + commit.**

  ```bash
  git diff --check
  git diff -- backend/application/import_runtime.py tests/test_import_runtime.py
  git add backend/application/import_runtime.py tests/test_import_runtime.py
  git commit -m "refactor: add narrow PR5 XLSX staging helpers"
  ```

---

### Task 8: Extend durable lineage, unified history, recovery metadata, and global source availability

**Files:**

- Modify: `backend/domain/lineage.py`
- Modify: `backend/persistence/repositories/lineage.py`
- Modify: `tests/test_lineage_repository.py`

**Interfaces — Consumes:** migration 004 context columns and Task 1 source-specific summary DTOs.

**Interfaces — Produces:**

```python
# ImportHistoryItem.report_type allows:
# OZON_PRODUCTS | OZON_SEARCH_VISIBILITY | OZON_OWN_PRODUCT_QUERIES | OZON_QUERY_METRICS

class LineageRepository:
    def finish_ozon_seller_queries_import(...) -> OzonSellerQueriesImportSummary: ...
    def finish_ozon_query_metrics_import(...) -> OzonQueryMetricsImportSummary: ...
    def fail_running_ozon_seller_queries_imports(*, finished_at: datetime) -> int: ...
    def fail_running_ozon_query_metrics_imports(*, finished_at: datetime) -> int: ...
    def get_pr5_source_availability(self) -> dict[str, bool]: ...
```

`get_pr5_source_availability()` returns exactly:

```python
{
    "own_product_queries": bool,
    "query_metrics": bool,
}
```

**Steps:**

- [ ] **Step 1: Write RED summary/finalization tests.** Seller finish validates exact import kind, status transition, nonnegative counters, `period_start<=period_end`, timezone-aware generated_at, positive-digit product Ozon ID; Query Metrics validates exact import kind, period, nonnegative counters, and exact supported sort context.
- [ ] **Step 2: Write RED ImportHistoryItem tests.** All four report types serialize correct applicable context; non-applicable fields are null; mixed history remains newest-first and paginated with correct total.
- [ ] **Step 3: Write RED global availability tests.** At least one SUCCESS/PARTIAL_SUCCESS seller batch → `own_product_queries=True`; same for Query Metrics; later FAILED does not reset; a kind with no success remains false.
- [ ] **Step 4: Write RED pagination-independence regression.** Put a qualifying PR5 success older than >50 newer history rows; first page excludes that batch but `get_pr5_source_availability()` remains true. Assert same result across different limit/offset.
- [ ] **Step 5: Write RED recovery tests.** Each PR5 `fail_running_*` only marks its own RUNNING kind FAILED with supplied aware UTC time; repeated call is idempotent.
- [ ] **Step 6: Run RED.**

  ```bash
  python -m pytest tests/test_lineage_repository.py -q
  ```

- [ ] **Step 7: Extend `ImportHistoryItem` with nullable PR5 context fields.** Prefer keyword construction in `_history_item` to prevent positional cross-population while preserving existing public PR3/PR4 fields.
- [ ] **Step 8: Implement source-specific finish/mapping methods and full-history availability SQL.** Production SQL stays in this repository. Availability query must use `EXISTS` over complete `import_batches`, not current paginated rows.
- [ ] **Step 9: Expand unified list/count from two to four import kinds.** Do not create a generic callback registry.
- [ ] **Step 10: Rerun GREEN + adjacent lineage/API-data regressions.**

  ```bash
  python -m pytest tests/test_lineage_repository.py -q
  python -m pytest tests/test_ozon_products_api.py tests/test_ozon_search_visibility_api.py -q
  ```

- [ ] **Step 11: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/domain/lineage.py backend/persistence/repositories/lineage.py tests/test_lineage_repository.py
  git commit -m "feat: extend lineage for PR5 query imports"
  ```

---

### Task 9: Implement seller-queries import service with atomic positive ownership evidence

**Files:**

- Create: `backend/application/ozon_seller_queries_import.py`
- Create: `tests/test_ozon_seller_queries_import.py`
- Modify: `tests/test_product_repository.py`

**Interfaces — Consumes:** Task 5 parser, Task 7 staging helpers/shared lock, Task 8 lineage, existing `ProductRepository` and `SearchDimensionRepository`, Task 3 snapshot repository.

**Interfaces — Produces:**

```python
def import_ozon_seller_queries_xlsx(
    *, upload: BinaryIO, original_name: str,
    db_path: Path | None = None, data_dir: Path = DATA_DIR,
) -> OzonSellerQueriesImportResult: ...

def recover_interrupted_ozon_seller_queries_imports(
    *, db_path: Path | None = None, data_dir: Path = DATA_DIR,
) -> None: ...
```

**Steps:**

- [ ] **Step 1: Write RED valid-import lifecycle test.** Shared lock → original staging/hash → durable RUNNING batch+artifact → parse → original archive → one transaction resolving Product, ownership, SearchQuery, snapshot revisions, lineage finish.
- [ ] **Step 2: Write RED ownership matrix.** Unknown Ozon Product resolves/creates and ends true; existing false becomes true; existing true stays true; exact external identity reused; later valid seller import may restore true after manual false.
- [ ] **Step 3: Write RED catalog-boundary tests.** Seller-only Product has no ProductSnapshot and stays absent from `/api/products` repository list/count/readiness; after PR3 ProductSnapshot exists for same identity, same Product is visible and owned.
- [ ] **Step 4: Write RED atomic rollback test.** Inject persistence failure after Product/ownership/SearchQuery work begins; transaction rolls all domain mutations back together, owned archive is compensated, durable batch becomes FAILED when possible.
- [ ] **Step 5: Write RED counters/revisions test.** Synthetic valid + invalid + in-file identical duplicate + DB duplicate produces exact `rows_seen`, `rows_accepted`, `rows_skipped`, `duplicate_observations`, `new_observations`, `corrected_revisions`; changed payload CORRECTED; changed period independent NEW.
- [ ] **Step 6: Write RED zero-usable/fatal/unexpected tests.** Zero usable commits no Product/SearchQuery/snapshot mutation; source parser error gets durable FAILED result when batch exists; unexpected programming exception is preserved after best-effort compensation and lock release.
- [ ] **Step 7: Write RED transport-mechanical mapping tests at service boundary.** Shared lock conflict, unsupported extension, >25 MiB, staging/archive filesystem failure, DB failure map only to seller-specific errors; no arbitrary internal error text leaks into domain messages.
- [ ] **Step 8: Write RED recovery/archive-safety tests.** RUNNING seller batches fail on recovery; stale `.upload-*` removed; orphan archives removed only when unreferenced globally; referenced/manual files preserved.
- [ ] **Step 9: Run RED.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_import.py tests/test_product_repository.py -q
  ```

- [ ] **Step 10: Implement service following the frozen lifecycle.** Use Task 7 helpers only for mechanics. After archive publication, perform `set_source_artifact_stored_relpath`, `resolve_or_create_ozon_product`, `set_owned(..., True)`, SearchQuery resolution, snapshot resolution, and success/partial lineage finish in one transaction.
- [ ] **Step 11: Implement private `_result` and best-effort `_finish_failed` patterns without catching unexpected programming exceptions as source/persistence errors.** Mirror the hardened PR4 compensation philosophy, but use seller DTOs/context.
- [ ] **Step 12: Rerun GREEN + PR3/PR4 import regressions.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_import.py tests/test_product_repository.py -q
  python -m pytest tests/test_ozon_products_import.py tests/test_ozon_search_visibility_import.py -q
  ```

- [ ] **Step 13: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/application/ozon_seller_queries_import.py tests/test_ozon_seller_queries_import.py tests/test_product_repository.py
  git commit -m "feat: import own-product query history"
  ```

---

### Task 10: Implement Query Metrics import service with transient compatibility copy

**Files:**

- Create: `backend/application/ozon_query_metrics_import.py`
- Create: `tests/test_ozon_query_metrics_import.py`

**Interfaces — Consumes:** Task 6 compatibility/parser, Task 7 staging helpers/shared lock, Task 8 lineage, `SearchDimensionRepository`, Task 4 QueryMetric repository.

**Interfaces — Produces:**

```python
def import_ozon_query_metrics_xlsx(
    *, upload: BinaryIO, original_name: str,
    db_path: Path | None = None, data_dir: Path = DATA_DIR,
) -> OzonQueryMetricsImportResult: ...

def recover_interrupted_ozon_query_metrics_imports(
    *, db_path: Path | None = None, data_dir: Path = DATA_DIR,
) -> None: ...
```

**Steps:**

- [ ] **Step 1: Write RED provenance/read-copy test.** SourceArtifact SHA/size/archive correspond to original bytes; `.readcopy-<uuid>.xlsx` is created only transiently, parsed, and deleted; never stored as SourceArtifact or archive.
- [ ] **Step 2: Write RED success/partial/counters/revision tests.** Valid import writes SearchQuery + QueryMetricSnapshot only; partial preserves valid rows; identical/input + DB duplicate counters obey frozen semantics; corrections/reperiod behave exactly.
- [ ] **Step 3: Write RED no-Product contract.** Snapshot import creates/mutates zero Products and Clusters; enforce by counts and by guarding against accidental `ProductRepository` use in service source.
- [ ] **Step 4: Write RED cleanup matrix.** Read-copy removed after success, parser fatal, zero usable, persistence failure, archive failure, and unexpected programming exception. Original staged/archive cleanup follows lifecycle ownership.
- [ ] **Step 5: Write RED source-package error mapping.** Exact compatibility failure that leaves unreadable ZIP/XML → QueryMetricsUnsupportedWorkbook; filesystem failure creating/removing read-copy → QueryMetricsImportPersistenceError, not schema error.
- [ ] **Step 6: Write RED shared-lock cross-kind test.** Lock held by PR3/PR4/seller/query-metrics import produces one common 409-class domain conflict and no durable side effects before batch.
- [ ] **Step 7: Write RED recovery test.** RUNNING batches become FAILED; stale `.upload-*` and `.readcopy-*` removed; global referenced archives/manual files preserved; recovery idempotent.
- [ ] **Step 8: Run RED.**

  ```bash
  python -m pytest tests/test_ozon_query_metrics_import.py -q
  ```

- [ ] **Step 9: Implement service with explicit stages.** Stage ORIGINAL → durable batch/artifact → create read-copy from ORIGINAL → parse → delete read-copy → zero-usable handling → publish ORIGINAL archive → one transaction resolving SearchQuery/snapshots/lineage. Never import/use ProductRepository.
- [ ] **Step 10: Preserve unexpected exceptions and compensate best-effort.** Do not reclassify programming errors as `UNSUPPORTED_WORKBOOK` or `IMPORT_PERSISTENCE_ERROR` unless they arose at the specific source/package or persistence boundary.
- [ ] **Step 11: Rerun GREEN + adjacent import regressions.**

  ```bash
  python -m pytest tests/test_ozon_query_metrics_import.py -q
  python -m pytest tests/test_ozon_seller_queries_import.py tests/test_ozon_search_visibility_import.py tests/test_ozon_products_import.py -q
  ```

- [ ] **Step 12: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/application/ozon_query_metrics_import.py tests/test_ozon_query_metrics_import.py
  git commit -m "feat: import market query metrics"
  ```

---

### Task 11: Wire FastAPI endpoints, unified history availability, and startup recovery

**Files:**

- Modify: `backend/main.py`
- Create: `tests/test_ozon_seller_queries_api.py`
- Create: `tests/test_ozon_query_metrics_api.py`

**Interfaces — Consumes:** Tasks 8–10 services/lineage and existing `_json` serializer/route pattern.

**Interfaces — Produces:**

```text
POST /api/imports/ozon-seller-queries
POST /api/imports/ozon-query-metrics
GET  /api/imports   # existing endpoint, extended response
```

`GET /api/imports` response includes:

```json
{
  "items": [],
  "total": 0,
  "source_availability": {
    "own_product_queries": false,
    "query_metrics": false
  }
}
```

**Steps:**

- [ ] **Step 1: Write RED seller HTTP success/partial tests with real `TestClient`.** Multipart valid → 200 source-specific result; partial → 200 with bounded first 50 row errors + total/truncated; metric payload arrays are not returned.
- [ ] **Step 2: Write RED Query Metrics HTTP success/partial tests.** Same transport guarantees; no generated_at invented; exact period/sort context returned.
- [ ] **Step 3: Write RED frozen error-envelope matrices for both endpoints.** unreadable 422, wrong report 422, incompatible 422, invalid period 422, conflict rows 422, no usable 422, lock 409/result null, oversized 413/result null, wrong media 415, missing/wrong multipart file 422, persistence 500 sanitized; seller additionally invalid generated_at/product context 422.
- [ ] **Step 4: Write RED close/sanitization tests.** `UploadFile.close()` in success and failure; no traceback, absolute path, `.part`, `.readcopy`, XML/SQL internals, or injected arbitrary exception text in responses.
- [ ] **Step 5: Write RED mixed-history/source-availability HTTP regression.** Four report types newest-first; pagination/total correct; >50 newer rows hide old success from `items` while `source_availability` stays true; later FAILED does not reset; availability identical across limit/offset.
- [ ] **Step 6: Write RED catalog/ownership integration.** Seller import updates ownership visible through `/api/products` only for an already PR3-backed Product; seller-only Product remains hidden.
- [ ] **Step 7: Write RED lifespan recovery.** TestClient startup invokes all four recovery functions and safely removes stale Query Metrics read-copy while preserving referenced archives.
- [ ] **Step 8: Run RED.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_api.py tests/test_ozon_query_metrics_api.py -q
  ```

- [ ] **Step 9: Add source-specific error maps and thin routes.** Routes validate transport, invoke one service call, serialize DTOs, map known failure classes, and close upload in `finally`; no parser/revision/persistence logic in route.
- [ ] **Step 10: Extend lifespan with seller and Query Metrics recovery after existing PR3/PR4 recovery.** No background cleanup service.
- [ ] **Step 11: Extend `GET /api/imports` to return full-history availability from `LineageRepository.get_pr5_source_availability()`.** Do not derive availability from returned `items`.
- [ ] **Step 12: Rerun GREEN + existing HTTP regressions.**

  ```bash
  python -m pytest tests/test_ozon_seller_queries_api.py tests/test_ozon_query_metrics_api.py -q
  python -m pytest tests/test_ozon_products_api.py tests/test_ozon_search_visibility_api.py tests/test_backend.py -q
  ```

- [ ] **Step 13: Hygiene + commit.**

  ```bash
  git diff --check
  git add backend/main.py tests/test_ozon_seller_queries_api.py tests/test_ozon_query_metrics_api.py
  git commit -m "feat: expose PR5 query import APIs"
  ```

---

### Task 12: Extend Data UI for both PR5 imports and global source availability

**Files:**

- Modify: `frontend/index.html`
- Modify: `frontend/assets/js/app.js`
- Modify: `frontend/assets/css/app.css` only if existing primitives cannot express the two cards/readiness labels
- Modify: `tests/test_frontend_contract.py`

**Interfaces — Consumes:** Task 11 API contracts and canonical Visual Design System.

**Interfaces — Produces:** exact UI hooks:

```text
ozon-seller-queries-file
seller-queries-file-name
seller-queries-submit
seller-queries-status
seller-queries-readiness

ozon-query-metrics-file
query-metrics-file-name
query-metrics-submit
query-metrics-status
query-metrics-readiness
```

and JS functions:

```javascript
submitSellerQueriesImport(file)
submitQueryMetricsImport(file)
```

**Steps:**

- [ ] **Step 1: Write RED static contract tests.** Four XLSX import controls exist with unique IDs/labels; PR5 endpoints appear exactly; no new global navigation or PR6+ analytics UI.
- [ ] **Step 2: Write RED interaction-source tests.** Seller success refreshes import history + Products; Query Metrics success refreshes import history; selected filename, disabled-until-selected, loading, success, partial, and error hooks are present.
- [ ] **Step 3: Write RED history rendering tests.** `OZON_OWN_PRODUCT_QUERIES` label/context includes product Ozon ID + exact period + accepted/skipped; `OZON_QUERY_METRICS` includes exact period + sort context; dynamic text is escaped or set through `textContent`.
- [ ] **Step 4: Write RED readiness-source test.** `loadImports()` renders readiness only from `data.source_availability`, while history uses `data.items`; no scan of paginated items is used to infer availability.
- [ ] **Step 5: Run RED.**

  ```bash
  python -m pytest tests/test_frontend_contract.py -q
  ```

- [ ] **Step 6: Add two Data-page cards using existing visual primitives.** Do not add Product Workspace, score, chart, heatmap, relevant-query selector, benchmark section, or generic import component framework.
- [ ] **Step 7: Implement the two source-specific submit functions and extend `historyContext`.** Keep response/error handling explicit; use bounded row errors; preserve existing PR3/PR4 behavior.
- [ ] **Step 8: Extend `loadImports()` to update both readiness labels from global booleans.** A false value says corresponding source is missing; do not claim freshness/compatibility/analytical readiness.
- [ ] **Step 9: Rerun GREEN and optional JS syntax.**

  ```bash
  python -m pytest tests/test_frontend_contract.py -q
  node --check frontend/assets/js/app.js
  ```

  If Node is unavailable in Codex Cloud, record `SKIP`; it is not an implementation blocker. GitHub Actions remains authoritative where configured.

- [ ] **Step 10: Hygiene + commit.**

  ```bash
  git diff --check
  git add frontend/index.html frontend/assets/js/app.js tests/test_frontend_contract.py
  git add frontend/assets/css/app.css 2>/dev/null || true
  git commit -m "feat: add PR5 query imports to Data UI"
  ```

  Before committing CSS, verify it actually changed; do not create a cosmetic-only diff.

---

### Task 13: Extend portable Windows acceptance and run the full PR5 verification gate

**Files:**

- Modify: `tests/windows_smoke.ps1`
- Verify all PR5-created/modified files from the File Map

**Interfaces — Consumes:** complete PR5 verticals.

**Produces:** authoritative implementation-complete evidence in Codex where runnable and post-push merge-gate evidence in GitHub Actions.

**Steps:**

- [ ] **Step 1: Write the PR5 Windows smoke probes before implementation change.** Add one seller synthetic import and one Query Metrics synthetic import after existing PR3/PR4 probes. Seller probe must persist at least one `product_query_snapshots` row and mark Product owned without manufacturing ProductSnapshot. Query Metrics probe must exercise synthetic `Left/Right` + false-dimension package quirks, persist at least one `query_metric_snapshots` row, and archive ORIGINAL bytes.
- [ ] **Step 2: Preserve PowerShell ASCII.** Use Python `\uXXXX`/`\N{...}` escapes for Russian workbook text inside embedded Python. Run:

  ```bash
  python -c "from pathlib import Path; b=Path('tests/windows_smoke.ps1').read_bytes(); bad=[(i,x) for i,x in enumerate(b) if x>=128]; print(bad[:20]); raise SystemExit(bool(bad))"
  ```

  Expected: `[]` and exit 0.

- [ ] **Step 3: Run focused PR5 suite.**

  ```bash
  python -m pytest \
    tests/test_ozon_seller_queries_parser.py \
    tests/test_ozon_query_metrics_parser.py \
    tests/test_product_query_snapshot_repository.py \
    tests/test_query_metric_snapshot_repository.py \
    tests/test_import_runtime.py \
    tests/test_lineage_repository.py \
    tests/test_ozon_seller_queries_import.py \
    tests/test_ozon_query_metrics_import.py \
    tests/test_ozon_seller_queries_api.py \
    tests/test_ozon_query_metrics_api.py \
    tests/test_product_repository.py \
    tests/test_frontend_contract.py -q
  ```

- [ ] **Step 4: Run full Python regression.**

  ```bash
  python -m pytest -q
  ```

  Require zero failed tests. Existing non-blocking dependency deprecation warnings may remain, but no new PR5 warning may hide an error.

- [ ] **Step 5: Compile Python.**

  ```bash
  python -m compileall -q backend launcher.py tests
  ```

- [ ] **Step 6: Optional JS syntax.**

  ```bash
  node --check frontend/assets/js/app.js
  ```

  Record `SKIP` only if Node is genuinely unavailable.

- [ ] **Step 7: Run diff/whitespace audit.**

  ```bash
  test -n "${PR5_BASE_SHA:-}"
  git rev-parse --verify "$PR5_BASE_SHA^{commit}"
  git diff --check "$PR5_BASE_SHA"..HEAD
  git diff --name-status "$PR5_BASE_SHA"..HEAD
  git diff --stat "$PR5_BASE_SHA"..HEAD
  ```

  Confirm every changed path belongs to the File Map and no protected dependency/runtime/spec/source-contract file changed.

- [ ] **Step 8: Run production SQL-boundary audit.**

  ```bash
  python -c "from pathlib import Path; roots=[Path('backend/application'),Path('backend/ingestion'),Path('backend/main.py')]; needles=('SELECT ','INSERT ','UPDATE ','DELETE ','CREATE TABLE','ALTER TABLE'); bad=[]; files=[]; [files.extend(r.rglob('*.py')) if r.is_dir() else files.append(r) for r in roots];
for p in files:
 t=p.read_text(encoding='utf-8');
 for n in needles:
  if n in t: bad.append((str(p),n));
print(bad); raise SystemExit(bool(bad))"
  ```

  If this simple textual audit flags a non-SQL user message/string, inspect it manually; production SQL itself must remain under persistence.

- [ ] **Step 9: Run dependency/scope audits.**

  ```bash
  test -n "${PR5_BASE_SHA:-}"
  git rev-parse --verify "$PR5_BASE_SHA^{commit}"
  git diff --exit-code "$PR5_BASE_SHA"..HEAD -- requirements.txt requirements-dev.txt .github/workflows/ci.yml launcher.py RUN_SERVER.cmd start.bat backend/config.py backend/persistence/connection.py
  git diff --name-only "$PR5_BASE_SHA"..HEAD | python -c "import sys; bad=[p.strip() for p in sys.stdin if p.strip().lower().endswith('.xlsx')]; print(bad); raise SystemExit(bool(bad))"
  ```

  Require no real XLSX tracked and no protected-file diff.

- [ ] **Step 10: Scan the implementation diff for accidental future-scope tokens and sensitive provenance.** Review any hits for `QueryOpportunity`, `RelevantQueryScope`, `BenchmarkSet`, `SearchPositionSnapshot`, MPStats, credentials, real evidence filenames/SHA/SKU/query lists. Documentation references are allowed only in existing canonical docs; production/tests must not embed real evidence identifiers.
- [ ] **Step 11: Run Windows smoke where available.** In Codex Cloud, execute only if PowerShell/Windows is actually available; otherwise record it as pending authoritative CI, not as a user desktop action. The authoritative command in GitHub Actions remains:

  ```powershell
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
  ```

  Require all existing PR1–PR4 scenarios plus the two PR5 probes to pass.

- [ ] **Step 12: Final local commit if Task 13 changed smoke only.**

  ```bash
  git diff --check
  git add tests/windows_smoke.ps1
  git commit -m "test: extend Windows smoke for PR5 query imports"
  ```

- [ ] **Step 13: Final implementation-complete report.** State exact targeted/full test counts, compile result, JS result or SKIP, ASCII audit, diff/scope audit, and Windows smoke status. Do not claim merge-ready.
- [ ] **Step 14: Post-push merge gate.** User pushes and opens the PR. Require GitHub Actions success on final PR HEAD, including Windows Python tests + JS syntax + full portable smoke, then independent review against both Source Contracts, the PR5 Implementation Spec, this Plan, AGENTS.md, and the final diff.

---

## Spec Coverage Matrix

| Frozen requirement | Implemented/verified by |
|---|---|
| Two isolated PR5 semantic verticals | Tasks 1, 5, 6, 9, 10 |
| Shared exact SearchQuery identity | Tasks 5, 6, 9, 10 |
| ProductQuerySnapshot exact grain/payload/revisions | Tasks 1, 2, 3, 9 |
| QueryMetricSnapshot exact grain/payload/revisions | Tasks 1, 2, 4, 10 |
| Seller `KNOWN` / `SOURCE_ZERO` only | Tasks 1, 3, 5 |
| Seller exact numeric bounds | Tasks 3, 5 |
| Seller observation-row structural boundary A:C/D:K | Task 5 |
| Seller positive ownership; no ProductSnapshot fabrication | Task 9; HTTP integration Task 11 |
| Query Metrics no Product/Cluster dependency | Tasks 4, 6, 10 |
| Query Metrics original artifact + transient read-copy | Tasks 6, 10 |
| Capitalized style compatibility | Tasks 1, 6, 10, 13 |
| False dimension ignored as coverage | Tasks 1, 6, 13 |
| Exact raw OOXML Decimal numeric source | Tasks 1, 4, 6 |
| Query Metrics canonical Decimal bounds | Tasks 4, 6 |
| Market CR distinct from own-product CR | Tasks 1, 3, 4, 5, 6 |
| Missing market coverage never zero-filled | Tasks 6, 10 |
| Import counter semantics incl. input + DB duplicates | Tasks 5, 6, 9, 10 |
| Shared mechanical staging only, no generic import framework | Task 7 |
| Archive reservation failure cleanup | Task 7 |
| Durable PR5 lineage context | Tasks 2, 8 |
| Unified four-kind history | Tasks 8, 11, 12 |
| Global source availability independent of pagination | Tasks 8, 11, 12 |
| Later FAILED does not reset availability | Tasks 8, 11 |
| Shared lock and compensation | Tasks 7, 9, 10, 11 |
| Startup recovery incl. stale read-copy | Tasks 9, 10, 11, 13 |
| Thin/sanitized FastAPI endpoints | Task 11 |
| Data page two new imports, no PR6+ UI | Task 12 |
| Synthetic fixture/no real report policy | Tasks 1, 5, 6, 13 |
| Windows portable acceptance | Task 13 |
| No new dependencies/npm/framework | Global Constraints + Task 13 audit |
| Executable `PR5_BASE_SHA` scope gate | Implementation Run Baseline + Task 13 |
| Full regression/compile/diff/independent review gates | Task 13 |

## Plan Self-Review Gate

Before using this plan for implementation, the plan author/reviewer must verify:

1. every Implementation Spec section 1–33 maps to at least one task or Global Constraint;
2. task interfaces are introduced before consumption;
3. seller and market conversions are never conflated;
4. Task 6 never mutates the original upload and never trusts stored dimension;
5. Task 8 availability is complete-history lineage state, not current-page UI inference;
6. Task 9 owns Product ownership semantics and Task 10 has no Product dependency;
7. no task introduces PR6+ entities/analytics;
8. no protected dependency/runtime file is in the implementation map;
9. no unresolved placeholder wording exists;
10. all shell variables referenced by verification commands are actually initialized or explicitly restored from recorded values;
11. implementation begins only after this plan is reviewed/merged.

A textual placeholder scan may construct tokens to avoid matching the scan command itself:

```bash
python -c "from pathlib import Path; p=Path('docs/superpowers/plans/2026-08-19-scoz-pr5-query-data-import.md'); t=p.read_text(encoding='utf-8'); bad=['T'+'BD','T'+'ODO','implement'+' later','fill in'+' details']; hits=[x for x in bad if x in t]; print(hits); raise SystemExit(bool(hits))"
```

## Execution Handoff

After this plan is merged, create/select the dedicated PR5 implementation branch from then-current `main` and execute Tasks 1–13 in order. Recommended execution is subagent-driven development with a fresh worker and review gate per task; executing-plans is acceptable when one agent owns the whole implementation but must preserve the same checkpoints.
