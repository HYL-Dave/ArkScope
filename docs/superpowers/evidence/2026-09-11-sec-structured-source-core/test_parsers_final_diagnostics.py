"""Independent synthetic parser review; no provider or storage operations."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
import hashlib
import json

import pytest

from src.sec_research.catalog import parse_submissions
from src.sec_research.common import SourceError, decode_object
from src.sec_research.facts import parse_companyfacts


CIK = "0000320193"
ACC = "0000950170-26-000001"
HISTORY = "CIK0000320193-submissions-001.json"


def raw(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()


def columns(**changes):
    return {"accessionNumber": [ACC], "filingDate": ["2026-05-01"],
            "form": ["10-Q"], **changes}


def catalog_doc(rows=None, **changes):
    return {"cik": 320193, "filings": {"recent": columns() if rows is None else rows, **changes}}


def observation(**changes):
    return {"val": 7, "end": "2026-03-31", "filed": "2026-05-01",
            "accn": ACC, "form": "10-Q", **changes}


def facts_doc(rows=None, namespace="us-gaap", concept="Revenue", unit="USD"):
    return {"cik": 320193, "facts": {namespace: {concept: {"units": {
        unit: [observation()] if rows is None else rows}}}}}


@pytest.mark.parametrize("body,code,pointer", [
    (b'{"items":[{"a/b~":1,"a/b~":2}]}', "duplicate_key", "/items/0/a~1b~0"),
    (b'{"unused":{"x":1,"x":2}}', "duplicate_key", "/unused/x"),
    (b'{"a":1,"\\u0061":2}', "duplicate_key", "/a"),
    (b'{"\\ud800":1}', "invalid_pointer", ""),
    (b'{"x":1e99999999999999999999999999}', "invalid_number", ""),
    (b'{"x":' + b'9' * 5000 + b'}', "invalid_number", ""),
    (b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}', "invalid_json", ""),
])
def test_closed_decoder_boundaries(body, code, pointer):
    with pytest.raises(SourceError) as caught:
        decode_object(body)
    assert caught.value.args == (code, pointer)


@pytest.mark.parametrize("slot", ["namespace", "concept", "unit", "form", "fp", "frame"])
@pytest.mark.parametrize("text", ["\ud800", "\udfff", "bad\x00text", "bad\u200btext"])
def test_invalid_fact_text_is_typed_at_every_location(slot, text):
    doc = facts_doc(**{slot: text}) if slot in {"namespace", "concept", "unit"} else facts_doc([observation(**{slot: text})])
    with pytest.raises(SourceError) as caught:
        parse_companyfacts(raw(doc), cik=CIK)
    assert caught.value.code in {"invalid_pointer", "invalid_text"}
    assert all(not 0xD800 <= ord(char) <= 0xDFFF for char in caught.value.pointer)


def test_unicode_source_pointer_resolves_and_binds_exact_bytes():
    doc = facts_doc(namespace="\U0001f600~/", concept="\u6536\u5165/~", unit="JPY/shares~")
    body = raw(doc)
    first = parse_companyfacts(body, cik=CIK).facts[0]
    decoded = decode_object(body)
    for part in first.source.pointer.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        decoded = decoded[int(key)] if isinstance(decoded, list) else decoded[key]
    assert decoded == observation()
    assert first.source.sha256 == hashlib.sha256(body).hexdigest()
    assert first == parse_companyfacts(body, cik="cIk:320193").facts[0]
    assert first.fact_id != parse_companyfacts(body + b" ", cik=CIK).facts[0].fact_id
    with pytest.raises(FrozenInstanceError):
        first.source.pointer = ""


@pytest.mark.parametrize("token,expected", [
    (b"9007199254740993", "9007199254740993"),
    (b"0.123456789012345678900", "0.123456789012345678900"),
    (b"-0.0000", "-0.0000"), (b"1e-1000000", "1E-1000000"),
])
def test_exact_values_under_restrictive_decimal_context(token, expected):
    body = raw(facts_doc()).replace(b'"val":7', b'"val":' + token)
    with localcontext() as context:
        context.prec, context.Emax, context.Emin = 2, 9, -9
        fact = parse_companyfacts(body, cik=CIK).facts[0]
    assert fact.value == expected
    assert Decimal(fact.value) == Decimal(token.decode())


@pytest.mark.parametrize("value", [True, False, "7", None])
def test_invalid_numeric_last_row_cannot_be_partial_success(value):
    with pytest.raises(SourceError) as caught:
        parse_companyfacts(raw(facts_doc([observation(), observation(val=value)])), cik=CIK)
    assert caught.value.args == ("sec_fact_value_invalid", "/facts/us-gaap/Revenue/units/USD/1/val")


@pytest.mark.parametrize("value", [True, False, 0.0, 1.0, -1, "0"])
def test_historical_count_requires_exact_nonnegative_int(value):
    with pytest.raises(SourceError) as caught:
        parse_submissions(raw(catalog_doc(files=[{"name": HISTORY}, {"name": HISTORY, "filingCount": value}])), cik=CIK)
    assert caught.value.args == ("invalid_count", "/filings/files/1/filingCount")


def test_optional_history_is_not_a_completeness_claim():
    missing = parse_submissions(raw(catalog_doc()), cik=CIK)
    empty = parse_submissions(raw(catalog_doc(files=[])), cik=CIK)
    declared = parse_submissions(raw(catalog_doc(files=[{"name": HISTORY, "filingCount": 0}])), cik=CIK)
    historical = parse_submissions(raw(columns()), cik=CIK, historical_name=HISTORY)
    assert (missing.historical_files_observed, empty.historical_files_observed,
            declared.historical_files_observed, historical.historical_files_observed) == (False, True, True, False)
    assert declared.historical_files[0].filing_count == 0
    assert declared.historical_files[0].filed_from is None
    assert missing.filings[0].filing_id == historical.filings[0].filing_id
    for snapshot in (missing, empty, declared, historical):
        assert not hasattr(snapshot, "complete") and not hasattr(snapshot, "coverage_complete")


@pytest.mark.parametrize("value", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00",
                                  "2026-05-01T12:00:00.1234567Z", "2026-02-29T12:00:00Z"])
def test_invalid_or_lossy_timestamp_rejects_entire_catalog(value):
    with pytest.raises(SourceError) as caught:
        parse_submissions(raw(catalog_doc(columns(acceptanceDateTime=[value]))), cik=CIK)
    assert caught.value.args == ("invalid_timestamp", "/filings/recent/acceptanceDateTime/0")


def test_valid_timestamp_retains_microseconds_and_changes_calendar_day():
    filing = parse_submissions(raw(catalog_doc(columns(acceptanceDateTime=["2026-01-01T00:00:00.123456+02:30"]))), cik=CIK).filings[0]
    assert filing.accepted_at == "2025-12-31T21:30:00.123456Z"
    assert filing.filed_date == "2026-05-01" and filing.report_date is None


def test_conflicts_in_unprojected_columns_reject_whole_catalog():
    rows = {key: values * 2 for key, values in columns().items()}
    rows["extra/~"] = [{"nested": [1]}, {"nested": [2]}]
    with pytest.raises(SourceError) as caught:
        parse_submissions(raw(catalog_doc(rows)), cik=CIK)
    assert caught.value.args == ("conflicting_accession", "/filings/recent/accessionNumber/1")


def test_contradictory_facts_and_empty_unit_arrays_are_not_rewritten():
    doc = facts_doc([observation(), observation(val=8), observation()])
    doc["facts"]["us-gaap"]["Revenue"]["units"]["JPY"] = []
    facts = parse_companyfacts(raw(doc), cik=CIK).facts
    assert [fact.value for fact in facts] == ["7", "8", "7"]
    assert len({fact.fact_id for fact in facts}) == 3
    assert all(fact.unit == "USD" and fact.accession == ACC and fact.cik == CIK for fact in facts)
