"""Throwaway probes of existing product methods against large synthetic ID sets."""

import sys
from pathlib import Path

import pytest

ROOT = Path('/tmp/arkscope-prebuilt-compat.oCmRRHrQ/source')
sys.path.insert(0, str(ROOT / 'tests'))
import test_sa_article_reconciliation_backend as sa
import test_security_lifecycle_fact_kernel as lifecycle


@pytest.fixture
def backend(tmp_path):
    return sa.SACaptureBackend(sa_db=str(tmp_path / 'sa.db'), market_db=str(tmp_path / 'market.db'))


@pytest.mark.parametrize('method', [
    'query_sa_market_news_recovery_rows', 'query_sa_market_news_body_presence',
])
def test_recovery_large_frozen_target_set(backend, method):
    assert backend.upsert_sa_market_news([
        {'news_id': '1', 'url': 'https://seekingalpha.com/news/1', 'title': 'fixture'},
    ]) == 1
    result = getattr(backend, method)([str(value) for value in range(33000)])
    if isinstance(result, dict):
        assert result == {'1': False}
    else:
        assert [row['news_id'] for row in result] == ['1']


def test_lineage_filter_large_input(backend):
    sa._refresh(backend, 'current', [sa._pick()])
    conn = sa._conn(backend)
    try:
        events = sa.reconciliation_store.list_events(conn, lineage_ids=range(1, 33001))
        assert len(events) == 1
        assert events[0]['symbol'] == 'BTSG'
    finally:
        conn.close()


def test_article_filter_large_input_keeps_global_limit(backend):
    sa._refresh(backend, 'current', [sa._pick()])
    backend.upsert_sa_articles_meta([sa._article(str(value)) for value in range(1, 26)])
    conn = sa._conn(backend)
    try:
        event = sa.reconciliation_store.list_events(conn)[0]
        rows = sa.reconciliation_store._candidate_rows(
            conn, event, article_ids=[str(value) for value in range(33000)],
        )
        assert len(rows) == 20
        assert [row['article_id'] for row in rows] == sorted(
            [str(value) for value in range(1, 26)], reverse=True,
        )[:20]
    finally:
        conn.close()


def test_many_pinned_citations_survive_family_refresh():
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, kernel, case_id = lifecycle._context()
    try:
        claim = lifecycle._reserve(kernel, case_id, policy_version=AUTOMATION_POLICY_VERSION)
        old = lifecycle._evidence('old')
        decision = lifecycle._symbol_decision('HAPN', readiness='waiting_effective_date')
        kernel.complete_run(
            run_id=claim.run_id, evidence=(old,), facts=(lifecycle._fact(old),), blockers=(),
            decision_tier='verified_automatic', action_readiness='waiting_effective_date',
            retry_at=None, diagnostics={}, at=lifecycle._LATER, terminal_decision=decision,
        )
        assessment_id = create_automation_assessment(
            store=store, run_id=claim.run_id, decision=decision,
            observation_fingerprint_sha256=lifecycle._FINGERPRINT, at=lifecycle._LATER,
        )
        row = dict(conn.execute('SELECT * FROM security_lifecycle_evidence').fetchone())
        columns = list(row)
        evidence = []
        citations = []
        for index in range(33000):
            item = dict(row, evidence_id=f'historical-{index}', evidence_dedupe_key=f'historical-{index}')
            evidence.append(tuple(item[key] for key in columns))
            citations.append((assessment_id, 'evidence', item['evidence_id'], item['content_sha256']))
        conn.executemany(
            f"INSERT INTO security_lifecycle_evidence ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            evidence,
        )
        conn.executemany(
            'INSERT INTO security_lifecycle_assessment_evidence '
            '(assessment_id,reference_kind,evidence_id,cited_content_sha256) VALUES (?,?,?,?)',
            citations,
        )
        conn.commit()
        retry = kernel.reserve_readiness_recheck(
            run_id=claim.run_id, due_at='2026-08-26T00:00:00Z', at='2026-08-26T00:00:00Z',
            execution_owner_id='fixture-owner',
        )
        fresh = lifecycle._evidence('fresh')
        kernel.complete_run(
            run_id=retry.run_id, evidence=(fresh,), facts=(lifecycle._fact(fresh),), blockers=(),
            decision_tier='verified_automatic', action_readiness='waiting_effective_date',
            retry_at=None, diagnostics={}, at='2026-08-26T00:01:00Z', terminal_decision=decision,
            refreshed_source_families=('regulator',),
        )
        assert conn.execute('SELECT count(*) FROM security_lifecycle_evidence').fetchone()[0] == 33002
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        conn.close()
