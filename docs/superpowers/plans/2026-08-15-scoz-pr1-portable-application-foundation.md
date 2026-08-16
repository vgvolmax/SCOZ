# SCOZ PR1 Portable Application Foundation Implementation Plan

> **Implementation basis:** follow the current main startup/runtime/server lifecycle of `bimjim225-ship-it/WB_OZON_Yandex`; adapt only SCOZ name, port, direct dependencies, backend and frontend.

**Goal:** Deliver repository ZIP → extract → `start.bat` → healthy local SCOZ UI without system Python, Node, administrator rights or a user-side frontend build.

**Architecture:** `start.bat` owns the simple reference-compatible embeddable-Python setup, validation, pip repair and disposable rebuild. `RUN_SERVER.cmd` is the small server wrapper. `launcher.py` owns preflight, port/server lifecycle, status/logs, health and browser-after-health. FastAPI provides the health/static foundation and serves the approved committed HTML/CSS/JavaScript shell directly.

**Scope boundary:** Documentation and implementation of PR1 only. Do not add SQLite/domain entities, marketplace adapters, imports, credentials, analytics, jobs, auth, updater, installer, LAN access or PR2+ behavior.

## Execution ownership

Codex implements on the already selected branch and runs every check available in its environment. The user later pushes and creates the PR. GitHub Actions `windows-latest` is authoritative for the post-push Windows acceptance flow; independent review follows CI.

## Global constraints

- Windows 10/11 x64; Python 3.13.14 embeddable x64.
- Python source: `https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip`.
- pip bootstrap source: `https://bootstrap.pypa.io/get-pip.py`.
- Runtime dependencies: exactly `fastapi==0.139.2` and `uvicorn==0.51.0` in `requirements.txt`.
- Fixed `127.0.0.1:17842`, app `SCOZ`, version `0.1.0`.
- `runtime/` is project-local and disposable; `data/` is separate persistent user state.
- No PATH changes, administrator rights, system Python or user-side Node/npm.
- Browser only after successful `GET /api/health`.
- TDD for deterministic launcher/runtime contracts; production code only after the relevant failing test.

## File map locked by this plan

```text
.github/workflows/ci.yml
.gitignore
README.md
RUN_SERVER.cmd
VERSION.txt
backend/__init__.py
backend/config.py
backend/main.py
frontend/index.html
frontend/assets/css/app.css
frontend/assets/js/app.js
launcher.py
requirements.txt
requirements-dev.txt
start.bat
tests/test_backend.py
tests/test_frontend_contract.py
tests/test_launcher.py
tests/test_runtime_contract.py
tests/windows_smoke.ps1
```

No additional portable-runtime subsystem is planned.

---

### Task 1: Establish version, requirements and basic runtime contracts

**Files:** create `VERSION.txt`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `tests/test_runtime_contract.py`.

- [ ] **Step 1: Write failing static contract tests**

Assert:

- `VERSION.txt` is exactly `0.1.0` plus newline;
- `requirements.txt` has only `fastapi==0.139.2` and `uvicorn==0.51.0`;
- runtime and test dependencies are separate;
- `.gitignore` excludes `runtime/`, `data/`, `.venv/`, encrypted credential files and plaintext credential-like JSON names;
- no generated runtime/data files are tracked.

- [ ] **Step 2: Run the focused test and confirm expected failure**

```powershell
python -m pytest tests\test_runtime_contract.py -q
```

- [ ] **Step 3: Create the minimal files**

`requirements-dev.txt` may include `-r requirements.txt`, pytest and httpx needed by PR1 tests. Do not make it the user runtime source.

- [ ] **Step 4: Run and pass the focused test**

```powershell
python -m pytest tests\test_runtime_contract.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add VERSION.txt requirements.txt requirements-dev.txt .gitignore tests/test_runtime_contract.py
git commit -m "chore: define SCOZ PR1 runtime inputs"
```

---

### Task 2: Build the committed static application shell

**Files:** create `frontend/index.html`, `frontend/assets/css/app.css`, `frontend/assets/js/app.js`, and `tests/test_frontend_contract.py`.

- [ ] **Step 1: Write frontend contract tests**

Check that `frontend/index.html` exists and links the local CSS and JavaScript; global navigation contains exactly `Товары`, `Данные`, `Настройки`, with `Товары` default active; Russian page title/description and neutral empty state remain; required design tokens, keyboard/focus basics and `aria-current` or equivalent active semantics are present. Reject PR2+ content, remote CDN references, framework/build dependencies and package-manager artifacts.

- [ ] **Step 2: Create the production entry point and styles**

Create shell markup in `frontend/index.html` and implement the canonical Visual Design System in `frontend/assets/css/app.css`, preferably using CSS custom properties. Add no CSS framework, CDN library, product workflow, fake chart/score, marketplace data, API settings or PR2+ behavior.

- [ ] **Step 3: Add only required shell behavior**

Implement global navigation, active-section state and genuinely required DOM behavior in `frontend/assets/js/app.js`. Do not add business analytics or speculative module/framework architecture.

- [ ] **Step 4: Verify the static contract**

```powershell
python -m pytest tests\test_frontend_contract.py -q
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check frontend/assets/js/app.js
} else {
    Write-Host "SKIP: optional Node syntax check is unavailable"
}
```

Node is not a required SCOZ dependency. When a preinstalled Node executable is available, `node --check` provides additional syntax verification; when Node is unavailable in Codex Cloud or a developer environment, report this check as `SKIP`, not `IMPLEMENTATION BLOCKED`. Python/static contract tests remain the required frontend verification, so this task requires no network, package manager or npm registry. Do not introduce another JavaScript runtime or JavaScript testing framework in PR1.

- [ ] **Step 5: Commit**

```powershell
git add frontend tests/test_frontend_contract.py
git commit -m "feat: add SCOZ application shell"
```

---

### Task 3: Add FastAPI health and static production serving

**Files:** create `backend/__init__.py`, `backend/config.py`, `backend/main.py`, `tests/test_backend.py`.

- [ ] **Step 1: Write failing backend tests**

Cover exact health response, `/` serving committed `frontend/index.html`, `/assets/*` serving committed production assets, missing asset, unknown `/api/*` returning 404, unknown frontend path returning 404, configuration `127.0.0.1:17842`, version loaded from `VERSION.txt`, and absence of database creation.

- [ ] **Step 2: Implement minimal backend composition**

`GET /api/health` returns:

```json
{"status":"ok","app":"SCOZ","version":"0.1.0"}
```

Serve committed `frontend/index.html` and `frontend/assets/*` same-origin. Do not add a catch-all SPA fallback: unknown frontend paths remain 404. Do not add business logic, persistence or permissive production CORS.

- [ ] **Step 3: Run tests**

```powershell
python -m pytest tests\test_backend.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add backend tests/test_backend.py
git commit -m "feat: add SCOZ health and static serving"
```

---

### Task 4: Implement testable launcher and server-wrapper lifecycle

**Files:** create `launcher.py`, `RUN_SERVER.cmd`, `tests/test_launcher.py`.

- [ ] **Step 1: Write failing lifecycle tests**

Cover atomic status-file output, log output, exact current-SCOZ health detection, healthy already-running reuse with the same PID and no duplicate backend, foreign occupied port failure without process termination, backend import failure, child exit/timeout, sole server-wrapper PID ownership/server log behavior, `SCOZ_NO_BROWSER`, and browser-after-health ordering.

- [ ] **Step 2: Implement launcher preflight**

Check repository root, committed frontend entry, writable `data/`, backend import and fixed port. Do not create DB/migrations. Health success for current SCOZ means already running; any other listener means controlled failure.

- [ ] **Step 3: Implement `RUN_SERVER.cmd`**

Use quoted paths and the simple reference shape:

```text
runtime\python.exe launcher.py --serve
→ obtain the started server-process PID and write data/server.pid
→ data/server_console.log
→ exit code diagnostic
```

The `--serve` path starts Uvicorn only on `127.0.0.1:17842`. `RUN_SERVER.cmd` is the sole owner that writes the server-process PID to `data/server.pid`. The parent launcher starts `RUN_SERVER.cmd` and coordinates preflight, exact current-SCOZ health polling, already-running detection, browser-after-health and startup status; it never writes a competing PID.

- [ ] **Step 4: Implement startup feedback and browser behavior**

Use:

```text
data/startup_status.json
data/launcher.log
data/server_console.log
data/server.pid
```

Browser opening occurs only after exact successful health. Tests suppress it with `SCOZ_NO_BROWSER=1`.

Write every `data/startup_status.json` update atomically: first write the complete JSON to a sibling temporary file such as `data/startup_status.json.tmp`, then use `os.replace` or an equivalent atomic replace. Unit tests must verify the atomic replacement path. This is a status-file safeguard, not staging or atomic publication of `runtime/`.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests\test_launcher.py -q
git add launcher.py RUN_SERVER.cmd tests/test_launcher.py
git commit -m "feat: add SCOZ launcher lifecycle"
```

---

### Task 5: Implement the reference-compatible portable bootstrap

**Files:** create `start.bat`; extend `tests/test_runtime_contract.py`.

- [ ] **Step 1: Add failing bootstrap contract tests**

Assert that `start.bat`:

- changes to `%~dp0` and quotes paths;
- creates/reuses only project-local `runtime/`;
- downloads the exact Python ZIP to `.part`, checks reasonable size, opens it as a ZIP and requires entries before publishing/extracting directly into runtime;
- writes `python313._pth` with `python313.zip`, `.`, `Lib\site-packages`, `..`, `import site`;
- downloads official `get-pip.py` to `.part`, checks basic size/content sanity, publishes and executes it with runtime Python;
- installs with `runtime\python.exe -m pip install -r requirements.txt`;
- validates runtime Python plus exact FastAPI/Uvicorn versions and imports;
- invokes `launcher.py` only through project-local Python;
- never invokes a frontend build or package manager; Node is unnecessary at runtime.

- [ ] **Step 2: Implement first-run flow**

Follow the reference algorithm literally, adapted to SCOZ:

```text
create data/ and log runtime_setup
→ download Python archive .part
→ basic file/size/openable-nonempty-ZIP checks
→ publish archive and extract into runtime/
→ configure embedded _pth and site-packages
→ download get-pip.py .part
→ basic file/size/content check and publish
→ runtime Python executes get-pip.py
→ ordinary pip install from requirements.txt
→ validate Python/direct versions/imports
→ launcher.py startup
```

Use official HTTPS sources and bounded understandable errors. Do not introduce extra bootstrap layers.

- [ ] **Step 3: Implement reuse, repair and rebuild**

```text
valid runtime → launch without install
invalid dependencies with usable Python
  → pip install -r requirements.txt
  → validate again
  → launch on success
repair failure or damaged Python
  → delete runtime/ only
  → repeat complete first-run preparation
```

At startup, an incomplete runtime is simply deleted/reprepared. Every path preserves `data/`.

- [ ] **Step 4: Run contract tests**

```powershell
python -m pytest tests\test_runtime_contract.py -q
```

- [ ] **Step 5: Run developer bootstrap where Windows is available**

```powershell
$env:SCOZ_NO_BROWSER='1'
cmd /c start.bat
if ($LASTEXITCODE -ne 0) { throw "start.bat failed" }
Invoke-RestMethod http://127.0.0.1:17842/api/health
```

- [ ] **Step 6: Commit**

```powershell
git add start.bat tests/test_runtime_contract.py
git commit -m "feat: add portable SCOZ runtime bootstrap"
```

---

### Task 6: Add Windows end-to-end smoke coverage

**Files:** create `tests/windows_smoke.ps1`; modify startup files only for concrete defects exposed by smoke.

- [ ] **Step 1: Create an isolated harness**

Copy the repository into a temporary writable path containing spaces and Cyrillic. Set `SCOZ_NO_BROWSER=1`. Never operate on developer `runtime/` or `data/`.

- [ ] **Step 2: Implement the eight user-flow scenarios**

1. With no runtime, run `start.bat`; assert runtime Python, startup files and healthy server.
2. Stop isolated server, run again with valid runtime; prove runtime reuse and health.
3. Without stopping that healthy SCOZ server, read `data/server.pid`, run `start.bat` again, and assert successful exit, no second backend process, unchanged PID, and the existing healthy SCOZ process still running.
4. Damage/mismatch a direct dependency; assert validation triggers pip repair and health.
5. Damage Python or force repair failure; assert only runtime is rebuilt and health returns.
6. Occupy port with a foreign test listener; assert understandable nonzero failure and listener remains alive.
7. Assert the isolated spaces/Cyrillic path succeeds.
8. Place `data/sentinel.txt` before repair/rebuild and assert it survives both.

- [ ] **Step 3: Run on Windows when available**

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Codex must not claim this passed without execution evidence. Post-push GitHub Actions is authoritative when the current environment is not Windows.

- [ ] **Step 4: Commit**

```powershell
git add tests/windows_smoke.ps1
git commit -m "test: add PR1 Windows portable smoke"
```

---

### Task 7: Add CI and static-frontend contract gate

**Files:** create `.github/workflows/ci.yml`.

- [ ] **Step 1: Configure `windows-latest`**

In order: checkout, setup Python 3.13, install `requirements-dev.txt`, run pytest (including frontend contract tests), optionally setup/use Node only for `node --check frontend/assets/js/app.js`, then run full Windows smoke. Add a reasonable timeout. Do not use marketplace credentials. CI must not access an npm registry.

- [ ] **Step 2: Verify production startup has no frontend build**

```powershell
Select-String -Path start.bat,RUN_SERVER.cmd,launcher.py -Pattern 'npm|frontend build'
```

Expected: no startup invocation.

- [ ] **Step 3: Run locally available checks and commit**

```powershell
python -m pytest -q
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check frontend/assets/js/app.js
} else {
    Write-Host "SKIP: optional Node syntax check is unavailable"
}
```

Node remains an optional CI/developer checker rather than a required SCOZ dependency. Its absence in Codex Cloud or a developer environment is a `SKIP`, never `IMPLEMENTATION BLOCKED`; Python/static contract tests still verify the frontend without Node. No package manager or npm registry is required, and no alternative JavaScript runtime or JavaScript testing framework should be added.

```powershell
git add .github/workflows/ci.yml
git commit -m "ci: verify PR1 portable foundation"
```

---

### Task 8: Document startup and perform final PR1 verification

**Files:** create `README.md`; modify implementation only for a concrete verified defect.

- [ ] **Step 1: Document end-user flow**

State Windows 10/11 x64, ZIP extraction to a writable local folder, `start.bat`, first-setup internet requirement, no system Python/Node/admin requirement, URL `http://127.0.0.1:17842`, logs and `data/` preservation. Do not describe PR2+ as implemented.

- [ ] **Step 2: Document developer commands**

From repository root in PowerShell: create developer venv, install `requirements-dev.txt`, run pytest and, when Node is available, direct JavaScript syntax checking without npm.

- [ ] **Step 3: Run verification available in the current environment**

```powershell
python -m pytest -q
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check frontend/assets/js/app.js
} else {
    Write-Host "SKIP: optional Node syntax check is unavailable"
}
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```

Report each actual result and explicitly defer unavailable Windows evidence to post-push CI. Node is not a required SCOZ dependency: use it only for additional `node --check` syntax verification when available, and report its absence in Codex Cloud or a developer environment as `SKIP`, not `IMPLEMENTATION BLOCKED`. Python/static contract tests remain sufficient to verify the frontend without Node; no package manager, npm registry, alternative JavaScript runtime or JavaScript testing framework is required. Do not ask the user to run development commands on a desktop.

- [ ] **Step 4: Scope and generated-state audit**

```powershell
git status --short
git diff --stat
git diff
git ls-files runtime data .venv
```

Reject SQLite/domain/import/credentials/marketplace/analytics/auth/updater/LAN/user-side build scope. Confirm all required file-map entries exist and no generated user state or secrets are tracked.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md
git commit -m "docs: document SCOZ portable startup"
```

## Completion gates

### Codex implementation-complete gate

- approved PR1 scope implemented;
- available Python/frontend/static checks actually run;
- scope and generated-state audits complete;
- no PR2+ scope;
- unavailable Windows checks explicitly listed;
- unavailable PyPI/network verification is reported as external pending verification for GitHub Actions/Windows acceptance, not as a frontend blocker; npm network access is never required.

### Post-push merge gate

After the user pushes and creates the PR: CI on current HEAD passes Python/static frontend checks and all eight Windows portable scenarios; independent review passes; only then may PR1 be called merge-ready.

## Plan self-review result

- Runtime lifecycle matches the proven `WB_OZON_Yandex` flow rather than a new packaging design.
- One `requirements.txt` carries exact direct user-runtime pins; pip resolves transitives during setup/repair.
- Valid runtime reuse, ordinary pip repair, disposable rebuild and `data/` preservation are explicit.
- `start.bat`, `RUN_SERVER.cmd` and `launcher.py` form the complete startup structure; `RUN_SERVER.cmd` is the sole writer of the server PID.
- Committed `frontend/index.html`, `frontend/assets/css/app.css` and `frontend/assets/js/app.js` are the production frontend; no package lock, build output or npm registry is required, and `Товары` remains the default section. The UI contract is unchanged.
- Fixed host/port, health-before-browser, occupied-port safety and understandable feedback remain acceptance requirements.
- Static routing has no SPA fallback, startup status writes atomically, and already-running smoke preserves the same healthy PID.
- PR1 stays foundation-only and introduces no PR2+ subsystem.
