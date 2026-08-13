# AGENTS.md — SCOZ repository instructions

These instructions apply to the whole repository.

## Before changing code

Do not implement a development PR until its PR-specific Implementation Spec has been written and approved.

For any development task, read the relevant parts of these documents first:

1. `ТЗ — система диагностики и benchmark-аналитики карточек Ozon.md`
2. `Дополнение к ТЗ — benchmark рекламной интенсивности.md`
3. `Дополнение к ТЗ — Query Opportunity Benchmark.md`
4. `docs/superpowers/specs/2026-08-13-scoz-architecture-design.md`
5. `docs/superpowers/specs/2026-08-13-scoz-ui-ux-design.md`
6. `docs/superpowers/specs/2026-08-13-scoz-preflight-decisions.md`
7. `docs/superpowers/plans/2026-08-13-scoz-pr-development-plan.md`
8. the approved PR-specific Implementation Spec for the PR being implemented.

## Precedence

The documents cover different kinds of requirements:

- Product Spec and its addenda define product behavior and analytical intent.
- Architecture Design defines module and technical boundaries.
- UI/UX Design defines user flows and feedback behavior.
- PR Development Plan defines implementation order and PR boundaries.
- `2026-08-13-scoz-preflight-decisions.md` contains later corrective decisions and **supersedes any conflicting older clause** on identity, revisions, temporal/granularity rules, source resolution, backfill, MPStats position semantics, Ramp-up grain, confidence/availability guardrails, local web security, secrets, update/data lifecycle and permitted Ozon automation.
- A PR-specific spec may concretize these contracts but must not silently override higher-level product/architecture decisions.

If two requirements still conflict after applying this precedence, stop and surface the conflict before implementation.

## Non-negotiable architecture invariants

- Local portable Windows app: ZIP → extract → `start.bat` → browser UI.
- No dependency on system Python, Node/npm, Docker or PostgreSQL for the end user.
- Backend binds to loopback only and follows the local-web security contract from Preflight Decisions.
- Source Adapter → Ingestion → Normalized Domain Model → Persistence/History → Analytics → Application Services → FastAPI → React UI.
- No business logic in React or FastAPI route handlers.
- No SQL outside persistence/repository layer.
- DataFrame is not an inter-module domain contract.
- Historical observations are immutable and support source corrections as explicit revisions.
- Benchmark composition is versioned through `BenchmarkSetRevision`.
- Analytics must preserve period/grain compatibility and must not invent missing dimensions.
- Ozon numerical source data has priority when it provides the required metric at compatible grain/period; MPStats sales estimates do not replace primary Ozon metrics.
- MPStats is used for competitor main images and search-position history as specified.
- Query Opportunity is not a separate BI product.
- Advertising intensity is context, not a separate advertising dashboard.
- Ramp-up must return insufficient data instead of pseudo-precision.
- Every long-running action provides visible feedback through the shared Operation contract.
- Real reports, user databases, credentials and sensitive logs must never be committed to this public repository.

## Ozon automation rule

Use only officially permitted public Ozon APIs and user-supplied/exported files.

Do not implement undocumented/internal Ozon endpoint scraping, `xapi` automation, Selenium/WebDriver or other automation that imitates a user in the Ozon seller cabinet unless a future approved design change cites an explicitly permitted public contract from Ozon.

The optional internal Search Visibility API section in the original PR Development Plan is superseded and inactive.

## Development workflow

- Work on one dependency-ordered PR at a time unless the approved plan explicitly permits parallel work.
- Use TDD for new business logic and deterministic analytics.
- Every parser needs synthetic fixtures and malformed/duplicate/edge-case tests.
- Every analytics module needs happy-path, missing-data, insufficient-sample and incompatible-grain tests.
- Every user-facing vertical needs loading/refresh, empty, partial, error and insufficient/stale states where applicable.
- Before claiming completion, run the relevant full verification suite and check the diff against Architecture, UI/UX and Preflight invariants.
