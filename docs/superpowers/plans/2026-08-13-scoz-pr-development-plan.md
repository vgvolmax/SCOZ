# SCOZ PR Development Plan

**Статус:** канонический PR-level plan после финального YAGNI-аудита.

## 1. Общий принцип

SCOZ реализуется последовательно как внутреннее portable Windows-приложение:

> `ZIP репозитория → start.bat → portable Python → FastAPI + committed static frontend → SQLite → adapters → analytics`.

Репозиторий должен оставаться пользовательски запускаемым: пользователь скачивает ZIP, распаковывает его и запускает `start.bat`. На его ПК не выполняется frontend build и не требуется Node/npm. Необходимые production static assets должны входить в распространяемое состояние репозитория/ZIP.

Не строить SaaS/enterprise infrastructure. Сохранять строгость data/history/granularity.

Global constraints:

- backend только `127.0.0.1`, frontend/API same-origin;
- no system Python/Node/Docker/PostgreSQL for user;
- immutable observations + lightweight revisions;
- `BenchmarkSetRevision` с момента появления benchmark workflow;
- no silent period/granularity mixing;
- Ozon primary numeric source when compatible;
- MPStats only approved roles: photos + search-position history;
- only official public Ozon APIs/user exports;
- portable encrypted keystore, no DPAPI/backend secret store;
- visible feedback without persistent job framework;
- no universal card/Opportunity score;
- Ramp-up returns insufficient data when evidence is weak;
- YAGNI: feature-specific tables/entities appear in the PR that first needs them, not заранее в foundation.

## 2. Phases

**PR1–PR5 — Foundation & initial Data Plane baseline.** Завершён базовый data foundation: portable app, canonical identities, первые immutable Ozon source histories, provenance и period/grain semantics. Later PRs may extend the Source Facts layer when a real feature first requires a new adapter/snapshot, without changing the architectural boundary between source facts and derived analytics.

**PR6–PR10 — Diagnostic MVP / Analytical Plane.** Начинается с user-curated analytical context, затем строит feature-specific derived analytics поверх Data Plane: relevant-query scope, competitors, benchmark, diagnosis, heatmap, Query Opportunity. PR6–PR10 не записывают analytical interpretation обратно в source snapshots PR3–PR5. Analytical-plane PR может также вводить feature-specific source observation, если впервые требует такой source fact (например, `SearchPositionSnapshot` в PR10); такой snapshot остаётся Source Fact, а не Derived Analytic.

**PR11–PR14 — API & Ramp-up.** Official APIs, advertising history, Ramp-up models/scenarios.

**PR15 — Release hardening.** Clean-Windows internal release.

## 3. Dependency chain

```text
PR1 → PR2 → PR3 → PR4 → PR5 → PR6 → PR7 → PR8
→ PR9 → PR10 → PR11 → PR12 → PR13 → PR14 → PR15
```

---

# PR1 — Portable Application Foundation

Result: ZIP текущего поддерживаемого состояния репозитория распаковывается на clean Windows и `start.bat` запускает SCOZ; первый run готовит project-local runtime, later runs reuse it.

Scope: portable Python bootstrap based on the proven `WB_OZON_Yandex` flow, project-local Windows embeddable Python, exact direct dependencies in `requirements.txt`, runtime validation/repair/rebuild, FastAPI health, static HTML/CSS/JavaScript application shell committed directly in the repository and already present in the distributable ZIP, loopback only, same-origin, startup status/logs, port/already-running handling, browser after health, base navigation and Windows smoke of the real user flow.

Non-goals: business DB schema, credentials, auth/session framework, DPAPI, persistent jobs, auto-updater, npm/frontend build on user machine.

Acceptance: downloaded repository ZIP works without system Python/Node; first and second run work; failure is understandable; spaces/Cyrillic path and occupied port are tested; browser opens only after health.

---

# PR2 — Core Domain, SQLite Foundation & Lineage

Result: минимальный data foundation, достаточный для безопасного наращивания последующих verticals.

Scope:

- `Product` + ownership;
- минимальный `ProductExternalIdentity`;
- `ImportBatch`;
- `SourceArtifact`;
- SQLite migrations/repository boundaries;
- общие provenance conventions;
- общая семантика logical observation key / duplicate / corrected revision для snapshot-типов, когда они появляются;
- period/granularity metadata conventions;
- user-owned `data/` layout.

Важно: **не создавать заранее все будущие feature-specific snapshot tables/entities**. Они добавляются migration-ами в первом PR, которому реально нужны.

Non-goals: `ProductSnapshot`, `SearchVisibilitySnapshot`, `QueryMetricSnapshot`, `ProductQuerySnapshot`, `SearchPositionSnapshot`, `AdvertisingSnapshot`, `BenchmarkSet*`, generic SourceCapability/job/source-policy frameworks, parsers, analytics.

Acceptance: migration/repository foundation работает на чистой SQLite; provenance можно привязать к source artifact/import batch; SQL остаётся в persistence; тестовая feature-snapshot fixture подтверждает общую duplicate/revision convention без предварительного моделирования всех будущих таблиц.

---

# PR3 — Ozon «Товары на Ozon» Import

Result: first end-to-end data import.

Scope: `ProductSnapshot` + parser/ingestion/API/UI; units/turnover/impressions/views/conversions/cart/price/stock/DRR fields when present; unit semantics; partial row errors; structural validation; logical key/revisions; import history; own-SKU selection.

Acceptance: valid synthetic XLSX imports; same payload is duplicate; corrected same-period payload is new revision; new period is new observation; invalid schema fails clearly; period/freshness visible.

---

# PR4 — Ozon «Что влияет на место» Import

Result: `product × query × cluster` search factors stored historically.

Scope: introduce `SearchQuery`, `Cluster`, `SearchVisibilitySnapshot`; query/cluster identity; position/relevance/popularity/promotion/CPC/CPO/delivery/price/index/rating/reviews; revisions/provenance; coverage summary.

Acceptance: clusters do not collapse; similar-but-different query texts do not merge incorrectly; missing stays missing; history/revisions are preserved.

---

# PR5 — Query Metrics & Own Product Queries

Result: Query Demand/Quality + own-SKU query history.

Scope: introduce `QueryMetricSnapshot` and `ProductQuerySnapshot`; frequency/popularity, market CR, no-action share, orders/turnover; own visibility/position/transitions/conversions/orders where available; explicit period/granularity.

Acceptance: market query CR cannot be confused with product CR; incompatible periods remain explicit; readiness is visible.

---

# PR6 — Relevant Queries, MPStats Photos, Benchmark Selection & Encrypted Keystore

Result: user формирует осмысленную benchmark-группу из кандидатов по действительно релевантным запросам.

Flow:

1. показать импортированные поисковые запросы own SKU;
2. пользователь включает/исключает запросы, которые реально описывают его товар и должны использоваться для поиска конкурентов;
3. сохранить этот product-specific relevant-query scope;
4. построить candidate pool из доступных Ozon Search Visibility observations по выбранным queries;
5. получить главные фото кандидатов через MPStats;
6. пользователь вручную include/exclude прямых конкурентов;
7. разрешить ручное добавление competitor по SKU, если нужного товара нет в candidate pool;
8. сохранить `BenchmarkSet` + `BenchmarkSetRevision` + members.

Relevant-query selection и benchmark composition являются **USER-CURATED ANALYTICAL CONTEXT**. Минимальную persisted model/name для relevant-query scope определит PR6 Implementation Spec против актуального `main`; план не вводит её заранее. PR6 не создаёт derived benchmark metric history: `BenchmarkSetRevision` фиксирует composition, а не копирует competitor metrics.

Scope также включает source settings/test connection и approved portable encrypted keystore from Preflight/UIUX: credentials only in current-tab memory after input/unlock; backend does not persist/log plaintext; lock action.

Acceptance: relevant-query scope сохраняется и повторно открывается; candidate pool использует только выбранные релевантные queries; competitor можно добавить/удалить вручную; keystore save/unlock/error flow works with synthetic credentials; partial photo failures do not block selection; MPStats sales estimates do not enter benchmark model.

---

# PR7 — Core Benchmark & Advertising Intensity

Result: own vs selected competitors by key metrics.

Scope: median, P25/P75 when valid, sample size, delta, performance status, confidence, metric direction, period compatibility, advertising-intensity addendum, detail view.

Core Benchmark — derived analytic из compatible current source observations и конкретной `BenchmarkSetRevision`. Metric sample определяется независимо для каждой metric; incompatible period/grain означает отсутствие comparable benchmark. Не создавать `BenchmarkSnapshot` как source-of-truth table. Advertising intensity сначала выводится из source facts и лишь затем сравнивается. Exact DTO/config/thresholds принадлежат PR7 Implementation Spec; generic benchmark framework не строится раньше появления реальных feature modules.

Acceptance: deterministic math; small sample not shown as confident; missing values reduce sample; benchmark revision changes result without changing source snapshots.

---

# PR8 — Diagnostics & Product Workspace

Result: main SKU screen explains the biggest problem quickly.

Scope: diagnostic reason codes, result/traffic/conversion/offer/ad context, max 2–3 reasons, OOS confounder, workspace header, readiness/freshness, benchmark drill-down, ready/stale/partial/insufficient/error states.

Acceptance: rules stay backend-side; OOS can reduce/block confidence; period/freshness always visible.

---

# PR9 — Search Visibility Heatmap

Result: selected query shows where and why own SKU loses by cluster.

Scope: five-column heatmap `Cluster | Position | Relevance | Popularity | Delivery | Price`, current benchmark revision, explicit missing observations, short system/local summary, weighted-all-clusters only with reliable weights, drill-down extras.

Acceptance: active query remains visible; no fake zeros; aggregation method explicit.

---

# PR10 — MPStats Position History & Query Opportunity

Result: relevant queries are prioritized by Demand, Quality, Visibility Gap and Stability.

Mandatory first step: verify MPStats position-history date order, missing days, `null` and business-date semantics before Share of Top.

Scope: introduce `SearchPositionSnapshot`; minimal deterministic source resolution where own position is available from more than one source; median position; Share of TOP-10/TOP-20 + denominator; Query Opportunity engine/UI before existing heatmap. By default analyze the saved relevant-query scope; excluded/irrelevant queries do not clutter the primary opportunity list.

Acceptance: no Opportunity Score; market query CR is not competitor CR; unknown position is not zero; weak-intent high-frequency query may rank lower; source resolution is explicit and tested when multiple position sources exist.

**Milestone:** Diagnostic MVP = `SKU → relevant queries → competitors → benchmark → diagnosis → valuable query → cluster/factor diagnosis`.

---

# PR11 — Ozon Public API Sync

Result: supported XLSX flows can be automated by official Ozon public APIs.

Scope: connection/sync using unlocked credentials; mapping into existing snapshot types; simple deterministic source resolution vs XLSX; adapter-specific pagination/rate-limit/errors/backfill/coverage; idempotent sync.

Non-goals: internal endpoints, xapi, Selenium, generic scheduler/capability/source-policy platform.

Acceptance: API/XLSX create compatible domain observations; source choice is deterministic; failed sync preserves history.

---

# PR12 — Ozon Performance API History

Result: observed own-SKU advertising history exists for Ramp-up.

Scope: introduce `AdvertisingSnapshot`; campaign/product/date/bid/strategy-relevant values and available impressions/clicks/CPC/spend/orders/sales; adapter-specific history coverage; readiness UI.

Acceptance: facts remain observed facts; no competitor benchmark; failure preserves prior history.

---

# PR13 — Ramp-up Core

Result: SCOZ distinguishes weak card from normal CR for current position.

Scope: position buckets, compatible position-normalized CR, cross-sectional vs longitudinal evidence, readiness/confidence, verdict, analysis granularity, graph only when valid, Query Opportunity context.

Rule: use the most detailed **common** granularity of required inputs. Baseline `SKU × query × time`; cluster only with genuine compatible cluster-level evidence.

Acceptance: weak/incompatible sample → insufficient; aggregate competitor CR never becomes query-position CR; no causality claim.

---

# PR14 — Ramp-up Scenarios & Organic Support

Result: range scenarios and signs of product anchoring when history is sufficient.

Scope: Current/TOP-20/TOP-10/TOP-3, expected position/CR ranges, bid ranges, confidence, empirical bid→position, trend of bid required to hold comparable TOP-N.

Acceptance: no pseudo-exact guaranteed bid; unavailable scenarios stay unavailable; comparable observations only.

**Milestone:** Full Analytical v1 = Diagnostics + Ramp-up.

---

# PR15 — Portable Release Hardening

Result: stable internal release.

Scope: clean-Windows first/second-run regression of repository ZIP, runtime integrity/repair, port/failure UX, migrations + local backup before risky migration, interrupted import/sync safety, logs/secrets audit, keystore smoke, full synthetic CJM, Windows scaling/basic keyboard review, realistic synthetic performance sanity.

Non-goal: enterprise hardening, network deployment, auto-update platform.

Acceptance: repository ZIP works without system runtimes; data survives normal repeated use/migrations; core CJM passes end-to-end.

---

## 4. Cross-PR review gate

Reject/correct a PR if it puts business logic in UI/routes, lets analytics read raw source directly, leaks SQL outside persistence, overwrites history, loses benchmark revision/provenance, invents/mixes granularity, persists plaintext credentials, introduces internal Ozon automation, hides long actions without feedback, presents estimates as facts, pre-creates future feature infrastructure without a current use case, or requires a local npm/frontend build from the end user.

## 5. PR-specific specs

Before each implementation PR, write a focused Implementation Spec against the actual current `main`: exact scope/non-goals, files/interfaces, schema/API changes, UX states, fixtures/tests, manual QA and DoD. Do not overdesign later file paths/interfaces before preceding PRs are merged.
