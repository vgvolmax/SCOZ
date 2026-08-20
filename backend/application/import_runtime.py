import re
import threading
import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ROW_ERRORS = 50
IMPORT_LOCK = threading.Lock()
ARCHIVE_RE = re.compile(r"\d{8}T\d{12}Z-[0-9a-f]{64}\.xlsx")


@dataclass(frozen=True)
class StagedXlsxUpload:
    original_name: str
    staged_path: Path
    sha256: str
    byte_size: int


class XlsxUploadUnsupportedMediaType(ValueError):
    pass


class XlsxUploadTooLarge(ValueError):
    pass


def safe_original_basename(original_name: str) -> str:
    name = PureWindowsPath(PurePosixPath(original_name).name).name
    return "upload.xlsx" if name in ("", ".", "..") else name


def stage_xlsx_upload(
    *, upload: BinaryIO, original_name: str, data_dir: Path,
) -> StagedXlsxUpload:
    original = safe_original_basename(original_name)
    if not original.lower().endswith(".xlsx"):
        raise XlsxUploadUnsupportedMediaType()
    imports_dir = data_dir / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    staged_path = imports_dir / f".upload-{uuid.uuid4()}.part"
    digest = hashlib.sha256()
    size = 0
    try:
        with staged_path.open("xb") as target:
            while chunk := upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise XlsxUploadTooLarge()
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        try:
            staged_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return StagedXlsxUpload(original, staged_path, digest.hexdigest(), size)


def publish_staged_archive(
    staged: StagedXlsxUpload, *, data_dir: Path, imported_at: datetime,
) -> tuple[Path, str]:
    filename = (
        f"{imported_at.strftime('%Y%m%dT%H%M%S%fZ')}-{staged.sha256}.xlsx"
    )
    final_path = data_dir / "imports" / filename
    owned = False
    try:
        with final_path.open("xb"):
            pass
        owned = True
        staged.staged_path.replace(final_path)
    except Exception:
        if owned:
            try:
                final_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return final_path, PurePosixPath("imports", filename).as_posix()
