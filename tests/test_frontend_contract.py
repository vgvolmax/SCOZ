from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_committed_local_frontend_shell():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '/assets/css/app.css' in html and '/assets/js/app.js' in html
    assert "http://" not in html and "https://" not in html
    assert html.count('class="nav-item') == 3
    for label in ("Товары", "Данные", "Настройки"):
        assert html.count(f">{label}</button>") == 1
    assert 'aria-current="page"' in html
    assert 'data-section="products"' in html
    assert 'id="products-view"' in html and 'id="data-view"' in html
    assert 'id="ozon-products-file"' in html and 'aria-live="polite"' in html


def test_visual_and_accessibility_contract():
    css = (ROOT / "frontend/assets/css/app.css").read_text(encoding="utf-8")
    for token in ("--color-app-bg", "--color-surface", "--color-primary", "--radius-control", "--radius-card"):
        assert token in css
    assert ":focus-visible" in css
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'lang="ru"' in html and '<nav aria-label=' in html


def test_no_frontend_toolchain_or_future_ui():
    assert not (ROOT / "package.json").exists()
    assert not (ROOT / "frontend/src").exists()
    combined = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend").rglob("*.*"))
    for forbidden in ("ReactDOM", "Диагностика", "Разгон", "Конкуренты", "MPStats", "API credentials"):
        assert forbidden not in combined


def test_pr3_frontend_state_contract():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert "Данные загружены. Выберите свои товары." not in html
    for text in (
        "Загрузка товаров…",
        "Для анализа загрузите данные Ozon и выберите собственный товар.",
        "Данные загружены. Выберите свои товары.",
        "Товары готовы к анализу.",
        "PARTIAL_SUCCESS",
        "rows_accepted",
        "rows_skipped",
        "row_errors",
        "Не удалось изменить принадлежность товара.",
        "box.checked=previous",
    ):
        assert text in html + js
    assert 'accept=".xlsx"' in html
    assert 'id="selected-file-name"' in html
    assert 'aria-live="polite"' in html


def test_pr4_search_visibility_import_and_history_contract():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert html.count('type="file" accept=".xlsx"') == 4
    for value in (
        "Отчёт «Товары на Ozon»", "Поисковая видимость Ozon",
        'id="ozon-search-visibility-file"', 'id="search-visibility-file-name"',
        'id="search-visibility-submit"', 'id="search-visibility-status"',
    ):
        assert value in html
    for value in (
        'item.report_type==="OZON_PRODUCTS"',
        'item.report_type==="OZON_SEARCH_VISIBILITY"',
        "query_text", "cluster_name", "observed_at", "declared_rows",
        "rows_accepted", "rows_skipped", "new_observations",
        "duplicate_observations", "corrected_revisions", "row_errors",
        "PARTIAL_SUCCESS", "loadImports()", "/api/imports/ozon-search-visibility",
    ):
        assert value in js


def test_pr4_does_not_leak_future_analytics_ui():
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "frontend").rglob("*.*")
    ).casefold()
    for forbidden in (
        "heatmap", "benchmark", "query opportunity", "тепловая карта",
        "анализ запросов", "карточки конкурентов", "оценка кластера",
    ):
        assert forbidden not in combined


def test_pr5_query_imports_and_global_readiness_contract():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    for hook in (
        "ozon-seller-queries-file", "seller-queries-file-name",
        "seller-queries-submit", "seller-queries-status", "seller-queries-readiness",
        "ozon-query-metrics-file", "query-metrics-file-name",
        "query-metrics-submit", "query-metrics-status", "query-metrics-readiness",
    ):
        assert f'id="{hook}"' in html
    for value in (
        "submitSellerQueriesImport", "submitQueryMetricsImport",
        "/api/imports/ozon-seller-queries", "/api/imports/ozon-query-metrics",
        'item.report_type==="OZON_OWN_PRODUCT_QUERIES"',
        'item.report_type==="OZON_QUERY_METRICS"',
        "report_product_ozon_id", "period_start", "period_end", "sort_context",
        "data.source_availability.own_product_queries",
        "data.source_availability.query_metrics",
        "textContent", "PARTIAL_SUCCESS", "loadProducts()", "loadImports()",
    ):
        assert value in js
    assert "data.items.some" not in js
