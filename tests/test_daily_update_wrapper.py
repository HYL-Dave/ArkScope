"""Smoke tests for the daily_update thin CLI wrapper (3e-E / F6).

Subprocess-level (the wrapper is a script): pins the flag-compatible + same-
effects gate — flag set, dry-run plan step set, explicit-scope errors, exit
codes. No test here touches IBKR, the DB, or job_runs (dry-run / error paths
only).
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

_SCRIPT = str(Path(__file__).resolve().parents[1] / "scripts" / "collection" / "daily_update.py")


def _profile_db(tmp_path: Path) -> str:
    db = tmp_path / "profile_state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE watchlist_memberships (ticker TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO watchlist_memberships (ticker) VALUES (?)",
            [("AAPL",), ("NVDA",)],
        )
        conn.commit()
    finally:
        conn.close()
    return str(db)


def _run(*flags: str, profile_db: str | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if profile_db is not None:
        env["ARKSCOPE_PROFILE_DB"] = profile_db
    return subprocess.run([sys.executable, _SCRIPT, *flags],
                          capture_output=True, text=True, timeout=120, env=env)


def test_help_exits_zero_with_full_flag_set():
    r = _run("--help")
    assert r.returncode == 0
    for flag in ("--status", "--all", "--news", "--polygon", "--finnhub",
                 "--ibkr-news", "--ibkr-prices", "--iv-history", "--dry-run",
                 "--parallel", "--quiet", "--sync-db", "--scores",
                 "--tickers", "--scope"):
        assert flag in r.stdout, f"flag {flag} missing from --help"


def test_protected_command_dry_run_plan(tmp_path):
    # The protected gate command in plan-only mode: same source step set as the
    # pre-wrapper orchestrator (news x3 + prices; IV stays opt-in), exit 0.
    r = _run(
        "--all",
        "--scope",
        "active-universe",
        "--sync-db",
        "--dry-run",
        profile_db=_profile_db(tmp_path),
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
