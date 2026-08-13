# SCOZ PR Development Plan

**Статус:** канонический PR-level plan после YAGNI-аудита.

## 1. Общий принцип

SCOZ реализуется последовательно как внутреннее portable Windows-приложение:

> `ZIP → start.bat → portable Python → FastAPI + built React → SQLite → adapters → analytics`.

Не строить SaaS/enterprise infrastructure. Сохранять строгость data/history/granularity.

Global constraints:

- backend только `127.0.0.1`, frontend/API same-origin;
- no system Python/Node/Docker/PostgreSQL for user;
- immutable observations + lightweight revisions;
- `BenchmarkSetRevision`;
- no silent period/granularity mixing;
- Ozon primary numeric source when compatible;
- MPStats only approved roles: photos + search-position history;
- only official public Ozon APIs/user exports;
- portable encrypted keystore, no DPAPI/backend secret store;
- visible feedback without persistent job framework;
- no universal card/Opportunity score;
- Ramp-up returns insufficient data when evidence is weak.

## 2. Phases

**PR1–PR5 — Foundation & Data Plane.** Portable app, SQLite history, Ozon imports.

**PR6–PR10 — Diagnostic MVP.** Competitors, benchmark, diagnosis, heatmap, Query Opportunity.

**PR11–PR14 — API & Ramp-up.** Official APIs, advertising history, Ramp-up models/scenarios.

**PR15 — Release hardening.** Clean-Windows internal release.

## 3. Dependency chain

```text
PR1 → PR2 → PR3 → PR4 → PR5 → PR6 → PR7 → PR8
→ PR9 → PR10 → PR11 → PR12 → PR13 → PR14 → PR15
```

---

# PR1 — Portable Application Foundation

Result: `start.bat` launches SCOZ on clean Windows; first run prepares project-local runtime, later runs reuse it.

Scope: portable Python bootstrap, pinned runtime/dependencies, SHA-256 verification, runtime marker/repair, FastAPI health, built React shell, loopback only, same-origin, startup status/logs, port/already-running handling, browser after health, base navigation, Windows smoke.

Non-goals: business DB schema, credentials, auth/session framework, DPAPI, persistent jobs, auto-updater.

Acceptance: first and second run work without system Python/Node; failure is understandable; spaces/Cyrillic path and occupied port are tested.

---

# PR2 — Domain, SQLite History & Lineage

Result: stable data foundation.

Scope: `Product`, ownership, `ProductExternalIdentity`, `SearchQuery`, `Cluster`, `BenchmarkSet`, `BenchmarkSetRevision`, `BenchmarkMember`, all snapshot types, `ImportBatch`, `SourceArtifact`; repositories/migrations; logical observation keys; duplicate/revision semantics; period/granularity metadata; simple source resolver; provenance.

Non-goals: generic SourceCapability/job frameworks, parsers, analytics.

Acceptance: same payload is duplicate; corrected same-period payload is new revision; new period is new observation; benchmark edits create revision; SQL stays in persistence.

---

# PR3 — Ozon «Товары на Ozon» Import

Result: first end-to-end data import.

Scope: parser/ingestion/API/UI, Product/ProductSnapshot, units/turnover/impressions/views/conversions/cart/price/stock/DRR fields when present, unit semantics, partial row errors, structural validation, revisions, import history, own-SKU selection.

Acceptance: valid synthetic XLSX imports; duplicate/revision behavior works; invalid schema fails clearly; period/freshness visible.

---

# PR4 — Ozon «Что влияет на место» Import

Result: `product × query × cluster` search factors stored historically.

Scope: query/cluster identity, position/relevance/popularity/promotion/CPC/CPO/delivery/price/index/rating/reviews, revisions/provenance, coverage summary.

Acceptance: clusters do not collapse, missing stays missing, history is preserved.

---

# PR5 — Query Metrics & Own Product Queries

Result: Query Demand/Quality + own-SKU query history.

Scope: `QueryMetricSnapshot` and `ProductQuerySnapshot`; frequency/popularity, market CR, no-action share, orders/turnover; own visibility/position/transitions/conversions/orders where available; explicit period/granularity.

Acceptance: market query CR cannot be confused with product CR; readiness is visible.

---

# PR6 — MPStats Photos, Benchmark Selection & Encrypted Keystore

Result: user can unlock source credentials, inspect candidate photos and save a real competitor set.

Scope: source settings/test connection; approved portable encrypted keystore from Preflight/UIUX; credentials only in current-tab memory after input/unlock; backend does not persist/log plaintext; lock action; MPStats photos; manual include/exclude; save `BenchmarkSetRevision`.

Acceptance: keystore save/unlock/error flow works with synthetic credentials; partial photo failures do not block selection; MPStats sales estimates do not enter benchmark model.

---

# PR7 — Core Benchmark & Advertising Intensity

Result: own vs selected competitors by key metrics.

Scope: median, P25/P75 when valid, sample size, delta, performance status, confidence, metric direction, period compatibility, advertising-intensity addendum, detail view.

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

Result: queries are prioritized by Demand, Quality, Visibility Gap and Stability.

Mandatory first step: verify MPStats position-history date order, missing days, `null` and business-date semantics before Share of Top.

Scope: `SearchPositionSnapshot`, median position, Share of TOP-10/TOP-20 + denominator, Query Opportunity engine/UI before existing heatmap.

Acceptance: no Opportunity Score; market query CR is not competitor CR; unknown position is not zero; weak-intent high-frequency query may rank lower.

**Milestone:** Diagnostic MVP = `SKU → competitors → benchmark → diagnosis → valuable query → cluster/factor diagnosis`.

---

# PR11 — Ozon Public API Sync

Result: supported XLSX flows can be automated by official Ozon public APIs.

Scope: connection/sync using unlocked credentials, mapping into existing snapshots, source resolution vs XLSX, adapter-specific pagination/rate-limit/errors/backfill/coverage, idempotent sync.

Non-goals: internal endpoints, xapi, Selenium, generic scheduler/capability platform.

Acceptance: API/XLSX create compatible domain observations; failed sync preserves history.

---

# PR12 — Ozon Performance API History

Result: observed own-SKU advertising history exists for Ramp-up.

Scope: campaign/product/date/bid/strategy-relevant values and available impressions/clicks/CPC/spend/orders/sales; AdvertisingSnapshots; adapter-specific history coverage; readiness UI.

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

Scope: clean-Windows first/second-run regression, runtime integrity/repair, port/failure UX, migrations + local backup before risky migration, interrupted import/sync safety, logs/secrets audit, keystore smoke, full synthetic CJM, Windows scaling/basic keyboard review, realistic synthetic performance sanity.

Non-goal: enterprise hardening, network deployment, auto-update platform.

Acceptance: release works without system runtimes; data survives normal repeated use/migrations; core CJM passes end-to-end.

---

## 4. Cross-PR review gate

Reject/correct a PR if it puts business logic in React/routes, lets analytics read raw source directly, leaks SQL outside persistence, overwrites history, loses benchmark revision/provenance, invents/mixes granularity, persists plaintext credentials, introduces internal Ozon automation, hides long actions without feedback, presents estimates as facts, or adds a generic infrastructure framework without a real use case.

## 5. PR-specific specs

Before each implementation PR, write a focused Implementation Spec against the actual current `main`: exact scope/non-goals, files/interfaces, schema/API changes, UX states, fixtures/tests, manual QA and DoD. Do not overdesign later file paths/interfaces before preceding PRs are merged.