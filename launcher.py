"""Minimal SCOZ lifecycle coordinator for the prepared portable runtime."""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from backend.config import APP_NAME, BASE_URL, DATA_DIR, FRONTEND_INDEX, HOST, PORT, ROOT_DIR, VERSION
from backend.persistence.database import initialize_database

HEALTH_URL = f"{BASE_URL}/api/health"
HEALTH_TIMEOUT_SECONDS = 30


def log(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with (DATA_DIR / "launcher.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {message}\n")
    print(message, flush=True)


def write_status(stage: str, message: str, *, ok: bool | None = None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / "startup_status.json"
    temporary = DATA_DIR / "startup_status.json.tmp"
    payload = {"stage": stage, "message": message, "updated_at": datetime.now(timezone.utc).isoformat()}
    if ok is not None:
        payload["ok"] = ok
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def expected_health(payload: object) -> bool:
    return payload == {"status": "ok", "app": APP_NAME, "version": VERSION}


def fetch_health(timeout: float = 1.0) -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            if response.status != 200:
                return None
            value = json.loads(response.read().decode("utf-8"))
            return value if isinstance(value, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def port_is_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=.4):
            return True
    except OSError:
        return False


def preflight() -> None:
    write_status("preflight", "Проверка файлов приложения")
    if not FRONTEND_INDEX.is_file():
        raise RuntimeError(f"Не найден frontend: {FRONTEND_INDEX}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    probe = DATA_DIR / ".write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    from backend.main import app  # noqa: F401


def open_browser() -> None:
    if os.environ.get("SCOZ_NO_BROWSER") == "1":
        log("Открытие браузера отключено для проверки.")
        return
    webbrowser.open(BASE_URL)


def start_wrapper() -> subprocess.Popen[bytes]:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    return subprocess.Popen(["cmd.exe", "/d", "/c", str(ROOT_DIR / "RUN_SERVER.cmd")], cwd=ROOT_DIR, creationflags=creationflags)


def wait_until_ready(process: subprocess.Popen[bytes], timeout: float = HEALTH_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = fetch_health()
        if expected_health(payload):
            return True
        if process.poll() is not None:
            raise RuntimeError(f"Сервер завершился до готовности (код {process.returncode}).")
        time.sleep(.25)
    raise RuntimeError("Сервер не ответил вовремя.")


def launch() -> int:
    try:
        preflight()
        payload = fetch_health()
        if expected_health(payload):
            log("SCOZ уже запущен.")
            write_status("ready", "SCOZ уже запущен", ok=True)
            open_browser()
            return 0
        if port_is_open():
            raise RuntimeError(f"Порт {PORT} занят другим приложением. SCOZ не запускался.")
        write_status("migration", "Подготовка локальной базы данных")
        log("Применение миграций локальной базы данных...")
        initialize_database()
        write_status("server start", "Запуск локального сервера")
        log("Запуск локального сервера...")
        process = start_wrapper()
        wait_until_ready(process)
        write_status("ready", f"SCOZ доступен по адресу {BASE_URL}", ok=True)
        log(f"SCOZ готов: {BASE_URL}")
        open_browser()
        return 0
    except Exception as exc:
        message = str(exc) or type(exc).__name__
        log(f"Ошибка запуска: {message}")
        write_status("failed", message, ok=False)
        return 1


def serve() -> int:
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, log_level="info")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    return serve() if args.serve else launch()


if __name__ == "__main__":
    sys.exit(main())
