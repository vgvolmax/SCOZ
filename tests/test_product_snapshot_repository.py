def test_product_snapshot_repository_module_imports() -> None:
    from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository
    assert ProductSnapshotRepository
