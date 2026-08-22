# SCOZ — Preflight Decisions: Internal Portable Profile

**Дата:** 2026-08-13  
**Статус:** канонические уточнения перед PR-specific ТЗ  
**Репозиторий:** `vgvolmax/SCOZ`

## 1. Контекст, который определяет сложность решения

SCOZ — внутреннее локальное приложение для небольшой группы доверенных пользователей компании.

Пользовательский сценарий:

> скачать ZIP → распаковать → запустить `start.bat` → при первом запуске приложение само готовит локальный runtime → при последующих запусках используется тот же `start.bat` из той же папки.

SCOZ не является публичным SaaS, сетевым сервисом или multi-user платформой.

В первой версии не нужны:

- аккаунты и роли пользователей;
- центральный сервер SCOZ;
- доступ к SCOZ с других компьютеров;
- desktop installer;
- системные Python/Node;
- Docker/PostgreSQL;
- auto-updater;
- отдельная auth/session-платформа;
- persistent background job framework;
- telemetry platform.

Главный YAGNI-принцип:

> инфраструктурная сложность добавляется только когда она нужна реальному внутреннему сценарию; строгость данных и аналитики не упрощается там, где упрощение может привести к неверному выводу.

---

## 2. Portable contract

Канонический пользовательский поток:

```text
start.bat
  → проверить project-local runtime
  → при первом запуске скачать/подготовить Windows embeddable Python
  → включить site-packages в embedded _pth и bootstrap pip через официальный get-pip.py
  → установить exact direct dependencies командой python -m pip install -r requirements.txt
  → выполнить preflight и DB migrations
  → запустить FastAPI на 127.0.0.1
  → дождаться health check
  → открыть browser UI
```

Повторный запуск:

```text
start.bat
  → проверить Python, direct package versions и imports
  → при mismatch выполнить pip install -r requirements.txt
  → при failed repair удалить только runtime/ и подготовить его заново
  → preflight/migrations
  → если SCOZ уже запущен — открыть существующий UI
  → иначе запустить backend и открыть UI после health check
```

Обязательные свойства:

- пользователь не устанавливает Python/Node вручную;
- права администратора не требуются;
- runtime находится внутри папки приложения;
- portable startup/runtime lifecycle следует proven `WB_OZON_Yandex` model;
- глобальный PATH не изменяется;
- frontend уже собран и не требует npm на пользовательском ПК;
- Python и `get-pip.py` скачиваются из official HTTPS sources через временный `.part` и проходят basic size/sanity validation; Python ZIP должен открываться и содержать entries;
- `runtime/` disposable: если setup/rebuild прерван, следующий запуск готовит runtime заново;
- `data/` является отдельным user state и переживает repair/rebuild runtime;
- повторный запуск не переустанавливает валидный runtime;
- backend открывает браузер только после успешного `/api/health`;
- конфликт занятого порта объясняется пользователю;
- запуск из путей с пробелами и кириллицей должен учитываться в Windows verification.

Не требуется строить самостоятельную систему обновления приложения. Обновление SCOZ в первой версии — отдельная пользовательская операция с новым ZIP/release.

---

## 3. Startup feedback без отдельного job framework

Референсная модель запуска из внутреннего portable-приложения считается подходящей для SCOZ.

Launcher хранит простой локальный статус запуска, например:

`data/startup_status.json`

Минимальные стадии:

- `preflight`;
- `runtime_setup`;
- `database_backup`, если нужен;
- `migration`;
- `server_start`;
- `ready`;
- `failed`.

BAT/launcher показывает человеку человеческие сообщения по стадиям и путь к логу при ошибке.

Для пользовательских операций внутри UI также не нужен общий persistent `Operation` domain/table.

Базовое правило:

- короткая операция выполняется обычным HTTP request и имеет локальный loading state;
- длительная операция может использовать лёгкое in-memory состояние + HTTP polling;
- после перезапуска приложения незавершённую UI-операцию восстанавливать не требуется;
- уже committed данные при прерывании не должны повреждаться.

Минимальные состояния длительной операции:

`VALIDATING → RUNNING → SUCCESS / PARTIAL_SUCCESS / FAILED`.

При необходимости `stage` уточняет реальный этап: `READING`, `NORMALIZING`, `SAVING`, `SYNCING` и т.п.

Процент отображается только когда его можно вычислить честно.

---

## 4. Encrypted portable keystore — выбранное решение для API-ключей

Для SCOZ используется подход из предоставленного внутреннего portable-приложения.

Ключи не сохраняются в SQLite и не записываются в открытый конфигурационный файл.

Пользователь может:

1. ввести credentials в `Настройки → Источники`;
2. проверить подключение;
3. сохранить их в зашифрованный portable-файл;
4. при следующем запуске выбрать этот файл и ввести пароль;
5. очистить ключи из памяти кнопкой `Заблокировать ключи`.

### Формат keystore

Рекомендуемый контракт v1:

- filename: `scoz_credentials.enc.json`;
- cipher: `AES-256-GCM`;
- KDF: `PBKDF2-HMAC-SHA256`;
- iterations: `600000`;
- случайный salt: 16 bytes;
- случайный IV: 12 bytes;
- versioned file format;
- пароль в файл не записывается.

Пример смысловой структуры:

```json
{
  "format": "scoz-credentials-keystore",
  "version": 1,
  "createdAt": "...",
  "crypto": {
    "cipher": "AES-256-GCM",
    "kdf": "PBKDF2-HMAC-SHA256",
    "iterations": 600000,
    "salt": "...",
    "iv": "...",
    "ciphertext": "..."
  }
}
```

Шифрование/расшифрование выполняется браузером через Web Crypto API.

После ввода или расшифрования credentials живут только в памяти текущей вкладки и передаются backend только по same-origin loopback request тогда, когда backend должен обратиться к Ozon/MPStats.

Backend:

- не сохраняет plaintext credentials;
- не пишет их в лог;
- не возвращает их в response;
- использует их только для конкретной операции источника.

Reload/закрытие вкладки очищает credentials естественным образом; пользователь при необходимости снова открывает keystore.

Keystore переносим между доверенными рабочими ПК вместе с паролем, который хранится отдельно от файла.

`.gitignore` обязан исключать как минимум:

```text
*.enc.json
scoz_credentials*.json
credentials*.json
```

### Что специально НЕ строим

В первой версии не нужны:

- Windows DPAPI;
- Credential Manager integration;
- machine/user binding keystore;
- собственная password vault система;
- backend persistent secret store.

---

## 5. Local web security — минимально достаточная

Поскольку SCOZ работает только на доверенном ПК и не предоставляет LAN-доступ, применяется простой контур:

- backend bind только на `127.0.0.1`;
- frontend и API работают с одного origin;
- production CORS не открывается на произвольные origins;
- GET endpoints не изменяют состояние;
- credentials не попадают в URL/query string;
- чувствительные values маскируются в логах.

Не вводятся без отдельной необходимости:

- login/auth layer;
- per-launch session tokens;
- CSRF subsystem;
- Host/Origin security framework;
- certificates/HTTPS для loopback.

Если в будущем появится LAN-доступ или недоверенные пользователи, security profile пересматривается отдельным design change.

---

## 6. User-owned state

Пользовательские данные находятся project-local:

```text
SCOZ/
├─ start.bat
├─ app/ или backend/
├─ web/ или frontend build/
├─ runtime/
├─ data/
│  ├─ scoz.db
│  ├─ imports/
│  ├─ cache/
│  └─ logs/
└─ ...
```

`data/` является пользовательским состоянием и не коммитится в Git.

Release/репозиторий не содержит рабочую пользовательскую SQLite.

DB migration выполняется автоматически при старте. Перед миграцией с реальным риском повреждения/необратимости создаётся локальная backup-копия БД.

Сложная backup/restore platform не нужна.

---

# 7. Каноническая идентификация Product

Один товар может приходить из Ozon XLSX, Ozon API и MPStats с разными IDs.

Используется единый `Product` и минимальная связь `ProductExternalIdentity`:

- `product_id` — внутренний ID SCOZ;
- `source`;
- `identity_type`;
- `identity_value`;
- `source_account_scope`, только если он реально нужен для уникальности.

На старте не нужны `valid_from/valid_to` и полноценная temporal identity model.

Правила:

- нельзя merge товаров только по названию, бренду или фото;
- `offer_id` учитывает seller/account scope, если требуется;
- неоднозначный mapping не объединяется молча;
- расширенная история identity добавляется только если встретится реальный кейс смены mapping.

---

# 8. SearchQuery и Cluster identity

Post-PR5 canonical `SearchQuery` identity следует утверждённым PR4/PR5 source contracts:

1. взять source query text;
2. убрать только leading/trailing U+0020 ordinary SPACE и U+00A0 NBSP;
3. потребовать non-empty result;
4. использовать resulting exact text как identity.

Не выполнять lowercase/casefold, Unicode normalization, `ё→е`, stemming, lemmatization, punctuation removal, spelling или keyboard-layout correction, internal-space collapse, synonym replacement, fuzzy/semantic matching. PR4 и PR5 reuse одну `SearchQuery` row только при exact canonical text equality. Source query ID, если он существует, сохраняется как external identity, но не ослабляет это правило.

Для текущего Ozon Search Visibility contract `Cluster` использует source cluster text с тем же единственным U+0020/U+00A0 edge cleanup; resulting exact text идентифицирует `Cluster`. Alias/fuzzy normalization, Cluster alias infrastructure и speculative cross-source cluster resolver не вводятся.

---

# 9. Immutable snapshots и исправления источника

Историю нужно сохранять, но без отдельной сложной revision subsystem.

Для каждого snapshot-type определяется logical observation key.

Правило:

```text
тот же logical key + тот же normalized payload
→ duplicate, новый snapshot не создаётся

тот же logical key + изменённый normalized payload
→ новая revision, предыдущая помечается superseded

новый period/date/dimensions
→ новое observation
```

Достаточные поля revision:

- revision number или порядок;
- `supersedes_snapshot_id`, если есть;
- `imported_at`;
- normalized payload hash;
- provenance.

Analytics использует последнюю актуальную revision для одного logical observation, но старые revisions остаются для проверки.

---

# 10. BenchmarkSet revisions

Состав прямых конкурентов влияет на результат, поэтому его история должна быть воспроизводима.

Используются:

- `BenchmarkSet` — стабильная группа собственного SKU;
- `BenchmarkSetRevision` — сохранённая версия состава.

Изменение списка конкурентов создаёт новую revision, а не переписывает старую.

Не нужна сложная effective-date model. Достаточно `revision_id`, `created_at` и состава участников.

Исторический аналитический результат при необходимости может сослаться на конкретную revision.

`BenchmarkSetRevision` — user-curated analytical context состава, а benchmark values — derived analytics. Member count не является metric sample size: sample формируется отдельно для каждой metric по доступным совместимым observations. `BenchmarkSnapshot` не является source of truth и не должен дублировать source histories.

---

# 11. Period/grain compatibility

Эта часть остаётся строгой, потому что напрямую влияет на достоверность выводов.

Каждый snapshot хранит доступные временные semantics:

- `observed_at` для point observation;
- `period_start` / `period_end` для aggregate period;
- `imported_at`;
- фактическую granularity/dimensions.

Не требуется строить отдельный тяжёлый framework `AnalysisWindow`/`ObservationGrain`.

Достаточно typed metadata + одной общей функции/набора правил compatibility в analytics/application layer.

Запрещено без явного правила:

- связывать дневную позицию row-by-row с CR за 28 дней;
- искусственно размножать query-level данные по кластерам;
- сравнивать own и benchmark за несовместимые периоды как будто они сопоставимы;
- интерполировать отсутствующие дни незаметно для пользователя.

Если данные несовместимы, результат получает `INSUFFICIENT_DATA`, `PERIOD_MISMATCH` или эквивалентное явное состояние.

Несовместимый period/grain блокирует comparable calculation; пониженный confidence не является общим способом обойти этот gate. Analytics не repair/clamp/rewrite source facts: correction возможна только новой source revision с provenance. Если analytical result когда-либо materialized или persistently saved, он должен сохранять воспроизводимый context, включая source observation/revisions, period/grain, benchmark revision и calculation/model version; exact result storage заранее не проектируется.

---

# 12. Source resolution — функция, не framework

Один показатель может прийти из нескольких источников.

Не нужен универсальный registry/policy engine.

Для каждой domain metric используется детерминированный resolver с простыми правилами:

1. сохранить все факты с provenance;
2. не усреднять конфликтующие sources;
3. первичные данные Ozon имеют приоритет, если дают нужную metric на совместимых period/grain;
4. более точная granularity важнее бренда источника;
5. MPStats используется только в утверждённых ролях: фото и история поисковых позиций.

Resolver покрывается unit tests.

---

# 13. Backfill/coverage — только там, где он реально существует

В PR2 не нужен общий `SourceCapability` framework.

Когда появляется конкретный API-adapter, его ТЗ фиксирует:

- какой historical range он умеет получить;
- умеет ли backfill;
- pagination/limits;
- какие gaps могут остаться.

Sync по возможности добирает пропущенный диапазон idempotently.

UI показывает реальный coverage только там, где он влияет на анализ.

---

# 14. MPStats position history

MPStats используется для истории позиций own SKU и выбранных competitors по запросам.

До реализации Share of Top PR10 обязан проверить реальный contract endpoint-а:

- порядок массива относительно `d1/d2`;
- пропущенные календарные дни;
- семантику `null`;
- business-date/timezone semantics;
- неполные диапазоны.

До проверки `null` означает unknown observation, а не позицию `0`, `1000+` или гарантированное отсутствие товара.

Share of Top всегда возвращает denominator/sample size.

---

# 15. Ramp-up granularity

Режим «Разгон» работает на **максимально детальной общей гранулярности**, которая реально присутствует одновременно у нужных входных данных.

Базовый практический уровень:

> `SKU × query × time`

Cluster добавляется только если совместимые cluster-level данные реально есть для необходимых position/conversion/advertising inputs.

Нельзя искусственно создавать cluster-level модель из query-level наблюдений.

Результат Ramp-up сообщает `analysis_grain` или человеческое эквивалентное пояснение в детализации.

---

# 16. Availability и confidence guardrails

OOS/ограниченная доступность может искажать продажи и трафик.

Если source даёт usable stock/availability data, Diagnostic Engine учитывает это как confounder.

При существенном OOS сильный диагноз по продажам/трафику понижается по confidence или блокируется; UI объясняет причину.

Benchmark отдельно возвращает:

- performance status;
- sample size;
- confidence.

Маленькая benchmark-группа не должна выглядеть как статистически уверенный красный/зелёный вывод.

Пороговые значения находятся в analytics config, не в UI.

---

# 17. Currency/percent/unit semantics

Ingestion нормализует единицы явно.

Минимально различать:

- money + currency;
- ratio/percent;
- percentage points;
- delivery duration unit;
- bid/CPC/CPO semantics.

Raw source value остаётся доступным через raw artifact/provenance.

Не делать неявный FX conversion.

---

# 18. Допустимая автоматизация Ozon

SCOZ использует только:

- официально разрешённые публичные Ozon API;
- пользовательские XLSX/другие экспортируемые файлы;
- иные официально разрешённые integration mechanisms.

Не включать в product dependency:

- undocumented/internal Ozon endpoints;
- `xapi`/internal cabinet calls;
- Selenium/WebDriver и имитацию пользователя;
- автоматизированный парсинг внутренних сервисов Ozon.

«Что влияет на место» остаётся XLSX-source, пока Ozon не предоставит подходящий разрешённый public API.

---

# 19. Что остаётся строгим, а что намеренно простое

Строго сохраняем:

- source adapters → normalized domain model;
- immutable history/revisions;
- benchmark revisions;
- period/grain compatibility;
- provenance;
- sample confidence;
- недостаточность данных вместо псевдоточного вывода;
- корректную granularity Ramp-up;
- честную семантику MPStats positions.

Намеренно не строим заранее:

- auth/session platform;
- DPAPI integration;
- persistent jobs;
- event bus;
- scheduler platform;
- capability registry;
- auto-updater;
- telemetry service;
- central cloud backend;
- LAN mode.

---

# 20. Поправки к PR-плану

Структура PR1–PR15 сохраняется.

Ключевые scope corrections:

**PR1** — portable bootstrap, local runtime, startup status/logging, health check, same-origin loopback app, frontend shell и Windows smoke. Без auth/session/security framework.

**PR2** — domain/storage/history, минимальный `ProductExternalIdentity`, logical observation/revision conventions и period/grain metadata conventions. Без `BenchmarkSet*` и без source-resolution implementation/framework до первого реального multi-source use case. Без capability/job frameworks.

**PR3–PR5** — imports + revisions + period/unit semantics.

**PR6** — MPStats photos + benchmark selection + encrypted portable keystore через Web Crypto. Без DPAPI.

**PR7** — benchmark math + advertising intensity + sample confidence + period compatibility.

**PR8** — diagnostics + availability confounder + data readiness.

**PR10** — обязательная contract verification MPStats position history до Share of Top.

**PR11–PR12** — конкретные public API adapters; backfill/coverage реализуются внутри каждого adapter-а, если источник это поддерживает.

**PR13–PR14** — Ramp-up только на общей фактически доступной granularity.

**PR15** — release regression, migration backup/recovery, clean-Windows portable test и end-to-end CJM. Не превращать PR15 в enterprise hardening project.

Internal Ozon API adapter не входит ни в обязательный, ни в optional план.

---

# 21. Preflight checklist для PR-specific ТЗ

Перед реализацией PR достаточно ответить на вопросы, которые реально применимы к его scope:

1. Какие domain entities/identities меняются?
2. Какой logical key у нового snapshot, если snapshot появляется?
3. Что происходит при повторе/исправлении данных за тот же period?
4. Совместимы ли periods/granularity сравниваемых metric?
5. Есть ли несколько sources одной metric и какой простой resolver используется?
6. Может ли OOS/маленькая выборка исказить вывод?
7. Как пользователь видит progress/success/error операции?
8. Где остаются пользовательские данные/credentials?
9. Используется ли только разрешённый source/API?
10. Как это проверяется tests/manual QA?

Не требовать искусственно отвечать на неприменимые enterprise-вопросы.

---

# 22. Итоговый критерий

Архитектура SCOZ должна оставаться понятной как:

```text
start.bat
  → portable Python
  → FastAPI + committed HTML/CSS/JavaScript
  → SQLite
  → Source adapters
  → normalized snapshots/history
  → analytics
  → понятный UI
```

Для аналитического вывода должно быть возможно понять:

```text
откуда пришли данные
→ за какой период
→ на какой granularity
→ какая benchmark revision использована
→ какое правило/модель применены
→ насколько вывод надёжен
```

Этого достаточно для внутреннего SCOZ. Дополнительная инфраструктура добавляется только после появления реального сценария, который без неё невозможно решить.
