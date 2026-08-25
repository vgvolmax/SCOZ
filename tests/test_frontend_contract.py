from pathlib import Path

import pytest


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
    for forbidden in ("ReactDOM", "Диагностика", "Разгон", "Конкуренты", "API credentials"):
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
        "heatmap", "query opportunity", "тепловая карта",
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


def test_ci_runs_both_js_checks_and_keystore_contract_without_npm():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for command in (
        "python -m pytest -q",
        "node --check frontend/assets/js/app.js",
        "node --check frontend/assets/js/keystore.js",
        "node tests/keystore_contract.mjs",
    ):
        assert command in workflow
    assert "npm " not in workflow


def test_candidate_renderer_uses_frozen_transport_field_names():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    for field in ("source_title", "contextual_price_rub", "matched_relevant_query_count", "representative_observed_at"):
        assert f"item.{field}" in js


def test_only_owned_products_expose_competitor_entry():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert "Выбрать конкурентов" in js
    assert "item.is_owned" in js
    assert "openCompetitorWorkspace(product)" in js


def test_competitor_workspace_has_active_context_and_relevance_states():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    for hook in ("competitors-workspace", "competitors-context", "relevant-queries-panel",
                 "relevant-queries-status", "relevant-queries-table", "relevant-queries-save"):
        assert f'id="{hook}"' in html
    for value in ("loadRelevantQueries(productId)", "renderRelevantQueries(selection)",
                  "saveRelevantQueries(productId)", "NO_OWN_QUERY_DATA", "Нет в свежем периоде",
                  "Искали", "Видели", "Средняя позиция", "Заказано", "Выручка"):
        assert value in html + js


def test_candidate_and_selected_panels_have_exact_controls():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    for hook in ("benchmark-candidates-panel", "benchmark-candidates-status",
                 "benchmark-candidates-list", "benchmark-candidates-prev", "benchmark-candidates-next",
                 "benchmark-selected-panel", "benchmark-selected-list", "manual-ozon-product-id",
                 "manual-candidate-add", "benchmark-save", "benchmark-save-status"):
        assert f'id="{hook}"' in html
    for function in ("loadBenchmark(productId)", "loadCandidates(productId, offset)",
                     "renderCandidates(page)", "addManualCandidate(productId)",
                     "renderSelectedBenchmark()", "saveBenchmark(productId)"):
        assert function in js
    assert 'placeholder="123456789"' in html


def test_stale_no_evidence_error_and_revision_feedback_are_renderable():
    combined = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend").rglob("*.*"))
    for value in ("NO_CANDIDATE_EVIDENCE", "Нет в свежем периоде", "Ещё не сохранено",
                  "Состав не изменился — revision", "Сохраняем…", "Фото недоступно"):
        assert value in combined


def test_frontend_uses_committed_classic_assets_without_framework():
    combined = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend").rglob("*.*"))
    assert "const competitorState =" in combined and "selectedProductIds: new Set()" in combined
    assert "candidateOffset: 0" in combined
    for forbidden in ("React", "Vue", "localStorage", "sessionStorage", "score", "Query Opportunity"):
        assert forbidden not in combined


def test_settings_source_controls_and_memory_only_state():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    for hook in ("mpstats-token", "mpstats-probe-sku", "mpstats-test", "mpstats-status",
                 "mpstats-save-password", "mpstats-save-password-confirm", "mpstats-save-keystore",
                 "mpstats-keystore-file", "mpstats-open-password", "mpstats-open-keystore", "mpstats-lock"):
        assert f'id="{hook}"' in html
    assert "let credentialState = null;" in js
    for function in ("testMpstatsSource()", "loadMpstatsPhotos()", "saveMpstatsKeystore()",
                     "openMpstatsKeystore()", "lockCredentials()"):
        assert function in js


def test_credentials_never_use_browser_persistence_or_urls():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "document.cookie",
                      "auth-token", "?token=", "/api/credentials", "/api/keystore"):
        assert forbidden not in js
    assert 'body:JSON.stringify({token:' in js
    assert 'type="password"' in (ROOT / "frontend/index.html").read_text(encoding="utf-8")


def test_unlock_failure_preserves_old_state_and_clears_password():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert "const previousState=credentialState" in js
    assert "credentialState=previousState" in js
    assert 'openPassword.value=""' in js


def test_save_requires_matching_confirmation():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert "password!==confirmation" in js
    assert "ScozKeystore.encryptMpstatsCredentials" in js
    assert "ScozKeystore.downloadEnvelope" in js


def test_lock_clears_credentials_inputs_status_and_preview_urls():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert "credentialState=null" in js
    for value in ("mpstats-token", "mpstats-save-password", "mpstats-save-password-confirm",
                  "mpstats-keystore-file", "mpstats-open-password", "mpstats-status"):
        assert value in js
    assert 'item.photo_url=null' in js and 'item.photo_status="NOT_REQUESTED"' in js


def test_windows_smoke_db_python_snippets_are_transported_over_stdin():
    smoke = Path("tests/windows_smoke.ps1").read_text(encoding="utf-8")

    assert "$schemaCode = @'" in smoke
    assert "$seed = @'" in smoke
    assert 'c.execute(\\"SELECT' not in smoke
    assert 'c.execute(\\"INSERT' not in smoke
    assert "$Code | & $python - $db @Arguments" in smoke
    assert "& $python -c $Code $db @Arguments" not in smoke


def test_competitor_state_behavioral_contract():
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    result = subprocess.run(
        [node, "tests/competitor_state_contract.mjs"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "competitor state contract: PASS" in result.stdout


def test_core_benchmark_fetch_is_race_safe_and_refetched_after_save():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    competitor_helper = (ROOT / "frontend/assets/js/competitor_state.js").read_text(encoding="utf-8")

    for value in (
        "coreBenchmark: null", "coreBenchmarkRequestId: 0",
        "resetCoreBenchmarkState()", "openCoreBenchmark()",
        "loadCoreBenchmark(productId, requestId)",
        "/core-benchmark", "competitorState.activeProduct?.id!==productId",
        "requestId!==competitorState.coreBenchmarkRequestId",
    ):
        assert value in js
    assert "resetCoreBenchmarkState();" in js
    assert "await openCoreBenchmark()" in js
    assert "coreBenchmark" not in competitor_helper


def test_core_benchmark_grouped_summary_contract():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/assets/css/app.css").read_text(encoding="utf-8")
    for hook in ("core-benchmark-open", "core-benchmark-panel", "core-benchmark-status",
                 "core-benchmark-context", "core-benchmark-groups"):
        assert f'id="{hook}"' in html
    assert html.index('id="core-benchmark-open"') > html.index('class="benchmark-layout"')
    for value in ("renderCoreBenchmark(result)", "formatBenchmarkValue(value, unit",
                  "coreBenchmarkObservationPhrase(observation)", 'Intl.NumberFormat("ru-RU"',
                  "Ниже медианы", "На уровне медианы", "Выше медианы",
                  "₽/заказанную ед.", "п.п.", "metric.label", "is_estimate"):
        assert value in js
    for heading in ("Result", "Traffic", "Conversion", "Offer", "Advertising"):
        assert heading in js
    assert ".core-benchmark-groups" in css and "--color-" in css
    forbidden = ("ниже benchmark", "внутри benchmark", "выше benchmark", "GOOD", "BAD", "WIN")
    assert not any(value in html + js for value in forbidden)


def test_benchmark_detail_renders_sample_values_without_transient_candidate_lookup():
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/assets/css/app.css").read_text(encoding="utf-8")
    for value in (
        "renderCoreBenchmarkMetric(metric, benchmark)",
        "toggleCoreBenchmarkMetricDetail(button)",
        'aria-expanded="false"', "aria-controls=", "metric.sample_values",
        "Ozon SKU ${item.ozon_product_id}", "Недоступно для текущей выборки",
        "Нет совместимого наблюдения", "Нет исходного значения показателя",
        "Нельзя вычислить производный показатель", "benchmark_revision_number",
        "benchmark_member_count", "metric.p25", "metric.p75",
    ):
        assert value in js
    renderer = js[js.index("function renderCoreBenchmarkMetric"):js.index("function renderCoreBenchmark(")]
    for forbidden in ("metadataByProductId", "candidatePage", "benchmark-selected-list", "MPStats"):
        assert forbidden not in renderer
    assert ".core-benchmark-detail" in css


def test_core_benchmark_readiness_partial_and_failure_states():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/assets/js/app.js").read_text(encoding="utf-8")
    assert 'id="core-benchmark-retry"' in html
    for value in (
        "renderCoreBenchmarkState(state, result)", "LOADING", "NO_BENCHMARK",
        "NO_OWN_SOURCE_DATA", "NO_COMPATIBLE_SAMPLE", "INSUFFICIENT_SAMPLE", "READY", "FAILED",
        "Рассчитываем benchmark…", "Сначала сохраните benchmark-группу.",
        "Нет товарных данных Ozon для собственного SKU. Импортируйте отчёт «Товары на Ozon».",
        "У конкурентов нет данных за тот же контекст отчёта.",
        "Совместимых конкурентов недостаточно для сравнения.",
        "Часть показателей недоступна", "Не удалось загрузить benchmark. Повторите попытку.",
        'document.querySelector("#core-benchmark-retry").addEventListener("click",openCoreBenchmark)',
    ):
        assert value in html + js
    assert 'value===null||value===undefined' in js
