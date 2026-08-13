# SCOZ — Architecture Design

**Дата:** 2026-08-13  
**Статус:** канонический technical design

## 1. Контекст

SCOZ — внутреннее локальное Windows-приложение для небольшой группы доверенных пользователей.

Пользовательский контракт:

> ZIP репозитория → распаковать → `start.bat` → первый запуск сам готовит локальный runtime → последующие запуски используют тот же `start.bat` из той же папки.

Репозиторий должен оставаться пользовательски запускаемым без локальной frontend-сборки: production static assets входят в распространяемое состояние ZIP. Node/npm на пользовательском ПК не нужны.

SCOZ не является SaaS, LAN-сервисом или multi-user платформой. Архитектура защищает достоверность аналитики, но не создаёт enterprise-инфраструктуру без реального сценария.

Детали YAGNI-профиля и portable keystore зафиксированы в `docs/superpowers/specs/2026-08-13-scoz-preflight-decisions.md`.

## 2. Стек

Backend — **Python + FastAPI**. Frontend — **React + TypeScript**, заранее собранный в static assets. Storage — **SQLite**.

`openpyxl`/`pandas` допустимы внутри ingestion, но DataFrame не является межмодульным контрактом. Node/npm нужны только development/CI для подготовки frontend assets.

## 3. Portable startup

```text
start.bat
  → project-local runtime check/setup
  → preflight + DB migrations
  → FastAPI @ 127.0.0.1
  → health check
  → browser UI
```

Первый запуск скачивает portable Python с pinned official HTTPS URL, проверяет SHA-256 и локально готовит runtime/pinned dependencies. Frontend уже собран.

Повторный запуск не переустанавливает валидный runtime. Launcher показывает понятные стадии и локальные логи. Пользователь не устанавливает Python/Node, не меняет PATH и не использует права администратора.

## 4. Local web profile

Backend слушает только `127.0.0.1`. Frontend и API работают same-origin. Production CORS не открывается произвольным origins.

Для trusted-local сценария не нужны login/auth, per-launch session token, CSRF framework, TLS для loopback и LAN security layer.

## 5. Credentials

Используется **portable encrypted keystore** из Preflight Decisions: ключи вводятся/расшифровываются в текущей browser tab, живут только в её памяти и передаются локальному backend только для конкретной операции source API. Backend не хранит plaintext credentials.

DPAPI, Credential Manager и backend secret database не используются.

## 6. Высокоуровневая архитектура

```text
External Sources
  → Source Adapters
  → Ingestion / Normalization
  → Normalized Domain Model
  → Persistence + History
  → Benchmark / Diagnostics / Search Visibility / Query Opportunity
  → Ramp-up
  → Application Services
  → FastAPI
  → React UI
```

Главный инвариант:

> **Source Adapter → Normalized Domain Model → Analytics → Application Services → API → UI**

UI и analytics не зависят от структуры конкретного XLSX/API response.

## 7. Sources и ingestion

Поддерживаемые источники:

- Ozon XLSX «Товары на Ozon»;
- Ozon XLSX «Что влияет на место»;
- Ozon XLSX/официальный public API поисковой аналитики;
- Ozon Seller API — только официальные public endpoints;
- Ozon Performance API;
- MPStats — главные фото и история поисковых позиций.

Не использовать undocumented/internal Ozon API, `xapi`, Selenium/WebDriver или автоматический парсинг кабинета.

Ingestion отвечает за report detection, schema validation, parsing, normalization IDs/types/units, row errors, hashes, duplicate/revision detection и normalized snapshots.

## 8. Canonical domain model

Целевая доменная модель по мере появления соответствующих verticals включает:

- `Product`;
- ownership flag/relation;
- `ProductExternalIdentity`;
- `SearchQuery`;
- `Cluster`;
- `BenchmarkSet`;
- `BenchmarkSetRevision`;
- `BenchmarkMember`;
- `ProductSnapshot`;
- `ProductQuerySnapshot`;
- `SearchVisibilitySnapshot`;
- `SearchPositionSnapshot`;
- `QueryMetricSnapshot`;
- `AdvertisingSnapshot`;
- `ImportBatch`;
- `SourceArtifact`.

Это **целевая карта сущностей, а не требование создать все таблицы в PR2**. Feature-specific entity/table появляется migration-ой в первом PR, который реально её использует.

Отдельных `OwnProduct`/`CompetitorProduct` нет. Конкурент — обычный `Product`, включённый в конкретную benchmark revision.

`BenchmarkSnapshot` не является source of truth: benchmark вычисляется из snapshots + `BenchmarkSetRevision`; materialized cache допустим только как оптимизация.

Минимальный `ProductExternalIdentity` хранит internal product ID, source, identity type/value и account scope только когда он реально нужен. Не merge по названию/фото. Temporal identity history заранее не строится.

## 9. Persistence, history и revisions

SQLite скрыта за repository layer. SQL не выполняется из analytics/routes. Schema меняется через migrations. `data/` — user-owned state и не коммитится.

Для snapshot-типа в момент его появления определяется logical observation key:

```text
same key + same normalized payload → duplicate
same key + changed payload → new revision, previous superseded
new period/date/dimensions → new observation
```

Analytics использует актуальную revision, старые остаются для provenance. Изменение состава конкурентов после появления benchmark workflow создаёт новую `BenchmarkSetRevision`.

## 10. Period/granularity и sources

Каждый snapshot хранит доступные `observed_at`, `period_start`, `period_end`, `imported_at` и фактические dimensions/granularity.

Не нужен тяжёлый temporal framework: достаточно typed metadata и reusable compatibility rules.

Нельзя молча связывать daily position с 28-day CR row-by-row, размножать query-level data по кластерам, сравнивать несовместимые periods или интерполировать missing days как observed facts.

Source resolver не строится заранее как framework. Минимальная детерминированная функция появляется тогда, когда одна metric реально начинает приходить из нескольких источников. Факты сохраняются с provenance и автоматически не усредняются; Ozon предпочтителен только при совместимых metric/grain/period; MPStats sales estimates не подменяют Ozon benchmark.

Backfill/coverage реализуются внутри конкретного API adapter-а только если source это поддерживает. Общий `SourceCapability` registry в foundation не нужен.

## 11. Формирование benchmark-группы

До benchmark пользователь формирует **product-specific scope релевантных поисковых запросов** из импортированной аналитики собственного SKU.

Далее candidate pool строится из доступных Ozon Search Visibility observations только по выбранным релевантным queries. Для кандидатов загружаются главные фото через MPStats.

Пользователь вручную include/exclude прямых конкурентов и может добавить competitor по SKU, если нужного товара нет в candidate pool.

После сохранения появляется `BenchmarkSet` и immutable `BenchmarkSetRevision`.

Этот workflow не является автоматическим выбором конкурентов: финальное решение всегда подтверждает пользователь.

## 12. Analytics modules

**Benchmark** возвращает own value, median, P25/P75 при достаточной выборке, sample size, delta, performance status и confidence. Здесь же считается рекламная интенсивность согласно отдельному Product Addendum.

**Diagnostics** формирует максимум 2–3 главные причины. OOS может выступать как `AVAILABILITY_CONFOUNDED`.

**Search Visibility** работает в `product × query × cluster`; основные factors — position, relevance, popularity, delivery, price.

**Query Opportunity** объединяет Query Demand, Query Quality, Visibility Gap и Position Stability. По умолчанию работает в сохранённом relevant-query scope. Без Opportunity Score 0–100. Share of Top возвращает denominator/sample size.

**Ramp-up** строит position-normalized CR, readiness/confidence, verdict, empirical bid-position model, scenarios и organic-support trend. Он работает на максимально детальной **общей** granularity входов. Базово — `SKU × query × time`; cluster добавляется только при совместимых cluster-level inputs. При недостатке данных возвращается `INSUFFICIENT_DATA`.

## 13. MPStats position history

До реализации Share of Top PR10 обязан проверить реальный contract истории позиций: порядок массива относительно дат, missing days, `null` semantics и business-date semantics. До подтверждения `null` означает unknown observation.

## 14. Application/API/UI

Application Services оркестрируют repositories и analytics. FastAPI routes остаются тонкими: validation → application service → DTO/error mapping.

Frontend отвечает за navigation, upload, relevant-query selection, competitor selection, encrypted-keystore UX, feedback states, tables/heatmap/charts/drill-down. Business rules в frontend запрещены.

## 15. Operation feedback

Persistent operation database/job platform не нужен. Короткие действия используют request-local loading state. Реально длинная операция при необходимости использует lightweight in-memory state + HTTP polling.

Минимальные states: `VALIDATING → RUNNING → SUCCESS / PARTIAL_SUCCESS / FAILED`. `STALE` и `INSUFFICIENT_DATA` — состояния данных/аналитики.

## 16. Testing

Каждый parser: valid synthetic fixture, malformed row, incompatible schema, duplicate, corrected same-period revision и relevant locale/date/unit edge cases.

Каждый analytics module: deterministic happy path, missing data, small sample, incompatible period/granularity и insufficient-data cases.

API adapters: mocked synthetic contracts; никаких real credentials в CI.

Portable Windows verification: clean machine without system Python/Node, repository-ZIP first run, second run, health/open browser, occupied port, Cyrillic/spaces path и runtime-integrity failure.

## 17. Explicit non-goals

В v1 не входят central server, accounts/roles, LAN mode, auto-updater, DPAPI/Credential Manager, auth/session platform, persistent job queue, event bus, telemetry SaaS, automatic bid changes, guaranteed positions, undocumented Ozon automation, competitor ad/organic reconstruction, seller-price/SPP calculations, universal card score 0–100, Opportunity Score 0–100 и отдельный advertising BI.

## 18. Code-review invariants

PR требует корректировки, если он добавляет business logic во frontend/routes, даёт analytics читать XLSX/API напрямую, выполняет SQL вне persistence, перезаписывает history, теряет benchmark revision/provenance, смешивает incompatible periods/granularity, строит cluster Ramp-up без cluster evidence, сохраняет plaintext credentials, требует system Python/Node или user-side frontend build, использует internal Ozon automation, создаёт все будущие feature tables заранее или вводит generic infrastructure без реального use case.

## 19. Итог

```text
ZIP репозитория → start.bat → portable runtime → FastAPI + React → SQLite
                                                       ↓
                                                   adapters
                                                       ↓
                                              normalized history
                                                       ↓
                                                   analytics
                                                       ↓
                                                  clear UI
```

Сложность оправдана там, где она защищает данные, воспроизводимость или аналитический вывод. Остальное добавляется только по реальной необходимости.