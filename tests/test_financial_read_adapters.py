"""Actual local sources normalize without acquisition or invented period identities."""

import json
import sqlite3
from unittest.mock import Mock

import pytest

from src.fundamentals.contracts import FinancialQuery
from src.sa.company_data import digest
from src.sa.company_store import save_capture
from tests.financial_read_fixtures import financial_local, sa_payload, save_fd


def read_sa(dal, **kwargs):
    from src.fundamentals.adapters import read_sa_statements
    return read_sa_statements(dal, FinancialQuery(ticker=kwargs.pop("ticker", "AAPL"), **kwargs))


def test_sa_without_market_db(financial_local, tmp_path):
    dal, http, sec = financial_local
    payload = sa_payload()
    receipt = save_capture(payload)
    before = (tmp_path / "sa.db").read_bytes()
    result = read_sa(dal)
    row = result.statements["income_statement"][0]
    assert row.report_period is None and row.end_month == "2025-12" and row.fiscal_period is None
    assert row.period_precision == "month" and row.provider == "seeking_alpha"
    assert row.data["revenue"] == "123400000"
    assert row.value_metadata["revenue"].display_half_step == "50000"
    assert row.value_metadata["earnings_per_share"].normalized_value == "2.5"
    assert row.observation_id == receipt["observation_id"]
    assert result.observations[0].fetched_at == payload["captured_at"]
    assert result.observations[0].history == "retained_observation"
    assert (tmp_path / "sa.db").read_bytes() == before
    assert not (tmp_path / "market.db").exists() and not (tmp_path / "profile.db").exists()
    http.assert_not_called()
    sec.assert_not_called()


def test_special_columns_and_unmapped_rows_preserved(financial_local):
    from src.tools.sa_company_tools import get_sa_company_data
    dal, _, _ = financial_local
    payload = sa_payload(values={"Total Revenues": "123.4", "Net Income": "5.0", "Other Revenue": "42.0"})
    save_capture(payload)
    normalized = read_sa(dal).statements["income_statement"]
    assert [r.end_month for r in normalized] == ["2025-12", "2024-12"]
    raw = get_sa_company_data(dal, "AAPL")
    assert raw["columns"][0]["kind"] == "trailing"
    assert raw["rows"][2]["label"] == "Other Revenue"
    assert "Other Revenue" not in normalized[0].data
    assert normalized[0].raw_reference["tool"] == "get_sa_company_data"


@pytest.mark.parametrize("alias", ["BRK B", "BRK-B", "BRK.B"])
def test_sa_class_share_alias_keeps_source_identity(financial_local, alias):
    dal, _, _ = financial_local
    save_capture(sa_payload(ticker="BRK.B"))
    query = FinancialQuery(ticker=alias)
    from src.fundamentals.adapters import read_sa_statements
    result = read_sa_statements(dal, query)
    assert result.statements["income_statement"][0].raw_reference["ticker"] == "BRK.B"
    assert query.ticker == alias


@pytest.mark.parametrize("state,code", [
    ("missing", "sa_company_capture_missing"), ("empty_schema", "sa_company_capture_missing"),
    ("corrupt", "sa_company_store_unavailable"), ("digest", "sa_company_observation_invalid"),
])
def test_sa_failure_is_not_empty_success(financial_local, tmp_path, state, code):
    dal, _, _ = financial_local
    path = tmp_path / "sa.db"
    if state == "empty_schema":
        with sqlite3.connect(path):
            pass
    elif state == "corrupt":
        path.write_bytes(b"not a database")
    elif state == "digest":
        save_capture(sa_payload())
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE sa_company_observations SET body_json='{}'")
    result = read_sa(dal, statement="income_statement")
    assert result.statements.get("income_statement", []) == []
    assert [g.code for g in result.gaps] == [code]
    assert not result.observations


def test_duplicate_sa_labels_do_not_pick_first_value(financial_local):
    dal, _, _ = financial_local
    payload = sa_payload()
    payload["rows"] += [{"kind": "section", "label": "Other basis", "values": []},
                         {"kind": "data", "label": "Total Revenues", "values": ["", "9", "9", "9"]}]
    save_capture(payload)
    row = read_sa(dal).statements["income_statement"][0]
    assert row.data["revenue"] is None
    assert row.value_metadata["revenue"].status == "label_ambiguous"


@pytest.mark.parametrize("problem", ["unit", "currency", "duplicate_period"])
def test_unreviewed_sa_records_produce_gaps(financial_local, tmp_path, problem):
    dal, _, _ = financial_local
    save_capture(sa_payload())
    with sqlite3.connect(tmp_path / "sa.db") as conn:
        body = json.loads(conn.execute("SELECT body_json FROM sa_company_observations").fetchone()[0])
        if problem == "unit":
            body["unit_note"] = "In Billions (changed structure)"
        elif problem == "currency":
            body["unit_note"] = "In Millions of Euro (EUR) except per share items"
        else:
            body["columns"][2]["end_month"] = "2025-12"
        conn.execute("UPDATE sa_company_observations SET body_json=?, observation_id=?", (json.dumps(body), digest(body)))
    result = read_sa(dal, statement="income_statement")
    if problem == "duplicate_period":
        assert not result.statements["income_statement"]
        assert "financial_period_ambiguous" in [g.code for g in result.gaps]
    else:
        row = result.statements["income_statement"][0]
        assert row.data["revenue"] is None and row.value_metadata["revenue"].status == "unit_unknown"


@pytest.mark.parametrize("from_file", [False, True])
def test_fd_expired_retained_read_never_promotes(financial_local, tmp_path, monkeypatch, from_file):
    from src.fundamentals.adapters import read_fd_statements
    dal, http, sec = financial_local
    entry = save_fd(dal, from_file=from_file)
    write = Mock(side_effect=AssertionError("stored read tried to promote/write"))
    monkeypatch.setattr(dal._backend, "set_financial_cache", write)
    result = read_fd_statements(dal, FinancialQuery(ticker="AAPL"))
    row = result.statements["income_statement"][0]
    assert row.report_period == "2025-09-27" and row.period_precision == "day"
    assert row.data["revenue"] == 416161000000.0 and row.data["cost_of_revenue"] == 220960000000.0
    assert result.observations[0].fetched_at == entry["fetched_at"]
    assert result.observations[0].history == "current_retained_version_only"
    assert result.observations[0].retrieval == "stored"
    assert result.observations[0].within_max_age is None
    if from_file:
        assert not (tmp_path / "market.db").exists()
    write.assert_not_called()
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("value", [True, float("inf"), float("nan"), "NaN"])
def test_fd_nonfinite_and_boolean_cells_cannot_become_financial_numbers(financial_local, value):
    from src.fundamentals.adapters import read_fd_statements
    dal, _, _ = financial_local
    save_fd(dal, from_file=True, change=lambda rows: rows[0].update(revenue=value))
    result = read_fd_statements(dal, FinancialQuery(ticker="AAPL", statement="income_statement"))
    row = result.statements["income_statement"][0]
    assert row.data["revenue"] is None and row.value_metadata["revenue"].status == "invalid_value"
    assert any(g.metric == "revenue" and g.code == "invalid_value" for g in result.gaps)


def test_fd_same_month_conflict_is_not_silently_resolved(financial_local):
    from src.fundamentals.adapters import read_fd_statements
    dal, _, _ = financial_local
    save_fd(dal, change=lambda rows: rows.append({**rows[0], "report_period": "2025-09-30"}))
    result = read_fd_statements(dal, FinancialQuery(ticker="AAPL", statement="income_statement"))
    assert result.statements["income_statement"] == []
    assert "financial_period_ambiguous" in [g.code for g in result.gaps]


def test_fd_currency_is_not_relabelled_to_requested_currency(financial_local):
    from src.fundamentals.adapters import read_fd_statements
    dal, _, _ = financial_local
    save_fd(dal, change=lambda rows: rows[0].update(currency="EUR"))
    result = read_fd_statements(dal, FinancialQuery(ticker="AAPL", statement="income_statement"))
    assert result.statements["income_statement"][0].currency == "EUR"
    assert "currency_mismatch" in [g.code for g in result.gaps]


def test_stored_fd_reports_age_bound_without_using_it_as_fact_expiry(financial_local):
    from src.fundamentals.adapters import read_fd_statements
    dal, _, _ = financial_local
    save_fd(dal)
    result = read_fd_statements(dal, FinancialQuery(ticker="AAPL", statement="income_statement", max_age_seconds=60))
    assert result.statements["income_statement"][0].data["revenue"] == 416161000000.0
    assert result.observations[0].max_age_seconds == 60
    assert result.observations[0].within_max_age is False


def test_fd_statement_shapes_remain_distinct(financial_local):
    from src.fundamentals.adapters import read_fd_statements
    dal, _, _ = financial_local
    for kind in ("income_statement", "balance_sheet", "cash_flow_statement"):
        save_fd(dal, kind)
    result = read_fd_statements(dal, FinancialQuery(ticker="AAPL"))
    assert result.statements["balance_sheet"][0].data["current_assets"] == 150000000000.0
    assert result.statements["cash_flow_statement"][0].data["capital_expenditure"] == -12000000000.0
    assert len({r.observation_id for r in result.observations}) == 3
    assert not result.gaps
