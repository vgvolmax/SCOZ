import sqlite3
from datetime import date
from decimal import Decimal

from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.domain.benchmark_selection import (
    BenchmarkCandidate, BenchmarkComposition, BenchmarkCompositionWriteResult,
    BenchmarkEmptyError, BenchmarkMember, BenchmarkMemberInvalidError,
    BenchmarkSet, BenchmarkSetRevision, BenchmarkWriteKind, CandidatePage,
    CandidateReadiness, NoOwnQueryDataError, PhotoStatus,
    RelevantQueryOption, RelevantQueryReadiness, RelevantQuerySelection,
    RelevantQuerySelectionEmptyError, RelevantQuerySelectionInvalidError,
    RelevantQueryWriteResult, SourcePeriod,
)


class BenchmarkSelectionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_selected_query_ids(self, product_id: int) -> frozenset[int]:
        return frozenset(row[0] for row in self._conn.execute(
            "SELECT search_query_id FROM product_relevant_queries WHERE product_id=?",
            (product_id,),
        ))

    def list_relevant_query_options(self, product_id: int) -> RelevantQuerySelection:
        rows = self._conn.execute("""
        WITH current_pqs AS (
          SELECT p.* FROM product_query_snapshots p WHERE p.product_id=? AND
          p.revision=(SELECT MAX(x.revision) FROM product_query_snapshots x
            WHERE x.product_id=p.product_id AND x.search_query_id=p.search_query_id
              AND x.period_start=p.period_start AND x.period_end=p.period_end)
        ), latest_period AS (
          SELECT period_start,period_end FROM current_pqs
          ORDER BY period_end DESC,period_start DESC LIMIT 1
        ), options AS (
          SELECT p.*,1 AS in_latest_period FROM current_pqs p JOIN latest_period l
            ON p.period_start=l.period_start AND p.period_end=l.period_end
          UNION ALL
          SELECT p.*,0 FROM current_pqs p JOIN product_relevant_queries r
            ON r.product_id=p.product_id AND r.search_query_id=p.search_query_id
          WHERE NOT EXISTS (SELECT 1 FROM latest_period l WHERE p.period_start=l.period_start AND p.period_end=l.period_end)
            AND (p.period_end,p.period_start,p.revision)=(SELECT x.period_end,x.period_start,x.revision
              FROM current_pqs x WHERE x.search_query_id=p.search_query_id
              ORDER BY x.period_end DESC,x.period_start DESC,x.revision DESC LIMIT 1)
        )
        SELECT o.*,q.query_text,r.selected_at FROM options o
        JOIN search_queries q ON q.id=o.search_query_id
        LEFT JOIN product_relevant_queries r ON r.product_id=o.product_id AND r.search_query_id=o.search_query_id
        ORDER BY (r.search_query_id IS NOT NULL) DESC,o.in_latest_period DESC,
          (o.searched_users IS NULL),o.searched_users DESC,q.query_text,o.search_query_id
        """, (product_id,)).fetchall()
        latest = self._conn.execute("""WITH c AS (SELECT period_start,period_end FROM product_query_snapshots p
          WHERE product_id=? AND revision=(SELECT MAX(revision) FROM product_query_snapshots x WHERE x.product_id=p.product_id AND x.search_query_id=p.search_query_id AND x.period_start=p.period_start AND x.period_end=p.period_end))
          SELECT period_start,period_end FROM c ORDER BY period_end DESC,period_start DESC LIMIT 1""", (product_id,)).fetchone()
        selected_count = len(self.list_selected_query_ids(product_id))
        items = tuple(RelevantQueryOption(
            r["search_query_id"], r["query_text"], r["selected_at"] is not None,
            None if r["selected_at"] is None else datetime_from_db(r["selected_at"]),
            bool(r["in_latest_period"]), SourcePeriod(date.fromisoformat(r["period_start"]), date.fromisoformat(r["period_end"])),
            r["searched_users"], r["seen_users"], r["average_position"], r["ordered_units"], Decimal(r["ordered_revenue_rub"]),
        ) for r in rows)
        period = None if latest is None else SourcePeriod(date.fromisoformat(latest[0]), date.fromisoformat(latest[1]))
        readiness = RelevantQueryReadiness.NO_OWN_QUERY_DATA if latest is None else (
            RelevantQueryReadiness.READY if selected_count else RelevantQueryReadiness.EMPTY_SELECTION)
        return RelevantQuerySelection(product_id, readiness, period, items, selected_count)

    def replace_relevant_queries(self, product_id: int, search_query_ids: frozenset[int]) -> RelevantQueryWriteResult:
        before = self.list_selected_query_ids(product_id)
        evidence = self._conn.execute("SELECT EXISTS(SELECT 1 FROM product_query_snapshots WHERE product_id=?)", (product_id,)).fetchone()[0]
        if not evidence:
            raise NoOwnQueryDataError()
        if any(isinstance(i, bool) or not isinstance(i, int) or i <= 0 for i in search_query_ids):
            raise RelevantQuerySelectionInvalidError()
        if search_query_ids:
            marks = ",".join("?" for _ in search_query_ids)
            found = self._conn.execute(f"SELECT COUNT(DISTINCT search_query_id) FROM product_query_snapshots WHERE product_id=? AND search_query_id IN ({marks})", (product_id, *search_query_ids)).fetchone()[0]
            if found != len(search_query_ids): raise RelevantQuerySelectionInvalidError()
        if search_query_ids:
            marks = ",".join("?" for _ in search_query_ids)
            self._conn.execute(f"DELETE FROM product_relevant_queries WHERE product_id=? AND search_query_id NOT IN ({marks})", (product_id, *search_query_ids))
        else:
            self._conn.execute("DELETE FROM product_relevant_queries WHERE product_id=?", (product_id,))
        stamp = datetime_to_db(utc_now())
        self._conn.executemany("INSERT OR IGNORE INTO product_relevant_queries(product_id,search_query_id,selected_at) VALUES (?,?,?)", ((product_id, q, stamp) for q in search_query_ids))
        return RelevantQueryWriteResult(self.list_relevant_query_options(product_id), before != search_query_ids)

    def list_candidates(self, product_id: int, *, limit: int, offset: int) -> CandidatePage:
        if not self.list_selected_query_ids(product_id): raise RelevantQuerySelectionEmptyError()
        cte = """WITH selected AS (SELECT search_query_id FROM product_relevant_queries WHERE product_id=?),
        latest AS (SELECT s.search_query_id,s.cluster_id,MAX(s.observed_at) observed_at FROM search_visibility_snapshots s JOIN selected q ON q.search_query_id=s.search_query_id GROUP BY s.search_query_id,s.cluster_id),
        current AS (SELECT s.* FROM search_visibility_snapshots s JOIN latest l ON l.search_query_id=s.search_query_id AND l.cluster_id=s.cluster_id AND l.observed_at=s.observed_at WHERE s.revision=(SELECT MAX(x.revision) FROM search_visibility_snapshots x WHERE x.product_id=s.product_id AND x.search_query_id=s.search_query_id AND x.cluster_id=s.cluster_id AND x.observed_at=s.observed_at) AND s.product_id<>?),
        ranked AS (SELECT c.*,ROW_NUMBER() OVER(PARTITION BY product_id ORDER BY position,observed_at DESC,search_query_id,cluster_id,id DESC) rn FROM current c),
        agg AS (SELECT product_id,COUNT(DISTINCT search_query_id) query_count,COUNT(DISTINCT cluster_id) cluster_count,MIN(position) best_position FROM current GROUP BY product_id),
        identity AS (SELECT product_id,MIN(identity_value) identity_value FROM product_external_identities
          WHERE source='ozon' AND identity_type='ozon_product_id' AND source_account_scope=''
          GROUP BY product_id HAVING COUNT(id)=1)
        """
        total = self._conn.execute(cte + "SELECT COUNT(*) FROM agg JOIN identity USING(product_id)", (product_id, product_id)).fetchone()[0]
        rows = self._conn.execute(cte + """SELECT r.*,a.query_count,a.cluster_count,a.best_position,i.identity_value,
          EXISTS(SELECT 1 FROM benchmark_sets bs JOIN benchmark_set_revisions br ON br.benchmark_set_id=bs.id JOIN benchmark_members bm ON bm.benchmark_set_revision_id=br.id WHERE bs.own_product_id=? AND br.revision=(SELECT MAX(revision) FROM benchmark_set_revisions WHERE benchmark_set_id=bs.id) AND bm.product_id=r.product_id) selected_now
          FROM ranked r JOIN agg a ON a.product_id=r.product_id JOIN identity i ON i.product_id=r.product_id WHERE r.rn=1
          ORDER BY a.best_position,a.query_count DESC,CAST(i.identity_value AS INTEGER),r.product_id LIMIT ? OFFSET ?""", (product_id, product_id, product_id, limit, offset)).fetchall()
        items = tuple(BenchmarkCandidate(r["product_id"],r["identity_value"],r["source_title"],r["seller_name"],Decimal(r["buyer_price_rub"]),datetime_from_db(r["observed_at"]),r["query_count"],r["cluster_count"],r["best_position"],PhotoStatus.NOT_REQUESTED,None,bool(r["selected_now"]),"SEARCH_VISIBILITY") for r in rows)
        return CandidatePage(product_id, CandidateReadiness.READY if total else CandidateReadiness.NO_CANDIDATE_EVIDENCE, items, total, limit, offset)

    def get_benchmark(self, own_product_id: int) -> BenchmarkComposition:
        row = self._conn.execute("SELECT * FROM benchmark_sets WHERE own_product_id=?", (own_product_id,)).fetchone()
        if row is None: return BenchmarkComposition(None, None)
        bs = BenchmarkSet(row["id"],row["own_product_id"],datetime_from_db(row["created_at"]))
        revision = self._current_revision(bs.id)
        return BenchmarkComposition(bs, revision)

    def _current_revision(self, benchmark_set_id: int) -> BenchmarkSetRevision | None:
        row = self._conn.execute("SELECT * FROM benchmark_set_revisions WHERE benchmark_set_id=? ORDER BY revision DESC LIMIT 1", (benchmark_set_id,)).fetchone()
        if row is None: return None
        member_rows = self._conn.execute("""SELECT bm.product_id,MIN(i.identity_value) AS identity_value
          FROM benchmark_members bm
          LEFT JOIN product_external_identities i ON i.product_id=bm.product_id
            AND i.source='ozon' AND i.identity_type='ozon_product_id' AND i.source_account_scope=''
          WHERE bm.benchmark_set_revision_id=?
          GROUP BY bm.product_id HAVING COUNT(i.id)=1
          ORDER BY CAST(MIN(i.identity_value) AS INTEGER),bm.product_id""", (row["id"],)).fetchall()
        expected = self._conn.execute("SELECT COUNT(*) FROM benchmark_members WHERE benchmark_set_revision_id=?", (row["id"],)).fetchone()[0]
        if len(member_rows) != expected:
            raise BenchmarkMemberInvalidError()
        members = tuple(BenchmarkMember(row["id"], m["product_id"], m["identity_value"]) for m in member_rows)
        return BenchmarkSetRevision(row["id"],row["benchmark_set_id"],row["revision"],datetime_from_db(row["created_at"]),members)

    def save_benchmark(self, own_product_id: int, member_product_ids: frozenset[int]) -> BenchmarkCompositionWriteResult:
        if not member_product_ids: raise BenchmarkEmptyError()
        marks=",".join("?" for _ in member_product_ids)
        valid=self._conn.execute(f"""SELECT COUNT(*) FROM (
          SELECT p.id FROM products p
          LEFT JOIN product_external_identities i ON i.product_id=p.id
            AND i.source='ozon' AND i.identity_type='ozon_product_id' AND i.source_account_scope=''
          WHERE p.id IN ({marks}) AND p.id<>?
          GROUP BY p.id HAVING COUNT(i.id)=1
        )""", (*member_product_ids,own_product_id)).fetchone()[0]
        if valid != len(member_product_ids): raise BenchmarkMemberInvalidError()
        stamp=datetime_to_db(utc_now())
        self._conn.execute("INSERT INTO benchmark_sets(own_product_id,created_at) VALUES (?,?) ON CONFLICT(own_product_id) DO NOTHING",(own_product_id,stamp))
        row=self._conn.execute("SELECT * FROM benchmark_sets WHERE own_product_id=?",(own_product_id,)).fetchone(); bs=BenchmarkSet(row["id"],own_product_id,datetime_from_db(row["created_at"]))
        current=self._current_revision(bs.id)
        if current and frozenset(m.product_id for m in current.members)==member_product_ids:
            return BenchmarkCompositionWriteResult(BenchmarkWriteKind.NO_CHANGE,bs,current)
        number=1 if current is None else current.revision+1
        cursor=self._conn.execute("INSERT INTO benchmark_set_revisions(benchmark_set_id,revision,created_at) VALUES (?,?,?)",(bs.id,number,stamp))
        self._conn.executemany("INSERT INTO benchmark_members(benchmark_set_revision_id,product_id) VALUES (?,?)",((cursor.lastrowid,p) for p in member_product_ids))
        revision=self._current_revision(bs.id); assert revision is not None
        return BenchmarkCompositionWriteResult(BenchmarkWriteKind.CREATED if number==1 else BenchmarkWriteKind.CHANGED,bs,revision)
