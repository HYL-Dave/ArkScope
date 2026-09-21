"""Admit recognized SA research tables without treating forecasts as filings."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
from urllib.parse import urlsplit

from src.sa.company_data import (
    CompanyDataFailure, _MONTHS, canonical_json, clean_value, digest, require, symbol,
)
from src.tools.result_policy import MAX_OUTPUT_BYTES


LAYOUT_ID = "sa.company-research.v1"
DATASETS = {
    "valuation": ("valuation/metrics", "Valuation", "snapshot", "provider_metrics_and_grades"),
    "peers": ("peers/comparison", "Comparison", "snapshot", "provider_comparison"),
    "estimates": ("earnings/estimates", "Earnings Estimates", "annual", "analyst_consensus"),
    "revisions": ("earnings/revisions", "Earnings Revisions", "annual", "analyst_consensus_revisions"),
}
ROUTES = {"valuation": "sa_company_valuation", "peers": "sa_company_valuation",
          "estimates": "sa_company_estimates", "revisions": "sa_company_estimates"}
# Row labels are semantic identities. A renamed/reordered metric is not a new baseline.
PEER_ROWS = {
    "profile": ("Profile", ["Company Name", "Sector", "Industry", "Market Cap", "Enterprise Value",
                             "Employees", "SA Analysts Covering", "Wall St. Analysts"]),
    "ratings": ("Ratings", ["Quant Rating", "SA Analysts Rating", "Wall St. Analysts Rating"]),
    "quant-rankings": ("Quant Rankings", ["Sector", "Sector Rank", "Industry", "Industry Rank"]),
    "quant-factor-grades": ("Quant Factor Grades", ["Valuation", "Growth", "Profitability", "Momentum", "EPS Revisions"]),
    "trading": ("Trading", ["Last Close", "52 Week High", "52 Week Low", "Price vs. 52 Week High",
                             "Price vs. 52 Week Low", "Week Volume/Shares"]),
    "total-return": ("Total Return", ["1 Month Return", "3 Month Return", "6 Month Return", "9 Month Return",
                                      "YTD Return", "1 Year Return", "3 Year Return", "5 Year Return", "10 Year Return"]),
    "dividends": ("Dividends", ["Dividend Yield (FWD)", "Dividend Yield (TTM)", "4 Year Average Yield",
                               "Dividend Rate (FWD)", "Dividend Rate (TTM)", "Payout Ratio", "Dividend Growth 3 Yr (CAGR)",
                               "Dividend Growth 5 Yr (CAGR)", "Consecutive Years of Dividend Growth", "Dividend Frequency"]),
    "dividend-grades": ("Dividend Grades", ["Dividend Safety", "Dividend Growth", "Dividend Yield", "Dividend Consistency"]),
    "valuation": ("Valuation", ["P/E Non-GAAP (FY1)", "P/E Non-GAAP (FY2)", "P/E Non-GAAP (FY3)",
                               "P/E Non-GAAP (TTM)", "P/E GAAP (FWD)", "P/E GAAP (TTM)", "PEG Non-GAAP (FWD)",
                               "PEG GAAP (TTM)", "Price/Sales (TTM)", "EV/Sales (FWD)", "EV/Sales (TTM)",
                               "EV/EBITDA (FWD)", "EV/EBITDA (TTM)", "Price to Book (TTM)", "Price/Cash Flow (TTM)"]),
    "growth": ("Growth", ["Revenue Growth (YoY)", "Revenue Growth (FWD)", "Revenue 3 Year (CAGR)", "Revenue 5 Year (CAGR)",
                         "EBITDA Growth (YoY)", "EBITDA Growth (FWD)", "EBITDA 3 Year (CAGR)", "EBIT 3 Year (CAGR)",
                         "Net Income 3 Year (CAGR)", "EPS Growth Diluted (YoY)", "EPS Growth Diluted (FWD)",
                         "EPS Diluted 3 Year (CAGR)", "Tang Book Value 3 Year (CAGR)", "Total Assets 3 Year (CAGR)",
                         "Levered FCF 3 Year (CAGR)"]),
    "profitability": ("Profitability", ["Gross Profit Margin", "EBIT Margin", "EBITDA Margin", "Net Income Margin",
                                       "Levered FCF Margin", "Return on Common Equity (TTM)", "Return on Assets",
                                       "Return on Total Capital", "Cash From Operations", "Revenue Per Employee",
                                       "Net Income Per Employee", "Asset Turnover"]),
    "ownership": ("Ownership", ["Shares Outstanding", "Float %", "Insider Shares", "Insider %", "Institutional Shares", "Institutional %"]),
    "performance": ("Performance", ["1 Month Price Performance", "3 Month Price Performance", "6 Month Price Performance",
                                     "9 Month Price Performance", "YTD Price Performance", "1Y Price Performance",
                                     "3 Year Price Performance", "5 Year Price Performance", "10 Year Price Performance"]),
    "risk": ("Risk", ["Short Interest", "24M Beta", "60M Beta", "Altman Z Score"]),
    "eps-revisions": ("EPS Revisions", ["EPS: FQ1 Up Revisions", "EPS: FQ1 Down Revisions", "Revenue: FQ1 Up Revisions",
                                       "Revenue: FQ1 Down Revisions", "EPS Beats (last 2 years)", "Revenue Beats (last 2 years)"]),
    "income-statement-ttm": ("Income Statement (TTM)", ["Revenue", "Revenue Per Share", "EPS Diluted", "Net Income",
                                                      "Gross Profit", "EBITDA", "Operating Income", "Net Income Avail. to Comm."]),
    "balance-sheet-mrq": ("Balance Sheet (MRQ)", ["Total Cash", "Total Cash Per Share", "Total Debt", "Net Debt",
                                               "Total Debt to Equity", "Short Term Debt", "Long Term Debt", "Current Ratio",
                                               "Quick Ratio", "Covered Ratio", "Book Value Per Share", "Debt/Free Cash Flow",
                                               "Long Term Debt/Total Capital"]),
    "cash-flow-statement-ttm": ("Cash Flow Statement (TTM)", ["Net Operating Cash Flow", "Levered Free Cash Flow",
                                                           "Cash from Operations", "Capital Expenditures"]),
}
VALUATION_ROWS = ["P/E Non-GAAP (TTM)", "P/E Non-GAAP (FWD)", "P/E GAAP (TTM)", "P/E GAAP (FWD)",
                  "PEG GAAP (TTM)", "PEG Non-GAAP (FWD)", "EV / Sales (TTM)", "EV / Sales (FWD)",
                  "EV / EBITDA (TTM)", "EV / EBITDA (FWD)", "EV / EBIT (TTM)", "EV / EBIT (FWD)",
                  "Price / Sales (TTM)", "Price / Sales (FWD)", "Price / Book (TTM)", "Price / Book (FWD)",
                  "Price / Cash Flow (TTM)", "Price / Cash Flow (FWD)", "Dividend Yield (TTM)"]
_KEYS = {"schema_version", "layout_id", "source_url", "ticker", "title", "heading", "captured_at",
         "dataset", "view", "tables", "loading"}


def _text(value):
    require(type(value) is str and bool(value.strip()))
    return " ".join(value.split())


def display_cell(raw, kind="number"):
    """Keep display rounding/scale; a dollar symbol alone does not establish ISO currency."""
    value = _text(raw)
    if re.fullmatch(r"-\s*Rating:\s*Not Covered", value, re.I):
        return {"raw": raw, "status": "not_covered", "number": None, "notation": None}
    if value in {"-", "\u2014", "N/A", "NM", "N/M", "N.M.", "NA", "Not Applicable"}:
        return clean_value(value)
    require(not re.search(r"subscribe|upgrade|sign in|log in|unlock", value, re.I), "sa_company_access_restricted")
    base = {"raw": raw, "status": "value", "number": None, "notation": kind}
    if kind == "text":
        return base
    if kind == "rating":
        require(value.upper() in {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}, "sa_company_value_unrecognized")
        return {**base, "rating": value.upper()}
    if kind == "grade":
        require(bool(re.fullmatch(r"[ABCD][+-]?|F", value)), "sa_company_value_unrecognized")
        return {**base, "grade": value}
    if kind == "rank":
        match = re.fullmatch(r"([1-9]\d*) out of ([1-9]\d*)", value, re.ASCII)
        require(match is not None and Decimal(match[1]) <= Decimal(match[2]), "sa_company_value_unrecognized")
        return {**base, "rank": match[1], "total": match[2]}
    if kind == "frequency":
        require(value in {"Monthly", "Quarterly", "Semiannual", "Semi-Annual", "Annual", "Other", "Irregular"}, "sa_company_value_unrecognized")
        return base
    if kind == "years":
        match = re.fullmatch(r"(\d+) Years?", value, re.ASCII)
        require(match is not None, "sa_company_value_unrecognized")
        return {**base, "number": match[1]}
    currency_symbol = "$" if "$" in value else None
    suffix = re.search(r"([KMBT])(?=\)?$)", value)
    multiplier = {"K": "1000", "M": "1000000", "B": "1000000000", "T": "1000000000000"}.get(suffix[1]) if suffix else "1"
    if suffix:
        value = value[:suffix.start()] + value[suffix.end():]
    cell = clean_value(value, currency="USD" if currency_symbol else None)
    require(not (suffix and cell["notation"] == "percent"), "sa_company_value_unrecognized")
    if kind == "percent":
        require(cell["notation"] == "percent", "sa_company_value_unrecognized")
    elif kind == "integer":
        require(not suffix and not currency_symbol and bool(re.fullmatch(r"\d+", cell["number"])), "sa_company_value_unrecognized")
    elif kind == "number":
        require(cell["notation"] != "percent", "sa_company_value_unrecognized")
    return {**cell, "raw": raw, "multiplier": multiplier, "currency_symbol": currency_symbol, "currency": None}


def _peer_kind(section, label):
    if label in {"Company Name", "Sector", "Industry"}:
        return "text"
    if section == "ratings":
        return "rating"
    if section in {"quant-factor-grades", "dividend-grades"}:
        return "grade"
    if section == "quant-rankings":
        return "rank"
    if label == "Dividend Frequency":
        return "frequency"
    if label == "Consecutive Years of Dividend Growth":
        return "years"
    if section in {"total-return", "growth", "performance"} or "%" in label or label in {
        "Price vs. 52 Week High", "Price vs. 52 Week Low", "Week Volume/Shares", "Dividend Yield (FWD)",
        "Dividend Yield (TTM)", "4 Year Average Yield", "Payout Ratio", "Dividend Growth 3 Yr (CAGR)",
        "Dividend Growth 5 Yr (CAGR)", "Gross Profit Margin", "EBIT Margin", "EBITDA Margin", "Net Income Margin",
        "Levered FCF Margin", "Return on Common Equity (TTM)", "Return on Assets", "Return on Total Capital",
        "Short Interest", "Total Debt to Equity", "Long Term Debt/Total Capital",
    }:
        return "percent"
    if section == "eps-revisions" or label in {"Employees", "SA Analysts Covering", "Wall St. Analysts"}:
        return "integer"
    return "number"


def expected_tables(dataset):
    if dataset == "peers":
        return ["card-container-" + key for key in PEER_ROWS]
    if dataset == "valuation":
        return ["card-container-valuation-metrics"]
    if dataset == "estimates":
        return ["consensus-normalized-estimates-card", "consensus-revenues-estimates-card"]
    return ["consensus-eps-revision-trend-card", "consensus-revenue-revision-trend-card"]


def _forecast_headers(dataset, index):
    estimate = "EPS Estimate" if index == 0 else "Revenue Estimate"
    if dataset == "estimates":
        return list(zip(["fiscal_period", "estimate", "yoy", "fwd_pe", "low", "high", "num_analysts"],
                        ["Fiscal Period Ending", estimate, "YoY Growth", "Forward PE" if index == 0 else "FWD Price/Sales",
                         "Low", "High", "# of Analysts"]))
    return list(zip(["fiscal-period-ending", "estimate", "yoy-growth", "1m-trend", "3m-trend", "6m-trend"],
                    ["Fiscal Period Ending", estimate, "YoY Growth", "1M Trend", "3M Trend", "6M Trend"]))


def normalize_research_capture(payload, *, now=None):
    require(type(payload) is dict and set(payload) == _KEYS)
    require(type(payload["schema_version"]) is int and payload["schema_version"] == 2 and payload["layout_id"] == LAYOUT_ID)
    try:
        size = len(canonical_json(payload).encode("utf-8"))
        url = urlsplit(payload["source_url"])
        captured = datetime.fromisoformat(payload["captured_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError, OverflowError, RecursionError) as exc:
        raise CompanyDataFailure("sa_company_layout_unrecognized") from exc
    require(size <= MAX_OUTPUT_BYTES, "sa_company_capture_too_large")
    require(captured.tzinfo is not None and captured <= (now or datetime.now(timezone.utc)) + timedelta(minutes=5),
            "sa_company_capture_time_invalid")
    ticker = symbol(payload["ticker"])
    dataset = payload["dataset"]
    require(type(dataset) is str and dataset in DATASETS, "sa_company_dataset_invalid")
    path, title, view, data_kind = DATASETS[dataset]
    require(payload["ticker"] == ticker and url.scheme == "https" and url.netloc == "seekingalpha.com"
            and url.path == f"/symbol/{ticker}/{path}" and not url.query and not url.fragment
            and f"({ticker})" in _text(payload["title"]) and title in payload["title"]
            and _text(payload["heading"]).startswith(ticker + " - "), "sa_company_identity_mismatch")
    require(payload["view"] == view, "sa_company_view_unsupported")
    require(payload["loading"] == {"strategy": "bounded_section_scroll", "pagination": "no_pagination_controls"},
            "sa_company_loading_unverified")
    raw_tables = payload["tables"]
    require(type(raw_tables) is list and all(type(t) is dict and set(t) == {"id", "headers", "rows"} for t in raw_tables))
    require([t["id"] for t in raw_tables] == expected_tables(dataset))
    tables, peer_symbols, forecast_periods = [], None, None
    structure = []
    for index, raw in enumerate(raw_tables):
        headers, rows = raw["headers"], raw["rows"]
        require(type(headers) is list and len(headers) >= 2 and all(type(h) is dict and set(h) == {"id", "label"} for h in headers))
        require(type(rows) is list and bool(rows) and all(type(r) is dict and set(r) == {"label", "values"} for r in rows))
        require(all(type(r["label"]) is str and bool(r["label"]) for r in rows))
        section = raw["id"].removeprefix("card-container-")
        if dataset == "peers":
            name, labels = PEER_ROWS[section]
            symbols = [symbol(h["label"]) for h in headers[1:]]
            require(symbols[0] == ticker and len(set(symbols)) == len(symbols), "sa_company_identity_mismatch")
            require(peer_symbols is None or symbols == peer_symbols, "sa_company_identity_mismatch")
            peer_symbols = symbols
            expected = [("label", name)] + [("ticker-" + s, s) for s in symbols]
            kinds = [_peer_kind(section, r["label"]) for r in rows]
        elif dataset == "valuation":
            name, labels = "Valuation Measures", VALUATION_ROWS
            expected = list(zip(["metricName", "grade", "symbolValue", "sectorMedian", "sectorDiff", "5yavg", "5yavgDiff"],
                                ["Type", "Sector Relative Grade", ticker, "Sector Median", "% Diff. to Sector", ticker + " 5Y Avg.", "% Diff. to 5Y Avg."]))
        else:
            name = ("EPS" if index == 0 else "Revenue") + (" Estimates" if dataset == "estimates" else " Revisions")
            expected = _forecast_headers(dataset, index)
            labels = [r["label"] for r in rows]
        require(headers == [{"id": key + "-header", "label": label} for key, label in expected])
        require([r["label"] for r in rows] == labels and len(set(labels)) == len(labels))
        cleaned, months = [], []
        for row_index, row in enumerate(rows):
            label = _text(row["label"])
            require(type(row["values"]) is list and len(row["values"]) == len(headers) - 1)
            if dataset == "peers":
                cells = [display_cell(v, kinds[row_index]) for v in row["values"]]
            elif dataset == "valuation":
                ratio = "percent" if label == "Dividend Yield (TTM)" else "number"
                cells = [display_cell(v, k) for v, k in zip(row["values"], ["grade", ratio, ratio, "percent", ratio, "percent"])]
            else:
                match = re.fullmatch(r"([A-Z][a-z]{2}) (\d{4})", label, re.ASCII)
                require(match is not None and match[1] in _MONTHS)
                months.append(f"{match[2]}-{_MONTHS[match[1]]:02d}")
                kinds = ["number", "percent", "number", "number", "number", "integer"] if dataset == "estimates" else ["number", "percent", "percent", "percent", "percent"]
                cells = [display_cell(v, k) for v, k in zip(row["values"], kinds)]
                if dataset == "estimates" and all(cells[i]["status"] == "value" for i in (0, 3, 4)):
                    try:
                        mean, low, high = (Decimal(cells[i]["number"]) * Decimal(cells[i]["multiplier"]) for i in (0, 3, 4))
                    except ArithmeticError as exc:
                        raise CompanyDataFailure("sa_company_value_unrecognized") from exc
                    require(low <= mean <= high, "sa_company_estimate_range_inconsistent")
            result = {"label": label, "section": name, "cells": cells}
            if months:
                result["period"] = {"kind": "annual", "end_month": months[-1], "period_end": None}
            cleaned.append(result)
        if dataset in {"estimates", "revisions"}:
            require(months == sorted(months) and len({m[:4] for m in months}) == len(months))
            require(forecast_periods is None or months == forecast_periods)
            forecast_periods = months
        columns = [{"label": h["label"], "role": "company" if dataset == "peers" else h["id"].removesuffix("-header")} for h in headers[1:]]
        tables.append({"id": raw["id"], "title": name, "columns": columns, "rows": cleaned})
        if dataset in {"estimates", "revisions"}:
            tables[-1]["earnings_basis"] = "not_applicable" if index else (
                "provider_normalized" if dataset == "estimates" else "not_declared_in_table")
        structure.append({"id": raw["id"], "columns": ["company*"] if dataset == "peers" else headers,
                          "rows": "annual_periods" if dataset in {"estimates", "revisions"} else labels})
    cells = [c for table in tables for r in table["rows"] for c in r["cells"]]
    require(any(c["number"] is not None for c in cells), "sa_company_values_unavailable")
    body = {
        "provider": "seeking_alpha", "ticker": ticker, "dataset": dataset,
        # Existing store indexes this internal scope column; no second observation store.
        "statement": dataset, "view": view, "currency": "DISPLAY",
        "source_url": payload["source_url"], "layout_id": LAYOUT_ID,
        "structure_sha256": digest(structure), "data_kind": data_kind,
        "provider_data_at": None, "price_qualification": "not_live_quote",
        "precision": "provider_display_rounded", "value_basis": "provider_display_not_rescaled",
        "tables": tables,
        "coverage": {"scope": "recognized_page_tables", "table_count": len(tables),
                     "row_count": sum(len(t["rows"]) for t in tables),
                     "column_count": max(len(t["columns"]) for t in tables),
                     "missing_cells": sum(c["status"] != "value" for c in cells)},
        "limitations": ["captured_tables_only", "capture_time_is_not_provider_update_time",
                        "currency_not_independently_established", "not_original_filing_facts"],
    }
    if dataset == "peers":
        body["peer_selection"] = {"symbols": peer_symbols, "basis": "displayed_comparison_set",
                                  "authority": "seeking_alpha_page_or_operator", "rules_verified": False,
                                  "classification": "judgment_not_financial_fact"}
    return {"observation_id": digest(body), "captured_at": captured.astimezone(timezone.utc).isoformat(), "body": body}
