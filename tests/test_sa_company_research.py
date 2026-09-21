"""Provider judgments, forecasts and lazy-loaded tables remain source observations."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import asyncio
import html
import json
import os
import subprocess
from unittest.mock import Mock

import pytest

from src.sa.company_data import CompanyDataFailure, normalize_capture
from src.sa.company_research import DATASETS, PEER_ROWS, VALUATION_ROWS, _peer_kind, display_cell
from src.sa.company_store import save_capture
from src.tools.sa_company_tools import get_sa_company_data
from tests.test_sa_company_data import ROOT, local


def estimates_capture():
    tables = []
    for kind, title, multiple in (("normalized", "EPS Estimate", "Forward PE"),
                                  ("revenues", "Revenue Estimate", "FWD Price/Sales")):
        labels = ["Fiscal Period Ending", title, "YoY Growth", multiple, "Low", "High", "# of Analysts"]
        ids = ["fiscal_period", "estimate", "yoy", "fwd_pe", "low", "high", "num_analysts"]
        tables.append({
            "id": f"consensus-{kind}-estimates-card",
            "headers": [{"id": name + "-header", "label": label} for name, label in zip(ids, labels)],
            "rows": [{"label": "Dec 2026", "values": ["12.50" if kind == "normalized" else "50.88B",
                                                        "10%", "12.34", "10" if kind == "normalized" else "48B",
                                                        "60" if kind == "normalized" else "55B", "3"]}],
        })
    return {
        "schema_version": 2, "layout_id": "sa.company-research.v1",
        "source_url": "https://seekingalpha.com/symbol/AMD/earnings/estimates",
        "ticker": "AMD", "title": "Example (AMD) Earnings Estimates, Revenue Estimates | Seeking Alpha",
        "heading": "AMD - Example", "captured_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "estimates", "view": "annual", "tables": tables,
        "loading": {"strategy": "bounded_section_scroll", "pagination": "no_pagination_controls"},
    }


def test_forecasts_are_not_reported_facts_or_live_quotes():
    body = normalize_capture(estimates_capture())["body"]
    assert body["dataset"] == "estimates"
    assert body["data_kind"] == "analyst_consensus"
    assert body["provider_data_at"] is None
    assert body["price_qualification"] == "not_live_quote"
    eps, revenue = body["tables"]
    assert eps["rows"][0]["period"] == {"kind": "annual", "end_month": "2026-12", "period_end": None}
    assert eps["rows"][0]["cells"][0]["number"] == "12.50"
    assert revenue["rows"][0]["cells"][0]["number"] == "50.88"
    assert revenue["rows"][0]["cells"][0]["multiplier"] == "1000000000"
    assert eps["columns"][-1]["label"] == "# of Analysts"


@pytest.mark.parametrize("mutate", [
    lambda p: p["tables"].pop(),
    lambda p: p["tables"][1]["rows"][0]["values"].pop(),
    lambda p: p["tables"][1]["headers"][1].update(label="EPS Estimate"),
    lambda p: p["tables"][0]["rows"][0]["values"].__setitem__(0, ""),
    lambda p: p["tables"][1]["rows"][0].update(label="Dec 2027"),
])
def test_incomplete_or_misaligned_research_is_not_an_observation(mutate):
    payload = deepcopy(estimates_capture())
    mutate(payload)
    with pytest.raises(CompanyDataFailure):
        normalize_capture(payload)


def research_capture(dataset):
    payload = estimates_capture()
    path, title, view, _ = DATASETS[dataset]
    payload.update(dataset=dataset, view=view, source_url="https://seekingalpha.com/symbol/AMD/" + path,
                   title="Example (AMD) " + title + " | Seeking Alpha")
    if dataset == "estimates":
        return payload
    tables = []
    if dataset == "revisions":
        for title, stem in (("EPS", "eps"), ("Revenue", "revenue")):
            headers = list(zip(["fiscal-period-ending", "estimate", "yoy-growth", "1m-trend", "3m-trend", "6m-trend"],
                               ["Fiscal Period Ending", title + " Estimate", "YoY Growth", "1M Trend", "3M Trend", "6M Trend"]))
            tables.append({"id": "consensus-" + stem + "-revision-trend-card",
                           "headers": [{"id": key + "-header", "label": label} for key, label in headers],
                           "rows": [{"label": "Dec 2026", "values": ["12.0", "10%", "-2%", "3%", "0%"]}]})
    elif dataset == "valuation":
        headers = list(zip(["metricName", "grade", "symbolValue", "sectorMedian", "sectorDiff", "5yavg", "5yavgDiff"],
                           ["Type", "Sector Relative Grade", "AMD", "Sector Median", "% Diff. to Sector", "AMD 5Y Avg.", "% Diff. to 5Y Avg."]))
        tables.append({"id": "card-container-valuation-metrics",
                       "headers": [{"id": key + "-header", "label": label} for key, label in headers],
                       "rows": [{"label": label, "values": ["A", "2.3", "3.4", "-10%", "2.5", "-3%"]
                                 if label != "Dividend Yield (TTM)" else ["- Rating: Not Covered", "-", "-", "NM", "-", "-"]}
                                for label in VALUATION_ROWS]})
    else:
        values = {"text": "Example", "rating": "Strong Buy", "grade": "A-", "rank": "2 out of 12", "frequency": "Quarterly",
                  "years": "2 Years", "percent": "2.5%", "integer": "3", "number": "12.0"}
        for section, (title, labels) in PEER_ROWS.items():
            tables.append({"id": "card-container-" + section,
                           "headers": [{"id": "label-header", "label": title}]
                           + [{"id": "ticker-" + s + "-header", "label": s} for s in ("AMD", "INTC")],
                           "rows": [{"label": label, "values": [values[_peer_kind(section, label)]] * 2} for label in labels]})
    payload["tables"] = tables
    return payload


@pytest.mark.parametrize("raw,kind,field,value", [
    ("50.88B", "number", "multiplier", "1000000000"), ("($1.20M)", "number", "number", "-1.20"),
    ("0%", "percent", "number", "0"), ("31,000", "integer", "number", "31000"),
    ("-2.5%", "percent", "number", "-2.5"), ("NM", "number", "status", "not_meaningful"),
    ("- RATING: NOT COVERED", "grade", "status", "not_covered"),
    ("3 out of 535", "rank", "rank", "3"), ("Strong Buy", "rating", "rating", "STRONG BUY"),
    ("A+", "grade", "grade", "A+"), ("1 Year", "years", "number", "1"),
    ("Semiannual", "frequency", "notation", "frequency"),
    ("9007199254740993", "number", "number", "9007199254740993"),
])
def test_typed_display_values_do_not_mix_units_judgment_or_missingness(raw, kind, field, value):
    result = display_cell(raw, kind)
    assert result[field] == value and result["raw"] == raw
    if "$" in raw:
        assert result["currency_symbol"] == "$" and result["currency"] is None


@pytest.mark.parametrize("raw,kind", [("2%", "number"), ("2", "percent"), ("4 out of 3", "rank"),
                                     ("2.5", "integer"), ("A++", "grade"), ("1.5B%", "number"), ("buy now", "rating"),
                                     ("NAN", "number"), ("10*", "number"), ("", "text"), ([], "number")])
def test_plausible_wrong_types_are_not_reinterpreted(raw, kind):
    with pytest.raises(CompanyDataFailure):
        display_cell(raw, kind)


def test_forecast_mean_cannot_silently_exceed_its_displayed_bounds():
    payload = estimates_capture()
    payload["tables"][1]["rows"][0]["values"][3] = "51B"
    with pytest.raises(CompanyDataFailure, match="estimate_range_inconsistent"):
        normalize_capture(payload)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_datasets_persist_and_reopen_across_four_channels(local, dataset, channel, monkeypatch):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap
    from src.sa_native_host import handle_message

    dal, db = local
    forbidden = Mock(side_effect=AssertionError("stored company research must not fetch or open market DAL"))
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    monkeypatch.setattr("src.tools.data_access.DataAccessLayer", forbidden)
    receipt = handle_message({"action": "save_company_data", "capture": research_capture(dataset)})
    assert receipt["status"] == "ok"
    before = sha256(db.read_bytes()).hexdigest()
    args = {"ticker": "AMD", "dataset": dataset, "observation_id": receipt["observation_id"], "row_limit": 1, "column_limit": 1}
    result = unwrap(asyncio.run(invoke(channel, "get_sa_company_data", args, dal)))
    assert result["status"] == "ok" and result["retrieval"] == "stored"
    assert result["observation_id"] == receipt["observation_id"]
    assert len(result["columns"]) == len(result["rows"]) == len(result["rows"][0]["cells"]) == 1
    assert result["provider_data_at"] is None and result["price_qualification"] == "not_live_quote"
    if dataset == "peers":
        assert result["peer_selection"]["classification"] == "judgment_not_financial_fact"
    if len(result["available_tables"]) > 1:
        args["table"] = result["available_tables"][-1]["id"]
        other = unwrap(asyncio.run(invoke(channel, "get_sa_company_data", args, dal)))
        assert other["selected_table"] == args["table"] and other["observation_id"] == result["observation_id"]
    assert sha256(db.read_bytes()).hexdigest() == before
    forbidden.assert_not_called()


def test_research_updates_deduplicate_and_do_not_rewrite_old_observations(local):
    payload = research_capture("estimates")
    first = save_capture(payload)
    assert save_capture(payload)["deduplicated"] is True
    payload["tables"][0]["rows"][0]["values"][0] = "13.25"
    payload["captured_at"] = datetime.now(timezone.utc).isoformat()
    second = save_capture(payload)
    assert first["observation_id"] != second["observation_id"]
    assert get_sa_company_data(local[0], "AMD", dataset="estimates")["observation_id"] == second["observation_id"]
    assert get_sa_company_data(local[0], "AMD", dataset="estimates", observation_id=first["observation_id"])["rows"][0]["cells"][0]["number"] == "12.50"


@pytest.mark.parametrize("mutate", [
    lambda p: p["tables"][5]["headers"].reverse(),
    lambda p: p["tables"][5]["headers"][1].update(label="AAPL", id="ticker-AAPL-header"),
    lambda p: p["tables"][5]["rows"].pop(),
    lambda p: p["tables"][5]["rows"][0].update(label="2 Month Return"),
    lambda p: p["tables"][5]["rows"][0].update(label=[]),
    lambda p: p["tables"].pop(),
])
def test_bad_peer_capture_does_not_replace_known_good(local, mutate):
    payload = research_capture("peers")
    first = save_capture(payload)
    mutate(payload)
    with pytest.raises(CompanyDataFailure):
        save_capture(payload)
    assert get_sa_company_data(local[0], "AMD", dataset="peers")["observation_id"] == first["observation_id"]


def test_legitimate_changed_peer_set_is_not_a_layout_change(local):
    payload = research_capture("peers")
    save_capture(payload)
    for table in payload["tables"]:
        table["headers"][2] = {"id": "ticker-AAPL-header", "label": "AAPL"}
    assert save_capture(payload)["status"] == "ok"


@pytest.mark.parametrize("dataset,route", [("valuation", "sa_company_valuation"), ("peers", "sa_company_valuation"),
                                          ("estimates", "sa_company_estimates"), ("revisions", "sa_company_estimates")])
def test_selection_preflight_and_persistence_both_recheck_permission(local, dataset, route):
    from src.data_provider_config import DataProviderConfigStore
    from src.sa_native_host import handle_message

    assert handle_message({"action": "get_company_capture_admission", "dataset": dataset}) == {"status": "ok", "dataset": dataset}
    assert not local[1].exists()
    DataProviderConfigStore(os.environ["ARKSCOPE_PROFILE_DB"]).set_setting("data_sources.route." + route, "[]")
    assert handle_message({"action": "get_company_capture_admission", "dataset": dataset})["error_code"] == "data_source_not_selected"
    assert handle_message({"action": "save_company_data", "capture": research_capture(dataset)})["error_code"] == "data_source_not_selected"
    assert get_sa_company_data(local[0], "AMD", dataset=dataset)["error_code"] == "data_source_not_selected"
    assert not local[1].exists()


@pytest.mark.parametrize("kwargs", [{"dataset": "peers", "currency": "USD"}, {"dataset": "estimates", "view": "quarterly"},
                                  {"dataset": "peers", "statement": "income_statement"}, {"dataset": []}, {"table": []}])
def test_inapplicable_scope_arguments_fail_before_read(local, monkeypatch, kwargs):
    reader = Mock(side_effect=AssertionError("invalid scope must not read"))
    monkeypatch.setattr("src.tools.sa_company_tools.read_capture", reader)
    assert get_sa_company_data(local[0], "AMD", **kwargs)["status"] == "unavailable"
    reader.assert_not_called()


def research_html(payload):
    esc = html.escape
    sections = []
    for table in payload["tables"]:
        headers = "".join(f'<th data-test-id="{h["id"]}">{esc(h["label"])}</th>' for h in table["headers"])
        rows = "".join('<tr><th scope="row">' + esc(row["label"]) + '</th>'
                       + ''.join('<td>' + esc(value) + '</td>' for value in row["values"]) + '</tr>' for row in table["rows"])
        sections.append(f'<section data-test-id="{table["id"]}"><h2>{table["id"]}</h2>'
                        f'<table data-test-id="table"><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></section>')
    annual = "Annual Estimates Summary" if payload["dataset"] == "estimates" else "Annual Estimates Revisions"
    return (f'<html><title>{esc(payload["title"])}</title><body><main><h1>{esc(payload["heading"])}</h1>'
            f'<h2>{annual}</h2>{"".join(sections)}</main></body></html>')


def extract_research(tmp_path, payload, scenario="loaded"):
    fixture, harness = tmp_path / "research.html", tmp_path / "loading.js"
    fixture.write_text(research_html(payload))
    harness.write_text('''
      const scenario = SCENARIO;
      window.scrollTo = () => {};
      window.setTimeout = (callback) => { callback(); return 0; };
      const originals = new Map();
      if (scenario === "lazy") for (const cell of document.querySelectorAll("td")) {
        originals.set(cell, cell.textContent); cell.textContent = "";
      }
      window.HTMLElement.prototype.scrollIntoView = function () {
        if (scenario === "lazy") for (const cell of this.querySelectorAll("td")) cell.textContent = originals.get(cell);
        if (scenario === "interrupted") document.dispatchEvent(new window.Event("wheel"));
        if (scenario === "changed") history.replaceState({}, "", "/symbol/INTC/peers/comparison");
        if (scenario === "challenge") document.title = "Verify you are human";
        if (scenario === "locked") this.querySelector("td").innerHTML = '<a href="/subscribe">Subscribe</a>';
        if (scenario === "pagination") this.insertAdjacentHTML("beforeend", '<button>Next page</button>');
        if (scenario === "icon_page") this.insertAdjacentHTML("beforeend", '<button aria-label="Next page">&gt;</button>');
        if (scenario === "replaced") { const main=document.querySelector("main"); main.replaceWith(main.cloneNode(true)); }
        if (scenario === "stuck") { this.querySelector("td").textContent = ""; Date.now = () => 99999999999999; }
        if (scenario === "virtualized" && this !== document.querySelector("section")) document.querySelector("td").textContent = "";
      };
    '''.replace("SCENARIO", json.dumps(scenario)))
    run = subprocess.run(["node", str(ROOT / "tests/js/run_sa_extension_fixture.mjs"), str(fixture), str(harness),
                          str(ROOT / "extensions/sa_alpha_picks/scrape_company_research.js")],
                         env={**os.environ, "ARKSCOPE_FIXTURE_URL": payload["source_url"]}, cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("scenario", ["loaded", "lazy"])
def test_actual_async_extractor_native_and_reader_accept_complete_tables(local, tmp_path, dataset, scenario):
    from src.sa_native_host import handle_message

    extracted = extract_research(tmp_path, research_capture(dataset), scenario)
    assert extracted["status"] == "ok", extracted
    receipt = handle_message({"action": "save_company_data", "capture": extracted["capture"]})
    assert receipt["status"] == "ok", receipt
    result = get_sa_company_data(local[0], "AMD", dataset=dataset)
    assert result["observation_id"] == receipt["observation_id"]
    assert result["coverage"]["table_count"] == len(extracted["capture"]["tables"])


@pytest.mark.parametrize("scenario,code", [("interrupted", "capture_interrupted"), ("changed", "page_changed"),
                                         ("challenge", "human_verification_required"), ("locked", "access_restricted"),
                                         ("pagination", "pagination_unverified"), ("stuck", "dom_not_ready"),
                                         ("icon_page", "pagination_unverified"), ("replaced", "page_changed"),
                                         ("virtualized", "dom_not_ready")])
def test_loading_failure_is_not_saved_or_retried_automatically(tmp_path, scenario, code):
    assert extract_research(tmp_path, research_capture("peers"), scenario) == {"status": "error", "error_code": "sa_company_" + code}


def test_disabled_source_never_starts_scrolling_or_saving():
    from tests.test_sa_extension_popup import _run_background_probe

    probe = _run_background_probe('''
      chrome.tabs.get = async () => ({url:"https://seekingalpha.com/symbol/AMD/peers/comparison"});
      chrome.scripting.executeScript = async () => { throw new Error("must not scroll before admission"); };
      const actions=[];
      sendNativeMessage2 = async request => {actions.push(request.action);return {status:"error",error_code:"data_source_not_selected"};};
      const result=await captureCompanyData({id:5,url:"https://seekingalpha.com/symbol/AMD/peers/comparison"},SAExtensionDiagnostics.createCollector());
      return {result,actions};
    ''')
    assert probe["result"]["error_code"] == "data_source_not_selected"
    assert probe["actions"] == ["get_company_capture_admission"]


@pytest.mark.parametrize("dataset", DATASETS)
def test_missing_capture_points_to_the_supported_company_page_without_network(local, dataset):
    result = get_sa_company_data(local[0], "AMD", dataset=dataset)
    assert result["capture_url"] == "https://seekingalpha.com/symbol/AMD/" + DATASETS[dataset][0]
    assert result["error_code"] == "sa_company_capture_missing"
    assert not local[1].exists()


def test_oversized_research_page_remains_whole_json_and_recoverable(local):
    from src.sa.company_data import company_result_reducer

    receipt = save_capture(research_capture("peers"))
    result = get_sa_company_data(local[0], "AMD", dataset="peers", table="card-container-growth")
    limited, diagnostic = company_result_reducer(json.dumps(result), budget=1000)
    error = json.loads(limited)
    assert error["error_code"] == "sa_company_page_too_large"
    assert error["observation_id"] == receipt["observation_id"]
    assert diagnostic["failure"] == error["error_code"]
    assert "rows" not in error and len(limited) < 1000
