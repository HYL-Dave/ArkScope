"""Contracts for the complete SQLite-derived active-universe snapshot."""

from __future__ import annotations

import importlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import sa_capture_store
from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore, UniverseSourceAnnotation


NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-07-19T12:00:00+00:00"
LEGACY_SOURCE = "legacy_config_seed"
SA_SOURCE = "sa_alpha_picks_current"


def _active_universe():
    return importlib.import_module("src.active_universe")


@pytest.fixture()
def databases(tmp_path):
    profile_path = tmp_path / "profile_state.db"
    sa_path = tmp_path / "sa_capture.db"
    profile_store = ProfileStateStore(profile_path)
    portfolio_store = PortfolioStore(profile_path)
    conn = sa_capture_store.connect(str(sa_path))
    conn.close()
    return SimpleNamespace(
        profile_path=profile_path,
        sa_path=sa_path,
        profile=profile_store,
        portfolio=portfolio_store,
    )


def _snapshot(databases, *, now: datetime = NOW):
    return _active_universe().build_active_universe_snapshot(
        profile_db=databases.profile_path,
        sa_db=databases.sa_path,
        now=now,
    )


def _insert_pick(
    path: Path,
    symbol: str,
    *,
    status: str = "current",
    stale: int = 0,
    picked_date: str = "2026-07-01",
) -> None:
    symbol_key = symbol.strip().upper()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sa_pick_lineages "
            "(symbol_key, picked_date, created_at) VALUES (?, ?, ?)",
            (symbol_key, picked_date, NOW_TEXT),
        )
        lineage_id = conn.execute(
            "SELECT lineage_id FROM sa_pick_lineages "
            "WHERE symbol_key=? AND picked_date=?",
            (symbol_key, picked_date),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO sa_alpha_picks "
            "(lineage_id, symbol, company, picked_date, portfolio_status, "
            "is_stale) VALUES (?, ?, ?, ?, ?, ?)",
            (lineage_id, symbol, f"{symbol_key} Inc", picked_date, status, stale),
        )


def _set_current_refresh(
    path: Path,
    *,
    last_success_at: str | None,
    ok: int,
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sa_refresh_meta "
            "(scope, last_attempt_at, last_success_at, ok, updated_at) "
            "VALUES ('current', ?, ?, ?, ?)",
            (NOW_TEXT, last_success_at, ok, NOW_TEXT),
        )


def _assert_sanitized_unavailable(exc, expected_reasons, *secrets: object) -> None:
    expected_sources = tuple(expected_reasons)
    assert exc.unavailable_sources == expected_sources
    assert exc.source_reasons == expected_reasons
    assert exc.as_dict() == {
        "code": "active_universe_unavailable",
        "status": "unavailable",
        "unavailable_sources": list(expected_sources),
        "source_reasons": expected_reasons,
    }
    rendered = f"{exc}\n{json.dumps(exc.as_dict(), sort_keys=True)}"
    for secret in secrets:
        assert str(secret) not in rendered


def test_snapshot_unions_all_four_sources_and_retains_sorted_provenance(databases):
    au = _active_universe()
    databases.profile.import_lists(
        [{"name": "Core", "tickers": [" aapl ", "nvda"]}]
    )
    account = databases.portfolio.ensure_manual_account()
    for symbol in ("MSFT", "nvda"):
        databases.portfolio.upsert_manual_position(
            account_id=account.id,
            symbol=symbol,
            quantity=1,
        )
    databases.profile.replace_legacy_config_import(
        approved_memberships=["TSLA", " nvda "],
        annotations=[],
    )
    _insert_pick(databases.sa_path, " goog ")
    _insert_pick(databases.sa_path, "NVDA", picked_date="2026-07-02")
    _set_current_refresh(databases.sa_path, last_success_at=NOW_TEXT, ok=1)

    snapshot = _snapshot(databases)

    assert snapshot.tickers == ("AAPL", "GOOG", "MSFT", "NVDA", "TSLA")
    assert snapshot.sources_by_ticker == {
        "AAPL": ("manual_lists",),
        "GOOG": (SA_SOURCE,),
        "MSFT": ("portfolio_open",),
        "NVDA": tuple(sorted(au.SOURCE_KEYS)),
        "TSLA": (LEGACY_SOURCE,),
    }
    assert tuple(snapshot.source_status) == tuple(sorted(au.SOURCE_KEYS))
    assert all(status.available for status in snapshot.source_status.values())
    assert snapshot.source_status[SA_SOURCE].last_success_at == NOW_TEXT
    assert snapshot.source_status[SA_SOURCE].warnings == ()
    assert snapshot.unavailable_sources == ()
    assert snapshot.generated_at == NOW_TEXT


def test_manual_lists_require_active_parent_and_membership(databases):
    _active_universe()
    databases.profile.import_lists(
        [
            {"name": "Active", "tickers": ["AAPL"]},
            {"name": "Archived parent", "tickers": ["MSFT"]},
            {"name": "Archived member", "tickers": ["TSLA"]},
        ]
    )
    with sqlite3.connect(databases.profile_path) as conn:
        conn.execute(
            "UPDATE watchlists SET archived_at=? WHERE name='Archived parent'",
            (NOW_TEXT,),
        )
        conn.execute(
            "UPDATE watchlist_memberships SET archived_at=? WHERE ticker='TSLA'",
            (NOW_TEXT,),
        )

    snapshot = _snapshot(databases)

    assert snapshot.tickers == ("AAPL",)
    assert snapshot.sources_by_ticker == {"AAPL": ("manual_lists",)}


def test_portfolio_open_requires_open_account_and_position_but_ignores_include_total(
    databases,
):
    _active_universe()
    open_account = databases.portfolio.ensure_manual_account()
    included = databases.portfolio.upsert_manual_position(
        account_id=open_account.id,
        symbol="INCLUDED",
        quantity=1,
    )
    closed = databases.portfolio.upsert_manual_position(
        account_id=open_account.id,
        symbol="CLOSED",
        quantity=1,
    )
    databases.portfolio.close_position(closed.id)
    databases.portfolio.update_account(open_account.id, include_in_total=False)

    archived_account = databases.portfolio.upsert_broker_account(
        "ibkr", "DU-ARCHIVED", "Archived"
    )
    databases.portfolio.upsert_manual_position(
        account_id=archived_account.id,
        symbol="ARCHIVED",
        quantity=1,
    )
    databases.portfolio.update_account(archived_account.id, archived=True)

    snapshot = _snapshot(databases)

    assert included.closed_at is None
    assert snapshot.tickers == ("INCLUDED",)
    assert snapshot.sources_by_ticker == {"INCLUDED": ("portfolio_open",)}


def test_portfolio_equity_classes_include_stock_etf_option_and_warn_on_others(
    databases, tmp_path
):
    au = _active_universe()
    account = databases.portfolio.ensure_manual_account()
    for symbol, asset_class in (
        ("STOCK", "stock"),
        ("FUND", " ETF "),
        ("UNDERLYING", "OPTION"),
        ("CASHROW", "cash"),
    ):
        databases.portfolio.upsert_manual_position(
            account_id=account.id,
            symbol=symbol,
            asset_class=asset_class,
            quantity=1,
        )
    hostile_token = "DO_NOT_LEAK_ASSET_TOKEN"
    hostile_class = f"future:{tmp_path}:{hostile_token}"
    databases.portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="HOSTILE",
        asset_class=hostile_class,
        quantity=1,
    )
    blank = databases.portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="BLANK",
        asset_class="stock",
        quantity=1,
    )
    with sqlite3.connect(databases.profile_path) as conn:
        conn.execute(
            "UPDATE portfolio_positions SET symbol='   ' WHERE id=?", (blank.id,)
        )

    snapshot = _snapshot(databases)

    assert au.EQUITY_ASSET_CLASSES == frozenset({"stock", "etf", "option"})
    assert snapshot.tickers == ("FUND", "STOCK", "UNDERLYING")
    warnings = snapshot.source_status["portfolio_open"].warnings
    assert warnings == (
        "invalid_symbol_count=1",
        "unsupported_asset_class_count=2",
    )
    assert str(tmp_path) not in repr(warnings)
    assert hostile_token not in repr(warnings)


def test_alpha_picks_current_excludes_stale_and_closed(databases):
    _active_universe()
    _insert_pick(databases.sa_path, "ACTIVE")
    _insert_pick(
        databases.sa_path,
        "STALE",
        stale=1,
        picked_date="2026-07-02",
    )
    _insert_pick(
        databases.sa_path,
        "CLOSED",
        status="closed",
        picked_date="2026-07-03",
    )
    _set_current_refresh(databases.sa_path, last_success_at=NOW_TEXT, ok=1)

    snapshot = _snapshot(databases)

    assert snapshot.tickers == ("ACTIVE",)
    assert snapshot.sources_by_ticker == {"ACTIVE": (SA_SOURCE,)}


def test_alpha_latest_refresh_failure_warns_without_withdrawing_facts(databases):
    _active_universe()
    _insert_pick(databases.sa_path, "AAPL")
    old_success = (NOW - timedelta(hours=49)).isoformat(timespec="seconds")
    _set_current_refresh(databases.sa_path, last_success_at=old_success, ok=0)

    snapshot = _snapshot(databases)

    status = snapshot.source_status[SA_SOURCE]
    assert snapshot.tickers == ("AAPL",)
    assert status.available is True
    assert status.last_success_at == old_success
    assert status.warnings == ("latest_refresh_failed", "stale_refresh")


def test_alpha_age_warning_uses_48_hours_without_expiring_membership(databases):
    au = _active_universe()
    _insert_pick(databases.sa_path, "AAPL")
    exactly_48_hours = (NOW - timedelta(hours=au.SA_STALE_AFTER_HOURS)).isoformat(
        timespec="seconds"
    )
    _set_current_refresh(databases.sa_path, last_success_at=exactly_48_hours, ok=1)

    fresh_boundary = _snapshot(databases)

    assert fresh_boundary.tickers == ("AAPL",)
    assert fresh_boundary.source_status[SA_SOURCE].warnings == ()

    older = (
        NOW - timedelta(hours=au.SA_STALE_AFTER_HOURS, seconds=1)
    ).isoformat(timespec="seconds")
    _set_current_refresh(databases.sa_path, last_success_at=older, ok=1)

    stale = _snapshot(databases)

    assert stale.tickers == ("AAPL",)
    assert stale.source_status[SA_SOURCE].last_success_at == older
    assert stale.source_status[SA_SOURCE].warnings == ("stale_refresh",)


def test_exact_hidden_veto_distinguishes_brk_dot_b_from_brk_space_b(databases):
    _active_universe()
    databases.profile.import_lists(
        [{"name": "Berkshire", "tickers": ["BRK.B", "BRK B"]}]
    )
    databases.profile.set_universe_hidden("BRK.B", True)

    snapshot = _snapshot(databases)

    assert snapshot.tickers == ("BRK B",)
    assert snapshot.sources_by_ticker == {"BRK B": ("manual_lists",)}


def test_legacy_config_seed_is_a_direct_source_not_an_annotation(databases):
    _active_universe()
    databases.profile.replace_legacy_config_import(
        approved_memberships=[" seed "],
        annotations=[
            UniverseSourceAnnotation(
                source_key=LEGACY_SOURCE,
                ticker="ANNOTATED_ONLY",
                annotation_key="legacy_tier",
                annotation_value="tier1_core",
            )
        ],
    )

    snapshot = _snapshot(databases)

    assert snapshot.tickers == ("SEED",)
    assert snapshot.sources_by_ticker == {"SEED": (LEGACY_SOURCE,)}


def test_complete_empty_sources_return_an_empty_snapshot(databases):
    au = _active_universe()

    snapshot = _snapshot(databases)

    assert snapshot.tickers == ()
    assert snapshot.sources_by_ticker == {}
    assert tuple(snapshot.source_status) == tuple(sorted(au.SOURCE_KEYS))
    assert all(status.available for status in snapshot.source_status.values())
    assert snapshot.source_status[SA_SOURCE].warnings == ("never_refreshed",)
    assert snapshot.unavailable_sources == ()
    assert snapshot.generated_at == NOW_TEXT


def test_missing_profile_db_reports_three_profile_sources_without_paths(
    tmp_path, monkeypatch
):
    au = _active_universe()
    sa_path = tmp_path / "sa_capture.db"
    sa_capture_store.connect(str(sa_path)).close()
    missing = tmp_path / "DO_NOT_LEAK_PROFILE_TOKEN.db"
    profile_sources = tuple(key for key in au.SOURCE_KEYS if key != SA_SOURCE)
    missing_reasons = {key: "source_db_missing" for key in profile_sources}

    with pytest.raises(au.ActiveUniverseUnavailable) as caught:
        au.build_active_universe_snapshot(
            profile_db=missing, sa_db=sa_path, now=NOW
        )

    _assert_sanitized_unavailable(
        caught.value, missing_reasons, missing, "DO_NOT_LEAK_PROFILE_TOKEN"
    )
    assert isinstance(caught.value.__cause__, FileNotFoundError)
    assert not missing.exists()

    missing_schema = tmp_path / "profile_missing_schema.db"
    with sqlite3.connect(missing_schema) as conn:
        conn.execute("CREATE TABLE unrelated(value TEXT)")
    schema_reasons = {key: "required_schema_missing" for key in profile_sources}
    with pytest.raises(au.ActiveUniverseUnavailable) as caught_schema:
        au.build_active_universe_snapshot(
            profile_db=missing_schema, sa_db=sa_path, now=NOW
        )
    _assert_sanitized_unavailable(
        caught_schema.value, schema_reasons, missing_schema
    )

    profile_path = tmp_path / "profile_state.db"
    ProfileStateStore(profile_path)
    PortfolioStore(profile_path)
    real_open = au._open_read_only
    hostile_token = f"DO_NOT_LEAK_ERROR:{tmp_path}"

    def fail_profile(path):
        if Path(path) == profile_path:
            raise sqlite3.DatabaseError(hostile_token)
        return real_open(path)

    with monkeypatch.context() as patch:
        patch.setattr(au, "_open_read_only", fail_profile)
        with pytest.raises(au.ActiveUniverseUnavailable) as caught_unreadable:
            au.build_active_universe_snapshot(
                profile_db=profile_path, sa_db=sa_path, now=NOW
            )
    unreadable_reasons = {key: "source_db_unreadable" for key in profile_sources}
    _assert_sanitized_unavailable(
        caught_unreadable.value, unreadable_reasons, hostile_token, tmp_path
    )
    assert isinstance(caught_unreadable.value.__cause__, sqlite3.DatabaseError)

    filtered = au.ActiveUniverseUnavailable(
        {"not_a_source": hostile_token, SA_SOURCE: hostile_token}
    )
    _assert_sanitized_unavailable(
        filtered, {SA_SOURCE: "source_db_unreadable"}, hostile_token, tmp_path
    )


def test_missing_sa_db_reports_only_alpha_source_without_fake_empty(
    tmp_path, databases
):
    au = _active_universe()
    missing = tmp_path / "DO_NOT_LEAK_SA_TOKEN.db"

    with pytest.raises(au.ActiveUniverseUnavailable) as caught:
        au.build_active_universe_snapshot(
            profile_db=databases.profile_path,
            sa_db=missing,
            now=NOW,
        )

    _assert_sanitized_unavailable(
        caught.value,
        {SA_SOURCE: "source_db_missing"},
        missing,
        "DO_NOT_LEAK_SA_TOKEN",
    )
    assert isinstance(caught.value.__cause__, FileNotFoundError)
    assert not missing.exists()

    missing_schema = tmp_path / "sa_missing_schema.db"
    with sqlite3.connect(missing_schema) as conn:
        conn.execute("CREATE TABLE unrelated(value TEXT)")
    with pytest.raises(au.ActiveUniverseUnavailable) as caught_schema:
        au.build_active_universe_snapshot(
            profile_db=databases.profile_path,
            sa_db=missing_schema,
            now=NOW,
        )
    _assert_sanitized_unavailable(
        caught_schema.value,
        {SA_SOURCE: "required_schema_missing"},
        missing_schema,
    )

    unreadable = tmp_path / "DO_NOT_LEAK_CORRUPT_SA_TOKEN.db"
    unreadable.write_bytes(b"not sqlite: DO_NOT_LEAK_CORRUPT_SA_TOKEN")
    with pytest.raises(au.ActiveUniverseUnavailable) as caught_unreadable:
        au.build_active_universe_snapshot(
            profile_db=databases.profile_path,
            sa_db=unreadable,
            now=NOW,
        )
    _assert_sanitized_unavailable(
        caught_unreadable.value,
        {SA_SOURCE: "source_db_unreadable"},
        unreadable,
        "DO_NOT_LEAK_CORRUPT_SA_TOKEN",
    )


def test_read_paths_use_mode_ro_query_only_and_create_no_files(
    databases, tmp_path, monkeypatch
):
    au = _active_universe()
    original_connect = sqlite3.connect
    opened = []

    class RecordingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            self.recorded_sql.append(sql)
            return super().execute(sql, parameters)

    def recording_connect(database, *args, **kwargs):
        assert "factory" not in kwargs
        conn = original_connect(
            database, *args, factory=RecordingConnection, **kwargs
        )
        conn.recorded_sql = []
        opened.append((database, dict(kwargs), conn))
        return conn

    with monkeypatch.context() as patch:
        patch.setattr(au.sqlite3, "connect", recording_connect)
        snapshot = _snapshot(databases)

    assert snapshot.tickers == ()
    assert len(opened) == 2
    for database, kwargs, conn in opened:
        assert str(database).endswith("?mode=ro")
        assert kwargs.get("uri") is True
        assert "PRAGMA query_only=ON" in conn.recorded_sql
        assert "BEGIN" in conn.recorded_sql

    missing_profile = tmp_path / "absent" / "profile_state.db"
    missing_sa = tmp_path / "absent" / "sa_capture.db"
    with pytest.raises(au.ActiveUniverseUnavailable) as caught:
        au.build_active_universe_snapshot(
            profile_db=missing_profile,
            sa_db=missing_sa,
            now=NOW,
        )
    assert caught.value.unavailable_sources == au.SOURCE_KEYS
    assert not missing_profile.exists()
    assert not missing_sa.exists()


def test_resolve_active_universe_is_a_thin_complete_snapshot_adapter(monkeypatch):
    _active_universe()
    scope = importlib.import_module("src.universe_scope")
    calls = []

    def build_snapshot():
        calls.append(True)
        return SimpleNamespace(tickers=("AAPL", "MSFT"))

    monkeypatch.setattr(scope, "build_active_universe_snapshot", build_snapshot)

    assert scope.resolve_active_universe() == ["AAPL", "MSFT"]
    assert calls == [True]
