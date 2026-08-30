import sqlite3
from datetime import date

from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.domain.product import (
    ExternalIdentityConflict,
    Product,
    ProductExternalIdentity,
    ProductNotFound,
)
from backend.domain.product_workspace import ProductDataStatus, ProductEntry


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
        self._conn.create_function("SCOZ_CASEFOLD", 1, lambda value: value.casefold() if isinstance(value, str) else "", deterministic=True)

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
        if not (
            ozon_product_id.isascii()
            and ozon_product_id.isdigit()
            and int(ozon_product_id) > 0
            and str(int(ozon_product_id)) == ozon_product_id
        ):
            raise ValueError("invalid Ozon product ID")
        product = self.find_by_external_identity(source="ozon", identity_type="ozon_product_id", identity_value=ozon_product_id)
        if product is not None: return product
        product = self.create_product(is_owned=False)
        self.add_external_identity(product.id, source="ozon", identity_type="ozon_product_id", identity_value=ozon_product_id)
        return product

    @staticmethod
    def _validate_catalog_query(query: str | None) -> None:
        if query is not None and (query != query.strip() or not query or len(query) > 200):
            raise ValueError("invalid product query")

    @staticmethod
    def _filter(query: str | None) -> tuple[str, tuple[str, ...]]:
        if query is None:
            return "", ()
        title = "instr(SCOZ_CASEFOLD(COALESCE(s.title,'')),SCOZ_CASEFOLD(?))>0"
        if query.isascii() and query.isdigit():
            return f" AND ({title} OR substr(i.ozon_product_id,1,length(?))=?)", (query, query, query)
        return f" AND {title}", (query,)

    @staticmethod
    def _projection() -> str:
        return """WITH i AS (
 SELECT product_id,MIN(identity_value) ozon_product_id FROM product_external_identities
 WHERE source='ozon' AND identity_type='ozon_product_id' AND source_account_scope=''
 GROUP BY product_id HAVING COUNT(*)=1
), s AS (SELECT ps.* FROM product_snapshots ps WHERE ps.id=(SELECT x.id FROM product_snapshots x
 WHERE x.product_id=ps.product_id ORDER BY x.report_generated_on DESC,x.report_window_days DESC,x.revision DESC LIMIT 1)) """

    def count_ozon_products(self, *, query: str | None = None) -> int:
        self._validate_catalog_query(query)
        clause, params = self._filter(query)
        return self._conn.execute(self._projection() + "SELECT COUNT(*) FROM products p JOIN i ON i.product_id=p.id JOIN s ON s.product_id=p.id WHERE 1=1" + clause, params).fetchone()[0]

    def any_owned(self) -> bool:
        return self._conn.execute(
            """SELECT EXISTS(
                   SELECT 1 FROM products AS p
                   WHERE p.is_owned=1
                     AND EXISTS (
                         SELECT 1 FROM product_snapshots AS ps
                         WHERE ps.product_id=p.id
                     )
               )"""
        ).fetchone()[0] == 1

    @staticmethod
    def _entry(row: sqlite3.Row) -> ProductEntry:
        available = row["report_generated_on"] is not None
        return ProductEntry(row["product_id"], row["ozon_product_id"], bool(row["is_owned"]), row["title"], row["seller_name"], row["brand"], ProductDataStatus.AVAILABLE if available else ProductDataStatus.MISSING, None if not available else date.fromisoformat(row["report_generated_on"]), row["report_window_days"], None if row["imported_at"] is None else datetime_from_db(row["imported_at"]))

    def list_ozon_products(self, *, limit: int, offset: int, query: str | None = None) -> tuple[ProductEntry, ...]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("invalid pagination")
        self._validate_catalog_query(query)
        clause, params = self._filter(query)
        rows = self._conn.execute(self._projection() + """SELECT p.id product_id,p.is_owned,i.ozon_product_id,s.title,s.seller_name,s.brand,s.report_generated_on,s.report_window_days,s.imported_at
 FROM products p JOIN i ON i.product_id=p.id JOIN s ON s.product_id=p.id WHERE 1=1""" + clause + " ORDER BY SCOZ_CASEFOLD(s.title),length(i.ozon_product_id),i.ozon_product_id,p.id LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        return tuple(self._entry(row) for row in rows)

    def list_owned_ozon_products(self) -> tuple[ProductEntry, ...]:
        rows = self._conn.execute(self._projection() + """SELECT p.id product_id,p.is_owned,i.ozon_product_id,s.title,s.seller_name,s.brand,s.report_generated_on,s.report_window_days,s.imported_at
 FROM products p JOIN i ON i.product_id=p.id LEFT JOIN s ON s.product_id=p.id WHERE p.is_owned=1
 ORDER BY SCOZ_CASEFOLD(COALESCE(s.title,'Ozon SKU '||i.ozon_product_id)),length(i.ozon_product_id),i.ozon_product_id,p.id""").fetchall()
        return tuple(self._entry(row) for row in rows)

    def get_ozon_product_entry(self, product_id: int) -> ProductEntry | None:
        row = self._conn.execute(self._projection() + """SELECT p.id product_id,p.is_owned,i.ozon_product_id,s.title,s.seller_name,s.brand,s.report_generated_on,s.report_window_days,s.imported_at
 FROM products p JOIN i ON i.product_id=p.id LEFT JOIN s ON s.product_id=p.id WHERE p.id=?""", (product_id,)).fetchone()
        return None if row is None else self._entry(row)
