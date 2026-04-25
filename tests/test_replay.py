"""Tests for the replay harness (P0.1 minimal-spike).

Coverage:
  - schema helpers (hash, digest, shape, normalize)
  - ReplayCapture lifecycle + on-disk fixture round-trip
  - load_trace input validation
  - validate_trace_against_registry: pass / unknown-tool / unknown-arg / missing-required
  - env-flag gating (capture is no-op when disabled)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.agents.shared.replay import (
    DIGEST_LEN,
    ENV_FLAG,
    SCHEMA_VERSION,
    CapturedToolCall,
    ReplayCapture,
    ValidationResult,
    compute_shape,
    digest_json,
    hash_text,
    is_capture_enabled,
    load_trace,
    normalize_args,
    validate_trace_against_registry,
)

FIXTURE_DIR = Path(__file__).parent / "replay_fixtures"
NO_TOOL_FIXTURE = FIXTURE_DIR / "no_tool_turn.json"
ONE_TOOL_FIXTURE = FIXTURE_DIR / "one_tool_turn.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_hash_text_stable_and_short():
    h1 = hash_text("hello")
    h2 = hash_text("hello")
    h3 = hash_text("world")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == DIGEST_LEN


def test_digest_json_sort_invariance():
    # Same logical dict, different insertion order → same digest.
    a = {"ticker": "NVDA", "days": 7}
    b = {"days": 7, "ticker": "NVDA"}
    assert digest_json(a) == digest_json(b)


def test_digest_json_handles_non_serializable():
    # default=str fallback should not crash on, e.g., a set
    d = digest_json({"x": {1, 2, 3}})
    assert isinstance(d, str) and len(d) == DIGEST_LEN


def test_compute_shape_basic_types():
    assert compute_shape("hello") == "str"
    assert compute_shape(42) == "int"
    assert compute_shape(3.14) == "float"
    assert compute_shape(True) == "bool"
    assert compute_shape(None) == "NoneType"


def test_compute_shape_dict_and_list():
    shape = compute_shape({"ticker": "NVDA", "count": 3, "items": [{"a": 1}]})
    assert shape == {
        "ticker": "str",
        "count": "int",
        "items": [{"a": "int"}],
    }


def test_compute_shape_empty_list():
    assert compute_shape([]) == []


def test_compute_shape_depth_capped():
    deep = {"a": {"b": {"c": {"d": {"e": "leaf"}}}}}
    shape = compute_shape(deep)
    # At max depth (4) anything deeper collapses to "..."
    assert shape["a"]["b"]["c"]["d"] == "..."


def test_normalize_args_sorts_keys():
    a = normalize_args({"b": 2, "a": 1, "c": 3})
    assert list(a.keys()) == ["a", "b", "c"]


def test_normalize_args_wraps_non_dict():
    assert normalize_args("raw_string") == {"_raw": "raw_string"}
    assert normalize_args(None) == {"_raw": None}


# ---------------------------------------------------------------------------
# Env flag gating
# ---------------------------------------------------------------------------


def test_is_capture_enabled_default_false(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    assert is_capture_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", "ON", "True"])
def test_is_capture_enabled_truthy(monkeypatch, val):
    monkeypatch.setenv(ENV_FLAG, val)
    assert is_capture_enabled() is True


@pytest.mark.parametrize("val", ["", "0", "false", "no", "off"])
def test_is_capture_enabled_falsy(monkeypatch, val):
    monkeypatch.setenv(ENV_FLAG, val)
    assert is_capture_enabled() is False


# ---------------------------------------------------------------------------
# Capture lifecycle + round-trip
# ---------------------------------------------------------------------------


def test_capture_save_and_reload(tmp_path):
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial(
        question="What is 2+2?",
        system_prompt="You are a helpful assistant.",
        tools_available=["get_ticker_news", "get_news_brief"],
    )
    cap.record_tool_call(
        name="get_ticker_news",
        arguments={"ticker": "NVDA", "days": 7},
        result='{"ticker": "NVDA", "articles": [], "count": 0}',
    )
    cap.record_final("Four.", {"input_tokens": 10, "output_tokens": 1})

    path = cap.save()
    assert path.exists()
    assert path.parent.parent == tmp_path  # nested under session_id dir

    trace = load_trace(path)
    assert trace.schema_version == SCHEMA_VERSION
    assert trace.user_input == "What is 2+2?"
    assert trace.provider == "anthropic"
    assert trace.tools_available == ["get_news_brief", "get_ticker_news"]  # sorted
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "get_ticker_news"
    assert call.arguments == {"days": 7, "ticker": "NVDA"}  # sorted
    assert call.result_shape == {"ticker": "str", "articles": [], "count": "int"}


def test_capture_records_no_tool_turns(tmp_path):
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial("hi", "system prompt", ["get_ticker_news"])
    cap.record_final("hello", {})
    path = cap.save()
    trace = load_trace(path)
    assert trace.tool_calls == []


# ---------------------------------------------------------------------------
# load_trace validation
# ---------------------------------------------------------------------------


def test_load_trace_rejects_unknown_schema_version(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 99}))
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        load_trace(bad)


def test_load_trace_rejects_missing_fields(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 1}))
    with pytest.raises(ValueError, match="missing required fields"):
        load_trace(bad)


def test_load_trace_rejects_non_object(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([]))
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_trace(bad)


def test_load_trace_loads_real_fixtures():
    no_tool = load_trace(NO_TOOL_FIXTURE)
    assert no_tool.tool_calls == []
    assert no_tool.user_input.startswith("What is")

    one_tool = load_trace(ONE_TOOL_FIXTURE)
    assert len(one_tool.tool_calls) == 1
    assert one_tool.tool_calls[0].name == "get_ticker_news"


# ---------------------------------------------------------------------------
# Validation against registry
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_registry():
    from src.tools.registry import create_default_registry
    return create_default_registry()


def test_validate_no_tool_fixture_passes(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert isinstance(result, ValidationResult)
    assert result.passed is True
    assert result.errors == []


def test_validate_one_tool_fixture_passes(real_registry):
    trace = load_trace(ONE_TOOL_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is True, result.render()


def test_validate_flags_unknown_tool(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    trace.tool_calls = [
        CapturedToolCall(
            index=0,
            name="this_tool_does_not_exist",
            arguments={"x": 1},
            arguments_digest="x",
            result_digest="x",
            result_shape={},
        )
    ]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("this_tool_does_not_exist" in e for e in result.errors)


def test_validate_flags_unknown_argument(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    trace.tool_calls = [
        CapturedToolCall(
            index=0,
            name="get_ticker_news",
            arguments={"ticker": "NVDA", "obsolete_arg": True},
            arguments_digest="x",
            result_digest="x",
            result_shape={},
        )
    ]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("obsolete_arg" in e for e in result.errors)


def test_validate_flags_missing_required_argument(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    # ticker is required for get_ticker_news; omit it
    trace.tool_calls = [
        CapturedToolCall(
            index=0,
            name="get_ticker_news",
            arguments={"days": 7},
            arguments_digest="x",
            result_digest="x",
            result_shape={},
        )
    ]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("ticker" in e for e in result.errors)


def test_validate_warns_on_prompt_drift(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    result = validate_trace_against_registry(
        trace, real_registry, current_system_prompt="totally different prompt text"
    )
    # Hash will not match the fixture's placeholder zeros
    assert any("system_prompt_hash drift" in w for w in result.warnings)
    # Drift is a warning only, not a failure
    assert result.passed is True


def test_validate_warns_on_registry_diff(real_registry):
    trace = load_trace(NO_TOOL_FIXTURE)
    # Capture claimed only 2 tools; current registry has many more → "added"
    result = validate_trace_against_registry(trace, real_registry)
    assert any("newly registered" in w for w in result.warnings)