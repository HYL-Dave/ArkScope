"""Exact stored query contracts against disposable, canonical SQLite stores."""

import base64
import json
import shutil

import pytest

from src.sec_research.facts import parse_companyfacts
from src.sec_research.paths import SecResearchPaths
from src.sec_research.queries import StoredQueries
from src.sec_research.store import Store


CIK = "0000320193"
WHEN = "2026-09-11T12:00:00Z"
MISSING_ID = "secfact_" + "0" * 64


@pytest.fixture
def store(tmp_path):
    result = Store(SecResearchPaths(tmp_path / "market.db"))
    result.install()
    return result


def fact(value="100", *, concept="Assets", namespace="us-gaap", unit="EUR", **fields):
    return namespace, concept, unit, dict(
        val=value, end="2025-12-31", filed="2026-01-15",
        accn="0000320193-26-000001", form="10-K", fy=2025, fp="FY",
    ) | fields


def publish(store, rows, *, cik=CIK):
    payload = {"cik": int(cik), "facts": {}}
    for namespace, concept, unit, values in rows:
        units = payload["facts"].setdefault(namespace, {}).setdefault(concept, {"units": {}})["units"]
        units.setdefault(unit, []).append(values)
    # Fixture input numbers are raw JSON numeric tokens, never decoded floats.
    raw = json.dumps(payload)
    import re
    raw = re.sub(r'"val": "([-+0-9.eE]+)"', r'"val": \1', raw).encode()
    parsed = parse_companyfacts(raw, cik=cik)
    with store.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO sec_research_objects VALUES (?, ?, ?)",
                     (parsed.sha256, "objects/" + parsed.sha256, len(raw)))
    sid = store.publish(parsed, object_sha256=parsed.sha256, observed_at=WHEN,
                        source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    return sid, [row.fact_id for row in parsed.facts]


def receipt(store, sid=None, *, pending=(), gaps=()):
    return store.record_receipt(
        CIK, status="partial" if pending or gaps else "ok",
        completed=["companyfacts"] if sid else [], pending=list(pending), gaps=list(gaps),
        observed_at=WHEN,
        source_snapshots={"companyfacts": {"snapshot_id": sid, "observed_at": WHEN}} if sid else {},
    )


def query(store, **params):
    service = StoredQueries(store)
    assert callable(getattr(service, "facts", None)), "stored fact queries missing"
    return service.facts(CIK, **params)


def values(page):
    return [row["value"] for row in page["data"]]


def codes(page):
    return {gap["code"] for gap in page["gaps"]}


@pytest.mark.parametrize("kind,params,expected", [
    ("filings", {"forms": ["10-k", "10-K", " 10-Q "]}, {
        "forms": ["10-K", "10-Q"], "filed_from": None, "filed_to": None,
        "include_amendments": True, "limit": 20}),
    ("facts", {"metrics": [" assets ", "assets"], "concepts": ["us-gaap:Assets"]}, {
        "metrics": ["assets"], "concepts": ["us-gaap:Assets"], "accession": None,
        "as_of": None, "period": "all", "start": None, "end": None, "revisions": "latest", "limit": 40}),
    ("facts", {"fact_ids": [MISSING_ID, MISSING_ID]}, {"fact_ids": [MISSING_ID], "limit": 40}),
])
def test_shared_query_operand_validation_normalizes_without_storage(monkeypatch, kind, params, expected):
    import src.sec_research.queries as queries
    validator = getattr(queries, "validate_query", None)
    assert callable(validator), "shared storage-independent query validation missing"

    def forbidden(*args, **kwargs):
        pytest.fail("pure validation constructed or read storage")

    monkeypatch.setattr(Store, "__init__", forbidden)
    monkeypatch.setattr(Store, "connect", forbidden)
    assert validator(" CIK:320193 ", kind, **params) == expected


def test_exact_decimal_non_usd_and_complete_original_provenance(store):
    sid, ids = publish(store, [fact("1234567890123456789.123")])
    saved = receipt(store, sid)
    page = query(store, concepts=["us-gaap:Assets"])
    assert set(page) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
    assert page["status"] == "ok"
    assert values(page) == ["1234567890123456789.123"]
    row = page["data"][0]
    assert row["unit"] == "EUR"
    assert row["fact_id"] == ids[0]
    assert row["snapshot_id"] == sid
    assert row["source"]["sha256"] == row["object_sha256"]
    assert row["source"]["pointer"] == "/facts/us-gaap/Assets/units/EUR/0"
    assert row["source_url"].endswith("CIK0000320193.json")
    assert row["period"] == "instant"
    assert row["start"] is None and row["end"] == "2025-12-31"
    assert page["coverage"]["receipt_id"] == saved["receipt_id"]


def test_as_of_is_filed_availability_not_period_end(store):
    sid, _ = publish(store, [fact("10"), fact("20", filed="2026-03-01", form="10-K/A",
                                                        accn="0000320193-26-000002")])
    receipt(store, sid)
    page = query(store, as_of="2026-02-01")
    assert values(page) == ["10"]
    assert all(row["filed_date"] <= "2026-02-01" for row in page["data"])
    assert values(query(store, as_of="2026-03-01")) == ["20"]
    assert values(query(store, revisions="all")) == ["20", "10"]
    assert values(query(store, accession="0000320193-26-000001")) == ["10"]


def test_same_latest_date_competing_values_remain_visible(store):
    sid, _ = publish(store, [fact("1", filed="2026-01-01"), fact("2"),
                            fact("3", accn="0000320193-26-000003")])
    receipt(store, sid)
    page = query(store)
    assert set(values(page)) == {"2", "3"}
    assert page["status"] == "partial"
    assert "fact_value_conflict" in codes(page)


def test_revision_identity_includes_namespace_unit_start_and_end(store):
    sid, _ = publish(store, [fact("1"), fact("2", namespace="custom"), fact("3", unit="JPY"),
        fact("4", start="2025-01-01"), fact("5", start="2025-10-01"), fact("6", end="2024-12-31")])
    receipt(store, sid)
    assert set(values(query(store))) == {"1", "2", "3", "4", "5", "6"}


def test_missing_unbound_failed_and_observed_empty_are_distinct(store):
    assert query(store)["status"] == "unavailable"
    sid, _ = publish(store, [])
    assert query(store)["status"] == "unavailable"
    receipt(store, sid)
    assert query(store)["status"] == "empty"
    receipt(store, pending=["companyfacts"])
    assert query(store)["status"] == "unavailable"
    assert query(store)["data"] == []


def test_catalog_incompleteness_does_not_erase_usable_facts(store):
    sid, _ = publish(store, [fact()])
    receipt(store, sid, pending=["submissions"], gaps=[{"source": "submissions", "code": "failed"}])
    page = query(store)
    assert page["status"] == "ok"
    assert values(page) == ["100"]
    assert page["coverage"]["catalog_pending"] == 1
    assert page["coverage"]["catalog_source_gaps"] == 1
    receipt(store, sid, gaps=[{"source": "companyfacts", "code": "failed"}])
    assert query(store)["status"] == "partial"


def test_metric_alternatives_are_visible_with_conflicts_and_missing_gaps(store):
    sid, _ = publish(store, [fact("10", concept="Revenues"),
                            fact("20", concept="SalesRevenueNet"), fact("30", namespace="custom")])
    receipt(store, sid)
    page = query(store, metrics=["revenue", "assets"], concepts=["custom:Assets", "custom:Absent"])
    assert set(values(page)) == {"10", "20", "30"}
    assert {"metric_alternatives_conflict", "metric_missing", "concept_missing"} <= codes(page)
    assert all(row["metrics"] == ["revenue"] for row in page["data"] if row["namespace"] == "us-gaap")


@pytest.mark.parametrize("metric,concept", [
    ("revenue", "SalesRevenueGoodsNet"), ("net_income", "ProfitLoss"),
    ("operating_income", "OperatingIncomeLoss"), ("assets", "Assets"),
    ("liabilities", "Liabilities"), ("equity", "StockholdersEquity"),
    ("cash", "CashCashEquivalentsAndShortTermInvestments"),
    ("operating_cash_flow", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ("capex", "PaymentsForCapitalImprovements"), ("eps", "EarningsPerShareDiluted"),
    ("shares", "WeightedAverageNumberOfDilutedSharesOutstanding"),
])
def test_reviewed_common_metric_mapping(store, metric, concept):
    sid, _ = publish(store, [fact("12", concept=concept)])
    receipt(store, sid)
    assert values(query(store, metrics=[metric])) == ["12"]


@pytest.mark.parametrize("start,end,fp,frame,expected", [
    (None, "2025-12-31", "FY", "CY2025Q4I", "instant"),
    ("2025-10-01", "2025-12-31", "FY", "CY2025Q4", "quarterly"),
    ("2025-01-01", "2025-12-31", "Q3", "CY2025", "annual"),
    ("2024-10-01", "2024-12-31", "Q2", "CY2024Q4", "quarterly"),
    ("2025-01-01", "2025-09-30", "Q3", "CY2025Q3", "unknown"),
    ("2025-01-01", "2025-03-31", "Q1", "CY2024Q1", "unknown"),
    ("2025-01-01", "2025-05-15", "Q2", None, "unknown"),
    ("2025-01-01", "2025-06-30", "Q2", None, "unknown"),
    ("2025-01-01", "2025-03-31", "Q3", None, "quarterly"),
    ("2024-10-01", "2025-09-30", "FY", None, "annual"),
])
def test_period_classification_never_uses_filing_fp_as_row_quarter(store, start, end, fp, frame, expected):
    fields = dict(end=end, fp=fp, frame=frame)
    if start:
        fields["start"] = start
    sid, _ = publish(store, [fact(**fields)])
    receipt(store, sid)
    page = query(store)
    assert page["data"][0]["period"] == expected
    assert page["data"][0]["start"] == start
    assert page["data"][0]["end"] == end
    assert ("period_unknown" in codes(page)) is (expected == "unknown")
    if expected == "unknown":
        filtered = query(store, period="quarterly")
        assert filtered["status"] == "partial"
        assert filtered["data"] == []


def test_quarterly_and_ytd_same_filing_require_matching_start_and_end_context(store):
    sid, _ = publish(store, [
        fact("5", start="2025-07-01", end="2025-09-30", fp="Q3"),
        fact("15", start="2025-01-01", end="2025-09-30", fp="Q3"),
        fact("3", start="2025-01-01", end="2025-03-31", fp="Q3"),
    ])
    receipt(store, sid)
    page = query(store, period="ytd")
    assert values(page) == ["15"]
    assert page["data"][0]["period"] == "ytd"
    assert set(values(query(store, period="quarterly"))) == {"3", "5"}
    assert values(query(store, start="2025-07-01", end="2025-09-30")) == ["5"]


def test_fact_cursor_pins_original_snapshot_after_refresh_restart_relocation(store, tmp_path):
    sid, _ = publish(store, [fact("1", end="2024-12-31"), fact("2")])
    receipt(store, sid)
    first = query(store, limit=1)
    newer, _ = publish(store, [fact("9")])
    receipt(store, newer)
    moved = tmp_path / "moved.db"
    shutil.copyfile(store.paths.market_db_path, moved)
    page = query(Store(SecResearchPaths(moved)), limit=1, cursor=first["next_cursor"])
    assert set(values(first) + values(page)) == {"1", "2"}
    assert page["coverage"]["receipt_id"] == first["coverage"]["receipt_id"]
    assert values(query(store)) == ["9"]


def test_fact_ids_reopen_all_original_revisions_without_latest_receipt(store, monkeypatch):
    sid, ids = publish(store, [fact("1"), fact("2", filed="2026-02-01")])
    receipt(store, sid)
    receipt(store, pending=["companyfacts"])
    monkeypatch.setattr(store, "latest_receipt", lambda *a: pytest.fail("fact ids consulted latest receipt"))
    page = query(store, fact_ids=ids)
    assert set(values(page)) == {"1", "2"}
    assert {row["fact_id"] for row in page["data"]} == set(ids)
    assert page["coverage"]["receipt_id"] is None


def test_id_cursor_freezes_missing_ids_and_rejects_changed_selection(store):
    _, ids = publish(store, [fact("1"), fact("2", filed="2026-02-01")])
    future_rows = [fact("9")]
    other = Store(SecResearchPaths(store.paths.market_db_path.parent / "future.db"))
    other.install()
    _, future_ids = publish(other, future_rows)
    requested = ids + future_ids
    first = query(store, fact_ids=requested, limit=1)
    assert "fact_id_missing" in codes(first)
    publish(store, future_rows)
    page = query(store, fact_ids=requested[::-1], limit=1, cursor=first["next_cursor"])
    assert set(values(first) + values(page)) == {"1", "2"}
    assert page["next_cursor"] is None
    assert "fact_id_missing" in codes(page)
    with pytest.raises(ValueError, match="sec_research_cursor_mismatch"):
        query(store, fact_ids=ids, limit=1, cursor=first["next_cursor"])
    assert query(store, fact_ids=[MISSING_ID])["status"] == "unavailable"


@pytest.mark.parametrize("params", [
    {"metrics": ["assets"]}, {"concepts": ["us-gaap:Assets"]},
    {"accession": "0000320193-26-000001"}, {"as_of": "2026-01-01"},
    {"period": "instant"}, {"start": "2025-01-01"}, {"end": "2025-12-31"},
    {"revisions": "all"},
])
def test_fact_ids_reject_selection_filters_before_storage(store, monkeypatch, params):
    monkeypatch.setattr(store, "connect", lambda *a, **k: pytest.fail("invalid selection read storage"))
    with pytest.raises(ValueError, match="^sec_research_query_invalid$"):
        query(store, fact_ids=[MISSING_ID], **params)


@pytest.mark.parametrize("params", [
    {"limit": True}, {"limit": 0}, {"limit": 101}, {"limit": 1.0},
    {"concepts": "us-gaap:Assets"}, {"concepts": ["Assets"]}, {"metrics": ["ratio"]},
    {"fact_ids": ["oops"]}, {"fact_ids": []}, {"as_of": "2026-02-30"},
    {"period": "ttm"}, {"period": "unknown"}, {"revisions": "first"}, {"accession": "x"},
    {"start": "2026-01-01", "end": "2025-01-01"},
])
def test_invalid_filters_fail_before_storage(store, monkeypatch, params):
    monkeypatch.setattr(store, "connect", lambda *a, **k: pytest.fail("invalid selection read storage"))
    with pytest.raises(ValueError, match="^sec_research_query_invalid$"):
        query(store, **params)


def test_fact_query_is_readonly_and_does_not_materialize_unbound_sources(store, monkeypatch):
    sid, _ = publish(store, [fact()])
    receipt(store, sid)
    before = store.paths.market_db_path.read_bytes()
    def forbidden(*a, **kw):
        pytest.fail("stored query used acquisition, mutation or unbounded source reads")
    for name in ("install", "publish", "record_receipt", "snapshots", "facts", "_observations", "snapshot_observations"):
        monkeypatch.setattr(store, name, forbidden)
    assert values(query(store)) == ["100"]
    assert store.paths.market_db_path.read_bytes() == before
    assert not store.paths.capture_root.exists()


def test_unavailable_store_is_sanitized_and_never_created(tmp_path):
    path = tmp_path / "missing" / "market.db"
    page = query(Store(SecResearchPaths(path)))
    assert page["status"] == "unavailable"
    assert not path.parent.exists()
    assert str(tmp_path) not in json.dumps(page)


def test_whole_fact_byte_envelope_skips_oversize_without_loop_or_truncation(store):
    sid, _ = publish(store, [fact("1", unit="X" * (256 * 1024)), fact("2", unit="JPY")])
    receipt(store, sid)
    page = query(store)
    assert values(page) == ["2"]
    page = query(store, cursor=page["next_cursor"])
    assert page["data"] == []
    assert "observation_too_large" in codes(page)
    assert page["next_cursor"] is None
    assert len(json.dumps(page).encode()) <= 256 * 1024


@pytest.mark.parametrize("ids_mode", [False, True])
def test_aggregate_budget_is_not_complete_or_empty(store, monkeypatch, ids_mode):
    from src.sec_research import queries
    sid, ids = publish(store, [fact("1"), fact("2", unit="JPY")])
    receipt(store, sid)
    monkeypatch.setattr(queries, "MAX_QUERY_ROWS", 1)
    page = query(store, **({"fact_ids": ids} if ids_mode else {}))
    assert page["status"] == "partial"
    assert "query_budget_exceeded" in codes(page)
    assert len(page["data"]) == 1


def test_date_filter_precedes_admission_budget(store, monkeypatch):
    from src.sec_research import queries
    sid, _ = publish(store, [fact("1", end="2024-12-31"), fact("2")])
    receipt(store, sid)
    monkeypatch.setattr(queries, "MAX_QUERY_ROWS", 1)
    page = query(store, start="2025-01-01", end="2025-12-31")
    assert values(page) == ["2"]
    assert page["status"] == "ok"


@pytest.mark.parametrize("ids_mode", [False, True])
@pytest.mark.parametrize("change", [{"kind": "filings"}, {"kind": "other"},
    {"bindings_digest": "0" * 64}, {"receipt_id": 9999},
    {"offset": True}, {"offset": 0}, {"offset": 9999}, {"v": 2}, {"extra": "x"}])
def test_fact_cursor_validates_kind_shape_and_binding(store, ids_mode, change):
    sid, ids = publish(store, [fact("1"), fact("2", unit="JPY")])
    receipt(store, sid)
    params = {"fact_ids": ids} if ids_mode else {}
    token = query(store, limit=1, **params)["next_cursor"]
    decoded = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    if change == {"kind": "other"}:
        change = {"kind": "facts" if ids_mode else "fact_ids"}
    mutated = base64.urlsafe_b64encode(json.dumps(decoded | change, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    with pytest.raises(ValueError, match="^sec_research_cursor_(invalid|mismatch)$"):
        query(store, limit=1, cursor=mutated, **params)


@pytest.mark.parametrize("changed", [{"metrics": ["assets"]}, {"as_of": "2026-12-31"},
    {"period": "instant"}, {"revisions": "all"}, {"limit": 2}])
def test_fact_cursor_rejects_changed_filters(store, changed):
    sid, _ = publish(store, [fact("1"), fact("2", unit="JPY")])
    receipt(store, sid)
    token = query(store, limit=1)["next_cursor"]
    with pytest.raises(ValueError, match="^sec_research_cursor_mismatch$"):
        query(store, cursor=token, **({"limit": 1} | changed))


def test_fact_ids_are_issuer_scoped_and_stable_after_relocation(store, tmp_path):
    _, foreign = publish(store, [fact("9")], cik="0000000001")
    sid, ids = publish(store, [fact("1"), fact("2", unit="JPY")])
    first = query(store, fact_ids=ids + foreign, limit=1)
    moved = tmp_path / "moved.db"
    shutil.copyfile(store.paths.market_db_path, moved)
    page = query(Store(SecResearchPaths(moved)), fact_ids=ids + foreign, limit=1, cursor=first["next_cursor"])
    assert set(values(first) + values(page)) == {"1", "2"}
    assert "fact_id_missing" in codes(page)
    assert all(row["snapshot_id"] == sid for row in first["data"] + page["data"])


@pytest.mark.parametrize("ids_mode", [False, True])
@pytest.mark.parametrize("bound", ["bytes", "sources"])
def test_source_and_byte_budget_before_admission_is_unavailable(store, monkeypatch, ids_mode, bound):
    from src.sec_research import queries
    sid, ids = publish(store, [fact()])
    receipt(store, sid)
    monkeypatch.setattr(queries, "MAX_QUERY_BYTES" if bound == "bytes" else "MAX_QUERY_SOURCES", 0)
    page = query(store, **({"fact_ids": ids} if ids_mode else {}))
    assert page["status"] == "unavailable"
    assert "query_budget_exceeded" in codes(page)


def test_corrupt_receipt_shape_is_closed_for_facts_but_not_needed_for_ids(store):
    _, ids = publish(store, [fact("7")])
    with store.connect() as conn:
        conn.execute("""INSERT INTO sec_research_receipts
            (cik, status, completed, pending, gaps, observed_at, recorded_at, source_snapshots)
            VALUES (?, 'ok', '[]', '[]', '[]', ?, ?, '[]')""", (CIK, WHEN, WHEN))
    assert query(store)["status"] == "unavailable"
    assert values(query(store, fact_ids=ids)) == ["7"]


def test_budget_limited_metric_and_concept_are_unresolved_not_missing(store, monkeypatch):
    from src.sec_research import queries
    sid, _ = publish(store, [fact("1"), fact("2", concept="Liabilities")])
    receipt(store, sid)
    monkeypatch.setattr(queries, "MAX_QUERY_ROWS", 1)
    page = query(store, metrics=["assets", "liabilities"], concepts=["us-gaap:Liabilities"])
    assert values(page) == ["1"]
    assert {"query_budget_exceeded", "metric_unresolved", "concept_unresolved"} <= codes(page)
    assert not {"metric_missing", "concept_missing"} & codes(page)


def test_unobserved_metrics_are_not_reported_as_missing(store):
    page = query(store, metrics=["assets"], concepts=["us-gaap:Assets"])
    assert page["status"] == "unavailable"
    assert {"metric_unresolved", "concept_unresolved"} <= codes(page)
    assert not {"metric_missing", "concept_missing"} & codes(page)
