from dataclasses import fields
from decimal import Decimal

from backend.domain.product_snapshot import (
    OzonProductsImportSummary, ProductSnapshot, canonical_decimal,
)


def test_frozen_domain_field_counts() -> None:
    assert len(fields(ProductSnapshot)) == 45
    assert len(fields(OzonProductsImportSummary)) == 17


def test_canonical_decimal() -> None:
    assert canonical_decimal(Decimal("1.2300")) == "1.23"
    assert canonical_decimal(Decimal("-0.00")) == "0"
