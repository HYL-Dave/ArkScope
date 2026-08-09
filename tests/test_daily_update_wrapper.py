"""Smoke tests for the daily_update thin CLI wrapper (3e-E / F6).

Subprocess-level (the wrapper is a script): pins the flag-compatible + same-
effects gate — flag set, dry-run plan step set, explicit-scope errors, exit
codes. No test here touches IBKR, the DB, or job_runs (dry-run / error paths
only).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src import sa_capture_store
from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore

_MODULE = "src.daily_update"


@pytest.fixture()
def universe_dbs(tmp_path: Path) -> dict[str, str]:
    profile_db = tmp_path / "profile_state.db"
    sa_db = tmp_path / "sa_capture.db"

    profile = ProfileStateStore(profile_db)
    profile.import_lists([{"name": "Core", "tickers": ["AAPL", "NVDA"]}])
    portfolio = PortfolioStore(profile_db)
    account = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="MSFT",
        quantity=1,
    )
    sa_conn = sa_capture_store.connect(str(sa_db))
    sa_conn.close()

    return {"profile_db": str(profile_db), "sa_db": str(sa_db)}


def _run(
    *flags: str,
    profile_db: str | None = None,
    sa_db: str | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if profile_db is not None:
        env["ARKSCOPE_PROFILE_DB"] = profile_db
    if sa_db is not None:
        env["ARKSCOPE_SA_DB"] = sa_db
    return subprocess.run([sys.executable, "-m", _MODULE, *flags],
                          capture_output=True, text=True, timeout=120, env=env)


def test_help_exits_zero_with_full_flag_set():
    r = _run("--help")
    assert r.returncode == 0
    for flag in ("--status", "--all", "--news", "--polygon", "--finnhub",
                 "--ibkr-news", "--ibkr-prices", "--dry-run",
                 "--parallel", "--quiet",
                 "--tickers", "--scope"):
        assert flag in r.stdout, f"flag {flag} missing from --help"
    assert "--iv-history" not in r.stdout
    assert "--sync-db" not in r.stdout
    assert "--scores" not in r.stdout


def test_protected_command_dry_run_plan(universe_dbs):
    # The protected gate command in plan-only mode: same source step set as the
    # active direct collectors (news x3 + prices), exit 0.
    r = _run(
        "--all",
        "--scope",
        "active-universe",
        "--dry-run",
        profile_db=universe_dbs["profile_db"],
        sa_db=universe_dbs["sa_db"],
    )
    out = r.stdout + r.stderr
    assert r.returncode == 0
    for source in ("polygon_news", "finnhub_news", "ibkr_news", "ibkr_prices"):
        assert source in out
    assert "iv_history" not in out
    assert "db sync" not in out
    assert "local mirror refresh" not in out
    assert "Dry run complete" in out


def test_dry_run_reports_direct_local_collection_without_mirror_controls():
    r = _run("--news", "--tickers", "AAPL", "--dry-run")
    out = r.stdout + r.stderr
    assert r.returncode == 0
    assert "polygon_news" in out and "ibkr_prices" not in out
    assert "db sync" not in out
    assert "local mirror refresh" not in out
    assert "collect (only)" not in out


def test_no_scope_errors():
    r = _run("--news", "--dry-run")
    assert r.returncode == 1
    assert "explicit ticker scope required" in (r.stdout + r.stderr)


def test_daily_update_unavailable_scope_exits_before_any_source(
    universe_dbs, tmp_path, monkeypatch,
):
    missing_sa = tmp_path / "missing-sa-capture.db"
    assert not missing_sa.exists()

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", universe_dbs["profile_db"])
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(missing_sa))

    import src.daily_update as daily_update
    import src.env_keys as env_keys
    import src.service.data_scheduler as data_scheduler

    calls = {"ensure_env": 0, "source": 0, "telemetry": 0}

    def _must_not_run(name):
        def _fail(*args, **kwargs):
            calls[name] += 1
            raise AssertionError(f"{name} must not run for unavailable scope")
        return _fail

    monkeypatch.setattr(env_keys, "ensure_env_loaded", _must_not_run("ensure_env"))
    monkeypatch.setattr(data_scheduler, "run_source", _must_not_run("source"))
    monkeypatch.setattr(daily_update, "_RunTelemetry", _must_not_run("telemetry"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["daily_update", "--all", "--scope", "active-universe"],
    )

    with pytest.raises(SystemExit) as caught:
        daily_update.main()

    assert caught.value.code == 1
    assert calls == {"ensure_env": 0, "source": 0, "telemetry": 0}

    result = _run(
        "--all",
        "--scope",
        "active-universe",
        "--dry-run",
        profile_db=universe_dbs["profile_db"],
        sa_db=str(missing_sa),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "active_universe_unavailable: sa_alpha_picks_current" in output
    assert str(missing_sa) not in output
    assert "Traceback" not in output


def test_price_status_uses_sqlite_stats_without_scanning_repository_files(monkeypatch):
    import src.daily_update as daily_update

    stats = {
        "exists": True,
        "prices": {
            "row_count": 321,
            "ticker_count": 7,
            "latest_datetime": "2026-07-31T19:45:00+0000",
        },
    }
    monkeypatch.setattr(
        daily_update,
        "local_market_stats",
        lambda: stats,
        raising=False,
    )

    def _must_not_scan(*_args, **_kwargs):
        raise AssertionError("retired repository price paths must not be scanned")

    real_exists = Path.exists
    real_glob = Path.glob
    real_rglob = Path.rglob

    def _is_retired_price_path(path):
        text = str(path)
        return text == "data/prices" or text.startswith("data/prices/")

    def _guarded_exists(path):
        if _is_retired_price_path(path):
            return _must_not_scan(path)
        return real_exists(path)

    def _guarded_glob(path, pattern):
        if _is_retired_price_path(path):
            return _must_not_scan(path, pattern)
        return real_glob(path, pattern)

    def _guarded_rglob(path, pattern):
        if _is_retired_price_path(path):
            return _must_not_scan(path, pattern)
        return real_rglob(path, pattern)

    monkeypatch.setattr(Path, "exists", _guarded_exists)
    monkeypatch.setattr(Path, "glob", _guarded_glob)
    monkeypatch.setattr(Path, "rglob", _guarded_rglob)
    monkeypatch.setattr(pd, "read_csv", _must_not_scan)
    monkeypatch.setattr(pd, "read_parquet", _must_not_scan)

    assert daily_update.get_ibkr_prices_status() == {
        "exists": True,
        "total_bars": 321,
        "latest_date": date(2026, 7, 31),
        "tickers": 7,
    }
