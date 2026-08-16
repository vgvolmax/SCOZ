from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
FRONTEND_DIR = ROOT_DIR / "frontend"
FRONTEND_INDEX = FRONTEND_DIR / "index.html"
APP_NAME = "SCOZ"
VERSION = (ROOT_DIR / "VERSION.txt").read_text(encoding="utf-8").strip()
HOST = "127.0.0.1"
PORT = 17842
BASE_URL = f"http://{HOST}:{PORT}"
