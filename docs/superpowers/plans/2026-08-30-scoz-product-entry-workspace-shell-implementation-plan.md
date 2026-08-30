# Product Entry & Workspace Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Draft for user approval  
**Planning base:** `8a7bac1e74b6f2f12a4c6dc945870b068bce553e` (`main` after merge of PR #92)  
**Goal:** Implement the approved corrective Product Entry & Workspace Shell slice so SCOZ has a bounded `Мои товары` + searchable catalog entry flow, restorable Product Workspace routing, factual Evidence Rail, own-SKU switching, and the existing PR6/PR7 competitor/comparison flow under the Workspace parent before PR8 Diagnostics begins.

**Architecture:** Preserve the existing local FastAPI + SQLite + committed vanilla HTML/CSS/JavaScript architecture. Add one focused Product Workspace read model/service over already persisted facts, keep SQL inside repositories, keep PR6 query/benchmark facts authoritative in their existing modules, and move frontend navigation from transient DOM state to a small hash-route owner without introducing a router/framework. The new shell reports factual readiness only; it does not create diagnosis, new analytics, fake ProductSnapshot data, or a generic readiness framework.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLite, pytest, committed vanilla JavaScript, HTML/CSS, Node for repository development/CI contract checks only, PowerShell Windows portable smoke.

**Spec:** `docs/superpowers/specs/2026-08-29-scoz-product-entry-workspace-shell-implementation-spec.md`

## Global Constraints

- Implement from the current implementation branch based on current `main`; never reset implementation work to the older spec analysis SHA.
- No database migration in this corrective PR.
- `Product.is_owned` remains authoritative ownership state.
- `Мои товары` includes every owned Product with exactly one canonical unscoped Ozon product identity, even when ProductSnapshot is missing.
- Full Ozon catalog remains ProductSnapshot-backed.
- Never fabricate title, seller, brand, report freshness, ProductSnapshot, metric, benchmark, or readiness facts.
- `GET /api/products` becomes searchable/paginated with default page size **50** and no old top-level `readiness` field.
- Add only `/api/products/owned` and `/api/products/{product_id}/workspace-context`; do not create a generic product/readiness API family.
- Workspace shell uses a narrow relevant-query summary read and must not materialize full relevant-query options for Evidence Rail.
- Server title search is Unicode-case-insensitive for Russian text; Ozon ID search is canonical ASCII-digit prefix matching.
- Hash/history state owns global section, catalog committed query/page, and active Product Workspace route.
- This corrective PR has only the implemented `Конкуренты` Workspace section. Do not render a one-item tab strip or dead `Диагностика`, `Поиск`, or `Разгон` navigation.
- Product Context Header + Evidence Rail show factual Product/Search/Comparison readiness only. No aggregate score.
- Benchmark revision stays out of the compact Evidence Rail; it remains available inside comparison/competitor detail.
- Existing PR6/PR7 business operations are relocated, not rewritten mathematically.
- Touched user-facing comparison vocabulary is Russian: `Сравнение с группой`, `Результат`, `Трафик`, `Конверсия`, `Предложение`, `Реклама`.
- Shared Product shell migrates to canonical 224px sidebar, 28/34 page-title scale, 24–32px page padding, fluid workspace, canonical tokens, and one global scrollbar baseline.
- No frontend framework, package runtime dependency, generic router, component framework, source-capability framework, persistent job platform, or import/event-loop refactor.
- No user-side frontend build; production frontend assets remain committed.
- No `alert()`, `confirm()`, or `prompt()`.
- Preserve loopback-only/same-origin/security and current-tab credential contracts.
- Existing Data and Settings workflows remain functionally intact.
- Production implementation follows RED → GREEN → refactor for every behavioral slice.
- Codex works only in the user-selected implementation branch. It does not create/switch/delete branches, push, create/merge PRs, or ask the user to run development commands locally.
- GitHub Actions is authoritative for the post-push Windows portable acceptance run.

## Current `main` Anchors

Verified at the planning base:

- `backend/persistence/repositories/products.py` returns catalog `dict` rows, requires `EXISTS(product_snapshots)`, sorts owned-first, and has no search/owned-list/single ProductEntry projection.
- `backend/persistence/repositories/benchmark_selection.py::list_relevant_query_options()` materializes detailed rows and separately derives latest period/readiness.
- `backend/main.py::get_products()` defaults to 100 and returns `items,total,readiness`.
- `frontend/index.html` has transient button navigation, `#products-list` card wall, and separate `#competitors-workspace`.
- `frontend/assets/js/app.js` stores the loaded catalog in `productCatalog` and opens competitors from that transient object.
- `.github/workflows/ci.yml` does not currently run `product_navigation_contract.mjs` or `competitor_state_contract.mjs`.
- `UX-CONTRACT.md` migration items 1, 2, 3, 5, 6, 7, 8, 9, and 11 are expected to resolve here. Item 4 remains partially open because compact progressive disclosure for the competitor editor is explicitly outside this corrective scope.

---

### Task 1: Add exact Product Workspace read-domain contracts

**Files:**
- Create: `backend/domain/product_workspace.py`
- Create: `tests/test_product_workspace_service.py`

**Interfaces:**
- Consumes: `RelevantQueryReadiness`, `SourcePeriod` from `backend.domain.benchmark_selection`.
- Produces: `ProductDataStatus`, `ProductEntry`, `ProductWorkspaceQueryContext`, `WorkspaceBenchmarkStatus`, `ProductWorkspaceBenchmarkContext`, `ProductWorkspaceContext`, `ProductCatalogPage`, `OwnedProductList`.

- [ ] **Step 1: Write the RED domain-contract test**

In `tests/test_product_workspace_service.py`:

```python
from dataclasses import fields

from backend.domain.product_workspace import (
    OwnedProductList,
    ProductCatalogPage,
    ProductDataStatus,
    ProductEntry,
    ProductWorkspaceBenchmarkContext,
    ProductWorkspaceContext,
    ProductWorkspaceQueryContext,
    WorkspaceBenchmarkStatus,
)


def test_product_workspace_domain_contract_is_exact():
    assert [item.value for item in ProductDataStatus] == ["AVAILABLE", "MISSING"]
    assert [item.value for item in WorkspaceBenchmarkStatus] == [
        "CONFIGURED", "NOT_CONFIGURED"
    ]
    assert [field.name for field in fields(ProductEntry)] == [
        "product_id", "ozon_product_id", "is_owned", "title", "seller_name",
        "brand", "product_data_status", "report_generated_on",
        "report_window_days", "imported_at",
    ]
    assert [field.name for field in fields(ProductWorkspaceQueryContext)] == [
        "readiness", "latest_period", "selected_count"
    ]
    assert [field.name for field in fields(ProductWorkspaceBenchmarkContext)] == [
        "status", "revision_id", "revision", "member_count"
    ]
    assert [field.name for field in fields(ProductWorkspaceContext)] == [
        "product", "queries", "benchmark"
    ]
    assert [field.name for field in fields(ProductCatalogPage)] == [
        "items", "total", "limit", "offset"
    ]
    assert [field.name for field in fields(OwnedProductList)] == ["items", "total"]
```

- [ ] **Step 2: Run the RED test**

From repo root in the Codex shell:

```bash
python -m pytest tests/test_product_workspace_service.py::test_product_workspace_domain_contract_is_exact -q
```

Expected: FAIL because `backend.domain.product_workspace` does not exist.

- [ ] **Step 3: Create `backend/domain/product_workspace.py`**

```python
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from backend.domain.benchmark_selection import RelevantQueryReadiness, SourcePeriod


class ProductDataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"


@dataclass(frozen=True)
class ProductEntry:
    product_id: int
    ozon_product_id: str
    is_owned: bool
    title: str | None
    seller_name: str | None
    brand: str | None
    product_data_status: ProductDataStatus
    report_generated_on: date | None
    report_window_days: int | None
    imported_at: datetime | None


@dataclass(frozen=True)
class ProductWorkspaceQueryContext:
    readiness: RelevantQueryReadiness
    latest_period: SourcePeriod | None
    selected_count: int


class WorkspaceBenchmarkStatus(str, Enum):
    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True)
class ProductWorkspaceBenchmarkContext:
    status: WorkspaceBenchmarkStatus
    revision_id: int | None
    revision: int | None
    member_count: int


@dataclass(frozen=True)
class ProductWorkspaceContext:
    product: ProductEntry
    queries: ProductWorkspaceQueryContext
    benchmark: ProductWorkspaceBenchmarkContext


@dataclass(frozen=True)
class ProductCatalogPage:
    items: tuple[ProductEntry, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class OwnedProductList:
    items: tuple[ProductEntry, ...]
    total: int
```

No calculation methods, persistence, API models, or generic readiness abstraction go in this module.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m pytest tests/test_product_workspace_service.py::test_product_workspace_domain_contract_is_exact -q
git add backend/domain/product_workspace.py tests/test_product_workspace_service.py
git commit -m "feat: add product workspace read contracts"
```

Expected: PASS before commit.

---

### Task 2: Implement ProductEntry persistence projections and server catalog search

**Files:**
- Modify: `backend/persistence/repositories/products.py`
- Modify: `tests/test_product_repository.py`

**Interfaces:**
- Produces:
  - `count_ozon_products(*, query: str | None = None) -> int`
  - `list_ozon_products(*, limit: int, offset: int, query: str | None = None) -> tuple[ProductEntry, ...]`
  - `list_owned_ozon_products() -> tuple[ProductEntry, ...]`
  - `get_ozon_product_entry(product_id: int) -> ProductEntry | None`
- Preserves `any_owned()` exactly for the existing PR3 import-result readiness path.

- [ ] **Step 1: Write RED projection tests**

Replace the old identity-only-owned assertion with a test that preserves the catalog invariant and adds the new ownership projection:

```python
def test_identity_only_owned_product_is_my_product_but_not_full_catalog(repository):
    repo, _ = repository
    product = repo.resolve_or_create_ozon_product("12345")
    repo.set_owned(product.id, True)

    assert repo.list_ozon_products(limit=10, offset=0) == ()
    assert repo.count_ozon_products() == 0
    assert repo.any_owned() is False

    owned = repo.list_owned_ozon_products()
    assert len(owned) == 1
    assert owned[0].product_id == product.id
    assert owned[0].ozon_product_id == "12345"
    assert owned[0].product_data_status is ProductDataStatus.MISSING
    assert owned[0].title is None
    assert owned[0].seller_name is None
    assert owned[0].brand is None
    assert owned[0].report_generated_on is None
    assert owned[0].report_window_days is None
    assert owned[0].imported_at is None
```

Update the separate non-owned identity-only catalog test to expect `()` rather than the current list.

- [ ] **Step 2: Add RED search/current-observation tests**

Use the existing `ProductSnapshotRepository` and `PAYLOAD_FIELDS` fixture pattern already used in PR7 tests. Seed snapshot-backed titles/IDs and prove:

```python
assert [item.ozon_product_id for item in repo.list_ozon_products(
    limit=50, offset=0, query="смеситель"
)] == ["100000001"]
assert [item.ozon_product_id for item in repo.list_ozon_products(
    limit=50, offset=0, query="1000"
)] == ["100000001", "100000002"]
assert repo.count_ozon_products(query="смеситель") == 1
```

Add explicit assertions for all of these cases:

```text
lowercase Russian query finds differently-cased title
seller-only text does not match
brand-only text does not match
ASCII digit query matches Ozon ID prefix
non-digit query does not activate ID-prefix branch
% and _ in title query are literal characters, not LIKE wildcards
catalog order = casefold(title), Ozon ID length, Ozon ID text, Product.id
selected presentation = report_generated_on DESC, report_window_days DESC, revision DESC
later imported_at on older business observation does not win
```

- [ ] **Step 3: Add RED direct-call validation and ambiguous-identity tests**

Repository calls must accept only already-normalized non-empty query text:

```python
for invalid in ("", "   ", " x", "x ", "x" * 201):
    with pytest.raises(ValueError):
        repo.count_ozon_products(query=invalid)
```

Also prove a Product with zero or more than one unscoped `ozon_product_id` identity is not a canonical ProductEntry:

```python
assert repo.get_ozon_product_entry(product_with_two_ozon_ids.id) is None
```

and does not duplicate rows in catalog/owned projections.

- [ ] **Step 4: Run repository RED**

```bash
python -m pytest tests/test_product_repository.py -q
```

Expected: FAIL on missing methods/new signatures/types.

- [ ] **Step 5: Register only the focused SQLite casefold function**

In `ProductRepository.__init__`:

```python
self._conn.create_function(
    "SCOZ_CASEFOLD",
    1,
    lambda value: value.casefold() if isinstance(value, str) else "",
    deterministic=True,
)
```

Do not add schema columns/indexes or a generic normalization framework.

- [ ] **Step 6: Build one canonical-identity/current-presentation projection**

Use an identity CTE/subquery constrained to:

```sql
source = 'ozon'
AND identity_type = 'ozon_product_id'
AND source_account_scope = ''
GROUP BY product_id
HAVING COUNT(*) = 1
```

Select the ProductSnapshot presentation observation with exact business ordering:

```sql
ORDER BY ps.report_generated_on DESC,
         ps.report_window_days DESC,
         ps.revision DESC
LIMIT 1
```

Map rows to `ProductEntry`, using `date.fromisoformat` and existing `datetime_from_db`. Missing ProductSnapshot maps to `ProductDataStatus.MISSING` and null snapshot-derived fields.

- [ ] **Step 7: Implement exact repository query validation**

Use one private validator with these semantics:

```python
def _validate_catalog_query(query: str | None) -> None:
    if query is None:
        return
    if query != query.strip() or not query or len(query) > 200:
        raise ValueError("invalid product query")
```

`list_ozon_products` additionally validates `1 <= limit <= 100` and `offset >= 0`. Repository does not trim; application service owns normalization.

- [ ] **Step 8: Implement literal title search and numeric ID prefix once for list/count**

Use literal substring semantics, not `LIKE`:

```sql
instr(SCOZ_CASEFOLD(COALESCE(s.title, '')), SCOZ_CASEFOLD(?)) > 0
```

When `query.isascii() and query.isdigit()` is true, OR that condition with:

```sql
substr(i.identity_value, 1, length(?)) = ?
```

Reuse the same filter builder/parameters for count and list so their semantics cannot drift.

- [ ] **Step 9: Implement catalog, owned-list, and single-entry reads**

Full catalog:

```text
canonical identity required
ProductSnapshot required
ORDER BY SCOZ_CASEFOLD(title), length(ozon_product_id), ozon_product_id, Product.id
```

Owned list:

```text
canonical identity required
is_owned = 1
LEFT JOIN selected ProductSnapshot presentation
fallback display-key for ordering = "Ozon SKU <id>"
```

Single entry:

```text
lookup by Product.id
canonical identity required
LEFT JOIN selected ProductSnapshot presentation
None if Product or canonical identity projection is unavailable
```

Leave `any_owned()` unchanged.

- [ ] **Step 10: Update exact repository public-boundary assertion, run GREEN, commit**

Add `list_owned_ozon_products` and `get_ozon_product_entry` to the existing method-set test, then run:

```bash
python -m pytest tests/test_product_repository.py -q
git add backend/persistence/repositories/products.py tests/test_product_repository.py
git commit -m "feat: add searchable product entry projections"
```

Expected: PASS before commit.

---

### Task 3: Add the narrow relevant-query summary read

**Files:**
- Modify: `backend/persistence/repositories/benchmark_selection.py`
- Modify: `tests/test_benchmark_selection_repository.py`

**Interfaces:**
- Produces `BenchmarkSelectionRepository.get_relevant_query_summary(product_id: int) -> ProductWorkspaceQueryContext`.
- Must match detailed relevant-query readiness semantics without calling/materializing `list_relevant_query_options()`.

- [ ] **Step 1: Write RED equivalence tests for all three states**

Add:

```python
def _assert_summary_matches_detail(repo, product_id):
    detail = repo.list_relevant_query_options(product_id)
    summary = repo.get_relevant_query_summary(product_id)
    assert summary.readiness is detail.readiness
    assert summary.latest_period == detail.latest_period
    assert summary.selected_count == detail.selected_count
```

Exercise:

```text
no query snapshots -> NO_OWN_QUERY_DATA / period None / count 0
current query period + no selection -> EMPTY_SELECTION / count 0
saved selection -> READY / count > 0
```

- [ ] **Step 2: Write RED no-materialization test**

```python
def test_summary_does_not_call_detailed_query_read(tmp_path, monkeypatch):
    _, conn, repo, own, _, _ = _repo_case(tmp_path)
    monkeypatch.setattr(
        repo,
        "list_relevant_query_options",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("detailed rows must not be loaded")
        ),
    )
    summary = repo.get_relevant_query_summary(own.id)
    assert summary.readiness is RelevantQueryReadiness.EMPTY_SELECTION
    conn.close()
```

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_benchmark_selection_repository.py -q
```

Expected: FAIL because the new read does not exist.

- [ ] **Step 4: Implement the focused summary**

Import `ProductWorkspaceQueryContext`. Query only:

1. latest **current revision** ProductQuerySnapshot period ordered `period_end DESC, period_start DESC`;
2. `COUNT(*)` from `product_relevant_queries` for the Product.

Map exactly:

```python
readiness = (
    RelevantQueryReadiness.NO_OWN_QUERY_DATA
    if latest_period is None
    else RelevantQueryReadiness.READY
    if selected_count > 0
    else RelevantQueryReadiness.EMPTY_SELECTION
)
return ProductWorkspaceQueryContext(readiness, latest_period, selected_count)
```

Do not call the detailed read.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest tests/test_benchmark_selection_repository.py -q
git add backend/persistence/repositories/benchmark_selection.py tests/test_benchmark_selection_repository.py
git commit -m "feat: add product workspace query summary"
```

Expected: PASS before commit.

---

### Task 4: Add `ProductWorkspaceService`

**Files:**
- Create: `backend/application/product_workspace.py`
- Modify: `tests/test_product_workspace_service.py`

**Interfaces:**
- Produces:
  - `list_catalog(*, query, limit, offset) -> ProductCatalogPage`
  - `list_owned() -> OwnedProductList`
  - `get_context(product_id) -> ProductWorkspaceContext`
- Reuses `ProductNotFound`, `ProductNotOwnedError`, ProductRepository reads, query summary, and existing `get_benchmark()`.

- [ ] **Step 1: Add RED normalization/list tests**

Prove `_normalize_query` through public service calls:

```text
None -> None
whitespace-only -> None
"  Смеситель  " -> "Смеситель"
200 characters -> accepted
201 characters -> ValueError("product query too long")
```

Assert catalog returns exact `total/limit/offset`, and owned-list `total == len(items)`.

- [ ] **Step 2: Add RED complete and identity-only context tests**

Seed:

```text
owned snapshot-backed Product + ProductQuerySnapshot + saved relevant query + benchmark revision
owned canonical identity-only Product with no ProductSnapshot/query/benchmark
```

Assert complete context has `AVAILABLE`, `READY`, selected count, `CONFIGURED`, revision/member count. Assert identity-only context has `MISSING`, `NO_OWN_QUERY_DATA`, `NOT_CONFIGURED`, null revision fields, member count 0.

- [ ] **Step 3: Add RED errors and PR7 separation test**

```python
with pytest.raises(ProductNotFound):
    service.get_context(999_999)
with pytest.raises(ProductNotOwnedError):
    service.get_context(non_owned.id)
```

Also assert the source of `backend.application.product_workspace` does not import or instantiate `CoreBenchmarkService`; Workspace context is composition/readiness, not PR7 calculation.

- [ ] **Step 4: Run RED**

```bash
python -m pytest tests/test_product_workspace_service.py -q
```

Expected: FAIL because the application service does not exist.

- [ ] **Step 5: Implement `backend/application/product_workspace.py`**

Use this exact service skeleton:

```python
class ProductWorkspaceService:
    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path

    @staticmethod
    def _normalize_query(query: str | None) -> str | None:
        if query is None:
            return None
        normalized = query.strip()
        if not normalized:
            return None
        if len(normalized) > 200:
            raise ValueError("product query too long")
        return normalized

    def list_catalog(self, *, query, limit, offset) -> ProductCatalogPage:
        normalized = self._normalize_query(query)
        with transaction(self._db_path) as connection:
            repo = ProductRepository(connection)
            return ProductCatalogPage(
                items=repo.list_ozon_products(
                    limit=limit, offset=offset, query=normalized
                ),
                total=repo.count_ozon_products(query=normalized),
                limit=limit,
                offset=offset,
            )

    def list_owned(self) -> OwnedProductList:
        with transaction(self._db_path) as connection:
            items = ProductRepository(connection).list_owned_ozon_products()
            return OwnedProductList(items=items, total=len(items))
```

`get_context()` uses one read transaction and this exact decision order:

```text
get Product -> missing => ProductNotFound
is_owned false => ProductNotOwnedError
get ProductEntry -> None => ProductNotFound
get_relevant_query_summary(product_id)
get_benchmark(product_id)
current_revision None => NOT_CONFIGURED
else => CONFIGURED with revision.id/revision/member_count
```

Do not import `CoreBenchmarkService`.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m pytest tests/test_product_workspace_service.py -q
git add backend/application/product_workspace.py tests/test_product_workspace_service.py
git commit -m "feat: add product workspace service"
```

Expected: PASS before commit.

---

### Task 5: Publish the exact Product API contract

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_ozon_products_api.py`
- Create: `tests/test_product_workspace_api.py`

**Interfaces:**
- Produces:
  - `GET /api/products?q=<optional>&limit=50&offset=0`
  - `GET /api/products/owned`
  - `GET /api/products/{product_id}/workspace-context`
- Preserves `PATCH /api/products/{product_id}/ownership` strict boolean semantics.

- [ ] **Step 1: Write RED catalog response/validation tests**

Replace old readiness/owned-first expectations with:

```python
body = client.get("/api/products").json()
assert set(body) == {"items", "total", "limit", "offset"}
assert body["limit"] == 50
assert body["offset"] == 0
assert "readiness" not in body
```

Add:

```text
limit=0 -> 422
limit=101 -> 422
offset=-1 -> 422
q length 201 -> 422
Russian case-insensitive q -> matching result
numeric prefix q -> matching result
```

Keep existing strict ownership tests for string/bool/int body behavior.

- [ ] **Step 2: Write RED owned/context endpoint tests**

In `tests/test_product_workspace_api.py`, seed owned identity-only, owned snapshot-backed, and non-owned Products. Assert identity-only `/owned` row exactly has:

```json
{
  "product_id": 23,
  "ozon_product_id": "123456789",
  "is_owned": true,
  "title": null,
  "seller_name": null,
  "brand": null,
  "product_data_status": "MISSING",
  "report_generated_on": null,
  "report_window_days": null,
  "imported_at": null
}
```

Use the actual seeded `product_id` rather than hardcoding 23 in the assertion.

Assert workspace outer shape is exactly `{product,queries,benchmark}`. Missing Product returns PR6 `PRODUCT_NOT_FOUND` 404 envelope; non-owned returns `PRODUCT_NOT_OWNED` 409 envelope.

- [ ] **Step 3: Run API RED**

```bash
python -m pytest tests/test_ozon_products_api.py tests/test_product_workspace_api.py -q
```

Expected: FAIL on old catalog shape and missing endpoints.

- [ ] **Step 4: Add `_product_workspace_service()` and replace `get_products()`**

```python
def _product_workspace_service():
    return ProductWorkspaceService(db_path=resolve_db_path())


@app.get("/api/products")
def get_products(
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return _json(
        _product_workspace_service().list_catalog(
            query=q, limit=limit, offset=offset
        )
    )
```

- [ ] **Step 5: Add owned/context GET routes using existing error mapping**

```python
@app.get("/api/products/owned")
def get_owned_products():
    return _json(_product_workspace_service().list_owned())


@app.get("/api/products/{product_id}/workspace-context")
def get_product_workspace_context(product_id: Annotated[int, Path(gt=0)]):
    try:
        return _json(_product_workspace_service().get_context(product_id))
    except (ProductNotFound, ProductNotOwnedError) as error:
        return _pr6_error_response(error)
```

Do not alter PATCH ownership response/error semantics in this task.

- [ ] **Step 6: Run API + PR6/PR7 regressions and commit**

```bash
python -m pytest tests/test_ozon_products_api.py tests/test_product_workspace_api.py -q
python -m pytest tests/test_benchmark_selection_api.py tests/test_core_benchmark_api.py -q
git add backend/main.py tests/test_ozon_products_api.py tests/test_product_workspace_api.py
git commit -m "feat: expose product workspace read APIs"
```

Expected: both test commands PASS before commit.

---

### Task 6: Add a pure hash-navigation contract

**Files:**
- Create: `frontend/assets/js/product_navigation.js`
- Create: `tests/product_navigation_contract.mjs`
- Modify: `frontend/index.html` only to load the helper before `app.js`.

**Interfaces:**
- Exposes `ScozProductNavigation.parseHash`, `serializeRoute`, `documentTitle`.
- Route shapes:

```javascript
{kind:"products", query:"", page:1}
{kind:"workspace", productId:17, section:"competitors"}
{kind:"data"}
{kind:"settings"}
{kind:"invalid", reason:"INVALID_ROUTE"}
```

- [ ] **Step 1: Write RED Node contract**

Create `tests/product_navigation_contract.mjs` using Node `vm`. Assert:

```javascript
assert.deepEqual(nav.parseHash("#products"), {
  kind:"products", query:"", page:1,
});
assert.equal(
  nav.serializeRoute({kind:"products", query:"смеситель кухня", page:3}),
  "#products?q=%D1%81%D0%BC%D0%B5%D1%81%D0%B8%D1%82%D0%B5%D0%BB%D1%8C+%D0%BA%D1%83%D1%85%D0%BD%D1%8F&page=3"
);
assert.deepEqual(nav.parseHash("#products/17/competitors"), {
  kind:"workspace", productId:17, section:"competitors",
});
assert.equal(nav.documentTitle({kind:"products",query:"",page:1}), "Товары — SCOZ");
assert.equal(
  nav.documentTitle({kind:"workspace",productId:17,section:"competitors"}, "Смеситель"),
  "Смеситель · Конкуренты — SCOZ"
);
```

Also prove invalid handling for page 0/negative/non-integer, Product ID 0/negative/non-canonical integer, unknown section, dead `diagnostics`, decoded q >200, unknown global route, and prove Unicode round-trip/default omission.

- [ ] **Step 2: Run RED**

```bash
node tests/product_navigation_contract.mjs
```

Expected: FAIL because the asset does not exist.

- [ ] **Step 3: Implement pure `product_navigation.js`**

Use an IIFE and `URLSearchParams`. This module does **not** touch DOM, fetch, or history. It exposes only:

```javascript
root.ScozProductNavigation = Object.freeze({
  parseHash,
  serializeRoute,
  documentTitle,
});
```

Rules:

```text
empty hash logically maps to Products page 1
#products is canonical empty-query/page-1 form
q/page only for Products route
productId must be positive canonical decimal integer
only competitors is accepted Workspace section
#data and #settings are exact
malformed/unknown route returns invalid object, never throws
```

- [ ] **Step 4: Load helper before `app.js`, run GREEN, commit**

Add to `frontend/index.html` immediately before `app.js`:

```html
<script src="/assets/js/product_navigation.js" defer></script>
```

Then:

```bash
node --check frontend/assets/js/product_navigation.js
node tests/product_navigation_contract.mjs
git add frontend/assets/js/product_navigation.js frontend/index.html tests/product_navigation_contract.mjs
git commit -m "feat: add product workspace navigation contract"
```

Expected: syntax PASS and contract prints `product navigation contract: PASS`.

---

### Task 7: Replace the Product card wall with independent `Мои товары` + paginated catalog surfaces

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/assets/js/app.js`
- Modify: `frontend/assets/css/app.css` only for minimal new Product-entry layout; canonical shell/token migration is Task 9.
- Modify: `tests/test_frontend_contract.py`

**Interfaces:**
- Consumes Task 5 APIs and Task 6 route helper.
- Produces functional Products/Data/Settings routing and Product management. It does **not** expose a Workspace-opening action until Task 8 makes that destination functional.

- [ ] **Step 1: Write RED Product-entry frontend contract**

Require hooks:

```text
owned-products-status
owned-products-list
catalog-search
catalog-search-clear
catalog-status
catalog-table
catalog-table-body
catalog-range
catalog-prev
catalog-next
product-workspace
product-workspace-status
```

Assert:

```text
Мои товары and Все товары Ozon are separate sections
catalog is semantic <table>
columns = Товар | Ozon ID | Данные | Статус | Действие
old .product card renderer and Свой товар checkbox are gone
global nav is three semantic hash links
product_navigation.js loads before app.js
no dead workspace navigation is rendered
```

- [ ] **Step 2: Write RED remote-search/history contract**

Static contract requires these stable names:

```text
productUiState
CATALOG_PAGE_SIZE
loadOwnedProducts
renderOwnedProducts
loadCatalog
renderCatalog
commitCatalogSearch
setOwnership
navigateTo
renderCurrentRoute
catalogRequestId
workspaceRequestId
```

and behavior markers for `300`, `compositionstart`, `compositionend`, `history.replaceState`, `history.pushState`, `popstate`.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_frontend_contract.py -q
```

Expected: FAIL on old card/button navigation contract.

- [ ] **Step 4: Replace Product markup with stable two-surface structure**

Create in `#products-view`:

```html
<section class="products-section" aria-labelledby="owned-products-heading">
  <h2 id="owned-products-heading">Мои товары</h2>
  <div id="owned-products-status" class="status" aria-live="polite">Загрузка…</div>
  <div id="owned-products-list" class="owned-products-list"></div>
</section>
<section class="products-section" aria-labelledby="catalog-heading">
  <h2 id="catalog-heading">Все товары Ozon</h2>
  <label for="catalog-search">Поиск по названию или Ozon ID</label>
  <div class="search-control">
    <input id="catalog-search" type="search" maxlength="200" autocomplete="off">
    <button id="catalog-search-clear" type="button" aria-label="Очистить поиск" hidden>Очистить</button>
  </div>
  <div id="catalog-status" class="status" aria-live="polite"></div>
  <div class="table-wrap catalog-table-wrap">
    <table id="catalog-table">
      <thead><tr><th>Товар</th><th>Ozon ID</th><th>Данные</th><th>Статус</th><th>Действие</th></tr></thead>
      <tbody id="catalog-table-body"></tbody>
    </table>
  </div>
  <div class="catalog-pagination" aria-label="Навигация по каталогу">
    <span id="catalog-range">0 из 0</span>
    <button id="catalog-prev" type="button" disabled>Назад</button>
    <button id="catalog-next" type="button" disabled>Далее</button>
  </div>
</section>
```

Keep an empty hidden `#product-workspace` container for Task 8, but do not expose any `Открыть`/Workspace action in Task 7.

- [ ] **Step 5: Convert global nav to route links**

```html
<a class="nav-item is-active" href="#products" data-section="products" aria-current="page">Товары</a>
<a class="nav-item" href="#data" data-section="data">Данные</a>
<a class="nav-item" href="#settings" data-section="settings">Настройки</a>
```

The click handler calls `preventDefault()` and routes through the history owner; there remain exactly three global sections.

- [ ] **Step 6: Introduce focused Product UI state**

```javascript
const productUiState = {
  ownedProducts: [],
  catalogItems: [],
  catalogTotal: 0,
  catalogRequestId: 0,
  workspaceRequestId: 0,
  searchTimer: null,
  composing: false,
};
const CATALOG_PAGE_SIZE = 50;
```

Remove reliance on a full-page `productCatalog` array. No browser persistence.

- [ ] **Step 7: Implement independent owned-list and catalog loading**

`renderProductsRoute(route)` starts `loadOwnedProducts()` and `loadCatalog(route)` independently; each function owns its own status/error handling. One failed request must not clear or replace the other successful surface.

Owned-row rules in this task:

```text
fallback label = Ozon SKU <id>
MISSING = Товар определён · нужны товарные данные
snapshot freshness = business report date/window, not import timestamp
empty = Добавьте свой товар из каталога Ozon.
secondary action = Убрать из моих товаров
no Открыть action until Task 8
```

- [ ] **Step 8: Implement pessimistic `setOwnership()`**

Exact lifecycle:

```text
disable originating action only
PATCH existing ownership endpoint
on failure: keep prior ownership, preserve q/page, inline retry-capable error
on success: refresh owned list + current catalog page independently
preserve route and scroll
no confirmation dialog
```

- [ ] **Step 9: Implement catalog rendering, pagination clamp, and no-results states**

Rows:

```text
owned status = Мой товар
non-owned status = —
non-owned action = Добавить в мои товары
owned secondary action = Убрать из моих товаров
freshness = DD.MM.YYYY · N дней
```

Pagination:

```javascript
const lastPage = Math.max(1, Math.ceil(total / CATALOG_PAGE_SIZE));
```

If response `total > 0` and requested page > lastPage, replace route with lastPage and reload instead of rendering an empty invalid page. If total is 0, canonical page is 1. Display `X–Y из N`.

No imported catalog:

> `Каталог пуст. Импортируйте отчёт «Товары на Ozon» в разделе «Данные».`

Search no-results:

> `По запросу «<query>» ничего не найдено.`

with an explicit `Сбросить поиск` action that clears q and returns to page 1.

- [ ] **Step 10: Implement IME-safe 300ms remote search and stale-response defense**

`loadCatalog(route)` increments `catalogRequestId`, captures it, fetches `q/limit=50/offset`, and mutates DOM only if the generation is still current **and** current parsed route has the same query/page.

Handlers:

```text
input -> show clear; schedule 300ms only when !composing
compositionstart -> composing=true; cancel timer
compositionend -> composing=false; schedule normal 300ms commit
Enter -> cancel timer; commit immediately
Clear -> cancel timer; increment request id; replace to empty q/page1; keep input focus
```

`commitCatalogSearch()` uses replaceState so typing does not flood Back history. Pagination uses pushState.

- [ ] **Step 11: Implement only Products/Data/Settings app routing in this task**

`navigateTo(route,{replace=false,state=null}={})` serializes with `ScozProductNavigation`; `renderCurrentRoute()` handles `products`, `data`, `settings`.

Intermediate Task-7 rule is explicit: if a manually entered Workspace hash is parsed before Task 8 lands, the app replaces it with `#products` and shows `Откройте товар из раздела «Мои товары».` There is no UI path that emits a Workspace route in this commit. Task 8 replaces this temporary guard with the real Workspace renderer in the immediately following commit.

Global route rules:

```text
empty hash -> replace #products
link navigation -> pushState
global aria-current follows route
document.title = localized global title
unknown route -> replace #products + actionable route error
route change focuses visible content heading
popstate rerenders URL state
```

- [ ] **Step 12: Run GREEN and commit**

```bash
python -m pytest tests/test_frontend_contract.py -q
node --check frontend/assets/js/app.js
node tests/product_navigation_contract.mjs
git add frontend/index.html frontend/assets/js/app.js frontend/assets/css/app.css tests/test_frontend_contract.py
git commit -m "feat: replace product catalog card wall"
```

Expected: all commands PASS before commit.

---

### Task 8: Build the real Product Workspace shell and relocate PR6/PR7 flow

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/assets/js/app.js`
- Modify: `tests/test_frontend_contract.py`
- Keep `frontend/assets/js/competitor_state.js` semantics unless a tested stale-route fix is actually required.
- Keep `tests/competitor_state_contract.mjs` green.

**Interfaces:**
- Consumes `/workspace-context`, `/owned`, existing PR6 endpoints, Core Benchmark endpoint, and route helper.
- Produces fully functional `#products/<product_id>/competitors` route.

- [ ] **Step 1: Write RED Workspace/accessibility contract**

Require hooks:

```text
product-context-header
workspace-title
workspace-product-id
workspace-product-meta
product-switcher-trigger
product-switcher-popover
product-switcher-search
product-switcher-listbox
product-switcher-status
product-switcher-manage
workspace-evidence-rail
workspace-evidence-product
workspace-evidence-search
workspace-evidence-benchmark
competitors-section
unsaved-changes-dialog
```

Assert old `#competitors-workspace` wrapper is removed; existing PR6 control IDs occur once inside `#competitors-section`.

Assert no Workspace `role="tablist"`, no one-item decorative tab, and no dead future sections.

- [ ] **Step 2: Write RED switcher/stale-request contract**

Require stable names:

```text
loadWorkspaceContext
renderProductContextHeader
renderEvidenceRail
openProductSwitcher
closeProductSwitcher
filterOwnedProductsForSwitcher
isCurrentWorkspaceRequest
workspaceRequestId
```

Require browser-side normalization:

```javascript
normalize("NFKC")
toLocaleLowerCase("ru-RU")
```

Require exact accessibility markers:

```text
aria-expanded
aria-controls
aria-activedescendant
role="combobox"
role="listbox"
role="option"
aria-selected
```

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_frontend_contract.py -q
```

Expected: FAIL on missing Workspace structure/behavior.

- [ ] **Step 4: Build Workspace markup with one visible H1**

On global routes, existing generic `.page-header` remains visible. On a Workspace route, hide the generic page header and make `#workspace-title` the sole visible H1.

`#product-workspace` order:

```text
Product Context Header
Evidence Rail
h2 Конкуренты
existing relevant-query panel
existing candidate/selected group editor
Сравнение с группой drill-down
```

Move, do not duplicate, existing PR6/PR7 markup. Remove the old separate `#competitors-workspace` wrapper.

- [ ] **Step 5: Implement server-first Workspace loading and exact error states**

On Workspace route:

```javascript
const requestId = ++productUiState.workspaceRequestId;
document.title = "Загрузка… — SCOZ";
```

Fetch `/api/products/{id}/workspace-context` before loading PR6 detail. Every async write verifies both:

```text
requestId === current workspaceRequestId
current parsed route still equals same productId/competitors
```

Outcomes:

```text
200 -> render header/evidence then existing PR6 flow
404 -> Товар не найден — SCOZ + action Вернуться к товарам
409 PRODUCT_NOT_OWNED -> explain no longer in Мои товары + Управление товарами
network/local API -> preserve shell/nav + Повторить
```

- [ ] **Step 6: Render Product Context Header and Evidence Rail exactly**

Header:

```text
title or Ozon SKU <id>
Ozon ID always visible
seller/brand only when known
business report date/window only when AVAILABLE
Сменить товар native button
```

Evidence labels:

```text
AVAILABLE -> Товарные данные · DD.MM.YYYY · N дней
MISSING -> Товарные данные · нужны данные
READY -> Поиск · выбрано N запросов
EMPTY_SELECTION -> Поиск · запросы не выбраны
NO_OWN_QUERY_DATA -> Поиск · нужны данные запросов
CONFIGURED -> Группа сравнения · N товаров
NOT_CONFIGURED -> Группа сравнения · не настроена
```

No benchmark revision, diagnostic/ramp-up status, aggregate score, or color-only meaning in the compact rail.

- [ ] **Step 7: Implement authored SKU chooser with exact combobox/listbox semantics**

Markup contract:

```html
<button id="product-switcher-trigger" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="product-switcher-popover">Сменить товар</button>
<div id="product-switcher-popover" hidden>
  <input id="product-switcher-search" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="product-switcher-listbox" autocomplete="off">
  <div id="product-switcher-status" class="status" aria-live="polite"></div>
  <div id="product-switcher-listbox" role="listbox"></div>
  <button id="product-switcher-manage" type="button">Управление товарами</button>
</div>
```

Each rendered option has stable id, `role="option"`, and `aria-selected`; input `aria-activedescendant` follows keyboard-active option.

Filtering:

```javascript
const needle = input.normalize("NFKC").toLocaleLowerCase("ru-RU");
const title = (item.title || "").normalize("NFKC").toLocaleLowerCase("ru-RU");
const titleMatch = title.includes(needle);
const idMatch = /^\d+$/.test(needle) && item.ozon_product_id.startsWith(needle);
```

Keyboard:

```text
ArrowDown/ArrowUp -> active option
Enter -> select active option
Escape -> close, no navigation, restore trigger focus
click outside -> close and restore trigger focus
selection -> close and navigate; focus moves to new Workspace H1 after render
```

Loading/empty/no-results are explicit. `Управление товарами` routes to `#products`.

- [ ] **Step 8: Add `Открыть` now that the destination is functional and implement catalog scroll restoration**

Owned-list row:

```text
primary Открыть
secondary Убрать из моих товаров
```

Owned catalog row:

```text
status Мой товар
primary Открыть
secondary Убрать из моих товаров
```

Immediately before Product→Workspace push, merge into current history entry:

```javascript
history.replaceState(
  {...(history.state || {}), catalogScrollY: window.scrollY},
  "",
  location.href,
);
```

On Back/Forward to a Products history entry:

```text
parse q/page
load matching catalog page
render it
requestAnimationFrame -> scrollTo(0, that entry's catalogScrollY || 0)
never reuse scroll state from another history entry
```

- [ ] **Step 9: Make PR6 detail requests Workspace-generation safe without changing business rules**

Capture requestId/productId through relevance, benchmark, candidate, and Core Benchmark loading. Before rendering, require current generation/product route. Existing Core Benchmark request-id defense remains and is reset on SKU switch.

Do not change relevant-query selection, candidate construction, benchmark revision writes, Core Benchmark metrics, sample rules, or confidence.

- [ ] **Step 10: Rename only touched user-facing comparison vocabulary**

```text
Benchmark details -> Сравнение с группой
Core Benchmark -> Сравнение с группой
Result -> Результат
Traffic -> Трафик
Conversion -> Конверсия
Offer -> Предложение
Advertising -> Реклама
```

Internal module/enum names remain unchanged.

- [ ] **Step 11: Add deterministic unsaved-change detection**

Track persisted vs current sets, not a generic dirty boolean:

```text
relevant queries: persisted selected search_query_ids vs currently checked IDs
benchmark members: persisted current_revision member product_ids vs currently selected IDs
```

`hasUnsavedCompetitorChanges()` compares normalized sorted ID sets. A successful relevant-query save or benchmark save refreshes the persisted baseline.

- [ ] **Step 12: Guard in-app navigation and browser Back/Forward with one app-owned dialog**

Add `<dialog id="unsaved-changes-dialog">` with explicit buttons `Остаться` and `Выйти без сохранения`.

For app-initiated global nav, SKU switch, `Управление товарами`, or other route leave:

```text
if clean -> navigate immediately
if dirty -> hold pending destination; show dialog; do not mutate history yet
Остаться -> close + restore originating focus
Выйти без сохранения -> clear pending dirty edits + perform held navigation
```

For browser Back/Forward, give each SCOZ-managed history entry an integer `scozNavIndex`. On `popstate`:

```text
currentIndex = index of currently rendered route before event
destinationIndex = event.state?.scozNavIndex
if clean -> accept event and render
if dirty and destination leaves current workspace:
  compute restoreDelta = currentIndex - destinationIndex
  set restoringHistoryGuard = true
  history.go(restoreDelta) to return to current entry
  on the restoring popstate, render current route and open dialog for remembered destination
  Остаться -> remain on restored current entry
  Выйти без сохранения -> set bypassHistoryGuard = true; history.go(destinationIndex - currentIndex)
  bypass popstate -> render destination once, then clear bypass
```

If a historical entry has no SCOZ index (for example an external/direct pre-app entry), do not guess a delta; replace the current app entry with an indexed canonical state at startup and only guard SCOZ-owned intra-app entries. No browser-native confirmation is used.

- [ ] **Step 13: Run Workspace GREEN and commit**

```bash
python -m pytest tests/test_frontend_contract.py -q
node --check frontend/assets/js/app.js
node tests/product_navigation_contract.mjs
node tests/competitor_state_contract.mjs
git add frontend/index.html frontend/assets/js/app.js tests/test_frontend_contract.py
git commit -m "feat: add product workspace shell"
```

Expected: all commands PASS before commit.

---

### Task 9: Complete canonical shell/token/scrollbar migration and reconcile design ledgers

**Files:**
- Modify: `frontend/assets/css/app.css`
- Modify: `DESIGN.md` runtime-drift section only as actually resolved.
- Modify: `UX-CONTRACT.md` migration ledger only as actually resolved/partially resolved.
- Modify: `tests/test_frontend_contract.py`

- [ ] **Step 1: Write RED canonical-token/shell tests**

Require exact runtime declarations:

```text
--color-control-border-hover: #475569
--color-text-disabled: #94A3B8
--color-primary-pressed: #1E40AF
--color-success: #16A34A
--color-success-text: #166534
--color-warning: #D97706
--color-warning-text: #92400E
--color-danger: #DC2626
--color-danger-text: #991B1B
--color-info: #0284C7
--color-info-text: #075985
--radius-pill: 999px
```

Require legacy `--color-error*` definitions absent. Require:

```text
grid-template-columns: 224px 1fr
h1 28px / 34px
no .view max-width:1000px
scrollbar-color
scrollbar-width
::-webkit-scrollbar-thumb
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_frontend_contract.py -q
```

Expected: FAIL on current legacy runtime CSS.

- [ ] **Step 3: Reconcile `:root` to canonical token names/values**

Status class names may stay `.is-error`, but references use `danger*` tokens. Text uses readable text tokens:

```css
.status.is-success { color: var(--color-success-text); }
.status.is-warning { color: var(--color-warning-text); }
.status.is-error { color: var(--color-danger-text); }
.file-guidance.is-match { color: var(--color-success-text); }
.file-guidance.is-warning { color: var(--color-warning-text); }
```

No new alias token layer.

- [ ] **Step 4: Apply canonical shared shell dimensions**

```css
.app-shell { grid-template-columns: 224px 1fr; }
.content { padding: clamp(24px, 2.2vw, 32px); min-width: 0; }
h1 { font-size: 28px; line-height: 34px; }
.view { width: 100%; max-width: none; }
```

Preserve narrow fallback with all three global labels/actions.

- [ ] **Step 5: Style the Product controls with existing tokens**

Cover exact classes introduced by Tasks 7–8: Products sections/rows, search, pagination, context header, evidence rail, switcher, Workspace errors, dialog.

Required behavior:

```text
semantic native controls
visible hover/focus/pressed/disabled/busy
input hover = control-border-hover
internal table overflow instead of hidden columns
Evidence Rail readable without hover/color
primary Workspace no page-level horizontal scroll at >=1280 CSS px
```

- [ ] **Step 6: Add one global scrollbar baseline**

```css
:root {
  scrollbar-color: var(--color-control-border) var(--color-surface-muted);
  scrollbar-width: thin;
}
*::-webkit-scrollbar { width: 12px; height: 12px; }
*::-webkit-scrollbar-track { background: var(--color-surface-muted); }
*::-webkit-scrollbar-thumb {
  background: var(--color-control-border);
  border: 3px solid var(--color-surface-muted);
  border-radius: var(--radius-pill);
}
*::-webkit-scrollbar-thumb:hover {
  background: var(--color-control-border-hover);
}
```

Forced-colors mode yields to system behavior; never hide scrollbar.

- [ ] **Step 7: Reconcile `DESIGN.md` and `UX-CONTRACT.md` truthfully**

`DESIGN.md`: remove/update runtime-drift claims actually resolved; do not change canonical token values/North Star.

`UX-CONTRACT.md`: mark resolved only after observable implementation:

```text
1 card wall
2 pseudo-workspace entry
3 seller-query-only owned visibility
5 touched English comparison copy
6 shared Product shell dimensions
7 canonical route state
8 catalog search/pagination
9 scrollbar baseline
11 document.title routing
```

Keep competitor compact progressive-disclosure migration explicitly partial/open and Settings secret reveal open.

- [ ] **Step 8: Run GREEN + DESIGN lint and commit**

```bash
python -m pytest tests/test_frontend_contract.py -q
npx --yes -p @google/design.md@0.4.0 designmd lint DESIGN.md
git add frontend/assets/css/app.css DESIGN.md UX-CONTRACT.md tests/test_frontend_contract.py
git commit -m "style: reconcile product workspace shell"
```

Expected: frontend tests PASS; DESIGN lint has 0 errors before commit. Record warnings separately if present.

---

### Task 10: Make navigation/competitor contracts mandatory in CI and extend Windows smoke

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_frontend_contract.py`
- Modify: `tests/windows_smoke.ps1`

- [ ] **Step 1: Write RED CI command assertions**

Require workflow commands:

```text
node --check frontend/assets/js/product_navigation.js
node tests/product_navigation_contract.mjs
node tests/competitor_state_contract.mjs
```

alongside current app/keystore/import checks. No package.json or frontend build pipeline is introduced; existing `npx designmd` is repository CI tooling, not a user runtime build.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_frontend_contract.py -q
```

Expected: FAIL because workflow lacks the new mandatory commands.

- [ ] **Step 3: Extend CI JavaScript step**

```powershell
node --check frontend/assets/js/product_navigation.js
node --check frontend/assets/js/app.js
node --check frontend/assets/js/keystore.js
node --check frontend/assets/js/import_ui.js
node tests/product_navigation_contract.mjs
node tests/competitor_state_contract.mjs
node tests/keystore_contract.mjs
node tests/import_ui_contract.mjs
```

Keep Python, DESIGN lint, and full Windows smoke steps.

- [ ] **Step 4: Add mandatory `Assert-ProductWorkspaceShell` Windows helper**

Using existing `Invoke-DbPython` stdin transport, the helper always creates a fresh owned Product with exactly one canonical unscoped Ozon identity and **no ProductSnapshot**, then verifies:

```text
/assets/js/product_navigation.js -> 200
/api/products/owned -> seeded Product present, MISSING
/api/products/{id}/workspace-context -> 200
queries.readiness -> NO_OWN_QUERY_DATA
queries.selected_count -> 0
benchmark.status -> NOT_CONFIGURED
benchmark.member_count -> 0
/api/products?limit=50&offset=0 -> keys items,total,limit,offset; no readiness
```

Do not condition this assertion on pre-existing smoke fixture state.

- [ ] **Step 5: Call helper in normal started-app sequence and preserve all PR3–PR7 smoke checks**

Place it after health/core DB availability and before destructive runtime-repair/foreign-port phases. Do not turn smoke into browser automation.

- [ ] **Step 6: Run locally available GREEN checks and commit**

```bash
python -m pytest tests/test_frontend_contract.py -q
node tests/product_navigation_contract.mjs
node tests/competitor_state_contract.mjs
git add .github/workflows/ci.yml tests/test_frontend_contract.py tests/windows_smoke.ps1
git commit -m "test: cover product workspace portable flow"
```

Expected: local checks PASS. If execution environment is not Windows, explicitly report Windows smoke as pending GitHub Actions; never fake a pass.

---

### Task 11: Run complete regression, Premium, and implementation handoff gates

**Files:**
- No production file is expected to change here.
- Change `DESIGN.md` / `UX-CONTRACT.md` only if verification proves Task 9 ledger text untruthful.

- [ ] **Step 1: Run full Python suite**

```bash
python -m pytest -q
```

Expected: 0 failed tests.

- [ ] **Step 2: Run every committed JavaScript syntax/behavior contract**

```bash
node --check frontend/assets/js/product_navigation.js
node --check frontend/assets/js/app.js
node --check frontend/assets/js/keystore.js
node --check frontend/assets/js/import_ui.js
node tests/product_navigation_contract.mjs
node tests/competitor_state_contract.mjs
node tests/import_ui_contract.mjs
node tests/keystore_contract.mjs
```

Expected: all exit 0; contract scripts print PASS.

- [ ] **Step 3: Run DESIGN lint**

```bash
npx --yes -p @google/design.md@0.4.0 designmd lint DESIGN.md
```

Expected: 0 errors. Record warnings separately.

- [ ] **Step 4: Run diff integrity checks**

```bash
git diff --check main...HEAD
git status --short
git diff --stat main...HEAD
```

Expected:

```text
diff --check exit 0
working tree clean
no migration
no package.json/build output
no credentials/real reports
no unrelated Data/Settings redesign
```

- [ ] **Step 5: Run Frontend Design Premium audit when its installed script is available**

```bash
python <installed-frontend-design-premium-skill-dir>/scripts/audit_project.py . --mode report --no-write
python <installed-frontend-design-premium-skill-dir>/scripts/audit_project.py . --mode strict --no-write
```

Triage every finding. `affordance.actionless-button` is non-blocking only for a specific button whose external `addEventListener` binding is verified. Never add inline `onclick` to satisfy the auditor. Any other untriaged strict finding blocks completion. If plugin tooling is unavailable in Codex, report it as pending post-push Premium review rather than a pass.

- [ ] **Step 6: Verify the approved-spec acceptance matrix source-by-source**

Confirm code + tests for every item:

```text
owned identity-only SKU visible in My Products
full catalog still snapshot-backed
Russian case-insensitive literal title search
numeric Ozon prefix search
server pagination 50 + clamp
explicit add/remove ownership actions
workspace opens for identity-only owned Product
Product Context Header factual identity/freshness
Evidence Rail Product/Search/Comparison only
benchmark revision omitted from compact rail
own-products-only accessible SKU switcher
no one-item tablist/dead future sections
existing PR6 selection/save remains functional
PR7 comparison remains current-revision/13-metric logic
Back/Forward/reload route reconstruction
catalog q/page/scroll restoration
localized document.title
stale Product/search responses cannot overwrite new route
narrow query summary used by workspace-context
canonical runtime tokens/shell/scrollbar
no DB migration/framework/generic router/new analytics
```

- [ ] **Step 7: Record post-push browser checks honestly**

If interactive Windows Chromium is unavailable in Codex, report these as pending, not passed:

```text
1280 / 1440 / 1600 CSS px
Windows effective scaling 125–150%
200% browser/text zoom
keyboard-only global nav/search/table/SKU switcher/competitor edit
Back/Forward q/page/scroll
reload #products/<id>/competitors
unsaved-change dialog navigation
no primary Workspace page-level horizontal scroll >=1280
```

Do not ask the user to run development commands locally.

- [ ] **Step 8: Produce final implementation report**

Report exact commits/tasks, exact verification commands/results, pending environment-specific checks, confirmation that Codex did not push/open/merge PR, and any discovered spec conflict. No completion claim before fresh results are read.

---

## Post-push Merge Gate

After the user pushes the implementation branch and opens the corrective implementation PR:

```text
GitHub Actions on pushed HEAD
→ Python + JS + DESIGN lint + full Windows smoke green
→ Frontend Design Premium review on actual PR HEAD
→ every strict-auditor exception proven button-by-button
→ substantial frontend browser/device matrix
→ independent PR review
→ merge decision
```

This corrective implementation PR is **not PR8**. After it merges, PR8 gets its own PR-specific Diagnostics Implementation Spec/plan against the new `main`; PR8 must not reopen Product ownership/catalog/routing fundamentals unless implementation evidence proves a defect in this approved corrective contract.
