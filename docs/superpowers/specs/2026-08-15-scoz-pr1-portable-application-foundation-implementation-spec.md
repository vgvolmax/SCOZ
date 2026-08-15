# SCOZ — PR1 Implementation Spec: Portable Application Foundation

**Дата:** 2026-08-15  
**Статус:** approved  
**Репозиторий:** `vgvolmax/SCOZ`  
**PR:** `PR1 — Portable Application Foundation`

## 1. Цель PR

Создать первый исполняемый каркас SCOZ.

Канонический пользовательский flow после PR1:

```text
скачать ZIP репозитория
→ полностью распаковать
→ запустить start.bat
→ при первом запуске автоматически подготовить project-local Python runtime
→ запустить SCOZ на loopback
→ дождаться успешного health check
→ автоматически открыть browser UI
```

На пользовательском ПК не требуются установленный Python, Node/npm, Docker, PostgreSQL, права администратора, изменение PATH, ручная установка зависимостей или frontend build.

PR1 создаёт только application foundation. SQLite domain model, imports, credentials, benchmark и analytics относятся к последующим PR.

## 2. Frozen contracts

PR1 обязан следовать frozen Product Spec, Architecture, UI/UX, Visual Design System, Preflight Decisions и canonical PR Development Plan.

Portable-модель повторяет проверенный принцип `WB_OZON_Yandex`: thin Windows entry point → project-local runtime bootstrap/repair → launcher preflight → FastAPI → health → browser.

Отличие SCOZ: скачиваемые bootstrap/runtime artifacts проверяются по pinned SHA-256 до использования.

## 3. Target platform

Поддерживаемая платформа PR1:

- Windows 10 x64;
- Windows 11 x64.

ARM64 и 32-bit Windows не входят в PR1.

Поддерживаются writable-пути с пробелами и кириллицей, например:

```text
C:\SCOZ
C:\My Apps\SCOZ
C:\Работа\SCOZ Аналитика
```

Запуск непосредственно из ZIP не поддерживается.

## 4. Python runtime

### 4.1. Pinned Python

Использовать **Python 3.13.14 Windows embeddable package x64**.

Official artifact:

```text
https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip
```

Expected SHA-256:

```text
90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907
```

Runtime существует только внутри:

```text
runtime/
```

Он не регистрируется в Windows и не добавляется в PATH.

### 4.2. Runtime manifest

Создать `runtime_manifest.json` с versioned contract. Минимальные поля:

```json
{
  "schemaVersion": 1,
  "pythonVersion": "3.13.14",
  "architecture": "amd64",
  "python": {
    "url": "https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip",
    "sha256": "90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"
  },
  "pipBootstrap": {
    "url": "https://bootstrap.pypa.io/get-pip.py",
    "sha256": "<verified exact SHA-256 committed by PR1>"
  }
}
```

Перед merge PR1 placeholder в `pipBootstrap.sha256` запрещён. PR1 обязан один раз скачать официальный artifact, вычислить SHA-256, записать его в manifest и использовать при каждом first-run/rebuild.

### 4.3. Dependency lock

Создать:

```text
requirements.in
requirements.lock.txt
```

Direct runtime pins:

```text
fastapi==0.139.2
uvicorn==0.51.0
```

`requirements.lock.txt` содержит полностью resolved exact pins транзитивных runtime dependencies и является единственным файлом, из которого устанавливается user runtime.

Runtime install должен использовать wheels, без локальной компиляции на пользовательском ПК.

Не добавлять в runtime заранее pandas, openpyxl, SQLAlchemy, Alembic, cryptography, HTTP clients для будущих adapters или analytics libraries.

### 4.4. Atomic runtime publication

Если валидного `runtime/python.exe` нет:

1. скачать Python archive во временный `.part`;
2. проверить SHA-256;
3. распаковать во staging directory;
4. настроить embedded `_pth` для `Lib/site-packages` и `import site`;
5. скачать и проверить pinned `get-pip.py`;
6. установить pip локально;
7. установить `requirements.lock.txt`;
8. проверить Python/version/imports/dependency versions;
9. записать runtime marker;
10. только после полного успеха атомарно опубликовать staging как `runtime/`.

Полуготовый runtime не становится рабочим runtime.

При rebuild существующий рабочий runtime сохраняется до успешной валидации нового staging runtime.

### 4.5. Runtime marker

После успешной подготовки создать:

```text
runtime/.scoz_runtime.json
```

Минимально хранить:

- schema version;
- Python version;
- architecture;
- hash `runtime_manifest.json`;
- hash `requirements.lock.txt`;
- createdAt.

### 4.6. Reuse / repair / rebuild

При повторном запуске runtime переиспользуется, если:

- `python.exe` существует;
- Python version совпадает;
- marker соответствует manifest/requirements lock;
- обязательные imports проходят;
- pinned package versions совпадают.

Если Python цел, но зависимости расходятся — выполнить dependency repair.

Если repair не удался или Python/runtime повреждён — выполнить rebuild через staging.

`data/` при repair/rebuild не удаляется.

## 5. Launcher boundaries

Создать:

```text
start.bat
scripts/bootstrap.ps1
launcher.py
```

### `start.bat`

Только:

- `cd /d "%~dp0"`;
- UTF-8 console;
- вызов `scripts/bootstrap.ps1`;
- propagation exit code;
- при ошибке понятное сообщение и путь к логу.

Большой bootstrap-код в BAT не помещать.

### `scripts/bootstrap.ps1`

Отвечает только за runtime lifecycle:

- manifest validation;
- download/retry;
- SHA-256 verification;
- staging;
- pip bootstrap;
- dependency install;
- runtime validation;
- repair/rebuild;
- запуск `runtime\python.exe launcher.py --start`.

### `launcher.py`

Отвечает за application lifecycle:

- preflight;
- startup status/log;
- already-running detection;
- occupied-port detection;
- server process launch;
- health polling;
- browser open после health.

Runtime download/install в `launcher.py` не переносить.

## 6. Local server

Host:

```text
127.0.0.1
```

Port PR1:

```text
17842
```

Canonical URL:

```text
http://127.0.0.1:17842
```

Health URL:

```text
http://127.0.0.1:17842/api/health
```

Не использовать `0.0.0.0`, LAN bind или silent dynamic port switching.

Порт `17842` выбран отдельно от `WB_OZON_Yandex`, который использует `17841`.

## 7. Already-running / port conflict

Перед стартом нового server process launcher делает запрос к `/api/health`.

Если получен валидный SCOZ health payload — второй server process не создаётся, существующий UI открывается, launcher завершается успешно.

Если `17842` занят, но SCOZ health не подтверждён:

- чужой процесс не завершать;
- другой порт молча не выбирать;
- SCOZ не запускать;
- показать понятную ошибку;
- если PID безопасно определяется, записать его в diagnostic detail/log.

## 8. Backend foundation

Создать:

```text
backend/
├─ __init__.py
├─ config.py
└─ main.py
```

### `backend/config.py`

Только foundation constants/helpers:

- app name;
- version from `VERSION.txt`;
- host;
- port;
- project root;
- frontend dist path.

Не создавать settings framework для будущих sources.

### `GET /api/health`

Response `200`:

```json
{
  "status": "ok",
  "app": "SCOZ",
  "version": "0.1.0"
}
```

Endpoint ничего не мутирует, не обращается к внешним APIs и не зависит от SQLite.

### Static frontend

PR1 не вводит client-side router.

FastAPI должен:

- отдавать `/` из committed `frontend/dist/index.html`;
- отдавать `/assets/*` из `frontend/dist/assets/`;
- возвращать обычный `404` для неизвестных API и неизвестных frontend paths.

SPA fallback для произвольных URL в PR1 не создавать.

## 9. SQLite / persistence

В PR1 не создавать:

- `scoz.db`;
- migrations framework;
- repositories;
- Product/ProductExternalIdentity;
- ImportBatch/SourceArtifact;
- snapshot tables;
- future feature entities.

SQLite foundation начинается в PR2.

Launcher architecture должна позволять позже добавить реальный migration step без переделки portable flow.

## 10. Frontend foundation

Frontend: React + TypeScript, production build committed в repo.

Базовые exact direct versions для PR1:

```text
react==19.2.8
react-dom==19.2.8
vite==8.1.5
@vitejs/plugin-react==6.0.4
typescript==7.0.2
@types/react==19.2.18
@types/react-dom==19.2.4
```

`package-lock.json` коммитится.

Canonical structure:

```text
frontend/
├─ package.json
├─ package-lock.json
├─ tsconfig.json
├─ vite.config.ts
├─ src/
│  ├─ main.tsx
│  ├─ App.tsx
│  └─ styles.css
└─ dist/
   ├─ index.html
   └─ assets/...
```

Node/npm используются только development/CI. `start.bat` не вызывает npm.

## 11. PR1 UI shell

Глобальная IA только:

- **Товары**;
- **Данные**;
- **Настройки**.

Default section: **Товары**.

Product Workspace tabs `Диагностика / Поиск / Разгон / Конкуренты` в PR1 не показывать: Product ещё не существует.

Не создавать фиктивные KPI, charts, benchmark cards, scores, demo analytics, competitor data, imports или source settings.

Foundation empty states не должны обещать несуществующие действия.

## 12. Visual contract

Shell обязан использовать frozen Visual Design System:

- desktop-first;
- sidebar около 224 px;
- approved design tokens/CSS custom properties;
- Segoe UI/system stack;
- light app background + white surfaces;
- thin borders;
- restrained shadows;
- primary-soft active navigation;
- visible focus;
- color не является единственным носителем состояния;
- usable от ~1280 CSS px;
- без page-level horizontal scroll на основном shell.

Не использовать Bootstrap/admin-template look, gradients, glassmorphism, тяжёлые shadows, hero headings, dashboard wall или emoji-icons.

## 13. Startup feedback

Runtime-generated files:

```text
data/startup_status.json
data/launcher.log
data/server_console.log
```

Минимальный status payload:

```json
{
  "stage": "server_start",
  "message": "Запускаем SCOZ",
  "startedAt": "...",
  "updatedAt": "..."
}
```

Allowed stages:

```text
preflight
runtime_setup
database_backup
migration
server_start
ready
failed
```

`database_backup` и `migration` зарезервированы общим startup contract, но PR1 не симулирует их выполнение.

Status write должен быть atomic temp-file → replace.

Пользовательские сообщения — человеческие. Raw traceback по умолчанию только в technical log.

## 14. Browser contract

Browser открывается только после успешного SCOZ health response.

Developer/test-only environment switch:

```text
SCOZ_NO_BROWSER=1
```

Он не является пользовательской настройкой.

## 15. Same-origin security

Production PR1:

- backend bind только `127.0.0.1`;
- frontend/API same-origin;
- permissive CORS не включать;
- login/auth/session token/CSRF/TLS/LAN security не добавлять;
- GET endpoints не мутируют состояние;
- logs не dump-ят environment и используют redaction-safe pattern для credential-like values на будущее.

## 16. Version

Создать единый источник версии:

```text
VERSION.txt
```

Initial version:

```text
0.1.0
```

Backend health, launcher diagnostics и UI при необходимости читают один источник, а не дублируют вручную version constants.

## 17. Gitignore / user-owned state

Не коммитить:

```text
runtime/
runtime.__staging*/
runtime.__old*/
data/
.venv/
frontend/node_modules/
__pycache__/
*.pyc
*.enc.json
scoz_credentials*.json
credentials*.json
```

`frontend/dist/` коммитится и не игнорируется.

## 18. Automated verification

### Backend

Проверить:

- `/api/health` → 200;
- `app == SCOZ`;
- version совпадает с `VERSION.txt`;
- `/` отдаёт production index;
- `/assets/*` отдаёт committed asset;
- unknown `/api/...` → 404;
- unknown frontend path → 404.

### Launcher

Проверить:

- SCOZ health считается already-running;
- чужой HTTP response не считается SCOZ;
- occupied non-SCOZ port → controlled failure;
- browser вызывается только после health success;
- `SCOZ_NO_BROWSER=1` suppresses browser;
- startup status atomic;
- invalid status stage rejected.

### Runtime contract

Проверить:

- Python version = `3.13.14`;
- architecture = `amd64`;
- exact official Python URL;
- exact Python SHA-256;
- `pipBootstrap.sha256` непустой и 64 hex chars;
- direct runtime packages exact-pinned;
- generated lock содержит только exact pins.

## 19. Windows smoke

Обязательные сценарии:

1. **First run:** `runtime/` отсутствует → bootstrap → health → success.
2. **Second run:** runtime reuse без полной переустановки.
3. **Already running:** второй запуск не создаёт второй server.
4. **Occupied port:** dummy server на `17842` не убивается, silent port switch отсутствует.
5. **Spaces/Cyrillic path:** запуск из `C:\Temp\SCOZ тест\Аналитика`.
6. **Runtime damage:** repair/rebuild без удаления `data/`.
7. **Bad checksum/download:** artifact не публикуется как runtime; ошибка понятна; log существует.

## 20. CI

Минимальный CI:

- Python tests;
- frontend `npm ci`;
- frontend build;
- `frontend/dist` consistency;
- deterministic Windows contract/smoke steps, которые не требуют реальных credentials/APIs.

Frontend consistency gate:

```text
npm ci
npm run build
git diff --exit-code -- frontend/dist
```

CI Node line: Node 24 LTS.

## 21. Target repository shape after PR1

```text
SCOZ/
├─ .github/workflows/ci.yml
├─ backend/
│  ├─ __init__.py
│  ├─ config.py
│  └─ main.py
├─ frontend/
│  ├─ src/
│  │  ├─ main.tsx
│  │  ├─ App.tsx
│  │  └─ styles.css
│  ├─ dist/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ tsconfig.json
│  └─ vite.config.ts
├─ scripts/bootstrap.ps1
├─ tests/
│  ├─ test_backend.py
│  ├─ test_launcher.py
│  ├─ test_runtime_contract.py
│  └─ windows_smoke.ps1
├─ start.bat
├─ launcher.py
├─ requirements.in
├─ requirements.lock.txt
├─ runtime_manifest.json
├─ VERSION.txt
├─ .gitignore
└─ AGENTS.md
```

Не создавать пустые future architecture folders.

## 22. Explicit non-goals

PR1 не реализует SQLite domain DB, migrations/repositories, Product, ProductExternalIdentity, ImportBatch, SourceArtifact, XLSX imports, Ozon/MPStats APIs, credentials UI, encrypted keystore, benchmark, relevant queries, competitors, analytics, diagnostics, Ramp-up, background jobs, scheduler, auth, users/roles, auto-update, installer или LAN mode.

UI-аудитные замечания по chart colors, competitor characteristics и `Добавить по SKU` решаются в PR-specific specs тех PR, где эти элементы впервые появляются.

## 23. Acceptance / Definition of Done

PR1 принят только если:

- clean Windows user проходит `ZIP → extract → start.bat → working SCOZ` без system Python/Node;
- Python runtime project-local и скачанный Python проверяется по pinned SHA-256;
- pip bootstrap также pinned by SHA-256 до merge;
- valid runtime reused on second run;
- dependency drift repairable, broken runtime rebuildable;
- backend слушает только `127.0.0.1:17842`;
- health однозначно идентифицирует SCOZ;
- browser открывается только после health;
- second launch не создаёт второй backend;
- чужой процесс на порту не завершается и не обходится silent port switching;
- spaces/Cyrillic path проверен;
- React production assets присутствуют в repository ZIP и соответствуют source;
- global shell содержит только `Товары / Данные / Настройки`;
- UI соответствует frozen Visual Design System;
- runtime/data не попадают в Git;
- automated tests и Windows smoke проходят;
- diff не содержит scope PR2+;
- при проверке diff frozen master documents пересматриваются только в части конкретного PR1 contract, без нового общего redesign.
