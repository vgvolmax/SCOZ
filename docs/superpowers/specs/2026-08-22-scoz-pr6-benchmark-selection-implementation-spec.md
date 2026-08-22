# SCOZ PR6 — Relevant Queries, Benchmark Selection, MPStats Photos, and Encrypted Keystore Implementation Spec

**Status:** Proposed for approval / implementation authority after merge

**Base:** `970c0fb0716da388b5af474d8f166c05f1b6622c`

**Scope:** PR6 only. This is an implementation specification, not an execution plan.

## 1. Authority, purpose, and scope

After merge and explicit approval, this document is the PR-specific implementation authority for PR6. It refines, without replacing, `AGENTS.md`, the product specification and addenda, Architecture Design, Preflight Decisions, UI/UX Design, Visual Design System, the latest PR Development Plan, and the approved PR4/PR5 source contracts. The Development Plan controls PR sequencing; the later source contracts control imported fact identity and revision semantics.

PR6 creates two forms of **user-curated analytical context**:

1. the current product-specific set of genuinely relevant `SearchQuery` rows; and
2. immutable revisions of a manually selected competitor set.

It derives a candidate view from existing Ozon facts, optionally enriches candidates with transient MPStats thumbnails, and supplies a browser-only portable encrypted credential file. Relevant-query choices and benchmark composition are neither source facts nor derived analytics.

The canonical flow is fixed:

1. enter competitor selection from an owned catalog Product;
2. review that Product's query universe and save a relevant-query set;
3. derive candidates only from Ozon Search Visibility evidence for that saved set;
4. optionally load candidate thumbnails from MPStats;
5. include/exclude candidates and optionally add a competitor by numeric Ozon product ID;
6. save a non-empty unordered composition as an immutable `BenchmarkSetRevision`;
7. manage the MPStats token in Settings → Sources by manual entry, test, encrypted download, encrypted-file open, and Lock.

## Current main baseline

Only these existing interfaces constrain PR6:

- `Product` is the shared identity registry and has `is_owned`; `ProductExternalIdentity` uniquely identifies an Ozon product with `source="ozon"`, `identity_type="ozon_product_id"`, empty account scope, and a digit-only string. `ProductRepository.resolve_or_create_ozon_product()` is the sole resolver PR6 reuses.
- `/api/products` is a catalog projection over Products that have `ProductSnapshot` evidence. Identity-only Products created by Search Visibility or seller-query imports do not appear there.
- `SearchQuery` identity is the PR4 identity: trim only edge U+0020/U+00A0 and compare the remaining text exactly. `SearchDimensionRepository` owns creation/lookup. PR6 never renormalizes or creates a query while saving relevance.
- `ProductQuerySnapshot` has logical grain `(product_id, search_query_id, period_start, period_end)` with immutable positive revisions. `SearchVisibilitySnapshot` has logical grain `(product_id, search_query_id, cluster_id, observed_at)` with immutable positive revisions. The greatest revision within an exact logical key is current; superseded rows remain history.
- `ProductQuerySnapshotRepository`, `SearchVisibilitySnapshotRepository`, and existing transaction helpers establish the SQLite repository and all-or-nothing application-service patterns. SQL remains in repositories.
- FastAPI routes in `backend/main.py` validate transport, invoke application services, serialize DTOs, and map domain failures. Production serves committed `frontend/index.html`, `frontend/assets/css/app.css`, and classic `frontend/assets/js/app.js` same-origin.
- migrations 001–004 are a contiguous registry in `backend/persistence/migrations/runner.py`; PR6 is migration 005.
- runtime requirements are exactly pinned. `requirements-dev.txt` inherits `requirements.txt` and currently adds `pytest` and `httpx`; CI runs Python tests, a Node syntax check when Node is present, and Windows portable smoke.
- `.gitignore` already ignores `*.enc.json`, `*credentials*.json`, and `*credential*.json`; it covers `scoz_credentials.enc.json`. No `.gitignore` change is required.

The PR6 MPStats contract was verified against the current official MPStats Ozon Analytics API documentation during independent spec review on 2026-08-22. The verified contract is `POST /api/analytics/v1/oz/items`, `ids` as a query-string parameter, `X-Mpstats-TOKEN` as primary authentication, a response envelope containing `data[]`, documented common statuses 200/202/401/429/500, and `Retry-After` semantics for 429. If the official contract changes before implementation and conflicts with this specification, implementation MUST stop and the specification must be corrected and approved separately; this is not permission to substitute an undocumented endpoint.

## 3. Explicit non-goals

PR6 MUST NOT implement benchmark median, P25/P75, delta, status, confidence, sample algorithms, advertising-intensity calculations, Diagnostics, Product Workspace diagnostics, Search Visibility heatmap, Query Opportunity, Opportunity Score, `SearchPositionSnapshot`, MPStats position history, Ozon Public API sync, `AdvertisingSnapshot`, Ramp-up, a generic analytics engine, `GenericBenchmarkEngine`, `GenericSourceResolver`, SourceCapability registry, persistent operation/job infrastructure, a backend credential database, DPAPI, Credential Manager, a frontend framework/npm build, MPStats sales/revenue as SCOZ facts, caching MPStats commercial metrics, `BenchmarkSnapshot`, or competitor metric history inside `BenchmarkSetRevision`.

PR6 stores composition/context, not benchmark math. It creates no future-feature table and no source-resolution framework.

## 4. Migration 005: exact schema

Create `backend/persistence/migrations/migration_005_benchmark_selection.py`; register `(5, "benchmark_selection", "backend.persistence.migrations.migration_005_benchmark_selection")` as the next and only new runner entry.

The migration executes exactly the following logical DDL (formatting may follow repository style):

```sql
CREATE TABLE product_relevant_queries (
    product_id INTEGER NOT NULL
        REFERENCES products(id) ON DELETE CASCADE,
    search_query_id INTEGER NOT NULL
        REFERENCES search_queries(id) ON DELETE RESTRICT,
    selected_at TEXT NOT NULL,
    PRIMARY KEY (product_id, search_query_id)
);
CREATE INDEX idx_product_relevant_queries_query_product
    ON product_relevant_queries(search_query_id, product_id);

CREATE TABLE benchmark_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    own_product_id INTEGER NOT NULL
        REFERENCES products(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    UNIQUE (own_product_id)
);

CREATE TABLE benchmark_set_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_set_id INTEGER NOT NULL
        REFERENCES benchmark_sets(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL CHECK (revision > 0),
    created_at TEXT NOT NULL,
    UNIQUE (benchmark_set_id, revision)
);
CREATE INDEX idx_benchmark_set_revisions_current
    ON benchmark_set_revisions(benchmark_set_id, revision DESC);

CREATE TABLE benchmark_members (
    benchmark_set_revision_id INTEGER NOT NULL
        REFERENCES benchmark_set_revisions(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL
        REFERENCES products(id) ON DELETE RESTRICT,
    PRIMARY KEY (benchmark_set_revision_id, product_id)
);
CREATE INDEX idx_benchmark_members_product_revision
    ON benchmark_members(product_id, benchmark_set_revision_id);
```

`selected_at` is UTC ISO-8601 in the repository's existing database representation and records when that relation was inserted by the most recent replacement. Retained rows keep their existing timestamp; newly selected rows receive one transaction-wide timestamp. It is display/audit context, not revision history.

No relevance revision/effective-date tables exist. Empty relevance is represented by zero rows. Deleting a Product removes its relevance rows but an owned Product referenced by a benchmark set and a member Product referenced by a revision are protected. Deleting a benchmark set cascades only its revisions and memberships. Application workflows do not expose deletes in PR6.

Upgrade from any valid migration prefix, including a populated v4 database, applies 005 transactionally and preserves every existing row. Migration 005 creates only the four tables and three indexes above.

## 5. Relevant-query contract

### 5.1 Query universe and current evidence

For an owned Product, define a coherent own-query period as exact `(period_start, period_end)`. Consider the **current revision** for every `ProductQuerySnapshot` logical key: the row with greatest `revision` for the same `(product_id, search_query_id, period_start, period_end)`.

The latest coherent period is the lexicographically greatest tuple `(period_end, period_start)` among periods having at least one current row for the Product. This chooses the greatest end date first and, only on equal end date, the greatest start date. Import time, row ID, and input order never choose the period.

The visible options are the set union of:

- all current rows in that latest period; and
- all already-selected query IDs that have any historical `ProductQuerySnapshot` evidence for this Product.

There is one option per query. A latest-period option uses the current snapshot in that exact latest period. A selected historical option absent there has `in_latest_period=false`, has no current-period metrics, and exposes the newest historical evidence period chosen by greatest `(period_end, period_start)`, then that key's greatest revision. It stays visible until deselected.

If no ProductQuery evidence exists and no valid stale selection can exist, GET returns `readiness="NO_OWN_QUERY_DATA"`, `latest_period=null`, and an empty `items` array with HTTP 200. PUT returns `NO_OWN_QUERY_DATA` with 409. An existing ProductQuery universe with zero selected rows returns `readiness="EMPTY_SELECTION"`; candidate GET returns `RELEVANT_QUERY_SELECTION_EMPTY` with 409. Empty selection is a valid atomic PUT and is the deliberate way to clear the scope.

Selection validation accepts only distinct positive integer query IDs. Every submitted ID must reference an existing `SearchQuery` and must have at least one `ProductQuerySnapshot` for this same own Product in any period. A query evidenced only for another Product is invalid. Duplicate IDs and non-integers are 422. The application opens one `immediate_transaction`, then repository SQL validates the complete set, deletes relations absent from the submitted set, inserts newly present relations, and retains unchanged relations. The helper commits on success; any failure rolls back and leaves the old set untouched.

The query identity contract remains exact after edge trimming performed at ingestion. PR6 does not lowercase, casefold, map `ё` to `е`, stem, lemmatize, correct spelling, collapse internal spaces, fuzzy-match, or semantically match.

### 5.2 Domain types

Create `backend/domain/benchmark_selection.py` with frozen dataclasses and enums:

```python
class RelevantQueryReadiness(str, Enum):
    READY = "READY"
    EMPTY_SELECTION = "EMPTY_SELECTION"
    NO_OWN_QUERY_DATA = "NO_OWN_QUERY_DATA"

@dataclass(frozen=True)
class SourcePeriod:
    period_start: date
    period_end: date

@dataclass(frozen=True)
class RelevantQueryOption:
    search_query_id: int
    query_text: str
    selected: bool
    selected_at: datetime | None
    in_latest_period: bool
    evidence_period: SourcePeriod
    searched_users: int | None
    seen_users: int | None
    average_position: int | None
    ordered_units: int | None
    ordered_revenue_rub: Decimal | None

@dataclass(frozen=True)
class RelevantQuerySelection:
    product_id: int
    readiness: RelevantQueryReadiness
    latest_period: SourcePeriod | None
    items: tuple[RelevantQueryOption, ...]
    selected_count: int

@dataclass(frozen=True)
class RelevantQueryWriteResult:
    selection: RelevantQuerySelection
    changed: bool
```

For stale rows, `evidence_period` is historical and all metric fields above come from that historical current revision; `in_latest_period` alone prevents that evidence from appearing fresh. Options order deterministically by `selected DESC`, `in_latest_period DESC`, `searched_users DESC NULLS LAST` expressed portably in SQL, then `query_text ASC`, `search_query_id ASC`.

## 6. Candidate derivation and display evidence

### 6.1 Temporal and deduplication semantics

Candidate existence is a derived view over persisted Ozon `SearchVisibilitySnapshot` source facts. It uses only the Product's persisted relevant-query rows; MPStats never creates a candidate.

For each selected `search_query_id × cluster_id` that has Search Visibility evidence:

1. choose greatest `observed_at` across that exact query/cluster;
2. at that timestamp, for every Product logical observation choose greatest `revision` for `(product_id, search_query_id, cluster_id, observed_at)`;
3. include every resulting Product except the active own Product.

The union is deduplicated by Product across queries and clusters. Older timestamps for a query/cluster and superseded revisions do not contribute counts or display values. `matched_relevant_query_count` and `matched_cluster_count` count distinct selected queries and clusters represented in the union.

For each candidate, the representative source row is selected from its contributing current rows by `position ASC`, then `observed_at DESC`, `search_query_id ASC`, `cluster_id ASC`, `snapshot id DESC`. `best_position` is that row's position. `source_title`, `seller_name`, `buyer_price_rub`, and `representative_observed_at` come only from that row and are explicitly contextual Search Visibility evidence, not canonical Product attributes.

Candidate order is `best_position ASC`, `matched_relevant_query_count DESC`, numeric Ozon ID ASC, `product_id ASC`. Pagination is applied after Product deduplication with `limit` 1–100, default 50, and `offset` ≥ 0, default 0. `total` is the full deduplicated count. No candidate score exists.

### 6.2 Candidate/domain DTOs

Add these exact types to `backend/domain/benchmark_selection.py`:

```python
class PhotoStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"

class CandidateReadiness(str, Enum):
    READY = "READY"
    NO_CANDIDATE_EVIDENCE = "NO_CANDIDATE_EVIDENCE"

@dataclass(frozen=True)
class BenchmarkCandidate:
    product_id: int
    ozon_product_id: str
    source_title: str | None
    seller_name: str | None
    contextual_price_rub: Decimal | None
    representative_observed_at: datetime | None
    matched_relevant_query_count: int
    matched_cluster_count: int
    best_position: int | None
    photo_status: PhotoStatus
    photo_url: str | None
    already_selected_in_current_benchmark: bool
    origin: Literal["SEARCH_VISIBILITY", "MANUAL"]

@dataclass(frozen=True)
class CandidatePage:
    product_id: int
    readiness: CandidateReadiness
    items: tuple[BenchmarkCandidate, ...]
    total: int
    limit: int
    offset: int
```

Local candidate GET always returns `photo_status=NOT_REQUESTED` and `photo_url=null`. A successful MPStats preview with a photo returns `AVAILABLE`; a successful response with no usable photo returns `MISSING`. Source-level failures remain typed source errors rather than fabricated per-item photo states. A browser image-load failure is a transient UI placeholder/error state, not a backend `PhotoStatus`. A manual candidate without local evidence has null contextual fields, zero counts, and null best position. Brand is absent because no approved local candidate source supplies it. MPStats `name`, `brand`, `seller`, sales, revenue, and all other non-photo fields are ignored.

Non-empty `items` yields `readiness=READY`. Zero candidate evidence yields HTTP 200 with an empty page and `readiness=NO_CANDIDATE_EVIDENCE`; this is not an error and manual add remains available. Empty relevant-query selection remains the separate 409 `RELEVANT_QUERY_SELECTION_EMPTY` domain error.

## 7. Manual competitor identity flow

The manual request accepts `ozon_product_id` as a JSON string matching `^[0-9]+$`; leading zeroes are rejected by requiring `str(int(value)) == value`, and zero is rejected. This is the canonical numeric representation passed to the existing `ProductRepository.resolve_or_create_ozon_product()`; implementation also tightens that repository method to apply this same canonical rule so there is only one resolver and validator.

Inside one `immediate_transaction`, the service validates the owned Product and canonical Ozon ID, then calls `find_by_external_identity(...)`. If found, it reuses that Product with `created=false`; otherwise it calls the existing `ProductRepository.resolve_or_create_ozon_product(...)`, which continues to return `Product`, and reports `created=true`. The resolver may tighten its canonical validation to reject zero, leading zeros, and nondigits, but its public return signature MUST NOT change. The service rejects only resolution to the active own Product; another Product with `is_owned=true` remains a valid comparator. It creates neither a `ProductSnapshot`, relevance row, candidate history, nor benchmark revision. Photo lookup remains a separate request and failure never rolls back the identity.

The type-safe application result is:

```python
@dataclass(frozen=True)
class ManualCandidateWriteResult:
    created: bool
    candidate: BenchmarkCandidate
```

An identity-only Product can be a `BenchmarkMember` but MUST NOT appear in `/api/products` merely because of identity creation or benchmark membership. No fake snapshot, implicit ownership, or orphan-cleanup subsystem is introduced.

## 8. Benchmark composition model and revision semantics

Add exact frozen types:

```python
@dataclass(frozen=True)
class BenchmarkSet:
    id: int
    own_product_id: int
    created_at: datetime

@dataclass(frozen=True)
class BenchmarkMember:
    benchmark_set_revision_id: int
    product_id: int
    ozon_product_id: str

@dataclass(frozen=True)
class BenchmarkSetRevision:
    id: int
    benchmark_set_id: int
    revision: int
    created_at: datetime
    members: tuple[BenchmarkMember, ...]

@dataclass(frozen=True)
class BenchmarkComposition:
    benchmark_set: BenchmarkSet | None
    current_revision: BenchmarkSetRevision | None

class BenchmarkWriteKind(str, Enum):
    CREATED = "CREATED"
    CHANGED = "CHANGED"
    NO_CHANGE = "NO_CHANGE"

@dataclass(frozen=True)
class BenchmarkCompositionWriteResult:
    kind: BenchmarkWriteKind
    benchmark_set: BenchmarkSet
    revision: BenchmarkSetRevision
```

A BenchmarkSet is the stable container uniquely owned by one own Product. Members are ordinary Products and their collection is an unordered set. The first non-empty save creates revision 1. A different set creates `current revision + 1`. Saving the exact same set in any order returns the current revision and `kind="NO_CHANGE"`; no row is inserted. Old revisions and memberships are immutable. Member output is sorted by numeric Ozon ID then Product ID.

An empty member set is invalid and returns `BENCHMARK_EMPTY` (422); it creates no BenchmarkSet. Every member must exist, have exactly one canonical Ozon external identity, and differ from the active own Product; otherwise the complete write returns `BENCHMARK_MEMBER_INVALID` (422). Another Product with `is_owned=true` may be a member when the user considers it a direct comparator for the active own Product. Membership never changes ownership and does not require Search Visibility evidence, a ProductSnapshot, or a photo. Candidate derivation likewise excludes only the active own Product, not every owned Product.

The application owns the transaction boundary and uses `immediate_transaction` around BenchmarkSet get/create, current revision read, normalized member-set comparison, next revision insert, and all member inserts. `BEGIN IMMEDIATE` serializes local SQLite writers: a second writer waits according to the connection timeout, then reads the committed current state and returns `NO_CHANGE` for the same set or writes `current revision + 1` for a different set. If acquiring the immediate transaction ends with an actual SQLite BUSY/LOCKED condition, the application maps it to 409 `BENCHMARK_CONCURRENT_WRITE`. Other SQLite failures, including unrelated `OperationalError` instances, MUST NOT be mislabeled as concurrency. There is no retry framework, repository reopen/retry loop, distributed lock, or generic optimistic-lock subsystem. UNIQUE constraints remain final invariant protection, and no half revision can commit.

No price, conversion, sales, median, quartile, delta, confidence, source-metric copy, photo, or metric history is stored in these tables.

## 9. Repository boundaries

Create `backend/persistence/repositories/benchmark_selection.py` with exactly these public methods; all SQL for PR6 remains here:

```python
class BenchmarkSelectionRepository:
    def list_relevant_query_options(self, product_id: int) -> RelevantQuerySelection: ...
    def list_selected_query_ids(self, product_id: int) -> frozenset[int]: ...
    def replace_relevant_queries(self, product_id: int, search_query_ids: frozenset[int]) -> RelevantQueryWriteResult: ...
    def list_candidates(self, product_id: int, *, limit: int, offset: int) -> CandidatePage: ...
    def get_benchmark(self, own_product_id: int) -> BenchmarkComposition: ...
    def save_benchmark(self, own_product_id: int, member_product_ids: frozenset[int]) -> BenchmarkCompositionWriteResult: ...
```

`BenchmarkSelectionRepository` receives an already-open connection. It MUST NOT issue `BEGIN`, `BEGIN IMMEDIATE`, `COMMIT`, or `ROLLBACK`, reopen the connection, or own transaction lifecycle. `replace_relevant_queries` and `save_benchmark` require a connection already inside the application's immediate boundary. Read methods receive a normal transaction connection. Candidate SQL implements the exact current-revision/latest-observation/deduplication rules in section 6, joins current benchmark membership to set the selection flag, and never calls MPStats.

Manual identity uses the existing `ProductRepository`; there is no second identity repository or resolver.

## 10. Application boundary

Create `backend/application/benchmark_selection.py` with one `BenchmarkSelectionService` and these exact public methods:

```python
class BenchmarkSelectionService:
    def get_relevant_queries(self, product_id: int) -> RelevantQuerySelection: ...
    def replace_relevant_queries(self, product_id: int, search_query_ids: tuple[int, ...]) -> RelevantQueryWriteResult: ...
    def get_candidates(self, product_id: int, *, limit: int, offset: int) -> CandidatePage: ...
    def add_manual_candidate(self, product_id: int, ozon_product_id: str) -> ManualCandidateWriteResult: ...
    def get_benchmark(self, product_id: int) -> BenchmarkComposition: ...
    def save_benchmark(self, product_id: int, member_product_ids: tuple[int, ...]) -> BenchmarkCompositionWriteResult: ...
    def enrich_mpstats_previews(self, token: SecretStr, ozon_product_ids: tuple[str, ...]) -> tuple[MPStatsProductPreview, ...]: ...
    def test_mpstats(self, token: SecretStr, ozon_product_id: str) -> MPStatsConnectionResult: ...
```

The service validates that product-specific workflow methods target an existing `is_owned=true` Product. It coordinates transactions, repository work, identity resolution, and the source adapter. For serialized writes it uses `with immediate_transaction(...) as conn:` and passes that connection to repositories; the application chooses transaction type but executes no raw SQL. Routes only validate Pydantic transport, call these methods, serialize DTOs (including `ManualCandidateWriteResult` directly), and map typed errors. Candidate and revision rules do not enter `backend/main.py` or JavaScript.

Add this focused connection helper to `backend/persistence/connection.py`:

```python
@contextmanager
def immediate_transaction(
    db_path: Path | None = None,
) -> Iterator[sqlite3.Connection]: ...
```

Its exact mechanics are `connect(...)`, `conn.execute("BEGIN IMMEDIATE")`, yield the connection, commit on success, rollback on exception, and always close. It contains no business SQL. Existing `transaction(...)` behavior is unchanged and remains the helper for reads. PR6 uses `immediate_transaction` for relevant-query replacement, manual identity resolve/create, and benchmark revision save.

## 11. MPStats adapter and network contract

### 11.1 Exact adapter

Create `backend/sources/__init__.py` and `backend/sources/mpstats.py`. `MPStatsClient` owns only the official request, token header, timeout, approved response parsing, and typed failure classification. Its constructor is:

```python
MPStatsClient(
    client: httpx.Client,
    *,
    base_url: str = "https://mpstats.io",
    timeout: httpx.Timeout = httpx.Timeout(15.0, connect=5.0),
)
```

Production code does not expose a configurable base URL; the constructor override exists only for tests and is rejected outside tests/application wiring if it is not HTTPS. The injected `httpx.Client` makes `httpx.MockTransport` sufficient; no generic HTTP abstraction is added.

`get_ozon_product_previews(token: SecretStr, ids: tuple[str, ...])` performs one request per chunk:

```http
POST https://mpstats.io/api/analytics/v1/oz/items?ids=123,456
X-Mpstats-TOKEN: <token>
```

`ids` is one comma-delimited query value without spaces. Inputs are already canonical positive Ozon digit strings, retain caller order, and duplicates are rejected before the adapter. Chunks contain 1–100 IDs; more than 100 is split sequentially into chunks of at most 100. An empty tuple returns locally without an HTTP request. The request has no JSON body, no `auth-token` query parameter, no `brands`, `sellers`, `keyword`, `d1`, `d2`, `filterModel`, or `sortModel`, and no automatic retry. Redirect following is disabled. Only HTTPS is allowed.

For a 200 response, the JSON root MUST be an object and `data` MUST exist as an array. Pagination metadata may exist but does not become SCOZ domain data; all other root fields are ignored. Each `data[]` item has a required positive JSON integer `id` (a boolean is invalid), normalized to a canonical decimal digit string, and `thumb`. The adapter consumes only `data[].id` and `data[].thumb`; `name`, `brand`, `seller`, `sales`, `revenue`, and every other field are ignored, never enter the DTO, are never persisted, and never become Product attributes or source facts. Duplicate occurrences of the same requested ID make the response malformed; unrequested IDs are ignored. Results are returned in original caller order:

```python
@dataclass(frozen=True)
class MPStatsProductPreview:
    ozon_product_id: str
    photo_status: PhotoStatus
    photo_url: str | None
```

A requested ID absent from valid `data`, or present with null/empty-string `thumb`, returns `MISSING`; a non-empty thumbnail must be a string and an approved absolute `https://` photo URL under the PR6 security rule or the response is malformed. Invalid item/id/thumb types are malformed. URLs are transient response data and are never written to SQLite, files, or logs.

### 11.2 Failure taxonomy and statuses

Create these typed adapter errors in `backend/domain/benchmark_selection.py`: `MPStatsAuthError`, `MPStatsRateLimitError(retry_after_seconds: int | None)`, `MPStatsPendingError`, `MPStatsTimeoutError`, `MPStatsNetworkError`, `MPStatsMalformedResponseError`, and `MPStatsUpstreamError`.

Mapping is exact:

| Upstream condition | Domain result |
|---|---|
| 200 and valid JSON schema | requested previews, including per-ID `MISSING` |
| 202 | `MPStatsPendingError` |
| 401 | `MPStatsAuthError` |
| 429 | `MPStatsRateLimitError`; parse `Retry-After` only when it is an integer 0–86400 seconds, otherwise null |
| 500–599 | `MPStatsUpstreamError` |
| any other HTTP status, including undocumented 403 | `MPStatsUpstreamError` |
| connect/read/write/pool timeout | `MPStatsTimeoutError` |
| other `httpx.RequestError` | `MPStatsNetworkError` |
| invalid JSON, wrong top-level/item shape, invalid id/thumb | `MPStatsMalformedResponseError` |

Raw response bodies, stack traces, request headers, and exception text are not user messages. Logging, if added, contains only operation name, status class, requested count, and safe error code.

### 11.3 Test connection probe

The public documentation does not establish a separate auth-only endpoint. Test connection therefore uses the same `POST /api/analytics/v1/oz/items` endpoint with `ids=<one canonical probe SKU>` in the query, `X-Mpstats-TOKEN` in the header, and no JSON body. The Settings form requires a numeric probe SKU, prefilled with the numerically smallest Ozon ID among current `/api/products` catalog items when available; without one the user enters a SKU. The local same-origin request body contains token and probe SKU; the backend translates them to the documented outbound query/header split. A valid 200 proves the authenticated request was accepted even when `data=[]`, that ID is absent, or it has no thumbnail. 202, auth, rate-limit, temporary, network, and malformed failures remain distinct. No competitor or business-critical SKU is hardcoded.

### 11.4 Dependency decision

The implementation adds `httpx==0.28.1` to `requirements.txt` as the sole outbound HTTP stack and removes the duplicate `httpx==0.28.1` line from `requirements-dev.txt`, which already inherits runtime requirements. It adds neither `requests` nor `aiohttp`. The exact pin works with the existing project-local portable pip installation and repair flow.

## 12. Exact REST API

All responses use JSON. Success bodies never contain a credential. Framework/transport validation failures—such as malformed JSON, a missing required field, a wrong JSON field type, or invalid path/query integer text—remain standard FastAPI HTTP 422 responses with the standard `detail` body. PR6 domain and source errors use `{"error":{"code":"...","message":"..."}}`. PR6 adds no global `RequestValidationError` handler and changes no existing endpoint response contract.

Path and query values are text on the wire and are normally parsed by FastAPI/Pydantic into typed integers: `product_id > 0`, `limit` obeys its bounds, and `offset >= 0`; nonnumeric text and prohibited zero/negative values are rejected. `StrictInt` is not a requirement for URL representation. JSON-body ID collections such as `search_query_ids` and `member_product_ids` use strict integer semantics (or exact equivalent validation): JSON `3` is accepted, while `"3"`, `true`, and `3.0` are rejected.

### 12.1 Relevant queries

`GET /api/products/{product_id}/relevant-queries`

- Request: no body or pagination.
- 200: `{"product_id":7,"readiness":"READY|EMPTY_SELECTION|NO_OWN_QUERY_DATA","latest_period":{"period_start":"YYYY-MM-DD","period_end":"YYYY-MM-DD"}|null,"selected_count":1,"items":[{"search_query_id":3,"query_text":"...","selected":true,"selected_at":"..."|null,"in_latest_period":true,"evidence_period":{"period_start":"...","period_end":"..."},"searched_users":10|null,"seen_users":8|null,"average_position":4|null,"ordered_units":2|null,"ordered_revenue_rub":"100.00"|null}]}`.
- Errors: 404 `PRODUCT_NOT_FOUND`; 409 `PRODUCT_NOT_OWNED`.
- Transaction: read transaction only.

`PUT /api/products/{product_id}/relevant-queries`

- Request: `{"search_query_ids":[3,8]}`; maximum 10,000 distinct IDs.
- 200: exact GET shape plus `"changed":true|false`. Repeating the same set is `changed=false`.
- Errors: 404 `PRODUCT_NOT_FOUND`; 409 `PRODUCT_NOT_OWNED`; 409 `NO_OWN_QUERY_DATA`; 422 `RELEVANT_QUERY_SELECTION_INVALID` for duplicates, nonexistent queries, or queries without evidence for this Product.
- Empty array is valid and clears selection.
- Transaction: one application-owned `immediate_transaction` all-or-nothing replacement.

### 12.2 Candidates

`GET /api/products/{product_id}/benchmark-candidates?limit=50&offset=0`

- Request: no body; pagination bounds are section 6.
- 200: `{"product_id":7,"readiness":"READY|NO_CANDIDATE_EVIDENCE","items":[<candidate>],"total":12,"limit":50,"offset":0}`. Candidate keys exactly match `BenchmarkCandidate`, decimals/datetimes serialized as strings.
- Errors: 404 `PRODUCT_NOT_FOUND`; 409 `PRODUCT_NOT_OWNED`; 409 `RELEVANT_QUERY_SELECTION_EMPTY`.
- Transaction: read only; never contacts MPStats.

`POST /api/products/{product_id}/benchmark-candidates/manual`

- Request: `{"ozon_product_id":"123456789"}`.
- 200 for reused identity or 201 for newly created identity: `{"created":true|false,"candidate":<candidate>}`.
- Errors: 404 `PRODUCT_NOT_FOUND`; 409 `PRODUCT_NOT_OWNED`; 409 `OWN_PRODUCT_CANNOT_BE_COMPETITOR`; 422 `MANUAL_OZON_SKU_INVALID`.
- Transaction: one application-owned `immediate_transaction` for identity resolve/create; no benchmark write and no remote call.

### 12.3 Benchmark

`GET /api/products/{product_id}/benchmark`

- 200 without a save: `{"benchmark_set":null,"current_revision":null}`.
- 200 with a save: `{"benchmark_set":{"id":1,"own_product_id":7,"created_at":"..."},"current_revision":{"id":4,"benchmark_set_id":1,"revision":2,"created_at":"...","members":[{"benchmark_set_revision_id":4,"product_id":9,"ozon_product_id":"123"}]}}`.
- Errors: 404 `PRODUCT_NOT_FOUND`; 409 `PRODUCT_NOT_OWNED`.
- Transaction: read only.

`POST /api/products/{product_id}/benchmark/revisions`

- Request: `{"member_product_ids":[9,12]}`; maximum 1,000 distinct positive IDs.
- 201 for `CREATED`/`CHANGED`, 200 for `NO_CHANGE`: `{"result":"CREATED|CHANGED|NO_CHANGE","benchmark_set":{...},"revision":{...}}`.
- Errors: 404 `PRODUCT_NOT_FOUND`; 409 `PRODUCT_NOT_OWNED`; 409 `BENCHMARK_CONCURRENT_WRITE`; 422 `BENCHMARK_EMPTY`; 422 `BENCHMARK_MEMBER_INVALID` (duplicate, missing, the active own Product itself, or lacking canonical Ozon identity). Another owned Product is valid.
- Idempotency compares the unordered ID set; order is irrelevant.
- Transaction: the application-owned `immediate_transaction` boundary in sections 8–10.

### 12.4 MPStats source operations

Pydantic request models store token as `SecretStr`, require 1–4096 Unicode characters after no transformation, reject an empty token, and pass `get_secret_value()` only at the adapter call boundary. Token is never serialized.

`POST /api/sources/mpstats/test`

- Request: `{"token":"secret","ozon_product_id":"123456789"}`.
- 200: `{"status":"AVAILABLE","message":"Подключение к MPStats подтверждено."}`. A missing item/thumb still yields AVAILABLE.
- Errors use source matrix below.
- Transaction: none; one remote probe only.

`POST /api/sources/mpstats/ozon-product-previews`

- Request: `{"token":"secret","ozon_product_ids":["123","456"]}`; 1–500 unique canonical IDs.
- 200: `{"items":[{"ozon_product_id":"123","photo_status":"AVAILABLE|MISSING","photo_url":"https://..."|null}]}` in request order.
- Entire-source failure returns the mapped error and no fabricated photos. The already loaded local candidate page is unaffected. Individual missing photos are successful `MISSING` items.
- Transaction: none; bounded remote batches only.

Source error mapping for both endpoints:

| Domain error | HTTP | code | actionable message |
|---|---:|---|---|
| pending | 409 | `MPSTATS_PENDING` | `MPStats ещё готовит ответ. Повторите запрос позже.` |
| auth | 401 | `MPSTATS_AUTH` | `MPStats отклонил токен. Проверьте токен и повторите.` |
| rate limit | 429 | `MPSTATS_RATE_LIMIT` | `Лимит MPStats исчерпан. Повторите позже.` |
| timeout | 504 | `MPSTATS_TIMEOUT` | `MPStats не ответил вовремя. Кандидаты сохранены; повторите загрузку фото.` |
| network | 502 | `MPSTATS_NETWORK` | `Не удалось связаться с MPStats. Проверьте сеть и повторите.` |
| malformed | 502 | `MPSTATS_MALFORMED_RESPONSE` | `MPStats вернул неподдерживаемый ответ. Повторите позже.` |
| upstream | 502 | `MPSTATS_UPSTREAM` | `MPStats временно недоступен. Повторите позже.` |

For rate limiting, response JSON additionally contains `retry_after_seconds` and the local response emits `Retry-After` only when safely parsed. No upstream body is forwarded.

## 13. Complete local error taxonomy

| Condition | HTTP/code | UI action |
|---|---|---|
| Product absent | 404 `PRODUCT_NOT_FOUND` | return to Products/refresh |
| Product exists but not owned | 409 `PRODUCT_NOT_OWNED` | choose an owned catalog Product |
| no own-query evidence | GET state; PUT 409 `NO_OWN_QUERY_DATA` | import own-product queries |
| invalid relevance set | 422 `RELEVANT_QUERY_SELECTION_INVALID` | refresh and select offered rows |
| deliberately empty relevance | saved state; candidate 409 `RELEVANT_QUERY_SELECTION_EMPTY` | select and save at least one query |
| no candidate evidence | 200 `NO_CANDIDATE_EVIDENCE` state | import Search Visibility or add manually |
| bad manual ID | 422 `MANUAL_OZON_SKU_INVALID` | enter canonical numeric SKU |
| own as competitor | 409 `OWN_PRODUCT_CANNOT_BE_COMPETITOR` | choose another SKU |
| invalid benchmark member | 422 `BENCHMARK_MEMBER_INVALID` | refresh/remove invalid member |
| empty benchmark | 422 `BENCHMARK_EMPTY` | select at least one competitor |
| same benchmark set | 200 `NO_CHANGE` result | show revision unchanged |
| concurrent write unresolved | 409 `BENCHMARK_CONCURRENT_WRITE` | refresh current revision and retry |

MPStats errors are defined in section 12. Keystore errors never call the backend: `UNSUPPORTED_KEYSTORE_FORMAT`, `UNSUPPORTED_KEYSTORE_VERSION`, `INVALID_KEYSTORE_ENVELOPE`, and `KEYSTORE_DECRYPT_FAILED`. The last intentionally combines wrong password and corrupt/authentication-failed ciphertext and displays `Не удалось открыть файл: неверный пароль или файл повреждён.` No partial plaintext is displayed.

## Credential and source-security invariants

Credentials travel from the local frontend to the SCOZ backend only in same-origin JSON POST bodies for the immediate source operation. They MUST NOT be placed in GET parameters, URLs, query strings, localStorage, sessionStorage, IndexedDB, cookies, SQLite, config, source artifacts, generated HTML state, logs, response bodies, error details, or exception text. The backend sends the Ozon SKU list in MPStats's documented `ids` query parameter; SKU IDs are not credentials.

Implementation MUST NOT log or echo the token; persist plaintext; use MPStats `auth-token` query-parameter authentication; save a decrypted keystore payload; commit encrypted credential files; include a real credential fixture; store the password; or reveal partial decrypted content after failure. The backend transfers the transient local token only to outbound `X-Mpstats-TOKEN`; no credential enters the outbound URL. Application logs redact headers and request bodies rather than attempting value-specific replacement.

Photos and their URLs are transient. MPStats commercial fields are discarded at the adapter. A photo outage cannot remove candidates, invalidate membership, roll back local data, or prevent a benchmark save.

## 15. Browser encrypted keystore v1

### 15.1 Plaintext payload

Before encryption, canonical UTF-8 JSON is produced by `JSON.stringify` on this exact insertion-ordered object, with no whitespace:

```json
{"version":1,"sources":{"mpstats":{"token":"..."}}}
```

Only these keys are accepted on decryption; unknown or missing keys, non-integer version, version other than 1, empty/non-string token, or non-object nodes are invalid. No Ozon/future provider, refresh token, or account object is predesigned.

### 15.2 Envelope and cryptography

Downloaded filename is exactly `scoz_credentials.enc.json`. Its UTF-8 JSON envelope is:

```json
{
  "format": "scoz-credentials-keystore",
  "version": 1,
  "kdf": {
    "name": "PBKDF2",
    "hash": "SHA-256",
    "iterations": 600000,
    "salt": "<base64>"
  },
  "cipher": {
    "name": "AES-GCM",
    "key_length": 256,
    "iv": "<base64>",
    "tag_length": 128
  },
  "ciphertext": "<base64>"
}
```

Base64 is standard RFC 4648 with `A–Z a–z 0–9 + /`, required `=` padding, and no whitespace or data-URL prefix. Decoding must be canonical: decode then re-encode to the same string. Salt is exactly 16 cryptographically random bytes and IV exactly 12 random bytes from `crypto.getRandomValues`; each save generates both anew. Password is UTF-8 encoded exactly as entered, is neither trimmed nor normalized, and is never written. Empty password is rejected.

Web Crypto imports the password as PBKDF2 key material, derives a non-extractable 256-bit AES-GCM key with PBKDF2-HMAC-SHA256 and 600000 iterations, and encrypts with 128-bit GCM tag. No additional authenticated data is used. Web Crypto ciphertext contains ciphertext followed by the authentication tag and is stored as the one `ciphertext` field.

Validation occurs before expensive derivation: exact format, supported version, exact algorithm names/numbers, exact key set, canonical base64, salt/IV lengths, and ciphertext length ≥ 17 bytes. Unsupported format/version are distinct; malformed fields are `INVALID_KEYSTORE_ENVELOPE`; Web Crypto decrypt/authentication failure or invalid decrypted UTF-8/JSON/payload is `KEYSTORE_DECRYPT_FAILED`.

### 15.3 JavaScript module contract

Create `frontend/assets/js/keystore.js` as a classic script loaded before `app.js`. It attaches one frozen global `window.ScozKeystore` with exact async functions:

```javascript
encryptMpstatsCredentials({ token }, password) // Promise<object envelope>
decryptMpstatsCredentials(envelope, password)  // Promise<{token: string}>
serializeEnvelope(envelope)                    // string
parseEnvelope(jsonText)                        // validated object
downloadEnvelope(envelope)                     // void; exact filename
```

For dependency-free Node tests, the same object is assigned to `globalThis.ScozKeystore`; the file uses `globalThis.crypto`, `TextEncoder`, `TextDecoder`, `atob`, and `btoa` compatible with current browser and Node built-ins. It has no DOM/UI orchestration except `downloadEnvelope`, which creates a UTF-8 `application/json` Blob, clicks a temporary object-URL anchor, then revokes the URL and removes the anchor.

`app.js` alone owns an in-memory `credentialState = { mpstats: { token } } | null`. Manual input copies a validated token into this variable. Open reads one selected local file in the browser, parses it, asks for password, decrypts it, replaces state only after complete success, clears password/file inputs, and shows unlocked status without revealing token. Failure preserves the pre-existing state and clears password fields.

Save requires non-empty in-memory token, password and confirmation; exact equality is required. On mismatch no encryption/download occurs. After download both password inputs are cleared; unlocked token stays in memory. Lock sets state to null, clears token/password/confirmation/file inputs, clears source-test/photo transient status and any preview URLs from candidate DOM/state, and renders locked status. Reload/tab close naturally clears state. There is no backend encrypt/decrypt/save endpoint.

## 16. Frontend customer journey and states

The existing Products view remains the entry. Each owned catalog card gets `Выбрать конкурентов`; non-owned cards do not. This opens an in-page Competitors workspace, not a new global navigation section or future Diagnostics workspace. The active own Product title/Ozon ID stays visible.

### 16.1 Relevant queries

The top card shows latest source period, selected count, and a table with checkbox, exact query text, searched/seen users, average position, ordered units/revenue, and freshness. Stale selected rows have a visible `Нет в свежем периоде` chip and historical evidence period. Save is disabled while loading/saving, gives `Сохраняем…`, success, no-change, and actionable error feedback. States are:

- loading skeleton/known layout;
- `NO_OWN_QUERY_DATA`: import guidance and link to Data;
- latest data with zero selection: explicit prompt;
- stale/partial selection: rows remain editable;
- fetch/save error: preserve prior visible rows and permit retry.

Candidate controls remain disabled until a non-empty relevant set has been saved.

### 16.2 Competitors

After relevance save, show scope summary with chosen query count and `Изменить запросы`. Use the Visual Design System desktop two-column layout: left 65–70% candidate grid/list, right 30–35% selected set. Candidate cards show placeholder/thumbnail, contextual local title, Ozon ID, local seller/price when present, best position, matched query/cluster counts, observation timestamp, and include checkbox. They never show a score or MPStats commercial data.

The right side shows selected count, current revision or `Ещё не сохранено`, removable members, manual canonical SKU field, and `Сохранить benchmark`. Candidate pagination uses the frozen API order. Manual add immediately adds/returns a selectable card but does not save a revision. Photo loading is a separate action enabled only with unlocked credentials; loading/error/MISSING use stable placeholders and never clear local cards or selection. Image load error changes that card to placeholder without changing identity.

Saving shows created revision, changed revision, or explicit `Состав не изменился — revision N`. Empty composition has inline validation. Refresh/reopen loads current membership and flags matching candidates. UI includes loading, empty, no-evidence, partial-photo, error, and stale evidence states; it adds no fake Diagnostics or Ramp-up screen.

### 16.3 Settings → Sources

Replace the current Settings empty state with one MPStats source card: password-type token field, probe Ozon SKU, `Проверить подключение`, status, `Сохранить зашифрованный файл`, file input + `Открыть`, password, save-only confirmation, and `Заблокировать ключи`. Test and photo actions use the current memory token only. Busy controls disable duplicate submission and have `aria-live` status. Unlock status never renders the token. Source errors use section 12 messages.

All markup/classes use existing committed HTML/CSS and canonical tokens, cards, controls, chips, spacing, placeholders, focus states, and desktop density. No npm, framework, TypeScript, bundler, build output, or user-side Node is introduced.

## 17. Atomicity and failure semantics

- the application wraps relevance PUT in one `immediate_transaction`; validation and replacement are all-or-nothing;
- the application wraps manual identity resolution/creation in one `immediate_transaction`, which never creates other facts;
- the application wraps benchmark set creation/current read/number allocation/revision/members in one `immediate_transaction`; rollback removes every partial row;
- the connection helper owns SQLite transaction mechanics, repositories own business SQL and never begin/commit/rollback/reopen;
- MPStats operations open no database transaction and cannot roll back or mutate local context;
- encryption/decryption occurs only in the browser and never reaches backend persistence;
- photo availability is not a validity condition for candidates or benchmark members.

## Proposed file map

### Create

- `backend/domain/benchmark_selection.py` — frozen PR6 context, composition, preview DTOs/enums/errors.
- `backend/application/benchmark_selection.py` — owned-product validation and PR6 orchestration.
- `backend/sources/__init__.py` — package marker only.
- `backend/sources/mpstats.py` — feature-specific official MPStats photo adapter.
- `backend/persistence/repositories/benchmark_selection.py` — all relevance/candidate/benchmark SQL.
- `backend/persistence/migrations/migration_005_benchmark_selection.py` — exact PR6 schema.
- `frontend/assets/js/keystore.js` — browser Web Crypto v1 contract.
- `tests/test_benchmark_selection_repository.py` — query/candidate/composition repository contract.
- `tests/test_benchmark_selection_api.py` — real TestClient endpoint/error/catalog-boundary contract.
- `tests/test_mpstats_source.py` — adapter contract with `httpx.MockTransport` only.
- `tests/keystore_contract.mjs` — dependency-free Node Web Crypto tests.

### Modify

- `backend/domain/__init__.py` — export PR6 domain symbols following current package convention.
- `backend/persistence/repositories/__init__.py` — export the PR6 repository.
- `backend/persistence/repositories/products.py` — tighten/reuse canonical Ozon-ID validation while preserving `resolve_or_create_ozon_product(...) -> Product` and catalog projection.
- `backend/persistence/connection.py` — add focused `immediate_transaction`, preserving existing `transaction` behavior.
- `backend/persistence/migrations/runner.py` — register migration 005.
- `backend/main.py` — Pydantic request models, thin routes, serialization, typed error mapping.
- `frontend/index.html` — Competitors workspace and MPStats source/keystore controls; load `keystore.js` before `app.js`.
- `frontend/assets/js/app.js` — PR6 UI orchestration and tab-memory credential state.
- `frontend/assets/css/app.css` — canonical competitor two-column, query table, photo placeholder, source-card states.
- `requirements.txt` — add exact runtime `httpx==0.28.1`.
- `requirements-dev.txt` — remove inherited duplicate `httpx` line.
- `.github/workflows/ci.yml` — syntax-check both JS files and run Node keystore contract without npm.
- `tests/test_migrations.py` — migration 005 fresh/upgrade/schema preservation assertions.
- `tests/test_database.py` — immediate transaction commit/rollback/close and lock behavior without changing the normal helper.
- `tests/test_product_repository.py` — canonical manual-ID and identity-only behavior.
- `tests/test_frontend_contract.py` — real DOM/static contract and credential-persistence prohibitions.
- `tests/windows_smoke.ps1` — keep portable smoke and add local PR6 route/UI probes without MPStats network.

No `.gitignore` modification is planned or allowed by PR6 implementation because current rules already cover the canonical file.

## 19. Automated test matrix

### 19.1 Migration and persistence

- fresh database runs migrations 1→5; populated v4 runs 4→5;
- exact tables, columns, PKs, UNIQUE/CHECK/FKs/delete actions, and named indexes exist;
- representative PR1–PR5 Products, identities, artifacts, revisions, and query rows are byte/value unchanged;
- relevance latest period chooses greatest `(period_end, period_start)`, not import/row order;
- only greatest revision per logical ProductQuery key appears;
- save/reopen, no-change, replacement removal, retained timestamp, new timestamp, and rollback;
- stale selected query remains visible/deselectable with historical period;
- nonexistent, duplicate, and another-product-only query rejection; valid empty clear and no-data behavior;
- candidates use selected queries only; an unselected query contributes nothing;
- latest timestamp per selected query/cluster and current revision only;
- multi-cluster and multi-query Product deduplication with distinct counts;
- representative-row tie-break, own exclusion, deterministic order, total/limit/offset;
- no evidence state and current-benchmark selection flag;
- manual existing identity yields `created=false`, new identity-only creation yields `created=true`, invalid/active-own rejection, and `ManualCandidateWriteResult` serialization;
- existing `resolve_or_create_ozon_product(...) -> Product` contract and catalog boundary remain unchanged;
- no ProductSnapshot fabricated and identity-only/member Product absent from `/api/products`;
- first benchmark revision 1; exact composition; unordered same set `NO_CHANGE`; changed set next revision; old revision/members immutable;
- empty and invalid member rejection; active own Product rejected, another Product with `is_owned=true` accepted, and membership does not alter ownership; no metric/photo columns or values stored;
- `immediate_transaction` commits on success, rolls back on exception, closes always, and leaves normal `transaction` behavior unchanged;
- injected failure rolls back complete revision; a competing writer cannot allocate a duplicate revision; after the first commit, a same-set second save returns `NO_CHANGE` and a different set gets the next revision;
- busy/locked timeout maps to `BENCHMARK_CONCURRENT_WRITE`, while an unrelated SQLite failure is not mislabeled as concurrency;
- zero candidate evidence produces `CandidatePage.readiness=NO_CANDIDATE_EVIDENCE`; a non-empty page produces `READY`.

### 19.2 MPStats and secrets

Using `httpx.MockTransport`, assert POST, host `mpstats.io`, path `/api/analytics/v1/oz/items`, decoded query `ids == "123,456"`, no `auth-token`, disabled redirects, timeout wiring, sequential chunks of at most 100, caller order, injected client, an empty outbound body, and token only in `X-Mpstats-TOKEN`—never query/body. The representative 200 fixture is an object containing `startRow`, `endRow`, `total`, and `data` with numeric `id`, `thumb`, and sentinel `name`/`brand`/`seller`/other fields. Assert only `data[].id`/`data[].thumb` consumption while all sentinel fields are ignored.

```json
{
  "startRow": 0,
  "endRow": 100,
  "total": 2,
  "data": [
    {
      "id": 123,
      "name": "sentinel",
      "brand": {"name": "sentinel"},
      "seller": {"name": "sentinel"},
      "thumb": "https://cdn.example.test/photo.jpg"
    }
  ]
}
```

Cover 200, `data=[]`, missing requested ID, null/empty thumb, invalid ID, boolean ID, invalid thumb type/URL, duplicate response ID, ignored extra/unrequested ID, malformed root, missing `data`, non-array `data`, 202, 401→auth, 403→upstream, 429 with safe integer `Retry-After` 0–86400 and invalid values mapping to null, every 5xx class, other status, each timeout/network class, malformed JSON, and no automatic retry. Test connection uses the same endpoint/query/header with no body and treats valid 200—including empty `data`—as AVAILABLE. No test makes a real network request or contains a real token.

Real FastAPI `TestClient` tests—not source grep—cover every route, JSON shape, status/error code, pagination bound, transaction behavior, idempotency, source mapping, and absence of a token sentinel from responses. They distinguish malformed/wrong-type transport failures with standard FastAPI 422 `detail` from valid transport with invalid business values using the PR6 domain envelope. Inspect SQLite, captured safe logs when logs are touched, and served/generated frontend state to prove the sentinel is absent. Photo tests assert only `NOT_REQUESTED`, `AVAILABLE`, and `MISSING`; source failures remain errors rather than per-item statuses.

### 19.3 Frontend and keystore

`tests/test_frontend_contract.py` asserts owned-Product entry, active context, query controls/period/stale state, candidate selected count, manual add, revision feedback, placeholders, settings controls, script order, accessible live states, and no credential use through localStorage, sessionStorage, IndexedDB, cookies, or URL construction. It verifies Lock wiring clears visible/transient UI state.

`tests/keystore_contract.mjs` runs with `node tests/keystore_contract.mjs` and imports/evaluates the committed classic script using Node built-in Web Crypto only. It asserts:

- exact payload roundtrip including UTF-8 token;
- wrong password and one-byte ciphertext corruption both fail without plaintext;
- independent encryptions have different 16-byte salts, 12-byte IVs, and ciphertext;
- exact envelope keys/format/version/PBKDF2/SHA-256/600000/AES-GCM/256/128 values;
- canonical padded base64 and exact decoded lengths;
- plaintext sentinel does not occur anywhere in serialized envelope;
- unsupported format/version, missing/extra fields, bad base64, bad lengths, and invalid payload are rejected;
- password is not normalized and save confirmation behavior is covered by frontend tests.

CI runs:

```text
python -m pytest -q
node --check frontend/assets/js/app.js
node --check frontend/assets/js/keystore.js
node tests/keystore_contract.mjs
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Node in CI is only a syntax/contract-test tool; there is no npm install and no Node end-user dependency. Windows smoke makes no MPStats request and existing portable startup remains green.

## 20. Manual acceptance

1. Start SCOZ with `start.bat` and use an owned catalog Product with PR5 query data.
2. Open competitor selection, select relevant queries, save, close, and reopen; confirm period and selection persist.
3. Confirm candidates correspond only to saved queries and own Product is absent.
4. Enter a valid MPStats token and probe SKU, test connection, then load photos.
5. Corrupt/lock the token and retry photos; confirm local candidates and selections remain and placeholders/errors appear.
6. Add a missing competitor by canonical Ozon SKU; confirm it is selectable and does not enter the Products catalog.
7. Save composition and see revision 1; change members and see revision 2; save the same unordered set and see no new revision.
8. Save encrypted credentials with matching password confirmation and confirm exact filename.
9. Reload the tab and confirm credentials are absent; open the encrypted file with its password and test the source.
10. Lock credentials and confirm memory-dependent actions, inputs, statuses, and preview URLs clear.

No benchmark calculation is part of this acceptance.

## 21. Portable Windows invariants

PR6 preserves repository ZIP → extract → `start.bat`; project-local embeddable Python; no system Python, end-user Node/npm, frontend build, admin rights, Docker, or machine-bound credential storage. Production frontend assets remain committed. `httpx` installs through the existing pinned project-local pip workflow. The encrypted file is portable rather than account/machine bound. Runtime validation/repair/rebuild never deletes user-owned `data/`; credentials are never stored there by SCOZ.

## 22. PR7 handoff boundary

After PR6, the available inputs are: an owned Product, persisted current relevant-query selection, deterministic local candidate evidence, a specific immutable `BenchmarkSetRevision` and members, and optional transient thumbnail URLs.

PR7 receives a specific revision plus compatible source facts. Only PR7 may compute median, P25/P75, sample, delta, status, confidence, and advertising intensity. PR6 does none of that mathematics, persists no derived result, and does not copy competitor metrics into the revision.

## 23. Approval and implementation gate

This specification freezes schema, domain/repository/application boundaries, adapter, REST JSON, UI states, cryptography, dependencies, file map, errors, and tests. It contains no implementation sequence. Implementation begins only after independent spec review, corrections, merge, and explicit user approval, followed by a separate execution-grade PR6 Implementation Plan.

The implementation must stop rather than improvise if official MPStats documentation contradicts section 11 or if any canonical authority conflict is discovered.
