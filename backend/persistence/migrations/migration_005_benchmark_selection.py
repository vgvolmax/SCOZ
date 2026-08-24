import sqlite3


def up(connection: sqlite3.Connection) -> None:
    for statement in (
        """
        CREATE TABLE product_relevant_queries (
            product_id INTEGER NOT NULL
                REFERENCES products(id) ON DELETE CASCADE,
            search_query_id INTEGER NOT NULL
                REFERENCES search_queries(id) ON DELETE RESTRICT,
            selected_at TEXT NOT NULL,
            PRIMARY KEY (product_id, search_query_id)
        );
        CREATE INDEX idx_product_relevant_queries_query_product
            ON product_relevant_queries(search_query_id, product_id);

        CREATE TABLE benchmark_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            own_product_id INTEGER NOT NULL
                REFERENCES products(id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL,
            UNIQUE (own_product_id)
        );

        CREATE TABLE benchmark_set_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_set_id INTEGER NOT NULL
                REFERENCES benchmark_sets(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL CHECK (revision > 0),
            created_at TEXT NOT NULL,
            UNIQUE (benchmark_set_id, revision)
        );
        CREATE INDEX idx_benchmark_set_revisions_current
            ON benchmark_set_revisions(benchmark_set_id, revision DESC);

        CREATE TABLE benchmark_members (
            benchmark_set_revision_id INTEGER NOT NULL
                REFERENCES benchmark_set_revisions(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL
                REFERENCES products(id) ON DELETE RESTRICT,
            PRIMARY KEY (benchmark_set_revision_id, product_id)
        );
        CREATE INDEX idx_benchmark_members_product_revision
            ON benchmark_members(product_id, benchmark_set_revision_id);
        """
    ).split(";"):
        if statement.strip():
            connection.execute(statement)
