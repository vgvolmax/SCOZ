from pathlib import Path


def test_seller_queries_route_is_thin_and_registered():
    source = (Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/imports/ozon-seller-queries")' in source
    assert "import_ozon_seller_queries_xlsx" in source
    assert "SellerQueriesUnsupportedUploadMediaType" in source
