"""Exact SEC observations, not the old value-only financial mapper."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
import hashlib
import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CIK = "0000320193"
ACCESSION = "0000950170-26-000001"


def test_fact_parser_has_a_runtime_owner():
    assert (ROOT / "src/sec_research/facts.py").is_file(), "SEC fact parser missing"


@pytest.fixture
def parser():
    assert (ROOT / "src/sec_research/facts.py").is_file(), "SEC fact parser missing"
    return importlib.import_module("src.sec_research.facts").parse_companyfacts


def observation(**changes):
    row = {
        "val": 123,
        "start": "2025-10-01",
        "end": "2026-03-31",
        "fy": 2026,
        "fp": "Q2",
        "form": "10-Q",
        "accn": ACCESSION,
        "filed": "2026-05-01",
    }
    row.update(changes)
    return row


def document(rows=None, *, unit="USD", concept="Revenue", namespace="us-gaap", cik=320193):
    return {
        "cik": cik,
        "entityName": "Fixture Issuer",
        "facts": {
            namespace: {concept: {"label": "Fixture metric", "units": {
                unit: [observation()] if rows is None else rows,
            }}},
        },
    }


def body(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decode_pointer(document, pointer):
    value = document
    for part in pointer.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def test_fractional_value_never_passes_through_binary_float(parser):
    raw = body(document()).replace(b'"val":123', b'"val":1234567890.123456789012345678900')
    result = parser(raw, cik=CIK)
    assert len(result.facts) == 1
    assert result.facts[0].value == "1234567890.123456789012345678900"
    assert type(result.facts[0].value) is str


@pytest.mark.parametrize("value,unit", [(2**80 + 1, "JPY"), (0, "shares"), (-999, "EUR")])
def test_large_integer_and_non_usd_units_are_preserved(parser, value, unit):
    result = parser(body(document([observation(val=value)], unit=unit)), cik=CIK)
    assert result.facts[0].value == str(value)
    assert result.facts[0].unit == unit


@pytest.mark.parametrize("literal,expected", [
    (b"1.234567890123456789E+1000", "1.234567890123456789E+1000"),
    (b"-0.000", "-0.000"),
    (b"1E-1000", "1E-1000"),
])
def test_decimal_exponents_are_preserved_without_context_rounding(parser, literal, expected):
    raw = body(document()).replace(b'"val":123', b'"val":' + literal)
    assert parser(raw, cik=CIK).facts[0].value == expected


def test_ytd_and_quarter_observations_keep_distinct_periods(parser):
    rows = [observation(val=400), observation(start="2026-01-01", val=200)]
    facts = parser(body(document(rows)), cik=CIK).facts
    assert [(fact.start, fact.end, fact.fiscal_period, fact.value) for fact in facts] == [
        ("2025-10-01", "2026-03-31", "Q2", "400"),
        ("2026-01-01", "2026-03-31", "Q2", "200"),
    ]
    assert facts[0].fact_id != facts[1].fact_id


def test_instant_value_has_no_invented_start(parser):
    row = observation()
    del row["start"]
    assert parser(body(document([row])), cik=CIK).facts[0].start is None


def test_amended_and_original_values_are_both_retained(parser):
    rows = [observation(), observation(form="10-Q/A", filed="2026-06-01",
                                      accn="0000950170-26-000002", val=124)]
    facts = parser(body(document(rows)), cik=CIK).facts
    assert [(fact.form, fact.accession, fact.filed_date, fact.value) for fact in facts] == [
        ("10-Q", ACCESSION, "2026-05-01", "123"),
        ("10-Q/A", "0000950170-26-000002", "2026-06-01", "124"),
    ]


def test_fact_ids_reopen_the_exact_source_pointer(parser):
    raw = body(document([observation(), observation()], unit="USD/shares"))
    snapshot = parser(raw, cik="cik:320193")
    assert snapshot.cik == CIK
    assert snapshot.sha256 == hashlib.sha256(raw).hexdigest()
    assert len({fact.fact_id for fact in snapshot.facts}) == 2
    decoded = json.loads(raw, parse_float=Decimal)
    for index, fact in enumerate(snapshot.facts):
        assert fact.source.sha256 == snapshot.sha256
        assert fact.source.pointer == f"/facts/us-gaap/Revenue/units/USD~1shares/{index}"
        assert decode_pointer(decoded, fact.source.pointer) == observation()
    assert parser(raw, cik=CIK) == snapshot
    changed_bytes = parser(raw + b"\n", cik=CIK)
    assert snapshot.facts[0].fact_id != changed_bytes.facts[0].fact_id


def test_namespace_and_unit_pointer_escaping_preserves_original_keys(parser):
    raw = body(document(unit="a~b/c", namespace="fixture~taxonomy", concept="Concept"))
    fact = parser(raw, cik=CIK).facts[0]
    assert fact.namespace == "fixture~taxonomy"
    assert fact.source.pointer == "/facts/fixture~0taxonomy/Concept/units/a~0b~1c/0"
    assert decode_pointer(json.loads(raw), fact.source.pointer)["val"] == 123


def test_optional_metadata_is_not_inferred(parser):
    row = {key: value for key, value in observation().items() if key not in {"start", "fy", "fp"}}
    fact = parser(body(document([row])), cik=CIK).facts[0]
    assert (fact.start, fact.fiscal_year, fact.fiscal_period, fact.frame) == (None, None, None, None)
    assert fact.cik == CIK
    assert fact.accession == ACCESSION  # Filing-agent CIK need not equal issuer CIK.


def test_snapshots_and_observations_are_immutable(parser):
    snapshot = parser(body(document()), cik=CIK)
    assert isinstance(snapshot.facts, tuple)
    with pytest.raises(FrozenInstanceError):
        snapshot.cik = "0000000001"
    with pytest.raises(FrozenInstanceError):
        snapshot.facts[0].value = "999"


@pytest.mark.parametrize("facts", [{}, {"us-gaap": {}}, {"us-gaap": {"Revenue": {"units": {}}}}])
def test_observed_empty_facts_are_distinct_from_missing_source(parser, facts):
    raw = body({"cik": 320193, "facts": facts})
    snapshot = parser(raw, cik=CIK)
    assert snapshot.facts == ()
    assert snapshot.sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("changes", [
    {"val": True}, {"val": None}, {"val": "source-value-not-a-number"},
    {"val": float("nan")}, {"val": float("inf")},
    {"start": "2026-04-01"}, {"start": "2026-02-29"},
    {"end": "2026-02-29"}, {"end": None}, {"end": 20260331},
    {"filed": "2026-5-1"}, {"filed": None},
    {"accn": "bad-accession"}, {"accn": None},
    {"form": ""}, {"form": None}, {"form": True},
    {"fy": True}, {"fy": "2026"}, {"fy": -1},
    {"fp": True}, {"fp": ""}, {"frame": False},
])
def test_malformed_observation_is_not_silently_dropped(parser, changes):
    from src.sec_research.common import SourceError

    with pytest.raises(SourceError) as caught:
        parser(body(document([observation(), observation(**changes)])), cik=CIK)
    assert caught.value.code
    assert "source-value-not-a-number" not in str(caught.value)


@pytest.mark.parametrize("missing", ["val", "end", "filed", "accn", "form"])
def test_required_observation_fields_cannot_be_missing(parser, missing):
    from src.sec_research.common import SourceError

    row = observation()
    del row[missing]
    with pytest.raises(SourceError):
        parser(body(document([row])), cik=CIK)


@pytest.mark.parametrize("value", [
    {}, {"cik": 1, "facts": {}}, {"cik": True, "facts": {}},
    {"cik": 320193, "facts": []}, {"cik": 320193, "facts": {"us-gaap": []}},
    {"cik": 320193, "facts": {"us-gaap": {"Revenue": {}}}},
    {"cik": 320193, "facts": {"us-gaap": {"Revenue": {"units": []}}}},
    {"cik": 320193, "facts": {"us-gaap": {"Revenue": {"units": {"USD": {}}}}}},
])
def test_invalid_companyfacts_shape_or_identity_cannot_be_empty_success(parser, value):
    from src.sec_research.common import SourceError

    with pytest.raises(SourceError):
        parser(body(value), cik=CIK)
