from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "SCOZ"
VERSION = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
HOST = "127.0.0.1"
PORT = 17842
FRONTEND_DIST = ROOT / "frontend" / "dist"
