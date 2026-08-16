import sqlite3

from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.domain.product import (
    ExternalIdentityConflict,
    Product,
    ProductExternalIdentity,
    ProductNotFound,
)


def _product_from_row(row: sqlite3.Row) -> Product:
    return Product(
        id=row["id"],
        is_owned=bool(row["is_owned"]),
        created_at=datetime_from_db(row["created_at"]),
        updated_at=datetime_from_db(row["updated_at"]),
    )


def _identity_from_row(row: sqlite3.Row) -> ProductExternalIdentity:
    return ProductExternalIdentity(
        id=row["id"],
        product_id=row["product_id"],
        source=row["source"],
        identity_type=row["identity_type"],
        identity_value=row["identity_value"],
        source_account_scope=row["source_account_scope"],
        created_at=datetime_from_db(row["created_at"]),
    )


class ProductRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_product(self, *, is_owned: bool) -> Product:
        timestamp = datetime_to_db(utc_now())
        cursor = self._conn.execute(
            "INSERT INTO products (is_owned, created_at, updated_at) VALUES (?, ?, ?)",
            (int(is_owned), timestamp, timestamp),
        )
        product = self.get_product(cursor.lastrowid)
        assert product is not None
        return product

    def get_product(self, product_id: int) -> Product | None:
        row = self._conn.execute(
            "SELECT id, is_owned, created_at, updated_at FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        return None if row is None else _product_from_row(row)

    def set_owned(self, product_id: int, is_owned: bool) -> Product:
        cursor = self._conn.execute(
            "UPDATE products SET is_owned = ?, updated_at = ? WHERE id = ?",
            (int(is_owned), datetime_to_db(utc_now()), product_id),
        )
        if cursor.rowcount == 0:
            raise ProductNotFound(product_id)
        product = self.get_product(product_id)
        assert product is not None
        return product

    def add_external_identity(
        self,
        product_id: int,
        *,
        source: str,
        identity_type: str,
        identity_value: str,
        source_account_scope: str = "",
    ) -> ProductExternalIdentity:
        if self.get_product(product_id) is None:
            raise ProductNotFound(product_id)
        values = (source, identity_type, identity_value, source_account_scope)
        try:
            cursor = self._conn.execute(
                """INSERT INTO product_external_identities
                   (product_id, source, identity_type, identity_value,
                    source_account_scope, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (product_id, *values, datetime_to_db(utc_now())),
            )
        except sqlite3.IntegrityError as exc:
            if exc.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                raise ExternalIdentityConflict(values) from None
            raise
        row = self._conn.execute(
            """SELECT id, product_id, source, identity_type, identity_value,
                      source_account_scope, created_at
               FROM product_external_identities WHERE id = ?""",
            (cursor.lastrowid,),
        ).fetchone()
        assert row is not None
        return _identity_from_row(row)

    def find_by_external_identity(
        self,
        *,
        source: str,
        identity_type: str,
        identity_value: str,
        source_account_scope: str = "",
    ) -> Product | None:
        row = self._conn.execute(
            """SELECT p.id, p.is_owned, p.created_at, p.updated_at
               FROM products AS p
               JOIN product_external_identities AS i ON i.product_id = p.id
               WHERE i.source = ? AND i.identity_type = ? AND i.identity_value = ?
                 AND i.source_account_scope = ?""",
            (source, identity_type, identity_value, source_account_scope),
        ).fetchone()
        return None if row is None else _product_from_row(row)

    def resolve_or_create_ozon_product(self, ozon_product_id: str) -> Product:
        if not ozon_product_id.isdigit(): raise ValueError("invalid Ozon product ID")
        product = self.find_by_external_identity(source="ozon", identity_type="ozon_product_id", identity_value=ozon_product_id)
        if product is not None: return product
        product = self.create_product(is_owned=False)
        self.add_external_identity(product.id, source="ozon", identity_type="ozon_product_id", identity_value=ozon_product_id)
        return product

    def count_ozon_products(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM product_external_identities WHERE source='ozon' AND identity_type='ozon_product_id' AND source_account_scope='' ").fetchone()[0]

    def any_owned(self) -> bool:
        return self._conn.execute("SELECT EXISTS(SELECT 1 FROM products WHERE is_owned=1)").fetchone()[0] == 1

    def list_ozon_products(self, *, limit: int, offset: int) -> list[dict[str, object]]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("invalid pagination")
        rows = self._conn.execute("""SELECT p.id,p.is_owned,p.created_at,p.updated_at,i.identity_value AS ozon_product_id,s.*
FROM products p JOIN product_external_identities i ON i.product_id=p.id
LEFT JOIN product_snapshots s ON s.id=(SELECT ps.id FROM product_snapshots ps WHERE ps.product_id=p.id ORDER BY ps.report_generated_on DESC,ps.report_window_days DESC,ps.revision DESC LIMIT 1)
WHERE i.source='ozon' AND i.identity_type='ozon_product_id' AND i.source_account_scope=''
ORDER BY p.is_owned DESC,lower(COALESCE(s.title,'')),p.id LIMIT ? OFFSET ?""",(limit,offset)).fetchall()
        return [dict(row) for row in rows]
