# SCOZ

SCOZ — локальная основа внутреннего Windows-приложения. В PR1 доступна только глобальная оболочка; импорт, интеграции и аналитика ещё не реализованы.

## Запуск

Поддерживаются Windows 10/11 x64. Скачайте ZIP репозитория, полностью распакуйте его в доступную для записи локальную папку и запустите `start.bat`. Не запускайте SCOZ внутри ZIP, из `Program Files`, защищённой или сетевой папки.

При первой подготовке требуется интернет: launcher скачает зафиксированный Python runtime, проверит SHA-256 и разместит его в `runtime/`. Следующие запуски переиспользуют исправный runtime. Системные Python, Node/npm, Docker, права администратора и изменение PATH пользователю не нужны.

После готовности откроется <http://127.0.0.1:17842>. Логи: `data/launcher.log` и `data/server_console.log`.

## Быстрая проверка и разработка

Команды выполняются в PowerShell из корня репозитория:

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

Windows end-to-end проверка: `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full`.

## Основные точки входа

- `start.bat:L1-L15` — тонкий пользовательский entry point.
- `scripts/bootstrap.ps1:L1-L70` — проверка, repair и атомарная сборка runtime.
- `launcher.py:L1-L130` — жизненный цикл локального приложения.
- `backend/main.py:L1-L23` — health и раздача production UI.
- `frontend/src/App.tsx:L1-L20` — глобальная оболочка.

Канонические границы PR1 описаны в
`docs/superpowers/specs/2026-08-15-scoz-pr1-portable-application-foundation-implementation-spec.md`,
а последовательность реализации и проверки — в
`docs/superpowers/plans/2026-08-15-scoz-pr1-portable-application-foundation.md`.
