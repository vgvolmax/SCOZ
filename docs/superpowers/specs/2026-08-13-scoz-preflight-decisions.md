# SCOZ — Preflight Architecture & Data Decisions

**Дата:** 2026-08-13  
**Статус:** обязательное корректирующее дополнение перед написанием PR-specific ТЗ  
**Репозиторий:** `vgvolmax/SCOZ`

## 1. Назначение документа

Этот документ фиксирует решения, выявленные на итоговом pre-flight аудите до начала реализации PR1.

Он **не добавляет новые пользовательские режимы и не расширяет продуктовый scope**. Его задача — устранить архитектурные неоднозначности, которые могли бы привести к неверной аналитике, потере воспроизводимости или переделке фундамента на поздних PR.

При конфликте с более ранними формулировками этот документ имеет приоритет для следующих тем:

- идентификация сущностей между источниками;
- ревизии наблюдений и исправленные данные;
- версионирование benchmark-групп;
- совместимость периодов и гранулярностей;
- разрешение конфликтующих источников;
- backfill и coverage источников;
- семантика истории позиций MPStats;
- гранулярность режима «Разгон»;
- confidence/availability guardrails;
- технический Operation Feedback Contract;
- безопасность local web-приложения и секретов;
- жизненный цикл пользовательских данных при обновлениях;
- допустимые способы автоматизации Ozon.

Этот документ необходимо читать вместе с:

1. `ТЗ — система диагностики и benchmark-аналитики карточек Ozon.md`;
2. `Дополнение к ТЗ — benchmark рекламной интенсивности.md`;
3. `Дополнение к ТЗ — Query Opportunity Benchmark.md`;
4. `docs/superpowers/specs/2026-08-13-scoz-architecture-design.md`;
5. `docs/superpowers/specs/2026-08-13-scoz-ui-ux-design.md`;
6. `docs/superpowers/plans/2026-08-13-scoz-pr-development-plan.md`.

---

# 2. Каноническая идентификация товара

Один и тот же товар может приходить из разных источников под разными идентификаторами.

Нельзя считать взаимозаменяемыми без явного mapping:

- Ozon SKU;
- Ozon `product_id`;
- `offer_id` продавца;
- идентификатор товара MPStats;
- иные source-specific IDs.

Каноническая модель:

### `Product`

Внутренняя стабильная сущность SCOZ.

### `ProductExternalIdentity`

Связь `Product` с внешним идентификатором.

Минимальные поля:

- `product_id` — внутренний ID SCOZ;
- `source`;
- `identity_type`;
- `identity_value`;
- `source_account_scope`, если идентификатор не является глобальным;
- `valid_from` / `valid_to`, если источник допускает изменение mapping;
- provenance mapping.

Правила:

1. Никогда не объединять товары только по названию, бренду или фото.
2. `offer_id` всегда рассматривать в контексте аккаунта/продавца, если источник не гарантирует глобальную уникальность.
3. Автоматический merge допустим только по проверенному source mapping или идентификатору, для которого контракт источника гарантирует нужную уникальность.
4. Неоднозначный mapping должен приводить к явному состоянию `IDENTITY_CONFLICT`, а не к молчаливому объединению.

---

# 3. Идентификация SearchQuery и Cluster

## 3.1. SearchQuery

`SearchQuery` хранит:

- `raw_text` — строку источника;
- `canonical_text` — консервативно нормализованную строку;
- source-specific query ID, если он существует.

Допустимая нормализация для identity:

- Unicode normalization;
- trim;
- схлопывание повторных пробелов;
- case folding/lowercase.

Не использовать для identity:

- stemming;
- перестановку слов;
- исправление орфографии;
- удаление значимых токенов;
- semantic similarity.

То есть похожие по смыслу запросы остаются разными `SearchQuery`, пока продуктовая логика отдельно не объединит их в аналитическую группу.

## 3.2. Cluster

Если источник предоставляет стабильный cluster ID, он имеет приоритет над названием.

Если источник даёт только текстовое имя, хранить:

- raw name;
- normalized name;
- source;
- provenance.

Переименование кластера не должно автоматически создавать ложную новую географическую сущность, если источник позволяет доказать тот же cluster ID.

---

# 4. Immutable history не означает «одна версия навсегда»

Ozon или другой источник может позднее вернуть **исправленные данные за тот же логический период**.

Поэтому различаются:

1. **дубликат** — повторно импортированы абсолютно те же source data;
2. **новое наблюдение** — новый период/дата/набор dimensions;
3. **ревизия наблюдения** — источник изменил значение для того же логического observation key.

## 4.1. Logical Observation Key

Каждый тип snapshot должен иметь формально определённый logical key, включающий только необходимые dimensions.

Примеры:

- `ProductSnapshot`: product + metric period + source scope;
- `ProductQuerySnapshot`: product + query + period/observation + source scope;
- `SearchVisibilitySnapshot`: product + query + cluster + observed_at + source scope;
- `SearchPositionSnapshot`: product + query + observation date + source scope;
- `AdvertisingSnapshot`: product/campaign + metric period + source scope.

Конкретный key фиксируется в ТЗ соответствующего PR.

## 4.2. ObservationRevision

Исправленные данные не обновляют старую запись in-place.

Новая версия сохраняется отдельно и содержит как минимум:

- `revision_no` или эквивалентный порядок;
- `supersedes_snapshot_id`, если применимо;
- `imported_at`;
- source/provenance;
- hash нормализованного payload.

Предыдущая ревизия остаётся доступна для аудита.

Analytics по умолчанию использует **актуальную авторитетную ревизию**, а не сумму/набор всех ревизий.

---

# 5. Версионирование BenchmarkSet

Состав прямых конкурентов является частью воспроизводимости аналитики.

`BenchmarkSet` — стабильная сущность, привязанная к собственному `Product`.

Каждое сохранённое изменение состава создаёт immutable:

### `BenchmarkSetRevision`

Минимально:

- `benchmark_set_id`;
- `revision_id`;
- `created_at`;
- список `BenchmarkMember`;
- причина/источник изменения при необходимости.

Аналитический результат должен ссылаться не просто на `BenchmarkSet`, а на конкретный `BenchmarkSetRevision`.

Это позволяет ответить:

> какой именно состав конкурентов использовался в расчёте на конкретную дату?

Изменение текущего benchmark не должно переписывать историческую интерпретацию старого анализа.

---

# 6. AnalysisWindow и ObservationGrain

Нельзя соединять метрики только потому, что они относятся к одному SKU.

Каждый snapshot должен сохранять фактическую временную семантику:

- `observed_at`, если это point-in-time наблюдение;
- `period_start` / `period_end`, если это агрегированный период;
- `imported_at`;
- source timezone / date semantics, если источник их задаёт;
- grain.

Канонически вводятся понятия:

### `ObservationGrain`

Например:

- instant;
- day;
- period;
- query-level;
- query×cluster-level.

Точный enum/typed model определяется в PR2.

### `AnalysisWindow`

Описывает период, в котором analytics разрешено сопоставлять наблюдения.

## 6.1. Правила совместимости

1. Нельзя row-by-row связывать дневную позицию с CR за 28 дней.
2. Нельзя считать одну дневную ставку причиной результата, агрегированного за иной период, без явного aggregation rule.
3. Для benchmark собственный товар и competitor values должны относиться к сопоставимым периодам или результат маркируется как period-mismatch/insufficient.
4. Для longitudinal модели «Разгон» все входные ряды должны быть приведены к совместимому временному шагу явной функцией aggregation.
5. Не выполнять скрытую интерполяцию отсутствующих дней.
6. Date-only значения источника не переводятся через timezone как timestamp. Исходная business date сохраняется как business date.

Если source timezone неизвестен и это может изменить временное сопоставление, confidence снижается или модель не строится.

---

# 7. SourceResolutionPolicy

После подключения API один и тот же логический показатель может существовать одновременно в XLSX, Ozon API и MPStats.

Нельзя:

- молча усреднять такие значения;
- выбирать «последнее импортированное» независимо от качества источника;
- удалять менее приоритетный факт.

Все source facts сохраняются с provenance.

Analytics использует отдельную **SourceResolutionPolicy**.

Минимальные факторы resolution:

- является ли источник первичным Ozon для данной метрики;
- гранулярность;
- совпадение периода;
- freshness;
- completeness;
- наличие identity conflict;
- source confidence/contract status.

Базовое правило:

> для собственной числовой аналитики Ozon source имеет приоритет над сторонней оценкой MPStats, если Ozon предоставляет нужную метрику с сопоставимой гранулярностью и периодом.

Нельзя использовать более приоритетный бренд источника как оправдание более грубой гранулярности. Например, агрегированная Ozon CR не становится query-level CR только потому, что Ozon — первичный источник.

Resolution должен быть воспроизводим и тестируем.

---

# 8. SourceCapability, coverage и backfill

SCOZ не должен исходить из предположения, что локальное приложение было запущено каждый день.

Каждый API adapter должен уметь сообщить capability metadata, если применимо:

- `supports_backfill`;
- доступный исторический горизонт;
- минимальный/максимальный размер окна запроса;
- granularity;
- timezone/date semantics;
- pagination/limit semantics;
- known missing-day semantics;
- последнюю успешную синхронизацию;
- фактически покрытый диапазон.

При sync система должна:

1. определить желаемый диапазон;
2. обнаружить известные пробелы;
3. сделать idempotent backfill там, где источник позволяет;
4. оставить явный `coverage gap`, где источник историю уже не отдаёт.

Data Readiness должен отличать:

- «история не загружена»;
- «источник не поддерживает backfill»;
- «частичный historical coverage»;
- «полное покрытие выбранного окна».

---

# 9. MPStats Position History — обязательный adapter contract

Официальная документация MPStats для Ozon `items/{id}/keywords` показывает:

- входной диапазон `d1` / `d2`;
- `avg_position`;
- массив `positions`;
- `null` внутри массива.

При этом сам пример массива не содержит даты внутри каждого элемента.

Следовательно, **до production-реализации Share of Top запрещено предполагать**, что индекс массива однозначно соответствует `d1 + N` или `d2 - N` без подтверждения контракта.

PR10 обязан включать contract verification, которое устанавливает:

- направление массива относительно `d1/d2`;
- наличие/отсутствие пропущенных календарных дней;
- фактическую семантику `null`;
- timezone/business-date semantics;
- поведение при неполном диапазоне.

До подтверждения `null` трактуется как **unknown source observation**, а не автоматически как:

- позиция 0;
- позиция 1000+;
- отсутствие товара в выдаче.

Для Share of Top denominator должен использовать только те observation days, семантика которых известна и подходит для расчёта.

Результат Share of Top всегда возвращает denominator/sample size.

---

# 10. Granularity режима «Разгон»

Более ранняя формулировка `SKU × query × cluster × time` была слишком жёсткой.

Каноническое правило:

> **Ramp-up работает на максимально детальной общей гранулярности, которая реально присутствует одновременно во всех необходимых входных данных.**

Базовый допустимый уровень:

> `SKU × query × time`

Cluster dimension используется только когда:

- позиция;
- conversion evidence;
- рекламное воздействие;
- и требуемые search factors

имеют совместимую cluster-level granularity.

Если хотя бы ключевой вход существует только query-level, нельзя искусственно размножать его по кластерам.

Каждый результат Ramp-up должен возвращать `analysis_grain`.

---

# 11. Availability / Out-of-stock guardrail

Продажи, трафик и часть conversion picture могут быть искажены отсутствием товара в продаже.

Если источник позволяет, хранить наблюдаемую доступность:

- stock;
- in-stock days / availability ratio;
- periods of zero stock;
- FBO/FBS availability context, если он нужен для корректной интерпретации.

Diagnostic Engine должен иметь состояние/confounder:

### `AVAILABILITY_CONFOUNDED`

Если существенная часть выбранного периода недоступна и нет корректного способа нормализовать показатель на доступные дни:

- сильный диагноз по продажам/трафику должен быть понижен по confidence или заблокирован;
- UI должен объяснить, что часть отставания может быть вызвана доступностью.

Порог существенности задаётся конфигурацией analytics, а не UI.

Нельзя автоматически считать stock=0 доказательством одного и того же бизнес-сценария во всех источниках; source semantics должны быть сохранены.

---

# 12. Benchmark sample confidence отдельно от performance status

Нужно различать два независимых вопроса:

1. где наш показатель относительно benchmark;
2. насколько надёжен сам benchmark.

Поэтому результат benchmark содержит отдельно:

- `performance_status`;
- `confidence`;
- `sample_size`;
- при необходимости `coverage`.

Низкий sample size не должен выглядеть как уверенный зелёный/красный вывод.

При выборке ниже конфигурируемого минимума допустимо показывать числовые значения медианы и конкурентов, но:

- `performance_status` становится `UNDETERMINED` или эквивалентным нейтральным состоянием;
- `confidence = INSUFFICIENT`;
- UI поясняет причину.

P25/P75 при статистически бессмысленной выборке не должны использоваться как уверенная граница статуса.

---

# 13. Технический Operation Feedback Contract

UI/UX уже требует, чтобы любое ожидание имело обратную связь. Для этого вводится единый технический contract, а не отдельные ad-hoc spinners.

Минимальная модель:

### `Operation`

- `operation_id`;
- `operation_type`;
- `status`;
- `stage`;
- `message`;
- `started_at`;
- `updated_at`;
- `completed_at`, если завершено;
- `progress_current`, если известно;
- `progress_total`, если известно;
- `progress_percent`, только если вычисляется честно;
- `retryable`;
- `error_code`, если есть;
- `result_ref`, если есть результат.

Статусы должны поддерживать как минимум:

- `IDLE`/не создана;
- `VALIDATING`;
- `RUNNING`;
- `PARTIAL_SUCCESS`;
- `SUCCESS`;
- `FAILED`.

`STALE` и `INSUFFICIENT_DATA` являются состояниями данных/аналитики, а не успешностью фоновой операции.

Для локального SCOZ базовая транспортная модель — **HTTP polling**, без обязательного WebSocket слоя.

Длительная операция должна возвращать `operation_id`; UI получает её состояние через единый application/API contract.

---

# 14. Local web security

Bind на `127.0.0.1` необходим, но недостаточен.

Минимальные требования:

1. backend слушает только loopback;
2. Host header проверяется по allowlist локальных hostnames/origin;
3. production CORS не является permissive;
4. state-changing API не должны быть доступны простым cross-site запросом без session proof;
5. launcher создаёт криптографически случайный per-launch session token;
6. frontend получает session token только через same-origin bootstrap flow и хранит его в памяти, не в `localStorage`;
7. mutating API требуют этот token/custom header и JSON contract;
8. `Origin`/`Host` validation применяется к чувствительным endpoints;
9. GET не должен иметь скрытых state-changing side effects.

Цель: сторонняя веб-страница не должна иметь возможность управлять локальным SCOZ только потому, что он открыт на loopback-порту.

Dev mode может иметь отдельные правила, но production security нельзя ослаблять ради удобства разработки.

---

# 15. Хранение секретов

API credentials не хранятся plaintext в конфигурационном JSON/TOML.

На Windows базовый механизм первой версии:

> **Windows DPAPI, CurrentUser scope**

Разрешено хранить project-local encrypted blob, но расшифровать его должен только тот Windows user, который сохранил credential.

Требования:

- frontend никогда не получает secret обратно;
- logs не содержат secret;
- support bundle не включает расшифрованные credentials;
- backup/export данных по умолчанию не экспортирует secrets;
- перенос приложения на другой Windows user/machine может потребовать повторного ввода credentials — это нормальное и объяснённое поведение.

---

# 16. Жизненный цикл пользовательских данных при обновлении

`data/` и пользовательская конфигурация являются **user-owned state**.

Release-managed assets (`app`, `web`, launcher/runtime components) и user-owned state не должны смешиваться в одной overwrite-модели.

Обязательные правила:

- release package не содержит рабочую пользовательскую SQLite;
- обновление приложения не удаляет `data/`;
- destructive-risk migration выполняется только после локального backup;
- migration либо завершается целиком, либо оставляет предыдущую валидную БД доступной для recovery;
- runtime/app update не заменяет raw imports, cache policy aside, logs policy aside;
- release manifest знает app/runtime version отдельно от DB schema version.

PR15 обязан проверить upgrade path минимум с предыдущей поддерживаемой schema/release.

Пользовательские данные остаются project-local в первой версии, как уже принято Architecture Design. Если позднее будет выбран `%LOCALAPPDATA%`, это отдельное архитектурное решение и миграция, а не скрытая реализация.

---

# 17. Допустимые способы автоматизации Ozon

После проверки официальной документации Ozon for Developers фиксируется более жёсткое правило.

Для автоматизации SCOZ использует только:

- официально доступные публичные Ozon API;
- пользовательский импорт XLSX/других файлов, которые пользователь легально получает в интерфейсе;
- иные явно разрешённые Ozon integration mechanisms.

Не использовать как product dependency:

- undocumented/internal Ozon endpoints;
- автоматизированный парсинг внутренних сервисов Ozon;
- Selenium/WebDriver или другой софт, имитирующий действия пользователя в личном кабинете;
- `xapi`/internal network calls, не разрешённые как публичный API.

Это решение основано на официальной рекомендации Ozon for Developers «Seller API: как избежать блокировок» (07.08.2024), где для автоматизации разрешаются публичные API Ozon и отдельно запрещается неразрешённый автоматизированный парсинг внутренних сервисов и имитация действий пользователя.

Следовательно:

> раздел PR Development Plan про optional post-v1 internal Search Visibility API **отменяется и не является действующим планом**.

Вернуться к автоматизации «Что влияет на место» можно только если Ozon выпустит/разрешит публичный контракт, который законно покрывает нужные данные.

До этого XLSX остаётся каноническим automation-safe способом получения этих данных.

---

# 18. Currency, percent и unit semantics

Ingestion обязан сохранять не только число, но и его нормализованную семантику.

Требования:

- денежные значения имеют currency;
- проценты различают ratio/percent/percentage-point semantics;
- ставки и DRR не смешиваются только из-за одинакового `%` формата;
- delivery duration имеет единицу;
- raw source value сохраняется в provenance/raw artifact;
- conversion/normalization version известна.

Не выполнять неявный FX conversion.

Если source value неоднозначен, parser должен вернуть validation error/warning, а не подобрать удобную единицу.

---

# 19. Поправки к ранее действующим документам

## 19.1. Product Spec

Следующие старые формулировки считаются заменёнными:

- `OwnProduct` и `CompetitorProduct` как отдельные доменные типы → единый `Product` + ownership + `BenchmarkSet`;
- `BenchmarkSnapshot` как обязательный первичный источник истины → benchmark вычисляется из snapshots + `BenchmarkSetRevision`; materialization только как воспроизводимый cache;
- MPStats только для фото → MPStats также используется для истории позиций по запросам в Query Opportunity;
- обязательная гранулярность Ramp-up `SKU × query × cluster × time` → максимально детальная **общая** гранулярность доступных входов;
- внутренний API Ozon в списке допустимых источников → удалён как допустимая product dependency до появления официально разрешённого публичного API.

## 19.2. Architecture Design

Архитектурно добавляются/уточняются:

- `ProductExternalIdentity`;
- `ProductQuerySnapshot`;
- `BenchmarkSetRevision`;
- observation revisions / supersession;
- `ObservationGrain` / `AnalysisWindow`;
- `SourceResolutionPolicy`;
- `SourceCapability` / coverage / backfill;
- `Operation` contract;
- local web security;
- DPAPI secrets;
- availability guardrails;
- source-safe Ozon automation only.

## 19.3. UI/UX Design

UI/UX Design остаётся действующим.

Дополнение:

- при недостаточной benchmark-выборке цветовой performance status не должен выглядеть уверенным;
- Data Readiness показывает coverage/backfill gaps;
- operation states получают единый backend contract;
- identity/source conflicts должны иметь пользовательски понятное состояние вместо молчаливого выбора.

## 19.4. PR Development Plan

Структура PR1–PR15 сохраняется.

Меняется scope отдельных PR:

### PR1

Добавить:

- Host/Origin security baseline;
- per-launch session token;
- production CORS policy;
- базовый `Operation` API/view contract;
- разделение release-managed и user-owned paths.

### PR2

Добавить:

- `ProductExternalIdentity`;
- query/cluster canonical identity;
- `BenchmarkSetRevision`;
- logical observation keys;
- immutable revisions/supersession;
- `ObservationGrain`/`AnalysisWindow` types;
- `SourceResolutionPolicy` contracts;
- `SourceCapability` contracts;
- schema tests на revisions/identity conflicts.

### PR3

Добавить:

- availability/stock fields, если они присутствуют;
- revision behavior для исправленного отчёта за тот же период;
- money/percent/unit normalization contract.

### PR4–PR5

Добавить:

- explicit period/grain semantics;
- revision behavior;
- query/cluster identity conflict tests.

### PR6

Добавить:

- DPAPI CurrentUser credential storage;
- `BenchmarkSetRevision` вместо in-place изменения состава;
- source identity mapping MPStats↔Product.

### PR7

Добавить:

- benchmark `confidence` отдельно от `performance_status`;
- запрет уверенных P25/P75 statuses при недостаточной выборке;
- period compatibility checks.

### PR8

Добавить:

- `AVAILABILITY_CONFOUNDED`;
- downgrade/block strong diagnosis при существенном OOS;
- UI identity/source/coverage warnings, если они влияют на результат.

### PR10

Добавить обязательный MPStats contract verification перед Share of Top:

- array date order;
- null semantics;
- missing days;
- denominator rules;
- timezone/business-date semantics.

Cluster не является обязательной dimension MPStats position history.

### PR11

Разрешены только публичные официальные Ozon API.

Добавить:

- `SourceCapability`;
- backfill/coverage;
- idempotent gap filling;
- source resolution между XLSX/API;
- удалить internal Ozon endpoint из возможного scope.

### PR12

Добавить:

- historical coverage/backfill semantics Performance API;
- period/grain compatibility для advertising facts.

### PR13–PR14

Добавить:

- `analysis_grain` в результат;
- построение только на максимально детальной общей гранулярности;
- явные time-window compatibility gates;
- никаких cluster-level сценариев при отсутствии cluster-level evidence.

### PR15

Добавить:

- upgrade preserving `data/`;
- DB backup/recovery before risky migrations;
- DPAPI behavior audit;
- local web security audit;
- operation-state regression;
- source coverage/backfill regression;
- upgrade test с предыдущего release/schema.

Раздел `Optional post-v1 source adapter: Ozon internal Search Visibility API` считать **удалённым из действующего плана**.

---

# 20. Preflight review gates для каждого PR-specific ТЗ

Перед approval любого PR-specific ТЗ проверить:

1. Какие external identities участвуют и как они связываются с `Product`?
2. Каков logical observation key?
3. Возможна ли ревизия данных за тот же период и как она хранится?
4. Каковы grain/period/time semantics?
5. Какие источники могут дать одну и ту же метрику и кто выбирает активный факт?
6. Есть ли backfill и как отображается coverage gap?
7. Может ли availability исказить вывод?
8. Достаточен ли sample size для сильного статуса?
9. Какая операция может занять время и как она сообщает feedback?
10. Есть ли state-changing local API и защищён ли он session/origin contract?
11. Где хранятся credentials и пользовательские данные?
12. Не используется ли запрещённая/неофициальная автоматизация Ozon?
13. Не смешиваются ли query-level, cluster-level и aggregate values?
14. Может ли результат быть полностью воспроизведён из source + revision + benchmark revision + rule version?

Если на любой из этих вопросов PR-specific ТЗ не даёт однозначного ответа, ТЗ не готово к реализации.

---

# 21. Итоговый архитектурный критерий

После этих поправок любой аналитический вывод SCOZ должен быть трассируем как минимум так:

```text
External identity
  → Source artifact / API response
  → Logical observation
  → Immutable revision
  → Source resolution
  → Analysis window/grain
  → BenchmarkSetRevision (если нужен benchmark)
  → Analytics rule/model version
  → Confidence / confounders
  → View result
```

А любое длительное пользовательское действие:

```text
User action
  → Operation ID
  → visible stage/status
  → success / partial / failure
  → persistent resulting state or actionable error
```

Это является обязательным pre-flight фундаментом перед написанием и реализацией PR1–PR15.
