"""Tests for the compressor overflow store (P1.4 commit 1).

Covers spec acceptance:

  - **A1**: 500KB round-trip — `test_round_trip_500kb`
  - **0/record_id_stable**: same `(tool_name, args, payload)` triple →
    same `record_id`; changing any of the three components →
    different `record_id`
  - **A2 (no agent imports)**: ast audit on the compressor package
  - Path-traversal guard for `record_id` and `session_id`
  - Missing / corrupt records return None (Layer 0 fail-open)
  - utf-8 round-trip including non-ASCII content
  - Session isolation: a record written in session A is invisible
    to session B
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.shared.compressor import (
    CompressionRecord,
    OverflowStore,
    canonical_args_hash,
    compute_record_id,
    is_valid_record_id,
)


# ============================================================
# record_id derivation (spec §3.1.1 contract)
# ============================================================


class TestRecordIdDerivation:
    def test_record_id_is_16_hex_chars(self):
        rid = compute_record_id("get_ticker_news", {"ticker": "NVDA"}, b"payload")
        assert len(rid) == 16
        assert all(c in "0123456789abcdef" for c in rid)

    def test_record_id_stable_for_same_triple(self):
        a = compute_record_id("t", {"x": 1}, b"hello")
        b = compute_record_id("t", {"x": 1}, b"hello")
        assert a == b

    def test_record_id_changes_on_tool_name(self):
        """Provenance: same payload, different tool → different id."""
        a = compute_record_id("tool_a", {"x": 1}, b"hello")
        b = compute_record_id("tool_b", {"x": 1}, b"hello")
        assert a != b

    def test_record_id_changes_on_args(self):
        a = compute_record_id("t", {"x": 1}, b"hello")
        b = compute_record_id("t", {"x": 2}, b"hello")
        assert a != b

    def test_record_id_changes_on_payload(self):
        a = compute_record_id("t", {"x": 1}, b"hello")
        b = compute_record_id("t", {"x": 1}, b"world")
        assert a != b

    def test_record_id_args_none_equivalent_to_empty_dict(self):
        """args=None and args={} both canonicalize to '{}'."""
        a = compute_record_id("t", None, b"x")
        b = compute_record_id("t", {}, b"x")
        assert a == b

    def test_record_id_rejects_empty_tool_name(self):
        with pytest.raises(ValueError):
            compute_record_id("", {}, b"x")

    def test_record_id_rejects_non_bytes_payload(self):
        with pytest.raises(TypeError):
            compute_record_id("t", {}, "string-not-bytes")  # type: ignore[arg-type]


class TestCanonicalArgsHash:
    def test_dict_order_independent(self):
        h1 = canonical_args_hash({"a": 1, "b": 2})
        h2 = canonical_args_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_handles_nested_dicts(self):
        h1 = canonical_args_hash({"x": {"a": 1, "b": 2}})
        h2 = canonical_args_hash({"x": {"b": 2, "a": 1}})
        assert h1 == h2

    def test_empty_dict_produces_full_sha256(self):
        h = canonical_args_hash({})
        assert len(h) == 64

    def test_none_equivalent_to_empty(self):
        assert canonical_args_hash(None) == canonical_args_hash({})

    def test_unicode_args_stable(self):
        h1 = canonical_args_hash({"name": "中文"})
        h2 = canonical_args_hash({"name": "中文"})
        assert h1 == h2


# ============================================================
# is_valid_record_id (path-traversal guard)
# ============================================================


class TestIsValidRecordId:
    def test_valid_id(self):
        assert is_valid_record_id("0123456789abcdef") is True

    def test_uppercase_rejected(self):
        assert is_valid_record_id("ABCDEF0123456789") is False

    def test_too_short(self):
        assert is_valid_record_id("0123456789abcde") is False

    def test_too_long(self):
        assert is_valid_record_id("0123456789abcdef0") is False

    def test_path_traversal_rejected(self):
        for bad in ["../etc/passwd", "..", "../", "../../sibling", "/abs/path"]:
            assert is_valid_record_id(bad) is False, f"bad: {bad!r}"

    def test_empty_rejected(self):
        assert is_valid_record_id("") is False

    def test_non_string_rejected(self):
        assert is_valid_record_id(None) is False
        assert is_valid_record_id(12345) is False
        assert is_valid_record_id(["a", "b"]) is False


# ============================================================
# OverflowStore round-trip (A1 acceptance)
# ============================================================


class TestOverflowStoreRoundTrip:
    def test_round_trip_small(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="sess-1")
        record = store.write("get_ticker_news", {"ticker": "NVDA"}, "small payload")

        result = store.read(record.record_id)
        assert result is not None
        assert result.original_payload == "small payload"
        assert result.tool_name == "get_ticker_news"
        assert result.args == {"ticker": "NVDA"}
        assert result.original_size == len(b"small payload")

    def test_round_trip_500kb(self, tmp_path):
        """A1 acceptance: 500KB tool output round-trips byte-for-byte."""
        store = OverflowStore(tmp_path, session_id="sess-1")
        big_payload = "x" * 500_000
        record = store.write("get_some_tool", {}, big_payload)

        result = store.read(record.record_id)
        assert result is not None
        assert result.original_payload == big_payload
        assert result.original_size == 500_000
        assert len(result.original_payload) == 500_000

    def test_unicode_payload_round_trip(self, tmp_path):
        """utf-8 with CJK + emoji + ascii round-trips cleanly."""
        store = OverflowStore(tmp_path, session_id="sess-1")
        text = "中文 mixed with emoji 🎉 and ascii — unicode test"
        record = store.write("t", {}, text)

        result = store.read(record.record_id)
        assert result is not None
        assert result.original_payload == text
        # Bytes count uses utf-8 encoding (not codepoint count)
        assert result.original_size == len(text.encode("utf-8"))

    def test_metadata_persists_through_round_trip(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="sess-1")
        args = {"a": 1, "b": "two", "c": [1, 2, 3]}
        record = store.write("t", args, "payload")

        result = store.read(record.record_id)
        assert result is not None
        assert result.args == args
        assert result.args_hash == canonical_args_hash(args)
        # written_at is an ISO timestamp with timezone info
        assert "T" in result.written_at
        assert "+" in result.written_at or "Z" in result.written_at

    def test_record_id_matches_compute_record_id(self, tmp_path):
        """The record_id assigned by write() matches compute_record_id() on
        the same triple — there's only one canonical derivation."""
        store = OverflowStore(tmp_path, session_id="sess-1")
        record = store.write("t", {"x": 1}, "payload")

        expected = compute_record_id("t", {"x": 1}, b"payload")
        assert record.record_id == expected


# ============================================================
# Missing / corrupt / malformed records (fail-open, never raise)
# ============================================================


class TestMissingAndCorruptRecords:
    def test_missing_returns_none(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="sess-1")
        assert store.read("0000000000000000") is None

    def test_invalid_record_id_returns_none(self, tmp_path):
        """Path-traversal / malformed IDs return None, NOT raise."""
        store = OverflowStore(tmp_path, session_id="sess-1")
        bad_ids = [
            "../etc/passwd",
            "ABCDEF0123456789",   # uppercase
            "short",
            "",
            "../../sibling",
            "/absolute/path",
        ]
        for bad in bad_ids:
            assert store.read(bad) is None, f"id {bad!r} must return None"

    def test_corrupt_json_returns_none(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="sess-1")
        record = store.write("t", {}, "payload")
        path = store.session_dir / f"{record.record_id}.json"
        path.write_text("{not valid json", encoding="utf-8")

        assert store.read(record.record_id) is None

    def test_missing_required_field_returns_none(self, tmp_path):
        """A record file present but missing a required field should
        gracefully degrade to None (corrupt/old-format scenario)."""
        store = OverflowStore(tmp_path, session_id="sess-1")
        # Create a file at a valid record_id path but with incomplete data
        valid_id = "0" * 16
        path = store.session_dir / f"{valid_id}.json"
        path.write_text(json.dumps({"record_id": valid_id}), encoding="utf-8")

        assert store.read(valid_id) is None


# ============================================================
# Session isolation
# ============================================================


class TestSessionIsolation:
    def test_session_b_cannot_read_session_a_record(self, tmp_path):
        """Records written in one session are invisible to other sessions."""
        store_a = OverflowStore(tmp_path, session_id="sess-a")
        store_b = OverflowStore(tmp_path, session_id="sess-b")

        record = store_a.write("t", {}, "payload")
        # Same record_id — but session B doesn't see it
        assert store_b.read(record.record_id) is None
        # Session A still has it
        assert store_a.read(record.record_id) is not None

    def test_invalid_session_id_rejected(self, tmp_path):
        """Path-traversal vectors at the session boundary are rejected."""
        for bad in ["../escape", "a/b", "..", "a\\b", "x/../y", ""]:
            with pytest.raises(ValueError):
                OverflowStore(tmp_path, session_id=bad)

    def test_session_dir_created_on_init(self, tmp_path):
        OverflowStore(tmp_path, session_id="auto-created")
        assert (tmp_path / "auto-created").is_dir()

    def test_session_dir_exposed_via_property(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="sess-x")
        assert store.session_dir == tmp_path / "sess-x"
        assert store.session_id == "sess-x"


# ============================================================
# Library-not-runner guarantee (A2 acceptance, spec §1.2 #1)
# ============================================================


class TestNoAgentImports:
    """The compressor package must not import from src.agents.anthropic_agent
    or src.agents.openai_agent. Future multi-round runner work depends on
    being able to reuse the compressor as a library; this test catches any
    drift toward a circular dependency."""

    @staticmethod
    def _scan_imports(py_path: Path) -> list[str]:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
        offences: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "anthropic_agent" in alias.name or "openai_agent" in alias.name:
                        offences.append(f"{py_path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "anthropic_agent" in module or "openai_agent" in module:
                    offences.append(f"{py_path.name}: from {module} ...")
        return offences

    def test_no_anthropic_or_openai_agent_imports(self):
        compressor_dir = (
            project_root / "src" / "agents" / "shared" / "compressor"
        )
        offences: list[str] = []
        for py_file in sorted(compressor_dir.glob("*.py")):
            offences.extend(self._scan_imports(py_file))
        assert offences == [], (
            f"compressor must not import agent code; found: {offences}"
        )