from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from src.research_history import (
    ResearchHistoryPage,
    ResearchHistoryQuery,
    ResearchHistoryStore,
    ResearchHistoryThread,
)
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore


MATCHED_AT = "2026-07-18T02:00:00+00:00"
NEWER_AT = "2026-07-18T03:00:00+00:00"


@pytest.fixture()
def stores(tmp_path):
    db_path = tmp_path / "profile_state.db"
    thread_store = ResearchThreadStore(db_path)
    run_store = ResearchRunStore(db_path)
    return thread_store, run_store, ResearchHistoryStore(db_path)


def _add_thread(
    thread_store: ResearchThreadStore,
    thread_id: str,
    *,
    title: str | None = None,
    ticker: str | None = None,
    updated_at: str = MATCHED_AT,
    archived: bool = False,
) -> None:
    thread_store.ensure_thread(
        id=thread_id,
        title=title or thread_id,
        ticker=ticker,
        provider="openai",
        model="gpt-5.4-mini",
        now=updated_at,
    )
    if archived:
        with sqlite3.connect(thread_store.db_path) as conn:
            conn.execute(
                "UPDATE research_threads SET archived_at = ? WHERE id = ?",
                (updated_at, thread_id),
            )


def _add_run(
    run_store: ResearchRunStore,
    thread_id: str,
    run_id: str,
    *,
    status: str,
    created_at: str = MATCHED_AT,
    question: str = "question",
) -> None:
    run_store.create_run(
        id=run_id,
        thread_id=thread_id,
        question=question,
        ticker=None,
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
        auth_mode="api_key",
        credential_id=None,
    )
    with sqlite3.connect(run_store.db_path) as conn:
        conn.execute(
            "UPDATE research_runs SET status = ?, created_at = ?, updated_at = ? WHERE id = ?",
            (status, created_at, created_at, run_id),
        )


def _assert_bounded_page(page: ResearchHistoryPage, ids: list[str], *, total: int) -> None:
    assert [thread.id for thread in page.threads] == ids
    assert page.total == total
    assert page.limit == 1
    assert page.offset == 0
    assert len(page.threads) <= page.limit


class _AfterFetchCursor:
    def __init__(self, cursor, after_fetch):
        self._cursor = cursor
        self._after_fetch = after_fetch

    def fetchone(self):
        row = self._cursor.fetchone()
        self._after_fetch()
        return row


class _InterleavingConnection:
    def __init__(self, conn, after_count):
        self._conn = conn
        self._after_count = after_count

    def execute(self, sql, params=()):
        cursor = self._conn.execute(sql, params)
        if "COUNT(*) AS total" not in sql:
            return cursor
        assert self._conn.in_transaction, "count and page require an explicit snapshot"
        return _AfterFetchCursor(cursor, self._after_count)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_query_searches_stored_title_and_ticker_before_limit(stores, monkeypatch):
    thread_store, run_store, history = stores
    _add_thread(thread_store, "match-a", ticker="100%_")
    _add_thread(thread_store, "match-z", title="Stored literal 100%_ marker")
    _add_thread(
        thread_store,
        "newer-counterexample",
        title="Newest unrelated title",
        ticker="OTHER",
        updated_at=NEWER_AT,
    )
    _add_run(
        run_store,
        "newer-counterexample",
        "counter-run",
        status="succeeded",
        question="100%_ appears only in the run question",
    )
    original_connect = history._connect

    def add_interleaved_match():
        _add_thread(
            thread_store,
            "interleaved-match",
            title="Stored literal 100%_ added between reads",
            updated_at="2026-07-18T04:00:00+00:00",
        )

    monkeypatch.setattr(
        history,
        "_connect",
        lambda: _InterleavingConnection(original_connect(), add_interleaved_match),
    )

    page = history.query_threads(q="%_", limit=1)

    _assert_bounded_page(page, ["match-z"], total=2)
    assert thread_store.get_thread("interleaved-match") is not None
    assert isinstance(page.threads[0], ResearchHistoryThread)
    assert isinstance(page.threads, tuple)
    with pytest.raises(FrozenInstanceError):
        page.total = 99
    with pytest.raises(FrozenInstanceError):
        page.threads[0].title = "mutated"
    query = ResearchHistoryQuery(q="literal")
    with pytest.raises(FrozenInstanceError):
        query.q = "mutated"


def test_query_filters_exact_ticker_before_limit(stores):
    thread_store, _, history = stores
    _add_thread(thread_store, "match-a", ticker="nvda")
    _add_thread(thread_store, "match-z", ticker="NVDA")
    _add_thread(
        thread_store,
        "newer-counterexample",
        title="NVDA appears only in the title",
        ticker="NVDA.A",
        updated_at=NEWER_AT,
    )

    page = history.query_threads(ticker=" nvda ", limit=1)

    _assert_bounded_page(page, ["match-z"], total=2)
    assert page.threads[0].ticker == "NVDA"

    largest_offset = history.query_threads(
        ticker="nvda",
        limit=200,
        offset=2**63 - 1,
    )
    assert largest_offset.threads == ()
    assert largest_offset.total == 2
    assert largest_offset.limit == 200
    assert largest_offset.offset == 2**63 - 1

    for invalid in (
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"offset": 2**63},
    ):
        with pytest.raises(ValueError):
            history.query_threads(**invalid)


def test_query_filters_updated_window_before_limit(stores):
    thread_store, _, history = stores
    _add_thread(thread_store, "match-a")
    _add_thread(thread_store, "match-z")
    _add_thread(
        thread_store,
        "newer-counterexample",
        updated_at="2026-07-18T03:00:00+00:00",
    )
    _add_thread(
        thread_store,
        "older-counterexample",
        updated_at="2026-07-18T00:59:59+00:00",
    )

    page = history.query_threads(
        updated_from="2026-07-18T09:00:00+08:00",
        updated_before="2026-07-17T23:00:00-04:00",
        limit=1,
    )

    _assert_bounded_page(page, ["match-z"], total=2)
    assert page.threads[0].updated_at == MATCHED_AT

    z_page = history.query_threads(
        updated_from="2026-07-18T01:00:00Z",
        updated_before="2026-07-18T03:00:00Z",
        limit=1,
    )
    _assert_bounded_page(z_page, ["match-z"], total=2)

    after_half_second = history.query_threads(
        updated_from="2026-07-18T02:00:00.500000Z",
        updated_before="2026-07-18T03:00:00Z",
        limit=1,
    )
    assert after_half_second.threads == ()
    assert after_half_second.total == 0

    before_half_second = history.query_threads(
        updated_from="2026-07-18T01:00:00Z",
        updated_before="2026-07-18T02:00:00.500000Z",
        limit=1,
    )
    _assert_bounded_page(before_half_second, ["match-z"], total=2)

    with pytest.raises(ValueError, match="updated_from"):
        history.query_threads(updated_from="not-a-timestamp")
    with pytest.raises(ValueError, match="updated_before"):
        history.query_threads(updated_before="2026-07-18T03:00:00")
    for updated_from, updated_before in (
        ("2026-07-18T03:00:00Z", "2026-07-18T03:00:00Z"),
        ("2026-07-18T04:00:00Z", "2026-07-18T03:00:00Z"),
    ):
        with pytest.raises(ValueError, match="positive"):
            history.query_threads(
                updated_from=updated_from,
                updated_before=updated_before,
            )


@pytest.mark.parametrize(
    ("run_state", "matching_statuses", "nonmatching_status"),
    [
        pytest.param("active", ("queued", "running"), "failed", id="active"),
        pytest.param("succeeded", ("succeeded", "succeeded"), "failed", id="succeeded"),
        pytest.param("failed", ("failed", "failed"), "succeeded", id="failed"),
        pytest.param(
            "interrupted",
            ("cancelled", "interrupted"),
            "succeeded",
            id="interrupted",
        ),
        pytest.param("no_run", (None, None), "queued", id="no_run"),
    ],
)
def test_query_filters_latest_run_state(
    stores,
    run_state: str,
    matching_statuses: tuple[str | None, str | None],
    nonmatching_status: str,
):
    thread_store, run_store, history = stores
    for thread_id, status in zip(("match-a", "match-z"), matching_statuses):
        _add_thread(thread_store, thread_id)
        if status is not None:
            _add_run(
                run_store,
                thread_id,
                f"{thread_id}-run-a",
                status=nonmatching_status,
            )
            _add_run(
                run_store,
                thread_id,
                f"{thread_id}-run-z",
                status=status,
            )

    _add_thread(thread_store, "newer-counterexample", updated_at=NEWER_AT)
    if run_state == "no_run":
        _add_run(
            run_store,
            "newer-counterexample",
            "counter-run-z",
            status=nonmatching_status,
        )
    else:
        _add_run(
            run_store,
            "newer-counterexample",
            "counter-run-a",
            status=matching_statuses[0] or "queued",
        )
        _add_run(
            run_store,
            "newer-counterexample",
            "counter-run-z",
            status=nonmatching_status,
        )

    page = history.query_threads(run_state=run_state, limit=1)

    _assert_bounded_page(page, ["match-z"], total=2)
    assert page.threads[0].latest_run_status == matching_statuses[1]


@pytest.mark.parametrize(
    ("archive_mode", "matching_archived"),
    [
        pytest.param("current", False, id="current"),
        pytest.param("archived", True, id="archived"),
    ],
)
def test_query_archive_mode(stores, archive_mode: str, matching_archived: bool):
    thread_store, _, history = stores
    _add_thread(thread_store, "match-a", archived=matching_archived)
    _add_thread(thread_store, "match-z", archived=matching_archived)
    _add_thread(
        thread_store,
        "newer-counterexample",
        updated_at=NEWER_AT,
        archived=not matching_archived,
    )

    page = history.query_threads(archive_mode=archive_mode, limit=1)

    _assert_bounded_page(page, ["match-z"], total=2)
    assert (page.threads[0].archived_at is not None) is matching_archived
