# SCOZ UX Contract

**Status:** canonical cross-screen frontend behavior contract  
**Reviewed:** 2026-08-29  
**Scope:** current and future committed HTML/CSS/JavaScript frontend; no framework requirement is introduced.

This file records durable navigation, state, feedback, dataset and recovery behavior. It does not redefine analytical formulas or source/domain semantics. Business/domain/API contracts remain authoritative for facts; `DESIGN.md` and the canonical visual design system own visual intent.

## Product context

- **Audience:** small group of trusted internal company users.
- **Primary jobs:** identify/select own Ozon SKU, diagnose it relative to direct competitors, inspect search/visibility evidence, maintain a comparable benchmark group, import/refresh source data, and understand why an analytical feature is or is not available.
- **Target market:** Ozon seller analytics in the existing internal deployment model.
- **Active locales:** Russian UI in v1.
- **Language/content register:** plain Russian product language; internal Python/domain names are not user-facing vocabulary.
- **Timezone/calendar policy:** source/business timestamps retain their source semantics; UI formats user-facing dates in Russian locale. Import time remains distinct from business observation freshness.
- **Accessibility target:** WCAG 2.2 AA where applicable to the local desktop web app; visible keyboard focus, semantic controls, text equivalents for color, 200% browser/text zoom without lost functionality.
- **Deployment scene:** local Windows app, `127.0.0.1`, same-origin browser UI, desktop-first, no user-side frontend build.

## Business-context sources

| Domain / scope | Authoritative source | Source type | Reviewed date |
|---|---|---|---|
| Repository/deployment invariants | `AGENTS.md` | Repository policy | 2026-08-29 |
| Architecture and local runtime | `docs/superpowers/specs/2026-08-13-scoz-architecture-design.md` | Architecture design | 2026-08-29 |
| Global IA, Product Workspace and UX North Star | `docs/superpowers/specs/2026-08-13-scoz-ui-ux-design.md` | Canonical UI/UX design | 2026-08-29 |
| Visual tokens, density and components | `docs/superpowers/specs/scoz-visual-design-system.md` | Canonical visual contract | 2026-08-29 |
| PR sequencing and feature availability | `docs/superpowers/plans/2026-08-13-scoz-pr-development-plan.md` | Development plan | 2026-08-29 |
| Product catalog and manual ownership | `docs/superpowers/specs/2026-08-16-scoz-pr3-ozon-products-import-implementation-spec.md` | Domain/API/UX contract | 2026-08-29 |
| Own-product queries/ownership evidence from seller queries; market query metrics | `docs/superpowers/specs/2026-08-19-scoz-pr5-query-data-import-implementation-spec.md` | Domain/API contract | 2026-08-29 |
| Relevant queries and competitor composition | `docs/superpowers/specs/2026-08-22-scoz-pr6-benchmark-selection-implementation-spec.md` | Domain/API/UX contract | 2026-08-29 |
| Core comparison mathematics and evidence | `docs/superpowers/specs/2026-08-24-scoz-pr7-core-benchmark-advertising-intensity-implementation-spec.md` | Analytics/API/UX contract | 2026-08-29 |

When these sources conflict, apply repository precedence from `AGENTS.md` and do not silently average behavior. This contract is authoritative for cross-screen frontend behavior only where it does not conflict with a higher-precedence business/domain/API source.

## Visual contract

- **Project `DESIGN.md`:** `/DESIGN.md`.
- **Token ownership model:** `docs/superpowers/specs/scoz-visual-design-system.md` remains canonical for exact token values; `DESIGN.md` records durable taste/context and approved workspace patterns.
- **Runtime design-system/token source:** `frontend/assets/css/app.css`.
- **Mapping/export/adapters:** direct CSS custom properties; no frontend build/token generator is required.
- **Token drift gate:** a system token change updates visual design system + `DESIGN.md` + runtime CSS in one changeset; feature-local one-off token values require an explicit layout reason.
- **Supported themes:** light theme v1. No dark theme is invented by this contract.
- **Design-context review policy:** any new multi-screen frontend vertical reviews `DESIGN.md`, this contract, the canonical UI/UX design and visual design system before implementation.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Global navigation | App shell | UI/UX Design + this contract | `Товары` / `Данные` / `Настройки` only | frontend contract + browser flow |
| Product Workspace navigation | Workspace tabs | UI/UX Design + this contract | implemented feature tabs only | keyboard + Back/forward + active state |
| Active SKU switching | `Сменить товар` searchable chooser | this contract | authored combobox/popover | keyboard + search + loading/empty |
| Product catalog dataset | semantic catalog table | this contract | paginated server dataset | paging/search/state restoration |
| Search field | shared search behavior pattern | this contract | local / remote | clear + IME + stale-response test |
| Upload/import | existing import-card workflow | source import specs + this contract | synchronous request / lightweight server-backed status when necessary | duplicate-submit + success/failure + reload behavior |
| Secret input | native password field + app-owned show/hide action | PR6 credential contract + this contract | masked/unmasked current field | keyboard + accessible label + no persistence |
| Scrollbar | global application stylesheet | `DESIGN.md` + visual design system | component geometry exceptions only | computed style + overflow review |
| Status/feedback | inline status/live region | this contract | success / warning / info / error / working | live-region + stable layout |
| Dialog | app-owned accessible dialog when required | this contract | modal / explicit non-modal business variant | focus trap/restore + Escape |

**Toast is deliberately not a required v1 primitive.** Existing SCOZ workflows use contextual inline feedback. If toasts are introduced later, they must become one shared system and cannot replace corrective inline errors.

## Component behavior

| Component | Default | Hover | Focus | Active | Disabled | Busy | Error |
|---|---|---|---|---|---|---|---|
| Button | semantic label; stable size | visible affordance | 3px primary focus ring | pressed state | visually disabled + no handler | stable geometry + progress cue | action-level error remains near owning block |
| Icon button | icon + accessible name | visible affordance | visible focus | pressed state | noninteractive | stable geometry | owning block explains failure |
| Input | label + readable border | stronger border where appropriate | visible focus | n/a | disabled/read-only differentiated | avoid resizing | inline text + `aria-invalid` when field-invalid |
| Secret input | masked | as input | as input + toggle reachable | show/hide only by explicit action | as input | n/a | never echo secret in error/status |
| Search | search icon/label; explicit clear when non-empty | input hover | focus stays usable after clear | committed query state | disabled only with reason | stable result surface | preserve query + actionable retry |
| Table/list | headers + bounded dataset navigation | row hover only as aid | actionable cells/controls reachable | current/selected context explicit | actions disabled with reason | headers/footprint remain | inline table state; do not blank unrelated page |
| Workspace tabs | visible labels | subtle hover | focus-visible | one current tab | unimplemented tab is not rendered | current content may show local loading | tab content owns its error |
| Evidence Rail | compact factual statuses | optional detail affordance | any interactive disclosure reachable | active detail only if user opened it | n/a | preserve prior facts during refresh | textual error/limitation, not color only |

## Information architecture and navigation

### Global IA

The global sidebar remains exactly:

1. **Товары** — own-SKU entry and Product Workspace;
2. **Данные** — source readiness, imports/sync and history;
3. **Настройки** — source credentials/connections and application settings.

Do not add global `Dashboard`, `Benchmark`, `Реклама`, `Query Opportunity`, `Кластеры`, `Analytics` or similar sections to mimic SaaS conventions.

### Product Workspace target IA

Inside an active own SKU:

- **Диагностика**;
- **Поиск**;
- **Разгон**;
- **Конкуренты**.

Feature tabs enter runtime only when the corresponding vertical is actually implemented. The target IA may be documented before all verticals ship, but the UI must not render dead placeholders or disabled future tabs without a current user action that can make them available.

### Route/state policy

The current framework-free frontend may use URL/hash state rather than introducing a router dependency. The durable requirement is behavior, not a specific library:

- active global section survives browser Back/Forward;
- active Product Workspace SKU and tab are represented in navigable state, not only transient JavaScript memory;
- catalog committed search/filter/page state can be restored after opening a SKU and returning;
- refreshing an active product route must not silently return the user to an unrelated screen;
- stale async responses cannot overwrite state after the user changes SKU/tab/query.

No localStorage/sessionStorage persistence is required merely for navigation. Product identity/selection persistence beyond normal URL/history state requires a separately approved reason.

## Products: entry, ownership and catalog

### Canonical model

The user-facing concept is **`Мои товары`**, not the database boolean `is_owned`.

There are two visual modes:

1. **Catalog First** — no active own SKU: show `Мои товары` and the management path into the catalog.
2. **Workspace First** — active own SKU: show Product Context Header + Evidence Rail + implemented workspace tabs.

### Ownership evidence

- Ozon Products report alone does **not** imply ownership.
- `seller-queries` own-product source is positive own-product evidence and may set `Product.is_owned=true` under the PR5 domain contract.
- Manual UI action can also change ownership through the existing ownership mutation contract.
- UI must not invent ownership from title, seller, brand, category or similarity.

### Owned product without ProductSnapshot

A Product that is known to be owned but lacks `ProductSnapshot` must remain visible in `Мои товары`.

Canonical readiness copy:

> **Товар определён · нужны товарные данные**

The product may open a limited Product Workspace/readiness state, but ProductSnapshot-based analytics remain unavailable and explain what source is missing.

Therefore a user-facing own-product entry projection must not require `EXISTS(product_snapshots)` merely to expose the owned Product. The implementation may add/adjust the narrow API projection needed for this UX, but must not create fake ProductSnapshot facts.

### Ownership actions

Primary catalog row action for a non-owned Product:

> **Добавить в мои товары**

Owned Product displays status:

> **Мой товар**

Removal is secondary:

> **Убрать из моих товаров**

The checkbox label `Свой товар` is not the canonical primary ownership interaction. Ownership mutation is reversible and low-risk, so no confirmation dialog is required by default. On success, update the same row/list context and announce the result. If the active SKU is removed from `Мои товары`, return to the own-product chooser/management context instead of leaving a stale Product Workspace active.

### SKU switcher

Inside Product Context Header:

> **Сменить товар**

opens a searchable chooser of own Products only.

The chooser includes:

- title;
- Ozon ID;
- concise readiness/freshness;
- current SKU marker;
- search by title/Ozon ID;
- loading, empty and no-results states;
- secondary action **Управление товарами** leading to the full catalog.

Choosing another SKU keeps the same workspace tab only when that tab exists and is meaningful for the destination SKU; otherwise fall back to the first implemented Product Workspace tab and explain readiness in content rather than producing a broken route.

## Dataset navigation

### Product catalog

Product catalog is a searchable admin dataset; canonical strategy is **server pagination**.

- default page size: **50**;
- show `X–Y из N`;
- search by Ozon ID or title;
- filter changes reset/clamp to a valid page;
- committed search/filter/page state is restorable via URL/history state;
- returning from a Product Workspace restores catalog context rather than returning to page 1/top;
- loading preserves table header and container geometry;
- no-results state says which query/filter produced no matches and offers clear/reset;
- initial empty state distinguishes `no imported catalog data` from `search returned nothing`.

Do not implement infinite scroll for this catalog. Do not render the entire potentially large catalog as vertical cards.

### My Products

`Мои товары` is expected to remain a much smaller operational list. Render all when bounded/small; if real usage later becomes large enough to hurt scanability, introduce search and pagination based on measured need rather than copying full-catalog controls pre-emptively.

### Search behavior

Remote/server search default debounce: **300ms**, IME-safe.

- do not fire while composition is active;
- explicit clear acts immediately, cancels/invalidates pending work and returns focus to input;
- superseded responses are ignored or cancelled;
- Enter may commit immediately without waiting for debounce;
- query text remains visible on error and retry.

## Product Workspace

### Product Context Header

Always keep visible:

- own product identity/title;
- Ozon ID / article where available;
- active business observation period;
- freshness/import context when relevant;
- current group-of-comparison status;
- `Сменить товар` action.

Do not turn the header into a KPI dashboard.

### Evidence Rail

Evidence Rail is the durable SCOZ readiness signature. It reports factual availability/limitations, for example:

- `Товарные данные — 16.08 · свежие`;
- `Поиск — данные есть`;
- `Группа сравнения — 8 товаров`;
- `Разгон — мало истории`.

Rules:

- no 0–100 readiness score;
- no fake aggregation of unrelated sources;
- semantic state always has text;
- clicking/disclosing a segment may explain missing/stale inputs, but the compact rail remains readable without hover;
- data refresh preserves the previous value with an explicit updating state where honest.

### Diagnostics and PR7 comparison

The user-facing goal of PR7 data is **`Сравнение с группой`**, not a separate global Core Benchmark product.

PR8 `Диагностика` should follow:

> **Ответ → причина → подтверждающие показатели → исходные данные**

and use PR7 metric comparison as evidence/drill-down. Do not start the screen with all 13 metrics at equal visual weight.

### Competitors

The default `Конкуренты` tab is a compact current-state view:

- current group size;
- revision/context;
- selected competitors summary;
- relevant-query summary;
- one explicit action `Изменить группу`.

Editing uses progressive disclosure inside the same business flow:

1. confirm relevant queries;
2. review candidate competitors;
3. confirm selected composition;
4. save a benchmark revision.

Do not keep query selection, candidate pool, selected composition and benchmark analytics permanently expanded as one long page after setup.

## Data page

`Данные` begins with a compact **readiness overview**, then import/source controls, then history.

Readiness answers what each source currently enables, for example:

- товарные данные — available/freshness;
- own-product queries — period/current product coverage;
- market query metrics — period;
- search visibility — query/cluster/context;
- analytics availability such as group comparison/search/ramp-up only where the current domain can support that statement.

Do not invent readiness for future features or claim analytic availability without the required inputs.

Import cards retain clear source identity and expected filename guidance. After success/partial success, refresh affected readiness and history so the user understands what became available.

## Settings and credentials

Credentials follow the approved browser-memory + encrypted-keystore model.

- secret fields masked by default;
- when Settings is next materially touched, provide keyboard-accessible show/hide controls with changing accessible labels;
- never put tokens/passwords in URLs, history, logs, toast/status text or persistent browser storage;
- `Проверить подключение`, encrypted save/open and `Заблокировать ключи` retain stable vocabulary;
- a source connection failure is shown near the source, with actionable retry/correction.

## Flow ledger

| Operation | Trigger | Pending | Success destination | Success feedback | Failure recovery | Focus outcome | Source ref |
|---|---|---|---|---|---|---|---|
| Add own product from catalog | `Добавить в мои товары` | row action busy; duplicate submit blocked | stay in catalog/current page | row becomes `Мой товар`; contextual status | preserve row/filter/page; retry action | same row/action region | PR3 + this contract |
| Remove own product | `Убрать из моих товаров` | action busy | stay in list; if active SKU, return to own-product chooser | contextual status | ownership unchanged; retry | originating row or own-products heading | PR3 + this contract |
| Open own SKU | `Открыть` / selecting in SKU chooser | product workspace local loading | selected SKU workspace | no redundant toast | product-level actionable error/readiness | Product Context Header | this contract |
| Switch own SKU | `Сменить товар` then choose SKU | chooser selection pending only if data load required | same meaningful workspace tab or first implemented tab | product header changes; no toast required | keep previous active SKU if load fails | Product Context Header | this contract |
| Catalog search | search field | stable table loading; stale response prevented | same catalog context | result range/count | preserve query + retry/reset | search input/result heading | this contract |
| Save relevant queries | `Сохранить запросы` | stable button busy | stay in competitors edit flow | `Запросы сохранены` | preserve selections; inline error | saved-step heading | PR6 |
| Save comparison group | `Сохранить группу` | stable button busy | compact current-state competitors view | `Группа сохранена` + revision context | preserve selection; inline error/retry | group summary heading | PR6 |
| Import source | `Импортировать` | file/card busy; duplicate submit blocked | stay on Data | success/partial/error inline + history/readiness refresh | preserve source context; retry/reselect as required | source status | PR3–PR5 |
| Test MPStats connection | `Проверить подключение` | button busy | stay in Settings/source | inline connection status | credentials preserved in current tab unless security contract requires clearing | source status / token field on correction | PR6 |
| Cancel/back from catalog/workspace | Back/global navigation | none | owning previous context | usually none | unsaved edit flow must warn before discarding | originating context/heading | this contract |

## Navigation and responsive behavior

- **Document/page title policy:** visible page title names the current user task; active SKU title is part of Product Workspace context, not a generic `Dashboard` heading.
- **Route error behavior:** unknown/invalid product route returns to a stable Products context with actionable error, not a blank workspace.
- **Breadcrumb/tab/state policy:** keep global section and Product Workspace subnavigation distinct; browser Back/Forward restores prior context.
- **Sidebar transformation:** desktop labels remain visible. Mobile-first/collapsible sidebar is not a v1 requirement; at narrow widths existing responsive fallback may stack global navigation while preserving all labels/actions.
- **Responsive table strategy:** preserve comparison semantics; product catalog may use horizontal table scroll at narrow widths rather than silently hiding identity/action columns.
- **Truncation:** product titles may truncate visually in dense tables only when full value remains available by accessible title/disclosure/detail; Ozon ID is never ambiguous.
- **Focus restoration:** after popover/dialog close return focus to trigger; after route/tab change focus the new content heading without hiding it under sticky UI.

## Overlays and feedback

- **Dialog primitive:** app-owned accessible modal dialog when confirmation/high-risk flow genuinely needs it; never browser `alert/confirm/prompt`.
- **Destructive confirmation:** reversible ownership toggle does not require confirmation by default. Future irreversible/high-impact actions require explicit app-owned confirmation.
- **Toast policy:** no toast system required in v1; contextual inline feedback is canonical. If a future feature introduces toasts, use one shared provider and never make a toast the only error/critical state.
- **Alert/banner scope:** persistent only while the underlying readiness/problem remains relevant.
- **Tooltip:** not the only way to discover required information/actions; icon-only controls require accessible names.
- **Unsaved changes:** leaving a modified relevant-query/competitor edit flow must not silently discard user changes; use app-owned confirmation for in-app navigation when unsaved state exists.
- **Layer order:** dialog > popover/chooser > ordinary content; toast layer only if later introduced.

## Async and resilience

- **Mutation default:** pessimistic for source imports, credentials, benchmark saves and ownership mutation unless a tested low-risk optimistic variant is deliberately introduced.
- **Duplicate submit:** every mutation/import disables or guards the owning action until the request settles.
- **Background refresh:** keep previous usable result visible with `Обновляем…` where the old value is still valid context.
- **Offline/network:** local same-origin failure is actionable; stale persisted data may remain visible when safe, but not presented as fresh.
- **Retry:** retry acts on the failed operation, not by reloading the entire application when narrower recovery is possible.
- **Long-running operations:** no generic job platform is required. If an operation can continue server-side after page-local state is lost or regularly exceeds a normal interactive wait, either make it fast enough to remain synchronous or expose minimal server-backed operation state that survives refresh. Do not rely only on an in-memory JavaScript `activeImport` flag for a server operation that can outlive the page.
- **Stale requests:** changing active SKU/tab/search invalidates older pending responses.
- **Multi-tab:** credentials remain current-tab memory by contract. Other application state is SQLite/source truth; do not invent cross-tab optimistic synchronization.

## Validation

- Use app-owned validation messages; do not depend on native browser validation bubbles as the product error experience.
- Invalid field errors are text, associated with the field, preserve correct user input and focus the first invalid field on submit.
- Server/domain errors map to human copy; raw traceback, SQL/XML internals and local absolute paths are not user messages.
- Sensitive fields never echo supplied values in errors.
- Duplicate submit prevention is mandatory.

## Permission and clipboard

SCOZ v1 has no account/role permission model. Do not invent role-based UI.

Clipboard actions, if introduced for SKU/technical IDs, copy exact visible/approved data and provide contextual acknowledgement. Secrets are never copied automatically and never repeated in feedback text.

## Migration status

This contract deliberately records the current frontend as a transitional implementation. The following current patterns are **legacy/drift**, not canonical precedents for future screens:

1. `#products-list` renders each catalog Product as a large card; migrate to `Мои товары` + paginated catalog table.
2. Product Workspace is currently entered through `Выбрать конкурентов` and implemented as `#competitors-workspace`; migrate to own-SKU workspace as the parent context.
3. `/api/products` currently requires ProductSnapshot evidence for catalog projection, so an owned seller-query-only Product can be invisible; future own-product entry must expose owned identity without fabricating ProductSnapshot data.
4. Current PR6/PR7 screen keeps relevant queries, candidates, selected competitors and Core Benchmark in one expanded workflow; migrate to compact `Конкуренты` current-state + explicit edit flow and evidence drill-down.
5. Current UI mixes Russian and English user-facing labels (`benchmark`, `Benchmark details`, `Core Benchmark`, group names); migrate to the vocabulary in `DESIGN.md`.
6. Current `.view { max-width: 1000px; }` and oversized page padding constrain the analytical workspace relative to the fluid canonical visual system; migrate touched Product Workspace screens to the canonical desktop layout.
7. Current frontend navigation/state is mainly transient JavaScript state; introduce restorable URL/hash state when the Products/Workspace corrective PR is implemented.
8. Current full-catalog UI has no search/pagination controls even though the backend dataset is potentially large; add bounded navigation before treating catalog UX as complete.
9. Global scrollbar styling/baseline is not yet established; add it when the shared app shell is next materially refactored.
10. Secret inputs are masked but do not yet expose the Premium show/hide affordance; add it when Settings is next materially touched.

Migration must be sliced by complete user workflows; do not rewrite unrelated working screens merely to normalize styling.

## Verification

For any PR that changes these workflows, run the checks applicable to the touched surface and report actual results.

### Static/project checks

- `python -m pytest tests/test_frontend_contract.py -q`
- relevant feature/API tests for any changed contract;
- `node --check frontend/assets/js/app.js`
- other existing committed JS contract checks affected by the change;
- `git diff --check`.

When Frontend Design Premium tooling is available in the development environment:

- `npx -p @google/design.md designmd lint DESIGN.md`
- `python <frontend-design-premium-skill-dir>/scripts/audit_project.py <repo-root> --mode report --no-write`

### Browser/device matrix

At minimum for substantial Product Workspace/catalog changes:

- Windows Chrome/Edge-like Chromium behavior;
- 1280, 1440 and 1600 CSS px desktop widths;
- Windows scaling 125–150% or equivalent effective viewport review;
- browser/text zoom 200%;
- keyboard-only navigation through global nav, SKU chooser, workspace tabs, search, table row actions and edit/save flow;
- reduced-motion behavior when motion exists.

### Accessibility checks

- visible focus is never clipped/covered;
- state does not rely on color alone;
- semantic table/navigation/form controls;
- popover/dialog focus return;
- `aria-live` only for appropriate dynamic feedback, without duplicate announcements;
- no horizontal page scroll on primary analytical screens at >=1280 CSS px.

### Canonical sibling flow

Until PR8 creates the first mature Product Workspace screen, compare new flow behavior against:

- Data import feedback for pending/success/error discipline;
- PR6 competitor save flow for server-confirmed mutation semantics;
- this contract for navigation and state restoration.

After the corrective Products/Workspace PR lands, that complete flow becomes the primary sibling reference for PR8–PR10.
