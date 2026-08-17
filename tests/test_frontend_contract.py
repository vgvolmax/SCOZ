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
