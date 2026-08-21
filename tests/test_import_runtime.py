import hashlib
import io
import os
from datetime import datetime, timezone

import pytest

from backend.application import import_runtime
from backend.application.import_runtime import (
    ARCHIVE_RE,
    MAX_UPLOAD_BYTES,
    StagedXlsxUpload,
    XlsxUploadTooLarge,
    XlsxUploadUnsupportedMediaType,
    publish_staged_archive,
    safe_original_basename,
    stage_xlsx_upload,
)


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [("dir/report.xlsx", "report.xlsx"), (r"C:\dir\report.xlsx", "report.xlsx"),
     (r"\\server\share\report.xlsx", "report.xlsx"), ("..", "upload.xlsx")],
)
def test_safe_original_basename_handles_hostile_path_styles(supplied, expected):
    assert safe_original_basename(supplied) == expected


def test_stage_accepts_xlsx_case_insensitively_and_hashes_original_bytes(monkeypatch, tmp_path):
    payload = b"synthetic workbook bytes"
    fsynced = []
    monkeypatch.setattr(os, "fsync", lambda fd: fsynced.append(fd))
    staged = stage_xlsx_upload(
        upload=io.BytesIO(payload), original_name=r"C:\reports\source.XLSX",
        data_dir=tmp_path,
    )
    assert staged.original_name == "source.XLSX"
    assert staged.staged_path.name.startswith(".upload-")
    assert staged.staged_path.suffix == ".part"
    assert staged.staged_path.read_bytes() == payload
    assert staged.sha256 == hashlib.sha256(payload).hexdigest()
    assert staged.byte_size == len(payload)
    assert fsynced


def test_stage_rejects_non_xlsx_without_creating_import_directory(tmp_path):
    with pytest.raises(XlsxUploadUnsupportedMediaType):
        stage_xlsx_upload(upload=io.BytesIO(b"x"), original_name="report.csv", data_dir=tmp_path)
    assert not (tmp_path / "imports").exists()


def test_stage_removes_partial_file_when_upload_is_too_large(tmp_path):
    with pytest.raises(XlsxUploadTooLarge):
        stage_xlsx_upload(
            upload=io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1)),
            original_name="report.xlsx", data_dir=tmp_path,
        )
    assert not list((tmp_path / "imports").glob(".upload-*.part"))


def test_stage_surfaces_filesystem_error(monkeypatch, tmp_path):
    monkeypatch.setattr(import_runtime.Path, "open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError, match="disk"):
        stage_xlsx_upload(upload=io.BytesIO(b"x"), original_name="report.xlsx", data_dir=tmp_path)


def test_publish_reserves_archive_and_moves_original_bytes(tmp_path):
    staged = stage_xlsx_upload(upload=io.BytesIO(b"original"), original_name="x.xlsx", data_dir=tmp_path)
    final, relative = publish_staged_archive(
        staged, data_dir=tmp_path, imported_at=datetime(2026, 8, 19, 1, 2, 3, 456789, timezone.utc),
    )
    assert ARCHIVE_RE.fullmatch(final.name)
    assert staged.sha256 in final.name
    assert relative == f"imports/{final.name}"
    assert final.read_bytes() == b"original"
    assert not staged.staged_path.exists()


def test_publish_collision_does_not_overwrite_existing_archive(tmp_path):
    staged = stage_xlsx_upload(upload=io.BytesIO(b"new"), original_name="x.xlsx", data_dir=tmp_path)
    instant = datetime(2026, 8, 19, 1, 2, 3, 456789, timezone.utc)
    name = f"{instant.strftime('%Y%m%dT%H%M%S%fZ')}-{staged.sha256}.xlsx"
    existing = tmp_path / "imports" / name
    existing.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        publish_staged_archive(staged, data_dir=tmp_path, imported_at=instant)
    assert existing.read_bytes() == b"existing"
    assert staged.staged_path.read_bytes() == b"new"


def test_publish_move_failure_removes_only_owned_reservation(monkeypatch, tmp_path):
    staged = stage_xlsx_upload(upload=io.BytesIO(b"new"), original_name="x.xlsx", data_dir=tmp_path)
    monkeypatch.setattr(import_runtime.Path, "replace", lambda self, target: (_ for _ in ()).throw(OSError("move")))
    with pytest.raises(OSError, match="move"):
        publish_staged_archive(staged, data_dir=tmp_path, imported_at=datetime.now(timezone.utc))
    assert staged.staged_path.read_bytes() == b"new"
    assert [path for path in (tmp_path / "imports").iterdir() if path != staged.staged_path] == []
