def test_repository_extensions_exist() -> None:
    from backend.persistence.repositories.lineage import LineageRepository
    from backend.persistence.repositories.products import ProductRepository
    assert hasattr(LineageRepository, "finish_ozon_products_import")
    assert hasattr(ProductRepository, "resolve_or_create_ozon_product")
