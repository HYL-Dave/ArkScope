"""Byte-stable journal serialization shared by current and retained readers."""

import ast
from importlib import import_module
from pathlib import Path

import pytest


_OWNER = "src.lifecycle_journal_codec"
_CASES = [
    pytest.param(
        None,
        b"null",
        "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        id="null",
    ),
    pytest.param(
        [True, False, None, 0, -2, 1.5],
        b"[true,false,null,0,-2,1.5]",
        "90dfd347bf2ff1098f211c0258ed6645b08cdf7df4da3b0ea4d9368a9a5eb759",
        id="scalar-array",
    ),
    pytest.param(
        {"z": [3, {"b": 2, "a": 1}], "a": {"d": [None, True, False], "c": "first"}},
        b'{"a":{"c":"first","d":[null,true,false]},"z":[3,{"a":1,"b":2}]}',
        "1083a8ce5911742ccb3f744ca90098a243ebe677d38db83216e3c8cb4273605c",
        id="nested-key-sort-compact",
    ),
    pytest.param(
        {"z": "\U0001f680", "a": "caf\u00e9 \u4e2d"},
        rb'{"a":"caf\u00e9 \u4e2d","z":"\ud83d\ude80"}',
        "4b5704b5afed23706bd0c195a110a296219e5cef9d18f0dc7e71c86e2ed1004e",
        id="ascii-escaping",
    ),
    pytest.param(
        {"z": "\b\f\r\x00", "a": 'quote" slash\\ line\n\t'},
        rb'{"a":"quote\" slash\\ line\n\t","z":"\b\f\r\u0000"}',
        "c116ff05bd0ea0b5a3f991efe3f2d4254bd41f2801abac52c2aaaef16591cbd2",
        id="control-escaping",
    ),
    pytest.param(
        {"\u4e2d": 2, "\u00e9": 1, "a": 0},
        rb'{"a":0,"\u00e9":1,"\u4e2d":2}',
        "1e28c10f01a640bce81e3d0ed71e098937e44a7ef4fb730ac4a03a2035e93721",
        id="unicode-key-sort",
    ),
]


def test_neutral_journal_codec_owns_public_functions():
    codec = import_module(_OWNER)
    assert codec.canonical_json.__module__ == _OWNER
    assert codec.digest_json.__module__ == _OWNER


@pytest.mark.parametrize("value,expected_bytes,_digest", _CASES)
def test_canonical_json_matches_literal_journal_bytes(value, expected_bytes, _digest):
    codec = import_module(_OWNER)
    assert codec.canonical_json(value).encode("utf-8") == expected_bytes


@pytest.mark.parametrize("value,_encoded,expected_digest", _CASES)
def test_digest_json_matches_literal_utf8_sha256(value, _encoded, expected_digest):
    codec = import_module(_OWNER)
    assert codec.digest_json(value) == expected_digest


def test_canonical_json_can_preserve_utf8_without_ascii_expansion():
    codec = import_module(_OWNER)
    value = {"z": "\U0001f680", "a": "caf\u00e9 \u4e2d"}
    assert codec.canonical_json(value, ensure_ascii=False).encode("utf-8") == (
        b'{"a":"caf\xc3\xa9 \xe4\xb8\xad","z":"\xf0\x9f\x9a\x80"}'
    )
    assert codec.digest_json(value) == "4b5704b5afed23706bd0c195a110a296219e5cef9d18f0dc7e71c86e2ed1004e"


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")], ids=["nan", "infinity", "negative-infinity"])
@pytest.mark.parametrize("nested", [False, True], ids=["scalar", "nested"])
@pytest.mark.parametrize("operation", ["canonical", "utf8", "digest"])
def test_nonfinite_numbers_are_rejected_before_journaling(number, nested, operation):
    codec = import_module(_OWNER)
    value = {"rows": [{"value": number}]} if nested else number
    with pytest.raises(ValueError):
        if operation == "digest":
            codec.digest_json(value)
        else:
            codec.canonical_json(value, ensure_ascii=operation != "utf8")


@pytest.mark.parametrize("module,names", [
    ("lifecycle_investigation.store", {"canonical_json", "digest_json"}),
    ("lifecycle_investigation.adoption", {"digest_json"}),
    ("lifecycle_investigation.agent", {"digest_json"}),
    ("lifecycle_investigation.target", {"digest_json"}),
    ("lifecycle_investigation.migration", {"digest_json"}),
    ("lifecycle_investigation.disposal", {"canonical_json", "digest_json"}),
    ("lifecycle_investigation.review", {"canonical_json"}),
    ("ticker_identity_history", {"digest_json"}),
])
def test_journal_consumers_import_the_neutral_codec_directly(module, names):
    path = Path(__file__).resolve().parents[1] / "src" / (module.replace(".", "/") + ".py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == _OWNER
        for alias in node.names
        if alias.asname is None
    }
    assert names <= imported
    legacy = {"_json", "_sha"}
    legacy_imports = [
        (node.lineno, node.name, node.asname)
        for node in ast.walk(tree)
        if isinstance(node, ast.alias) and legacy.intersection((node.name, node.asname))
    ]
    assert not legacy_imports, legacy_imports
    legacy_definitions = [
        (node.lineno, node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in legacy
    ]
    assert not legacy_definitions, legacy_definitions
    legacy_references = [
        (node.lineno, node.id if isinstance(node, ast.Name) else node.attr)
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id in legacy)
        or (isinstance(node, ast.Attribute) and node.attr in legacy)
    ]
    assert not legacy_references, legacy_references
