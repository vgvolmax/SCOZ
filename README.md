# SCOZ

SCOZ в версии 0.1.0 — локальный foundation приложения для Windows с браузерным интерфейсом. Функции загрузки и аналитики в эту версию ещё не входят.

## Запуск

Поддерживаются Windows 10 и Windows 11 x64.

1. Скачайте ZIP репозитория.
2. Полностью распакуйте его в доступную для записи локальную папку (можно использовать путь с пробелами и кириллицей).
3. Запустите `start.bat`.

Не запускайте приложение внутри ZIP, из защищённой папки `Program Files` или сетевой папки. При первой подготовке требуется интернет: launcher скачает закреплённый и проверяемый project-local Python runtime. Последующие запуски используют ту же среду. Системные Python и Node/npm, права администратора и изменение `PATH` не нужны.

После проверки готовности откроется <http://127.0.0.1:17842>. Технические журналы находятся в `data/launcher.log` и `data/server_console.log`.

## Основные точки входа

- `start.bat` — пользовательский запуск;
- `scripts/bootstrap.ps1` — проверка и подготовка runtime;
- `launcher.py` — запуск локального сервера после preflight;
- `backend/main.py` — health API и раздача production UI;
- `frontend/src/` — исходный React UI, `frontend/dist/` — готовая сборка для пользователя.

Канонические продуктовые и архитектурные документы находятся в `docs/superpowers/`.

## Разработка

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
