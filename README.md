# SCOZ

SCOZ 0.1.0 — основа локального Windows-приложения. Текущая версия предоставляет portable-запуск, локальный FastAPI-сервер и базовую оболочку интерфейса без функций импорта и аналитики следующих PR.

## Запуск на Windows

1. Используйте Windows 10/11 x64.
2. Скачайте ZIP репозитория и **полностью** распакуйте его в доступную для записи локальную папку.
3. Запустите `start.bat`.
4. Дождитесь сообщения о готовности. Интерфейс откроется по адресу <http://127.0.0.1:17842>.

Первый запуск требует подключения к интернету: приложение загрузит официальный embeddable Python 3.13.14, `get-pip.py` и Python-зависимости. Устанавливать Python, Node/npm или запускать frontend build вручную не нужно. Права администратора также не нужны.

### Локальные папки и диагностика

- `runtime/` — закрытая для приложения, одноразовая portable-среда Python. При повреждении она может быть удалена и собрана заново автоматически.
- `data/` — постоянное пользовательское состояние. Ремонт и пересборка `runtime/` не удаляют эту папку.
- `data/scoz.db` — user-owned persistent SQLite database; pending schema migrations apply automatically before a new local server starts.
- `data/launcher.log` — этапы подготовки и запуска.
- `data/startup_status.json` — актуальный статус запуска.
- `data/server_console.log` — вывод серверного процесса.
- `data/server.pid` — идентификатор запущенного серверного процесса.

Сервер доступен только на loopback-адресе `127.0.0.1:17842`. Если порт занят другим приложением, SCOZ сообщит об ошибке и не будет завершать чужой процесс или выбирать другой порт.

## Разработка и проверки

Окно/редактор: **PowerShell**. Рабочая папка: **корень репозитория**.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Необязательная проверка JavaScript (без npm):

```powershell
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check frontend/assets/js/app.js
} else {
    Write-Host "SKIP: optional Node syntax check is unavailable"
}
```

Полный portable smoke предназначен для Windows и всегда работает с изолированной временной копией:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\windows_smoke.ps1 -Mode Full
```
