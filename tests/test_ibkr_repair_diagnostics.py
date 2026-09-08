"""Price error phases must survive immutable repair receipts without replay."""

import json
import sqlite3

import pytest

from src import market_data_direct, price_repair_execution as execution
from tests.test_ibkr_price_request_diagnostics import offline_source
from tests.test_recent_price_repair import recent, repair_setup, run_repair


@pytest.mark.parametrize("phase,broker_code,expected", [
    ("qualification", 321, "ibkr_contract_qualification_failed"),
    ("qualification", 200, "security_definition_unavailable"),
    ("history", 321, "ibkr_historical_data_request_failed"),
    ("history", 200, "ibkr_historical_data_request_failed"),
])
def test_broker_failure_receipt_keeps_phase_and_never_replays(
    recent, offline_source, monkeypatch, phase, broker_code, expected,
):
    source, calls = offline_source
    plan = execution.build_repair_plan(
        recent.service.get_coverage(universe=["LIVE"], lookback_days=15, interval="15min"),
        recent.path, pacing_seconds=0,
    )
    directory = recent.tmp / "diagnostic-repair"

    def rejected(req_id, *args):
        calls.append(phase)
        source._ib.wrapper.error(req_id, broker_code, "PRIVATE_PROVIDER_TEXT", "")

    method = "reqContractDetails" if phase == "qualification" else "reqHistoricalData"
    monkeypatch.setattr(source._ib.client, method, rejected)

    def run():
        return execution.execute_price_repair(
            plan, directory, source=source, active_scope=lambda: {"LIVE"},
            coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False,
        )

    result = run()
    expected_calls = ["qualification"] if phase == "qualification" else ["qualification", "history"]
    assert result["errors"] == {"LIVE": expected}
    assert result["repair_execution"]["requests_total"] == len(expected_calls)
    assert calls == expected_calls
    assert source._ib.RaiseRequestErrors is False
    with sqlite3.connect(directory / "requests.sqlite3") as conn:
        receipts = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM responses")]
    assert [receipt["code"] for receipt in receipts if receipt["code"]] == [expected]
    assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(receipts)

    replay = run()

    assert replay["errors"] == result["errors"]
    assert replay["repair_execution"]["requests_this_execution"] == 0
    assert calls == expected_calls
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT count(*) FROM prices").fetchone() == (0,)


def test_repair_and_cached_replay_do_not_clear_prior_telemetry(recent):
    module, plan, source, directory = repair_setup(recent)
    with sqlite3.connect(recent.path) as conn:
        market_data_direct._ensure_provider_sync_tables(conn)
        conn.execute(
            "INSERT INTO provider_sync_meta (provider,ticker,interval,last_error,updated_at) "
            "VALUES ('ibkr','FORMER','15min','ibkr_historical_data_request_failed','2026-08-20T00:00:00Z')",
        )

    result = run_repair(recent, module, plan, source, directory)

    assert result["status"] == "succeeded"
    assert recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min").history_gaps == []
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT last_error,updated_at FROM provider_sync_meta").fetchone() == (
            "ibkr_historical_data_request_failed", "2026-08-20T00:00:00Z",
        )
    before = recent.path.read_bytes()

    replay = run_repair(recent, module, plan, source, directory)

    assert replay["repair_execution"]["requests_this_execution"] == 0
    assert recent.path.read_bytes() == before
