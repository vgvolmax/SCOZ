def test_pr3_routes_are_declared_in_source() -> None:
    source = open("backend/main.py", encoding="utf-8").read()
    assert '"/api/imports/ozon-products"' in source
    assert '"/api/products/{product_id}/ownership"' in source
