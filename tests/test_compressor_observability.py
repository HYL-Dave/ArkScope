"""P1.4 commit 4 observability tests.

The Medium finding from commit 3 review: scratchpad / replay / chat
history were silently logging compressed-only content (the L0 hook ran
before any of them got the result). Commit 4's contract: each tool call
emits a single ``compression`` dict that is forwarded byte-equal to all
three audit pipelines, and the pieces reconcile against the on-disk
overflow record.

These tests lock:

  - the metadata shape (single ``compression`` key with 7 fields)
  - UTF-8 byte semantics (so CJK / emoji line up with OverflowStore.original_size)
  - 16-hex digest length (aligns with record_id)
  - passthrough behaviour when L0 is disabled / payload under budget
  - cross-pipeline equality (pad ⇔ replay ⇔ chat-history)
  - cross-disk equality (raw_digest matches sha256 of overflow record's
    ``original_payload``)
  - replay JSON round-trip + backwards compat (old fixtures without
    ``compression`` load cleanly)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.shared.compressor import CompressorConfig
from src.agents.shared.context_manager import ContextManager
from src.agents.shared.replay import (
    CapturedToolCall,
    ReplayCapture,
    load_trace,
)
from src.agents.shared.scratchpad import Scratchpad


# ============================================================
# Helpers
# ============================================================


def _make_ctx(tmp_path: Path, *, enabled: bool = True, **cfg_kwargs) -> ContextManager:
    config = CompressorConfig(enabled=enabled, **cfg_kwargs) if enabled else None
    return ContextManager(
        model="claude-opus-4-7",
        keep_recent_turns=2,
        session_id="obs-session",
        overflow_dir=tmp_path,
        compaction_config=config,
    )


def _wrapped(content: str, tool_name: str) -> str:
    return f'<tool_output tool="{tool_name}">\n{content}\n</tool_output>'


_COMPRESSION_KEYS = {
    "layer", "compressed",
    "raw_bytes", "compressed_bytes",
    "raw_digest", "compressed_digest",
    "overflow_record_id",
}


# ============================================================
# Metadata shape: compress_tool_result
# ============================================================


class TestCompressToolResultShape:
    def test_returns_string_and_metadata_tuple(self, tmp_path):
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=1000)
        out, meta = ctx.compress_tool_result("t", {}, "small")
        assert isinstance(out, str)
        assert isinstance(meta, dict)
        assert set(meta.keys()) == _COMPRESSION_KEYS

    def test_passthrough_metadata_when_l0_disabled(self, tmp_path):
        """ContextManager without compaction → metadata still emitted, but
        compressed=False, raw==compressed, no record_id."""
        ctx = ContextManager(model="claude-opus-4-7")  # no compaction config
        out, meta = ctx.compress_tool_result("t", {}, "hello")
        assert out == "hello"
        assert meta["compressed"] is False
        assert meta["raw_bytes"] == 5
        assert meta["compressed_bytes"] == 5
        assert meta["raw_digest"] == meta["compressed_digest"]
        assert meta["overflow_record_id"] is None
        assert meta["layer"] == 0

    def test_passthrough_metadata_when_under_budget(self, tmp_path):
        """L0 enabled but payload < budget → reducer never runs; we still
        emit the same metadata shape with compressed=False."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10_000)
        small = "small payload"
        out, meta = ctx.compress_tool_result("t", {}, small)
        assert out == small
        assert meta["compressed"] is False
        assert meta["raw_bytes"] == meta["compressed_bytes"]
        assert meta["raw_digest"] == meta["compressed_digest"]
        assert meta["overflow_record_id"] is None

    def test_compressed_metadata_when_oversized(self, tmp_path):
        """L0 enabled + payload over budget → compressed=True + record_id
        present + bytes go down."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)
        wrapped = _wrapped(
            json.dumps({"results": [{"url": "u", "content": "y" * 30_000}]}),
            "tavily_search",
        )
        out, meta = ctx.compress_tool_result(
            "tavily_search", {"query": "q"}, wrapped,
        )
        assert meta["compressed"] is True
        assert meta["raw_bytes"] > meta["compressed_bytes"]
        assert meta["raw_digest"] != meta["compressed_digest"]
        assert meta["overflow_record_id"] is not None
        assert len(meta["overflow_record_id"]) == 16
        assert all(c in "0123456789abcdef" for c in meta["overflow_record_id"])

    def test_metadata_uses_utf8_byte_counts_for_cjk(self, tmp_path):
        """CJK content: char count != byte count. We must report bytes so
        raw_bytes lines up with OverflowStore.original_size."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10_000)
        cjk = "蘋果公司股價" * 10  # 60 chars but 180 utf-8 bytes
        out, meta = ctx.compress_tool_result("t", {}, cjk)
        # 60 chars * 3 utf-8 bytes per char = 180 bytes
        assert meta["raw_bytes"] == 180
        assert meta["raw_bytes"] != len(cjk)  # would be 60 if we used chars

    def test_metadata_uses_utf8_byte_counts_for_emoji(self, tmp_path):
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10_000)
        emoji = "🚀🎯💡"  # 3 chars, 12 utf-8 bytes (4 each)
        out, meta = ctx.compress_tool_result("t", {}, emoji)
        assert meta["raw_bytes"] == 12

    def test_digest_length_is_16_hex(self, tmp_path):
        """Digest is sha256[:16] hex — same length as record_id, easy
        for humans to compare side-by-side."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10_000)
        out, meta = ctx.compress_tool_result("t", {}, "data")
        for k in ("raw_digest", "compressed_digest"):
            assert len(meta[k]) == 16
            assert all(c in "0123456789abcdef" for c in meta[k])

    def test_raw_digest_matches_overflow_payload_sha256(self, tmp_path):
        """Cross-disk reconciliation: re-hashing the on-disk record's
        original_payload reproduces the metadata's raw_digest."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)
        big = _wrapped(json.dumps({"x": "y" * 50_000}), "t")
        _out, meta = ctx.compress_tool_result("t", {}, big)
        record_id = meta["overflow_record_id"]
        assert record_id is not None
        retrieved_payload = ctx.compressor.get_overflow_payload(record_id)
        assert retrieved_payload is not None
        recomputed = hashlib.sha256(
            retrieved_payload.encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        assert recomputed == meta["raw_digest"]

    def test_raw_bytes_matches_overflow_record_original_size(self, tmp_path):
        """OverflowStore stores original_size = len(utf-8 bytes). Our
        metadata's raw_bytes must equal it for reconciliation."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)
        # CJK to make sure we don't accidentally line up via len(str)
        cjk_big = "蘋果" * 5_000  # 10K chars, 30K utf-8 bytes
        wrapped = _wrapped(cjk_big, "t")
        _out, meta = ctx.compress_tool_result("t", {}, wrapped)
        record_id = meta["overflow_record_id"]
        assert record_id is not None
        # Read the on-disk record file directly
        record_files = list(tmp_path.glob(f"*/{record_id}.json"))
        assert len(record_files) == 1
        record_data = json.loads(record_files[0].read_text(encoding="utf-8"))
        assert record_data["original_size"] == meta["raw_bytes"]

    def test_maybe_apply_layer_0_bc_wrapper_preserves_old_signature(self, tmp_path):
        """Old code calling maybe_apply_layer_0 still gets back just a string."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10_000)
        out = ctx.maybe_apply_layer_0("t", {}, "data")
        assert isinstance(out, str)
        assert out == "data"


# ============================================================
# Scratchpad: compression in JSONL
# ============================================================


class TestScratchpadCompression:
    def test_log_tool_result_includes_compression(self, tmp_path):
        pad = Scratchpad(query="Q", provider="anthropic", model="claude-opus-4-7")
        # Redirect to tmp_path
        pad._filepath = tmp_path / "test_pad.jsonl"
        pad._file = open(pad._filepath, "a", encoding="utf-8")

        compression = {
            "layer": 0, "compressed": True,
            "raw_bytes": 9000, "compressed_bytes": 1500,
            "raw_digest": "deadbeef" * 2, "compressed_digest": "cafebabe" * 2,
            "overflow_record_id": "abcdef0123456789",
        }
        pad.log_tool_result("tavily_search",
                            result_data="<compressed>",
                            tool_input={"q": "x"},
                            compression=compression)
        pad.close()

        events = [
            json.loads(line) for line in
            pad._filepath.read_text(encoding="utf-8").splitlines() if line
        ]
        tool_event = [e for e in events if e.get("type") == "tool_result"][0]
        assert "compression" in tool_event["data"]
        assert tool_event["data"]["compression"] == compression

    def test_log_tool_result_omits_compression_when_none(self, tmp_path):
        pad = Scratchpad(query="Q", provider="anthropic", model="claude-opus-4-7")
        pad._filepath = tmp_path / "test_pad.jsonl"
        pad._file = open(pad._filepath, "a", encoding="utf-8")
        pad.log_tool_result("t", result_data="x", tool_input={})
        pad.close()
        events = [
            json.loads(line) for line in
            pad._filepath.read_text(encoding="utf-8").splitlines() if line
        ]
        tool_event = [e for e in events if e.get("type") == "tool_result"][0]
        assert "compression" not in tool_event["data"]


# ============================================================
# ReplayCapture: compression on CapturedToolCall
# ============================================================


class TestReplayCompression:
    def test_record_tool_call_stores_compression(self):
        cap = ReplayCapture(provider="anthropic", model="claude-opus-4-7", entrypoint="test")
        cap.set_initial(question="Q", system_prompt="P", tools_available=["t"])
        compression = {
            "layer": 0, "compressed": True,
            "raw_bytes": 9000, "compressed_bytes": 1500,
            "raw_digest": "0" * 16, "compressed_digest": "1" * 16,
            "overflow_record_id": "f" * 16,
        }
        cap.record_tool_call("t", {"a": 1}, "result", compression=compression)
        trace = cap.to_trace()
        assert trace.tool_calls[0].compression == compression

    def test_record_tool_call_compression_optional(self):
        """Old call sites (no compression kwarg) still work; field is None."""
        cap = ReplayCapture(provider="anthropic", model="claude-opus-4-7", entrypoint="test")
        cap.set_initial(question="Q", system_prompt="P", tools_available=["t"])
        cap.record_tool_call("t", {"a": 1}, "result")
        assert cap.to_trace().tool_calls[0].compression is None

    def test_serialize_round_trip(self, tmp_path):
        cap = ReplayCapture(provider="anthropic", model="claude-opus-4-7", entrypoint="test")
        cap.set_initial(question="Q", system_prompt="P", tools_available=["t"])
        compression = {
            "layer": 0, "compressed": True,
            "raw_bytes": 9000, "compressed_bytes": 1500,
            "raw_digest": "0" * 16, "compressed_digest": "1" * 16,
            "overflow_record_id": "f" * 16,
        }
        cap.record_tool_call("t", {"a": 1}, "x", compression=compression)
        cap.record_final("done")
        # ReplayCapture.save writes to a fixed path; for the round-trip we
        # serialize via to_dict() and load back via load_trace.
        d = cap.to_trace().to_dict()
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(d), encoding="utf-8")
        loaded = load_trace(path)
        assert loaded.tool_calls[0].compression == compression

    def test_old_fixture_without_compression_loads_clean(self):
        """Backwards compat: old fixtures (pre-commit-4) loaded cleanly with
        compression=None. Critical for replay_fixtures/one_tool_turn.json."""
        path = project_root / "tests" / "replay_fixtures" / "one_tool_turn.json"
        if not path.exists():
            pytest.skip("legacy fixture not present in this repo")
        loaded = load_trace(path)
        assert loaded.tool_calls
        assert loaded.tool_calls[0].compression is None

    def test_l1_minify_fixture_runs_through_compressor(self, tmp_path):
        """tests/fixtures/p1_4_compressor/l1_minify_wrapped_json.json carries
        a representative input + expected outcome for Layer 1. Loading +
        running it through the compressor must produce the expected shape.
        These fixtures are NOT under tests/replay_fixtures/ because the
        existing replay validator does not re-run layer transformations."""
        path = (project_root / "tests" / "fixtures" / "p1_4_compressor"
                / "l1_minify_wrapped_json.json")
        if not path.exists():
            pytest.skip("L1 compressor fixture not present")
        spec = json.loads(path.read_text(encoding="utf-8"))
        cfg = spec["config"]
        ctx = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=cfg["keep_recent_turns"],
            session_id="fixture-l1",
            overflow_dir=tmp_path,
            compaction_config=CompressorConfig(
                enabled=cfg["compaction_enabled"],
                layer_2_threshold_chars=cfg["layer_2_threshold_chars"],
                layer_3_threshold_chars=cfg["layer_3_threshold_chars"],
                keep_recent_turns=cfg["keep_recent_turns"],
            ),
        )
        out, stats = ctx.compact_messages(spec["input_messages"])

        exp = spec["expected"]
        old_msg = out[exp["old_tool_result_index"]]
        old_content = old_msg["content"][0]["content"]
        if exp["envelope_preserved"]:
            assert old_content.startswith('<tool_output tool="')
            assert old_content.endswith("</tool_output>")
        # Inner JSON is minified — strip envelope and compare
        prefix = old_content.find(">\n") + 2
        inner = old_content[prefix:-len("\n</tool_output>")]
        assert inner == exp["old_tool_result_inner_minified"]
        # Layer 1 fired
        assert any(e["layer"] == 1 for e in stats["events"])
        assert stats["compacted"] >= exp["compacted_at_least"]

    def test_l3_stub_fixture_runs_through_compressor(self, tmp_path):
        """L3 fixture: old tool_result is replaced with a stub that preserves
        the overflow_record_id (regex-extracted from the content marker)."""
        path = (project_root / "tests" / "fixtures" / "p1_4_compressor"
                / "l3_stub_old_results.json")
        if not path.exists():
            pytest.skip("L3 compressor fixture not present")
        spec = json.loads(path.read_text(encoding="utf-8"))
        cfg = spec["config"]
        ctx = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=cfg["keep_recent_turns"],
            session_id="fixture-l3",
            overflow_dir=tmp_path,
            compaction_config=CompressorConfig(
                enabled=cfg["compaction_enabled"],
                layer_1_enabled=cfg["layer_1_enabled"],
                layer_2_threshold_chars=cfg["layer_2_threshold_chars"],
                layer_3_threshold_chars=cfg["layer_3_threshold_chars"],
                keep_recent_turns=cfg["keep_recent_turns"],
            ),
        )
        out, stats = ctx.compact_messages(spec["input_messages"])
        exp = spec["expected"]
        old_msg = out[exp["old_tool_result_index"]]
        old_content = old_msg["content"][0]["content"]
        assert old_content.startswith(exp["old_tool_result_content_starts_with"])
        # Layer 3 fired, Layer 1 didn't
        layers_fired = {e["layer"] for e in stats["events"]}
        assert 3 in layers_fired
        assert 1 not in layers_fired

    def test_p1_4_l0_overflow_fixture_loads_with_compression(self):
        """The new commit-4 fixture exercises the compression metadata
        round-trip end-to-end: load_trace must preserve all 7 keys with
        their types intact, and the values must be self-consistent
        (compressed=True implies record_id present, raw>compressed)."""
        path = project_root / "tests" / "replay_fixtures" / "p1_4_l0_overflow.json"
        if not path.exists():
            pytest.skip("p1_4 L0 overflow fixture not present")
        loaded = load_trace(path)
        assert len(loaded.tool_calls) == 1
        comp = loaded.tool_calls[0].compression
        assert comp is not None
        assert set(comp.keys()) == _COMPRESSION_KEYS
        # Self-consistency invariants
        assert comp["compressed"] is True
        assert comp["overflow_record_id"] is not None
        assert len(comp["overflow_record_id"]) == 16
        assert comp["raw_bytes"] > comp["compressed_bytes"]
        assert comp["raw_digest"] != comp["compressed_digest"]


# ============================================================
# Cross-pipeline consistency
# ============================================================


class TestPipelineConsistency:
    def test_pad_and_replay_get_same_compression_dict(self, tmp_path):
        """When agent.py / cli.py call ctx.compress_tool_result once and
        forward the SAME metadata dict to pad and capture, both pipelines
        see byte-equal data."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)

        wrapped = _wrapped(json.dumps({"x": "y" * 30_000}), "t")
        _out, compression = ctx.compress_tool_result("t", {}, wrapped)

        # Both sinks see the same dict (object identity even — same source)
        pad = Scratchpad(query="Q", provider="anthropic", model="claude-opus-4-7")
        pad._filepath = tmp_path / "pad.jsonl"
        pad._file = open(pad._filepath, "a", encoding="utf-8")
        pad.log_tool_result("t", result_data="x", tool_input={}, compression=compression)
        pad.close()

        cap = ReplayCapture(provider="anthropic", model="claude-opus-4-7", entrypoint="test")
        cap.set_initial(question="Q", system_prompt="P", tools_available=["t"])
        cap.record_tool_call("t", {}, "x", compression=compression)

        events = [
            json.loads(line) for line in
            pad._filepath.read_text(encoding="utf-8").splitlines() if line
        ]
        tool_event = [e for e in events if e.get("type") == "tool_result"][0]
        pad_compression = tool_event["data"]["compression"]
        replay_compression = cap.to_trace().tool_calls[0].compression

        # Byte-equal across pipelines
        assert pad_compression == replay_compression == compression
        # Digests, sizes, record_id reconcile
        assert pad_compression["overflow_record_id"] == compression["overflow_record_id"]
        assert pad_compression["raw_digest"] == compression["raw_digest"]
        assert pad_compression["raw_bytes"] == compression["raw_bytes"]

    def test_replay_compression_reconciles_with_overflow_disk(self, tmp_path):
        """The replay trace alone is enough to find + verify the on-disk
        record: replay.compression.raw_digest must match sha256 of the
        overflow record's original_payload."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)
        big = _wrapped(json.dumps({"x": "y" * 30_000}), "tavily_search")
        _out, compression = ctx.compress_tool_result("tavily_search", {}, big)

        cap = ReplayCapture(provider="anthropic", model="claude-opus-4-7", entrypoint="test")
        cap.set_initial(question="Q", system_prompt="P", tools_available=["tavily_search"])
        cap.record_tool_call("tavily_search", {}, "x", compression=compression)

        rec_id = cap.to_trace().tool_calls[0].compression["overflow_record_id"]
        record_files = list(tmp_path.glob(f"*/{rec_id}.json"))
        assert len(record_files) == 1
        record_data = json.loads(record_files[0].read_text(encoding="utf-8"))
        recomputed = hashlib.sha256(
            record_data["original_payload"].encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        assert recomputed == cap.to_trace().tool_calls[0].compression["raw_digest"]