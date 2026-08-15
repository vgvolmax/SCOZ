# SCOZ — PR1 Implementation Spec: Portable Application Foundation

**Дата:** 2026-08-15  
**Статус:** approved corrective implementation spec
**PR:** PR1 из canonical PR Development Plan

## 1. Цель PR

Создать минимальный, реально запускаемый foundation локального Windows-приложения SCOZ:

> repository ZIP → extract → `start.bat` → browser UI.

PR1 обеспечивает portable runtime, FastAPI health/static foundation, React/TypeScript shell с committed production assets, понятный startup lifecycle и Windows smoke. Он не реализует imports, credentials, SQLite schema, marketplace adapters, analytics или другие PR2+ features.

Portable runtime не проектируется заново: SCOZ адаптирует proven startup/runtime/server lifecycle текущего main проекта `bimjim225-ship-it/WB_OZON_Yandex`, меняя только SCOZ-specific имя, порт, dependencies, backend и frontend.

## 2. Frozen contracts

- Windows 10/11 x64.
- Python 3.13.14 Windows embeddable x64 в project-local `runtime/`.
- Python URL: `https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip`.
- pip bootstrap URL: `https://bootstrap.pypa.io/get-pip.py`.
- Host `127.0.0.1`, port `17842`; no LAN и no dynamic fallback.
- App/version: `SCOZ` / `0.1.0` из `VERSION.txt`.
- Runtime direct requirements: `fastapi==0.139.2`, `uvicorn==0.51.0` в одном `requirements.txt`.
- Frontend production assets committed в `frontend/dist/`; end user не использует Node/npm.
- `runtime/` disposable; `data/` separate persistent user state.

## 3. Target platform and user contract

Поддерживается repository ZIP, распакованный в writable local folder, включая path с spaces и Cyrillic. End user не устанавливает system Python или Node, не меняет PATH и не получает administrator rights. Runtime не регистрируется и не устанавливается в Windows.

Первый setup требует internet access к двум official HTTPS sources и package index, используемому pip. Не добавлять installer, Docker, PostgreSQL, updater, service registration или system-wide configuration.

## 4. Portable runtime

### 4.1 First-run preparation

`start.bat` является SCOZ-аналогом reference `START_DASHBOARD.cmd` и выполняет простой последовательный flow:

```text
change directory to repository root
→ create/use project-local runtime/
→ download Python ZIP to temporary .part
→ verify download exists and has a reasonable minimum size
→ verify ZIP opens and contains entries
→ publish downloaded archive
→ extract directly into runtime/
→ configure python313._pth
→ download get-pip.py to temporary .part
→ verify basic size/content sanity
→ publish temporary file
→ runtime\python.exe get-pip.py
→ runtime\python.exe -m pip install -r requirements.txt
→ validate Python and required direct packages/imports
→ launcher
```

`python313._pth` must contain active lines equivalent to:

```text
python313.zip
.
Lib\site-packages
..
import site
```

`Lib\site-packages` создаётся при необходимости. Download helpers используют bounded failure handling and understandable logs, но PR1 не создаёт отдельную artifact/integrity subsystem.

### 4.2 Dependencies

`requirements.txt` is the only user-runtime dependency input:

```text
fastapi==0.139.2
uvicorn==0.51.0
```

Installation and repair use ordinary pip resolution:

```text
runtime\python.exe -m pip install -r requirements.txt
```

Pip resolves transitive dependencies. Development/CI packages may live separately in `requirements-dev.txt` when needed by pytest/httpx/frontend consistency work; that file is not the user runtime source.

### 4.3 Validation, reuse, repair and rebuild

Before reuse startup checks:

1. `runtime\python.exe` exists;
2. Python starts and reports 3.13.14 on Windows x64;
3. installed direct versions equal the two exact requirements;
4. `import fastapi` and `import uvicorn` succeed.

A valid runtime is reused without reinstall.

If validation fails while runtime Python remains usable:

```text
runtime\python.exe -m pip install -r requirements.txt
→ repeat direct version/import validation
→ success: launch
```

If repair fails, or runtime Python is damaged:

```text
delete runtime/ only
→ repeat full first-run preparation
→ validate
→ launch
```

If preparation is interrupted, the next `start.bat` invocation removes/reprepares the incomplete disposable runtime. Runtime repair/rebuild never deletes or resets `data/`.

## 5. Startup file responsibilities

### `start.bat`

- changes directory safely with `%~dp0`;
- owns runtime bootstrap, validation, repair and rebuild using CMD-compatible Windows tooling, as in the reference;
- writes understandable runtime stages/errors to console and `data/launcher.log`;
- invokes project-local Python only;
- after validation invokes `launcher.py` startup flow;
- returns a meaningful nonzero exit code on failure.

### `RUN_SERVER.cmd`

Small server-process wrapper following the reference model:

```text
runtime\python.exe launcher.py --serve
→ record PID
→ append server console log
→ expose exit-code diagnostic
```

It contains no business logic and uses quoted project-relative paths.

### `launcher.py`

Owns application lifecycle after runtime is ready:

- preflight;
- already-running/port check;
- backend import;
- server start through `RUN_SERVER.cmd`;
- PID and server console log coordination;
- startup status;
- health polling;
- browser open after health.

No separate bootstrap or runtime-validator layer is required for PR1.

## 6. Local server

Uvicorn serves only `127.0.0.1:17842`. Do not bind `0.0.0.0`, expose LAN access or choose another port automatically.

`GET /api/health` returns:

```json
{
  "status": "ok",
  "app": "SCOZ",
  "version": "0.1.0"
}
```

Health response is enough to identify a ready SCOZ process; no separate identity subsystem is introduced. Production FastAPI also serves committed `frontend/dist/index.html` and `/assets/*` same-origin. Unknown `/api/*` paths remain API 404 rather than frontend fallback.

## 7. Already-running and port conflict

Launcher first probes SCOZ health. If current SCOZ is already healthy, do not start a duplicate process; report ready and open its UI. If another/old process occupies port 17842 without the expected health response, fail with a controlled diagnostic. Never kill the foreign process and never fall back to another port.

## 8. Backend foundation

Minimal structure:

```text
backend/
  __init__.py
  config.py
  main.py
```

`backend/config.py` centralizes root, data path, host, port, app version and frontend distribution path. `backend/main.py` contains app composition and static/health wiring only. No business logic belongs in routes.

## 9. SQLite / persistence

SQLite schema, migrations, repositories and domain entities are explicit PR1 non-goals. `data/` may be created for startup state/logs, but no application database is created in PR1.

## 10. Frontend foundation

React + TypeScript + Vite stays as already approved:

```text
frontend/package.json
frontend/package-lock.json
frontend/src/**
frontend/dist/**
```

`package-lock.json` must be genuinely npm-generated and `frontend/dist` genuinely Vite-generated. Source and committed production build must stay consistent in CI. User startup never invokes npm, Node or Vite.

## 11. PR1 UI shell and visual contract

PR1 renders only the frozen foundation shell from the canonical UI/UX and Visual Design System:

- navigation: `Товары`, `Данные`, `Настройки`;
- one clearly selected section;
- page title/description area;
- neutral empty content state;
- Russian user-facing copy;
- no invented scores, charts, marketplace data or PR2+ workflows.

Use canonical colors, typography, spacing, radii, focus behavior and reusable primitives. No React Router is required before a real routing need.

## 12. Startup feedback

Runtime-generated files:

```text
data/startup_status.json
data/launcher.log
data/server_console.log
data/server.pid
```

Understandable stages cover runtime setup, preflight, server start, ready and failed. Logs must not contain credentials/sensitive data. No general operations database or persistent background-job framework is introduced.

## 13. Browser contract

Browser opens only after `GET /api/health` returns successful SCOZ health. Failed runtime preparation, failed backend import, occupied foreign port, child exit or health timeout must not open the browser. `SCOZ_NO_BROWSER=1` may suppress opening for tests without changing health behavior.

## 14. Same-origin security

- loopback only;
- same-origin frontend/API;
- no permissive production CORS;
- no login/session/CSRF/TLS subsystem for the approved trusted-local profile;
- no credentials in URLs or logs;
- GET does not mutate state.

## 15. Version

`VERSION.txt` contains `0.1.0` and is the single PR1 application-version source used by backend health and launcher health validation.

## 16. Gitignore / user-owned state

Ignore at minimum:

```text
runtime/
data/
.venv/
frontend/node_modules/
*.enc.json
credential-like plaintext JSON names
```

Never commit real reports, databases, credentials, generated user state or logs. Runtime rebuild must preserve every file in `data/`.

## 17. Automated verification

### Backend

- exact health payload;
- static root and assets;
- missing assets and unknown API behavior;
- fixed host/port configuration;
- no database creation.

### Launcher

- health polling and browser ordering;
- already-running behavior;
- foreign occupied port fails without killing process;
- backend import/start failure diagnostics;
- status/log/PID behavior;
- `SCOZ_NO_BROWSER` behavior.

### Runtime contract

Static/unit checks cover:

- exact Python URL/version/architecture;
- official `get-pip.py` URL;
- `.part` downloads and basic size/archive sanity checks;
- required `_pth` entries;
- exact two direct dependencies in `requirements.txt`;
- ordinary initial install and repair command;
- validation of Python launch, direct versions and imports;
- reuse, repair, destructive rebuild of only `runtime/`;
- preservation of `data/`;
- quoted paths and project-local execution.

## 18. Windows smoke

Authoritative `windows-latest` smoke exercises the actual user flow in an isolated copy:

1. clean first run creates runtime and reaches health;
2. second run reuses a valid runtime;
3. mismatched/damaged dependency triggers pip repair and reaches health;
4. failed repair or damaged Python triggers runtime rebuild;
5. occupied foreign port fails understandably and the foreign process survives;
6. path with spaces and Cyrillic succeeds;
7. a sentinel in `data/` survives repair and rebuild.

The harness suppresses browser UI only through `SCOZ_NO_BROWSER=1`, never uses real marketplace credentials and does not mutate developer user state.

## 19. CI

Windows CI runs:

- developer Python tests from `requirements-dev.txt`;
- frontend `npm ci` and production build;
- `git diff --exit-code -- frontend/dist`;
- full portable Windows smoke.

GitHub Actions is authoritative for Windows-specific acceptance after the user pushes and creates the PR. Codex reports commands actually available in its environment and does not claim unexecuted Windows scenarios.

## 20. Target repository shape after PR1

```text
.github/workflows/ci.yml
.gitignore
README.md
RUN_SERVER.cmd
VERSION.txt
backend/
frontend/
  package.json
  package-lock.json
  src/
  dist/
launcher.py
requirements.txt
requirements-dev.txt
start.bat
tests/
  test_backend.py
  test_launcher.py
  test_runtime_contract.py
  windows_smoke.ps1
```

## 21. Explicit non-goals

No SQLite/domain foundation, migrations, imports, credentials UI/keystore implementation, Ozon/MPStats integration, benchmark, analytics, query workflow, jobs, auth, updater, installer, LAN support or user-side frontend build.

## 22. Acceptance / Definition of Done

- repository ZIP starts through `start.bat` on Windows x64 without system Python/Node/admin rights;
- runtime is Python 3.13.14 embeddable x64 in project-local `runtime/`;
- first run follows the proven reference download, `_pth`, get-pip and ordinary requirements install flow;
- exact direct FastAPI/Uvicorn pins are installed from `requirements.txt`;
- valid runtime reuse, pip repair and disposable full rebuild work;
- repair/rebuild never touches `data/`;
- server binds only `127.0.0.1:17842` and health identifies SCOZ 0.1.0;
- browser opens only after health;
- occupied foreign port is not killed;
- committed Vite production assets match frontend source and need no user-side build;
- startup has understandable console/status/log feedback;
- seven Windows smoke scenarios pass in authoritative CI;
- no PR2+ product/application scope is present.
