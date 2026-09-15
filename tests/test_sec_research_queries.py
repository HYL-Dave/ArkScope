"""Offline receipt-bound catalog query contracts using disposable real SQLite."""

import base64
import importlib
import json
import shutil

import pytest

from src.sec_research.catalog import parse_submissions
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store


CIK = "0000320193"
WHEN = "2026-09-11T12:00:00Z"
HISTORY = "CIK0000320193-submissions-001.json"


def queries(store):
    assert importlib.util.find_spec("src.sec_research.queries"), "receipt-bound queries missing"
    return importlib.import_module("src.sec_research.queries").StoredQueries(store)


@pytest.fixture
def store(tmp_path):
    result = Store(SecResearchPaths(tmp_path / "market.db"))
    result.install()
    return result


def publish(store, rows, *, history=None, files=(), observed=True):
    columns = {"accessionNumber": [], "filingDate": [], "form": [], "primaryDocument": []}
    for number, filed, form in rows:
        columns["accessionNumber"].append(f"0000320193-26-{number:06d}")
        columns["filingDate"].append(filed)
        columns["form"].append(form)
        columns["primaryDocument"].append("report.htm")
    body = columns if history else {"cik": 320193, "filings": {"recent": columns}}
    if not history and observed:
        body["filings"]["files"] = [{"name": name} for name in files]
    raw = json.dumps(body).encode()
    snapshot = parse_submissions(raw, cik=CIK, historical_name=history)
    with store.connect() as conn:
        if not conn.execute("SELECT 1 FROM sec_research_objects WHERE sha256=?", (snapshot.sha256,)).fetchone():
            conn.execute("INSERT INTO sec_research_objects VALUES (?, ?, ?)",
                         (snapshot.sha256, "objects/" + snapshot.sha256, len(raw)))
    return store.publish(snapshot, object_sha256=snapshot.sha256, observed_at=WHEN,
                         source_url="https://data.sec.gov/submissions/" + (history or f"CIK{CIK}.json"))


def receipt(store, bindings, *, pending=(), gaps=(), observed_at=WHEN):
    return store.record_receipt(
        CIK, status="partial" if pending or gaps else "ok", completed=list(bindings),
        pending=list(pending), gaps=list(gaps), observed_at=observed_at,
        source_snapshots={key: {"snapshot_id": sid, "observed_at": observed_at}
                          for key, sid in bindings.items()},
    )


def seed(store):
    sid = publish(store, [(1, "2026-06-01", "8-K"), (2, "2026-05-01", "10-K/A"),
                          (3, "2026-04-01", "10-K"), (4, "2026-03-01", "10-K"),
                          (5, "2026-03-01", "10-K"), (6, "2026-02-01", "10-Q")])
    return receipt(store, {"submissions": sid})


def numbers(page):
    return [int(row["accession"][-6:]) for row in page["data"]]


def test_catalog_filters_before_limit_and_normalizes_forms(store):
    query = queries(store)
    saved = seed(store)
    first = query.filings(" CIK:320193 ", forms=["10-k", "10-K"], limit=1)
    assert set(first) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
    assert numbers(first) == [2]
    assert first["status"] == "ok"
    assert first["coverage"]["receipt_id"] == saved["receipt_id"]
    assert first["observed_at"] == WHEN
    second = query.filings(CIK, forms=["10-K"], limit=1, cursor=first["next_cursor"])
    assert numbers(second) == [3]
    assert numbers(query.filings(CIK, forms=["10-K"], include_amendments=False, limit=1)) == [3]
    assert numbers(query.filings(CIK, forms=["10-K/A"], include_amendments=True)) == [2]
    assert numbers(query.filings(CIK, include_amendments=False)) == [1, 3, 4, 5, 6]
    assert numbers(query.filings(CIK, forms=["10-K"], filed_from="2026-03-01",
                                 filed_to="2026-04-01")) == [3, 4, 5]


@pytest.mark.parametrize("recent_count", [25, 127], ids=["28-options", "130-options"])
def test_filing_forms_use_every_receipt_bound_catalog_source_without_page_cap(store, recent_count):
    query = queries(store)
    recent_forms = [f"CURRENT {index:03d}" for index in range(recent_count)]
    recent = publish(store, [
        (index + 1, "2026-06-01", form) for index, form in enumerate(recent_forms)
    ] + [(recent_count + 1, "2026-05-01", "DEF 14A"),
         (recent_count + 2, "2026-04-01", "DEF 14A")],
        files=[HISTORY])
    historical = publish(store, [
        (recent_count + 3, "2020-03-01", "S-1/A"),
        (recent_count + 4, "2019-03-01", "10-K"),
        (recent_count + 5, "2018-03-01", "DEF 14A"),
    ], history=HISTORY)
    saved = receipt(store, {"submissions": recent, HISTORY: historical})

    assert len(query.filings(CIK)["data"]) == 20
    result = query.filing_forms(CIK)

    expected = sorted({*recent_forms, "DEF 14A", "S-1/A", "10-K"})
    assert len(expected) == recent_count + 3
    assert result["status"] == "ok"
    assert result["data"] == expected
    assert result["data"].count("DEF 14A") == 1
    assert result["coverage"]["receipt_id"] == saved["receipt_id"]
    assert result["coverage"]["complete"] is True
    assert result["next_cursor"] is None


def test_filing_forms_latest_failed_receipt_never_blesses_retained_catalog(store):
    old = publish(store, [(1, "2026-01-01", "10-K")])
    receipt(store, {"submissions": old})
    failed = receipt(store, {}, pending=["submissions"],
                     gaps=[{"source": "submissions", "code": "sec_transport_unavailable"}])

    result = queries(store).filing_forms(CIK)

    assert result["status"] == "unavailable"
    assert result["data"] == []
    assert result["coverage"]["receipt_id"] == failed["receipt_id"]
    assert result["coverage"]["complete"] is False
    assert result["gaps"]


def test_filing_forms_latest_successful_unbound_receipt_never_blesses_retained_catalog(store):
    old = publish(store, [(1, "2026-01-01", "10-K")])
    receipt(store, {"submissions": old})
    unbound = store.record_receipt(
        CIK, status="ok", completed=["submissions"], pending=[], gaps=[], observed_at=WHEN,
    )

    result = queries(store).filing_forms(CIK)

    assert result["status"] == "unavailable"
    assert result["data"] == []
    assert result["coverage"]["receipt_id"] == unbound["receipt_id"]
    assert result["coverage"]["complete"] is False
    assert {gap["code"] for gap in result["gaps"]} == {"submissions_unavailable"}


def test_filing_forms_distinguish_observed_empty_from_unobserved_history(store):
    query = queries(store)
    assert query.filing_forms(CIK)["status"] == "unavailable"

    complete = publish(store, [])
    receipt(store, {"submissions": complete})
    observed = query.filing_forms(CIK)
    assert observed["status"] == "empty"
    assert observed["data"] == []
    assert observed["gaps"] == []

    unobserved = publish(store, [], observed=False)
    receipt(store, {"submissions": unobserved})
    partial = query.filing_forms(CIK)
    assert partial["status"] == "partial"
    assert partial["data"] == []
    assert {gap["code"] for gap in partial["gaps"]} == {"historical_files_unobserved"}


@pytest.mark.parametrize("bound", ["rows", "bytes", "sources"])
def test_filing_forms_query_budgets_are_explicit_partial(store, monkeypatch, bound):
    module = importlib.import_module("src.sec_research.queries")
    names = [f"CIK{CIK}-submissions-{index:03d}.json" for index in range(3)]
    recent = publish(store, [], files=names)
    bindings = {"submissions": recent}
    for index, name in enumerate(names):
        bindings[name] = publish(store, [(index + 1, "2026-01-01", f"FORM {index}")], history=name)
    receipt(store, bindings)
    if bound == "rows":
        monkeypatch.setattr(module, "MAX_QUERY_ROWS", 2)
    elif bound == "bytes":
        monkeypatch.setattr(module, "MAX_QUERY_BYTES", 4000)
    else:
        monkeypatch.setattr(module, "MAX_QUERY_SOURCES", 2)

    result = queries(store).filing_forms(CIK)

    assert result["status"] == "partial"
    assert len(result["data"]) < 3
    assert {gap["code"] for gap in result["gaps"]} >= {"query_budget_exceeded"}
    assert result["coverage"]["complete"] is False


def test_filing_forms_envelope_bound_fails_closed_without_truncation(store, monkeypatch):
    module = importlib.import_module("src.sec_research.queries")
    sid = publish(store, [(1, "2026-03-01", "FORM ONE"),
                          (2, "2026-02-01", "FORM TWO"),
                          (3, "2026-01-01", "FORM THREE")])
    receipt(store, {"submissions": sid})
    monkeypatch.setattr(module, "MAX_ENVELOPE_BYTES", 100)
    oversized = queries(store).filing_forms(CIK)
    assert oversized["status"] == "unavailable"
    assert oversized["data"] == []
    assert oversized["gaps"] == [{"code": "sec_result_too_large"}]


def test_cursor_continuation_reopens_pinned_receipt_after_refresh_restart_and_relocation(store, tmp_path):
    query = queries(store)
    seed(store)
    first = query.filings(CIK, forms=["10-K"], limit=1)
    newer = publish(store, [(9, "2026-09-01", "10-K"), (10, "2026-08-01", "10-K")])
    receipt(store, {"submissions": newer})
    destination = tmp_path / "moved.db"
    shutil.copyfile(store.paths.market_db_path, destination)
    reopened = queries(Store(SecResearchPaths(destination)))
    second = reopened.filings(CIK, forms=["10-K"], limit=1, cursor=first["next_cursor"])
    assert first["coverage"]["receipt_id"] == second["coverage"]["receipt_id"]
    assert numbers(second) == [3]
    assert numbers(reopened.filings(CIK, forms=["10-K"], limit=1)) == [9]
    seen = [2, 3]
    while second["next_cursor"]:
        second = reopened.filings(CIK, forms=["10-K"], limit=1, cursor=second["next_cursor"])
        seen.extend(numbers(second))
    assert seen == [2, 3, 4, 5]


@pytest.mark.parametrize("changed", [{"forms": ["10-Q"]}, {"limit": 2},
    {"filed_from": "2026-01-01"}, {"filed_to": "2026-12-31"}, {"include_amendments": False}])
def test_cursor_rejects_changed_filters(store, changed):
    query = queries(store)
    seed(store)
    params = {"forms": ["10-K"], "limit": 1}
    token = query.filings(CIK, **params)["next_cursor"]
    with pytest.raises(ValueError, match="^sec_research_cursor_mismatch$"):
        query.filings(CIK, cursor=token, **(params | changed))


def unpack(token):
    return json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))


def pack(value):
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")


@pytest.mark.parametrize("change", [{"v": 2}, {"receipt_id": True}, {"offset": -1},
    {"offset": 1.0}, {"offset": 0}, {"extra": "x"}, {"kind": "facts"},
    {"bindings_digest": "0" * 64}, {"receipt_id": 999999}, {"cik": "0000000001"}])
def test_cursor_strict_shape_and_receipt_binding(store, change):
    query = queries(store)
    seed(store)
    token = query.filings(CIK, limit=1)["next_cursor"]
    with pytest.raises(ValueError, match="^sec_research_cursor_(invalid|mismatch)$"):
        query.filings(CIK, limit=1, cursor=pack(unpack(token) | change))


@pytest.mark.parametrize("token", ["", "!", "a" * 4097, "e30", "e30=", 1,
    base64.urlsafe_b64encode(b'{"v":1,"v":1}').decode().rstrip("="), "\ud800"])
def test_cursor_malformed_is_closed_error(store, token):
    query = queries(store)
    with pytest.raises(ValueError, match="^sec_research_cursor_invalid$"):
        query.filings(CIK, cursor=token)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"limit": True},
    {"limit": 1.0}, {"forms": "10-K"}, {"forms": [None]}, {"forms": [""]},
    {"filed_from": "2026-02-30"}, {"filed_to": "20260101"},
    {"filed_from": "2026-02-01", "filed_to": "2026-01-01"}, {"include_amendments": 1}])
def test_invalid_filters_are_closed_errors_without_storage_reads(store, params, monkeypatch):
    query = queries(store)
    monkeypatch.setattr(store, "connect", lambda *a, **k: pytest.fail("invalid input read storage"))
    with pytest.raises(ValueError, match="^sec_research_query_invalid$"):
        query.filings(CIK, **params)


def test_missing_and_unbound_receipts_never_borrow_old_snapshots(store):
    query = queries(store)
    assert query.filings(CIK)["status"] == "unavailable"
    sid = publish(store, [(1, "2026-01-01", "10-K")])
    assert query.filings(CIK)["data"] == []
    receipt(store, {"submissions": sid})
    store.record_receipt(CIK, status="ok", completed=["submissions"], pending=[], gaps=[], observed_at=WHEN)
    page = query.filings(CIK)
    assert page["status"] == "unavailable"
    assert page["data"] == []
    assert page["gaps"]


@pytest.mark.parametrize("mode,expected", [("covered", "empty"), ("unobserved", "partial"),
    ("pending", "partial"), ("facts_pending", "empty")])
def test_empty_requires_observed_catalog_coverage(store, mode, expected):
    query = queries(store)
    sid = publish(store, [], observed=mode != "unobserved", files=[HISTORY] if mode == "pending" else [])
    pending = [HISTORY] if mode == "pending" else ["companyfacts"] if mode == "facts_pending" else []
    receipt(store, {"submissions": sid}, pending=pending)
    page = query.filings(CIK, forms=["10-K"])
    assert page["status"] == expected
    assert page["data"] == []
    assert page["next_cursor"] is None
    assert bool(page["gaps"]) is (expected == "partial")


def test_history_pointer_requires_binding_even_when_receipt_claims_ok(store):
    query = queries(store)
    sid = publish(store, [], files=[HISTORY])
    receipt(store, {"submissions": sid})
    assert query.filings(CIK)["status"] == "partial"


def test_identical_duplicate_metadata_merges_provenance_but_conflicts_stay_visible(store):
    query = queries(store)
    recent = publish(store, [(1, "2026-01-01", "10-K"), (2, "2026-02-01", "10-K")], files=[HISTORY])
    historical = publish(store, [(1, "2026-01-01", "10-K"), (2, "2026-02-01", "10-Q")], history=HISTORY)
    receipt(store, {HISTORY: historical, "submissions": recent})
    page = query.filings(CIK)
    assert numbers(page) == [2, 2, 1]
    assert page["status"] == "partial"
    assert {row["form"] for row in page["data"][:2]} == {"10-K", "10-Q"}
    merged = page["data"][2]
    assert {source["snapshot_id"] for source in merged["sources"]} == {recent, historical}
    assert all(source["source"]["sha256"] and source["source"]["pointer"] for source in merged["sources"])
    assert any(gap["code"] == "filing_metadata_conflict" for gap in page["gaps"])
    receipt(store, {"submissions": recent, HISTORY: historical})
    assert query.filings(CIK)["data"] == page["data"]


def test_byte_ceiling_returns_whole_records_and_advances_past_oversized_record(store):
    query = queries(store)
    sid = publish(store, [(1, "2026-04-01", "X" * (256 * 1024)),
                          (2, "2026-03-01", "Y" * (140 * 1024)),
                          (3, "2026-02-01", "Y" * (140 * 1024)), (4, "2026-01-01", "10-K")])
    receipt(store, {"submissions": sid})
    page = query.filings(CIK, limit=100)
    seen, tokens = [], set()
    assert page["status"] == "partial"
    assert any(gap["code"] == "observation_too_large" for gap in page["gaps"])
    while True:
        assert len(json.dumps(page, ensure_ascii=False).encode()) <= 256 * 1024
        seen.extend(numbers(page))
        for row in page["data"]:
            if row["accession"].endswith(("000002", "000003")):
                assert row["form"] == "Y" * (140 * 1024)
        token = page["next_cursor"]
        if token is None:
            break
        assert token not in tokens
        tokens.add(token)
        page = query.filings(CIK, limit=100, cursor=token)
    assert seen == [2, 3, 4]


def test_query_is_readonly_without_install_capture_access_or_unpaged_latest_reads(store, monkeypatch):
    query = queries(store)
    seed(store)
    before = store.paths.market_db_path.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail("query used mutation or unbound observations")
    for name in ("install", "publish", "record_receipt", "catalog", "facts", "snapshots"):
        monkeypatch.setattr(store, name, forbidden)
    assert numbers(query.filings(CIK, limit=1)) == [1]
    assert query.filing_forms(CIK)["data"] == ["10-K", "10-K/A", "10-Q", "8-K"]
    assert store.paths.market_db_path.read_bytes() == before
    assert not store.paths.capture_root.exists()


def test_absent_or_mismatched_store_returns_closed_unavailable_without_creating_files(tmp_path):
    absent = tmp_path / "absent" / "market.db"
    query = queries(Store(SecResearchPaths(absent)))
    result = query.filings(CIK)
    assert result["status"] == "unavailable"
    assert result["data"] == []
    assert not absent.parent.exists()
    store = Store(SecResearchPaths(tmp_path / "noncanonical.db"))
    with store.connect() as conn:
        conn.execute("CREATE TABLE private_fixture(secret TEXT)")
    before = store.paths.market_db_path.read_bytes()
    result = queries(store).filings(CIK)
    assert result["status"] == "unavailable"
    assert str(tmp_path) not in json.dumps(result)
    assert store.paths.market_db_path.read_bytes() == before


def test_catalog_receipt_gap_cannot_become_observed_empty(store):
    query = queries(store)
    sid = publish(store, [])
    receipt(store, {"submissions": sid}, gaps=[{"source": "submissions", "code": "source_invalid"}])
    page = query.filings(CIK)
    assert page["status"] == "partial"
    assert page["gaps"]
    forms = query.filing_forms(CIK)
    assert forms["status"] == "partial"
    assert forms["gaps"]


def test_corrupt_receipt_json_is_closed_storage_unavailability(store):
    query = queries(store)
    with store.connect() as conn:
        conn.execute("""INSERT INTO sec_research_receipts
            (cik, status, completed, pending, gaps, observed_at, recorded_at, source_snapshots)
            VALUES (?, 'ok', '[]', '[]', '[]', ?, ?, 'PRIVATE invalid JSON')""", (CIK, WHEN, WHEN))
    page = query.filings(CIK)
    assert page["status"] == "unavailable"
    assert "PRIVATE" not in json.dumps(page)


def test_record_that_fits_actual_envelope_is_not_discarded_for_cursor_reserve(store):
    query = queries(store)
    form = "X" * (256 * 1024 - 2000)
    sid = publish(store, [(1, "2026-01-01", form)])
    receipt(store, {"submissions": sid})
    page = query.filings(CIK, limit=1)
    assert numbers(page) == [1]
    assert page["data"][0]["form"] == form
    assert page["status"] == "ok"
    assert len(json.dumps(page).encode()) <= 256 * 1024


@pytest.mark.parametrize("bound", ["rows", "bytes", "sources"])
def test_aggregate_bound_across_historical_snapshots_is_explicit_partial(store, monkeypatch, bound):
    query = queries(store)
    module = importlib.import_module("src.sec_research.queries")
    names = [f"CIK{CIK}-submissions-{index:03d}.json" for index in range(3)]
    recent = publish(store, [], files=names)
    bindings = {"submissions": recent}
    for index, name in enumerate(names):
        bindings[name] = publish(store, [(index + 1, "2026-01-01", "10-K")], history=name)
    receipt(store, bindings)
    if bound == "rows":
        monkeypatch.setattr(module, "MAX_QUERY_ROWS", 2, raising=False)
    elif bound == "bytes":
        monkeypatch.setattr(module, "MAX_QUERY_BYTES", 4000, raising=False)
    else:
        monkeypatch.setattr(module, "MAX_QUERY_SOURCES", 2, raising=False)
    page = query.filings(CIK)
    assert page["status"] == "partial"
    assert len(page["data"]) < 3
    assert {gap["code"] for gap in page["gaps"]} >= {"query_budget_exceeded"}
    assert page["coverage"]["complete"] is False


def test_aggregate_bound_filters_stream_before_admission_and_stops_reading(store, monkeypatch):
    query = queries(store)
    module = importlib.import_module("src.sec_research.queries")
    rows = [(number, "2026-02-01", "8-K") for number in range(1, 101)]
    rows.extend([(101, "2026-01-01", "10-K"), (102, "2026-01-01", "10-K")])
    sid = publish(store, rows)
    receipt(store, {"submissions": sid})
    monkeypatch.setattr(module, "MAX_QUERY_ROWS", 1, raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail("query materialized a whole snapshot before its aggregate budget")
    monkeypatch.setattr(store, "snapshot_observations", forbidden)
    monkeypatch.setattr(store, "_observations", forbidden)
    page = query.filings(CIK, forms=["10-K"])
    assert numbers(page) == [101]
    assert page["status"] == "partial"
    assert any(gap["code"] == "query_budget_exceeded" for gap in page["gaps"])


def test_budget_exhaustion_with_no_matching_rows_is_not_observed_empty(store, monkeypatch):
    query = queries(store)
    module = importlib.import_module("src.sec_research.queries")
    recent = publish(store, [], files=[HISTORY])
    historical = publish(store, [(1, "2026-01-01", "10-K")], history=HISTORY)
    receipt(store, {"submissions": recent, HISTORY: historical})
    monkeypatch.setattr(module, "MAX_QUERY_SOURCES", 1, raising=False)
    page = query.filings(CIK, forms=["10-Q"])
    assert page["data"] == []
    assert page["status"] == "partial"
    assert page["next_cursor"] is None


@pytest.mark.parametrize("bindings", ["{}", "PRIVATE invalid JSON", "null", "1", "[]", "true"])
def test_invalid_stored_binding_shape_has_closed_envelope(store, bindings):
    query = queries(store)
    seed(store)
    with store.connect() as conn:
        conn.execute("""INSERT INTO sec_research_receipts
            (cik, status, completed, pending, gaps, observed_at, recorded_at, source_snapshots)
            VALUES (?, 'ok', '[]', '[]', '[]', ?, ?, ?)""", (CIK, WHEN, WHEN, bindings))
    result = query.filings(CIK)
    assert result["status"] == "unavailable"
    assert result["data"] == []
    assert "PRIVATE" not in json.dumps(result)
    assert set(result) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}


@pytest.mark.parametrize("field", ["completed", "pending", "gaps"])
@pytest.mark.parametrize("value", ["null", "1", "{}", "[null]"])
def test_invalid_stored_receipt_fields_have_closed_envelope(store, field, value):
    query = queries(store)
    fields = dict(completed="[]", pending="[]", gaps="[]")
    fields[field] = value
    with store.connect() as conn:
        conn.execute("""INSERT INTO sec_research_receipts
            (cik, status, completed, pending, gaps, observed_at, recorded_at, source_snapshots)
            VALUES (?, 'ok', ?, ?, ?, ?, ?, '{}')""", (CIK, *fields.values(), WHEN, WHEN))
    result = query.filings(CIK)
    assert result["status"] == "unavailable"
    assert result["data"] == []
