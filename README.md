# SCOZ

SCOZ — локальное Windows-приложение. В PR1 реализована переносимая основа приложения и нейтральная оболочка интерфейса; функции загрузки и анализа данных появятся в последующих этапах.

## Запуск пользователем

1. На Windows 10 или Windows 11 x64 скачайте ZIP репозитория.
2. Полностью распакуйте ZIP в доступную для записи локальную папку.
3. Запустите `start.bat`.

При первом запуске требуется интернет: SCOZ скачает официальный Windows embeddable Python 3.13.14, `get-pip.py` и зависимости в локальную папку `runtime/`. Установленные в системе Python и Node/npm не требуются. Права администратора и изменение `PATH` не требуются.

После успешной проверки приложение откроется по адресу <http://127.0.0.1:17842>. Сервер доступен только с этого компьютера.

`runtime/` — одноразовая среда, которую SCOZ может восстановить. Пользовательское состояние в `data/` при восстановлении среды сохраняется. Основные диагностические файлы: `data/launcher.log`, `data/server_console.log` и `data/startup_status.json`.

## Команды разработчика

Выполняйте команды в PowerShell из корня репозитория:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q

Set-Location frontend
npm ci
npm run build
Set-Location ..
git diff --exit-code -- frontend/dist
```

Полный portable smoke предназначен для Windows и запускается CI из изолированной копии репозитория.
