# AGENTS.md — SCOZ repository instructions

These instructions apply to the whole repository.

## Product context

SCOZ is an internal local Windows tool for a small group of trusted company users.

Canonical user flow:

> repository ZIP → extract → `start.bat` → first run prepares the project-local runtime → later runs use the same `start.bat` from the same folder.

The supported repository ZIP must be runnable without a local frontend build. The end user must not need Node/npm.

Do not turn SCOZ into a SaaS, enterprise desktop platform or multi-user network service unless a future approved design explicitly changes this context.

## Before changing code

Do not implement a development PR until its PR-specific Implementation Spec has been written and approved.

Read the relevant parts of these documents first:

1. `ТЗ — система диагностики и benchmark-аналитики карточек Ozon.md`
2. `Дополнение к ТЗ — benchmark рекламной интенсивности.md`
3. `Дополнение к ТЗ — Query Opportunity Benchmark.md`
4. `docs/superpowers/specs/2026-08-13-scoz-architecture-design.md`
5. `docs/superpowers/specs/2026-08-13-scoz-ui-ux-design.md`
6. `docs/superpowers/specs/2026-08-13-scoz-preflight-decisions.md`
7. `docs/superpowers/specs/scoz-visual-design-system.md`
8. `docs/superpowers/plans/2026-08-13-scoz-pr-development-plan.md`
9. the approved PR-specific Implementation Spec for the PR being implemented.

If requirements conflict, stop and surface the conflict before implementation.

For **PR sequencing, timing of entity/table introduction and exact PR scope**, the latest canonical PR Development Plan controls. Earlier documents describe the target model and analytical contracts, not a requirement to create future feature tables early.

For **visual language, typography, spacing, colors, layout density and reusable UI primitives**, `docs/superpowers/specs/scoz-visual-design-system.md` controls. It does not create product features or business behavior.

## YAGNI rule

Prefer the simplest implementation that satisfies the approved internal-use workflow and preserves analytical correctness.

Do not introduce without a real requirement:

- user accounts/roles;
- auth/session frameworks;
- DPAPI/Credential Manager integration;
- persistent background job infrastructure;
- event bus/message queue;
- generic scheduler platform;
- source capability registry;
- generic source-resolution framework before a real multi-source conflict exists;
- auto-updater;
- telemetry service;
- central SCOZ backend;
- LAN access;
- Docker/PostgreSQL;
- future feature tables/entities before the PR that first uses them.

Do not remove data-integrity safeguards merely to reduce code size.

## Non-negotiable architecture invariants

- Local portable Windows app: repository ZIP → extract → `start.bat` → browser UI.
- No dependency on system Python, Node/npm, Docker or PostgreSQL for the end user.
- Production frontend static assets are already present in the distributable ZIP; no user-side frontend build.
- Backend binds only to `127.0.0.1`; frontend and API are same-origin in production.
- Source Adapter → Ingestion → Normalized Domain Model → Persistence/History → Analytics → Application Services → FastAPI → React UI.
- No business logic in React or FastAPI route handlers.
- No SQL outside the persistence/repository layer.
- DataFrame is not an inter-module domain contract.
- Historical observations are immutable and source corrections are stored as explicit lightweight revisions rather than overwriting history.
- Benchmark composition is versioned through `BenchmarkSetRevision` once benchmark workflow is introduced.
- Analytics preserves period/granularity compatibility and never invents missing dimensions.
- Ozon numerical data has priority only when it provides the required metric at compatible period/granularity.
- MPStats is used for competitor main images and search-position history, not as the primary sales benchmark when Ozon data exists.
- Query Opportunity is part of the search workflow, not a separate BI product.
- Advertising intensity is context, not a separate advertising dashboard.
- Ramp-up returns insufficient data instead of pseudo-precision.
- Every visible wait/action provides understandable feedback, but no persistent job framework is required by default.
- Real reports, user databases, credentials and sensitive logs never enter this public repository.

## Competitor and relevant-query workflow

Do not skip the query-relevance step.

The intended workflow is:

1. load own-product query analytics;
2. user includes/excludes queries that are genuinely relevant for the own SKU;
3. persist that product-specific relevant-query scope;
4. build competitor candidates from available Ozon search-visibility observations for those selected queries;
5. load candidate main photos through MPStats;
6. user manually includes/excludes direct competitors;
7. allow manual competitor add by SKU when a needed competitor is absent from the candidate pool;
8. save the benchmark set/revision.

Query Opportunity later prioritizes the saved relevant-query scope by default. Do not let irrelevant queries clutter the primary opportunity list.

## API credential model

Use the approved portable encrypted keystore model.

- Credentials may be entered or decrypted in the browser tab.
- After unlocking they live only in current-tab memory.
- They may be sent to the local backend over same-origin loopback requests only for the operation that needs them.
- Backend must not persist plaintext credentials or log/echo them.
- User may save `scoz_credentials.enc.json` encrypted with Web Crypto using AES-256-GCM and PBKDF2-HMAC-SHA256 (600000 iterations, random salt/IV).
- Provide a `Lock credentials` action that clears them from UI memory.
- `.enc.json` credential files and plaintext credential-like JSON names must be gitignored.

Do not replace this with DPAPI, account-bound storage or a backend secret database without an approved design change.

## Local web security profile

For the approved trusted local-only scenario, the baseline is deliberately simple:

- bind to `127.0.0.1` only;
- same-origin frontend/API;
- no permissive production CORS;
- no credentials in URL/query strings;
- GET endpoints do not mutate state;
- logs redact sensitive values.

Do not add login, per-launch session token, CSRF framework, certificates or LAN security unless the deployment model changes.

## Portable/startup behavior

- Runtime is project-local and uses pinned dependencies.
- Runtime downloads use pinned official HTTPS sources and SHA-256 verification.
- First-run setup and later runs show understandable stages.
- Browser opens only after a successful health check.
- Use simple startup status/log files such as `data/startup_status.json` and `data/launcher.log`; do not create a general operations database for startup.
- `data/` is user-owned state and is never committed.
- DB migrations run automatically; a risky migration requires a local backup first.

## Ozon automation rule

Use only officially permitted public Ozon APIs and user-supplied/exported files.

Do not implement undocumented/internal Ozon endpoint scraping, `xapi` automation, Selenium/WebDriver or other automation that imitates a user in the Ozon seller cabinet unless a future approved design explicitly replaces this rule with an officially permitted contract.

There is no optional internal Search Visibility API PR in the active plan.

## Codex Cloud execution model

The user manually selects the working branch before starting a Codex task. Codex works only inside that already selected branch: it does not need to search for other branches and must not create, switch, or delete branches.

Codex does not push, create a Pull Request, merge a Pull Request, or otherwise perform the post-handoff Git lifecycle. The user performs the push and creates the Pull Request manually. A merge decision is made only after the separate post-push verification sequence described below.

Responsibilities are divided as follows:

- **Codex Cloud** reads the canonical documents, implements the approved changes in the selected branch, runs checks available in its current environment, reports the actual results, and explicitly lists checks that were not executed in that environment.
- **User** selects the branch, pushes the resulting commits, and creates the Pull Request.
- **GitHub Actions** is the authoritative environment for post-push CI and the authoritative Windows acceptance environment for Windows-specific workflows.
- **Independent PR review** occurs after push, Pull Request creation, and CI; only then is a merge decision made.

`Codex implementation complete` is not the same as `PR merge-ready`.

Codex may complete an implementation task when it has implemented the approved scope, run every check available in its cloud environment, and honestly enumerated the pending post-push checks. A Pull Request is merge-ready only after the user has pushed the changes and created the Pull Request, mandatory GitHub Actions CI has passed, and an independent merge review has passed.

The canonical sequence is:

```text
Codex implementation
→ user push
→ user creates PR
→ GitHub Actions
→ independent merge review
→ merge decision
```

Codex must not ask the user to run development or testing commands on the user's desktop.

## Development workflow

- Work on one dependency-ordered PR at a time unless the approved plan explicitly permits parallel work.
- Use TDD for business logic and deterministic analytics.
- Add feature-specific schema/domain structures when the feature first needs them; migrations are expected and preferred over speculative schema design.
- Every parser needs synthetic fixtures and malformed/duplicate/edge-case tests.
- Every analytics module needs happy-path, missing-data, insufficient-sample and incompatible-granularity tests where applicable.
- Every user-facing vertical needs loading/refresh, empty, partial, error and insufficient/stale states where applicable.
- Keep modules focused; do not build generic abstractions before a second real use case requires them.
- Frontend PRs must use the canonical visual tokens and component hierarchy from `docs/superpowers/specs/scoz-visual-design-system.md`; do not invent new navigation, scores or visual semantics to fill layouts.
- Before claiming completion, run the relevant verification suite and check the diff against Product, Architecture, UI/UX, Visual Design System, Preflight and the latest PR Plan invariants.
