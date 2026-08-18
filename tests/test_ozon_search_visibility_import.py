from io import BytesIO

import pytest

from backend.application.ozon_search_visibility_import import import_ozon_search_visibility_xlsx
from backend.domain.product_snapshot import SnapshotWriteKind
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from tests.xlsx_factory import build_ozon_search_visibility_workbook


def test_import_is_archived_and_same_payload_is_duplicate(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)
    workbook = build_ozon_search_visibility_workbook()
    first = import_ozon_search_visibility_xlsx(
        upload=BytesIO(workbook), original_name="../report.xlsx", db_path=db, data_dir=data
    )
    second = import_ozon_search_visibility_xlsx(
        upload=BytesIO(workbook), original_name="report.xlsx", db_path=db, data_dir=data
    )
    assert first.new_observations == 1
    assert second.duplicate_observations == 1
    assert first.source_artifact.original_name == "report.xlsx"
    assert (data / first.source_artifact.stored_relpath).is_file()
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_visibility_snapshots").fetchone()[0] == 1
        assert conn.execute("SELECT is_owned FROM products").fetchone()[0] == 0


def test_visibility_only_product_does_not_enter_catalog(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    import_ozon_search_visibility_xlsx(
        upload=BytesIO(build_ozon_search_visibility_workbook()), original_name="report.xlsx",
        db_path=db, data_dir=tmp_path / "data",
    )
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0] == 0
