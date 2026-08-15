# Changelog

## 2026-08-15 — PR1 Portable Application Foundation

Changed:
- Добавлены verified project-local runtime, launcher, loopback FastAPI и committed global React shell.
- Добавлены Python contract tests, Windows portable smoke и Windows CI.

Code:
- `scripts/bootstrap.ps1:L1-L70`
- `launcher.py:L1-L130`
- `backend/main.py:L1-L23`
- `frontend/src/App.tsx:L1-L20`

Docs:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PIPELINE.md`
- `docs/UI_GUIDE.md`

Contracts / UX:
- Changed: добавлены PR1 startup contract и frozen global shell; PR2+ не реализован.
