"""Original-byte decoding and reusable SEC scalar contracts."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
import hashlib
import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_common_has_a_runtime_owner():
    assert (ROOT / "src/sec_research/common.py").is_file(), "SEC common parser missing"


@pytest.fixture
def common():
    assert (ROOT / "src/sec_research/common.py").is_file(), "SEC common parser missing"
    return importlib.import_module("src.sec_research.common")


def test_decode_preserves_exact_decimal_and_large_integer(common):
    raw = b'{"value":1234567890.123456789012345678900,"count":1208925819614629174706177,"tiny":1e-1000}'
    with localcontext() as context:
        context.prec = 3
        result = common.decode_object(raw)
    assert result["value"] == Decimal("1234567890.123456789012345678900")
    assert str(result["value"]) == "1234567890.123456789012345678900"
    assert type(result["count"]) is int
    assert result["count"] == 1208925819614629174706177
    assert result["tiny"] == Decimal("1e-1000")


@pytest.mark.parametrize("raw,code,pointer", [
    (b'{"secret":1,"secret":2}', "duplicate_key", "/secret"),
    (b'{"a/b":{"~key":1,"~key":2}}', "duplicate_key", "/a~1b/~0key"),
    (b'{"x":NaN}', "invalid_number", ""),
    (b'{"x":Infinity}', "invalid_number", ""),
    (b'{"x":-Infinity}', "invalid_number", ""),
    (b'{"x":1e999999999999999999999999999}', "invalid_number", ""),
])
def test_duplicate_keys_and_nonfinite_numbers_are_rejected(common, raw, code, pointer):
    with pytest.raises(common.SourceError) as caught:
        common.decode_object(raw)
    assert (caught.value.code, caught.value.pointer) == (code, pointer)
    assert repr(raw) not in str(caught.value)


@pytest.mark.parametrize("raw", [b'[]', b'null', b'1', b'"private-body"', b'{"private-body":', b'\xff'])
def test_invalid_json_is_typed_and_does_not_expose_body(common, raw):
    with pytest.raises(common.SourceError) as caught:
        common.decode_object(raw)
    assert caught.value.code in {"invalid_json", "invalid_root"}
    assert caught.value.pointer == ""
    assert "private-body" not in str(caught.value)


@pytest.mark.parametrize("value", ['{}', {}, bytearray(b'{}'), None])
def test_only_original_bytes_are_accepted(common, value):
    with pytest.raises(common.SourceError):
        common.decode_object(value)


@pytest.mark.parametrize("value", ["0", "0000000000", "", "CIK:", "+1", "-1", "12345678901", "1 2", "CIK: 1", "\u0661", "\uff11", 1, True, None])
def test_cik_requires_nonzero_ascii_digits(common, value):
    with pytest.raises(common.SourceError) as caught:
        common.normalize_cik(value)
    assert caught.value.code == "invalid_cik"


@pytest.mark.parametrize("value", ["320193", "0000320193", "  cIk:320193\t"])
def test_cik_normalizes_explicit_identity(common, value):
    assert common.normalize_cik(value) == "0000320193"


def test_pointer_escaping_and_original_byte_hash(common):
    raw = b'{ "a/b": {"~x": [1]} }\n'
    pointer = common.json_pointer("a/b", "~x", 0)
    assert pointer == "/a~1b/~0x/0"
    assert common.json_pointer() == ""
    assert common.json_pointer("") == "/"
    ref = common.source_ref(raw, pointer)
    assert ref.sha256 == hashlib.sha256(raw).hexdigest()
    assert ref.pointer == pointer
    assert ref.sha256 != common.source_ref(b'{"a/b":{"~x":[1]}}', pointer).sha256
    with pytest.raises(FrozenInstanceError):
        ref.pointer = ""


def test_pointer_rejects_unpaired_surrogates_but_preserves_astral_unicode(common):
    for value in ("bad\ud800", "bad\udfff"):
        with pytest.raises(common.SourceError):
            common.json_pointer(value)
    value = common.decode_object(b'{"label":"\\ud83d\\ude00"}')["label"]
    assert common.text_value(value, "/label") == "\U0001f600"
    assert common.json_pointer(value, "USD/shares") == "/\U0001f600/USD~1shares"


@pytest.mark.parametrize("value", ["2026-02-29", "2026-9-01", "20260901", "2026-09-01T00:00:00Z", "0000-01-01", " 2026-09-01", 20260901, True])
def test_dates_are_strict_calendar_dates(common, value):
    with pytest.raises(common.SourceError) as caught:
        common.date_value(value, "/date")
    assert (caught.value.code, caught.value.pointer) == ("invalid_date", "/date")


def test_optional_dates_are_missing_not_guessed(common):
    assert common.date_value("2024-02-29", "/date") == "2024-02-29"
    for value in (None, ""):
        assert common.date_value(value, "/date", optional=True) is None
        with pytest.raises(common.SourceError):
            common.date_value(value, "/date")


@pytest.mark.parametrize("value", ["", "   ", "bad\ntext", "bad\x7ftext", "bad\u0085text", "bad\ud800text", 1, 1.2, True, Decimal("1")])
def test_text_is_nonempty_unicode_not_a_coerced_scalar(common, value):
    with pytest.raises(common.SourceError) as caught:
        common.text_value(value, "/label", optional=True)
    assert (caught.value.code, caught.value.pointer) == ("invalid_text", "/label")


def test_text_and_accession_shared_apis(common):
    assert common.text_value("\u6536\u5165", "/label") == "\u6536\u5165"
    assert common.text_value(None, "/label", optional=True) is None
    with pytest.raises(common.SourceError):
        common.text_value(None, "/label")
    assert common.accession_value("0000950170-26-000001", "/accn") == "0000950170-26-000001"
    for value in ("000095017026000001", "0000950170-2026-000001", "0000950170-26-000001\n", None, 1):
        with pytest.raises(common.SourceError) as caught:
            common.accession_value(value, "/accn")
        assert caught.value.pointer == "/accn"


def test_payload_cik_is_checked_without_identity_inference(common):
    for value in (320193, "0000320193"):
        assert common.validate_payload_cik({"cik": value}, "0000320193", required=True) is None
    assert common.validate_payload_cik({}, "0000320193", required=False) is None
    for payload, required in [({}, True), ({"cik": 1}, False), ({"cik": None}, False), ({"cik": True}, True), ({"cik": 320193.0}, True)]:
        with pytest.raises(common.SourceError) as caught:
            common.validate_payload_cik(payload, "0000320193", required=required)
        assert caught.value.pointer == "/cik"
