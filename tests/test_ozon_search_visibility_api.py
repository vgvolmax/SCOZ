from backend.domain.search_visibility import (
    SearchVisibilityNoUsableRows,
    SearchVisibilityWrongReportType,
)
from backend.main import SEARCH_VISIBILITY_ERRORS, app


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
