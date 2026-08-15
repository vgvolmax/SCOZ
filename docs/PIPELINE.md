# Runtime pipeline

Пользовательский flow:

1. `start.bat:L1-L15` фиксирует рабочую директорию и вызывает PowerShell.
2. `scripts/bootstrap.ps1:L1-L70` проверяет manifest/lock marker и runtime; при необходимости выполняет repair или SHA-verified staging rebuild.
3. `launcher.py:L76-L130` проверяет committed UI и порт, запускает Uvicorn только на `127.0.0.1:17842`, ждёт exact current-version health и лишь затем открывает browser.
4. `backend/main.py:L10-L23` обслуживает `/api/health`, `/` и `/assets/*`.

Generated `runtime/` и `data/` не являются входными данными репозитория и не коммитятся.
