"""All-or-nothing columnar submissions parsing, without acquisition."""

from dataclasses import FrozenInstanceError
import hashlib
import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CIK = "0000320193"
HISTORY = "CIK0000320193-submissions-001.json"


def test_catalog_has_a_runtime_owner():
    assert (ROOT / "src/sec_research/catalog.py").is_file(), "SEC catalog parser missing"


@pytest.fixture
def catalog():
    assert (ROOT / "src/sec_research/catalog.py").is_file(), "SEC catalog parser missing"
    return importlib.import_module("src.sec_research.catalog")


def arrays(**changes):
    result = {"accessionNumber": ["0000950170-26-000001"], "filingDate": ["2026-05-01"], "form": ["10-Q"],
              "reportDate": ["2026-03-31"], "acceptanceDateTime": ["2026-04-30T20:30:15-04:00"],
              "primaryDocument": ["issuer-20260331.htm"], "size": [1200]}
    result.update(changes)
    return result


def document(rows=None, files=None):
    return {"cik": "320193", "filings": {"recent": arrays() if rows is None else rows, "files": [] if files is None else files}}


def body(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def resolve(value, pointer):
    for part in pointer.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def test_catalog_preserves_report_filed_accepted_dates_separately(catalog):
    snapshot = catalog.parse_submissions(body(document()), cik="cik:320193")
    filing, = snapshot.filings
    assert snapshot.cik == CIK
    assert (filing.filed_date, filing.report_date, filing.accepted_at) == ("2026-05-01", "2026-03-31", "2026-05-01T00:30:15Z")
    assert filing.cik == CIK
    assert snapshot.historical_name is None
    with pytest.raises(FrozenInstanceError):
        filing.report_date = filing.filed_date
    with pytest.raises(FrozenInstanceError):
        snapshot.cik = "1"


def test_historical_arrays_share_recent_validation(catalog):
    raw = body(arrays())
    snapshot = catalog.parse_submissions(raw, cik=CIK, historical_name=HISTORY)
    assert snapshot.historical_name == HISTORY
    assert snapshot.historical_files == ()
    assert snapshot.filings[0].report_date == "2026-03-31"
    assert snapshot.filings[0].source.pointer == "/accessionNumber/0"
    assert resolve(json.loads(raw), snapshot.filings[0].source.pointer) == "0000950170-26-000001"
    with pytest.raises(catalog.SourceError) as caught:
        catalog.parse_submissions(body(arrays(filingDate=["2026-02-30"])), cik=CIK, historical_name=HISTORY)
    assert caught.value.pointer == "/filingDate/0"


@pytest.mark.parametrize("kind,observed", [("missing", False), ("empty", True), ("declared", True), ("historical", False)])
def test_missing_historical_files_is_distinct_from_observed_empty(catalog, kind, observed):
    doc = document()
    historical_name = None
    if kind == "missing":
        del doc["filings"]["files"]
    elif kind == "declared":
        doc["filings"]["files"] = [{"name": HISTORY}]
    elif kind == "historical":
        doc = arrays()
        historical_name = HISTORY
    snapshot = catalog.parse_submissions(body(doc), cik=CIK, historical_name=historical_name)
    assert getattr(snapshot, "historical_files_observed", None) is observed
    assert tuple(item.name for item in snapshot.historical_files) == ((HISTORY,) if kind == "declared" else ())


@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize("column,value", [("form", []), ("reportDate", ["2026-03-31", ""]), ("extra", []), ("extra", "not-an-array"), ("filingDate", None)])
def test_misaligned_arrays_never_yield_a_partial_success(catalog, historical, column, value):
    rows = arrays(**{column: value})
    raw = body(rows if historical else document(rows))
    with pytest.raises(catalog.SourceError) as caught:
        catalog.parse_submissions(raw, cik=CIK, historical_name=HISTORY if historical else None)
    assert caught.value.pointer == ("" if historical else "/filings/recent") + "/" + column


def test_amendments_remain_distinct_accessions(catalog):
    rows = {"accessionNumber": ["0000950170-26-000001", "0000950170-26-000002"], "filingDate": ["2026-05-01", "2026-05-02"], "form": ["10-Q", "10-Q/A"]}
    first, second = catalog.parse_submissions(body(document(rows)), cik=CIK).filings
    assert (first.form, second.form) == ("10-Q", "10-Q/A")
    assert first.filing_id != second.filing_id


@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize("name", ["issuer-20260331.htm", "real_document.xml", "exhibit.htm",
                                "xslF345X06/form4.xml", "a/b.htm", "a/b/c.htm"])
def test_primary_url_uses_actual_document_name(catalog, name, historical):
    rows = arrays(primaryDocument=[name])
    raw = body(rows if historical else document(rows))
    filing, = catalog.parse_submissions(raw, cik=CIK, historical_name=HISTORY if historical else None).filings
    assert filing.primary_document == name
    assert filing.primary_url == "https://www.sec.gov/Archives/edgar/data/320193/000095017026000001/" + name


@pytest.mark.parametrize("name", ["../a.htm", "/a.htm", "a/../b.htm", "a/./b.htm",
                                "a//b.htm", "a/", "//other.example/a.htm", "a/%2e%2e/b.htm",
                                "a/b.htm?x=1", "a/b.htm#x", "a\\b.htm", "%2e%2e.htm",
                                "a%252f.htm", "a.htm?x=1", "a.htm#x", "a\n.htm", "a b.htm",
                                "https:a.htm", ".", "..", 1])
def test_primary_document_rejects_unsafe_url_components(catalog, name):
    with pytest.raises(catalog.SourceError) as caught:
        catalog.parse_submissions(body(document(arrays(primaryDocument=[name]))), cik=CIK)
    assert caught.value.pointer == "/filings/recent/primaryDocument/0"


@pytest.mark.parametrize("name", ["../" + HISTORY, "/" + HISTORY, "CIK0000000001-submissions-001.json", "CIK0000320193-submissions-1.json?x", "CIK0000320193-submissions-%31.json", "CIK0000320193-submissions-x.json", HISTORY + "\n"])
def test_historical_pointer_cannot_leave_submissions_directory(catalog, name):
    with pytest.raises(catalog.SourceError):
        catalog.parse_submissions(body(document(files=[{"name": name}])), cik=CIK)
    with pytest.raises(catalog.SourceError):
        catalog.parse_submissions(body(arrays()), cik=CIK, historical_name=name)


def test_historical_metadata_and_all_sources_bind_original_bytes(catalog):
    doc = document(files=[{"name": HISTORY, "filingCount": 12, "filingFrom": "2020-01-01", "filingTo": "2025-12-31"}])
    raw = b" \n" + body(doc) + b"\n"
    snapshot = catalog.parse_submissions(raw, cik=CIK)
    assert snapshot.sha256 == hashlib.sha256(raw).hexdigest()
    filing, = snapshot.filings
    historical, = snapshot.historical_files
    assert filing.source.pointer == "/filings/recent/accessionNumber/0"
    assert resolve(doc, filing.source.pointer) == filing.accession
    assert (historical.name, historical.filing_count, historical.filed_from, historical.filed_to) == (HISTORY, 12, "2020-01-01", "2025-12-31")
    assert resolve(doc, historical.source.pointer) == doc["filings"]["files"][0]
    assert filing.source.sha256 == historical.source.sha256 == snapshot.sha256
    with pytest.raises(FrozenInstanceError):
        historical.name = "changed"


def test_snapshot_hashes_original_body_only_once(catalog, monkeypatch):
    real_sha256 = hashlib.sha256
    calls = []

    def counted(raw=b"", *args, **kwargs):
        calls.append(raw)
        return real_sha256(raw, *args, **kwargs)

    monkeypatch.setattr(hashlib, "sha256", counted)
    rows = {name: values * 4 for name, values in arrays().items()}
    raw = body(document(rows, [{"name": HISTORY}]))
    snapshot = catalog.parse_submissions(raw, cik=CIK)
    assert len(snapshot.filings) == 4
    assert calls.count(raw) == 1


def test_missing_optional_metadata_remains_missing(catalog):
    for rows in ({name: arrays()[name] for name in ("accessionNumber", "filingDate", "form")}, arrays(reportDate=[""], acceptanceDateTime=[None], primaryDocument=[""])):
        snapshot = catalog.parse_submissions(body(document(rows, [{"name": HISTORY}])), cik=CIK)
        filing, = snapshot.filings
        assert (filing.report_date, filing.accepted_at, filing.primary_document, filing.primary_url) == (None, None, None, None)
        historical, = snapshot.historical_files
        assert (historical.filing_count, historical.filed_from, historical.filed_to) == (None, None, None)


def test_truthful_zero_rows_require_explicit_arrays(catalog):
    rows = {"accessionNumber": [], "filingDate": [], "form": []}
    assert catalog.parse_submissions(body(document(rows)), cik=CIK).filings == ()
    assert catalog.parse_submissions(body(rows), cik=CIK, historical_name=HISTORY).filings == ()
    for doc in ({}, {"cik": CIK}, {"cik": CIK, "filings": {}}, document({}), document({"accessionNumber": []}), document(files=None) | {"cik": None}):
        with pytest.raises(catalog.SourceError):
            catalog.parse_submissions(body(doc), cik=CIK)


@pytest.mark.parametrize("field,value", [("filingDate", "2026-02-29"), ("reportDate", "20260101"), ("acceptanceDateTime", "2026-05-01T12:00:00"), ("acceptanceDateTime", "2026-05-01T12:00:00+24:00"), ("acceptanceDateTime", 1), ("form", True), ("form", "bad\nform"), ("accessionNumber", "bad")])
def test_malformed_rows_reject_whole_snapshot(catalog, field, value):
    rows = {name: values * 2 for name, values in arrays().items()}
    rows[field][1] = value
    with pytest.raises(catalog.SourceError) as caught:
        catalog.parse_submissions(body(document(rows)), cik=CIK)
    assert caught.value.pointer == "/filings/recent/" + field + "/1"


def test_conflicting_duplicate_accessions_are_rejected(catalog):
    rows = {name: values * 2 for name, values in arrays().items()}
    rows["form"][1] = "10-Q/A"
    with pytest.raises(catalog.SourceError) as caught:
        catalog.parse_submissions(body(document(rows)), cik=CIK)
    assert (caught.value.code, caught.value.pointer) == ("conflicting_accession", "/filings/recent/accessionNumber/1")


def test_cross_cik_payload_rejected_for_recent_and_historical(catalog):
    for doc, name in [(document() | {"cik": 1}, None), (arrays() | {"cik": 1}, HISTORY)]:
        with pytest.raises(catalog.SourceError) as caught:
            catalog.parse_submissions(body(doc), cik=CIK, historical_name=name)
        assert caught.value.pointer == "/cik"


@pytest.mark.parametrize("change", [{"filingCount": True}, {"filingCount": -1}, {"filingCount": 1.5}, {"filingFrom": "2026-02-30"}, {"filingFrom": "2026-05-01", "filingTo": "2026-01-01"}])
def test_invalid_historical_metadata_is_not_silently_dropped(catalog, change):
    with pytest.raises(catalog.SourceError):
        catalog.parse_submissions(body(document(files=[{"name": HISTORY, **change}])), cik=CIK)


@pytest.mark.parametrize("files", [None, {}, [None], ["name"], [{}]])
def test_present_historical_files_must_be_valid(catalog, files):
    doc = document()
    doc["filings"]["files"] = files
    with pytest.raises(catalog.SourceError):
        catalog.parse_submissions(body(doc), cik=CIK)
