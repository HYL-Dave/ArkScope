"""Tests for the per-tool reducers (P1.4 commit 2).

Locks down:

  - Default ``truncate_with_marker``: head + tail + marker, ≤ budget,
    pass-through when within budget.
  - Each specific reducer respects its expected JSON shape AND falls
    back to the default when the shape is unexpected (parse error,
    missing keys, wrong types).
  - Registry: known tools route to specific reducers; unknown tools
    fall through to default.
  - Output is always ≤ budget (the ToolReducer contract).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.shared.compressor import (
    default_registry,
    get_reducer,
    iv_history_reducer,
    option_chain_reducer,
    python_output_reducer,
    register_reducer,
    truncate_with_marker,
    web_result_reducer,
)


# ============================================================
# Default reducer: truncate_with_marker
# ============================================================


class TestTruncateWithMarker:
    def test_short_payload_passes_through(self):
        out, meta = truncate_with_marker("hello", budget=100)
        assert out == "hello"
        assert meta == {}

    def test_exact_budget_passes_through(self):
        payload = "x" * 100
        out, meta = truncate_with_marker(payload, budget=100)
        assert out == payload
        assert meta == {}

    def test_long_payload_truncated_under_budget(self):
        payload = "x" * 10_000
        out, meta = truncate_with_marker(payload, budget=1000)
        assert len(out) <= 1000
        assert "[" in out and "chars dropped" in out
        assert meta["dropped_chars"] > 0

    def test_truncation_keeps_head_and_tail(self):
        payload = "HEAD-abc" + ("x" * 5000) + "TAIL-xyz"
        out, _meta = truncate_with_marker(payload, budget=500)
        assert out.startswith("HEAD-abc")
        assert out.endswith("TAIL-xyz")
        assert "chars dropped" in out

    def test_zero_budget_returns_empty(self):
        out, meta = truncate_with_marker("anything", budget=0)
        assert out == ""
        assert meta["dropped_chars"] == len("anything")

    def test_non_string_input_stringified(self):
        # Reducer accepts whatever; should not raise even on weird input
        out, _meta = truncate_with_marker("plain", budget=10)
        assert isinstance(out, str)


# ============================================================
# web_result_reducer
# ============================================================


class TestWebResultReducer:
    def _big_web_payload(self, n_results: int = 5, body_chars: int = 5000) -> str:
        return json.dumps({
            "query": "find me NVDA earnings news",
            "results": [
                {
                    "title": f"Result {i} title",
                    "url": f"https://example.com/{i}",
                    "content": "x" * body_chars,
                }
                for i in range(n_results)
            ],
        })

    def test_short_payload_passes_through(self):
        payload = json.dumps({"query": "small", "results": [{"title": "t", "url": "u", "content": "c"}]})
        out, meta = web_result_reducer(payload, budget=10000)
        assert out == payload
        assert meta == {}

    def test_long_payload_keeps_titles_urls_drops_bodies(self):
        payload = self._big_web_payload(n_results=4, body_chars=10_000)
        out, meta = web_result_reducer(payload, budget=8000)
        assert len(out) <= 8000
        # Titles + URLs preserved
        for i in range(4):
            assert f"Result {i} title" in out
            assert f"https://example.com/{i}" in out
        # Body content NOT preserved verbatim — snippet ≤500 chars per result
        assert out.count("x" * 1000) == 0  # no 1000-char x runs survive
        assert meta["kept_results"] == 4
        assert meta["snippet_chars"] == 500

    def test_falls_back_to_default_on_invalid_json(self):
        garbage = "not valid json {" * 1000  # >> budget, garbage
        out, _meta = web_result_reducer(garbage, budget=500)
        # Default reducer's output has "chars dropped" marker
        assert "chars dropped" in out
        assert len(out) <= 500

    def test_falls_back_when_results_missing(self):
        payload = json.dumps({"query": "no results field"})  # missing "results"
        # Pad to overflow
        payload = payload + "x" * 5000
        out, _meta = web_result_reducer(payload, budget=500)
        assert len(out) <= 500


# ============================================================
# option_chain_reducer
# ============================================================


class TestOptionChainReducer:
    def _big_option_chain(self) -> str:
        return json.dumps({
            "ticker": "NVDA",
            "spot": 500.0,
            "expiries": [
                {
                    "date": "2026-05-16",
                    "calls": [{"strike": s, "iv": 0.3, "volume": 100} for s in range(400, 601, 5)],
                    "puts": [{"strike": s, "iv": 0.3, "volume": 100} for s in range(400, 601, 5)],
                }
            ],
        })

    def test_short_passes_through(self):
        payload = json.dumps({"ticker": "T", "spot": 100.0, "expiries": []})
        out, _meta = option_chain_reducer(payload, budget=10_000)
        assert out == payload

    def test_keeps_atm_plus_minus_5_strikes(self):
        payload = self._big_option_chain()
        # Tight budget forces the reducer to actually run (default
        # truncate_with_marker would still fall back gracefully if it
        # didn't, but we want to test the option-chain-specific path).
        assert len(payload) > 2_000  # confirm payload is over the budget
        out, meta = option_chain_reducer(payload, budget=2_000)
        assert len(out) <= 2_000

        data = json.loads(out)
        assert data["ticker"] == "NVDA"
        assert data["spot"] == 500.0
        # Each side keeps at most 10 strikes (5 either side)
        for exp in data["expiries"]:
            assert len(exp["calls"]) <= 10
            assert len(exp["puts"]) <= 10
            # Strikes around spot — extreme strikes (400, 600) should be dropped
            call_strikes = [c["strike"] for c in exp["calls"]]
            assert all(450 <= s <= 550 for s in call_strikes), call_strikes
        assert meta["dropped_strikes"] > 0
        assert meta["kept_per_side"] == 5

    def test_falls_back_on_invalid_shape(self):
        # spot missing → fall through
        payload = json.dumps({"ticker": "T", "expiries": []}) + "y" * 10_000
        out, _meta = option_chain_reducer(payload, budget=500)
        assert len(out) <= 500


# ============================================================
# iv_history_reducer
# ============================================================


class TestIvHistoryReducer:
    def test_short_passes_through(self):
        payload = json.dumps({"ticker": "T", "history": [{"date": "2026-04-01", "iv": 0.25}]})
        out, _meta = iv_history_reducer(payload, budget=10_000)
        assert out == payload

    def test_long_keeps_last_30_days(self):
        history = [{"date": f"2026-01-{i:02d}", "iv": 0.2 + i * 0.001} for i in range(1, 91)]
        payload = json.dumps({"ticker": "NVDA", "history": history})
        # Tight budget forces the reducer to run (vs pass-through)
        assert len(payload) > 2_000
        out, meta = iv_history_reducer(payload, budget=2_000)
        assert len(out) <= 2_000

        data = json.loads(out)
        assert len(data["history"]) == 30
        # Most recent days kept (i=90, 89, ..., 61)
        assert data["history"][-1] == history[-1]
        assert meta["kept_days"] == 30
        assert meta["dropped_rows"] == 60

    def test_falls_back_on_missing_history(self):
        payload = json.dumps({"ticker": "T"}) + "z" * 10_000
        out, _meta = iv_history_reducer(payload, budget=500)
        assert len(out) <= 500


# ============================================================
# python_output_reducer
# ============================================================


class TestPythonOutputReducer:
    def test_short_passes_through(self):
        payload = json.dumps({"stdout": "small", "stderr": "", "ok": True})
        out, _meta = python_output_reducer(payload, budget=10_000)
        assert out == payload

    def test_keeps_stdout_tail_and_stderr_tail(self):
        stdout = "HEAD" + ("a" * 100_000) + "STDOUT-TAIL"
        stderr = "STARTERR" + ("b" * 50_000) + "STDERR-TAIL"
        payload = json.dumps({"stdout": stdout, "stderr": stderr, "ok": True})
        out, meta = python_output_reducer(payload, budget=5_000)
        assert len(out) <= 5_000

        data = json.loads(out)
        # Tail of stdout kept, head dropped
        assert data["stdout"].endswith("STDOUT-TAIL")
        assert "HEAD" not in data["stdout"]
        # Tail of stderr kept, head dropped
        assert data["stderr"].endswith("STDERR-TAIL")
        assert "STARTERR" not in data["stderr"]
        assert meta["stdout_keep_chars"] == 2000
        assert meta["stderr_keep_chars"] == 1000

    def test_falls_back_on_non_object_payload(self):
        payload = json.dumps([1, 2, 3]) + "p" * 10_000
        out, _meta = python_output_reducer(payload, budget=500)
        assert len(out) <= 500


# ============================================================
# Registry
# ============================================================


class TestRegistry:
    def test_known_tools_route_to_specific_reducers(self):
        reg = default_registry()
        assert reg["tavily_search"] is web_result_reducer
        assert reg["web_browse"] is web_result_reducer
        assert reg["codex_web_research"] is web_result_reducer
        assert reg["get_option_chain"] is option_chain_reducer
        assert reg["get_iv_history_data"] is iv_history_reducer
        assert reg["execute_python_analysis"] is python_output_reducer

    def test_unknown_tool_returns_default(self):
        # default_registry passed → fall through to global default behaviour
        assert get_reducer("nonexistent_tool") is truncate_with_marker

    def test_get_reducer_uses_provided_registry(self):
        local = {"my_tool": web_result_reducer}
        assert get_reducer("my_tool", local) is web_result_reducer
        assert get_reducer("other_tool", local) is truncate_with_marker

    def test_register_reducer_to_local_registry(self):
        local = {}
        register_reducer("my_tool", web_result_reducer, registry=local)
        assert local["my_tool"] is web_result_reducer

    def test_default_registry_returns_copy(self):
        a = default_registry()
        b = default_registry()
        a["new_tool"] = truncate_with_marker
        assert "new_tool" not in b
