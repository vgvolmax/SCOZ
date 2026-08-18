import re
import threading
from pathlib import PurePosixPath, PureWindowsPath


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ROW_ERRORS = 50
IMPORT_LOCK = threading.Lock()
ARCHIVE_RE = re.compile(r"\d{8}T\d{12}Z-[0-9a-f]{64}\.xlsx")


def safe_original_basename(original_name: str) -> str:
    name = PureWindowsPath(PurePosixPath(original_name).name).name
    return "upload.xlsx" if name in ("", ".", "..") else name
