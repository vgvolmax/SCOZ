from datetime import datetime, timezone
from io import BytesIO

from backend.application.ozon_search_visibility_import import import_ozon_search_visibility_xlsx
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from tests.xlsx_factory import OZON_SEARCH_VISIBILITY_HEADERS, build_ozon_search_visibility_workbook


def test_changed_position_appends_revision_and_preserves_history(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    base = build_ozon_search_visibility_workbook()
    import_ozon_search_visibility_xlsx(upload=BytesIO(base), original_name="a.xlsx", db_path=db, data_dir=tmp_path / "data")
    row = dict(zip(OZON_SEARCH_VISIBILITY_HEADERS, (
        "2", 100000001, "Синтетический товар", "Синтетический продавец", "0,526",
        "Продвигается", "10,50 ₽", "Автостратегия", "5%", "99,1",
        "4,8 (1 234 шт.)", "1 999 ₽", "42,2", "Да", "1-2 дня", "10,0%",
    ), strict=True))
    changed = build_ozon_search_visibility_workbook(rows=(row,))
    result = import_ozon_search_visibility_xlsx(upload=BytesIO(changed), original_name="b.xlsx", db_path=db, data_dir=tmp_path / "data")
    assert result.corrected_revisions == 1
    with connect(db) as conn:
        rows = conn.execute("SELECT revision,position,supersedes_snapshot_id FROM search_visibility_snapshots ORDER BY revision").fetchall()
    assert [(item[0], item[1]) for item in rows] == [(1, 1), (2, 2)]
    assert rows[1][2] is not None
