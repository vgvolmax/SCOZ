import inspect

from fastapi.testclient import TestClient
import pytest

import backend.application.ozon_search_visibility_import as service
from backend.application.import_runtime import IMPORT_LOCK
import backend.main as main
from backend.domain.lineage import ImportStatus
from backend.domain.search_visibility import (
    SearchVisibilityConcurrentImportConflict,
    SearchVisibilityConflictingObservationRows,
    SearchVisibilityImportPersistenceError,
    SearchVisibilityIncompatibleReportSchema,
    SearchVisibilityInvalidObservedAt,
    SearchVisibilityInvalidSearchContext,
    SearchVisibilityNoUsableRows,
    SearchVisibilityUnsupportedUploadMediaType,
    SearchVisibilityUnsupportedWorkbook,
    SearchVisibilityUploadTooLarge,
    SearchVisibilityWrongReportType,
)
from backend.persistence.connection import transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from tests.xlsx_factory import (
    OZON_PRODUCTS_HEADERS,
    OZON_SEARCH_VISIBILITY_HEADERS,
    _default_row,
    build_ozon_products_workbook,
    build_ozon_search_visibility_workbook,
)


XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(db_path))
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    return TestClient(main.app)


def _post(client, payload, *, filename="visibility.xlsx"):
    return client.post(
        "/api/imports/ozon-search-visibility",
        files={"file": (filename, payload, XLSX_MEDIA)},
    )


def _row(product_id=100000001, **changes):
    row = dict(zip(OZON_SEARCH_VISIBILITY_HEADERS, (
        "1", product_id, "Синтетический товар", "Синтетический продавец", "0,526",
        "Продвигается", "10,50 ₽", "Автостратегия", "5%", "99,1",
        "4,8 (1 234 шт.)", "1 999 ₽", "42,2", "Да", "1-2 дня", "10,0%",
    ), strict=True))
    row.update(changes)
    return row


def _counts(db_path):
    with transaction(db_path) as conn:
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            "import_batches", "source_artifacts", "search_queries", "clusters", "products",
            "search_visibility_snapshots", "product_snapshots",
        )}


def _assert_sanitized(response, *secrets):
    text = response.text
    for forbidden in ("traceback", "Traceback", "C:\\", "/tmp/", ".part", *secrets):
        assert forbidden not in text


def test_search_visibility_route_and_frozen_error_mapping():
    paths = {route.path for route in main.app.routes}
    assert "/api/imports/ozon-search-visibility" in paths
    assert main.SEARCH_VISIBILITY_ERRORS[SearchVisibilityWrongReportType] == (
        422, "WRONG_REPORT_TYPE",
        "Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи.",
    )
    assert main.SEARCH_VISIBILITY_ERRORS[SearchVisibilityNoUsableRows] == (
        422, "NO_USABLE_ROWS", "В отчёте нет пригодных строк товаров.",
    )


@pytest.mark.parametrize(("error", "triple"), [
    (SearchVisibilityUnsupportedWorkbook, (422, "UNSUPPORTED_WORKBOOK", "Не удалось прочитать XLSX-файл.")),
    (SearchVisibilityWrongReportType, (422, "WRONG_REPORT_TYPE", "Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи.")),
    (SearchVisibilityIncompatibleReportSchema, (422, "INCOMPATIBLE_REPORT_SCHEMA", "Версия или структура отчёта не поддерживается.")),
    (SearchVisibilityInvalidObservedAt, (422, "INVALID_OBSERVED_AT", "Не удалось прочитать дату или время наблюдения.")),
    (SearchVisibilityInvalidSearchContext, (422, "INVALID_SEARCH_CONTEXT", "Не удалось прочитать поисковый запрос или кластер.")),
    (SearchVisibilityConflictingObservationRows, (422, "CONFLICTING_OBSERVATION_ROWS", "В отчёте есть противоречивые строки одного товара.")),
    (SearchVisibilityNoUsableRows, (422, "NO_USABLE_ROWS", "В отчёте нет пригодных строк товаров.")),
    (SearchVisibilityConcurrentImportConflict, (409, "CONCURRENT_IMPORT_CONFLICT", "Другой импорт уже выполняется. Дождитесь его завершения.")),
    (SearchVisibilityUploadTooLarge, (413, "UPLOAD_TOO_LARGE", "Размер файла превышает 25 МиБ.")),
    (SearchVisibilityUnsupportedUploadMediaType, (415, "UNSUPPORTED_UPLOAD_MEDIA_TYPE", "Выберите XLSX-файл.")),
    (SearchVisibilityImportPersistenceError, (500, "IMPORT_PERSISTENCE_ERROR", "Не удалось сохранить импорт. Данные не изменены.")),
])
def test_complete_frozen_http_error_matrix(error, triple):
    assert main.SEARCH_VISIBILITY_ERRORS[error] == triple


def test_http_valid_import_returns_transport_contract_and_persists_lineage(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_search_visibility_workbook())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "import_batch_id", "report_type", "status", "observed_at", "query_text",
        "cluster_name", "declared_rows", "rows_seen", "rows_accepted", "rows_skipped",
        "duplicate_observations", "new_observations", "corrected_revisions", "warnings_count",
        "row_errors_total", "row_errors", "row_errors_truncated", "source_artifact", "imported_at",
    }
    assert body["report_type"] == "OZON_SEARCH_VISIBILITY"
    assert body["status"] == "SUCCESS"
    assert body["query_text"] == "тестовый запрос"
    assert body["cluster_name"] == "г. Тестоград, Россия"
    assert body["observed_at"] == "2026-08-17T03:55:00+00:00"
    assert [body[key] for key in ("declared_rows", "rows_seen", "rows_accepted")] == [1, 1, 1]
    assert [body[key] for key in ("rows_skipped", "new_observations", "duplicate_observations", "corrected_revisions")] == [0, 1, 0, 0]
    assert body["source_artifact"]["stored_relpath"]
    counts = _counts(tmp_path / "scoz.db")
    assert {key: counts[key] for key in ("search_queries", "clusters", "products", "search_visibility_snapshots", "source_artifacts")} == {key: 1 for key in ("search_queries", "clusters", "products", "search_visibility_snapshots", "source_artifacts")}
    assert (tmp_path / body["source_artifact"]["stored_relpath"]).is_file()


def test_http_partial_success_and_row_error_truncation(monkeypatch, tmp_path):
    rows = (_row(),) + tuple(_row(index + 2, **{"ID товара": True}) for index in range(52))
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_search_visibility_workbook(rows=rows))
    body = response.json()
    assert response.status_code == 200 and response.status_code != 207
    assert body["status"] == "PARTIAL_SUCCESS"
    assert (body["rows_accepted"], body["rows_skipped"], body["row_errors_total"]) == (1, 52, 52)
    assert len(body["row_errors"]) == 50 and body["row_errors_truncated"] is True
    assert [error["row"] for error in body["row_errors"]] == list(range(11, 61))
    counts = _counts(tmp_path / "scoz.db")
    assert counts["products"] == counts["search_visibility_snapshots"] == 1


@pytest.mark.parametrize(("payload", "expected_code", "expected_message"), [
    (b"not-xlsx uploaded-secret", "UNSUPPORTED_WORKBOOK", "Не удалось прочитать XLSX-файл."),
    (build_ozon_products_workbook(), "WRONG_REPORT_TYPE", "Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи."),
    (build_ozon_search_visibility_workbook(headers=("wrong", *OZON_SEARCH_VISIBILITY_HEADERS[1:])), "INCOMPATIBLE_REPORT_SCHEMA", "Версия или структура отчёта не поддерживается."),
    (build_ozon_search_visibility_workbook(date="not-a-date"), "INVALID_OBSERVED_AT", "Не удалось прочитать дату или время наблюдения."),
    (build_ozon_search_visibility_workbook(query=" "), "INVALID_SEARCH_CONTEXT", "Не удалось прочитать поисковый запрос или кластер."),
])
def test_http_fatal_parser_errors_are_exact_sanitized_and_domain_atomic(
    monkeypatch, tmp_path, payload, expected_code, expected_message,
):
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, payload)
    assert response.status_code == 422
    assert response.json()["error"] == {"code": expected_code, "message": expected_message}
    assert response.json()["result"]["status"] == "FAILED"
    _assert_sanitized(response, "uploaded-secret")
    counts = _counts(tmp_path / "scoz.db")
    assert all(counts[key] == 0 for key in ("search_queries", "clusters", "products", "search_visibility_snapshots"))


def test_http_conflict_and_zero_usable_are_failed_and_domain_atomic(monkeypatch, tmp_path):
    conflict_rows = (_row(), _row(**{"Позиция": "2"}))
    invalid_rows = (_row(**{"ID товара": True}), _row(2, **{"Позиция": "bad"}))
    with _client(monkeypatch, tmp_path) as client:
        conflict = _post(client, build_ozon_search_visibility_workbook(rows=conflict_rows))
        zero = _post(client, build_ozon_search_visibility_workbook(rows=invalid_rows))
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "CONFLICTING_OBSERVATION_ROWS"
    assert zero.status_code == 422
    assert zero.json()["error"]["code"] == "NO_USABLE_ROWS"
    assert zero.json()["result"]["status"] == "FAILED"
    assert zero.json()["result"]["row_errors_total"] == 2
    assert len(zero.json()["result"]["row_errors"]) == 2
    counts = _counts(tmp_path / "scoz.db")
    assert all(counts[key] == 0 for key in ("search_queries", "clusters", "products", "search_visibility_snapshots"))


def test_http_transport_rejections_have_no_side_effects(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        wrong_type = client.post("/api/imports/ozon-search-visibility", content=b"raw")
        wrong_extension = _post(client, b"x", filename="report.xls")
        missing = client.post(
            "/api/imports/ozon-search-visibility",
            content=b"--empty--\r\n--empty----\r\n",
            headers={"content-type": "multipart/form-data; boundary=empty"},
        )
        wrong_field = client.post("/api/imports/ozon-search-visibility", files={"wrong": ("x.xlsx", b"x")})
    assert wrong_type.status_code == wrong_extension.status_code == 415
    for response in (wrong_type, wrong_extension):
        assert response.json() == {"error": {"code": "UNSUPPORTED_UPLOAD_MEDIA_TYPE", "message": "Выберите XLSX-файл."}, "result": None}
    assert missing.status_code == wrong_field.status_code == 422
    assert _counts(tmp_path / "scoz.db")["import_batches"] == 0


def test_http_shared_lock_and_upload_limit_have_no_side_effects(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        IMPORT_LOCK.acquire()
        try:
            locked = _post(client, build_ozon_search_visibility_workbook())
        finally:
            IMPORT_LOCK.release()
        monkeypatch.setattr(service, "MAX_UPLOAD_BYTES", 4)
        oversized = _post(client, b"12345")
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "CONCURRENT_IMPORT_CONFLICT"
    assert oversized.status_code == 413 and oversized.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert locked.json()["result"] is oversized.json()["result"] is None
    assert _counts(tmp_path / "scoz.db")["import_batches"] == 0


def test_http_persistence_failure_is_compensated_and_sanitized(monkeypatch, tmp_path):
    monkeypatch.setattr(
        SearchDimensionRepository, "resolve_cluster",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected-secret")),
    )
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_search_visibility_workbook())
    assert response.status_code == 500
    assert response.json()["error"] == {"code": "IMPORT_PERSISTENCE_ERROR", "message": "Не удалось сохранить импорт. Данные не изменены."}
    assert response.json()["result"]["status"] == "FAILED"
    assert response.json()["result"]["source_artifact"]["stored_relpath"] is None
    _assert_sanitized(response, "injected-secret")
    counts = _counts(tmp_path / "scoz.db")
    assert all(counts[key] == 0 for key in ("search_queries", "clusters", "products", "search_visibility_snapshots"))
    assert not list((tmp_path / "imports").glob("*.xlsx"))


def test_http_unified_history_pagination_and_nullable_context(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        assert client.post("/api/imports/ozon-products", files={"file": ("products.xlsx", build_ozon_products_workbook(), XLSX_MEDIA)}).status_code == 200
        assert _post(client, build_ozon_search_visibility_workbook()).status_code == 200
        history = client.get("/api/imports").json()
        page = client.get("/api/imports?limit=1&offset=1").json()
    assert history["total"] == page["total"] == 2
    assert [item["report_type"] for item in history["items"]] == ["OZON_SEARCH_VISIBILITY", "OZON_PRODUCTS"]
    visibility, products = history["items"]
    assert (visibility["observed_at"], visibility["query_text"], visibility["cluster_name"], visibility["declared_rows"]) == ("2026-08-17T03:55:00+00:00", "тестовый запрос", "г. Тестоград, Россия", 1)
    assert visibility["report_generated_on"] is visibility["report_window_days"] is None
    assert products["report_generated_on"] == "2026-08-16" and products["report_window_days"] == 7
    assert products["observed_at"] is products["query_text"] is products["cluster_name"] is products["declared_rows"] is None
    assert len(page["items"]) == 1 and page["items"][0]["report_type"] == "OZON_PRODUCTS"


def test_visibility_identity_does_not_pollute_product_api_then_is_reused_by_pr3(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        assert _post(client, build_ozon_search_visibility_workbook()).status_code == 200
        assert client.get("/api/products").json()["total"] == 0
        before = _counts(tmp_path / "scoz.db")
        product_row = _default_row("Синтетическая категория")
        assert client.post("/api/imports/ozon-products", files={"file": ("products.xlsx", build_ozon_products_workbook(rows=[product_row]), XLSX_MEDIA)}).status_code == 200
        catalog = client.get("/api/products").json()
    after = _counts(tmp_path / "scoz.db")
    assert before["products"] == after["products"] == 1
    assert catalog["total"] == 1 and catalog["items"][0]["ozon_product_id"] == "100000001"


def test_testclient_lifespan_recovers_both_import_kinds_and_preserves_archives(monkeypatch, tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(db_path))
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    imports = tmp_path / "imports"
    imports.mkdir()
    staging = imports / ".upload-interrupted.part"
    staging.write_bytes(b"garbage")
    archive = imports / ("20260817T035500000000Z-" + "a" * 64 + ".xlsx")
    archive.write_bytes(b"archive")
    with transaction(db_path) as conn:
        lineage = LineageRepository(conn)
        products = lineage.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
        visibility = lineage.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
        lineage.add_source_artifact(products.id, artifact_kind="ozon_products_xlsx", original_name="x.xlsx", content_sha256="a" * 64, byte_size=7, stored_relpath=f"imports/{archive.name}")
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code == 200
        with transaction(db_path) as conn:
            repo = LineageRepository(conn)
            assert repo.get_import_batch(products.id).status is ImportStatus.FAILED
            assert repo.get_import_batch(visibility.id).status is ImportStatus.FAILED
    assert not staging.exists() and archive.exists()


def test_route_remains_thin_closes_upload_and_does_not_expose_internal_details():
    source = inspect.getsource(main.post_ozon_search_visibility_import)
    assert source.count("import_ozon_search_visibility_xlsx(") == 1
    assert "finally:" in source and "await file.close()" in source
    for forbidden in ("traceback", "cell.value", "execute(", "stored_relpath"):
        assert forbidden not in source
