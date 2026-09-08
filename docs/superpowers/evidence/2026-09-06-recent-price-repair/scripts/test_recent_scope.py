from contextlib import closing
import copy
import importlib.util
from pathlib import Path
import sqlite3

import pytest

from src import market_data_direct
from src.market_coverage.repair import preview_price_repair
from tests.test_recent_price_repair import no_network, recent, raw_source
from tests.test_trading_day_coverage import _slots


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prepare = module("prepare_recent")
inspect = module("inspect_recent")


def inputs(recent):
    with sqlite3.connect(recent.path) as conn:
        conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", [
            ("FORMER", market_data_direct._normalize_utc(at), "15min", 10, 11, 9, 10, 100)
            for day, session in recent.sessions.items() if day.isoformat() >= "2026-08-31" for at in _slots(session)])
    coverage = recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min")
    preview = preview_price_repair(coverage)
    inventory = {"sources_by_ticker": {"FORMER": ["sa_alpha_picks_former"]}, "coverage": {"current_15": {
        "preview": preview, "history_gaps": [row.model_dump(mode="json") for row in coverage.history_gaps],
        "days": [row.model_dump(mode="json") for row in coverage.days]}}}
    summary = {"status": "readonly_inventory_complete_no_execution", "at": recent.now.isoformat(), "coverage": {"current_15": {
        "lookback_days": 15, "as_of_date": "2026-09-05", "calendar_health": "ok", "observation_health": "ok",
        "preview_sha256": preview["preview_sha256"], "repair_tickers": 1, "missing_ticker_days": 6, "partial_ticker_days": 0}}}
    return inventory, summary, preview["preview_sha256"]


def test_recent_manifest_is_provider_free_and_does_not_open_the_destination_database(recent, monkeypatch):
    inventory, summary, digest = inputs(recent)
    source = raw_source(recent)
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: pytest.fail("provider"))
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database"))
    plan, public = prepare.prepare(inventory, summary, recent.tmp / "not_created.db", digest)
    assert plan["request_budget"] == {"qualification": 1, "history": 1, "total": 2}
    assert plan["windows"] == {"FORMER": {"start": "2026-08-21", "end": "2026-08-28"}}
    assert public["max_insertable_slots"] == 156 and public["provider_requests"] == 0
    assert source._ib.calls == [] and not (recent.tmp / "not_created.db").exists()
    assert "FORMER" not in str(public)


@pytest.mark.parametrize("field,value", (("lookback_days", 120), ("as_of_date", "2026-09-06"), ("calendar_health", "unavailable"),
                                        ("preview_sha256", "f" * 64), ("missing_ticker_days", 7), ("repair_tickers", 2)))
def test_recent_manifest_rejects_changed_readonly_scope(recent, field, value):
    inventory, summary, digest = inputs(recent)
    changed = copy.deepcopy(summary)
    changed["coverage"]["current_15"][field] = value
    with pytest.raises(ValueError, match="recent_price_manifest_mismatch"):
        prepare.prepare(inventory, changed, recent.path, digest)


def test_recent_manifest_never_expands_into_deferred_old_history(recent):
    inventory, summary, digest = inputs(recent)
    inventory["coverage"]["current_15"]["history_gaps"][0]["missing_dates"].append("2026-06-05")
    with pytest.raises(ValueError, match="recent_price_manifest_mismatch"):
        prepare.prepare(inventory, summary, recent.path, digest)


def test_private_manifest_cannot_overwrite_a_prior_authorization(tmp_path):
    path = tmp_path / "plan.json"
    prepare.private_write(path, {"first": True})
    with pytest.raises(FileExistsError):
        prepare.private_write(path, {"second": True})
    assert path.stat().st_mode & 0o077 == 0
    assert "first" in path.read_text()


def test_metadata_reader_rejects_credentials_unapproved_columns_and_writes(tmp_path):
    path = tmp_path / "metadata.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE provider_sync_runs (provider TEXT, error TEXT)")
        conn.execute("INSERT INTO provider_sync_runs VALUES ('ibkr','PRIVATE_ERROR')")
        conn.execute("CREATE TABLE credentials (token TEXT)")
    with closing(inspect.readonly(path)) as conn:
        assert conn.execute("SELECT provider FROM provider_sync_runs").fetchall()[0][0] == "ibkr"
        for sql in ("SELECT error FROM provider_sync_runs", "SELECT token FROM credentials", "DELETE FROM provider_sync_runs"):
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(sql)
