from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIST = ROOT / "frontend" / "dist"
APP_NAME = "SCOZ"
VERSION = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
HOST = "127.0.0.1"
PORT = 17842
LOCAL_URL = f"http://{HOST}:{PORT}"
