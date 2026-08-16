from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Product:
    id: int
    is_owned: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ProductExternalIdentity:
    id: int
    product_id: int
    source: str
    identity_type: str
    identity_value: str
    source_account_scope: str
    created_at: datetime


class ProductNotFound(LookupError):
    pass


class ExternalIdentityConflict(ValueError):
    pass
