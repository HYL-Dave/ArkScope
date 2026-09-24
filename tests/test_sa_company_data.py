"""Financial DOM -> native admission -> immutable SA observation -> model tools."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import html
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import sa_capture_store
from src.sa.company_data import CompanyDataFailure, canonical_json, clean_value, company_result_reducer, normalize_capture
from src.sa.company_store import read_capture, save_capture
from src.tools.sa_company_tools import get_sa_company_data


ROOT = Path(__file__).resolve().parents[1]


def capture(statement="income-statement", *, ticker="AMD"):
    titles = {"income-statement": "Income Statement", "balance-sheet": "Balance Sheet",
              "cash-flow-statement": "Cash Flow Statement"}
    labels = {
        "income-statement": ["Total Revenues", "Net Income", "Basic EPS"],
        "balance-sheet": ["Total Assets", "Total Liabilities", "Book Value / Share"],
        "cash-flow-statement": ["Cash from Operations", "Cash from Investing", "Cash from Financing"],
    }
    recent = "Last Report" if statement == "balance-sheet" else "TTM"
    return {
        "schema_version": 1, "layout_id": "sa.financial-table.v1",
        "source_url": f"https://seekingalpha.com/symbol/{ticker}/{statement}",
        "ticker": ticker, "title": f"Example Company ({ticker}) {titles[statement]} | Seeking Alpha",
        "heading": f"{ticker} - Example Company", "captured_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "controls": {"period": "Annual", "view": "Absolute", "order": "Latest on the Left",
                     "currency": "United States Dollar (USD)"},
        "unit_note": "In Millions of United States Dollar (USD) except per share items",
        "headers": [{"id": "value-header", "label": "Line Item"}, {"id": "chart-header", "label": "Price Chart"}]
                   + [{"id": label.lower().replace(" ", "-") + "-column-header", "label": label}
                      for label in (recent, "Dec 2025", "Dec 2024")],
        "rows": [{"kind": "section", "label": "Financials", "values": []}]
                + [{"kind": "data", "label": label, "values": ["", "1,234.50", "(12.0)", "-"]}
                   for label in labels[statement]],
    }


@pytest.fixture
def local(tmp_path, monkeypatch):
    db = tmp_path / "sa.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(db))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    monkeypatch.delenv("ARKSCOPE_SA_COMPANY_BUDGET_BYTES", raising=False)
    return SimpleNamespace(_backend=SimpleNamespace(_sa_db=db)), db


@pytest.mark.parametrize("raw,number,notation", [
    ("0", "0", "number"), ("1,234.50", "1234.50", "number"), ("(1,234.50)", "-1234.50", "number"),
    ("\u22121.25", "-1.25", "number"), ("12.5%", "12.5", "percent"), ("$41.19", "41.19", "currency"),
    ("($0.10)", "-0.10", "currency"), ("9007199254740993", "9007199254740993", "number"),
])
def test_values_preserve_display_scale_precision_and_zero(raw, number, notation):
    assert clean_value(raw, currency="USD") == {"raw": raw, "status": "value", "number": number, "notation": notation}


@pytest.mark.parametrize("raw", ["-", "\u2014", "N/A", "NM", "N/M", "NA", "Not Applicable"])
def test_missing_and_not_meaningful_are_not_zero(raw):
    result = clean_value(raw)
    assert result["raw"] == raw and result["number"] is None and result["status"] != "value"


@pytest.mark.parametrize("raw", ["", "1,23.0", "1.2B", "1e10", "NaN", "inf", "1*", "1 234", "$1%", True, None])
def test_unrecognized_numbers_are_not_silently_cleaned(raw):
    with pytest.raises(CompanyDataFailure, match="sa_company_value_unrecognized"):
        clean_value(raw, currency="USD")


def test_currency_symbol_cannot_supply_a_missing_or_different_currency():
    for currency in (None, "EUR"):
        with pytest.raises(CompanyDataFailure, match="value_unrecognized"):
            clean_value("$12.0", currency=currency)
    with pytest.raises(CompanyDataFailure, match="access_restricted"):
        clean_value("Subscribe to Premium")


@pytest.mark.parametrize("statement", ["income-statement", "balance-sheet", "cash-flow-statement"])
def test_statement_contract_retains_labels_units_provenance_without_invented_fiscal_dates(statement):
    result = normalize_capture(capture(statement))
    body = result["body"]
    assert body["value_basis"] == "provider_display_not_rescaled"
    assert body["precision"] == "provider_display_rounded"
    assert body["columns"][1]["end_month"] == "2025-12"
    assert all(c["period_end"] is None for c in body["columns"])
    assert body["coverage"] == {"scope": "displayed_table", "row_count": 3, "column_count": 3, "missing_cells": 3}
    assert body["rows"][0]["cells"][0]["number"] == "1234.50"
    assert body["source_url"].startswith("https://seekingalpha.com/symbol/AMD/")


@pytest.mark.parametrize("change,code", [
    (lambda p: p.update(schema_version=True), "layout_unrecognized"),
    (lambda p: p.update(ticker="INTC"), "identity_mismatch"),
    (lambda p: p.update(source_url="https://[invalid"), "identity_mismatch"),
    (lambda p: p.update(source_url=p["source_url"] + "?token=private"), "identity_mismatch"),
    (lambda p: p.update(title="Example (AMD) Balance Sheet"), "identity_mismatch"),
    (lambda p: p["controls"].update(view="YoY Growth"), "view_unsupported"),
    (lambda p: p["controls"].update(period=[]), "layout_unrecognized"),
    (lambda p: p["controls"].update(currency="Euro (EUR)"), "units_unrecognized"),
    (lambda p: p.update(unit_note="In Billions of United States Dollar (USD)"), "units_unrecognized"),
    (lambda p: p["headers"][3].update(id="dec-2024-column-header"), "layout_unrecognized"),
    (lambda p: p["headers"].append(p["headers"][3]), "layout_unrecognized"),
    (lambda p: p["headers"].__setitem__(slice(2, 4), p["headers"][2:4][::-1]), "layout_unrecognized"),
    (lambda p: p["rows"][1]["values"].pop(), "layout_unrecognized"),
    (lambda p: p["rows"][1]["values"].__setitem__(0, "99.0"), "layout_unrecognized"),
    (lambda p: p["rows"][1]["values"].__setitem__(1, "Loading"), "value_unrecognized"),
    (lambda p: p["rows"].append(p["rows"][1]), "layout_unrecognized"),
    (lambda p: p["rows"][1].update(label="Unknown Revenues"), "layout_unrecognized"),
    (lambda p: p.update(captured_at="2026-01-01T12:00:00"), "capture_time_invalid"),
    (lambda p: p.update(captured_at="2999-01-01T00:00:00Z"), "capture_time_invalid"),
])
def test_unknown_capture_fails_before_any_database_is_created(local, change, code):
    _, db = local
    payload = capture()
    change(payload)
    with pytest.raises(CompanyDataFailure, match="sa_company_" + code):
        save_capture(payload)
    assert not db.exists()


def test_capture_with_only_missing_cells_is_not_success(local):
    payload = capture()
    for row in payload["rows"][1:]:
        row["values"][1:] = ["-", "N/A", "NM"]
    with pytest.raises(CompanyDataFailure, match="values_unavailable"):
        save_capture(payload)


def test_same_content_deduplicates_and_history_reopens_after_new_capture(local):
    dal, db = local
    first = capture()
    receipt = save_capture(first)
    later = deepcopy(first)
    later["captured_at"] = datetime.now(timezone.utc).isoformat()
    repeated = save_capture(later)
    assert repeated["deduplicated"] is True and repeated["observation_id"] == receipt["observation_id"]
    later["rows"][1]["values"][1] = "2,000.0"
    updated = save_capture(later)
    assert updated["observation_id"] != receipt["observation_id"]
    old = get_sa_company_data(dal, "AMD", observation_id=receipt["observation_id"])
    assert old["rows"][0]["cells"][0]["raw"] == "1,234.50"
    assert old["first_captured_at"] == first["captured_at"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sa_company_observations").fetchone()[0] == 2


def test_structural_change_with_plausible_numbers_cannot_replace_baseline(local):
    dal, db = local
    payload = capture()
    receipt = save_capture(payload)
    payload["rows"][3]["label"] = "Different EPS concept"
    with pytest.raises(CompanyDataFailure, match="sa_company_structure_changed"):
        save_capture(payload)
    result = get_sa_company_data(dal, "AMD")
    assert result["observation_id"] == receipt["observation_id"]
    assert result["rows"][2]["label"] == "Basic EPS"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sa_company_observations").fetchone()[0] == 1


def test_rotating_years_and_column_order_are_not_schema_drift(local):
    payload = capture()
    first = save_capture(payload)
    payload["headers"][3:] = [{"id": "dec-2026-column-header", "label": "Dec 2026"}, payload["headers"][3]]
    second = save_capture(payload)
    assert second["structure_sha256"] == first["structure_sha256"]
    payload["controls"]["order"] = "Latest on the Right"
    payload["headers"][2:] = reversed(payload["headers"][2:])
    for row in payload["rows"][1:]:
        row["values"][1:] = reversed(row["values"][1:])
    assert save_capture(payload)["structure_sha256"] == first["structure_sha256"]


def test_quarterly_columns_cannot_be_mislabeled_as_annual(local):
    payload = capture()
    payload["headers"][4] = {"id": "sep-2025-column-header", "label": "Sep 2025"}
    with pytest.raises(CompanyDataFailure, match="view_unsupported"):
        save_capture(payload)
    payload["controls"]["period"] = "Quarterly"
    payload["headers"].pop(2)
    for row in payload["rows"][1:]:
        row["values"].pop(1)
    assert normalize_capture(payload)["body"]["view"] == "quarterly"


def test_changed_period_control_with_old_annual_columns_fails_closed(local):
    payload = capture()
    payload["controls"]["period"] = "Quarterly"
    with pytest.raises(CompanyDataFailure, match="view_unsupported"):
        save_capture(payload)


def test_storage_budget_rejects_new_content_without_eviction_but_allows_duplicate(local, monkeypatch):
    dal, _ = local
    payload = capture()
    first = save_capture(payload)
    monkeypatch.setenv("ARKSCOPE_SA_COMPANY_BUDGET_BYTES", "1")
    assert save_capture(payload)["deduplicated"] is True
    payload["rows"][1]["values"][1] = "9"
    with pytest.raises(CompanyDataFailure, match="budget_exceeded"):
        save_capture(payload)
    assert get_sa_company_data(dal, "AMD")["observation_id"] == first["observation_id"]


@pytest.mark.parametrize("budget", ["0", "-1", "1e6", "bad", str(2**63)])
def test_invalid_quota_cannot_open_store(local, monkeypatch, budget):
    monkeypatch.setenv("ARKSCOPE_SA_COMPANY_BUDGET_BYTES", budget)
    with pytest.raises(CompanyDataFailure, match="budget_invalid"):
        save_capture(capture())
    assert not local[1].exists()


def test_two_writers_share_unique_content_and_serialized_upgrade(local):
    _, db = local
    # Start at v3 to exercise concurrent upgrade admission as well as inserts.
    conn = sa_capture_store.connect(db)
    conn.execute("DROP TABLE sa_company_observations")
    for column in ("comment_backfill_pending", "comment_scan_attempted_at", "comment_scan_stop_reason", "comment_scan_policy"):
        conn.execute(f"ALTER TABLE sa_articles DROP COLUMN {column}")
    conn.execute("DELETE FROM schema_migrations WHERE version>=4")
    conn.execute("PRAGMA user_version=3")
    conn.commit()
    conn.close()
    payload = capture()
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(save_capture, [payload, payload]))
    assert {r["deduplicated"] for r in receipts} == {False, True}
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == sa_capture_store.SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM sa_company_observations").fetchone()[0] == 1


def test_two_different_captures_cannot_both_admit_against_one_remaining_budget(local, monkeypatch):
    _, db = local
    payloads = [capture(ticker=ticker) for ticker in ("AMD", "INTC")]
    sizes = [len(canonical_json(normalize_capture(p)["body"]).encode()) for p in payloads]
    budget = max(sizes) + 1
    monkeypatch.setenv("ARKSCOPE_SA_COMPANY_BUDGET_BYTES", str(budget))
    sa_capture_store.connect(db).close()

    def attempt(payload):
        try:
            return save_capture(payload)["status"]
        except CompanyDataFailure as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, payloads))
    assert set(outcomes) == {"ok", "sa_company_budget_exceeded"}
    with sqlite3.connect(db) as conn:
        count, size = conn.execute("SELECT COUNT(*), SUM(byte_count) FROM sa_company_observations").fetchone()
    assert count == 1 and size <= budget


def test_old_sa_store_read_does_not_upgrade_and_new_capture_preserves_existing_content(local):
    dal, db = local
    conn = sa_capture_store.connect(db)
    conn.execute("DROP TABLE sa_company_observations")
    for column in ("comment_backfill_pending", "comment_scan_attempted_at", "comment_scan_stop_reason", "comment_scan_policy"):
        conn.execute(f"ALTER TABLE sa_articles DROP COLUMN {column}")
    conn.execute("DELETE FROM schema_migrations WHERE version>=4")
    conn.execute("PRAGMA user_version=3")
    conn.execute("CREATE TABLE keep_existing_evidence(id INTEGER, content TEXT)")
    conn.execute("INSERT INTO keep_existing_evidence VALUES(1, 'article and comments')")
    conn.commit()
    conn.close()
    before = sha256(db.read_bytes()).hexdigest()
    assert get_sa_company_data(dal, "AMD")["error_code"] == "sa_company_capture_missing"
    assert sha256(db.read_bytes()).hexdigest() == before
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
    save_capture(capture())
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT * FROM keep_existing_evidence").fetchall() == [(1, "article and comments")]


def test_stored_lookup_has_no_acquisition_or_database_creation(local, monkeypatch):
    dal, db = local
    forbidden = Mock(side_effect=AssertionError("local reads must not create stores, refresh or spend"))
    monkeypatch.setattr("requests.get", forbidden)
    monkeypatch.setattr("src.tools.data_access.DataAccessLayer", forbidden)
    monkeypatch.setattr(sa_capture_store, "connect", forbidden)
    assert get_sa_company_data(dal, "AMD")["error_code"] == "sa_company_capture_missing"
    assert not db.exists() and not Path(os.environ["ARKSCOPE_PROFILE_DB"]).exists()
    forbidden.assert_not_called()


def test_native_capture_uses_sa_only_and_disabled_route_blocks_read_and_write(local, monkeypatch):
    from src.data_provider_config import DataProviderConfigStore
    from src.sa_native_host import handle_message

    dal, db = local
    forbidden = Mock(side_effect=AssertionError("company capture does not open market DAL or fetch"))
    monkeypatch.setattr("src.tools.data_access.DataAccessLayer", forbidden)
    monkeypatch.setattr("requests.get", forbidden)
    receipt = handle_message({"action": "save_company_data", "capture": capture()})
    assert receipt["status"] == "ok"
    config = DataProviderConfigStore(os.environ["ARKSCOPE_PROFILE_DB"])
    config.set_setting("data_sources.route.sa_company_financials", "[]")
    before = sha256(db.read_bytes()).hexdigest()
    assert handle_message({"action": "save_company_data", "capture": capture()})["error_code"] == "data_source_not_selected"
    assert get_sa_company_data(dal, "AMD")["error_code"] == "data_source_not_selected"
    assert sha256(db.read_bytes()).hexdigest() == before
    forbidden.assert_not_called()


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_observation_pagination_and_provenance_survive_four_model_channels(local, channel):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    dal, db = local
    receipt = save_capture(capture())
    before = sha256(db.read_bytes()).hexdigest()
    result = unwrap(asyncio.run(invoke(channel, "get_sa_company_data", {
        "ticker": "AMD", "observation_id": receipt["observation_id"], "row_limit": 1, "column_limit": 1,
    }, dal)))
    assert result["status"] == "ok" and result["retrieval"] == "stored"
    assert result["observation_id"] == receipt["observation_id"]
    assert result["source_route"]["selected_source"] == "seeking_alpha"
    assert len(result["rows"]) == len(result["columns"]) == len(result["rows"][0]["cells"]) == 1
    assert result["pagination"]["next_row_offset"] == result["pagination"]["next_column_offset"] == 1
    assert sha256(db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("argument,value", [("row_limit", True), ("row_offset", -1), ("column_limit", "20"),
                                          ("row_limit", 2**63), ("observation_id", "../private")])
def test_invalid_pages_do_not_read_store(local, monkeypatch, argument, value):
    forbidden = Mock(side_effect=AssertionError("invalid arguments must be rejected before data access"))
    monkeypatch.setattr("src.tools.sa_company_tools.read_capture", forbidden)
    assert get_sa_company_data(local[0], "AMD", **{argument: value})["status"] == "unavailable"
    forbidden.assert_not_called()


def test_page_limits_are_not_an_arbitrary_dataset_ceiling(local):
    save_capture(capture())
    result = get_sa_company_data(local[0], "AMD", row_limit=2**63-1, column_limit=2**63-1)
    assert len(result["rows"]) == 3 and len(result["columns"]) == 3


def test_tampered_observation_does_not_return_plausible_numbers(local):
    _, db = local
    save_capture(capture())
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE sa_company_observations SET body_json=replace(body_json, '1234.50', '9999.50')")
    assert get_sa_company_data(local[0], "AMD")["error_code"] == "sa_company_observation_invalid"


@pytest.mark.parametrize("wrapped", [False, True])
def test_model_budget_never_slices_financial_json(local, wrapped):
    from src.agents.shared.compressor.reducers import get_reducer

    save_capture(capture())
    result = get_sa_company_data(local[0], "AMD")
    payload = json.dumps(result)
    if wrapped:
        payload = '<tool_output tool="get_sa_company_data">\n' + payload + '\n</tool_output>'
    assert get_reducer("get_sa_company_data") is company_result_reducer
    assert company_result_reducer(payload, budget=len(payload))[0] == payload
    reduced, diagnostic = company_result_reducer(payload, budget=1000)
    if wrapped:
        reduced = reduced.split("\n", 1)[1].rsplit("\n", 1)[0]
    failure = json.loads(reduced)
    assert failure["error_code"] == "sa_company_page_too_large"
    assert failure["observation_id"] == result["observation_id"]
    assert "rows" not in failure and diagnostic["failure"] == failure["error_code"]


def test_financial_subagents_receive_the_same_local_reader():
    from src.agents.shared.subagent import SUBAGENT_REGISTRY

    for name in ("code_analyst", "deep_researcher", "data_summarizer"):
        assert "get_sa_company_data" in SUBAGENT_REGISTRY[name].tool_names


def test_native_compression_never_fails_open_to_an_oversized_financial_table(local):
    from src.agents.shared.compressor.layers import apply_layer_0

    save_capture(capture())
    payload = json.dumps(get_sa_company_data(local[0], "AMD"))
    store = SimpleNamespace(write=Mock(side_effect=OSError("disk full")))
    reduced, record = apply_layer_0(tool_name="tool_get_sa_company_data", args={"ticker":"AMD"},
                                   payload=payload, overflow_store=store, budget_chars=1000)
    assert record is None
    assert json.loads(reduced)["error_code"] == "sa_company_page_too_large"
    assert "rows" not in json.loads(reduced)


@pytest.mark.parametrize("scenario,expected", [
    ("saved", "complete"), ("changed", "failed"), ("locked", "failed"),
    ("native_failed", "failed"), ("bad_receipt", "failed"),
])
def test_background_capture_never_navigates_and_reports_native_failure(scenario, expected):
    from tests.test_sa_extension_popup import _run_background_probe
    from tests.sa_acquisition_helpers import ADMITTED_TASK
    from src.sa.extension_run_protocol import derive_run_result

    payload = capture()
    probe = _run_background_probe(ADMITTED_TASK + """
      const scenario = SCENARIO;
      const capture = PAYLOAD;
      const calls = [];
      let reads = 0;
      chrome.tabs.get = async function () {
        reads += 1;
        return {url: scenario === "changed" && reads === 2 ? "https://seekingalpha.com/symbol/INTC/income-statement" : capture.source_url};
      };
      for (const method of ["update", "create", "remove"]) {
        chrome.tabs[method] = function () { throw new Error("capture must not navigate"); };
      }
      chrome.scripting.executeScript = async function (request) {
        calls.push({kind: "extract", request});
        return [{result: scenario === "locked" ? {status:"error", error_code:"sa_company_access_restricted"} : {status:"ok", capture}}];
      };
      sendNativeMessage2 = async function (request) {
        calls.push({kind: "native", action: request.action});
        if (request.action === "get_company_capture_admission") return {status:"ok",dataset:"financials"};
        if (scenario === "native_failed") return {status:"error", error_code:"sa_company_budget_exceeded"};
        if (scenario === "bad_receipt") return {status:"ok"};
        return {status:"ok", observation_id:"a".repeat(64), ticker: "AMD", statement:"income_statement", view:"annual", currency:"USD",
          coverage:{scope:"displayed_table",row_count:3,column_count:3},deduplicated:false};
      };
      const diagnostics = SAExtensionDiagnostics.createCollector();
      const result = await captureCompanyData({id: 5, url:capture.source_url}, diagnostics);
      const structured = attachExtensionRunProtocol("company_financial_capture", "current_tab", result);
      return {result:structured,calls,diagnostics:diagnostics.freeze(),stored:(await chrome.storage.local.get(["lastCompanyCapture"])).lastCompanyCapture};
    """.replace("SCENARIO", json.dumps(scenario)).replace("PAYLOAD", json.dumps(payload)))
    protocol = probe["result"]["extension_run"]
    assert protocol["derived_outcome"] == expected
    inputs = {key: protocol[key] for key in ("schema_version", "operation", "mode", "phases", "item_outcomes")}
    assert derive_run_result(inputs)["derived_outcome"] == expected
    assert len(probe["diagnostics"]["entries"]) == (0 if expected == "complete" else 1)
    if scenario in {"changed", "locked"}:
        assert not any(call.get("action") == "save_company_data" for call in probe["calls"])
    assert probe["stored"]["status"] == ("ok" if expected == "complete" else "error")
    assert "rows" not in probe["stored"] and "capture" not in probe["stored"]


def test_company_failure_is_available_in_the_existing_durable_extension_diagnostics(tmp_path):
    from src.sa.extension_run_protocol import derive_run_result
    from src.service.job_runs_store import JobRunsLocalStore

    result = derive_run_result({
        "schema_version": 1, "operation": "company_financial_capture", "mode": "current_tab", "item_outcomes": [],
        "phases": {"extraction": {"state": "complete", "reason_code": None},
                   "persistence": {"state": "failed", "reason_code": "company_layout_unrecognized"}},
    })
    assert result["db_status"] == "failed"
    store = JobRunsLocalStore(tmp_path / "profile.db")
    run_id = store.record_extension_event_once(
        client_event_id="company-capture-test", event_hash="a" * 64, job_name=result["job_name"],
        status=result["db_status"], started_at="2026-09-21T01:00:00Z", finished_at="2026-09-21T01:00:01Z",
        result=result, duration_ms=1000,
    )
    rows = store.completed_extension_runs_by_name()
    assert len(rows) == 1 and rows[0]["id"] == run_id
    assert rows[0]["result"]["derived_outcome"] == "failed"
    assert store.completed_extension_runs_by_name(["sa_market_news_refresh"]) == []


def financial_html(payload):
    esc = html.escape
    headers = "".join(f'<th data-test-id="{esc(h["id"])}">{esc(h["label"])}</th>' for h in payload["headers"])
    rows = []
    for row in payload["rows"]:
        if row["kind"] == "section":
            rows.append(f'<tr><th scope="colgroup" colspan="{len(payload["headers"])}">{esc(row["label"])}</th></tr>')
        else:
            rows.append('<tr><th scope="row">' + esc(row["label"]) + '</th>'
                        + ''.join('<td>' + esc(value) + '</td>' for value in row["values"]) + '</tr>')
    controls = "".join(f'<button role="combobox" aria-labelledby="financials-filter-{key}">{esc(value)}</button>'
                       for key, value in payload["controls"].items())
    return (f'<html><head><title>{esc(payload["title"])}</title></head><body><main>'
            f'<h1>{esc(payload["heading"])}</h1>{controls}\n{esc(payload["unit_note"])}\n'
            f'<table aria-hidden="true" data-test-id="table"><thead><tr>{headers}</tr></thead></table>'
            f'<table data-test-id="table"><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
            '</main></body></html>')


def extract_dom(tmp_path, markup):
    fixture = tmp_path / "company.html"
    fixture.write_text(markup)
    run = subprocess.run(["node", str(ROOT / "tests/js/run_sa_extension_fixture.mjs"), str(fixture),
                          str(ROOT / "extensions/sa_alpha_picks/scrape_company.js")],
                         env={**os.environ, "ARKSCOPE_FIXTURE_URL": "https://seekingalpha.com/symbol/AMD/income-statement"},
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


def test_actual_extractor_native_store_and_tool_contract_end_to_end(local, tmp_path):
    from src.sa_native_host import handle_message

    extracted = extract_dom(tmp_path, financial_html(capture()))
    assert extracted["status"] == "ok"
    receipt = handle_message({"action": "save_company_data", "capture": extracted["capture"]})
    assert receipt["status"] == "ok"
    result = get_sa_company_data(local[0], "AMD")
    assert result["rows"][0]["cells"][0]["raw"] == "1,234.50"
    assert result["observation_id"] == receipt["observation_id"]


@pytest.mark.parametrize("before,after,code", [
    ('scope="row"', 'scope="col"', "layout_unrecognized"),
    ('colspan="5"', 'colspan="4"', "layout_unrecognized"),
    ('<td>1,234.50</td>', '<td colspan="2">1,234.50</td>', "layout_unrecognized"),
    ('<td>1,234.50</td>', '<td><a href="/subscribe">Subscribe</a></td>', "access_restricted"),
    ('<main>', '<main aria-busy="true">', "dom_not_ready"),
    ('Line Item', '', "dom_not_ready"),
    ('<main>', '<main style="display:none">', "layout_unrecognized"),
    ('In Millions of United States Dollar (USD) except per share items', 'In unknown units', "units_unrecognized"),
    ('Example Company (AMD) Income Statement', 'Verify you are human', "human_verification_required"),
    ('Example Company (AMD) Income Statement', 'Access to this page has been denied', "human_verification_required"),
    ('Example Company (AMD) Income Statement', '429 Too Many Requests', "rate_limited"),
    ('<main>', '<main><h1>Rate limit exceeded</h1>', "rate_limited"),
])
def test_dom_changes_and_loading_states_refuse_numbers(tmp_path, before, after, code):
    markup = financial_html(capture()).replace(before, after)
    assert extract_dom(tmp_path, markup) == {"status": "error", "error_code": "sa_company_" + code}


def test_hidden_rate_banner_and_a_429_financial_value_are_not_a_visible_limit(tmp_path):
    markup = financial_html(capture()).replace(
        '<main>', '<main><h1 hidden>Too many requests</h1>'
    ).replace('1,234.50', '429.0')
    result = extract_dom(tmp_path, markup)
    assert result["status"] == "ok"
    assert any("429.0" in row["values"] for row in result["capture"]["rows"])


@pytest.mark.parametrize("challenge", ["title", "frame"])
def test_verification_takes_priority_over_a_timed_rate_cooldown(tmp_path, challenge):
    markup = financial_html(capture()).replace('<main>', '<main><h1>Too many requests</h1>')
    if challenge == "title":
        markup = markup.replace('Example Company (AMD) Income Statement', 'Verify you are human')
    else:
        markup = markup.replace('</body>', '<iframe title="Human verification challenge"></iframe></body>')
    assert extract_dom(tmp_path, markup) == {
        "status": "error", "error_code": "sa_company_human_verification_required",
    }
