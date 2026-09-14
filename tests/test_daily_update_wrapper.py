"""CLI routing and read-only news status, using disposable local stores only."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import closing
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
    for flag in ("--status", "--all", "--news", "--massive", "--finnhub",
                 "--ibkr-news", "--ibkr-prices", "--dry-run",
                 "--parallel", "--quiet",
                 "--tickers", "--scope"):
        assert flag in r.stdout, f"flag {flag} missing from --help"
    assert re.search(
        r"(?m)^  --massive\s+Update Massive news only$",
        r.stdout,
    )
    assert "--polygon" not in r.stdout
    assert "--iv-history" not in r.stdout
    assert "--sync-db" not in r.stdout
    assert "--scores" not in r.stdout


@pytest.mark.parametrize("flag", ["--massive", "--polygon"])
def test_massive_flag_and_hidden_legacy_alias_select_the_same_source(flag):
    result = _run(flag, "--tickers", "AAPL", "--dry-run")

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "polygon_news: direct-local collect" in output
    assert "finnhub_news" not in output


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


@pytest.fixture
def status_cli(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    for key, filename in (
        ("ARKSCOPE_MARKET_DB", "market_data.db"),
        ("ARKSCOPE_PROFILE_DB", "profile_state.db"),
        ("ARKSCOPE_SA_DB", "sa_capture.db"),
        ("ARKSCOPE_LOCK_DIR", "locks"),
    ):
        monkeypatch.setenv(key, str(tmp_path / filename))

    import src.daily_update as daily_update
    import src.env_keys as env_keys
    import src.service.data_scheduler as data_scheduler

    def forbidden(*args, **kwargs):
        pytest.fail("status/scope guard reached environment loading or collection")

    monkeypatch.setattr(env_keys, "ensure_env_loaded", forbidden)
    monkeypatch.setattr(data_scheduler, "run_source", forbidden)
    caplog.set_level(logging.INFO, logger=daily_update.__name__)
    return daily_update


class _NewsFixtureProvider:
    def __init__(self, source):
        self.source = source

    def fetch_news(self, ticker, since_iso):
        if ticker == "BAD":
            raise RuntimeError("fixture ticker unavailable")
        return [{
            "ticker": ticker,
            "title": f"Fixture news for {ticker}",
            "published_at": f"{date.today().isoformat()}T10:00:00Z",
            "article_hash": f"{self.source}-{ticker}",
            "description": "Retained fixture article",
            "url": f"https://example.invalid/{self.source}/{ticker}",
            "publisher": "Fixture Wire",
        }]

    def fetch_articles(self, ticker, since_iso):
        from src.news_normalized.models import ArticleCandidate, BodyCandidate, BodyStatus

        row = self.fetch_news(ticker, since_iso)[0]
        return [ArticleCandidate(
            source=self.source,
            provider_article_id=row["article_hash"],
            title=row["title"],
            published_at=row["published_at"],
            publisher=row["publisher"],
            url=row["url"],
            primary_ticker=ticker,
            related_tickers=(ticker,),
            content_kind="headline_only",
            body=BodyCandidate(status=BodyStatus.UNAVAILABLE),
        )]

    def fetch_body(self, article):
        pytest.fail("headline fixture must not request a provider body")


def _write_news_fixture(path, writer, source, tickers):
    provider = _NewsFixtureProvider(source)
    if writer == "direct":
        from src.news_direct import backfill_news_direct

        return backfill_news_direct(
            tickers, source=source, provider=provider, db_path=str(path),
        )

    from src.news_normalized.models import WriterBudget
    from src.news_normalized.store import NormalizedNewsStore
    from src.news_normalized.writer import write_news_batch

    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        return write_news_batch(
            NormalizedNewsStore(conn), provider, tickers,
            WriterBudget(max_articles=10, max_body_fetches=0),
        )


@pytest.mark.parametrize("error", [
    "provider failed: Bearer synthetic-token-123456",
    "provider failed: api_key=AbCdEf0123456789Synthetic",
])
def test_status_redacts_stored_provider_diagnostics_without_mutating_them(
    status_cli, tmp_path, caplog, error,
):
    from src.market_data_direct import _ensure_provider_sync_tables

    path = tmp_path / "market_data.db"
    with closing(sqlite3.connect(path)) as conn:
        _ensure_provider_sync_tables(conn)
        conn.execute(
            "INSERT INTO provider_sync_runs "
            "(provider,domain,interval,started_at,finished_at,status,error) "
            "VALUES ('polygon','news','news',?,?,'failed',?)",
            ("2026-09-14T10:00:00Z", "2026-09-14T10:01:00Z", error),
        )
        conn.commit()
    before = path.read_bytes()

    status_cli.show_status()

    section = _news_section(caplog, "MASSIVE")
    assert error not in caplog.text
    assert "[REDACTED]" in section
    assert "provider failed:" in section
    assert "Recorded collection status: failed" in section
    assert "2026-09-14T10:01:00Z" in section
    assert path.read_bytes() == before


def _news_section(caplog, label):
    output = "\n".join(
        record.getMessage() for record in caplog.records
        if record.name == _MODULE
    )
    return output.split(f"{label} NEWS", 1)[1].split("\n\n", 1)[0]


@pytest.mark.parametrize("writer,source,label", [
    ("direct", "polygon", "MASSIVE"),
    ("normalized", "finnhub", "FINNHUB"),
])
@pytest.mark.parametrize("partial", [False, True])
def test_status_reads_real_writer_telemetry_once_and_retains_articles(
    status_cli, tmp_path, monkeypatch, caplog, writer, source, label, partial,
):
    import src.market_data_direct as market_data_direct
    import src.news_sync_status as news_sync_status

    path = tmp_path / "market_data.db"
    monkeypatch.setattr(market_data_direct, "_now", lambda: "2026-09-13T09:00:00+00:00")
    _write_news_fixture(path, writer, source, ["AAPL"])
    monkeypatch.setattr(market_data_direct, "_now", lambda: "2026-09-14T10:00:00+00:00")
    _write_news_fixture(path, writer, source, ["MSFT", "BAD"] if partial else ["MSFT"])
    before = path.read_bytes()
    calls = []
    real_reader = news_sync_status.read_news_sync_status

    def read_status(db_path):
        calls.append(str(db_path))
        return real_reader(db_path)

    monkeypatch.setattr(news_sync_status, "read_news_sync_status", read_status)
    monkeypatch.setattr(sys, "argv", ["daily_update", "--status"])

    assert status_cli.main() is None

    assert calls == [str(path)]
    section = _news_section(caplog, label)
    expected_status = "partial" if partial else "succeeded"
    assert re.search(rf"Recorded collection status:\s+{expected_status}\b", section)
    assert re.search(r"Last attempt:\s+2026-09-14T10:00:00\+00:00", section)
    assert re.search(r"Last success:\s+2026-09-14T10:00:00\+00:00", section)
    assert re.search(r"Rows added by run:\s+1\b", section)
    if partial:
        assert "BAD: fixture ticker unavailable" in section
    assert "Total articles" not in section
    assert "up to date" not in caplog.text.lower()
    assert "only provides ~7 days" not in caplog.text
    assert "~1 month" not in caplog.text
    assert path.read_bytes() == before


@pytest.mark.parametrize("status,finished_at,attempt", [
    ("failed", "2026-09-14T11:01:00Z", "2026-09-14T11:01:00Z"),
    ("running", None, "2026-09-14T11:00:00Z"),
    ("succeeded", "2026-09-14T11:01:00Z", "2026-09-14T11:01:00Z"),
])
def test_status_reports_latest_run_not_historical_rows_or_price_telemetry(
    status_cli, tmp_path, caplog, status, finished_at, attempt,
):
    from src.market_data_direct import _ensure_provider_sync_tables

    path = tmp_path / "market_data.db"
    with closing(sqlite3.connect(path)) as conn:
        _ensure_provider_sync_tables(conn)
        conn.executemany(
            "INSERT INTO provider_sync_runs "
            "(provider,domain,interval,started_at,finished_at,rows_added,status,error) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                ("ibkr", "news", "news", "2026-09-13T09:00:00Z",
                 "2026-09-13T09:01:00Z", 91, "succeeded", None),
                ("ibkr", "news", "news", "2026-09-14T11:00:00Z",
                 finished_at, 0, status, "fixture run interrupted" if status == "failed" else None),
                ("ibkr", "prices", "15min", "2026-09-14T12:00:00Z",
                 "2026-09-14T12:01:00Z", 888, "succeeded", None),
            ],
        )
        conn.commit()
    before = path.read_bytes()

    status_cli.show_status()

    section = _news_section(caplog, "IBKR")
    last_success = finished_at if status == "succeeded" else "2026-09-13T09:01:00Z"
    assert re.search(rf"Recorded collection status:\s+{status}\b", section)
    assert re.search(rf"Last attempt:\s+{attempt}", section)
    assert re.search(rf"Last success:\s+{last_success}", section)
    assert re.search(r"Rows added by run:\s+0\b", section)
    assert "888" not in section
    assert "up to date" not in caplog.text.lower()
    if status == "failed":
        assert "fixture run interrupted" in section
    assert path.read_bytes() == before


def test_status_meta_only_error_does_not_invent_an_aggregate_run(
    status_cli, tmp_path, caplog,
):
    from src.market_data_direct import _ensure_provider_sync_tables

    path = tmp_path / "market_data.db"
    with closing(sqlite3.connect(path)) as conn:
        _ensure_provider_sync_tables(conn)
        conn.execute(
            "INSERT INTO provider_sync_meta "
            "(provider,ticker,interval,last_error,updated_at) "
            "VALUES ('polygon','BAD','news','fixture ticker unavailable',"
            "'2026-09-14T10:00:00Z')"
        )
        conn.commit()
    before = path.read_bytes()

    status_cli.show_status()

    section = _news_section(caplog, "MASSIVE")
    assert re.search(r"Recorded collection status:\s+partial\b", section)
    assert "Recorded run status" not in section
    for field in ("Last attempt", "Last success", "Rows added by run"):
        assert re.search(rf"{field}:\s+Not recorded\b", section)
    assert "BAD: fixture ticker unavailable" in section
    assert path.read_bytes() == before


@pytest.mark.parametrize("store_state", [
    "missing", "no-tables", "empty-telemetry", "articles-without-telemetry",
])
def test_status_without_telemetry_does_not_claim_no_articles(
    status_cli, tmp_path, monkeypatch, caplog, store_state,
):
    from src.market_data_direct import _ensure_provider_sync_tables

    path = tmp_path / "market_data.db"
    if store_state == "articles-without-telemetry":
        _write_news_fixture(path, "direct", "polygon", ["AAPL"])
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("DROP TABLE provider_sync_runs")
            conn.execute("DROP TABLE provider_sync_meta")
            conn.commit()
    elif store_state != "missing":
        with closing(sqlite3.connect(path)) as conn:
            if store_state == "empty-telemetry":
                _ensure_provider_sync_tables(conn)
            conn.commit()
    before = path.read_bytes() if path.exists() else None
    monkeypatch.setattr(sys, "argv", ["daily_update"])

    assert status_cli.main() is None

    for label in ("MASSIVE", "FINNHUB", "IBKR"):
        section = _news_section(caplog, label).lower()
        assert "no recorded telemetry" in section
        assert "no data" not in section
        assert "total articles" not in section
        assert "rows added" not in section
        assert "succeeded" not in section
    if before is None:
        assert not path.exists()
    else:
        assert path.read_bytes() == before


@pytest.mark.parametrize("malformed", ["schema", "rows"])
def test_status_malformed_telemetry_is_unavailable_not_empty_or_successful(
    status_cli, tmp_path, caplog, malformed,
):
    from src.market_data_direct import _ensure_provider_sync_tables

    path = tmp_path / "market_data.db"
    with closing(sqlite3.connect(path)) as conn:
        if malformed == "schema":
            conn.execute("CREATE TABLE provider_sync_runs (id INTEGER)")
        else:
            _ensure_provider_sync_tables(conn)
            conn.execute(
                "INSERT INTO provider_sync_runs "
                "(provider,domain,interval,started_at,rows_added,status) "
                "VALUES ('polygon','news','news','2026-09-14T10:00:00Z',"
                "'not-a-count','succeeded')"
            )
        conn.commit()
    before = path.read_bytes()

    status_cli.show_status()

    for label in ("MASSIVE", "FINNHUB", "IBKR"):
        section = _news_section(caplog, label).lower()
        assert "status unavailable" in section
        assert "no recorded telemetry" not in section
        assert "no data" not in section
        assert "rows added" not in section
        assert "succeeded" not in section
    assert "not-a-count" not in caplog.text
    assert str(path) not in caplog.text
    assert path.read_bytes() == before


def test_status_never_scans_retained_parquet_archives(
    status_cli, tmp_path, monkeypatch, caplog,
):
    _write_news_fixture(tmp_path / "market_data.db", "direct", "polygon", ["AAPL"])
    archive_root = tmp_path / "data" / "news" / "raw"
    for source in ("polygon", "finnhub", "ibkr"):
        archive = archive_root / source / "2022" / "old.parquet"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"retained archive sentinel")

    def forbidden_parquet(*args, **kwargs):
        pytest.fail("news status must not read retained Parquet archives")

    def guard(method):
        def checked(path, *args, **kwargs):
            absolute = path.absolute()
            if absolute == archive_root or archive_root in absolute.parents:
                pytest.fail("news status must not inspect retained archive paths")
            return method(path, *args, **kwargs)
        return checked

    for name in ("exists", "iterdir", "glob", "rglob"):
        monkeypatch.setattr(Path, name, guard(getattr(Path, name)))
    monkeypatch.setattr(pd, "read_parquet", forbidden_parquet)

    status_cli.show_status()

    assert "succeeded" in _news_section(caplog, "MASSIVE")
    assert "no recorded telemetry" in _news_section(caplog, "FINNHUB").lower()
    for source in ("polygon", "finnhub", "ibkr"):
        assert (archive_root / source / "2022" / "old.parquet").read_bytes() == b"retained archive sentinel"


def test_recent_articles_and_successful_runs_do_not_prove_news_completeness(
    status_cli, tmp_path, monkeypatch, caplog,
):
    for source in ("polygon", "finnhub", "ibkr"):
        _write_news_fixture(tmp_path / "market_data.db", "direct", source, ["AAPL"])
        archive = tmp_path / "data" / "news" / "raw" / source / "2026" / "recent.parquet"
        archive.parent.mkdir(parents=True)
        archive.touch()
    monkeypatch.setattr(
        pd, "read_parquet",
        lambda *args, **kwargs: pd.DataFrame({"published_at": [date.today().isoformat()]}),
    )

    status_cli.show_status()

    assert "up to date" not in caplog.text.lower()
    assert "only provides ~7 days" not in caplog.text
    assert "~1 month" not in caplog.text
    for label in ("MASSIVE", "FINNHUB", "IBKR"):
        assert "succeeded" in _news_section(caplog, label)
    for command in re.findall(r"python -m src\.daily_update[^\n]*", caplog.text):
        assert "--scope active-universe" in command or "--tickers" in command


@pytest.fixture
def collection_cli(status_cli, tmp_path, monkeypatch):
    import src.env_keys as env_keys
    import src.tools.data_access as data_access

    real_dal = data_access.DataAccessLayer
    monkeypatch.setattr(data_access, "DataAccessLayer", lambda: real_dal(base_path=tmp_path))
    monkeypatch.setattr(env_keys, "ensure_env_loaded", lambda: None)
    return status_cli


@pytest.mark.parametrize("flags,sources", [
    (["--massive"], ["polygon_news"]),
    (["--polygon"], ["polygon_news"]),
    (["--finnhub"], ["finnhub_news"]),
    (["--ibkr-news"], ["ibkr_news"]),
    (["--ibkr-prices"], ["ibkr_prices"]),
    (["--massive", "--finnhub"], ["polygon_news", "finnhub_news"]),
    (["--news"], ["polygon_news", "finnhub_news", "ibkr_news"]),
    (["--all"], ["polygon_news", "finnhub_news", "ibkr_news", "ibkr_prices"]),
    (["--all", "--parallel"], ["polygon_news", "finnhub_news", "ibkr_news", "ibkr_prices"]),
])
@pytest.mark.parametrize("active_scope", [False, True])
def test_main_routes_sources_and_scope_and_records_real_summary(
    collection_cli, universe_dbs, tmp_path, monkeypatch, flags, sources, active_scope,
):
    import src.service.data_scheduler as data_scheduler

    calls = []

    def run_source(source, *, trigger_source, tickers):
        calls.append((source, trigger_source, tuple(tickers)))
        return {"status": "succeeded"}

    monkeypatch.setattr(data_scheduler, "run_source", run_source)
    scope_flags = ["--scope", "active-universe"] if active_scope else ["--tickers", " aapl, msft ,, "]
    monkeypatch.setattr(sys, "argv", ["daily_update", *flags, *scope_flags])

    with pytest.raises(SystemExit) as caught:
        collection_cli.main()

    assert caught.value.code == 0
    tickers = ("AAPL", "MSFT", "NVDA") if active_scope else ("AAPL", "MSFT")
    expected_calls = [(source, "cli", tickers) for source in sources]
    assert (sorted(calls) if "--parallel" in flags else calls) == (
        sorted(expected_calls) if "--parallel" in flags else expected_calls
    )
    with closing(sqlite3.connect(universe_dbs["profile_db"])) as conn:
        rows = conn.execute(
            "SELECT job_name,status,trigger_source,payload,started_at,finished_at "
            "FROM job_runs ORDER BY id"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][:3] == ("daily_update.run", "succeeded", "cli")
    payload = json.loads(rows[0][3])
    assert payload["ticker_count"] == len(tickers)
    assert payload["scope"] == ("active-universe" if active_scope else None)
    assert payload["tickers"] == (None if active_scope else " aapl, msft ,, ")
    assert payload["flags"]["parallel"] == ("--parallel" in flags)
    assert rows[0][4] <= rows[0][5]


@pytest.mark.parametrize("outcome,exit_code,summary_status", [
    ("succeeded", 0, "succeeded"),
    ("partial", 1, "failed"),
    ("failed", 1, "failed"),
    ("skipped", 1, "failed"),
])
def test_main_retains_news_and_job_telemetry_and_preserves_outcome_exit_codes(
    collection_cli, tmp_path, monkeypatch, caplog, outcome, exit_code, summary_status,
):
    import src.service.data_scheduler as data_scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    path = tmp_path / "market_data.db"
    _write_news_fixture(path, "direct", "polygon", ["AAPL", "BAD"])
    before = path.read_bytes()
    profile_path = tmp_path / "profile_state.db"
    store = JobRunsLocalStore(profile_path)
    store.record_completed_run(
        "collect.polygon_news", status="succeeded", trigger_source="scheduler",
        started_at="2026-09-13T09:00:00Z", finished_at="2026-09-13T09:01:00Z",
        payload={"retained": True},
    )
    with closing(sqlite3.connect(profile_path)) as conn:
        retained_job = conn.execute("SELECT * FROM job_runs").fetchone()
    calls = []

    def run_source(source, *, trigger_source, tickers):
        calls.append((source, trigger_source, tickers))
        return {"status": outcome if source == "finnhub_news" else "succeeded",
                "reason": "fixture source busy" if outcome == "skipped" else None}

    monkeypatch.setattr(data_scheduler, "run_source", run_source)
    monkeypatch.setattr(sys, "argv", ["daily_update", "--news", "--tickers", "AAPL"])

    with pytest.raises(SystemExit) as caught:
        collection_cli.main()

    assert caught.value.code == exit_code
    assert calls == [
        ("polygon_news", "cli", ["AAPL"]),
        ("finnhub_news", "cli", ["AAPL"]),
        ("ibkr_news", "cli", ["AAPL"]),
    ]
    with closing(sqlite3.connect(profile_path)) as conn:
        assert conn.execute("SELECT * FROM job_runs ORDER BY id LIMIT 1").fetchone() == retained_job
        summary = conn.execute(
            "SELECT status,trigger_source,payload,error FROM job_runs "
            "WHERE job_name='daily_update.run'"
        ).fetchone()
    assert summary[:2] == (summary_status, "cli")
    assert json.loads(summary[2])["flags"]["news"] is True
    assert (summary[3] is None) == (exit_code == 0)
    assert "partial" in _news_section(caplog, "MASSIVE")
    if outcome == "skipped":
        assert "fixture source busy" in caplog.text
    assert path.read_bytes() == before


@pytest.mark.parametrize("flags,exit_code", [
    (["--news"], 1),
    (["--all", "--scope", "active-universe"], 1),
    (["--news", "--tickers", "AAPL", "--dry-run"], 0),
])
def test_main_scope_and_dry_run_guards_precede_environment_provider_and_telemetry(
    status_cli, tmp_path, monkeypatch, flags, exit_code,
):
    def forbidden(*args, **kwargs):
        pytest.fail("scope error or dry run must not construct telemetry")

    monkeypatch.setattr(status_cli, "_RunTelemetry", forbidden)
    monkeypatch.setattr(sys, "argv", ["daily_update", *flags])

    with pytest.raises(SystemExit) as caught:
        status_cli.main()

    assert caught.value.code == exit_code
    assert not (tmp_path / "market_data.db").exists()
    assert not (tmp_path / "profile_state.db").exists()


def test_main_empty_active_scope_exits_before_environment_provider_and_telemetry(
    status_cli, tmp_path, monkeypatch, caplog,
):
    profile_path = tmp_path / "profile_state.db"
    ProfileStateStore(profile_path)
    PortfolioStore(profile_path)
    sa_capture_store.connect(str(tmp_path / "sa_capture.db")).close()

    def forbidden(*args, **kwargs):
        pytest.fail("empty active scope must not construct telemetry")

    monkeypatch.setattr(status_cli, "_RunTelemetry", forbidden)
    monkeypatch.setattr(sys, "argv", ["daily_update", "--all", "--scope", "active-universe"])

    with pytest.raises(SystemExit) as caught:
        status_cli.main()

    assert caught.value.code == 1
    assert "active-universe scope is empty/unavailable" in caplog.text
    assert not (tmp_path / "market_data.db").exists()


def test_main_explicit_tickers_override_unavailable_active_scope(
    collection_cli, tmp_path, monkeypatch,
):
    import src.service.data_scheduler as data_scheduler

    calls = []

    def run_source(source, *, trigger_source, tickers):
        calls.append((source, trigger_source, tickers))
        return {"status": "succeeded"}

    monkeypatch.setattr(data_scheduler, "run_source", run_source)
    monkeypatch.setattr(sys, "argv", [
        "daily_update", "--massive", "--scope", "active-universe", "--tickers", " msft ,aapl ",
    ])

    with pytest.raises(SystemExit) as caught:
        collection_cli.main()

    assert caught.value.code == 0
    assert calls == [("polygon_news", "cli", ["MSFT", "AAPL"])]
    assert not (tmp_path / "sa_capture.db").exists()
