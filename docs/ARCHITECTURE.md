# Architecture

PR1 реализует только portable application foundation. `start.bat` делегирует lifecycle runtime скрипту `scripts/bootstrap.ps1:L1-L70`; тот запускает приложение исключительно через project-local Python. `launcher.py:L76-L130` выполняет preflight, различает текущий SCOZ и конфликт порта, запускает Uvicorn и открывает browser после health.

`backend/main.py:L1-L23` содержит тонкий HTTP foundation: неизменяющий состояние health и committed static UI. `frontend/src/App.tsx:L1-L20` хранит только локальное состояние глобальной навигации.

Planned / Not implemented: persistence, domain model, adapters, imports, credentials and analytics.
