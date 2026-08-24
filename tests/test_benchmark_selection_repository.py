from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest


def test_pr6_domain_types_are_frozen_and_enum_values_are_exact():
    from backend.domain.benchmark_selection import (
        BenchmarkCandidate, BenchmarkComposition, BenchmarkCompositionWriteResult,
        BenchmarkEmptyError, BenchmarkMember, BenchmarkMemberInvalidError,
        BenchmarkSelectionError, BenchmarkSet, BenchmarkSetRevision,
        BenchmarkConcurrentWriteError, BenchmarkWriteKind, CandidatePage,
        CandidateReadiness, ManualCandidateWriteResult, ManualOzonSkuInvalidError,
        MPStatsAuthError, MPStatsConnectionResult, MPStatsConnectionStatus,
        MPStatsMalformedResponseError, MPStatsNetworkError, MPStatsPendingError,
        MPStatsProductPreview, MPStatsRateLimitError, MPStatsTimeoutError,
        MPStatsUpstreamError, NoOwnQueryDataError,
        OwnProductCannotBeCompetitorError, PhotoStatus, ProductNotOwnedError,
        RelevantQueryOption, RelevantQueryReadiness, RelevantQuerySelection,
        RelevantQuerySelectionEmptyError, RelevantQuerySelectionInvalidError,
        RelevantQueryWriteResult, SourcePeriod,
    )

    now = datetime.now(timezone.utc)
    period = SourcePeriod(date(2026, 1, 1), date(2026, 1, 31))
    option = RelevantQueryOption(1, "query", True, now, True, period, 5, 4, 3, 2, Decimal("1.00"))
    selection = RelevantQuerySelection(1, RelevantQueryReadiness.READY, period, (option,), 1)
    write = RelevantQueryWriteResult(selection, True)
    candidate = BenchmarkCandidate(2, "123", None, None, None, None, 0, 0, None,
                                   PhotoStatus.NOT_REQUESTED, None, False, "MANUAL")
    candidate_page = CandidatePage(1, CandidateReadiness.READY, (candidate,), 1, 50, 0)
    manual = ManualCandidateWriteResult(True, candidate)
    benchmark_set = BenchmarkSet(1, 1, now)
    member = BenchmarkMember(1, 2, "123")
    revision = BenchmarkSetRevision(1, 1, 1, now, (member,))
    composition = BenchmarkComposition(benchmark_set, revision)
    composition_write = BenchmarkCompositionWriteResult(BenchmarkWriteKind.CREATED, benchmark_set, revision)
    preview = MPStatsProductPreview("123", PhotoStatus.AVAILABLE, "https://example.test/a.jpg")
    connection = MPStatsConnectionResult(MPStatsConnectionStatus.AVAILABLE)

    for value in (period, option, selection, write, candidate, candidate_page, manual,
                  benchmark_set, member, revision, composition, composition_write,
                  preview, connection):
        with pytest.raises(FrozenInstanceError):
            value.__setattr__(next(iter(value.__dataclass_fields__)), None)

    assert [item.value for item in RelevantQueryReadiness] == ["READY", "EMPTY_SELECTION", "NO_OWN_QUERY_DATA"]
    assert [item.value for item in PhotoStatus] == ["NOT_REQUESTED", "AVAILABLE", "MISSING"]
    assert [item.value for item in CandidateReadiness] == ["READY", "NO_CANDIDATE_EVIDENCE"]
    assert [item.value for item in BenchmarkWriteKind] == ["CREATED", "CHANGED", "NO_CHANGE"]
    assert [item.value for item in MPStatsConnectionStatus] == ["AVAILABLE"]
    for error in (ProductNotOwnedError, NoOwnQueryDataError,
                  RelevantQuerySelectionInvalidError, RelevantQuerySelectionEmptyError,
                  ManualOzonSkuInvalidError, OwnProductCannotBeCompetitorError,
                  BenchmarkEmptyError, BenchmarkMemberInvalidError,
                  BenchmarkConcurrentWriteError):
        assert issubclass(error, BenchmarkSelectionError)
    for error in (MPStatsAuthError, MPStatsPendingError, MPStatsTimeoutError,
                  MPStatsNetworkError, MPStatsMalformedResponseError, MPStatsUpstreamError):
        assert issubclass(error, Exception)
    assert MPStatsRateLimitError(12).retry_after_seconds == 12

from pathlib import Path
from backend.persistence.database import initialize_database
from backend.persistence.connection import connect
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.domain.benchmark_selection import (RelevantQueryReadiness, RelevantQuerySelectionInvalidError,
    RelevantQuerySelectionEmptyError, BenchmarkWriteKind, BenchmarkEmptyError,
    BenchmarkMemberInvalidError, CandidateReadiness)


def _repo_case(tmp_path):
    path = tmp_path / "pr6.db"; initialize_database(path); conn = connect(path)
    products = ProductRepository(conn); own = products.resolve_or_create_ozon_product("10")
    conn.execute("UPDATE products SET is_owned=1 WHERE id=?", (own.id,))
    competitor = products.resolve_or_create_ozon_product("20")
    dims = SearchDimensionRepository(conn); query = dims.resolve_search_query("Exact Query")
    conn.execute("INSERT INTO import_batches(source,import_kind,status,started_at) VALUES ('ozon','test','RUNNING',?)", ("2026-01-01T00:00:00+00:00",))
    conn.execute("INSERT INTO source_artifacts(import_batch_id,artifact_kind,content_sha256,byte_size,created_at) VALUES (1,'test',?,1,?)", ("b"*64,"2026-01-01T00:00:00+00:00"))
    conn.execute("""INSERT INTO product_query_snapshots
      (product_id,search_query_id,period_start,period_end,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,searched_users,seen_users,position_state,average_position,search_to_card_conversion_pct,search_to_order_conversion_pct,ordered_units,ordered_revenue_rub)
      VALUES (?,?,?,?,1,NULL,?,1,1,?,100,50,'KNOWN',3,'1','2',4,'500')""",
      (own.id,query.id,"2026-01-01","2026-01-31","a"*64,"2026-02-01T00:00:00+00:00"))
    conn.commit()
    from backend.persistence.repositories.benchmark_selection import BenchmarkSelectionRepository
    return path, conn, BenchmarkSelectionRepository(conn), own, competitor, query


def test_relevant_options_and_atomic_replace(tmp_path):
    _, conn, repo, own, _, query = _repo_case(tmp_path)
    initial = repo.list_relevant_query_options(own.id)
    assert initial.readiness is RelevantQueryReadiness.EMPTY_SELECTION
    result = repo.replace_relevant_queries(own.id, frozenset({query.id}))
    assert result.changed and result.selection.selected_count == 1
    stamp = result.selection.items[0].selected_at
    unchanged = repo.replace_relevant_queries(own.id, frozenset({query.id}))
    assert not unchanged.changed and unchanged.selection.items[0].selected_at == stamp
    with pytest.raises(RelevantQuerySelectionInvalidError):
        repo.replace_relevant_queries(own.id, frozenset({999}))
    assert repo.list_selected_query_ids(own.id) == frozenset({query.id})
    cleared = repo.replace_relevant_queries(own.id, frozenset())
    assert cleared.selection.readiness is RelevantQueryReadiness.EMPTY_SELECTION
    conn.close()

def _visibility(conn, product_id, query_id, observed="2026-02-01T00:00:00+00:00", revision=1, position=5, title="Candidate"):
    conn.execute("""INSERT INTO clusters(name,created_at) VALUES ('cluster'||?,?) ON CONFLICT(name) DO NOTHING""",(query_id,observed))
    cluster=conn.execute("SELECT id FROM clusters WHERE name='cluster'||?",(query_id,)).fetchone()[0]
    conn.execute("""INSERT INTO search_visibility_snapshots(product_id,search_query_id,cluster_id,observed_at,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,source_title,seller_name,position,overall_score,promotion_status,cpc_rub,promotion_strategy,cpo_state,cpo_pct,relevance_score,rating,reviews_count,buyer_price_rub,popularity_score,ozon_promotion,delivery_label,delivery_min_days,delivery_max_days,price_index_pct) VALUES (?,?,?,?,?,NULL,?,1,1,?,?,?,?,'1','none','0','none','DISABLED',NULL,'1',NULL,NULL,'99','1',0,'x',1,1,'1')""",(product_id,query_id,cluster,observed,revision,(str(product_id)+str(revision)).ljust(64,'a')[:64],observed,title,"Seller",position))


def test_candidates_use_selected_latest_evidence_and_page_after_dedupe(tmp_path):
    _,conn,repo,own,competitor,query=_repo_case(tmp_path)
    repo.replace_relevant_queries(own.id,frozenset({query.id}))
    _visibility(conn,competitor.id,query.id,"2026-01-01T00:00:00+00:00",position=9,title="old")
    _visibility(conn,competitor.id,query.id,"2026-02-01T00:00:00+00:00",position=4,title="new")
    page=repo.list_candidates(own.id,limit=50,offset=0)
    assert page.readiness is CandidateReadiness.READY and page.total==1
    assert page.items[0].source_title=="new" and page.items[0].best_position==4
    assert repo.list_candidates(own.id,limit=1,offset=5).total==1
    conn.close()

def test_benchmark_revisions_are_immutable_unordered_and_no_change(tmp_path):
    _,conn,repo,own,competitor,query=_repo_case(tmp_path)
    first=repo.save_benchmark(own.id,frozenset({competitor.id}))
    assert first.kind is BenchmarkWriteKind.CREATED and first.revision.revision==1
    assert repo.save_benchmark(own.id,frozenset({competitor.id})).kind is BenchmarkWriteKind.NO_CHANGE
    other=ProductRepository(conn).resolve_or_create_ozon_product("30")
    second=repo.save_benchmark(own.id,frozenset({other.id,competitor.id}))
    assert second.kind is BenchmarkWriteKind.CHANGED and second.revision.revision==2
    old=conn.execute("SELECT product_id FROM benchmark_members WHERE benchmark_set_revision_id=?",(first.revision.id,)).fetchall()
    assert [r[0] for r in old]==[competitor.id]
    assert [m.ozon_product_id for m in second.revision.members]==["20","30"]
    with pytest.raises(BenchmarkEmptyError): repo.save_benchmark(own.id,frozenset())
    with pytest.raises(BenchmarkMemberInvalidError): repo.save_benchmark(own.id,frozenset({own.id}))
    assert repo.get_benchmark(own.id).current_revision.revision==2
    conn.close()


def test_benchmark_rejects_member_with_multiple_canonical_ozon_identities_atomically(tmp_path):
    _, conn, repo, own, competitor, _ = _repo_case(tmp_path)
    first = repo.save_benchmark(own.id, frozenset({competitor.id}))
    now = "2026-02-02T00:00:00+00:00"
    conn.execute(
        """INSERT INTO product_external_identities
        (product_id,source,identity_type,identity_value,source_account_scope,created_at)
        VALUES (?,'ozon','ozon_product_id','21','',?)""",
        (competitor.id, now),
    )

    with pytest.raises(BenchmarkMemberInvalidError):
        repo.save_benchmark(own.id, frozenset({competitor.id}))

    assert conn.execute("SELECT COUNT(*) FROM benchmark_set_revisions").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM benchmark_members").fetchone()[0] == 1
    assert conn.execute(
        "SELECT revision FROM benchmark_set_revisions WHERE id=?", (first.revision.id,)
    ).fetchone()[0] == 1
    with pytest.raises(BenchmarkMemberInvalidError):
        repo.get_benchmark(own.id)
    conn.close()


def test_candidates_exclude_product_with_ambiguous_ozon_identity(tmp_path):
    _, conn, repo, own, competitor, query = _repo_case(tmp_path)
    repo.replace_relevant_queries(own.id, frozenset({query.id}))
    _visibility(conn, competitor.id, query.id)
    conn.execute(
        """INSERT INTO product_external_identities
        (product_id,source,identity_type,identity_value,source_account_scope,created_at)
        VALUES (?,'ozon','ozon_product_id','21','',?)""",
        (competitor.id, "2026-02-02T00:00:00+00:00"),
    )

    page = repo.list_candidates(own.id, limit=50, offset=0)

    assert page.items == ()
    assert page.total == 0
    assert page.readiness is CandidateReadiness.NO_CANDIDATE_EVIDENCE
    conn.close()
