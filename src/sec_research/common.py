"""Pure, exact decoding and source-bound SEC scalar validation."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DecimalException
import hashlib
import json
import re
import unicodedata


class SourceError(ValueError):
    """Parser failure with a closed caller-selected code and source pointer only."""

    def __init__(self, code: str, pointer: str = ""):
        self.code = code
        self.pointer = pointer
        super().__init__(code, pointer)


@dataclass(frozen=True)
class SourceRef:
    sha256: str
    pointer: str


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def json_pointer(*parts) -> str:
    encoded = []
    for part in parts:
        if not isinstance(part, (str, int)) or isinstance(part, bool):
            raise SourceError("invalid_pointer")
        text = str(part)
        if _has_surrogate(text):
            raise SourceError("invalid_pointer")
        encoded.append(text.replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(encoded) if encoded else ""


def source_ref(body: bytes, pointer: str) -> SourceRef:
    if not isinstance(body, bytes):
        raise SourceError("invalid_source")
    return SourceRef(hashlib.sha256(body).hexdigest(), pointer)


class _ObjectPairs(list):
    """Keep duplicate keys until their full source path is available."""


def _materialize(value, parts=()):
    if isinstance(value, _ObjectPairs):
        result = {}
        for key, child in value:
            child_parts = (*parts, key)
            pointer = json_pointer(*child_parts)
            if key in result:
                raise SourceError("duplicate_key", pointer)
            result[key] = _materialize(child, child_parts)
        return result
    if isinstance(value, list):
        return [_materialize(child, (*parts, index)) for index, child in enumerate(value)]
    return value


def _decimal_number(token: str) -> Decimal:
    try:
        value = Decimal(token)
    except (DecimalException, OverflowError, ValueError):
        raise SourceError("invalid_number") from None
    if not value.is_finite():
        raise SourceError("invalid_number")
    return value


def _integer_number(token: str) -> int:
    try:
        return int(token)
    except (OverflowError, ValueError):
        raise SourceError("invalid_number") from None


def _nonfinite_number(token: str):
    raise SourceError("invalid_number")


def decode_object(body: bytes) -> dict:
    if not isinstance(body, bytes):
        raise SourceError("invalid_source")
    try:
        value = json.loads(
            body.decode("utf-8"),
            parse_float=_decimal_number,
            parse_int=_integer_number,
            parse_constant=_nonfinite_number,
            object_pairs_hook=_ObjectPairs,
        )
        if not isinstance(value, _ObjectPairs):
            raise SourceError("invalid_root")
        return _materialize(value)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise SourceError("invalid_json") from None


def normalize_cik(value: str) -> str:
    if not isinstance(value, str):
        raise SourceError("invalid_cik")
    value = value.strip()
    if value[:4].lower() == "cik:":
        value = value[4:]
    if not re.fullmatch(r"[0-9]{1,10}", value) or int(value) == 0:
        raise SourceError("invalid_cik")
    return value.zfill(10)


def validate_payload_cik(payload: dict, cik: str, *, required: bool) -> None:
    expected = normalize_cik(cik)
    if "cik" not in payload:
        if required:
            raise SourceError("missing_cik", "/cik")
        return
    value = payload["cik"]
    if type(value) is int:
        value = str(value)
    try:
        actual = normalize_cik(value)
    except SourceError:
        raise SourceError("invalid_cik", "/cik") from None
    if actual != expected:
        raise SourceError("cik_mismatch", "/cik")


def date_value(value, pointer, *, optional=False) -> str | None:
    if optional and (value is None or value == ""):
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise SourceError("invalid_date", pointer)
    try:
        date.fromisoformat(value)
    except ValueError:
        raise SourceError("invalid_date", pointer) from None
    return value


def accession_value(value, pointer) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", value):
        raise SourceError("invalid_accession", pointer)
    return value


def text_value(value, pointer, *, optional=False) -> str | None:
    if value is None and optional:
        return None
    if (not isinstance(value, str) or not value.strip()
            or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)):
        raise SourceError("invalid_text", pointer)
    return value
