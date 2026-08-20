from pathlib import Path


def test_query_metrics_route_and_global_availability_are_registered():
    source = (Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/imports/ozon-query-metrics")' in source
    assert "import_ozon_query_metrics_xlsx" in source
    assert '"source_availability":repo.get_pr5_source_availability()' in source
