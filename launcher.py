from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from backend.config import APP_NAME, DATA_DIR, FRONTEND_DIST, HOST, LOCAL_URL, PORT, ROOT, VERSION

STATUS_FILE = DATA_DIR / "startup_status.json"
LOG_FILE = DATA_DIR / "launcher.log"
EXPECTED_HEALTH = {"status": "ok", "app": APP_NAME, "version": VERSION}

def configure_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")

def write_status(stage: str, message: str, *, state: str = "running") -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": stage, "state": state, "message": message, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    temporary = STATUS_FILE.with_suffix(STATUS_FILE.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, STATUS_FILE)
    logging.info("%s: %s", stage, message)

def probe_health(timeout: float = 1.0) -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(f"{LOCAL_URL}/api/health", timeout=timeout) as response:
            if response.status != 200:
                return None
            value = json.load(response)
            return value if isinstance(value, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None

def is_current_scoz(payload: dict[str, object] | None) -> bool:
    return payload == EXPECTED_HEALTH

def port_is_occupied() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((HOST, PORT)) == 0

def open_browser() -> None:
    if os.environ.get("SCOZ_NO_BROWSER") != "1":
        webbrowser.open(LOCAL_URL)

def preflight() -> None:
    write_status("preflight", "Проверяем компоненты SCOZ")
    if not (ROOT / "VERSION.txt").is_file() or not (FRONTEND_DIST / "index.html").is_file():
        raise RuntimeError("Не найдены обязательные файлы приложения.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    probe = DATA_DIR / ".write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    __import__("backend.main")

def start_wrapper() -> subprocess.Popen[bytes]:
    write_status("server start", "Запускаем SCOZ")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    return subprocess.Popen(["cmd", "/d", "/c", str(ROOT / "RUN_SERVER.cmd")], cwd=ROOT, creationflags=creationflags)

def wait_until_ready(child: subprocess.Popen[bytes], timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_current_scoz(probe_health()):
            return
        if child.poll() not in (None, 0):
            raise RuntimeError(f"Сервер завершился до готовности (код {child.returncode}).")
        time.sleep(0.25)
    raise RuntimeError("Сервер SCOZ не ответил вовремя.")

def launch() -> int:
    configure_logging()
    try:
        preflight()
        health = probe_health()
        if is_current_scoz(health):
            write_status("ready", "SCOZ уже запущен", state="ready")
            open_browser()
            return 0
        if port_is_occupied():
            raise RuntimeError(f"Порт {PORT} занят другим приложением или другой версией SCOZ.")
        child = start_wrapper()
        wait_until_ready(child)
        write_status("ready", "SCOZ готов к работе", state="ready")
        open_browser()
        return 0
    except Exception as exc:
        logging.exception("Startup failed")
        write_status("failed", str(exc), state="failed")
        print(f"Ошибка запуска SCOZ: {exc}\nПодробности: {LOG_FILE}", file=sys.stderr)
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
    raise SystemExit(main())
