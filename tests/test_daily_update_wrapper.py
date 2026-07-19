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
from pathlib import Path

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
                 "--ibkr-news", "--ibkr-prices", "--iv-history", "--dry-run",
                 "--parallel", "--quiet", "--sync-db", "--scores",
                 "--tickers", "--scope"):
        assert flag in r.stdout, f"flag {flag} missing from --help"


def test_protected_command_dry_run_plan(universe_dbs):
    # The protected gate command in plan-only mode: same source step set as the
    # pre-wrapper orchestrator (news x3 + prices; IV stays opt-in), exit 0.
    r = _run(
        "--all",
        "--scope",
        "active-universe",
        "--sync-db",
        "--dry-run",
        profile_db=universe_dbs["profile_db"],
        sa_db=universe_dbs["sa_db"],
    )
    out = r.stdout + r.stderr
    assert r.returncode == 0
    for source in ("polygon_news", "finnhub_news", "ibkr_news", "ibkr_prices"):
        assert source in out
    assert "iv_history" not in out          # --all never sweeps IV
    assert "db sync" in out                  # --sync-db reflected in the plan
    assert "Dry run complete" in out


def test_dry_run_without_sync_db_collect_only():
    r = _run("--news", "--tickers", "AAPL", "--dry-run")
    out = r.stdout + r.stderr
    assert r.returncode == 0
    assert "polygon_news" in out and "ibkr_prices" not in out
    assert "db sync" not in out              # collect-only: PG sync skipped
    # TRUE collect-only: the plan must not promise a local mirror refresh either
    # (PG untouched → nothing to mirror; run_source skips it when skip_sync=True)
    assert "local mirror refresh" not in out
    assert "collect (only)" in out


def test_no_scope_errors():
    r = _run("--news", "--dry-run")
    assert r.returncode == 1
    assert "explicit ticker scope required" in (r.stdout + r.stderr)


def test_iv_history_opt_in_only():
    r = _run("--iv-history", "--tickers", "AAPL", "--dry-run")
    out = r.stdout + r.stderr
    assert r.returncode == 0
    assert "iv_history" in out and "polygon_news" not in out


def test_scores_flag_is_retired_and_does_not_shell_to_pg_importer():
    r = _run("--scores", "--dry-run")
    out = r.stdout + r.stderr
    assert r.returncode != 0
    assert "retired" in out.lower()
    assert "migrate_to_supabase" not in out


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
