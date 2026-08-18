import inspect

import pytest

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
from backend.main import SEARCH_VISIBILITY_ERRORS, app, post_ozon_search_visibility_import


def test_search_visibility_route_and_frozen_error_mapping():
    paths = {route.path for route in app.routes}
    assert "/api/imports/ozon-search-visibility" in paths
    assert SEARCH_VISIBILITY_ERRORS[SearchVisibilityWrongReportType] == (
        422, "WRONG_REPORT_TYPE",
        "Выберите XLSX-выгрузку Ozon с факторами поисковой выдачи.",
    )
    assert SEARCH_VISIBILITY_ERRORS[SearchVisibilityNoUsableRows] == (
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
    assert SEARCH_VISIBILITY_ERRORS[error] == triple


def test_route_remains_thin_closes_upload_and_does_not_expose_internal_details():
    source = inspect.getsource(post_ozon_search_visibility_import)
    assert source.count("import_ozon_search_visibility_xlsx(") == 1
    assert "finally:" in source and "await file.close()" in source
    for forbidden in ("traceback", "cell.value", "execute(", "stored_relpath"):
        assert forbidden not in source
