"""Profile-state contracts for DB-derived universe compatibility state."""

from __future__ import annotations

import sqlite3

import pytest

from src import profile_state
from src.profile_state import ProfileStateStore


@pytest.fixture()
def store(tmp_path):
    return ProfileStateStore(tmp_path / "profile_state.db")


def _compat_state(db_path: str) -> tuple[list[tuple], list[tuple]]:
    with sqlite3.connect(db_path) as conn:
        memberships = conn.execute(
            "SELECT source_key, ticker, created_at, archived_at "
            "FROM universe_source_memberships ORDER BY source_key, ticker"
        ).fetchall()
        annotations = conn.execute(
            "SELECT source_key, ticker, annotation_key, annotation_value "
            "FROM universe_source_annotations "
            "ORDER BY source_key, ticker, annotation_key, annotation_value"
        ).fetchall()
    return memberships, annotations


def _annotation(ticker: str, key: str, value: str):
    return profile_state.UniverseSourceAnnotation(
        source_key="legacy_config_seed",
        ticker=ticker,
        annotation_key=key,
        annotation_value=value,
    )


def test_universe_source_tables_have_reviewed_shape_without_annotation_fk(store):
    with sqlite3.connect(store.db_path) as conn:
        membership_columns = [
            (row[1], row[2], row[3], row[4], row[5])
            for row in conn.execute("PRAGMA table_info(universe_source_memberships)")
        ]
        annotation_columns = [
            (row[1], row[2], row[3], row[4], row[5])
            for row in conn.execute("PRAGMA table_info(universe_source_annotations)")
        ]

        assert membership_columns == [
            ("source_key", "TEXT", 1, None, 1),
            ("ticker", "TEXT", 1, None, 2),
            ("created_at", "TEXT", 1, None, 0),
            ("archived_at", "TEXT", 0, None, 0),
        ]
        assert annotation_columns == [
            ("source_key", "TEXT", 1, None, 1),
            ("ticker", "TEXT", 1, None, 2),
            ("annotation_key", "TEXT", 1, None, 3),
            ("annotation_value", "TEXT", 1, None, 4),
        ]

        membership_indexes = {
            row[1]: row
            for row in conn.execute("PRAGMA index_list(universe_source_memberships)")
        }
        active_index = membership_indexes["idx_universe_source_memberships_active"]
        assert (active_index[2], active_index[3], active_index[4]) == (0, "c", 1)
        assert [
            row[2]
            for row in conn.execute(
                "PRAGMA index_info(idx_universe_source_memberships_active)"
            )
        ] == ["source_key", "ticker"]
        active_index_sql = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'index' AND name = 'idx_universe_source_memberships_active'"
        ).fetchone()[0]
        assert "WHERE archived_at IS NULL" in " ".join(active_index_sql.split())

        annotation_indexes = {
            row[1]: row
            for row in conn.execute("PRAGMA index_list(universe_source_annotations)")
        }
        annotation_index = annotation_indexes["idx_universe_source_annotations_ticker"]
        assert (annotation_index[2], annotation_index[3], annotation_index[4]) == (0, "c", 0)
        assert [
            row[2]
            for row in conn.execute(
                "PRAGMA index_info(idx_universe_source_annotations_ticker)"
            )
        ] == ["ticker", "source_key"]

        membership_pk = next(row[1] for row in membership_indexes.values() if row[3] == "pk")
        annotation_pk = next(row[1] for row in annotation_indexes.values() if row[3] == "pk")
        assert [row[2] for row in conn.execute(f"PRAGMA index_info({membership_pk})")] == [
            "source_key",
            "ticker",
        ]
        assert [row[2] for row in conn.execute(f"PRAGMA index_info({annotation_pk})")] == [
            "source_key",
            "ticker",
            "annotation_key",
            "annotation_value",
        ]
        assert conn.execute(
            "PRAGMA foreign_key_list(universe_source_annotations)"
        ).fetchall() == []


def test_replace_legacy_config_import_validates_every_row_before_begin(store, monkeypatch):
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "INSERT INTO universe_source_memberships "
            "(source_key, ticker, created_at) VALUES (?, ?, ?)",
            ("legacy_config_seed", "OLD", "2026-07-19T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO universe_source_annotations "
            "(source_key, ticker, annotation_key, annotation_value) VALUES (?, ?, ?, ?)",
            ("legacy_config_seed", "OLD", "legacy_tier", "tier1_core"),
        )
        conn.commit()
    before = _compat_state(store.db_path)

    connect_calls = 0

    def fail_if_connected():
        nonlocal connect_calls
        connect_calls += 1
        raise AssertionError("validation opened a database connection")

    monkeypatch.setattr(store, "_connect", fail_if_connected)
    annotations = [
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation("   ", "legacy_category", "tier1_core/mega_cap_tech"),
    ]

    with pytest.raises(ValueError, match="ticker"):
        store.replace_legacy_config_import(
            approved_memberships=["AAPL"],
            annotations=annotations,
        )

    assert connect_calls == 0
    assert _compat_state(store.db_path) == before


def test_replace_legacy_config_import_is_atomic_on_sql_failure(store, monkeypatch):
    conn = store._connect()
    try:
        conn.execute(
            "INSERT INTO universe_source_memberships "
            "(source_key, ticker, created_at) VALUES (?, ?, ?)",
            ("legacy_config_seed", "OLD", "2026-07-19T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO universe_source_annotations "
            "(source_key, ticker, annotation_key, annotation_value) VALUES (?, ?, ?, ?)",
            ("legacy_config_seed", "OLD", "legacy_tier", "tier1_core"),
        )
        conn.commit()
        before = _compat_state(store.db_path)
        conn.execute(
            """
            CREATE TEMP TRIGGER abort_second_annotation
            BEFORE INSERT ON universe_source_annotations
            WHEN NEW.ticker = 'MSFT'
            BEGIN
                SELECT RAISE(ABORT, 'forced second annotation');
            END
            """
        )
        monkeypatch.setattr(store, "_connect", lambda: conn)

        with pytest.raises(sqlite3.IntegrityError, match="forced second annotation"):
            store.replace_legacy_config_import(
                approved_memberships=["AAPL"],
                annotations=[
                    _annotation("AAPL", "legacy_tier", "tier1_core"),
                    _annotation("MSFT", "legacy_tier", "tier2_growth"),
                ],
            )

        assert _compat_state(store.db_path) == before
    finally:
        conn.close()


def test_replace_legacy_config_import_archives_reactivates_and_is_idempotent(store):
    annotations = [
        _annotation(" aapl ", "legacy_tier", " tier1_core "),
        _annotation("AAPL", "legacy_category", " tier1_core / mega_cap_tech "),
        _annotation("aapl", "legacy_category", "tier1_core/mega_cap_tech"),
        _annotation(" msft ", "legacy_category", "tier2_growth/seeking_picks_financials"),
    ]

    first = store.replace_legacy_config_import(
        approved_memberships=[" msft ", "AAPL", "MSFT"],
        annotations=annotations,
    )
    assert first == {
        "memberships_active": 2,
        "memberships_archived": 0,
        "annotations": 3,
    }
    assert store.list_active_universe_source_memberships() == ["AAPL", "MSFT"]
    assert store.list_universe_source_annotations() == [
        _annotation("AAPL", "legacy_category", "tier1_core/mega_cap_tech"),
        _annotation("AAPL", "legacy_tier", "tier1_core"),
        _annotation("MSFT", "legacy_category", "tier2_growth/seeking_picks_financials"),
    ]
    created_at = {
        ticker: created
        for _, ticker, created, _ in _compat_state(store.db_path)[0]
    }

    archived = store.replace_legacy_config_import(
        approved_memberships=["MSFT"],
        annotations=annotations,
    )
    assert archived == {
        "memberships_active": 1,
        "memberships_archived": 1,
        "annotations": 3,
    }
    assert store.list_active_universe_source_memberships() == ["MSFT"]
    memberships, _ = _compat_state(store.db_path)
    assert len(memberships) == 2
    assert next(row for row in memberships if row[1] == "AAPL")[3] is not None

    reactivated = store.replace_legacy_config_import(
        approved_memberships=["AAPL", "MSFT"],
        annotations=annotations,
    )
    assert reactivated == {
        "memberships_active": 2,
        "memberships_archived": 0,
        "annotations": 3,
    }
    assert store.list_active_universe_source_memberships() == ["AAPL", "MSFT"]
    assert {
        ticker: created
        for _, ticker, created, archived_at in _compat_state(store.db_path)[0]
        if archived_at is None
    } == created_at

    before_repeat = _compat_state(store.db_path)
    repeated = store.replace_legacy_config_import(
        approved_memberships=["AAPL", "MSFT"],
        annotations=annotations,
    )
    assert repeated == reactivated
    assert _compat_state(store.db_path) == before_repeat


def test_annotation_tag_groups_preserve_paired_paths_without_membership(store):
    store.replace_legacy_config_import(
        approved_memberships=[],
        annotations=[
            _annotation("DUAL", "legacy_tier", "tier1_core"),
            _annotation("DUAL", "legacy_tier", "tier3_user_watchlist"),
            _annotation("DUAL", "legacy_category", "tier1_core/sa_alpha_picks_auto"),
            _annotation(
                "DUAL",
                "legacy_category",
                "tier3_user_watchlist/seeking_picks_financials",
            ),
            _annotation("GENERIC", "legacy_tier", "tier2_growth"),
            _annotation("GENERIC", "legacy_category", "tier2_growth/mega_cap_tech"),
        ],
    )

    assert store.list_active_universe_source_memberships() == []
    dual_paths = {
        row.annotation_value
        for row in store.list_universe_source_annotations()
        if row.ticker == "DUAL" and row.annotation_key == "legacy_category"
    }
    assert dual_paths == {
        "tier1_core/sa_alpha_picks_auto",
        "tier3_user_watchlist/seeking_picks_financials",
    }
    assert "tier1_core/seeking_picks_financials" not in dual_paths
    assert "tier3_user_watchlist/sa_alpha_picks_auto" not in dual_paths
    assert store.legacy_annotation_tag_groups() == [
        {"facet": "category", "value": "Financials", "source": "legacy", "tickers": ["DUAL"]},
        {
            "facet": "category",
            "value": "Mega Cap Tech",
            "source": "legacy",
            "tickers": ["GENERIC"],
        },
        {
            "facet": "provenance",
            "value": "Alpha Picks",
            "source": "legacy",
            "tickers": ["DUAL"],
        },
        {
            "facet": "provenance",
            "value": "Seeking Alpha",
            "source": "legacy",
            "tickers": ["DUAL"],
        },
    ]


def test_archived_list_history_query_never_qualifies_membership(store):
    parent_archived = store.create_list("Parent archived")
    member_archived = store.create_list("Member archived")
    active = store.create_list("Still active")

    store.add_member(parent_archived.id, "PARENT")
    store.add_member(parent_archived.id, "RESCUED")
    store.add_member(member_archived.id, "MEMBER")
    store.add_member(member_archived.id, "RESCUED")
    store.add_member(active.id, "ACTIVE")
    store.add_member(active.id, "RESCUED")
    store.set_universe_hidden("PARENT", True)

    archived_at = "2026-07-19T00:00:00+00:00"
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE watchlists SET archived_at = ?, updated_at = ? WHERE id = ?",
            (archived_at, archived_at, parent_archived.id),
        )
        conn.execute(
            "UPDATE watchlist_memberships SET archived_at = ?, updated_at = ? "
            "WHERE list_id = ?",
            (archived_at, archived_at, member_archived.id),
        )
        conn.commit()

    assert store.archived_list_tickers() == ["MEMBER", "PARENT"]
