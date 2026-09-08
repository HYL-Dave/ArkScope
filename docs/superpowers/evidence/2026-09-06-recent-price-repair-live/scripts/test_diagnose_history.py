import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


spec = importlib.util.spec_from_file_location("price_history", Path(__file__).with_name("diagnose_history.py"))
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def test_history_projects_only_price_metadata_and_keeps_missing_distinct(tmp_path):
    path = tmp_path / "profile.db"
    secret = "PRIVATE_TEST_API_KEY_NOT_FOR_HISTORY"
    value = {"ticker_count": 187, "collect": {"status": "partial", "tickers_scanned": 187,
             "succeeded_ticker_count": 183, "error_count": 4, "rows_added": 4758,
             "error_tickers": ["ARCH", "LTHM", "SMCI*", "TA"], "error": secret}, "api_key": secret}
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE job_runs(job_name TEXT,started_at TEXT,status TEXT,duration_ms INTEGER,result TEXT)")
        conn.executemany("INSERT INTO job_runs VALUES(?,?,?,?,?)", [
            ("collect.ibkr_prices", "2026-09-03", "failed", 100, json.dumps(value)),
            ("collect.ibkr_prices", "2026-09-04", "failed", 10, "malformed"),
            ("other", "2026-09-03", "failed", 10, json.dumps({"secret": secret})),
            ("collect.ibkr_prices", "2026-06-01", "failed", 10, json.dumps({"secret": secret})),
        ])
    result = history.inspect(path)
    assert result["job_count"] == 2
    assert result["rows"][0]["scanned"] == 187
    assert result["rows"][0]["error_count"] == 4
    assert result["rows"][1]["result_valid"] == 0
    assert result["rows"][1]["scanned"] is None
    assert secret not in json.dumps(result)


def test_invalid_footnote_ticker_can_mask_completed_writes_in_old_worker_summary():
    from src import prices_runtime
    from src.service.data_scheduler import _parse_sanitized_prices_worker_stdout

    raw = {"status": "partial", "provider": "ibkr", "tickers_scanned": 187,
           "succeeded_ticker_count": 183, "gaps_found": 0, "rows_added": 4758,
           "unresolved_after_fetch_count": 0, "unresolved_after_fetch_tickers": [],
           "errors": {name: "security_definition_unavailable" for name in ("ARCH", "LTHM", "SMCI*", "TA")}}
    with pytest.raises(ValueError, match="error_tickers") as caught:
        prices_runtime.sanitize_result(raw)
    boundary = _parse_sanitized_prices_worker_stdout(json.dumps(prices_runtime.sanitize_error(caught.value)))
    assert boundary["error_class"] == "ValueError"
    assert boundary["tickers_scanned"] == boundary["rows_added"] == 0
    assert raw["rows_added"] == 4758

    clean = {**raw, "tickers_scanned": 186, "errors": {name: "security_definition_unavailable" for name in ("ARCH", "LTHM", "TA")}}
    valid = prices_runtime.sanitize_result(clean)
    assert valid["status"] == "partial" and valid["succeeded_ticker_count"] == 183
    assert valid["error_count"] == 3 and valid["rows_added"] == 4758
