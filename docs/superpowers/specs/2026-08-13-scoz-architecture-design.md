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

Backend — **Python + FastAPI**. Frontend — committed **HTML + CSS + JavaScript**, served directly by FastAPI. Storage — **SQLite**.

`openpyxl`/`pandas` допустимы внутри ingestion, но DataFrame не является межмодульным контрактом. Frontend files already exist in the repository ZIP: there is no frontend dependency resolution or user-side build. Node is not a SCOZ runtime or dependency-delivery mechanism; CI may use a preinstalled Node executable only for direct JavaScript syntax/tests such as `node --check`, without an npm registry requirement.

## 3. Portable startup

```text
start.bat
  → verify or prepare project-local Windows embeddable Python in runtime/
  → bootstrap pip with official get-pip.py
  → python -m pip install -r requirements.txt when setup/repair is needed
  → preflight + DB migrations
  → RUN_SERVER.cmd → launcher.py → FastAPI @ 127.0.0.1
  → GET /api/health
  → browser UI
```

Portable-механика следует proven startup model проекта `WB_OZON_Yandex`. Первый запуск скачивает Python 3.13.14 Windows embeddable x64 с официального HTTPS URL во временный `.part`, проверяет, что файл имеет разумный размер и является непустым открываемым ZIP, затем распаковывает его прямо в disposable `runtime/`. Embedded `_pth` включает `python313.zip`, `.`, `Lib\site-packages`, `..` и `import site`. Официальный `get-pip.py` также скачивается через `.part`, проходит базовую size/sanity-проверку и запускается runtime Python; exact direct dependencies устанавливаются обычной командой `python -m pip install -r requirements.txt`. Committed frontend уже находится в repository ZIP и не требует build.

Повторный запуск проверяет `runtime\python.exe`, запуск Python, imports и exact direct versions реально используемых packages. Валидный runtime reuse-ится. При mismatch сначала повторяется тот же pip install; если repair или сам runtime неработоспособен, удаляется и с нуля готовится только `runtime/`. Прерванная подготовка повторяется на следующем старте. Отдельный user state в `data/` не затрагивается. Launcher показывает понятные стадии и локальные логи, а browser открывается только после успешного health. Пользователь не устанавливает Python/Node, не меняет PATH и не использует права администратора.

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
  → Static Web UI
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

### 12.1. Post-PR5 boundary: от Data Plane к Analytical Plane

После PR5 dependency/responsibility model имеет следующий вид:

```text
INFRASTRUCTURE
    ↓
CANONICAL IDENTITIES
    ↓
SOURCE FACTS + PROVENANCE
    ↓
USER-CURATED ANALYTICAL CONTEXT
    ↓
DERIVED ANALYTICS
    ↓
DIAGNOSTIC / DECISION OUTPUT
    ↓
APPLICATION SERVICES
    ↓
API / UI
```

Это модель зависимостей и ответственности, а не требование создать отдельный module или table для каждого прямоугольника. `Product`, `ProductExternalIdentity`, `SearchQuery` и `Cluster` — canonical identities, а не аналитические результаты. `ProductSnapshot`, `SearchVisibilitySnapshot`, `ProductQuerySnapshot` и `QueryMetricSnapshot` — существующие post-PR5 source facts; `ImportBatch`, `SourceArtifact` и snapshot revisions сохраняют их provenance. Будущие `SearchPositionSnapshot` и `AdvertisingSnapshot` появляются только в PR, который впервые реально их использует.

**USER-CURATED ANALYTICAL CONTEXT** — сохранённые решения пользователя, определяющие scope анализа, но не являющиеся ни source observations, ни derived analytics. Сюда по смыслу входят product-specific выбор релевантных queries, состав benchmark и его revision. `BenchmarkSet`, `BenchmarkSetRevision` и `BenchmarkMember` — канонические примеры такого context. Точное persisted имя, schema и interface для relevant-query selection определит PR6 Implementation Spec по фактическому `main`; эта архитектура не вводит заранее новые implementation entities для него.

| Категория | Примеры |
|---|---|
| Source fact | Ozon query popularity/frequency; `average_position` из own-product report; `ProductSnapshot` turnover, total DRR и ordered units; фактически сообщённый `no_action_share` |
| User-curated context | query, включённый/исключённый пользователем как релевантный own SKU; competitor, включённый в `BenchmarkSetRevision` |
| Derived analytic | benchmark median, P25/P75 и delta; estimated promotion spend; advertising support per sold unit; position gap; Share of Top; performance status; confidence |
| Diagnostic / decision output | traffic problem; conversion problem; availability-confounded diagnosis; candidate for ramp-up; insufficient data; explainable Query Opportunity verdict |

Смысловой инвариант: **SOURCE FACT ≠ USER-CURATED CONTEXT ≠ DERIVED ANALYTIC ≠ DIAGNOSTIC INTERPRETATION**. UI остаётся presentation layer.

### 12.2. Benchmark definition, inputs и result

Эти три понятия не смешиваются:

1. **Benchmark definition** — `BenchmarkSet`, `BenchmarkSetRevision`, `BenchmarkMember`. Revision фиксирует состав выбранных пользователем прямых competitors; изменение состава создаёт новую immutable revision и не переписывает старую.
2. **Benchmark inputs** — canonical source facts из соответствующих snapshot histories. Benchmark вычисляется из compatible current snapshot revisions вместе с конкретной `BenchmarkSetRevision` и не создаёт вторую копию source truth. `BenchmarkSnapshot` не является source of truth и не должен становиться дублирующей competitor-metric history. Materialized cache допустим позднее только как техническая оптимизация при доказанной необходимости.
3. **Benchmark result** — derived analytic. Когда применимо, его семантика выражает own value, median, P25/P75 только при достаточной sample, sample size, delta, metric direction, performance status, confidence, benchmark revision и period/grain context.

Точный Python DTO/class, DB table, API JSON, enum names, thresholds, минимальный N для quantiles, confidence algorithm и обязательный набор delta не фиксируются здесь: это scope PR7 Implementation Spec.

Членство Product в `BenchmarkSetRevision` не означает участие во всех metrics. Для каждого сравнения независимо формируется metric-specific valid sample по availability metric, требуемым dimensions/grain, совместимому period/observation context и valid current source revision. Поэтому **BenchmarkSet member count != metric sample size**: если выбрано 12 competitors, а совместимая CR есть у четырёх, `sample_size` CR равен 4, не 12. Правило действует для price, sales, CR, advertising intensity, Search Visibility factors, positions и других metrics. Search Visibility factor comparison использует только валидные competitor observations для того же query, cluster и совместимого observation context.

Period/grain compatibility — строгий gate:

- compatible period/grain → comparison may be calculated;
- incompatible period/grain → comparison не рассчитывается как comparable и возвращает явное `INSUFFICIENT_DATA`, `PERIOD_MISMATCH` или feature-specific equivalent.

Частичная совместимость сама по себе не разрешает расчёт с пониженным confidence. Любое aggregation/alignment, объявляющее разные исходные grains совместимыми, должно быть явно обосновано feature analytics spec и покрыто tests. Нельзя молча сопоставлять daily position с 28-day CR row-by-row, копировать query metric на cluster level, считать overlapping-but-different periods идентичными или заменять missing observation нулём.

### 12.3. Чистота source history и воспроизводимость analytics

Analytics MUST NOT mutate, repair, clamp, rewrite или «improve» source snapshots. Необычный source fact может привести к отклонению comparison, снижению confidence, warning или insufficient-data state, но остаётся неизменным вместе с provenance. Исправление source приходит только новой source revision по существующему revision contract; analytics никогда не производит «corrected source revision».

Derived analytics не является source of truth, поэтому persistent result tables не создаются заранее ради гипотетической истории. Если result когда-либо materialized, persistently cached, explicitly saved или используется как reproducible historical result, должен определяться достаточный calculation context: source observation/revision inputs и provenance, где применимо; period/date; benchmark revision; analysis grain/dimensions; calculation/model version; sample size/confidence, где применимо. Изменение формулы не меняет source facts. Exact storage schema для saved results здесь не проектируется.

### 12.4. Feature-specific analytics, не линейный pipeline

```text
                    Source Facts
                         +
              Curated Analytical Context
                /        |          \
               ↓         ↓           ↓
        Core Benchmark  Search    Query Opportunity
               │       Visibility       │
               ↓                        │
          Diagnostics                   │
                                        ↓
                                     Ramp-up
```

Это информационная схема, не exact module-call graph. Analytics modules могут быть sibling consumers source facts/context; один analytical result не обязан становиться source input другого модуля. Feature-specific semantic rules остаются внутри соответствующего analytics module.

YAGNI запрещает заранее вводить универсальные `GenericBenchmarkEngine`, `GenericBenchmarkResult`, `GenericMetricBenchmarkRepository` или аналоги. Проверенные low-level median/quantile helpers можно переиспользовать после появления второго реального use case, но semantic comparison rules остаются feature-specific: product-level core benchmark, Search Visibility factors, advertising intensity и Query Opportunity positions имеют разные grain и semantics. Общая `BenchmarkSetRevision` не превращает их в один generic semantic engine.

Advertising intensity показывает границы слоёв: turnover, total DRR и ordered units — source facts; estimated promotion spend `≈ turnover × total DRR` и advertising support per sold unit `= estimated promotion spend / ordered units` — derived metrics; benchmark сравнивает own derived value с совместимыми competitor derived values в текущей `BenchmarkSetRevision`. Более низкая intensity не автоматически «better»: интерпретация также зависит от position, popularity, traffic и sales/result.

Query Opportunity — отдельный analytical module, не строка Generic Core Benchmark. Он комбинирует Query Demand, Query Quality, Visibility Gap и Position Stability и в будущем PR10 может использовать `QueryMetricSnapshot`, `SearchPositionSnapshot`, `BenchmarkSetRevision`/members и own product/query context. Market query CR характеризует market query intent/quality, а не CR competitor Product. Модуль не создаёт Opportunity Score 0–100; PR10 implementation здесь не проектируется.

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
ZIP репозитория → start.bat → portable runtime → FastAPI + Static Web UI → SQLite
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
