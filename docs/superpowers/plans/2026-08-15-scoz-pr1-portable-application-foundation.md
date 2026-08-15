# SCOZ PR1 Portable Application Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable SCOZ foundation so a clean Windows 10/11 x64 user can extract the repository ZIP, run `start.bat`, get a verified project-local Python runtime, start FastAPI on `127.0.0.1:17842`, and open the committed React production UI only after health succeeds.

**Architecture:** `start.bat` is a thin Windows entry point; `scripts/bootstrap.ps1` owns runtime download, SHA verification, staging, repair and rebuild; `launcher.py` owns application lifecycle, already-running/port handling, status/logs, server process and browser-after-health. FastAPI serves only `/api/health`, `/`, and committed `/assets/*` in PR1; React contains only the frozen global shell `Товары / Данные / Настройки`.

**Tech Stack:** Python 3.13.14 embeddable x64, FastAPI 0.139.2, Uvicorn 0.51.0, React 19.2.8, React DOM 19.2.8, Vite 8.1.5, TypeScript 7.0.2, PowerShell, Windows batch, pytest 9.1.1, HTTPX 0.28.1.

## Execution ownership

- The user selects the working branch before the task starts. Codex works only in that selected branch and does not create, switch, search for, or delete branches.
- Codex implements the approved scope and runs the checks available in its cloud environment. Codex does not push, create a Pull Request, or merge.
- The user pushes the implementation and creates the Pull Request.
- GitHub Actions performs the authoritative post-push CI. GitHub Actions `windows-latest` is the authoritative Windows-specific acceptance environment for the active Codex Cloud workflow.
- Independent review follows push, Pull Request creation, and successful CI; only then is a merge decision made.
- Codex must not ask the user to run development or testing commands on the user's desktop.

The commit messages shown in Tasks 1–8 are recommended logical checkpoints, not acceptance requirements. The Codex execution environment may return the PR1 change in one or several commits. The final diff, verification evidence, and scope compliance are authoritative; one Task is not one Pull Request, and the complete PR1 remains the single sequence of Tasks 1–8.

## Global Constraints

- End-user flow is `repository ZIP → extract → start.bat → project-local runtime → FastAPI + committed React build`.
- End user must not need system Python, Node/npm, Docker, PostgreSQL, admin rights, PATH changes, or a frontend build.
- Production bind is exactly `127.0.0.1:17842`; never `0.0.0.0`, LAN bind, or silent dynamic-port fallback.
- Browser opens only after a valid current-version SCOZ `/api/health` response.
- Python artifact is exactly `python-3.13.14-embed-amd64.zip` with SHA-256 `90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907`.
- Every downloaded bootstrap/runtime artifact is SHA-256 verified before use.
- `frontend/dist/` is committed; `start.bat` never runs npm.
- `runtime/` and `data/` are user-owned/generated state and never committed.
- No SQLite/domain schema, imports, credentials, benchmark, analytics, future feature tables, auth, jobs, updater, or LAN infrastructure in PR1.
- No business logic in React or route handlers.
- Visual shell must follow `docs/superpowers/specs/scoz-visual-design-system.md` without inventing product features.
- Use TDD for deterministic Python lifecycle/runtime contracts. Do not add a frontend test framework solely for the static PR1 shell.

---

## File map locked by this plan

**Create:**

```text
.github/workflows/ci.yml
.gitignore
README.md
VERSION.txt
requirements.in
requirements.lock.txt
requirements-dev.txt
runtime_manifest.json
start.bat
launcher.py
backend/__init__.py
backend/config.py
backend/main.py
scripts/bootstrap.ps1
scripts/validate_runtime.py
frontend/package.json
frontend/package-lock.json
frontend/tsconfig.json
frontend/vite.config.ts
frontend/index.html
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/styles.css
frontend/dist/**
tests/test_runtime_contract.py
tests/test_backend.py
tests/test_launcher.py
tests/windows_smoke.ps1
```

**Modify only if implementation proves necessary:**

```text
AGENTS.md
```

Do not create `db/`, `repositories/`, `domain/`, `adapters/`, `analytics/`, `services/`, or future feature folders in PR1.

---

### Task 1: Lock version, runtime manifest and dependency contracts

**Files:**
- Create: `VERSION.txt`
- Create: `runtime_manifest.json`
- Create: `requirements.in`
- Create: `requirements.lock.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `tests/test_runtime_contract.py`

**Interfaces:**
- Produces: `VERSION.txt` containing `0.1.0`.
- Produces: `runtime_manifest.json` schema version 1 with Python 3.13.14 amd64, official URL/SHA and verified get-pip SHA.
- Produces: `requirements.lock.txt` as the only runtime install source.
- Later tasks consume these files; no Python module API yet.

- [ ] **Step 1: Create the test environment files and write failing runtime-contract tests**

In **VS Code**, from repository root, create `requirements-dev.txt`:

```text
-r requirements.lock.txt
httpx==0.28.1
pytest==9.1.1
```

Create `tests/test_runtime_contract.py` with tests equivalent to:

```python
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_pr1_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "0.1.0"


def test_runtime_manifest_is_fully_pinned():
    manifest = json.loads((ROOT / "runtime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["pythonVersion"] == "3.13.14"
    assert manifest["architecture"] == "amd64"
    assert manifest["python"]["url"] == "https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip"
    assert manifest["python"]["sha256"] == "90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"
    assert manifest["pipBootstrap"]["url"] == "https://bootstrap.pypa.io/get-pip.py"
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["pipBootstrap"]["sha256"])


def test_runtime_lock_is_exactly_pinned():
    lines = [line.strip() for line in (ROOT / "requirements.lock.txt").read_text(encoding="utf-8").splitlines()]
    packages = [line for line in lines if line and not line.startswith("#")]
    assert packages
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^=<>~!\s]+", line) for line in packages)
    names = {line.split("==", 1)[0].lower().replace("_", "-") for line in packages}
    assert "fastapi" in names
    assert "uvicorn" in names


def test_user_state_is_ignored_but_frontend_dist_is_not():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for required in ("runtime/", "data/", ".venv/", "frontend/node_modules/", "*.enc.json"):
        assert required in text
    assert "frontend/dist/" not in text
```

- [ ] **Step 2: Run the targeted test and confirm failure**

In **PowerShell**, repository root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest==9.1.1
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_contract.py -q
```

Expected: FAIL because `VERSION.txt`, manifest, lock and `.gitignore` do not exist yet.

- [ ] **Step 3: Pin the official get-pip artifact hash**

In **PowerShell**, repository root:

```powershell
$GetPip = Join-Path $env:TEMP 'scoz-get-pip.py'
Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $GetPip
$GetPipSha = (Get-FileHash -LiteralPath $GetPip -Algorithm SHA256).Hash.ToLowerInvariant()
$GetPipSha
```

Expected: exactly 64 lowercase hex characters. Put this exact value into `runtime_manifest.json`; do not leave a placeholder. Delete the temporary file after recording the hash.

- [ ] **Step 4: Create version, manifest and direct requirements**

Create `VERSION.txt`:

```text
0.1.0
```

Create `requirements.in`:

```text
fastapi==0.139.2
uvicorn==0.51.0
```

Create `runtime_manifest.json` using the approved spec and the exact SHA from Step 3.

Create `.gitignore` with at least:

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

Do not ignore `frontend/dist/`.

- [ ] **Step 5: Generate and verify the authoritative Windows runtime lock**

Codex should generate the authoritative Windows x64 + Python 3.13 runtime lock directly when its current execution environment can perform trustworthy Windows-target dependency resolution. The following PowerShell commands are the reference procedure for such a Windows execution environment; they are not instructions for the user to run on a desktop. From the repository root, use a clean environment that contains no test packages:

```powershell
py -3.13 -m venv .lock-venv
.\.lock-venv\Scripts\python.exe -m pip install --upgrade pip
.\.lock-venv\Scripts\python.exe -m pip install -r requirements.in
.\.lock-venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding ascii requirements.lock.txt
Remove-Item -Recurse -Force .lock-venv
```

Then inspect `requirements.lock.txt`: every package line must be `name==version`; no editable/VCS/local-path dependencies.

The resulting lock must be fully resolved, exact-pinned, authoritative for the Windows x64 + Python 3.13 user runtime, include all runtime dependencies actually required on Windows, and contain no Linux-only assumptions. Production runtime installation remains locked to `--only-binary=:all:` and `--no-deps`.

If the current Codex Cloud environment cannot perform trustworthy Windows-target dependency resolution, Codex must not substitute a Linux-generated `pip freeze` and call it authoritative, and it must not ask the user to run the process on a desktop. Codex may commit `requirements.lock.txt` only when it can justify the lock's Windows-target correctness; otherwise it must explicitly identify Windows runtime-lock verification as pending post-push verification.

After the user pushes the implementation, GitHub Actions `windows-latest` is the authoritative verification environment for the committed runtime lock. Any missing Windows dependency, incorrect pin, Linux-only assumption, or runtime-lock validation failure discovered there means the Pull Request is not merge-ready and requires a corrective implementation cycle; desktop fallback is not used. Windows runtime-lock verification, runtime validation, and the full Windows smoke must pass in the post-push merge gate.

- [ ] **Step 6: Install dev requirements and run tests green**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add VERSION.txt runtime_manifest.json requirements.in requirements.lock.txt requirements-dev.txt .gitignore tests/test_runtime_contract.py
git commit -m "chore: lock PR1 runtime contract"
```

---

### Task 2: Build the minimal React/TypeScript shell and committed production assets

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/dist/**`

**Interfaces:**
- Produces: static production entry `frontend/dist/index.html` and hashed assets under `frontend/dist/assets/`.
- Backend Task 3 serves these files unchanged.
- UI state is local React state only; no routing/API/business model.

- [ ] **Step 1: Create exact frontend package metadata**

In **VS Code**, create `frontend/package.json` with exact direct versions:

```json
{
  "name": "scoz-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "tsc --noEmit && vite build"
  },
  "dependencies": {
    "react": "19.2.8",
    "react-dom": "19.2.8"
  },
  "devDependencies": {
    "@types/react": "19.2.18",
    "@types/react-dom": "19.2.4",
    "@vitejs/plugin-react": "6.0.4",
    "typescript": "7.0.2",
    "vite": "8.1.5"
  }
}
```

Generate `frontend/package-lock.json` through normal npm resolution. Never hand-write it, reduce it to direct dependencies, or imitate a resolved dependency graph; the generated lock must pass `npm ci`.

- [ ] **Step 2: Create TypeScript/Vite config with no router**

`frontend/tsconfig.json` should enable strict TS, modern browser modules and React JSX. `frontend/vite.config.ts` should use `@vitejs/plugin-react` and output to the default `dist/` directory. Do not add React Router or any other application dependency.

- [ ] **Step 3: Implement the shell**

`frontend/src/App.tsx` must expose exactly three global sections:

```tsx
const sections = ["Товары", "Данные", "Настройки"] as const;
```

Default active section is `Товары`. Navigation is keyboard reachable and uses `aria-current="page"` for the active item. Section bodies are truthful foundation empty states only; no fake upload, source, benchmark, diagnostic or KPI actions.

A minimal shape:

```tsx
export function App() {
  const [active, setActive] = useState<(typeof sections)[number]>("Товары");
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Основная навигация">
        <div className="brand">SCOZ</div>
        <nav>
          {sections.map((section) => (
            <button
              key={section}
              type="button"
              className={active === section ? "nav-item is-active" : "nav-item"}
              aria-current={active === section ? "page" : undefined}
              onClick={() => setActive(section)}
            >
              {section}
            </button>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <h1>{active}</h1>
        <section className="empty-state">Данные для этого раздела пока не загружены.</section>
      </main>
    </div>
  );
}
```

Do not show Product Workspace tabs in PR1.

- [ ] **Step 4: Implement the frozen visual tokens**

In `frontend/src/styles.css`, centralize the approved base/primary tokens from `scoz-visual-design-system.md`, including `--color-app-bg`, surfaces, borders, text, primary states, spacing/radii and focus ring. Use Segoe UI stack, ~224px sidebar, 24–32px content padding, thin borders, no gradients/glassmorphism/dashboard wall.

Include an explicit focus rule such as:

```css
:focus-visible {
  outline: 3px solid var(--color-primary-border);
  outline-offset: 2px;
}
```

- [ ] **Step 5: Build production assets**

In **PowerShell**:

```powershell
cd frontend
npm ci
npm run build
cd ..
```

Expected: `frontend/dist/index.html` plus at least one asset under `frontend/dist/assets/`; build exits 0.

`frontend/dist` is Vite-generated production output from the current source. Never hand-write production JS/CSS, substitute Vite output manually, or maintain a separate handcrafted dist implementation.

- [ ] **Step 6: Verify the build contains no development dependency on Node at runtime**

From repository root:

```powershell
Test-Path frontend\dist\index.html
Get-ChildItem frontend\dist\assets
```

Expected: production files exist. No script in `start.bat` exists yet, so no npm runtime call can exist.

- [ ] **Step 7: Commit**

```powershell
git add frontend
git commit -m "feat: add SCOZ React application shell"
```

---

### Task 3: Add FastAPI health and static production serving

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `backend/main.py`
- Create: `tests/test_backend.py`

**Interfaces:**
- Produces: `backend.config.APP_NAME`, `VERSION`, `HOST`, `PORT`, `ROOT`, `FRONTEND_DIST`.
- Produces: `backend.main.app: FastAPI`.
- Produces: `GET /api/health` payload `{status, app, version}`.
- Serves: `/` and `/assets/*`; unknown paths remain 404.

- [ ] **Step 1: Write failing backend tests**

Create `tests/test_backend.py`:

```python
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import VERSION

client = TestClient(app)


def test_health_identifies_current_scoz():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "SCOZ", "version": VERSION}


def test_root_serves_committed_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root"></div>' in response.text


def test_unknown_api_is_not_frontend_fallback():
    assert client.get("/api/not-real").status_code == 404


def test_unknown_frontend_path_is_404():
    assert client.get("/not-a-route").status_code == 404
```

Add one test that reads the generated `frontend/dist/index.html`, extracts an `/assets/...` reference, and confirms that exact asset returns 200.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_backend.py -q
```

Expected: FAIL because backend package/app does not exist.

- [ ] **Step 3: Implement foundation config**

`backend/config.py` must read `VERSION.txt` from repository root:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "SCOZ"
VERSION = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
HOST = "127.0.0.1"
PORT = 17842
FRONTEND_DIST = ROOT / "frontend" / "dist"
```

Do not add environment-driven source/database settings.

- [ ] **Step 4: Implement FastAPI app**

`backend/main.py` should create FastAPI, mount assets only if the committed assets directory exists, expose exact health and root routes, and not add catch-all fallback:

```python
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import APP_NAME, FRONTEND_DIST, VERSION

app = FastAPI(title=APP_NAME, version=VERSION)

assets = FRONTEND_DIST / "assets"
if assets.is_dir():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME, "version": VERSION}

@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIST / "index.html")
```

No CORS middleware.

- [ ] **Step 5: Run backend tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_backend.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend tests/test_backend.py
git commit -m "feat: add SCOZ health and static backend"
```

---

### Task 4: Implement testable launcher lifecycle

**Files:**
- Create: `launcher.py`
- Create: `tests/test_launcher.py`

**Interfaces:**
- Produces: `write_startup_status(stage: str, message: str) -> None`.
- Produces: `probe_health(timeout: float = ...) -> bool`, requiring `status=ok`, `app=SCOZ`, and current `version`.
- Produces: `port_is_occupied() -> bool`.
- Produces: `wait_until_healthy(timeout_seconds: float, interval_seconds: float) -> bool`.
- Produces: `open_browser() -> None`, respecting `SCOZ_NO_BROWSER=1`.
- Produces: `start_server_process() -> subprocess.Popen` and writes `data/server.pid`.
- Produces CLI mode `python launcher.py --start`.

- [ ] **Step 1: Write failing launcher tests**

Create isolated tests using `tmp_path`/`monkeypatch`; never bind a real production port in unit tests.

Required cases:

```python
def test_health_requires_scoz_identity_and_current_version(...): ...
def test_foreign_health_payload_is_not_scoz(...): ...
def test_old_scoz_version_is_not_current_running_instance(...): ...
def test_status_write_replaces_file_atomically(...): ...
def test_invalid_status_stage_is_rejected(...): ...
def test_no_browser_env_suppresses_open(...): ...
def test_browser_open_happens_only_after_health(...): ...
def test_occupied_non_scoz_port_fails_without_starting_server(...): ...
def test_start_server_writes_pid(...): ...
```

For health tests inject/monkeypatch `urllib.request.urlopen`; for browser tests monkeypatch the platform open function; for server tests monkeypatch `subprocess.Popen`.

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_launcher.py -q
```

Expected: FAIL because `launcher.py` does not exist.

- [ ] **Step 3: Implement status/log foundation**

Create constants from `backend.config`; runtime-generated files:

```text
data/startup_status.json
data/launcher.log
data/server_console.log
data/server.pid
```

Allowed stages exactly:

```python
ALLOWED_STAGES = {
    "preflight", "runtime_setup", "database_backup", "migration",
    "server_start", "ready", "failed"
}
```

`write_startup_status()` must write `startup_status.json.tmp` then `os.replace()`.

If environment variable `SCOZ_STARTUP_STARTED_AT` is present, reuse it as `startedAt`; otherwise create UTC ISO timestamp.

- [ ] **Step 4: Implement strict health identity**

`probe_health()` must parse JSON and return true only when all match:

```python
payload.get("status") == "ok"
payload.get("app") == "SCOZ"
payload.get("version") == VERSION
```

A server that returns HTTP 200 but wrong/missing payload is not SCOZ. An older SCOZ version is treated as a port conflict, not as the current running instance.

- [ ] **Step 5: Implement preflight and port handling**

Preflight checks only current PR1 needs:

- repository root exists;
- `frontend/dist/index.html` exists;
- `data/` can be created/written;
- if current-version SCOZ health succeeds → already running;
- else if port 17842 accepts a TCP connection → raise a safe diagnostic error;
- do not kill process or choose another port.

Do not create DB/migration logic.

- [ ] **Step 6: Implement detached server start and PID file**

Use argv list, never shell command concatenation:

```python
command = [
    sys.executable,
    "-m", "uvicorn",
    "backend.main:app",
    "--host", HOST,
    "--port", str(PORT),
    "--no-access-log",
]
```

Run with `cwd=ROOT`, redirect stdout/stderr to `data/server_console.log`, and use Windows creation flags only when `os.name == "nt"`. Write returned PID atomically to `data/server.pid`.

- [ ] **Step 7: Implement health wait and browser-after-health**

`--start` flow:

```text
write preflight
→ if current SCOZ already running: write ready → open browser → 0
→ if foreign/old service occupies port: write failed → nonzero
→ start server process
→ write server_start
→ poll health
→ if child exits or timeout: failed + nonzero
→ health current-version SCOZ: ready → browser unless SCOZ_NO_BROWSER=1 → 0
```

Do not call browser before the health branch.

- [ ] **Step 8: Run launcher tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_launcher.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add launcher.py tests/test_launcher.py
git commit -m "feat: add SCOZ launcher lifecycle"
```

---

### Task 5: Implement portable PowerShell bootstrap and runtime validator

**Files:**
- Create: `scripts/validate_runtime.py`
- Create: `scripts/bootstrap.ps1`
- Create: `start.bat`
- Modify: `tests/test_runtime_contract.py`

**Interfaces:**
- `scripts/validate_runtime.py ROOT` exits 0 only if interpreter/version/architecture and every exact runtime lock package match.
- `scripts/bootstrap.ps1` prepares or repairs `runtime/`, then invokes `runtime\python.exe launcher.py --start`.
- `start.bat` delegates to PowerShell and returns its exit code.

- [ ] **Step 1: Extend failing runtime tests for launcher/bootstrap files**

Add static contract tests asserting:

- `start.bat` changes directory using `%~dp0` and calls `scripts\bootstrap.ps1`;
- `start.bat` contains no `pip install`, `Invoke-WebRequest`, `curl`, or application business logic;
- bootstrap references `runtime_manifest.json` and `requirements.lock.txt`;
- bootstrap computes SHA-256 before archive expansion;
- bootstrap uses a staging runtime path;
- bootstrap eventually calls `launcher.py --start` through the project-local Python;
- validator rejects a Python version not equal to manifest version and package mismatch.

- [ ] **Step 2: Run targeted tests and confirm failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_contract.py -q
```

Expected: FAIL for missing scripts.

- [ ] **Step 3: Implement `scripts/validate_runtime.py`**

The validator must:

1. read `runtime_manifest.json` and `requirements.lock.txt` from supplied root;
2. require exact `platform.machine()`/architecture compatibility for Windows amd64 when running user runtime;
3. require `platform.python_version() == manifest["pythonVersion"]`;
4. parse every non-comment lock line as exact `name==version`;
5. compare each package with `importlib.metadata.version(name)`;
6. import `fastapi` and `uvicorn`;
7. exit nonzero with a short reason on mismatch.

Keep it independent of FastAPI so it can validate runtime before app import.

- [ ] **Step 4: Implement bootstrap status helper before Python exists**

At bootstrap start:

```powershell
$env:SCOZ_STARTUP_STARTED_AT = [DateTime]::UtcNow.ToString('o')
```

Create `data/` and atomically write `stage=runtime_setup` status using temporary JSON + `Move-Item -Force`/replace semantics. Log human-readable bootstrap stages to `data/launcher.log` in UTF-8.

- [ ] **Step 5: Implement download + SHA verification helpers**

PowerShell helper must download to `.part`, retry bounded times, then run:

```powershell
$actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha.ToLowerInvariant()) { throw "Checksum mismatch" }
```

Never expand/execute before this check.

- [ ] **Step 6: Implement atomic fresh runtime build**

Use a unique staging directory such as:

```text
runtime.__staging.<pid>
```

Flow:

```text
download+verify Python
→ Expand-Archive to staging
→ rewrite python313._pth to include Lib\site-packages, .., import site
→ create Lib\site-packages
→ download+verify get-pip.py
→ staging\python.exe get-pip.py --no-warn-script-location
→ staging\python.exe -m pip install --only-binary=:all: --no-deps -r requirements.lock.txt
→ staging\python.exe scripts\validate_runtime.py <root>
→ write staging\.scoz_runtime.json with manifest/lock hashes
→ rename old runtime to runtime.__old.<pid> if present
→ rename staging to runtime
→ delete old only after publication succeeds
```

If any pre-publication step fails, delete staging and leave existing valid runtime untouched.

- [ ] **Step 7: Implement reuse and repair**

Reuse requires marker manifest hash + lock hash and `validate_runtime.py` success.

If Python launches with correct version but marker/lock validation fails:

```text
runtime\python.exe -m pip install --only-binary=:all: --no-deps -r requirements.lock.txt
→ validate again
```

If repair fails, perform atomic rebuild from Step 6.

Never delete `data/`.

- [ ] **Step 8: Implement thin `start.bat`**

Minimal shape:

```bat
@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo SCOZ не удалось запустить.
  echo Лог: %~dp0data\launcher.log
  pause
)
exit /b %EXIT_CODE%
```

If `powershell.exe` is unavailable/blocked, return nonzero with an understandable message.

- [ ] **Step 9: Run Python contract tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_contract.py -q
```

Expected: PASS.

- [ ] **Step 10: Run a developer bootstrap with browser suppressed**

In **PowerShell**, repository root:

```powershell
$env:SCOZ_NO_BROWSER='1'
cmd /c start.bat
$code = $LASTEXITCODE
Remove-Item Env:SCOZ_NO_BROWSER
if ($code -ne 0) { throw "start.bat failed: $code" }
Invoke-RestMethod http://127.0.0.1:17842/api/health
```

Expected payload exactly identifies SCOZ version 0.1.0.

- [ ] **Step 11: Commit**

```powershell
git add scripts start.bat tests/test_runtime_contract.py
git commit -m "feat: add verified portable runtime bootstrap"
```

---

### Task 6: Add Windows end-to-end smoke coverage

**Files:**
- Create: `tests/windows_smoke.ps1`
- Modify: `launcher.py` only if smoke exposes a real lifecycle defect

**Interfaces:**
- `tests/windows_smoke.ps1 -Mode Full` verifies the repository-ZIP-equivalent workflow without real Ozon/MPStats credentials.
- It uses `SCOZ_NO_BROWSER=1` and only local loopback/network download of approved runtime artifacts.

- [ ] **Step 1: Write the smoke harness before fixing any discovered issues**

The script must create an isolated copy in a path containing spaces and Cyrillic, for example under temp:

```text
...\SCOZ тест\Аналитика
```

Do not operate on the developer's real `data/` or `runtime/`.

- [ ] **Step 2: First-run case**

In isolated copy:

```powershell
$env:SCOZ_NO_BROWSER='1'
cmd /c start.bat
if ($LASTEXITCODE -ne 0) { throw 'First run failed' }
```

Assert:

- `runtime/python.exe` exists;
- `runtime/.scoz_runtime.json` exists;
- `/api/health` returns current SCOZ version;
- `data/launcher.log`, `startup_status.json`, `server_console.log`, `server.pid` exist;
- final status is `ready`.

- [ ] **Step 3: Second-run/reuse case**

Record marker `createdAt` and runtime directory timestamp, run `start.bat` again, then assert marker `createdAt` did not change. This proves no full reinstall/rebuild occurred.

- [ ] **Step 4: Already-running case**

While first server is healthy, run `start.bat` again and assert success. Compare `data/server.pid` before/after; it must remain the same.

- [ ] **Step 5: Stop the isolated SCOZ server using its PID**

Read `data/server.pid`, call `Stop-Process -Id ... -Force` only inside this isolated smoke directory, wait until port 17842 is free. Never add a production shutdown API solely for tests.

- [ ] **Step 6: Occupied-port case**

Start a temporary PowerShell/.NET `TcpListener` or minimal HTTP listener on `127.0.0.1:17842` that does not return valid SCOZ health. Run `start.bat`; assert nonzero exit, listener remains alive, and launcher log contains controlled port-conflict text. Stop the test listener afterwards.

- [ ] **Step 7: Runtime-damage repair case**

Restore free port, alter the isolated runtime marker lock hash to an invalid value, run `start.bat`, assert success and valid marker afterward. Put a sentinel file in `data/` before repair and assert it survives.

- [ ] **Step 8: Checksum-failure case**

In a fresh isolated copy, temporarily replace the manifest Python SHA with 64 zeros, ensure no runtime exists, run bootstrap, assert:

- nonzero exit;
- no published `runtime/python.exe`;
- no leftover staging directory;
- `data/launcher.log` exists and reports checksum failure.

Do not modify the source checkout manifest; mutate only the isolated smoke copy.

- [ ] **Step 9: Run the full smoke in an available Windows execution environment**

For the active Codex Cloud workflow, GitHub Actions `windows-latest` is the authoritative post-push execution environment. Codex must implement the smoke harness before handoff but must not claim the Windows smoke passed without actual execution evidence.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Expected: PASS with all seven scenarios.

- [ ] **Step 10: Commit**

```powershell
git add tests/windows_smoke.ps1 launcher.py
git commit -m "test: add PR1 Windows portable smoke"
```

---

### Task 7: Add CI and committed-frontend consistency gate

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- One Windows CI workflow validates Python tests, frontend build consistency and full portable smoke.
- No real external marketplace credentials/APIs.

- [ ] **Step 1: Create the Windows CI workflow**

Use `windows-latest`, checkout, Python 3.13 for developer tests and Node 24 LTS for frontend build.

Workflow steps, in this order:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: '3.13'
- run: python -m pip install -r requirements-dev.txt
- run: python -m pytest -q
- uses: actions/setup-node@v4
  with:
    node-version: '24'
    cache: npm
    cache-dependency-path: frontend/package-lock.json
- working-directory: frontend
  run: npm ci
- working-directory: frontend
  run: npm run build
- run: git diff --exit-code -- frontend/dist
- shell: powershell
  run: powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Add a reasonable job timeout so a stalled runtime download cannot hang CI indefinitely.

- [ ] **Step 2: Verify no user-side build leaked into launcher**

Run from repository root:

```powershell
Select-String -Path start.bat,scripts\bootstrap.ps1,launcher.py -Pattern 'npm|node_modules|vite build' -SimpleMatch
```

Expected: no production-launch invocation of npm/Node/Vite.

- [ ] **Step 3: Run verification available in the current implementation environment**

Run each command that the current environment supports and report its actual result. Do not ask the user to reproduce development/testing commands on a desktop. The full sequence, including Windows smoke, remains mandatory in the post-push GitHub Actions `windows-latest` gate.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm ci
npm run build
cd ..
git diff --exit-code -- frontend/dist
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Expected: all commands pass.

- [ ] **Step 4: Commit**

```powershell
git add .github/workflows/ci.yml frontend/dist
git commit -m "ci: verify PR1 portable foundation"
```

---

### Task 8: Document end-user startup and perform final PR1 verification

**Files:**
- Create: `README.md`
- Modify: implementation files only if verification finds a concrete defect

**Interfaces:**
- README is the user/developer entry point for PR1 and must not describe PR2+ as implemented.

- [ ] **Step 1: Write README user flow**

README must state:

```text
Windows 10/11 x64
Download ZIP → extract to writable local folder → start.bat
Internet is required on first runtime setup
No system Python/Node/admin rights required
Do not run from inside ZIP or protected Program Files/network folders
Local URL: http://127.0.0.1:17842
Logs: data/launcher.log and data/server_console.log
```

Document that first run downloads the pinned project-local runtime and later runs reuse it. Do not document any import/API/analytics feature as working in PR1.

- [ ] **Step 2: Document developer commands with exact location**

README developer section must say commands run in **PowerShell from repository root**:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm ci
npm run build
cd ..
git diff --exit-code -- frontend/dist
```

- [ ] **Step 3: Run available automated verification and identify post-push checks**

From repository root, run the applicable commands in an available execution environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm ci
npm run build
cd ..
git diff --exit-code -- frontend/dist
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Expected: all pass.

Codex must record any command it could not execute and defer that evidence to the mandatory post-push GitHub Actions run. It must not ask the user to execute these development/testing commands on the user's desktop.

- [ ] **Step 4: Run scope audit**

Inspect:

```powershell
git status --short
git diff main...HEAD --stat
git diff main...HEAD
```

Reject/remove any PR1 additions involving SQLite schema/migrations, Product/domain entities, imports, credentials, Ozon/MPStats, analytics, benchmark, jobs, auth, auto-update, LAN support, React Router, or user-side npm build.

- [ ] **Step 5: Run secret/state audit**

```powershell
git ls-files runtime data .venv frontend/node_modules
git ls-files | Select-String -Pattern '\.enc\.json$|credentials.*\.json$'
```

Expected: no generated runtime/data/credentials files are tracked.

- [ ] **Step 6: Verify required repository files exist**

```powershell
$required = @(
  'start.bat','launcher.py','VERSION.txt','runtime_manifest.json',
  'requirements.in','requirements.lock.txt','backend/main.py',
  'frontend/dist/index.html','scripts/bootstrap.ps1',
  'tests/windows_smoke.ps1','README.md'
)
$required | ForEach-Object { if (-not (Test-Path $_)) { throw "Missing: $_" } }
```

- [ ] **Step 7: Commit documentation/final corrections**

```powershell
git add README.md
git commit -m "docs: document SCOZ portable startup"
```

If verification required code fixes, commit those separately with a precise message before this docs commit.

- [ ] **Step 8: Apply the two completion gates**

### A. Codex implementation-complete gate

Before completing the Codex task, confirm from evidence:

```text
[ ] approved PR1 scope is implemented
[ ] available Python tests were run
[ ] frontend dependency/build checks were run when environment/network allowed
[ ] static contract tests were run
[ ] scope audit was completed
[ ] secret/generated-state audit was completed
[ ] no PR2+ scope is present
[ ] every check requiring post-push GitHub Actions is explicitly listed
```

Passing this gate means `Codex implementation complete`; it does not mean `PR ready to merge`.

### B. Post-push merge gate

After the user pushes and creates the Pull Request, confirm all of the following from evidence on the current HEAD:

```text
[ ] GitHub Actions workflow actually ran on current HEAD
[ ] Python tests pass
[ ] npm ci passes
[ ] npm run build passes
[ ] frontend/dist consistency passes
[ ] clean-style first run passed
[ ] second run reused runtime
[ ] already-running reused same PID
[ ] occupied foreign port failed safely
[ ] Cyrillic/spaces path passed
[ ] damaged runtime repaired/rebuilt and data sentinel survived
[ ] bad checksum was rejected before publication
[ ] health is exact app+version
[ ] browser is after health only
[ ] server binds 127.0.0.1:17842 only
[ ] frontend/dist matches source build
[ ] no user-side Node/npm
[ ] no PR2+ scope
[ ] full Windows smoke passes
[ ] no scope violations
[ ] independent PR review passes
```

Only after this post-push gate is green may the Pull Request be described as merge-ready. Windows checksum rejection, Cyrillic/spaces path, runtime reuse and repair, occupied-port safety, and the rest of the full smoke remain mandatory; their ownership/timing has changed, not their acceptance strength.

---

## Plan self-review result

- **Spec coverage:** every PR1 requirement maps to Tasks 1–8; runtime integrity, frontend static build, health, launcher, port handling, browser timing, startup files, paths, repair, checksum failure, CI and documentation are covered.
- **Scope:** no PR2 domain/persistence/import/API work is introduced.
- **Interfaces:** fixed host `127.0.0.1`, port `17842`, app `SCOZ`, version `0.1.0`, runtime Python `3.13.14`, and file paths are consistent across tasks.
- **YAGNI:** no React Router, generic settings framework, persistent job system, installer, updater or database foundation.
- **Remaining dynamic value:** the current official `get-pip.py` SHA is intentionally derived once in Task 1 and then committed as an immutable manifest value; PR1 cannot merge with a placeholder.
