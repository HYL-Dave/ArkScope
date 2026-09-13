"""Reported, exact Company Facts selection; no acquisition or derived numbers."""

from datetime import date
from decimal import Decimal
import json
import re
import sqlite3

from data_sources.sec_edgar_financials import (
    BALANCE_SHEET_MAPPING as BALANCE,
    CASH_FLOW_MAPPING as CASH_FLOW,
    INCOME_STATEMENT_MAPPING as INCOME,
)

from .common import normalize_cik
from .capture_lock import store_operation
from .queries import (
    open_fact_ids_query, open_query, page_envelope, query_date,
    read_bound_sources, unavailable_envelope, validate_query,
)


METRIC_CONCEPTS = {
    name: frozenset("us-gaap:" + concept for concept in concepts)
    for name, concepts in {
        "revenue": INCOME["revenue"],
        "net_income": INCOME["net_income"] + CASH_FLOW["net_income"],
        "operating_income": INCOME["operating_income"],
        "assets": BALANCE["total_assets"],
        "liabilities": BALANCE["total_liabilities"],
        "equity": BALANCE["shareholders_equity"],
        "cash": BALANCE["cash_and_equivalents"],
        "operating_cash_flow": CASH_FLOW["net_cash_flow_from_operations"],
        "capex": CASH_FLOW["capital_expenditure"],
        "eps": INCOME["earnings_per_share"] + INCOME["earnings_per_share_diluted"],
        "shares": BALANCE["outstanding_shares"] + INCOME["weighted_average_shares"]
                  + INCOME["weighted_average_shares_diluted"],
    }.items()
}
MAX_SELECTORS = 100


def _names(value, pattern):
    if value is None:
        return None
    if (not isinstance(value, (list, tuple)) or len(value) > MAX_SELECTORS
            or any(not isinstance(item, str) or not 1 <= len(item) <= 256
                   or re.fullmatch(pattern, item.strip()) is None for item in value)):
        raise ValueError("sec_research_query_invalid")
    return sorted({item.strip() for item in value}) or None


def fact_filters(*, metrics=None, concepts=None, fact_ids=None, accession=None, as_of=None,
                 period="all", start=None, end=None, revisions="latest", limit=40):
    if (type(limit) is not int or not 1 <= limit <= 100
            or not isinstance(period, str) or period not in ("all", "instant", "annual", "quarterly", "ytd")
            or not isinstance(revisions, str) or revisions not in ("latest", "all")):
        raise ValueError("sec_research_query_invalid")
    if fact_ids is not None:
        if (metrics is not None or concepts is not None or accession is not None or as_of is not None
                or period != "all" or start is not None or end is not None or revisions != "latest"):
            raise ValueError("sec_research_query_invalid")
        ids = _names(fact_ids, r"secfact_[0-9a-f]{64}")
        if not ids:
            raise ValueError("sec_research_query_invalid")
        return {"fact_ids": ids, "limit": limit}
    metrics = _names(metrics, r"[a-z_]+")
    concepts = _names(concepts, r"[^\s:]+:[^\s:]+")
    if metrics and any(metric not in METRIC_CONCEPTS for metric in metrics):
        raise ValueError("sec_research_query_invalid")
    if accession is not None and (not isinstance(accession, str)
                                  or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None):
        raise ValueError("sec_research_query_invalid")
    as_of, start, end = query_date(as_of), query_date(start), query_date(end)
    if start and end and start > end:
        raise ValueError("sec_research_query_invalid")
    return dict(metrics=metrics, concepts=concepts, accession=accession, as_of=as_of,
                period=period, start=start, end=end, revisions=revisions, limit=limit)


def _concept(row):
    return row["namespace"] + ":" + row["concept"]


def _identity(row):
    return row["namespace"], row["concept"], row["unit"], row["start"], row["end"]


def _duration_period(row):
    if row["start"] is None:
        return "instant"
    start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
    days = (end - start).days + 1
    candidate = "quarterly" if 61 <= days <= 121 else "annual" if 335 <= days <= 395 else "unknown"
    frame = row["frame"]
    if not frame:
        return candidate
    match = re.fullmatch(r"CY([0-9]{4})(?:Q([1-4]))?", frame)
    if match is None:
        return "unknown"
    year = int(match[1])
    if year == 0:
        return "unknown"
    quarter = int(match[2]) if match[2] else None
    month = 3 * quarter if quarter else 12
    expected_start = date(year, month - 2 if quarter else 1, 1)
    # Avoid constructing year 10000 at the final calendar boundary.
    expected_end = date(year, month, 31 if month in (3, 12) else 30)
    if (abs((start - expected_start).days) > 30 or abs((end - expected_end).days) > 30
            or candidate != ("quarterly" if quarter else "annual")):
        return "unknown"
    return candidate


def _periods(rows):
    projected = [{**row, "period": _duration_period(row)} for row in rows]
    # A 6/9-month duration alone is not proof of fiscal YTD. Require original
    # first and final quarter windows of this concept/unit in the same filing.
    quarters = {}
    for row in projected:
        if row["period"] == "quarterly":
            key = row["namespace"], row["concept"], row["unit"], row["accession"]
            starts, ends = quarters.setdefault(key, ({}, {}))
            starts[row["start"]] = min(starts.get(row["start"], row["end"]), row["end"])
            ends[row["end"]] = max(ends.get(row["end"], row["start"]), row["start"])
    for row in projected:
        if row["period"] != "unknown" or row["frame"] or row["start"] is None:
            continue
        days = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days + 1
        fp = row["fiscal_period"]
        if not (fp == "Q2" and 152 <= days <= 212 or fp == "Q3" and 243 <= days <= 303):
            continue
        key = row["namespace"], row["concept"], row["unit"], row["accession"]
        starts, ends = quarters.get(key, ({}, {}))
        first = starts.get(row["start"], row["end"]) < row["end"]
        last = ends.get(row["end"], row["start"]) > row["start"]
        if first and last:
            row["period"] = "ytd"
    return projected


def _latest(rows):
    dates = {}
    for row in rows:
        key = _identity(row)
        dates[key] = max(dates.get(key, ""), row["filed_date"])
    return [row for row in rows if row["filed_date"] == dates[_identity(row)]]


def _selection(rows, filters, gaps):
    rows = _periods(rows)
    if "fact_ids" not in filters and filters["revisions"] == "latest":
        rows = _latest(rows)
    unknown = sum(row["period"] == "unknown" for row in rows)
    if unknown:
        gaps.append({"code": "period_unknown", "count": unknown})
    if "fact_ids" not in filters and filters["period"] != "all":
        rows = [row for row in rows if row["period"] == filters["period"]]
    conflicts = {}
    for row in rows:
        conflicts.setdefault((*_identity(row), row["filed_date"]), set()).add(Decimal(row["value"]))
        row["metrics"] = sorted(name for name, concepts in METRIC_CONCEPTS.items() if _concept(row) in concepts)
    count = sum(len(variants) > 1 for variants in conflicts.values())
    if count:
        gaps.append({"code": "fact_value_conflict", "count": count})
    if "fact_ids" not in filters:
        present = {_concept(row) for row in rows}
        unresolved = any(gap["code"] in {"query_budget_exceeded", "companyfacts_unavailable",
                                        "facts_source_gaps", "period_unknown"} for gap in gaps)
        for concept in filters["concepts"] or []:
            if concept not in present:
                gaps.append({"code": "concept_unresolved" if unresolved else "concept_missing", "concept": concept})
        for metric in filters["metrics"] or []:
            alternatives = METRIC_CONCEPTS[metric]
            if not present & alternatives:
                gaps.append({"code": "metric_unresolved" if unresolved else "metric_missing", "metric": metric})
                continue
            windows = {}
            for row in rows:
                if _concept(row) in alternatives:
                    windows.setdefault((row["unit"], row["start"], row["end"]), set()).add(_concept(row))
            count = sum(len(concepts) > 1 for concepts in windows.values())
            if count:
                gaps.append({"code": "metric_alternatives_conflict", "metric": metric, "count": count})
    rows.sort(key=lambda row: (row["namespace"], row["concept"], row["unit"],
                              row["start"] or "", row["end"], row["accession"], row["fact_id"], row["snapshot_id"]))
    rows.sort(key=lambda row: row["filed_date"], reverse=True)
    return rows


@store_operation
def query_facts(store, cik, *, metrics=None, concepts=None, fact_ids=None, accession=None,
                as_of=None, period="all", start=None, end=None, revisions="latest",
                cursor=None, limit=40, result_fits=None):
    cik = normalize_cik(cik)
    filters = validate_query(cik, "facts", metrics=metrics, concepts=concepts, fact_ids=fact_ids,
                             accession=accession, as_of=as_of, period=period, start=start, end=end,
                             revisions=revisions, cursor=cursor, limit=limit)
    ids_mode = "fact_ids" in filters
    allowed = set(filters.get("concepts") or [])
    for metric in filters.get("metrics") or []:
        allowed.update(METRIC_CONCEPTS[metric])

    def selected(row):
        # Inclusive contained windows also retain any supporting YTD quarters.
        return not (allowed and _concept(row) not in allowed
                    or filters["accession"] and row["accession"] != filters["accession"]
                    or filters["as_of"] and row["filed_date"] > filters["as_of"]
                    or filters["start"] and (row["start"] or row["end"]) < filters["start"]
                    or filters["end"] and row["end"] > filters["end"])

    try:
        if ids_mode:
            context, bound = open_fact_ids_query(store, cik, filters=filters, cursor=cursor)
        else:
            context = open_query(store, cik, kind="facts", filters=filters, cursor=cursor)
            bound = read_bound_sources(store, context, kind="facts", row_filter=selected)
    except (sqlite3.Error, OSError, json.JSONDecodeError):
        return unavailable_envelope()
    except ValueError as exc:
        if str(exc) in {"sec_research_schema_mismatch", "sec_research_receipt_binding_invalid", "sec_research_receipt_invalid"}:
            return unavailable_envelope()
        raise
    gaps = list(bound.gaps)
    rows = [row for _, observations in bound.sources.values() for row in observations]
    coverage = {"facts_sources": len(bound.sources), "admitted_rows": bound.row_count,
                "admitted_bytes": bound.encoded_bytes, "mode": "fact_ids" if ids_mode else "snapshot"}
    if ids_mode:
        present = {row["fact_id"] for row in rows}
        for fact_id in filters["fact_ids"]:
            if fact_id not in present:
                gaps.append({"code": "fact_id_unresolved" if bound.gaps else "fact_id_missing", "fact_id": fact_id})
        coverage["snapshot_watermark"] = context.anchor_id
    else:
        if not bound.sources:
            gaps.append({"code": "companyfacts_unavailable"})
        receipt = context.receipt
        source_gaps = sum(gap.get("source") in (None, "companyfacts") for gap in receipt["gaps"]) if receipt else 0
        if source_gaps:
            gaps.append({"code": "facts_source_gaps", "count": source_gaps})
        coverage["catalog_pending"] = sum(source != "companyfacts" for source in receipt["pending"]) if receipt else 0
        coverage["catalog_source_gaps"] = sum(gap.get("source") not in (None, "companyfacts") for gap in receipt["gaps"]) if receipt else 0
    selection = _selection(rows, filters, gaps)
    return page_envelope(context, selection, limit=limit, gaps=gaps, available=bool(bound.sources),
                         coverage=coverage, result_fits=result_fits)
