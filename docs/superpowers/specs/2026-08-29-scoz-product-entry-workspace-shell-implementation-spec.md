# SCOZ — Product Entry & Workspace Shell Corrective PR — Implementation Spec

## 1. Status, authority, and analysis base

**Status:** Approved. This document is the PR-specific implementation authority for one corrective Product Entry & Workspace Shell PR between the completed PR7 analytical work and PR8 Diagnostics. It does **not** renumber the canonical PR Development Plan: PR8 remains the next analytical PR after this corrective slice.

```text
PRODUCT_WORKSPACE_SHELL_SPEC_BASE_SHA=c995c163a5b5559a5ba14c0ac8cc8a2c24956058
```

The SHA above is the factual `main` analysis base after merge of PR #91 (`docs: establish SCOZ design and UX contracts`). It is not an instruction to reset a later implementation branch.

This spec is subordinate to the maintained business/domain/API contracts, Architecture Design, Preflight Decisions, canonical UI/UX Design, canonical Visual Design System, root `DESIGN.md`, root `UX-CONTRACT.md`, and the latest PR Development Plan. For source/domain facts, the PR3/PR5/PR6/PR7 implementation specs remain authoritative. For cross-screen frontend behavior, `UX-CONTRACT.md` controls where it does not conflict with those higher-precedence facts. Exact visual token values remain owned by `docs/superpowers/specs/scoz-visual-design-system.md`.

The inspected implementation base contains the following relevant facts:

- `GET /api/products` currently projects only Products that have at least one `ProductSnapshot`;
- `ProductRepository.list_ozon_products()`, `count_ozon_products()` and `any_owned()` currently use `EXISTS(product_snapshots)` and therefore hide an owned Product whose identity/ownership came from seller-queries but that has no ProductSnapshot;
- the current `Товары` frontend renders the catalog as large repeated cards with a checkbox `Свой товар` and opens the PR6 flow through `Выбрать конкурентов`;
- current global navigation and selected-product state are transient JavaScript state, not restorable URL/history state;
- the PR6 relevant-query and benchmark APIs, and the PR7 Core Benchmark API, already exist and remain authoritative business operations;
- no database migration is required to expose the already persisted Product identity/ownership state.

No unresolved authoritative-source conflict was found for this corrective scope.

---

## 2. Why this corrective PR exists

PR3 correctly implemented the first imported ProductSnapshot catalog and manual ownership selection. PR5 later introduced seller-query ownership evidence, so a Product can now be a known own Product even when no ProductSnapshot exists. The current catalog projection still requires ProductSnapshot evidence and therefore conflates two distinct concepts:

```text
Product ownership identity
!=
ProductSnapshot analytical-data readiness
```

PR #91 made that distinction canonical in `UX-CONTRACT.md` and also froze the Product entry model:

```text
no active own SKU -> Catalog First
active own SKU    -> Workspace First
```

PR8 Diagnostics needs a stable Product Workspace parent, current-SKU context, readiness presentation and restorable navigation. Building those foundations inside PR8 would mix shell/navigation correction with diagnostic business logic and would make PR8 harder to test and review. This corrective PR establishes the shell and entry workflow only.

---

## 3. Goal

After this PR, a user can:

```text
open Товары
-> see Мои товары separately from the full Ozon catalog
-> find a catalog SKU by title or Ozon ID
-> add/remove own-product membership
-> open an owned SKU even if ProductSnapshot data is missing
-> land in a stable Product Workspace
-> see factual Product/Search/Comparison readiness
-> switch to another owned SKU
-> use the already implemented Конкуренты workflow
-> return with browser Back/Forward to the same catalog search/page/scroll context
```

The Product Workspace created here is the parent shell that PR8 will later extend with `Диагностика`. This PR must not manufacture diagnostic conclusions merely to fill the new workspace.

---

## 4. Exact scope

This corrective PR includes exactly:

1. a focused Product-entry/workspace read model with no new table or migration;
2. a separate own-products projection that includes owned Ozon Products even when ProductSnapshot is absent;
3. a searchable, server-paginated full ProductSnapshot-backed Ozon catalog;
4. a focused workspace-context read endpoint built from already persisted Product identity, latest ProductSnapshot presentation data, a narrow relevant-query summary read and existing current benchmark composition;
5. hash-based navigable frontend state for global sections, catalog query/page and active Product Workspace SKU/section;
6. `Мои товары` + compact semantic catalog table replacing the current product card wall;
7. Product Context Header, authored own-SKU switcher and Evidence Rail;
8. migration of the touched shared Product shell to canonical dimensions/tokens and a global application scrollbar baseline;
9. relocation of the existing PR6/PR7 competitor UI into the `Конкуренты` Product Workspace section without changing its business operations;
10. Russian user-facing naming for the PR7 comparison UI that is touched by the relocation;
11. deterministic tests for repository/API/navigation/frontend contracts and a small Windows smoke extension.

---

## 5. Exhaustive non-goals

This PR does **not** include:

- PR8 diagnostic reason codes, causal interpretation, top 2–3 reasons, recommendations, OOS confounder logic or diagnostic confidence;
- a `Диагностика` runtime section before PR8 implements its vertical;
- PR9 Search Visibility Heatmap;
- PR10 Query Opportunity or MPStats position history;
- PR11+ public-API sync, advertising history or Ramp-up;
- new analytical metrics, new Core Benchmark mathematics, changed PR7 temporal/sample rules, persisted analytics or benchmark-history tables;
- automatic competitor selection, competitor reranking or changes to the PR6 relevant-query/benchmark domain model;
- a redesign of the complete PR6 competitor-edit workflow into the future compact progressive-disclosure target; the existing functional editor is moved into the Product Workspace and remains a separately documented migration target;
- a generic router, frontend framework, SPA build system, npm dependency for the end user, component library or state-management framework;
- a generic readiness engine, source-capability registry, universal score or progress percentage;
- a database migration or new persistent ProductWorkspace table;
- changes to Query Metrics import threading/event-loop behavior;
- unrelated Data-page or Settings-page redesign;
- secret reveal controls in Settings in this PR;
- Product photos in the Product Context Header. This PR adds no new own-product photo source and absence of a photo is not an error.

---

## 6. Canonical concepts and invariants

### 6.1 Ownership and data readiness are separate

`Product.is_owned` remains the authoritative ownership relation. Seller-query ingestion and manual ownership mutation remain the only current ways that can establish ownership under existing contracts.

A Product can therefore be:

| Ownership | ProductSnapshot | User-facing meaning |
|---|---|---|
| false | present | catalog Product, not in `Мои товары` |
| true | present | own Product with product-level source data |
| true | absent | own Product identity known; product-level source data missing |
| false | absent | identity-only Product such as a manual competitor; not shown in the full imported catalog and not shown in `Мои товары` |

The implementation must not create a fake ProductSnapshot, fake title, fake seller/brand, fake report date or fake metric to make an owned identity-only Product fit the existing catalog DTO.

Canonical user-facing readiness for an owned Product without ProductSnapshot:

> **Товар определён · нужны товарные данные**

### 6.2 Full catalog and My Products are different projections

The full Ozon catalog remains the imported `Товары на Ozon` catalog and therefore includes only canonical unscoped Ozon identities with at least one ProductSnapshot.

`Мои товары` is an ownership projection and includes every `Product.is_owned=true` Product that has a canonical unscoped Ozon identity, regardless of ProductSnapshot availability.

Identity-only non-owned competitor Products created by PR6 manual add remain outside both user-facing lists.

### 6.3 No change to Product identity

Canonical internal identity remains `Product.id`. Ozon SKU is projected from `ProductExternalIdentity(source='ozon', identity_type='ozon_product_id', source_account_scope='')`.

Title, seller, brand and ProductSnapshot URL remain presentation/source facts and never merge Products or determine ownership.

---

## 7. Focused domain/read DTOs

Add `backend/domain/product_workspace.py`. It contains read contracts only and no business calculation engine.

### 7.1 `ProductDataStatus`

```python
class ProductDataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
```

`AVAILABLE` means the Product has the selected latest current ProductSnapshot presentation observation described in section 8. `MISSING` means no ProductSnapshot exists. It is not an overall analytical-readiness score.

### 7.2 `ProductEntry`

Exact fields:

```python
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
```

Rules:

- `product_id` is the canonical internal Product ID;
- `ozon_product_id` is the canonical unscoped Ozon external identity;
- when `product_data_status == MISSING`, every ProductSnapshot-derived field is `None`;
- API does not fabricate fallback title text; UI displays `Ozon SKU <ozon_product_id>` when `title is null`;
- `report_generated_on` is business/source freshness; `imported_at` is technical provenance/update time and never substitutes for business freshness.

### 7.3 Workspace query context

Reuse the existing `RelevantQueryReadiness` enum values without inventing another search-readiness taxonomy:

```text
READY
EMPTY_SELECTION
NO_OWN_QUERY_DATA
```

Expose only:

```python
@dataclass(frozen=True)
class ProductWorkspaceQueryContext:
    readiness: RelevantQueryReadiness
    latest_period: SourcePeriod | None
    selected_count: int
```

Do not include all query rows in the workspace-context endpoint; the existing relevant-query endpoint remains the owner of that detailed dataset.

### 7.4 Workspace benchmark context

```python
class WorkspaceBenchmarkStatus(str, Enum):
    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"

@dataclass(frozen=True)
class ProductWorkspaceBenchmarkContext:
    status: WorkspaceBenchmarkStatus
    revision_id: int | None
    revision: int | None
    member_count: int
```

Rules:

- `CONFIGURED` only when an existing BenchmarkSet has a current revision;
- `member_count == len(current_revision.members)`;
- `NOT_CONFIGURED` has null revision fields and member_count 0;
- this DTO does not contain PR7 metric values or confidence.

### 7.5 `ProductWorkspaceContext`

```python
@dataclass(frozen=True)
class ProductWorkspaceContext:
    product: ProductEntry
    queries: ProductWorkspaceQueryContext
    benchmark: ProductWorkspaceBenchmarkContext
```

This is factual shell context, not a diagnostic model.

### 7.6 Page/list DTOs

These DTOs also live in `backend/domain/product_workspace.py`:

```python
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

---

## 8. ProductSnapshot presentation selection

For `ProductEntry`, when a Product has ProductSnapshot history, select one latest **current** presentation observation using the same declared business ordering already used by current Product catalog behavior and PR7 anchor semantics:

1. `report_generated_on DESC`;
2. same date: `report_window_days DESC`;
3. inside the chosen exact logical key: greatest `revision`.

`imported_at`, database ID, insert order and filename must not choose the business observation context.

This selection is only for Product identity/presentation/readiness in the catalog/header. It does not change PR7 Core Benchmark anchor selection or sample mathematics.

---

## 9. Persistence contract

Extend `ProductRepository`; SQL remains inside `backend/persistence/repositories/products.py` for Product projections. Extend `BenchmarkSelectionRepository` only with the narrow query-summary read defined below; existing detailed relevant-query reads remain unchanged.

### 9.1 Full catalog reads

Keep the existing conceptual catalog methods but extend them deliberately:

```python
count_ozon_products(*, query: str | None = None) -> int

list_ozon_products(
    *,
    limit: int,
    offset: int,
    query: str | None = None,
) -> tuple[ProductEntry, ...]
```

The methods continue to require a ProductSnapshot because they represent the imported full catalog.

Validation:

```text
1 <= limit <= 100
offset >= 0
query is None or 1..200 Unicode code points after trim
```

The application/API layer normalizes empty/whitespace query to `None`; repository rejects invalid direct calls.

### 9.2 Search semantics

Search supports exactly:

- title substring;
- Ozon Product ID prefix when the normalized query consists only of ASCII digits.

Seller and brand are display context, not search dimensions in this PR.

Title search must be Unicode-case-insensitive for Russian text. SQLite built-in `NOCASE`/`lower()` is not sufficient for Cyrillic, so the repository registers one deterministic connection-local SQL function named `SCOZ_CASEFOLD` backed by Python `str.casefold()` and uses it only for this Product projection/search/sort. This introduces no schema column, no index contract and no global generic normalization framework.

Required semantics:

```text
SCOZ_CASEFOLD(title) contains SCOZ_CASEFOLD(query)
OR
(query is ASCII digits AND ozon_product_id starts with query)
```

A digit query still also searches title text. Leading zeroes in a search prefix are allowed as ordinary search text; they do not alter or create Product identity.

### 9.3 Catalog ordering

The full catalog no longer sorts `is_owned` first because own membership has a dedicated `Мои товары` surface.

Deterministic order:

1. `SCOZ_CASEFOLD(title)` ascending;
2. canonical Ozon Product ID numerically without integer-overflow dependence: `length(identity_value) ASC`, then `identity_value ASC`;
3. `Product.id ASC` as final stable tie-breaker.

### 9.4 Own-products read

Add:

```python
list_owned_ozon_products() -> tuple[ProductEntry, ...]
```

It selects every owned Product with the canonical unscoped Ozon identity using a LEFT JOIN to the latest ProductSnapshot projection. No `EXISTS(product_snapshots)` filter is allowed.

Deterministic ordering:

1. display-key casefold where display-key is `title` when present, otherwise `Ozon SKU <ozon_product_id>`;
2. Ozon Product ID length/text;
3. Product.id.

The list is expected to remain small and is returned unpaginated in v1. If measured usage later makes that assumption false, pagination becomes a separate approved change.

### 9.5 One Product entry read

Add:

```python
get_ozon_product_entry(product_id: int) -> ProductEntry | None
```

It resolves the canonical Ozon identity and optional latest ProductSnapshot. A Product without canonical unscoped Ozon identity returns `None` for this Product-entry projection even if a raw Product row exists.

### 9.6 Narrow relevant-query summary read

Add to `BenchmarkSelectionRepository`:

```python
get_relevant_query_summary(product_id: int) -> ProductWorkspaceQueryContext
```

This method exists specifically for Product Workspace shell/readiness and must **not** call or materialize `list_relevant_query_options()`.

It computes only:

- `latest_period`: the same latest current ProductQuerySnapshot period semantics already owned by `list_relevant_query_options()` — `period_end DESC`, then `period_start DESC`, considering current revisions only;
- `selected_count`: count of rows in `product_relevant_queries` for the Product;
- `readiness`: `NO_OWN_QUERY_DATA` when no current query period exists, otherwise `READY` when `selected_count > 0`, otherwise `EMPTY_SELECTION`.

The narrow summary must remain semantically identical to the corresponding fields of the existing detailed relevant-query read. Repository tests prove equivalence for no data, data with empty selection and data with saved selection.

No generic readiness repository/framework is introduced.

### 9.7 Existing `any_owned()`

Do not reinterpret the existing `any_owned()` silently in this PR. It currently supports the PR3 Ozon Products import-result readiness and means, in practice, “there is an owned Product with ProductSnapshot data.” It must not be used by the new `Мои товары` UI or workspace availability logic.

A later cleanup may rename that import-specific helper if separately justified; this corrective PR must not change PR3 import-result semantics merely to improve a method name.

---

## 10. Application service boundary

Add `backend/application/product_workspace.py` with:

```python
class ProductWorkspaceService:
    def __init__(self, *, db_path: Path) -> None: ...

    def list_catalog(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
    ) -> ProductCatalogPage: ...

    def list_owned(self) -> OwnedProductList: ...

    def get_context(self, product_id: int) -> ProductWorkspaceContext: ...
```

### 10.1 Catalog service behavior

Normalize query exactly once:

```text
None -> None
trimmed empty -> None
trimmed non-empty length <= 200 -> preserved trimmed Unicode text
trimmed non-empty length > 200 -> ValueError("product query too long")
```

FastAPI validates the public max length before calling the service, but the service remains deterministic for direct callers/tests.

The service does not perform SQL or client-side pagination.

### 10.2 Owned-list behavior

Return the focused ownership projection from ProductRepository. `total == len(items)`.

### 10.3 Workspace-context algorithm

One read transaction:

1. load `Product` by internal path ID;
2. missing Product -> existing `ProductNotFound`;
3. `is_owned == false` -> existing `ProductNotOwnedError`;
4. load `ProductEntry`; if canonical Ozon Product identity is unexpectedly missing for an owned Product routed through this UI, return `ProductNotFound` rather than inventing an identity;
5. call `BenchmarkSelectionRepository.get_relevant_query_summary(product_id)`; do not load detailed query-option rows for the shell;
6. call existing `BenchmarkSelectionRepository.get_benchmark(product_id)` and project current revision identity/member count;
7. return `ProductWorkspaceContext`.

The service must not call the Core Benchmark service just to build Evidence Rail. Comparison configuration and comparison analytical availability are distinct; this shell reports composition only.

No business logic belongs in FastAPI route handlers or frontend JavaScript.

---

## 11. HTTP API contract

### 11.1 Catalog endpoint

Revise the existing endpoint:

```http
GET /api/products?q=<optional>&limit=50&offset=0
```

Parameters:

- `q`: optional text, max 200 characters;
- `limit`: integer 1..100, default **50**;
- `offset`: integer >=0, default 0.

Exact response shape:

```json
{
  "items": [
    {
      "product_id": 17,
      "ozon_product_id": "100000001",
      "is_owned": true,
      "title": "Товар",
      "seller_name": "Продавец",
      "brand": "Бренд",
      "product_data_status": "AVAILABLE",
      "report_generated_on": "2026-08-16",
      "report_window_days": 7,
      "imported_at": "2026-08-16T10:00:00+00:00"
    }
  ],
  "total": 1000,
  "limit": 50,
  "offset": 0
}
```

The old top-level `readiness` field is removed from this catalog response. Readiness is no longer inferred from whether the paginated ProductSnapshot catalog happens to contain an owned item.

Do not add a second legacy endpoint or compatibility alias.

### 11.2 Own-products endpoint

Add:

```http
GET /api/products/owned
```

Response:

```json
{
  "items": [ProductEntry, ...],
  "total": 3
}
```

An owned identity-only Product is returned with:

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

### 11.3 Workspace context endpoint

Add:

```http
GET /api/products/{product_id}/workspace-context
```

200 response:

```json
{
  "product": {
    "product_id": 17,
    "ozon_product_id": "100000001",
    "is_owned": true,
    "title": "Товар",
    "seller_name": "Продавец",
    "brand": "Бренд",
    "product_data_status": "AVAILABLE",
    "report_generated_on": "2026-08-16",
    "report_window_days": 7,
    "imported_at": "2026-08-16T10:00:00+00:00"
  },
  "queries": {
    "readiness": "READY",
    "latest_period": {
      "period_start": "2026-07-20",
      "period_end": "2026-08-16"
    },
    "selected_count": 7
  },
  "benchmark": {
    "status": "CONFIGURED",
    "revision_id": 31,
    "revision": 2,
    "member_count": 8
  }
}
```

Existing error mapping is reused:

```text
404 PRODUCT_NOT_FOUND  -> Товар не найден.
409 PRODUCT_NOT_OWNED  -> Выберите свой товар из каталога.
```

No new generic error envelope is introduced.

### 11.4 Ownership mutation

Keep:

```http
PATCH /api/products/{product_id}/ownership
{"is_owned": true|false}
```

It remains pessimistic/server-confirmed. The backend mutation contract is not replaced by a new `/my-products` CRUD API.

---

## 12. Frontend routing and history contract

No router dependency is introduced. Use hash-based navigation because the committed static app already serves `/`, and URL fragments never require FastAPI catch-all routing.

Add `frontend/assets/js/product_navigation.js` exposing one small pure global helper, `window.ScozProductNavigation`, and load it before `app.js`.

The module owns route parsing/serialization/normalization only. It does not perform fetches or DOM rendering.

### 12.1 Exact route states

```text
#products
#products?q=<url-encoded-query>&page=<N>
#products/<product_id>/competitors
#data
#settings
```

Canonicalization:

- `#products` means empty query, page 1;
- page 1 is omitted when serializing unless another reason requires preserving it;
- empty `q` is omitted;
- `page` is positive integer only;
- product_id is canonical positive integer only;
- the only implemented Product Workspace section in this PR is `competitors`;
- unknown section/invalid product route normalizes to stable Products context and shows an actionable route error instead of a blank screen;
- an over-200-character decoded query is invalid; do not silently truncate it.

PR8 extends the Product Workspace route set with `diagnostics`; this PR must not render or accept a dead `diagnostics` surface early.

### 12.2 Browser title

The route owner updates `document.title` independently from visible H1:

```text
Товары — SCOZ
Данные — SCOZ
Настройки — SCOZ
{Product title or Ozon SKU N} · Конкуренты — SCOZ
Загрузка… — SCOZ
Товар не найден — SCOZ
```

No token, credential, path or technical error content enters title text.

### 12.3 History behavior

- global section navigation: create a history entry;
- opening Product Workspace: create a history entry;
- changing workspace SKU: create a history entry;
- catalog pagination: create a history entry;
- debounced committed catalog search: update the current Products history entry with `history.replaceState` so every keystroke/search refinement does not flood Back history;
- Back/Forward must re-render from URL/history state, not from stale hidden DOM state.

### 12.4 Catalog scroll restoration

Before leaving Products for a Product Workspace route, persist `window.scrollY` in the current history entry, e.g. `history.state.catalogScrollY`.

When returning to the matching Products entry through Back/Forward:

1. restore q/page from the hash;
2. load the corresponding table page;
3. restore the stored scroll position after the page is rendered;
4. do not restore a scroll value belonging to a different search/page history entry.

No localStorage/sessionStorage is introduced for navigation.

---

## 13. Products entry UI

### 13.1 Overall structure

`Товары` is no longer one repeated card wall. The page contains two deliberate sections:

```text
Товары
├─ Мои товары
└─ Все товары Ozon
```

The visual register remains the canonical **Analytical Control Desk**: compact, calm, evidence-oriented, desktop-first. No redesign of the whole product brand is allowed.

### 13.2 `Мои товары`

Render all returned owned Products as compact operational rows, not giant cards.

Each row contains:

- title, or UI fallback `Ozon SKU <id>`;
- Ozon ID;
- concise factual product-data readiness;
- business observation phrase when ProductSnapshot exists;
- primary navigation action **`Открыть`**;
- secondary ownership action **`Убрать из моих товаров`**.

The removal action uses the existing ownership PATCH with `is_owned=false`, follows the same pessimistic/busy/error rules as catalog ownership mutation, and on success removes the row from `Мои товары` only after server confirmation while refreshing the corresponding catalog row/status. No confirmation dialog is required.

For `MISSING` Product data, display exactly the concept:

> **Товар определён · нужны товарные данные**

Do not display blank seller/brand placeholders as if they were facts.

If no own products exist, show an actionable empty state that points to the full catalog below:

> `Добавьте свой товар из каталога Ozon.`

The empty state is not an error.

### 13.3 Full catalog table

Use native semantic `<table>` for the read/locate workflow.

Required visible columns:

```text
Товар | Ozon ID | Данные | Статус | Действие
```

`Товар` cell:

- product title primary;
- seller and brand secondary when present.

`Данные`:

- report generated date + window, e.g. `16.08.2026 · 7 дней`;
- do not use import timestamp as the business-freshness label.

`Статус`:

- owned -> `Мой товар`;
- non-owned -> exactly `—` with neutral styling; do not invent a warning/negative status label.

`Действие`:

- non-owned primary row action -> **`Добавить в мои товары`**;
- owned primary navigation -> **`Открыть`**;
- owned removal is secondary -> **`Убрать из моих товаров`**.

The checkbox-first `Свой товар` interaction is removed from the canonical Product surface.

### 13.4 Catalog search

Visible search input:

- label/accessible name refers to title or Ozon ID;
- `maxlength=200`;
- explicit clear button appears when non-empty;
- remote request default debounce 300ms;
- IME composition prevents request while composing;
- Enter commits immediately;
- clear acts immediately, resets page 1, cancels/invalidates pending request and keeps focus in the input;
- query remains visible when a request fails;
- newer query/page request must not be overwritten by an older response.

### 13.5 Pagination

Frontend page size is frozen at **50** in this PR; there is no page-size chooser.

Show:

```text
1–50 из 1000
Назад | Далее
```

Rules:

- page = `floor(offset / 50) + 1`;
- filter/search change resets page to 1;
- if total shrinks and current page becomes out of range, clamp to last valid page and replace URL state;
- empty filtered result shows no-results copy and a clear/reset action;
- initial empty imported catalog is distinct from no-results;
- loading keeps table heading/frame/pagination region stable rather than replacing the whole page with text.

No infinite scroll.

### 13.6 Ownership mutation behavior

Mutation is pessimistic on both `Мои товары` and full-catalog surfaces:

1. disable/busy only the owning row action;
2. send existing PATCH;
3. on success refresh both `Мои товары` and the current catalog page;
4. preserve q/page/scroll context;
5. show contextual success near the affected list/row, not a mandatory global toast;
6. on failure leave ownership unchanged and provide retry-capable inline status.

Because ownership removal is reversible and low impact, no confirmation dialog is used by default.

---

## 14. Product Workspace shell

### 14.1 Entry

Opening an owned Product navigates to:

```text
#products/<product_id>/competitors
```

The route first loads `/workspace-context` and then existing competitor data as needed.

An owned Product with missing ProductSnapshot is still a valid Workspace route. Product-level analytical features that require ProductSnapshot remain unavailable; the shell explains missing source data instead of redirecting away.

### 14.2 Product Context Header

Persistent top context contains:

- Product title or fallback `Ozon SKU <id>`;
- Ozon ID;
- seller/brand only if ProductSnapshot supplies them;
- current product-data observation date/window when available;
- action **`Сменить товар`**.

No KPI wall and no fake hero banner.

If Product data is missing, header shows the Product identity and explicit missing-data state; it does not pretend that seller/brand/report context is known.

### 14.3 Evidence Rail

Evidence Rail sits directly below Product Context Header and contains only factual segments available in this PR.

#### `Товарные данные`

```text
AVAILABLE -> Товарные данные · 16.08.2026 · 7 дней
MISSING   -> Товарные данные · нужны данные
```

#### `Поиск`

Map existing `RelevantQueryReadiness` without inventing another score:

```text
READY             -> Поиск · выбрано N запросов
EMPTY_SELECTION   -> Поиск · запросы не выбраны
NO_OWN_QUERY_DATA -> Поиск · нужны данные запросов
```

When `latest_period` exists it may appear in disclosed detail, not as a fake merged freshness with ProductSnapshot.

#### `Группа сравнения`

```text
CONFIGURED     -> Группа сравнения · N товаров
NOT_CONFIGURED -> Группа сравнения · не настроена
```

Benchmark revision remains available in workspace-context and may be shown inside the `Конкуренты` section/detail where provenance is useful; it is intentionally omitted from the compact Evidence Rail.

Do not include `Диагностика`, `Разгон`, a 0–100 readiness score or a synthesized overall green/yellow/red state.

Semantic color, if used, always has text.

### 14.4 Workspace section navigation lifecycle

This PR establishes the Product Workspace route owner but **does not render a one-item tab strip/tablist**.

The only implemented Product Workspace section in this PR is `Конкуренты`, reached by the route:

```text
#products/<product_id>/competitors
```

Because there is only one peer workspace section, render its section heading/content directly below the shared Product Context Header + Evidence Rail. Do not create decorative or ARIA `tablist` UI containing only `Конкуренты`, and do not render disabled placeholders `Диагностика`, `Поиск` or `Разгон`.

PR8 adds the real `Диагностика` section. Once at least two peer route-backed workspace sections exist, PR8 introduces workspace subnavigation using semantic `<nav>` with route links and `aria-current="page"` for the active section (for example `Диагностика | Конкуренты`). Future implemented sections join that same navigation owner.

The URL/route ownership established here is therefore durable even though the visible multi-section navigation waits until there is something meaningful to navigate between.

### 14.5 `Сменить товар` switcher

Use an app-owned searchable combobox/popover because SCOZ owns query, empty state and keyboard behavior. Do not use browser `<select>` merely to avoid implementing the existing UX contract.

Data source: `/api/products/owned`.

The owned list is small, so switcher filtering is local and immediate; no remote debounce is needed while typing.

Required behavior:

- trigger is a native button;
- opening moves focus to the search/combobox input;
- list exposes current SKU marker;
- local title matching normalizes text with `String.prototype.normalize("NFKC")` and compares `toLocaleLowerCase("ru-RU")`; Ozon-ID matching remains direct digit-prefix matching. Do not claim Python `str.casefold()` semantics in browser JavaScript;
- ArrowDown/ArrowUp move active option;
- Enter selects active option;
- Escape closes without changing SKU;
- closing returns focus to `Сменить товар` unless navigation moves focus to the new Workspace heading;
- loading, empty and no-results states are explicit;
- secondary action **`Управление товарами`** navigates to `#products`;
- selected destination keeps the same implemented section (`competitors`); future sections may be retained only when meaningful and implemented for the destination SKU.

Do not create a generic component framework; keep the authored behavior focused and testable.

---

## 15. Existing Competitors and Core Benchmark relocation

The already working PR6/PR7 business operations remain intact:

- relevant-query load/save;
- candidates and pagination;
- MPStats preview request;
- manual candidate add;
- benchmark save/revision;
- Core Benchmark read.

Move the current competitor workspace markup/content into the `Конкуренты` Product Workspace section. Do not create a second copy of the PR6 workflow.

This corrective PR does **not** claim to finish the future compact progressive-disclosure redesign recorded in `UX-CONTRACT.md`. The existing expanded edit workflow may remain inside the section so long as it is no longer a separate top-level pseudo-workspace and continues to function end to end.

While touching this surface, replace obvious English user-facing labels with the canonical Russian vocabulary:

```text
Benchmark details / Core Benchmark -> Сравнение с группой
Result                            -> Результат
Traffic                           -> Трафик
Conversion                        -> Конверсия
Offer                             -> Предложение
Advertising                       -> Реклама
```

Internal enum/module names remain unchanged.

Do not change PR7 metric order, values, sample/exclusion details or readiness mathematics.

---

## 16. Shared shell and visual migration slice

Because this PR materially refactors the Product shell, it must resolve the shared-shell drift already named in `DESIGN.md` / `UX-CONTRACT.md` for the touched area rather than copying legacy values into the new Workspace.

### 16.1 Required shell target

```text
sidebar width:       224px
page title:          28px / 34px / 700
page/content padding 24–32px
analytical workspace fluid; no global .view max-width: 1000px constraint
```

At >=1280 CSS px the primary Product Workspace must not require page-level horizontal scroll. Detail tables may scroll inside their own containers.

### 16.2 Runtime token reconciliation

Use the exact canonical values from `docs/superpowers/specs/scoz-visual-design-system.md` / `DESIGN.md`. For tokens touched by the shell/components, migrate legacy runtime naming instead of adding more aliases.

At minimum, the implementation must account for the currently documented drift around:

- `danger` vs legacy `error` naming;
- accent vs readable `success-text` / `warning-text` semantics;
- `primary-pressed`;
- `text-disabled`;
- `info*`;
- `radius-pill`;
- `control-border-hover`.

Do not perform an unrelated aesthetic rewrite of every old rule. The migration slice must be complete for the shared controls/shell that this PR touches and must not leave new Product UI depending on deprecated token names.

If the implementation changes a durable system token rather than merely mapping the already approved value, update the canonical Visual Design System + `DESIGN.md` + runtime CSS together. This spec does not authorize changing canonical token values.

### 16.3 Global scrollbar baseline

`UX-CONTRACT.md` explicitly defers the scrollbar baseline until the shared app shell is materially refactored. This PR is that refactor point.

Add one application-wide baseline in `frontend/assets/css/app.css`:

- standards-based `scrollbar-color` and `scrollbar-width` where supported;
- WebKit fallback for thumb/track/hover/active;
- token-derived neutral styling;
- no hidden scrollbar;
- forced-colors/high-contrast remains system-operable;
- component classes only for geometry exceptions such as stable gutter, not to opt into the theme.

---

## 17. Async, loading, failure and stale-state behavior

### 17.1 Products load

`Мои товары` and catalog are separate requests/surfaces. One failure must not erase the other successful surface.

Initial Products screen has explicit stable loading regions for both.

### 17.2 Catalog request freshness

Catalog fetches use either AbortController or a monotonically increasing request ID. A superseded search/page response cannot overwrite the latest route state.

Route rendering verifies that the response still belongs to the active Products q/page before writing DOM.

### 17.3 Workspace context freshness

Changing SKU invalidates older workspace-context/competitor requests. An old Product response cannot overwrite a newer selected SKU header/Evidence Rail.

### 17.4 Workspace errors

- 404: show actionable `Товар не найден` state and stable route back to `Товары`;
- 409 PRODUCT_NOT_OWNED: explain that the Product is no longer in `Мои товары` and offer return to Product management;
- network/local API failure: keep shell navigable and offer retry rather than blanking the entire app.

`document.title` reflects loading/error state honestly.

### 17.5 No browser-native dialogs

No `alert()`, `confirm()` or `prompt()` is introduced. This PR has no irreversible action requiring a modal confirmation.

---

## 18. Focus, keyboard and accessibility contract

Target remains WCAG 2.2 AA where applicable to the local desktop web app.

Required:

- native `<button>`, `<a>` and semantic `<table>` elements for their normal roles;
- every enabled action has hover, `cursor:pointer`, focus-visible, pressed and disabled/busy states as applicable;
- route change focuses the new visible content heading after DOM is ready;
- table row actions are reachable in logical order;
- search clear control has localized accessible name;
- current global nav uses `aria-current` appropriately;
- this PR does not render a one-item workspace tablist; when PR8 introduces multi-section workspace navigation it uses semantic route links with `aria-current="page"` as frozen in section 14.4;
- Evidence Rail does not depend on color;
- authored SKU chooser follows combobox/listbox keyboard semantics and exposes labels/expanded/active state;
- focus is returned predictably after closing the switcher;
- no required content exists only in hover tooltip;
- 200% zoom preserves all actions/content; table may horizontally scroll internally rather than hiding columns.

---

## 19. Exact production file map

Expected production changes are limited to the following unless implementation discovers a concrete dependency that must be surfaced before proceeding:

```text
backend/domain/product_workspace.py                         NEW
backend/persistence/repositories/products.py                MODIFY
backend/persistence/repositories/benchmark_selection.py     MODIFY narrow query-summary read only
backend/application/product_workspace.py                    NEW
backend/main.py                                             MODIFY
frontend/index.html                                         MODIFY
frontend/assets/css/app.css                                 MODIFY
frontend/assets/js/product_navigation.js                    NEW
frontend/assets/js/app.js                                   MODIFY
DESIGN.md                                                   MODIFY to reconcile runtime token/shell drift actually resolved here
UX-CONTRACT.md                                              MODIFY migration-status ledger for actually resolved items
```

No migration file is expected.

The implementation must not add a frontend framework, package.json runtime dependency or compiled asset pipeline.

---

## 20. Exact test/CI file map

Expected tests:

```text
tests/test_product_repository.py                            MODIFY
tests/test_benchmark_selection_repository.py                MODIFY query-summary equivalence tests
tests/test_ozon_products_api.py                             MODIFY
tests/test_product_workspace_service.py                    NEW
tests/test_product_workspace_api.py                        NEW
tests/product_navigation_contract.mjs                      NEW
tests/test_frontend_contract.py                            MODIFY
tests/windows_smoke.ps1                                    MODIFY
.github/workflows/ci.yml                                    MODIFY to run both product_navigation_contract.mjs and competitor_state_contract.mjs
```

Existing PR6/PR7 test suites remain regression coverage and must stay green.

---

## 21. TDD requirements

Production implementation follows RED -> GREEN -> refactor for each behavioral slice. The implementation plan may decompose tasks further, but it must preserve these required regressions.

### 21.1 Repository RED tests first

Add failing tests proving:

1. owned identity-only Ozon Product appears in `list_owned_ozon_products()` with `ProductDataStatus.MISSING` and null ProductSnapshot fields;
2. identity-only non-owned Product remains absent from full catalog;
3. ProductSnapshot-backed non-owned/owned Products remain in full catalog;
4. catalog title search is Unicode-case-insensitive for Russian text;
5. numeric query matches Ozon ID prefix;
6. seller/brand-only text does not become an accidental search dimension;
7. filtered `count_ozon_products(query=...)` matches list semantics;
8. stable pagination order is title casefold -> Ozon ID length/text -> Product.id;
9. selected latest ProductSnapshot remains generated-date -> window -> revision, independent of imported_at;
10. `get_ozon_product_entry()` returns null only when Product/canonical Ozon projection is unavailable, not merely because ProductSnapshot is missing;
11. `get_relevant_query_summary()` returns the same readiness/latest-period/selected-count semantics as the detailed read without materializing query-option rows.

Update the old test that currently asserts an owned identity-only Product is invisible. The old expectation is intentionally superseded for **My Products**, while full imported catalog behavior remains ProductSnapshot-backed.

### 21.2 Application-service RED tests

Prove:

- catalog query normalization/limits;
- owned list total;
- workspace context with complete ProductSnapshot/query/benchmark data;
- workspace context for seller-query-only owned Product returns Product MISSING while preserving existing query readiness;
- workspace context uses the narrow query-summary read rather than `list_relevant_query_options()`;
- benchmark not configured maps to NOT_CONFIGURED, not an exception;
- missing Product -> ProductNotFound;
- non-owned Product -> ProductNotOwnedError;
- Core Benchmark service is not called by workspace-context construction.

### 21.3 API RED tests

Prove exact response shapes and status mappings for:

- `GET /api/products` default limit 50;
- `GET /api/products?q=...` search and total;
- invalid q length/limit/offset;
- `GET /api/products/owned` includes seller-query-only own Product;
- `GET /api/products/{id}/workspace-context` complete and missing-ProductSnapshot states;
- 404/409 errors;
- existing PATCH ownership behavior remains strict boolean and functional.

The old `/api/products` top-level `readiness` expectation is intentionally removed and tests must assert the new exact shape.

### 21.4 Navigation module RED tests

`tests/product_navigation_contract.mjs` covers pure behavior:

- parse/serialize `#products`, q/page;
- percent-encoding and Unicode round trip;
- page 1/empty query canonicalization;
- invalid page/product/query routes;
- `#products/<id>/competitors`;
- `#data`, `#settings`;
- no acceptance of future/dead `diagnostics` section;
- document-title helper output/fallback.

### 21.5 Frontend contract RED tests

At minimum assert:

- `product_navigation.js` loaded before `app.js`;
- Product page contains separate My Products and catalog containers;
- full catalog uses semantic table structure, not repeated `.product` article cards;
- checkbox `Свой товар` is no longer the canonical Product membership control;
- `Мои товары` exposes both `Открыть` and secondary `Убрать из моих товаров` actions;
- search/clear/pagination hooks exist;
- Product Context Header + Evidence Rail + SKU switcher hooks exist;
- `Конкуренты` renders as the current workspace section without a one-item `tablist` and no dead future workspace sections are rendered;
- Russian `Сравнение с группой` naming replaces touched English labels;
- route/document-title ownership exists;
- no `alert(`, `confirm(` or `prompt(` in changed product flow;
- stale request protection exists for remote catalog/workspace loads;
- local SKU switcher uses the frozen Russian-locale normalization/comparison behavior;
- import UI and keystore contracts remain present/unchanged.

Static string tests are not sufficient for all accessibility behavior; browser/manual verification remains required.

---

## 22. Windows smoke and browser verification

### 22.1 Windows smoke

Extend the existing portable smoke minimally to prove the packaged app can:

1. start normally;
2. reach `GET /api/products` with new response contract;
3. reach `GET /api/products/owned`;
4. explicitly create/seed an owned synthetic Product with a canonical Ozon identity in the smoke fixture and require `GET /api/products/{id}/workspace-context` to return HTTP 200 for that Product; ProductSnapshot/query/benchmark evidence may be absent and must map to honest missing/not-configured readiness rather than skipping this assertion;
5. serve `product_navigation.js` as a committed static asset;
6. continue serving existing PR6/PR7 endpoints.

The workspace-context smoke assertion is mandatory, not conditional on pre-existing fixture state.

Do not turn Windows smoke into a full browser automation framework.

### 22.2 Browser matrix

For this substantial Product Workspace/catalog change, manually inspect on Windows Chromium/Edge-equivalent behavior:

```text
1280 CSS px
1440 CSS px
1600 CSS px
Windows scaling/effective 125–150%
200% browser/text zoom
keyboard-only flow
```

Required user journeys:

- no own products -> add one -> opens/appears in My Products;
- remove own Product directly from `Мои товары` -> catalog status refreshes without losing q/page/scroll;
- seller-query-only own Product -> visible with missing-data readiness -> Workspace opens;
- search by lowercase Russian title against differently cased title;
- search by Ozon prefix;
- pagination -> open SKU -> Back restores q/page/scroll;
- direct reload of `#products/<id>/competitors`;
- SKU switcher keyboard selection/Escape;
- ownership API failure;
- catalog load failure while My Products succeeds and inverse;
- invalid/missing/non-owned workspace Product;
- 200% zoom and narrow desktop table overflow.

No page-level horizontal scroll is acceptable for the primary Workspace at >=1280 CSS px.

---

## 23. Frontend Design Premium verification

Implementation completion requires the project-owned checks plus the Premium checks already documented in `UX-CONTRACT.md`.

Run and record:

```text
python -m pytest -q
node --check frontend/assets/js/product_navigation.js
node --check frontend/assets/js/app.js
node --check frontend/assets/js/keystore.js
node --check frontend/assets/js/import_ui.js
node tests/product_navigation_contract.mjs
node tests/competitor_state_contract.mjs
node tests/import_ui_contract.mjs
node tests/keystore_contract.mjs
npx --yes -p @google/design.md@0.4.0 designmd lint DESIGN.md
```

`.github/workflows/ci.yml` must execute both `node tests/product_navigation_contract.mjs` and the already existing `node tests/competitor_state_contract.mjs`; neither remains manual-only after this PR touches routing/competitor placement.

Also run Frontend Design Premium static audit in report and strict modes as specified by `UX-CONTRACT.md`. `affordance.actionless-button` findings caused solely by externally attached verified `addEventListener` bindings remain the documented v1.4.0 tooling limitation; every other strict finding is blocking.

Search changed frontend code for the Premium anti-pattern catalog, including native dialogs, non-semantic click targets, uncancelled request races, hidden actions, missing clear behavior and screen-local duplicate primitives.

GitHub Actions remains authoritative for the post-push Windows CI run.

---

## 24. Migration-ledger reconciliation

If implementation resolves a drift item recorded in root `UX-CONTRACT.md`, update that ledger in the same PR so it remains truthful.

Expected resolved/partially resolved after this PR:

- product card wall -> resolved;
- Product Workspace entered only through `Выбрать конкурентов` -> resolved;
- owned seller-query-only Product invisible -> resolved;
- mixed Benchmark English labels on touched PR7 surface -> resolved;
- legacy shell max-width/sidebar/H1/padding for touched Product shell -> resolved;
- transient Product/global navigation -> resolved for canonical routes defined here;
- no catalog search/pagination -> resolved;
- no global scrollbar baseline -> resolved;
- static `<title>SCOZ</title>` behavior -> resolved for canonical navigable states.

Expected still open unless separately implemented:

- PR6 competitor editor compact/progressive-disclosure redesign;
- Settings secret show/hide affordance;
- visible multi-section Product Workspace navigation, which intentionally begins in PR8 when at least two implemented peer sections exist;
- future workspace verticals not yet implemented.

Do not delete a ledger item merely because some CSS/markup changed; mark/remove it only when its full observable behavior is actually corrected.

---

## 25. Acceptance criteria

The corrective PR is functionally acceptable only if all of the following are true:

1. a seller-query-only owned Ozon Product appears in `Мои товары` with no fabricated ProductSnapshot fields;
2. the full imported Ozon catalog remains ProductSnapshot-backed and excludes identity-only non-owned competitors;
3. the full catalog is a bounded semantic table with server search and 50-row pagination;
4. Russian-title search works case-insensitively and Ozon prefix search works deterministically;
5. ownership uses explicit action/status vocabulary, not checkbox-first UX, and an owned Product can be removed directly from `Мои товары`;
6. Product Workspace can open for any owned Ozon Product, including missing ProductSnapshot state;
7. Product Context Header always identifies the active SKU;
8. Evidence Rail reports only factual Product/Search/Comparison readiness, omits benchmark revision from its compact label and never creates an aggregate score;
9. `Сменить товар` is keyboard-operable, searches only own Products and uses the frozen Russian-locale local comparison behavior;
10. `Конкуренты` is the only implemented workspace section in this PR and no one-item tablist/dead future navigation is rendered;
11. existing PR6 competitor selection/save and PR7 Core Benchmark behavior still work under the Workspace parent;
12. browser Back/Forward and reload reconstruct global section / Product SKU / workspace section / catalog q/page state;
13. returning from SKU to catalog restores the matching search/page/scroll context;
14. localized `document.title` follows canonical route state;
15. stale requests cannot overwrite newer catalog/SKU state;
16. workspace-context uses the narrow query-summary read rather than materializing detailed query rows;
17. shell/tokens/scrollbar migration for the touched Product surface matches canonical design contracts;
18. no database migration, fake data, new analytics, framework or generic router was introduced;
19. full Python/JS/Design lint/Windows CI and applicable Premium checks pass with only explicitly triaged documented tooling false positives;
20. Windows smoke always creates an owned synthetic Ozon Product and proves its workspace-context endpoint returns HTTP 200.

---

## 26. Definition of Done and handoff to PR8

The PR is complete when:

- all approved scope above is implemented;
- required RED tests were observed before production fixes and all are GREEN afterward;
- full regression suite is green;
- GitHub Actions Windows run is green after push;
- Frontend Design Premium review finds no unresolved blocker beyond the already documented verified external-listener static-auditor limitation;
- independent PR review passes;
- `DESIGN.md` / `UX-CONTRACT.md` reflect actual post-PR runtime rather than aspirationally marking unfinished work resolved.

After this corrective PR merges, PR8 may assume the following stable parent contract:

```text
Product Workspace route exists
active own SKU is explicit
Product Context Header exists
Evidence Rail exists
catalog/My Products selection is solved
workspace route/section ownership exists
PR6/PR7 competitor/comparison flow is reachable inside that workspace
```

PR8 then adds **`Диагностика`** as a real implemented Product Workspace section and, because there will then be at least two peer sections, introduces visible route-backed workspace subnavigation (`Диагностика | Конкуренты`) using semantic links with `aria-current="page"`. PR8 owns diagnostic reason codes, OOS confounder logic, top 2–3 reasons and diagnostic presentation. PR8 must not reopen Product ownership/catalog/routing fundamentals unless implementation evidence proves a defect in this corrective contract.
