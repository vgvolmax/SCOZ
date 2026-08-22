# SCOZ PR6 Benchmark Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PR6 relevant-query selection, benchmark candidate/composition workflow, MPStats photo enrichment, and browser encrypted keystore exactly as frozen by the approved PR6 Implementation Spec.

**Architecture:** Persist user-curated relevance and immutable benchmark composition through application-owned SQLite transactions, with all SQL isolated in the PR6 repository and thin FastAPI routes. Derive candidates exclusively from current Ozon Search Visibility facts, keep MPStats photos and credentials transient, and perform portable credential encryption only with browser Web Crypto.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLite stdlib `sqlite3`, committed HTML/CSS/classic JavaScript, browser Web Crypto, `httpx==0.28.1`, pytest, Node built-in Web Crypto for contract tests.

**Spec:** `docs/superpowers/specs/2026-08-22-scoz-pr6-benchmark-selection-implementation-spec.md`

## Global Constraints

- Implement only PR6 composition/context: relevant queries, candidate selection, immutable benchmark revisions, transient MPStats thumbnails, and the v1 portable encrypted keystore. PR7 mathematics and later-source work are non-goals.
- Preserve ZIP → extract → `start.bat`, project-local Python, committed same-origin frontend, `127.0.0.1`, and no end-user Node/npm/build, Docker, PostgreSQL, accounts, background jobs, or generic source framework.
- Preserve layer direction: Source Adapter → Ingestion → Normalized Domain → Persistence/History → Analytics → Application → FastAPI → browser. Routes and UI contain no business rules; application contains no SQL; repositories contain no transaction lifecycle.
- `Product`, exact `SearchQuery` identity, and current immutable `ProductQuerySnapshot`/`SearchVisibilitySnapshot` revision semantics remain authoritative. Candidate evidence comes only from persisted Ozon facts; MPStats never creates candidates or facts.
- `immediate_transaction` is used only for relevance replacement, manual identity resolution/creation, and benchmark revision saves. Existing `transaction` stays unchanged for reads.
- Benchmark composition is a non-empty unordered Product set. Old revisions/members are immutable; exact same composition is `NO_CHANGE`; no metrics, photos, or future entities are stored.
- Credentials exist only in current-tab memory or the user-downloaded encrypted file. Tokens travel only in same-origin JSON POST bodies and outbound `X-Mpstats-TOKEN`; never URLs, storage APIs, SQLite, artifacts, HTML state, logs, responses, or errors.
- MPStats uses only the frozen official HTTPS `POST /api/analytics/v1/oz/items?ids=...` contract, consumes only `id`/`thumb`, makes no real-network test, and does not persist photo URLs.
- Framework transport failures retain standard FastAPI 422 `detail`; typed PR6 domain/source failures use `{"error":{"code":"...","message":"..."}}` and the frozen status/message matrix.
- Do not modify `.gitignore`, `backend/application/__init__.py`, prior migrations, source-fact contracts, or add future analytics files/tables.

## File Map

### Create
- `backend/domain/benchmark_selection.py` — frozen PR6 DTOs, enums, and typed failures.
- `backend/application/benchmark_selection.py` — owned-product checks, transaction selection, identity/source orchestration.
- `backend/sources/__init__.py` — source package marker only.
- `backend/sources/mpstats.py` — official MPStats Ozon thumbnail adapter.
- `backend/persistence/repositories/benchmark_selection.py` — all relevance, candidate, and benchmark SQL.
- `backend/persistence/migrations/migration_005_benchmark_selection.py` — four PR6 tables and three indexes.
- `frontend/assets/js/keystore.js` — frozen browser/Node Web Crypto v1 contract.
- `tests/test_benchmark_selection_repository.py` — repository temporal, set, history, and concurrency contract.
- `tests/test_benchmark_selection_api.py` — real TestClient service/API/error/catalog contract.
- `tests/test_mpstats_source.py` — `httpx.MockTransport` request/response/error contract.
- `tests/keystore_contract.mjs` — dependency-free Node Web Crypto contract.

### Modify
- `backend/domain/__init__.py` — export PR6 symbols alongside current exports (current lines 1–29).
- `backend/persistence/repositories/__init__.py` — export `BenchmarkSelectionRepository` (current lines 1–4).
- `backend/persistence/repositories/products.py` — tighten canonical Ozon identity validation in `resolve_or_create_ozon_product` while preserving its return type (current lines 24–54) and catalog query (lines 91–154).
- `backend/persistence/connection.py` — add `immediate_transaction` after existing `transaction` without altering lines 20–33.
- `backend/persistence/migrations/runner.py` — append registry entry 005 at current lines 6–15.
- `backend/main.py` — add imports/models/service wiring near lines 1–32 and thin PR6 routes after current routes at lines 72–164.
- `frontend/index.html` — extend Products/Settings views at current lines 25–35 and load `keystore.js` before `app.js` at line 38.
- `frontend/assets/js/app.js` — extend the current IIFE, product rendering, and bindings at lines 1–20.
- `frontend/assets/css/app.css` — append token-based PR6 workspace/source states after current lines 33–40.
- `requirements.txt` — add runtime `httpx==0.28.1` to current lines 1–4.
- `requirements-dev.txt` — remove inherited duplicate `httpx==0.28.1` from current lines 1–3.
- `.github/workflows/ci.yml` — extend current Python/Node checks at lines 14–29 without npm.
- `tests/test_migrations.py` — extend current migration registry/schema/upgrade tests at lines 1–235.
- `tests/test_database.py` — add immediate commit/rollback/close/locking tests after current lines 1–126.
- `tests/test_product_repository.py` — extend identity validation/catalog tests at current lines 1–207.
- `tests/test_frontend_contract.py` — extend committed-markup/script/security assertions at current lines 1–112.
- `tests/windows_smoke.ps1` — append local PR6 probes while preserving current startup scenarios at lines 1–180.

## Execution Start Gate

Implementation MUST start from fresh `main` after this plan has been merged. Before Task 1 run:

```bash
git status --short
git rev-parse HEAD
```

The worktree must be clean, and HEAD must be the then-current `main` containing both the approved PR6 Implementation Spec and this approved PR6 Implementation Plan. Record that post-merge SHA as the implementation base; do not use the pre-plan authoring SHA.

### Task 1: Add SQLite Immediate Transactions

**Files:**
- Modify: `backend/persistence/connection.py:20-33`
- Test: `tests/test_database.py:1-126`

**Interfaces:**
- Consumes: existing `connect(db_path)` and unchanged `transaction(db_path)`.
- Produces: `immediate_transaction(db_path: Path | None = None) -> Iterator[sqlite3.Connection]`.

- [ ] Add `test_immediate_transaction_commits_and_closes`, `test_immediate_transaction_rolls_back_and_closes`, `test_transaction_retains_deferred_behavior`, and `test_immediate_transaction_exposes_locked_timeout`. Use a real temporary SQLite file, monkeypatch/wrapped `connect` to observe `close`, two connections for the lock case, and assert committed row visibility, absent rolled-back row, closed-connection `ProgrammingError`, normal helper regression, and SQLite `SQLITE_BUSY`/`SQLITE_LOCKED` foundation.
- [ ] Run `python -m pytest tests/test_database.py -q`. Expected before implementation: FAIL because `immediate_transaction` cannot be imported. Expected after implementation: PASS.
- [ ] Implement exactly:
  ```python
  @contextmanager
  def immediate_transaction(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
      connection = connect(db_path)
      try:
          connection.execute("BEGIN IMMEDIATE")
          yield connection
          connection.commit()
      except Exception:
          connection.rollback()
          raise
      finally:
          connection.close()
  ```
  Do not edit `transaction` or add business SQL/retry behavior.
- [ ] Run regression `python -m pytest tests/test_database.py tests/test_migrations.py -q`; expect PASS.
- [ ] Commit with `git add backend/persistence/connection.py tests/test_database.py && git commit -m "feat(PR6): add immediate SQLite transactions"`.

### Task 2: Establish the Frozen Domain Contract

**Files:**
- Create: `backend/domain/benchmark_selection.py`
- Modify: `backend/domain/__init__.py:1-29`
- Test: `tests/test_benchmark_selection_repository.py`

**Interfaces:**
- Consumes: `date`, `datetime`, `Decimal`, `Enum`, `Literal`.
- Produces: every type used by Tasks 4–10.

- [ ] Create `test_pr6_domain_types_are_frozen_and_enum_values_are_exact`; construct each DTO, assert mutation raises `FrozenInstanceError`, and assert exact enum values. Run `python -m pytest tests/test_benchmark_selection_repository.py::test_pr6_domain_types_are_frozen_and_enum_values_are_exact -q`; expected FAIL because the module is absent.
- [ ] Add the spec-exact enums/dataclasses: `RelevantQueryReadiness`, `SourcePeriod`, `RelevantQueryOption`, `RelevantQuerySelection`, `RelevantQueryWriteResult`, `PhotoStatus`, `CandidateReadiness`, `BenchmarkCandidate`, `CandidatePage`, `ManualCandidateWriteResult`, `BenchmarkSet`, `BenchmarkMember`, `BenchmarkSetRevision`, `BenchmarkComposition`, `BenchmarkWriteKind`, `BenchmarkCompositionWriteResult`, `MPStatsProductPreview`, `MPStatsConnectionStatus`, and `MPStatsConnectionResult`. Preserve all field names/types/order from spec sections 5–8 and 11; use `@dataclass(frozen=True)` and `origin: Literal["SEARCH_VISIBILITY", "MANUAL"]`.
- [ ] Add typed `MPStatsAuthError`, `MPStatsRateLimitError(retry_after_seconds: int | None)`, `MPStatsPendingError`, `MPStatsTimeoutError`, `MPStatsNetworkError`, `MPStatsMalformedResponseError`, and `MPStatsUpstreamError`; expose the frozen local error codes through focused domain exceptions without embedding HTTP.
- [ ] Export the symbols through `backend/domain/__init__.py`; add no SQL, HTTP, Pydantic, or mutation logic.
- [ ] Re-run the focused test, then `python -m pytest tests/test_observation_revision_convention.py tests/test_product_query_snapshot_repository.py tests/test_search_visibility_snapshot_repository.py -q`; expect PASS.
- [ ] Commit with `git add backend/domain/benchmark_selection.py backend/domain/__init__.py tests/test_benchmark_selection_repository.py && git commit -m "feat(PR6): add benchmark selection domain"`.

### Task 3: Apply Migration 005

**Files:**
- Create: `backend/persistence/migrations/migration_005_benchmark_selection.py`
- Modify: `backend/persistence/migrations/runner.py:6-15`
- Test: `tests/test_migrations.py:1-235`

**Interfaces:**
- Consumes: contiguous migration runner contract and v1–v4 schema.
- Produces: `product_relevant_queries`, `benchmark_sets`, `benchmark_set_revisions`, `benchmark_members` and three named indexes.

- [ ] Add `test_fresh_database_applies_migrations_one_through_five`, `test_migration_005_upgrades_populated_v4_without_changing_rows`, and `test_migration_005_schema_is_exact`. Seed representative Product/identity/query/snapshot/revision rows at v4; assert values survive byte-for-byte, `PRAGMA table_info`, `foreign_key_list`, `index_list/index_info`, CHECK/UNIQUE/PK/delete actions, exactly four new tables, exactly three named indexes, and schema version 5.
- [ ] Run `python -m pytest tests/test_migrations.py -q`; expected FAIL because registry version 5 and schema objects are absent.
- [ ] Implement `upgrade(connection)` executing the spec section 4 DDL verbatim: composite relevance PK with CASCADE/RESTRICT, stable set unique by own product, positive unique revision, member composite PK, and indexes `idx_product_relevant_queries_query_product`, `idx_benchmark_set_revisions_current`, `idx_benchmark_members_product_revision`.
- [ ] Append only `(5, "benchmark_selection", "backend.persistence.migrations.migration_005_benchmark_selection")` to `MIGRATIONS`; do not modify migrations 001–004 or create future tables.
- [ ] Re-run focused tests, then `python -m pytest tests/test_migrations.py tests/test_database.py tests/test_observation_revision_convention.py -q`; expect PASS.
- [ ] Commit with `git add backend/persistence/migrations/migration_005_benchmark_selection.py backend/persistence/migrations/runner.py tests/test_migrations.py && git commit -m "feat(PR6): add benchmark selection schema"`.

### Task 4: Persist Relevant Query Selection

**Files:**
- Create: `backend/persistence/repositories/benchmark_selection.py`
- Modify: `backend/persistence/repositories/__init__.py:1-4`
- Test: `tests/test_benchmark_selection_repository.py`

**Interfaces:**
- Consumes: open SQLite connection, migration 005, current ProductQuery revisions, Task 2 DTOs.
- Produces: `list_relevant_query_options(product_id: int) -> RelevantQuerySelection`, `list_selected_query_ids(product_id: int) -> frozenset[int]`, `replace_relevant_queries(product_id: int, search_query_ids: frozenset[int]) -> RelevantQueryWriteResult`.

- [ ] Add exact tests `test_relevant_options_choose_latest_coherent_period_and_current_revisions`, `test_stale_selected_query_uses_latest_historical_evidence`, `test_relevant_option_order_is_deterministic`, `test_replace_relevant_queries_retains_timestamp_and_stamps_new_rows_once`, `test_replace_relevant_queries_empty_clear_and_no_change`, and `test_replace_relevant_queries_rejects_missing_or_other_product_evidence_atomically`. Fixtures must include tied end dates, superseded revisions, exact case/spacing-distinct queries, stale selection, retained/new timestamps, and an invalid mixed set; assert readiness/count/metrics/order and unchanged old rows after error.
- [ ] Run `python -m pytest tests/test_benchmark_selection_repository.py -k 'relevant' -q`; expected FAIL because repository/methods are absent.
- [ ] Implement current evidence with CTE shape:
  ```sql
  WITH current_pqs AS (
    SELECT p.* FROM product_query_snapshots p
    WHERE p.product_id=? AND p.revision=(SELECT MAX(x.revision) FROM product_query_snapshots x
      WHERE x.product_id=p.product_id AND x.search_query_id=p.search_query_id
        AND x.period_start=p.period_start AND x.period_end=p.period_end)
  ), latest_period AS (
    SELECT period_start,period_end FROM current_pqs ORDER BY period_end DESC,period_start DESC LIMIT 1
  )
  ```
  Union latest-period rows with selected IDs having same-product historical evidence; rank stale evidence by `period_end DESC, period_start DESC, revision DESC`; order using `selected DESC, in_latest_period DESC, searched_users IS NULL, searched_users DESC, query_text, search_query_id`.
- [ ] In `replace_relevant_queries`, validate the entire positive-ID set by joining `search_queries` and same-product `product_query_snapshots`, reject on count mismatch/no own data, compute one UTC timestamp, delete absent rows, `INSERT` only new rows, retain existing timestamps, and derive `changed` from before/after sets. Issue no transaction-control statements.
- [ ] Export the repository. Re-run focused tests, then `python -m pytest tests/test_product_query_snapshot_repository.py tests/test_search_dimensions_repository.py -q`; expect PASS.
- [ ] Commit with `git add backend/persistence/repositories/benchmark_selection.py backend/persistence/repositories/__init__.py tests/test_benchmark_selection_repository.py && git commit -m "feat(PR6): add relevant query persistence"`.

### Task 5: Derive and Page Benchmark Candidates

**Files:**
- Modify: `backend/persistence/repositories/benchmark_selection.py`
- Test: `tests/test_benchmark_selection_repository.py`

**Interfaces:**
- Consumes: persisted selected queries, current Search Visibility revisions, canonical Ozon identities, current benchmark membership.
- Produces: `list_candidates(product_id: int, *, limit: int, offset: int) -> CandidatePage`.

- [ ] Add `test_candidates_use_only_selected_queries_and_latest_query_cluster_time`, `test_candidates_use_current_revision_and_dedupe_counts`, `test_candidate_representative_tie_break_and_order`, `test_candidates_exclude_only_active_own_product_and_flag_current_members`, and `test_candidate_readiness_uses_unpaginated_total`. Seed older timestamps, corrected revisions, two queries/clusters, duplicate Product appearances, representative ties, another owned Product, current revision membership, and an out-of-range page; assert all frozen counts/fields/order/total/readiness.
- [ ] Run `python -m pytest tests/test_benchmark_selection_repository.py -k 'candidate' -q`; expected FAIL because `list_candidates` is absent.
- [ ] Implement essential SQL CTE chain `selected_queries → latest_query_cluster(MAX(observed_at)) → current_rows(MAX(revision) per logical key) → contributing(exclude own) → aggregate(COUNT DISTINCT query/cluster, MIN position) → representative(ROW_NUMBER OVER PARTITION BY product ORDER BY position, observed_at DESC, search_query_id, cluster_id, snapshot id DESC)`. Join exactly one canonical Ozon external identity and current benchmark members; order by best position, matched query count DESC, `CAST(ozon_product_id AS INTEGER)`, Product ID, then apply limit/offset.
- [ ] Return local candidates with `NOT_REQUESTED`, null photo URL, `SEARCH_VISIBILITY`; compute `total` before pagination and readiness solely from total. Empty persisted relevance raises `RELEVANT_QUERY_SELECTION_EMPTY`; no facts returns 200 DTO state.
- [ ] Re-run focused tests, then `python -m pytest tests/test_search_visibility_snapshot_repository.py tests/test_benchmark_selection_repository.py -q`; expect PASS.
- [ ] Commit with `git add backend/persistence/repositories/benchmark_selection.py tests/test_benchmark_selection_repository.py && git commit -m "feat(PR6): derive benchmark candidates"`.

### Task 6: Persist Immutable Benchmark Revisions

**Files:**
- Modify: `backend/persistence/repositories/benchmark_selection.py`
- Test: `tests/test_benchmark_selection_repository.py`

**Interfaces:**
- Consumes: an already-open transaction connection and validated Product/member identities.
- Produces: `get_benchmark(own_product_id: int) -> BenchmarkComposition`, `save_benchmark(own_product_id: int, member_product_ids: frozenset[int]) -> BenchmarkCompositionWriteResult`.

- [ ] Add `test_first_benchmark_save_creates_revision_one`, `test_same_member_set_is_no_change`, `test_changed_set_creates_next_immutable_revision`, `test_benchmark_rejects_empty_invalid_and_active_own_atomically`, `test_another_owned_product_is_valid_member`, `test_benchmark_failure_rolls_back_complete_revision`, and `test_competing_immediate_writers_serialize_revision_allocation`. Assert stable set, numeric Ozon member order, no row on invalid/empty, unchanged old rows, no metric/photo columns, same-set second writer `NO_CHANGE`, different-set next revision.
- [ ] Run `python -m pytest tests/test_benchmark_selection_repository.py -k 'benchmark' -q`; expected FAIL because methods are absent.
- [ ] Implement `get_benchmark` by stable set lookup, current `ORDER BY revision DESC LIMIT 1`, and member join/order. Implement `save_benchmark` as validation/count query followed by `INSERT benchmark_sets ... ON CONFLICT DO NOTHING`, current-set comparison, early `NO_CHANGE`, next revision insert, then all member inserts. Do not issue BEGIN/commit/rollback or retry/reopen.
- [ ] Re-run focused tests, then `python -m pytest tests/test_benchmark_selection_repository.py tests/test_database.py -q`; expect PASS.
- [ ] Commit with `git add backend/persistence/repositories/benchmark_selection.py tests/test_benchmark_selection_repository.py && git commit -m "feat(PR6): add benchmark revision persistence"`.

### Task 7: Harden Manual Ozon Product Identity

**Files:**
- Modify: `backend/persistence/repositories/products.py:24-54,91-154`
- Test: `tests/test_product_repository.py:1-207`

**Interfaces:**
- Consumes: `source="ozon"`, `identity_type="ozon_product_id"`, empty account scope.
- Produces: unchanged `resolve_or_create_ozon_product(...) -> Product` with canonical positive decimal validation.

- [ ] Add `test_resolver_rejects_zero_leading_zero_and_nondigit_ozon_ids`, `test_resolver_reuses_existing_canonical_identity`, and `test_identity_only_product_is_not_in_catalog_projection`. Assert rejection of `"0"`, `"01"`, signs/whitespace/non-digits; exact reuse; new Product has no snapshot and is absent from catalog.
- [ ] Run `python -m pytest tests/test_product_repository.py -k 'resolver or identity_only' -q`; expected FAIL because current resolver accepts at least one prohibited representation.
- [ ] At the sole resolver boundary enforce `value.isascii() and value.isdigit() and int(value) > 0 and str(int(value)) == value`; keep the current method name, parameters, `Product` return, identity uniqueness, ownership behavior, and catalog projection unchanged. Do not add a resolver.
- [ ] Re-run focused tests, then `python -m pytest tests/test_product_repository.py tests/test_ozon_products_api.py tests/test_ozon_search_visibility_import.py -q`; expect PASS.
- [ ] Commit with `git add backend/persistence/repositories/products.py tests/test_product_repository.py && git commit -m "feat(PR6): harden manual Ozon product identity"`.

### Task 8: Orchestrate Benchmark Selection in the Application

**Files:**
- Create: `backend/application/benchmark_selection.py`
- Test: `tests/test_benchmark_selection_api.py`

**Interfaces:**
- Consumes: database path, connection helpers, `ProductRepository`, `BenchmarkSelectionRepository`, `MPStatsClient`.
- Produces: the eight spec-exact `BenchmarkSelectionService` methods.

- [ ] Add service-focused tests `test_service_rejects_missing_and_non_owned_products`, `test_service_uses_immediate_boundaries_for_all_three_writes`, `test_manual_add_checks_relevance_before_identity_mutation`, `test_benchmark_history_survives_relevance_clear_restore`, and `test_only_busy_locked_maps_to_concurrent_write`. The lifecycle test must save relevance → revision 1 → clear → read same history → prove candidate/manual/save blocked and no identity/revision created → restore → same unordered composition returns revision 1 `NO_CHANGE`.
- [ ] Run `python -m pytest tests/test_benchmark_selection_api.py -k 'service' -q`; expected FAIL because service is absent.
- [ ] Implement exact signatures:
  ```python
  get_relevant_queries(product_id: int) -> RelevantQuerySelection
  replace_relevant_queries(product_id: int, search_query_ids: tuple[int, ...]) -> RelevantQueryWriteResult
  get_candidates(product_id: int, *, limit: int, offset: int) -> CandidatePage
  add_manual_candidate(product_id: int, ozon_product_id: str) -> ManualCandidateWriteResult
  get_benchmark(product_id: int) -> BenchmarkComposition
  save_benchmark(product_id: int, member_product_ids: tuple[int, ...]) -> BenchmarkCompositionWriteResult
  enrich_mpstats_previews(token: SecretStr, ozon_product_ids: tuple[str, ...]) -> tuple[MPStatsProductPreview, ...]
  test_mpstats(token: SecretStr, ozon_product_id: str) -> MPStatsConnectionResult
  ```
- [ ] Centralize owned Product lookup using repositories. Use normal `transaction` for reads, `immediate_transaction` for relevance/manual/benchmark writes; check non-empty relevance before manual identity mutation and benchmark save; within manual transaction find identity first then call the unchanged resolver only when absent. Build manual DTO with null context/zero counts/`MANUAL`.
- [ ] Catch only SQLite errors whose code is `SQLITE_BUSY` or `SQLITE_LOCKED` around benchmark immediate acquisition/body and map them to `BENCHMARK_CONCURRENT_WRITE`; propagate unrelated operational failures. Add no raw SQL.
- [ ] Re-run focused tests, then `python -m pytest tests/test_benchmark_selection_api.py tests/test_benchmark_selection_repository.py tests/test_product_repository.py -q`; expect PASS.
- [ ] Commit with `git add backend/application/benchmark_selection.py tests/test_benchmark_selection_api.py && git commit -m "feat(PR6): add benchmark selection service"`.

### Task 9: Add the MPStats Photo Adapter and Runtime Dependency

**Files:**
- Create: `backend/sources/__init__.py`
- Create: `backend/sources/mpstats.py`
- Create: `tests/test_mpstats_source.py`
- Modify: `requirements.txt:1-4`
- Modify: `requirements-dev.txt:1-3`

**Interfaces:**
- Consumes: `SecretStr`, injected `httpx.Client`, canonical unique Ozon IDs.
- Produces: `MPStatsClient(client, *, base_url="https://mpstats.io", timeout=httpx.Timeout(15.0, connect=5.0))`, `get_ozon_product_previews(...)`, connection probe DTO/errors.

- [ ] Write MockTransport tests named `test_mpstats_request_contract_and_ignored_fields`, `test_mpstats_chunks_at_100_and_preserves_caller_order`, `test_mpstats_empty_ids_make_no_request`, `test_mpstats_missing_thumb_and_id_are_missing`, `test_mpstats_rejects_malformed_response_shapes`, `test_mpstats_maps_every_http_status`, `test_mpstats_maps_timeout_and_network_errors`, and `test_mpstats_probe_accepts_valid_empty_data`. Assert POST/HTTPS/host/path, decoded one `ids=123,456`, empty body, only `X-Mpstats-TOKEN`, no redirects/retry/auth-token, ignored sentinel commercial fields, canonical numeric response IDs, safe `Retry-After` range, and exact typed mapping.
- [ ] Run `python -m pytest tests/test_mpstats_source.py -q`; expected FAIL because source package/client is absent.
- [ ] Implement sequential `ids[index:index+100]` requests with `params={"ids": ",".join(chunk)}`, header `X-Mpstats-TOKEN`, no content/body, frozen timeout, and `follow_redirects=False`. Validate root/data/item types, positive non-bool integer ID, unique requested response IDs, string null/empty/approved absolute HTTPS thumb, ignore unrequested IDs, and reconstruct caller order.
- [ ] Map 202/pending, 401/auth, 429/rate with integer 0–86400, every other non-200/upstream, `httpx.TimeoutException`, other `RequestError`, invalid JSON/schema exactly as spec. Probe delegates to one preview request and returns `AVAILABLE` on any valid 200.
- [ ] Move the exact `httpx==0.28.1` pin into runtime requirements and remove only its inherited dev duplicate. Run `python -m pytest tests/test_mpstats_source.py tests/test_runtime_contract.py -q`; expect PASS.
- [ ] Commit with `git add backend/sources requirements.txt requirements-dev.txt tests/test_mpstats_source.py && git commit -m "feat(PR6): add MPStats photo source"`.

### Task 10: Expose Thin PR6 FastAPI Endpoints

**Files:**
- Modify: `backend/main.py:1-32,72-164`
- Modify: `tests/test_benchmark_selection_api.py`

**Interfaces:**
- Consumes: all service methods and typed domain/source failures.
- Produces: eight exact REST endpoints from spec section 12.

- [ ] Add real TestClient tests `test_relevant_query_get_put_contract`, `test_candidate_get_and_manual_post_contract`, `test_benchmark_get_post_and_no_change_statuses`, `test_mpstats_test_and_preview_contract`, `test_transport_422_detail_is_distinct_from_domain_envelope`, `test_all_pr6_error_codes_and_retry_after_mapping`, `test_secret_sentinel_absent_from_response_database_and_logs`, and `test_manual_identity_and_membership_do_not_enter_products_catalog`. Cover path/query bounds, strict JSON IDs, maxima 10,000/1,000/500, duplicate semantics, 200/201 choices, decimal/datetime strings, and every frozen source message.
- [ ] Run `python -m pytest tests/test_benchmark_selection_api.py -q`; expected FAIL with route 404/model absence.
- [ ] Add Pydantic request models with strict positive integer collections and uniqueness/size constraints: `RelevantQueriesRequest(search_query_ids)`, `ManualCandidateRequest(ozon_product_id)`, `BenchmarkRevisionRequest(member_product_ids)`, `MPStatsTestRequest(token: SecretStr, ozon_product_id)`, `MPStatsPreviewsRequest(token: SecretStr, ozon_product_ids)`. Token length is 1–4096 with no transformation; canonical SKU domain errors remain the SCOZ envelope.
- [ ] Add thin route skeletons for `GET/PUT /api/products/{product_id}/relevant-queries`, `GET /benchmark-candidates`, `POST /benchmark-candidates/manual`, `GET /benchmark`, `POST /benchmark/revisions`, `POST /api/sources/mpstats/test`, and `POST /api/sources/mpstats/ozon-product-previews`. Each route only calls the exact service method, serializes dataclasses, selects frozen status, and delegates typed mapping; do not add a global validation handler.
- [ ] Map local/source errors to exact section 12–13 status/code/Russian message envelope. Emit local `Retry-After` and JSON `retry_after_seconds` only for safely parsed rate limits; never forward body/header/token/exception text.
- [ ] Run focused tests, then `python -m pytest tests/test_backend.py tests/test_ozon_products_api.py tests/test_ozon_query_metrics_api.py tests/test_ozon_search_visibility_api.py tests/test_benchmark_selection_api.py -q`; expect PASS.
- [ ] Commit with `git add backend/main.py tests/test_benchmark_selection_api.py && git commit -m "feat(PR6): add benchmark selection API"`.

### Task 11: Implement the Browser Encrypted Keystore

**Files:**
- Create: `frontend/assets/js/keystore.js`
- Create: `tests/keystore_contract.mjs`
- Modify: `frontend/index.html:38`

**Interfaces:**
- Consumes: `globalThis.crypto`, `TextEncoder`, `TextDecoder`, `atob`, `btoa`.
- Produces: frozen `globalThis.ScozKeystore` with five exact functions.

- [ ] Write Node tests for `test roundtrip preserves UTF-8 token`, `wrong password and corruption collapse to KEYSTORE_DECRYPT_FAILED`, `independent encryptions randomize salt IV ciphertext`, `envelope is exact and canonical`, `serialized envelope contains no plaintext sentinel`, and `format version field base64 length and payload validation are exact`. Use Node built-in Web Crypto only.
- [ ] Run `node tests/keystore_contract.mjs`; expected FAIL because `keystore.js`/global is absent.
- [ ] Implement password import/derivation/encryption skeleton:
  ```javascript
  const material=await crypto.subtle.importKey("raw",enc.encode(password),"PBKDF2",false,["deriveKey"]);
  const key=await crypto.subtle.deriveKey({name:"PBKDF2",hash:"SHA-256",iterations:600000,salt},material,{name:"AES-GCM",length:256},false,["encrypt","decrypt"]);
  const ciphertext=await crypto.subtle.encrypt({name:"AES-GCM",iv,tagLength:128},key,plaintext);
  ```
  Generate 16-byte salt/12-byte IV per save; payload is exact insertion-ordered `{"version":1,"sources":{"mpstats":{"token":...}}}`; use padded canonical RFC4648 base64.
- [ ] Validate exact nested key sets/algorithms/numbers/base64/lengths/ciphertext ≥17 before derivation; distinguish `UNSUPPORTED_KEYSTORE_FORMAT`, `UNSUPPORTED_KEYSTORE_VERSION`, `INVALID_KEYSTORE_ENVELOPE`, and collapse auth/UTF-8/JSON/payload failure to `KEYSTORE_DECRYPT_FAILED`. Password is exact, non-empty, untrimmed, unnormalized.
- [ ] Freeze and expose `encryptMpstatsCredentials`, `decryptMpstatsCredentials`, `serializeEnvelope`, `parseEnvelope`, `downloadEnvelope`; download exact `scoz_credentials.enc.json` through a temporary UTF-8 JSON Blob/object URL and cleanup. Load script before deferred `app.js`.
- [ ] Run `node --check frontend/assets/js/keystore.js && node tests/keystore_contract.mjs`, then `python -m pytest tests/test_frontend_contract.py -q`; expect PASS.
- [ ] Commit with `git add frontend/assets/js/keystore.js frontend/index.html tests/keystore_contract.mjs && git commit -m "feat(PR6): add encrypted credential keystore"`.

### Task 12: Build Relevant Query and Competitor Selection UI

**Files:**
- Modify: `frontend/index.html:25-35`
- Modify: `frontend/assets/js/app.js:1-20`
- Modify: `frontend/assets/css/app.css:33-40`
- Modify: `tests/test_frontend_contract.py:1-112`

**Interfaces:**
- Consumes: Products catalog and six local relevance/candidate/benchmark endpoints; `NOT_REQUESTED` photo state.
- Produces: in-page owned-Product Competitors workspace with saved selection/revision UI.

- [ ] Add contract tests `test_only_owned_products_expose_competitor_entry`, `test_competitor_workspace_has_active_context_and_relevance_states`, `test_candidate_and_selected_panels_have_exact_controls`, `test_stale_no_evidence_error_and_revision_feedback_are_renderable`, and `test_frontend_uses_committed_classic_assets_without_framework`. Assert stable IDs, Russian labels, aria-live/busy/disabled hooks, placeholder, pagination/manual/save controls, no score/PR7 screen.
- [ ] Run `python -m pytest tests/test_frontend_contract.py -q`; expected FAIL because PR6 markup/wiring is absent.
- [ ] Extend product cards with `Выбрать конкурентов` only when `is_owned`; open a view that retains active Product title/Ozon ID. Fetch relevance; render latest period and exact metric columns, selected count, stale `Нет в свежем периоде`, loading skeleton, `NO_OWN_QUERY_DATA` Data link, zero-selection prompt, preserved rows on error, and PUT save/no-change feedback.
- [ ] Gate competitor controls on persisted non-empty relevance. Fetch benchmark and paged candidates; maintain selected Product IDs as an unordered UI set; render 65–70/30–35 candidate/selected columns, contextual fields/counts/time, placeholders, current flags, manual canonical SKU add, removals, empty validation, revision created/changed/`Состав не изменился — revision N` feedback.
- [ ] Use existing visual tokens/cards/controls/chips/focus styles and stable known layouts; photo failure only changes placeholder. Add no global navigation, framework/build/npm, business scoring, credentials UI, or MPStats commercial fields.
- [ ] Run `node --check frontend/assets/js/app.js && python -m pytest tests/test_frontend_contract.py tests/test_ozon_products_api.py -q`; expect PASS.
- [ ] Commit with `git add frontend/index.html frontend/assets/js/app.js frontend/assets/css/app.css tests/test_frontend_contract.py && git commit -m "feat(PR6): add competitor selection UI"`.

### Task 13: Integrate Settings, Transient Credentials, and MPStats Photos

**Files:**
- Modify: `frontend/index.html:35-38`
- Modify: `frontend/assets/js/app.js:1-20`
- Modify: `frontend/assets/css/app.css:33-40`
- Modify: `tests/test_frontend_contract.py:1-112`

**Interfaces:**
- Consumes: `ScozKeystore`, MPStats test/preview endpoints, loaded candidates/catalog.
- Produces: memory-only `credentialState = { mpstats: { token } } | null`, Settings → Sources card, transient previews and Lock.

- [ ] Add `test_settings_source_controls_and_memory_only_state`, `test_credentials_never_use_browser_persistence_or_urls`, `test_unlock_failure_preserves_old_state_and_clears_password`, `test_save_requires_matching_confirmation`, and `test_lock_clears_credentials_inputs_status_and_preview_urls`. Assert absence of `localStorage`, `sessionStorage`, `indexedDB`, `document.cookie`, token query construction, backend keystore endpoints, and visible token rendering.
- [ ] Run `python -m pytest tests/test_frontend_contract.py -q`; expected FAIL because Settings and credential state are absent.
- [ ] Replace Settings empty state with password token, numeric probe, test, status, encrypted save, file/open, password, save-only confirmation, and Lock controls. Prefill probe from numerically smallest catalog Ozon ID; use busy/aria-live and frozen source messages.
- [ ] Manual entry validates non-empty token then copies it into `credentialState`. Test/photo POST the token only in same-origin JSON body. Preview results update only photo state/URL in request order; source/image failures preserve candidate identities, selection, and local cards.
- [ ] Open reads one local file, parses/decrypts, replaces state only after full success, clears password/file inputs, never displays token; failure preserves old state. Save requires memory token and exact password confirmation, downloads through keystore, clears passwords but keeps state. Lock nulls state; clears token/password/confirmation/file/probe-dependent transient statuses and all preview URLs/card photo state.
- [ ] Run `node --check frontend/assets/js/app.js && node --check frontend/assets/js/keystore.js && node tests/keystore_contract.mjs && python -m pytest tests/test_frontend_contract.py -q`; expect PASS.
- [ ] Commit with `git add frontend/index.html frontend/assets/js/app.js frontend/assets/css/app.css tests/test_frontend_contract.py && git commit -m "feat(PR6): add MPStats source settings"`.

### Task 14: Complete CI and Portable Windows Integration

**Files:**
- Modify: `.github/workflows/ci.yml:14-29`
- Modify: `tests/windows_smoke.ps1:1-180`
- Test: `tests/test_frontend_contract.py`

**Interfaces:**
- Consumes: complete PR6 backend, committed frontend, Node keystore contract, existing portable launcher.
- Produces: authoritative Linux/Python/Node checks and Windows Full local-only smoke coverage.

- [ ] Add a failing contract assertion `test_ci_runs_both_js_checks_and_keystore_contract_without_npm`; assert exact commands. Extend Windows Full smoke with migration 005 health, served `keystore.js`, local relevant-query/benchmark state/error probes using synthetic SQLite/local TestClient-compatible data, and UI markers; retain every existing scenario and make no MPStats network request.
- [ ] Run `python -m pytest tests/test_frontend_contract.py -q`; expected before CI edit: FAIL because new CI commands are absent. Update CI to run `python -m pytest -q`, both `node --check` commands, `node tests/keystore_contract.mjs`, and existing Windows `-Mode Full`, with no npm.
- [ ] Run the fresh full verification gate:
  ```bash
  python -m pytest -q
  node --check frontend/assets/js/app.js
  node --check frontend/assets/js/keystore.js
  node tests/keystore_contract.mjs
  powershell.exe \
    -NoLogo \
    -NoProfile \
    -ExecutionPolicy Bypass \
    -File tests\\windows_smoke.ps1 \
    -Mode Full
  rg -n "localStorage|sessionStorage|indexedDB|document\\.cookie|auth-token|token=.*fetch|scoz_credentials" frontend backend tests --glob '!tests/keystore_contract.mjs'
  git diff --check
  git status --short
  ```
  Expected: all behavioral/syntax/smoke checks PASS; grep output contains only explicit prohibitions, safe filename/UI wiring, or test assertions and is manually classified line-by-line—never credential persistence or URL construction. The grep supplements rather than replaces tests.
- [ ] Review all 23 spec sections: migration, query universe/stale/current revisions, candidate time/dedupe/readiness/ties, manual/catalog, stable set/immutable/NO_CHANGE/clear-restore/concurrency, MPStats request/status/probe/dependency, exact REST/error split, crypto/transience/Lock/UI states, CI/Windows, and PR7 handoff. Confirm class fields/signatures/JSON keys/error codes match Tasks 2/4/8/10 and no PR7 scope exists.
- [ ] Commit with `git add .github/workflows/ci.yml tests/windows_smoke.ps1 tests/test_frontend_contract.py && git commit -m "test(PR6): complete portable integration"`.

## Completion and Handoff

After Task 14, inspect `git log --oneline` for exactly one reviewable commit per task and confirm the worktree is clean. PR6 output at this boundary is curated relevance, deterministic candidate evidence, immutable composition revision, and optional transient thumbnails only. PR7 receives a specific revision and compatible source facts; median, P25/P75, sample, delta, status, confidence, advertising intensity, Search Position, Query Opportunity, Ozon Public API, Advertising Snapshot, and Ramp-up remain outside this plan.
