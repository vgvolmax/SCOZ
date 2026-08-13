# SCOZ PR Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Последовательно реализовать SCOZ как локальное portable Windows-приложение для benchmark-диагностики карточек Ozon, поисковой аналитики и режима «Разгон», не нарушая утверждённые продуктовые, архитектурные и UI/UX-контракты.

**Architecture:** SCOZ строится как `Source Adapter → Ingestion → Normalized Domain Model → Persistence/History → Analytics Engines → Application Services → FastAPI → React UI`. История snapshots и data lineage являются фундаментом с первого этапа. Аналитическое ядро не зависит от конкретного XLSX/API, а UI не содержит бизнес-расчётов.

**Tech Stack:** Windows portable runtime, Python, FastAPI, SQLite, React, TypeScript, pytest, frontend component/smoke tests, GitHub Actions/Windows CI, `openpyxl`/`pandas` внутри ingestion, HTTP clients для Ozon/MPStats.

## Global Constraints

- Пользовательский контракт: `ZIP → распаковать → start.bat → приложение открывается в браузере`.
- Пользователю не нужны системные Python, Node.js/npm, Docker, PostgreSQL, инсталлятор или права администратора.
- Backend слушает только `127.0.0.1`.
- Node/npm используются только при разработке и сборке frontend; в portable-релизе находится готовая статика.
- Основное хранилище — локальная SQLite; SQL не выполняется непосредственно из analytics или API endpoints.
- Исторические наблюдения immutable: новый импорт не перезаписывает прошлые snapshots.
- Для каждого результата сохраняется provenance: источник → raw artifact → normalized snapshot → benchmark set/rule → аналитический результат.
- Реальные API-ключи, коммерческие XLSX, SQLite и чувствительные логи не попадают в публичный GitHub.
- Для тестов используются только синтетические fixtures.
- Ozon является приоритетным источником числовой аналитики; MPStats используется только для главных фото и истории позиций по запросам.
- Benchmark строится только по явно выбранной пользователем группе прямых конкурентов.
- Базовый benchmark — медиана; P25/P75/sample size доступны в детализации.
- Не создавать универсальный score карточки 0–100 и Opportunity Score 0–100 в первой версии.
- Рекламная интенсивность — контекст benchmark, а не отдельный рекламный BI.
- Не рассчитывать цену продавца/СПП-подобные показатели и оценочные рекламные/органические продажи конкурентов.
- Query Opportunity — слой приоритизации внутри «Диагностики» и «Разгона», а не отдельный глобальный раздел.
- Режим «Разгон» не выдаёт сильный вывод при недостатке данных и не утверждает внутреннюю формулу ранжирования Ozon.
- Любое действие/ожидание в UI даёт обратную связь; loading, partial success, error, stale и insufficient-data состояния различимы.
- Главный UI-принцип: `ответ → причина → подтверждающие показатели → исходные данные`.
- Основные аналитические экраны desktop-first и не требуют горизонтальной прокрутки на целевых рабочих разрешениях.
- Каждый PR должен быть mergeable отдельно, иметь собственные acceptance criteria и тесты и не оставлять основной сценарий в заведомо сломанном состоянии.

---

## 1. Документы-источники

Этот план опирается на следующие нормативные документы репозитория:

1. `ТЗ — система диагностики и benchmark-аналитики карточек Ozon.md`;
2. `Дополнение к ТЗ — benchmark рекламной интенсивности.md`;
3. `Дополнение к ТЗ — Query Opportunity Benchmark.md`;
4. `docs/superpowers/specs/2026-08-13-scoz-architecture-design.md`;
5. `docs/superpowers/specs/2026-08-13-scoz-ui-ux-design.md`.

При конфликте:

- Product Spec определяет **что** должна делать система;
- Architecture Design определяет технические границы;
- UI/UX Design определяет пользовательское поведение и feedback contract;
- этот PR Plan определяет порядок реализации и границы изменений.

### Уточнение канонической domain model

В ходе PR-планирования выявлен один терминологический пробел Architecture Design: отдельная история аналитики **собственного SKU по поисковому запросу** нужна продуктовой спецификации, но не была названа отдельной сущностью в списке domain entities.

В дальнейшей разработке канонически использовать:

`ProductQuerySnapshot = product × search_query × period/observation`

для показателей собственного товара по запросу, например позиции, показов/видимости, переходов, конверсий и заказов, если соответствующая гранулярность доступна источнику.

Это не расширяет продуктовый scope, а явно фиксирует уже предусмотренный Product Spec поток «аналитика собственного товара / поисковые запросы».

---

## 2. Принцип разбиения на PR

PR делятся не по экранным макетам и не по внешним API, а по устойчивым проверяемым возможностям.

Каждый PR должен:

- иметь один основной архитектурный результат;
- заканчиваться работающим и тестируемым состоянием;
- не тащить будущую бизнес-логику «на всякий случай»;
- не создавать зависимость analytics от конкретного источника;
- включать UX states, если появляется пользовательское действие;
- включать миграции и тесты, если меняется storage;
- включать synthetic fixtures, если добавляется новый источник;
- содержать документацию только по реально реализованному контракту.

Не объединять несколько PR только ради сокращения их количества, если независимый reviewer мог бы обоснованно принять одну часть и отклонить другую.

---

## 3. Этапы релиза

### Phase A — Foundation & Data Plane

PR1–PR5.

Результат: portable-приложение запускается, имеет корректную историческую модель данных и умеет безопасно импортировать основные Ozon XLSX в нормализованный storage.

### Phase B — Diagnostic MVP

PR6–PR10.

Результат: пользователь может выбрать прямых конкурентов, получить benchmark и автоматическую диагностику, увидеть поисковые возможности и кластерную heatmap.

Это первая полноценная пользовательская вертикаль, пригодная для реальной проверки методологии на данных.

### Phase C — Automation & Ramp-up

PR11–PR14.

Результат: ручные источники постепенно заменяются официальными API там, где это возможно; собирается собственная рекламная история; реализуется позиционно-нормализованная конверсия, сценарии разгона и наблюдение органической опоры.

### Phase D — Release Hardening

PR15.

Результат: проверенный portable Windows release, миграции/восстановление, устойчивые ошибки источников, support diagnostics и сквозной regression suite.

---

## 4. Dependency graph

```text
PR1 Portable App Foundation
  ↓
PR2 Domain + Temporal Storage + Lineage
  ↓
PR3 Ozon Product Analytics XLSX
  ↓
PR4 Ozon Search Visibility XLSX
  ↓
PR5 Query Metrics + Own Product Queries XLSX
  ↓
PR6 MPStats Images + Benchmark Set Workflow
  ↓
PR7 Core Benchmark + Advertising Intensity
  ↓
PR8 Diagnostic Workspace + Data Readiness
  ↓
PR9 Search Visibility Heatmap
  ↓
PR10 MPStats Position History + Query Opportunity
  ↓
PR11 Ozon Public API Sync Framework
  ↓
PR12 Performance API + Advertising History
  ↓
PR13 Ramp-up Core: Position-normalized CR + Verdict
  ↓
PR14 Ramp-up Scenarios + Organic Support Trend
  ↓
PR15 Portable Release Hardening
```

Реализация рекомендуется именно в этом порядке. Некоторые adapters технически могли бы разрабатываться параллельно, но последовательный merge снижает стоимость интеграции и делает каждый следующий PR опирающимся на уже проверенный контракт.

---

## 5. Краткий индекс PR

| PR | Название | Основной результат | Пользовательская ценность | Размер |
|---|---|---|---|---|
| 1 | Portable Application Foundation | Запускаемый local web-app | SCOZ реально стартует через `start.bat` | L |
| 2 | Domain, Temporal Storage & Lineage | Каноническая модель + SQLite history | Данные можно безопасно накапливать | L |
| 3 | Ozon Product Analytics Import | Импорт «Товары на Ozon» | Появляется список SKU и товарные snapshots | M/L |
| 4 | Search Visibility Import | Импорт «Что влияет на место» | Появляются query×cluster факторы | M |
| 5 | Query Analytics Imports | Рыночные запросы + запросы своего SKU | Появляются Demand/Quality и own-query history | M/L |
| 6 | Benchmark Set & MPStats Images | Выбор реальных конкурентов по фото | Benchmark становится осмысленным | L |
| 7 | Core Benchmark & Ad Intensity | Медианы/P25/P75/Δ + реклама/продажу | Видно, где мы выше/ниже конкурентов | M/L |
| 8 | Diagnostic Workspace | Диагноз + readiness + drill-down | За секунды понятен главный провал SKU | L |
| 9 | Search Visibility Heatmap | Query×cluster benchmark | Видно системные и локальные причины | M/L |
| 10 | Query Opportunity | MPStats позиции + Share of Top | Видно, по каким запросам стоит расти | L |
| 11 | Ozon Public API Sync | API adapters для собственных Ozon-данных | Меньше ручных XLSX | L |
| 12 | Performance API | История собственной рекламы | Появляется честный ad context для разгона | M/L |
| 13 | Ramp-up Core | Position-normalized CR + verdict | Отличаем плохую карточку от плохого места | L |
| 14 | Ramp-up Scenarios | TOP-сценарии + organic support trend | Можно оценивать стратегию разгона/снижения ставки | L |
| 15 | Release Hardening | Production-grade portable release | Приложение можно стабильно отдавать в работу | L |

Размер — относительная оценка review surface, а не календарный срок.

---

# PR1 — Portable Application Foundation

## Цель

Создать минимальный, но настоящий SCOZ application shell, который соблюдает утверждённый portable Windows contract с первого дня.

## Основные файлы/области

- `start.bat`;
- `launcher/`;
- `backend/scoz/main.py`;
- `backend/scoz/api/health.py`;
- `frontend/`;
- build scripts;
- `.gitignore`;
- базовый CI;
- `tests/portable/`, `tests/api/`.

## Scope

- project-local verified Python runtime bootstrap;
- SHA-256/allowlist для runtime artifacts;
- atomic runtime publication;
- OS-backed single-instance lock;
- dependency-free launcher;
- FastAPI health endpoint;
- React + TypeScript shell;
- frontend build раздаётся backend как статика;
- backend bind только на `127.0.0.1`;
- автоматическое открытие браузера после успешного health check;
- базовая структура `Товары / Данные / Настройки` без бизнес-аналитики;
- локальные логи без секретов;
- Windows CI/smoke для старта application shell.

## UX contract

Пользователь всегда понимает стадии запуска:

- проверка runtime;
- подготовка приложения;
- запуск backend;
- открытие UI;
- понятная ошибка при невозможности запуска.

Не допускается «чёрное окно без объяснений» на длительной операции.

## Acceptance criteria

- На Windows-машине без системных Python/Node `start.bat` поднимает приложение.
- Повторный запуск использует уже валидный runtime и не переустанавливает его.
- Параллельный запуск корректно обрабатывается lock-механизмом.
- UI открывается только после успешного health check.
- Backend недоступен с внешнего интерфейса сети.
- В релизном runtime отсутствует зависимость от системного Node/npm.
- Backend и frontend smoke tests проходят в CI.

## Out of scope

- SQLite business schema;
- импорт Ozon;
- benchmark;
- API credentials;
- реальные аналитические screens.

---

# PR2 — Canonical Domain, Temporal SQLite & Data Lineage

## Цель

Создать устойчивый data foundation до появления реального импорта и аналитики.

## Основные файлы/области

- `backend/scoz/domain/`;
- `backend/scoz/persistence/`;
- `backend/scoz/migrations/`;
- `backend/scoz/application/imports/` базовые contracts;
- `tests/domain/`;
- `tests/persistence/`.

## Domain entities

Минимально:

- `Product`;
- ownership/признак собственного товара;
- `SearchQuery`;
- `Cluster`;
- `BenchmarkSet`;
- `BenchmarkMember`;
- `ProductSnapshot`;
- `ProductQuerySnapshot`;
- `SearchVisibilitySnapshot`;
- `SearchPositionSnapshot`;
- `QueryMetricSnapshot`;
- `AdvertisingSnapshot`;
- `ImportBatch`;
- `SourceArtifact`.

## Scope

- versioned SQLite migrations;
- repository interfaces;
- immutable snapshot semantics;
- `observed_at`, `period_start`, `period_end`, `imported_at`;
- raw artifact metadata и SHA-256;
- parser/adapter version в provenance;
- deduplication keys;
- local directories `data/imports`, `data/cache`, `data/logs`;
- запрет SQL вне persistence layer;
- тесты восстановления истории на дату/период.

## Acceptance criteria

- Повторное наблюдение за новую дату создаёт новый snapshot, а не обновляет старый.
- Идентичный source artifact определяется как duplicate предсказуемо.
- Repository возвращает domain structures, а не raw SQL rows.
- Можно восстановить provenance любого сохранённого snapshot до `SourceArtifact`/`ImportBatch`.
- Миграции работают на чистой БД и при обновлении предыдущей версии schema.
- Реальные пользовательские данные не нужны для tests.

## Out of scope

- конкретные XLSX parsers;
- benchmark calculations;
- UI аналитики.

---

# PR3 — Ozon «Товары на Ozon» Import Vertical

## Цель

Реализовать первый end-to-end ingestion flow на реальном классе Ozon-отчёта.

## Основные файлы/области

- `backend/scoz/sources/ozon_xlsx/product_analytics.py`;
- `backend/scoz/ingestion/product_analytics.py`;
- `backend/scoz/application/imports/product_analytics.py`;
- `backend/scoz/api/imports.py`;
- `frontend/src/features/data-imports/`;
- `frontend/src/features/products/`;
- synthetic XLSX fixtures и parser tests.

## Scope

Парсить и сохранять доступные поля «Товары на Ozon», необходимые текущему Product Spec, включая при наличии:

- SKU/product identity;
- title/brand;
- turnover;
- units ordered;
- impressions;
- search/catalog views;
- card views;
- conversion metrics;
- cart metrics;
- buyer price;
- stock-related context;
- total DRR;
- promotion days/flags;
- остальные исходные поля — как source/raw context, если они не входят в основную domain model.

Также:

- пользователь может явно отметить/выбрать собственный SKU;
- раздел `Данные` показывает import history;
- раздел `Товары` показывает обнаруженные собственные товары;
- импорт поддерживает partial row errors без потери валидных строк.

## UX contract

Состояния импорта:

`VALIDATING → IMPORTING → SUCCESS / PARTIAL_SUCCESS / FAILED`

После завершения показать:

- тип отчёта;
- период;
- количество импортированных строк;
- пропущенные строки;
- причины ошибок;
- freshness/result state.

## Acceptance criteria

- Валидный synthetic report создаёт `Product` + `ProductSnapshot`.
- Повторный импорт идентичного файла не размножает snapshots.
- Новый период сохраняется как новая история.
- Частично битая строка не блокирует валидные записи.
- Несовместимая структура файла блокируется понятной ошибкой.
- Пользователь после импорта видит товар в `Товары` и историю импорта в `Данные`.

---

# PR4 — Ozon «Что влияет на место» Search Visibility Import

## Цель

Добавить источник факторов поисковой выдачи в гранулярности `product × query × cluster × observation`.

## Основные файлы/области

- `backend/scoz/sources/ozon_xlsx/search_visibility.py`;
- `backend/scoz/ingestion/search_visibility.py`;
- repositories для queries/clusters/visibility;
- import UI states;
- synthetic fixtures/tests.

## Scope

Сохранять как минимум:

- query;
- cluster;
- product/SKU;
- position;
- Ozon summary score, если присутствует;
- relevance;
- popularity;
- promotion flags;
- CPC;
- CPO, если присутствует;
- delivery;
- buyer price;
- price index;
- rating;
- reviews;
- дополнительные source fields для drill-down.

Не строить heatmap в этом PR.

## Acceptance criteria

- Один импорт создаёт корректные `SearchQuery`, `Cluster`, `SearchVisibilitySnapshot`.
- Одинаковый SKU в разных кластерах не схлопывается в одну запись.
- Одинаковый query на разные даты сохраняет историю.
- Отсутствующее значение не превращается молча в `0`.
- UI импорта сообщает period/query/cluster coverage и ошибки.

---

# PR5 — Search Query Metrics & Own Product Query Imports

## Цель

Закрыть оба оставшихся поисковых data flows: метрики самого рыночного запроса и аналитику собственного SKU по запросам.

## Основные файлы/области

- `backend/scoz/sources/ozon_xlsx/query_metrics.py`;
- `backend/scoz/sources/ozon_xlsx/product_queries.py`;
- соответствующий ingestion/application code;
- `QueryMetricSnapshot`;
- `ProductQuerySnapshot`;
- synthetic fixtures/tests.

## Scope A — рыночные метрики запросов

При наличии источника сохранять:

- query popularity/frequency;
- demand dynamics;
- CR to cart;
- CR to order;
- share without actions;
- ordered units;
- ordered turnover;
- period.

## Scope B — собственный SKU по запросу

При наличии источника сохранять:

- query;
- own SKU;
- visibility/impressions/searchers;
- position;
- transitions;
- conversion metrics;
- orders/turnover;
- period.

Не смешивать Query CR рынка с CR конкретного товара.

## Acceptance criteria

- Рыночный query report создаёт `QueryMetricSnapshot`.
- Own product query report создаёт `ProductQuerySnapshot`.
- Два типа snapshot невозможно случайно спутать в repository/API contract.
- Разные aggregation periods сохраняются явно.
- UI раздела `Данные` показывает, какие поисковые источники доступны для SKU.

---

# PR6 — MPStats Source Settings, Product Images & Benchmark Set Workflow

## Цель

Позволить пользователю сформировать корректную benchmark-группу прямых конкурентов, используя кандидатов из Ozon и главные фото из MPStats.

## Основные файлы/области

- local source settings/secret storage;
- `backend/scoz/sources/mpstats/`;
- `backend/scoz/application/benchmark_sets/`;
- `backend/scoz/api/benchmark_sets.py`;
- `frontend/src/features/settings/sources/`;
- `frontend/src/features/benchmark-set/`;
- API contract tests с mocked MPStats.

## Scope

- настройка MPStats credentials локально;
- `Проверить подключение`;
- credentials не возвращаются frontend в открытом виде;
- кандидаты строятся из импортированной релевантной выдачи Ozon;
- для кандидатов загружаются главные фото;
- пользователь вручную включает/исключает товары;
- benchmark set сохраняется на own SKU;
- один Product может входить в benchmark нескольких own SKU;
- fallback/empty state, если фото конкретного SKU недоступно;
- удаление/добавление competitor не удаляет исторические snapshots товара.

## UX contract

Пользователь видит:

- собственный SKU;
- кандидатов с фото/названием/SKU/ценой при наличии;
- сколько товаров выбрано;
- состояние сохранения;
- отсутствие фото отдельно от отсутствия товара;
- connection/error state MPStats.

## Acceptance criteria

- BenchmarkSet нельзя сохранить для несуществующего own product.
- Пользователь может добавить, удалить и повторно открыть сохранённую группу.
- Фото загружаются через adapter, а не напрямую из UI.
- MPStats numerical sales estimates не попадают в benchmark data model.
- API key отсутствует в network payload к frontend после сохранения.
- Benchmark workflow работает и при частично недоступных фотографиях.

---

# PR7 — Core Benchmark Engine & Advertising Intensity

## Цель

Реализовать чистый математический benchmark engine на выбранной benchmark-группе.

## Основные файлы/области

- `backend/scoz/analytics/benchmark/`;
- benchmark application services/API DTO;
- детерминированные unit tests;
- минимальный benchmark detail view.

## Scope

Для метрик рассчитывать:

- own value;
- median;
- P25;
- P75;
- sample size;
- delta;
- status;
- корректное направление метрики «больше лучше / меньше лучше / только контекст».

Рекламная интенсивность:

```text
promotion_spend = turnover × total_DRR
promotion_intensity = promotion_spend / units_ordered
```

Дополнительно показывать DRR как контекст.

Рекламная интенсивность не получает автоматическую оценку «меньше всегда лучше»; интерпретация зависит от результата, позиции, популярности и трафика.

## Acceptance criteria

- Median/P25/P75 воспроизводимы на фиксированном dataset.
- Один крупный competitor не искажает базовый benchmark через arithmetic mean.
- Missing values исключаются по явно определённым правилам и уменьшают sample size.
- Sample size возвращается вместе с результатом.
- Изменение BenchmarkSet меняет расчёт без изменения исходных snapshots.
- Advertising intensity рассчитывается только при достаточных turnover/DRR/units и корректно сообщает отсутствие данных.
- Никакой текстовой диагноз не формируется внутри Benchmark Engine.

---

# PR8 — Diagnostic Engine, Product Workspace & Data Readiness

## Цель

Дать пользователю главный рабочий экран SCOZ: быстрый диагноз SKU относительно выбранных конкурентов.

## Основные файлы/области

- `backend/scoz/analytics/diagnostics/`;
- `backend/scoz/application/diagnosis/`;
- `/api/products/{id}/diagnosis`;
- `frontend/src/features/product-workspace/diagnosis/`;
- readiness view models;
- diagnostic unit/component tests.

## Scope

Минимальные reason codes:

- `TRAFFIC_DEFICIT`;
- `WEAK_CONVERSION`;
- `CARD_CONVERSION_PROBLEM`;
- `SEARCH_RESULT_PROBLEM`;
- `OFFER_PROBLEM`;
- `COMBINED_GAP`;
- `HIGH_AD_SUPPORT_LOW_RESULT`.

Главный экран:

- итоговые продажи относительно benchmark;
- трафик;
- показ→заказ;
- card→cart / search→cart по доступности;
- компактный контекст price/delivery/rating;
- рекламная интенсивность;
- максимум 2–3 главных вывода;
- benchmark drill-down;
- активный SKU/period/benchmark set/freshness;
- Data Readiness по доступным источникам.

## UX contract

Не показывать пустой dashboard.

Различать:

- ready;
- stale;
- missing benchmark;
- partial data;
- insufficient data;
- source/import error.

На `Почему SCOZ так считает?` показывать конкретные показатели и benchmark, а не внутренний rule ID.

## Acceptance criteria

- Детерминированные datasets приводят к ожидаемым diagnosis reason codes.
- UI не содержит бизнес-условий определения диагноза.
- На основном экране нет P25/P75 и длинного списка всех полей Ozon.
- Benchmark details раскрывают sample size и список конкурентов.
- Смена benchmark-группы явно показывает refresh/recalculation state.
- Пользователь всегда видит период и freshness результата.

---

# PR9 — Search Visibility Benchmark & Cluster Heatmap

## Цель

Показать, по каким кластерам и факторам выбранный query отстаёт от benchmark.

## Основные файлы/области

- `backend/scoz/analytics/search_visibility/`;
- search visibility application/API;
- `frontend/src/features/product-workspace/search/heatmap/`;
- tests на cluster/query granularity.

## Scope

Основная гранулярность:

`own SKU × query × cluster`

Основная heatmap:

- position;
- relevance;
- popularity;
- delivery;
- price.

Дополнительные Ozon factors доступны через drill-down.

Общий режим `Все кластеры`:

- weighted by demand, если надёжный вес доступен;
- иначе явно обозначенное unweighted aggregation.

## Acceptance criteria

- Выбранный query остаётся видимым активным контекстом.
- Один и тот же factor оценивается относительно валидных членов сохранённого BenchmarkSet.
- Отсутствие observation конкурента не трактуется как обычная позиция/нулевое значение.
- UI отличает системную проблему от локальной через краткое summary.
- Основная heatmap содержит только пять предусмотренных столбцов и не превращается в raw Explainer table.
- Все кластеры отображают метод агрегации.

---

# PR10 — MPStats Position History & Query Opportunity

## Цель

Добавить слой приоритизации поисковых запросов на основе спроса, качества интента и устойчивого разрыва позиций с выбранными конкурентами.

## Основные файлы/области

- `backend/scoz/sources/mpstats/positions.py`;
- `SearchPositionSnapshot` ingestion;
- `backend/scoz/analytics/query_opportunity/`;
- `/api/products/{id}/query-opportunities`;
- query opportunity UI перед heatmap;
- MPStats mocked contract tests;
- deterministic analytics tests.

## Scope

MPStats positions:

- daily/available history `date × product × query × position`;
- own SKU и выбранные competitors;
- provenance source.

Query Opportunity blocks:

1. Query Demand;
2. Query Quality;
3. Visibility Gap;
4. Position Stability.

Derived metrics:

- median position за период;
- Share of TOP-10;
- Share of TOP-20;
- optional TOP-3/TOP-50 в детализации;
- benchmark median position;
- доля benchmark competitors выше own SKU;
- explainable priority class.

Не создавать единый Opportunity Score 0–100.

## UX contract

Перед heatmap показывается компактный список `Поисковые возможности`:

- query;
- demand;
- один ключевой quality metric;
- own position;
- benchmark position;
- понятный verdict.

## Acceptance criteria

- Query Opportunity не использует MPStats sales estimates.
- CR запроса не маркируется как CR конкретного competitor.
- Share of Top считается по фактическим дням наблюдения и возвращает denominator/sample size.
- Missing/non-observed positions обрабатываются явно и не превращаются в «позицию 0».
- High-frequency low-quality query может получить более низкий приоритет, чем менее частотный, но более коммерческий запрос.
- Клик по query переводит пользователя в существующую cluster heatmap без нового глобального раздела.

### Milestone: Diagnostic MVP

После merge PR10 SCOZ должен обеспечивать полный основной диагностический цикл:

`SKU → benchmark competitors → общий диагноз → приоритетные queries → cluster/factor diagnosis`.

На этой точке методологию уже можно проверять на реальных рабочих сценариях до автоматизации всех источников и до сложной ramp-up модели.

---

# PR11 — Ozon Public API Sync Framework

## Цель

Начать заменять ручной импорт официальными Ozon APIs, не меняя domain и analytics contracts.

## Основные файлы/области

- generic source connection/sync contracts;
- `backend/scoz/sources/ozon_seller_api/`;
- scheduler/explicit sync application services без фонового cloud service;
- `frontend/src/features/settings/sources/ozon/`;
- sync states в `Данные`;
- API mocks/contract tests.

## Scope

- Ozon Seller API credentials local-only;
- connection test;
- explicit manual sync;
- adapters для доступной официальной аналитики собственного товара/поисковых запросов и иных уже подтверждённых public endpoints;
- mapping в существующие `ProductQuerySnapshot`/другие domain entities;
- source priority: более точный Ozon source для own SKU может иметь приоритет над MPStats observations;
- rate limit/retry/error mapping;
- sync provenance.

Не менять Analytics Engine ради формы API response.

## Acceptance criteria

- API и XLSX для одной domain entity создают совместимые normalized snapshots.
- API credentials не возвращаются frontend после сохранения.
- Rate limit, auth error, network error и incompatible response имеют разные user-facing states.
- Неудачный sync не повреждает предыдущую историю.
- Пользователь видит последнюю успешную синхронизацию и freshness.

## Out of scope

- undocumented internal Ozon Explainer endpoint как обязательная зависимость;
- Performance API — отдельный PR12.

---

# PR12 — Ozon Performance API & Advertising History

## Цель

Собирать наблюдаемую рекламную историю собственного SKU для режима «Разгон».

## Основные файлы/области

- `backend/scoz/sources/ozon_performance/`;
- `AdvertisingSnapshot` ingestion/repositories;
- source settings/sync UI;
- advertising history API/view model;
- contract/integration tests.

## Scope

Сохранять доступные наблюдаемые параметры собственного продвижения:

- campaign/product identity;
- date/period;
- bid/strategy-relevant values, если доступны;
- impressions;
- clicks;
- CPC;
- spend;
- attributed orders/sales, если source предоставляет;
- другие необходимые observed values для связи рекламы и позиции.

Не использовать Performance API для конкурентного benchmark.

## Acceptance criteria

- Advertising history immutable и привязана к собственному SKU/периоду.
- Наблюдаемые Performance metrics помечены как source facts, а не модельные оценки.
- Data Readiness показывает наличие/глубину рекламной истории.
- Sync errors не уничтожают предыдущие AdvertisingSnapshots.
- UI не превращается в отдельный рекламный BI.

---

# PR13 — Ramp-up Core: Position-normalized Conversion & Verdict

## Цель

Реализовать первую честную модель «Разгона»: определить, плохая ли CR сама по себе или соответствует текущей позиции.

## Основные файлы/области

- `backend/scoz/analytics/ramp_up/position_conversion.py`;
- `backend/scoz/analytics/ramp_up/readiness.py`;
- `backend/scoz/analytics/ramp_up/verdict.py`;
- ramp-up application/API;
- `frontend/src/features/product-workspace/ramp-up/`;
- statistical/deterministic tests.

## Scope

- position buckets конфигурируемы;
- benchmark typical CR per comparable position bucket при достаточной гранулярности;
- различение cross-sectional и longitudinal evidence;
- собственная longitudinal history получает больший вес при достаточных наблюдениях;
- confidence `HIGH / MEDIUM / INSUFFICIENT`;
- readiness gate;
- основной verdict:
  - кандидат на разгон;
  - сначала улучшить карточку/оффер;
  - дополнительный разгон не требуется;
  - проблема карточки/оффера;
  - недостаточно данных;
- график `position → conversion` только при корректной evidence base.

## Критическое ограничение

Не использовать aggregate competitor CR как CR конкретной позиции/query, если такой гранулярности нет.

Если доступные данные не позволяют построить статистически честную curve, engine обязан вернуть `INSUFFICIENT_DATA` или более слабый явно обозначенный оценочный вывод.

## Acceptance criteria

- Один и тот же dataset всегда даёт один verdict/confidence.
- Маленькая выборка не создаёт прогноз.
- UI объясняет, каких данных не хватает.
- Market observations, own history и current point визуально различимы.
- График/текст не формулируют correlation как доказанную causality.
- Verdict учитывает Query Opportunity: низкая позиция по слабому query не становится автоматически основанием для разгона.

---

# PR14 — Ramp-up Bid Scenarios & Organic Support Trend

## Цель

Добавить сценарное планирование ставки и наблюдение, закрепляется ли товар после разгона.

## Основные файлы/области

- `backend/scoz/analytics/ramp_up/bid_position.py`;
- `scenario_estimator.py`;
- `organic_support.py`;
- ramp-up DTO/UI extensions;
- deterministic/history tests.

## Scope

Сценарии:

- Сейчас;
- TOP-20;
- TOP-10;
- TOP-3.

Для сценария при достаточных данных:

- expected position range;
- expected CR range;
- estimated bid range;
- confidence.

Organic Support Trend:

- оценка ставки, необходимой для удержания выбранного TOP-N во времени;
- снижение требуемой ставки при сопоставимой позиции трактуется как наблюдаемый признак укрепления органической опоры;
- никакого утверждения скрытого «base score Ozon».

## Acceptance criteria

- Bid выдаётся диапазоном, а не псевдоточной гарантией.
- При недостатке history соответствующий scenario скрывается/маркируется unavailable.
- Тренд органической опоры строится только на сопоставимых observations.
- Текущая рекламная интенсивность используется как контекст, а не как единственный trigger повысить ставку.
- UI содержит максимум четыре предусмотренные смысловые области режима «Разгон».

### Milestone: Full Analytical v1

После PR14 реализованы оба ключевых режима Product Spec:

- Диагностика;
- Разгон.

API automation ещё может расширяться, но аналитический продуктовый контур считается функционально полным.

---

# PR15 — Portable Release Hardening & Operational Readiness

## Цель

Довести весь накопленный продукт до состояния устойчивого portable Windows release.

## Основные файлы/области

- launcher/bootstrap hardening;
- Windows CI;
- migrations/backup/restore checks;
- logging/support diagnostics;
- end-to-end regression suite;
- release manifest/build scripts;
- documentation for end-user startup/recovery.

## Scope

- clean-machine bootstrap verification;
- repeated start/update verification;
- runtime integrity/failure recovery;
- DB migration backup before destructive-risk migration;
- graceful recovery after interrupted import/sync;
- stale data handling audit;
- external source auth/rate-limit/network error audit;
- secret masking audit;
- local support bundle/log export без credentials;
- full smoke journey:
  `start → import/sync → choose SKU → benchmark group → diagnosis → query opportunity → heatmap → ramp-up`;
- performance sanity на реалистичном synthetic dataset;
- Windows scaling 125–150% UI review;
- final accessibility/basic keyboard pass.

## Acceptance criteria

- Clean Windows environment запускает release через `start.bat` без системных runtime.
- Все migrations проходят с предыдущей поддерживаемой schema.
- Прерывание импорта/API sync не повреждает committed snapshots.
- Secret scan не находит credentials в logs/frontend payloads/repo fixtures.
- Основной CJM проходит end-to-end на synthetic regression dataset.
- Loading/empty/error/partial/stale/insufficient states проверены для ключевых workflows.
- Release artifact содержит только необходимые runtime/app assets и не требует npm у пользователя.

### Milestone: Release Candidate

После PR15 приложение можно передавать рабочему пользователю для регулярной эксплуатации и дальнейшего предметного тестирования аналитических правил.

---

## 6. Optional post-v1 source adapter: Ozon internal Search Visibility API

Этот adapter **не входит в обязательную цепочку PR1–PR15**.

Причина: текущая продуктовая система уже умеет работать через XLSX «Что влияет на место», а undocumented/internal endpoint не должен становиться архитектурной зависимостью до отдельной проверки.

Он может быть реализован позднее отдельным PR только после feasibility review:

- подтверждён точный endpoint/contract;
- понятна авторизация;
- понятна допустимость использования;
- известна устойчивость к изменениям;
- данные действительно покрывают поля XLSX/UI;
- adapter может быть изолирован за существующим `SearchVisibilitySnapshot` contract.

Если условия выполнены, такой PR меняет только source/ingestion слой и sync UX, но не analytics/domain/UI methodology.

---

## 7. Cross-PR UX requirements

Каждый PR с пользовательским действием обязан реализовать только применимые, но явные состояния:

- idle;
- validating;
- running/loading;
- success;
- partial success;
- failed;
- stale;
- insufficient data.

Правила:

- длительный процесс показывает stage/progress, а не бесконечный безымянный spinner;
- previous valid data можно оставить во время refresh, но они помечаются как предыдущие;
- empty state объясняет причину и следующий шаг;
- ошибка объясняет, что не удалось, что осталось сохранено и можно ли повторить;
- критически важный success state остаётся видимым в контексте, а не исчезает только в toast;
- active SKU/query/period не теряются при drill-down;
- freshness видна там, где влияет на решение;
- цвет не является единственным носителем статуса.

---

## 8. Cross-PR testing requirements

### TDD

Для новой бизнес-логики сначала фиксировать ожидаемое поведение тестом, затем реализацию.

### Parser tests

Каждый XLSX parser должен иметь минимум:

- valid fixture;
- missing optional field;
- malformed row;
- incompatible schema;
- duplicate import;
- locale/percent/currency/date edge case, если применимо.

### Analytics tests

Каждый analytics engine должен иметь:

- happy path;
- insufficient sample;
- missing values;
- boundary/status cases;
- deterministic expected outputs;
- проверку запрета смешения несовместимых granularities.

### External API tests

- реальные credentials в CI запрещены;
- использовать mocked/recorded synthetic contracts;
- отдельно проверять auth/network/rate-limit/incompatible response.

### UI tests

Для каждого сложного view:

- ready;
- loading/refresh;
- empty;
- partial;
- error;
- insufficient/stale, где применимо.

### Portable tests

PR1 устанавливает базовый Windows smoke; PR15 расширяет его до полного release regression.

---

## 9. PR review gates

PR нельзя считать готовым к merge, если:

- тесты не подтверждают acceptance criteria;
- изменена domain/API schema без миграции/контрактного обновления;
- бизнес-логика появилась во frontend или FastAPI route;
- analytics начал читать XLSX/API напрямую;
- SQL появился вне persistence layer;
- DataFrame стал межмодульным контрактом;
- исторические snapshots обновляются in-place;
- новый metric появился на основном UI без JTBD;
- внешняя ошибка может уничтожить ранее сохранённую историю;
- secrets могут попасть в frontend/log/repo;
- UI action не даёт feedback;
- model estimate выглядит как observed fact;
- PR требует будущего PR, чтобы хотя бы базовый изменённый workflow перестал быть сломанным.

---

## 10. Что должно быть в отдельном ТЗ каждого PR

Перед началом реализации каждого PR создаётся отдельная подробная спецификация.

Она обязана содержать:

1. цель PR и пользовательский результат;
2. зависимости от предыдущих PR;
3. exact scope;
4. explicit non-goals;
5. новые/изменяемые domain entities и interfaces;
6. exact files/modules, которые создаются или изменяются;
7. API contracts/DTO;
8. DB migration/schema changes;
9. UX flow и все states;
10. error handling;
11. synthetic fixtures;
12. unit/integration/component/portable tests;
13. manual QA сценарий;
14. acceptance criteria;
15. Definition of Done;
16. запреты/архитектурные инварианты, особенно важные для этого PR.

ТЗ PR не должно повторно принимать продуктовые решения, уже закреплённые в Product/Architecture/UIUX docs. Оно конкретизирует реализацию в рамках этих решений.

---

## 11. Recommended implementation workflow

Для каждого PR:

1. открыть актуальный `main`;
2. перечитать этот PR Plan и соответствующие Product/Architecture/UIUX sections;
3. написать подробное ТЗ PR;
4. провести self-review ТЗ на scope/ambiguity/contradictions;
5. после approval создать отдельную feature branch/worktree;
6. реализовывать TDD по небольшим задачам;
7. прогнать полный relevant test suite;
8. проверить diff против архитектурных/UX invariants;
9. открыть PR;
10. провести code review и merge только после подтверждения acceptance criteria.

Не начинать следующий PR поверх незамерженного предыдущего, если между ними есть dependency edge из этого плана.

---

## 12. Планируемая последовательность подробных ТЗ

После утверждения этого документа следующий документ:

`PR1 — Portable Application Foundation — Implementation Spec`

После merge PR1 готовится ТЗ PR2 на основании фактического состояния `main`, и так далее.

Это важно: список PR фиксируется сейчас, но exact file paths/signatures последующих PR уточняются по уже смерженному коду, чтобы спецификации не расходились с реальной архитектурой репозитория.

---

## 13. Definition of Done этого PR Development Plan

План считается пригодным для последовательной разработки, если:

- каждый Product Spec capability имеет место в PR1–PR15;
- foundation/history реализуются до зависимой аналитики;
- Diagnostic MVP достигается до подключения сложной ramp-up модели;
- API adapters не диктуют domain/analytics design;
- UI/UX feedback включён в каждый пользовательский vertical;
- рекламная интенсивность и Query Opportunity находятся в правильных контекстах и не превращены в отдельные BI-продукты;
- Ramp-up явно зависит от history/confidence и не обещает причинность/точность, которой нет в данных;
- portable Windows contract защищён с PR1 и окончательно проверяется в PR15;
- каждый PR достаточно изолирован, чтобы для него можно было написать отдельное ТЗ и провести независимый code review.
