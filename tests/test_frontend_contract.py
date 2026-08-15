import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_exact_package_versions():
    package = json.loads((ROOT / "frontend/package.json").read_text())
    versions = package["dependencies"] | package["devDependencies"]
    assert versions == {"react":"19.2.8", "react-dom":"19.2.8", "vite":"8.1.5", "@vitejs/plugin-react":"6.0.4", "typescript":"7.0.2", "@types/react":"19.2.18", "@types/react-dom":"19.2.4"}

def test_minimal_accessible_shell_contract():
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "['Товары', 'Данные', 'Настройки']" in app
    assert "useState<(typeof sections)[number]>('Товары')" in app
    assert 'aria-label="Основная навигация"' in app and "aria-current" in app
    forbidden = ["Диагностика", "Поиск", "Разгон", "Конкуренты", "React Router", "KPI"]
    assert all(word not in app for word in forbidden)

def test_design_tokens_and_real_build_are_present():
    css = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
    assert all(token in css for token in ["--color-primary", "--color-surface", "--space-4", ":focus-visible"])
    assert (ROOT / "frontend/package-lock.json").is_file()
    assert (ROOT / "frontend/dist/index.html").is_file()
    assert list((ROOT / "frontend/dist/assets").glob("*.js"))
