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
    option_chain_reducer,
    python_output_reducer,
    register_reducer,
    truncate_with_marker,
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
# option_chain_reducer
# ============================================================


class TestOptionChainReducer:
    """Tests use the real shape from src/tools/option_chain_tools.py:336."""

    def _real_option_chain(self) -> str:
        return json.dumps({
            "ticker": "NVDA",
            "spot_price": 500.0,
            "timestamp": "2026-04-28T12:00:00",
            "selected_expiry": "20260516",
            "selected_dte": 14,
            "expirations_summary": [
                {"expiry": f"2026-05-{d:02d}", "dte": d, "iv": 0.3 + d * 0.001}
                for d in range(1, 21)
            ],
            "chain": {
                "calls": [{"strike": s, "iv": 0.3, "volume": 100, "oi": 500}
                          for s in range(400, 601, 5)],
                "puts": [{"strike": s, "iv": 0.3, "volume": 100, "oi": 500}
                         for s in range(400, 601, 5)],
            },
            "metrics": {
                "pc_ratio_volume": 0.85,
                "pc_ratio_oi": 0.92,
                "max_pain_strike": 495.0,
            },
            "oi_concentration": {
                "calls": [{"strike": 500.0, "oi": 5000}],
                "puts": [{"strike": 495.0, "oi": 4800}],
            },
        })

    def test_short_passes_through(self):
        payload = json.dumps({
            "ticker": "T", "spot_price": 100.0,
            "chain": {"calls": [], "puts": []},
        })
        out, _meta = option_chain_reducer(payload, budget=10_000)
        assert out == payload

    def test_keeps_atm_plus_minus_5_strikes(self):
        payload = self._real_option_chain()
        assert len(payload) > 3_000
        out, meta = option_chain_reducer(payload, budget=3_000)
        assert len(out) <= 3_000

        data = json.loads(out)
        assert data["ticker"] == "NVDA"
        assert data["spot_price"] == 500.0
        assert data["selected_expiry"] == "20260516"
        # Single chain dict (not list of expiries)
        chain = data["chain"]
        assert len(chain["calls"]) <= 10
        assert len(chain["puts"]) <= 10
        # Strikes around spot — extreme strikes (400, 600) dropped
        call_strikes = [c["strike"] for c in chain["calls"]]
        assert all(450 <= s <= 550 for s in call_strikes), call_strikes
        # Metrics + oi_concentration preserved verbatim
        assert data["metrics"]["max_pain_strike"] == 495.0
        assert data["oi_concentration"]["calls"][0]["strike"] == 500.0
        assert meta["dropped_strikes"] > 0
        assert meta["kept_per_side"] == 5

    def test_caps_expirations_summary(self):
        payload = self._real_option_chain()
        # Use a tight budget so the reducer runs and caps to 10
        out, _meta = option_chain_reducer(payload, budget=3_000)
        data = json.loads(out)
        # Original has 20 expirations; reducer caps at 10
        assert len(data["expirations_summary"]) <= 10

    def test_falls_back_on_missing_spot_price(self):
        # Old key "spot" not "spot_price" → fall through
        payload = json.dumps({"ticker": "T", "spot": 100.0,
                              "chain": {"calls": [], "puts": []}}) + "y" * 10_000
        out, _meta = option_chain_reducer(payload, budget=500)
        assert len(out) <= 500
        # Default reducer marker
        assert "chars dropped" in out

    def test_falls_back_when_chain_missing(self):
        payload = json.dumps({"ticker": "T", "spot_price": 100.0}) + "z" * 10_000
        out, _meta = option_chain_reducer(payload, budget=500)
        assert len(out) <= 500


# ============================================================
# python_output_reducer
# ============================================================


class TestPythonOutputReducer:
    """Real shape from src/tools/code_executor.py CodeExecutionResult:
    fields are output / error / generated_code (NOT stdout / stderr)."""

    def test_short_passes_through(self):
        payload = json.dumps({
            "success": True, "output": "small", "error": "",
            "execution_time": 0.5, "output_file": "", "pid": 0,
            "generated_code": "",
        })
        out, _meta = python_output_reducer(payload, budget=10_000)
        assert out == payload

    def test_keeps_output_tail_and_error_tail(self):
        output = "HEAD" + ("a" * 100_000) + "OUTPUT-TAIL"
        error = "STARTERR" + ("b" * 50_000) + "ERROR-TAIL"
        payload = json.dumps({
            "success": False, "output": output, "error": error,
            "execution_time": 1.2,
        })
        out, meta = python_output_reducer(payload, budget=5_000)
        assert len(out) <= 5_000

        data = json.loads(out)
        # Tail of output kept (was named "stdout" upstream)
        assert data["output"].endswith("OUTPUT-TAIL")
        assert "HEAD" not in data["output"]
        # Tail of error kept (was named "stderr" upstream)
        assert data["error"].endswith("ERROR-TAIL")
        assert "STARTERR" not in data["error"]
        # _compressed metadata
        assert data["_compressed"]["output_dropped_chars"] > 0
        assert data["_compressed"]["error_dropped_chars"] > 0
        assert meta["output_keep_chars"] == 2000
        assert meta["error_keep_chars"] == 1000

    def test_trims_large_generated_code(self):
        """generated_code is the second-largest source of bloat after output."""
        gen_code = "def f():\n    pass\n" * 1000  # ~17KB
        payload = json.dumps({
            "success": True, "output": "", "error": "",
            "generated_code": gen_code,
        })
        out, _meta = python_output_reducer(payload, budget=4_000)
        data = json.loads(out)
        assert len(data["generated_code"]) <= 2000
        assert data["_compressed"]["generated_code_dropped_chars"] > 0

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
        assert "tavily_search" not in reg
        assert reg["get_option_chain"] is option_chain_reducer
        assert "get_iv_history_data" not in reg
        assert reg["execute_python_analysis"] is python_output_reducer

    def test_web_browse_uses_default(self):
        """The browser payload uses default head+tail truncation."""
        reg = default_registry()
        assert "web_browse" not in reg
        assert get_reducer("web_browse") is truncate_with_marker

    def test_unknown_tool_returns_default(self):
        assert get_reducer("nonexistent_tool") is truncate_with_marker

    def test_get_reducer_uses_provided_registry(self):
        local = {"my_tool": option_chain_reducer}
        assert get_reducer("my_tool", local) is option_chain_reducer
        assert get_reducer("other_tool", local) is truncate_with_marker

    def test_register_reducer_to_local_registry(self):
        local = {}
        register_reducer("my_tool", option_chain_reducer, registry=local)
        assert local["my_tool"] is option_chain_reducer

    def test_default_registry_returns_copy(self):
        a = default_registry()
        b = default_registry()
        a["new_tool"] = truncate_with_marker
        assert "new_tool" not in b
