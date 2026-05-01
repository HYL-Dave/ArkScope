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
    _SERVER_TOOL_KINDS_BY_PROVIDER,
    _canonical_tool_name,
    _currently_wired_server_tools,
    _size_class,
    classify_attachments,
    compute_shape,
    digest_bytes,
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
# P0.1 full-v1 commit 2 fixtures
OPENAI_NO_TOOL_FIXTURE = FIXTURE_DIR / "openai_no_tool_turn.json"
OPENAI_ONE_TOOL_FIXTURE = FIXTURE_DIR / "openai_one_tool_turn.json"
ATTACHMENT_FIXTURE = FIXTURE_DIR / "attachment_turn.json"
SUBAGENT_FIXTURE = FIXTURE_DIR / "subagent_turn.json"


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


# ---------------------------------------------------------------------------
# P0.1 full-v1 commit 1: tool-name canonicalization
# ---------------------------------------------------------------------------


def test_canonical_tool_name_strips_openai_bridge_prefix():
    # OpenAI bridge functions are registered as ``tool_<canonical>``.
    assert _canonical_tool_name("tool_get_ticker_news") == "get_ticker_news"
    assert _canonical_tool_name("tool_get_news_brief") == "get_news_brief"


def test_canonical_tool_name_idempotent_and_safe():
    # Anthropic / canonical names are pass-through.
    assert _canonical_tool_name("get_ticker_news") == "get_ticker_news"
    # Idempotent — applying twice yields the same result.
    once = _canonical_tool_name("tool_foo")
    assert _canonical_tool_name(once) == once
    # Non-string input must not raise.
    assert _canonical_tool_name(None) == ""  # type: ignore[arg-type]
    assert _canonical_tool_name(123) == ""  # type: ignore[arg-type]
    # Empty string stays empty (no spurious prefix strip).
    assert _canonical_tool_name("") == ""


def test_provider_tool_name_round_trips_through_save_and_load(tmp_path):
    cap = ReplayCapture(
        provider="openai",
        model="gpt-5.4",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial(
        question="news on NVDA",
        system_prompt="You are an assistant.",
        tools_available=["get_ticker_news"],
    )
    cap.record_tool_call(
        name="get_ticker_news",
        arguments={"ticker": "NVDA"},
        result='{"ticker": "NVDA", "articles": []}',
        provider_tool_name="tool_get_ticker_news",
    )
    cap.record_final("done", {})
    path = cap.save()

    trace = load_trace(path)
    call = trace.tool_calls[0]
    assert call.name == "get_ticker_news"  # canonical persisted as primary name
    assert call.provider_tool_name == "tool_get_ticker_news"  # bridge name preserved


def test_provider_tool_name_optional_for_anthropic_path(tmp_path):
    # Anthropic regular tools never set ``provider_tool_name`` — confirm
    # the field stays ``None`` (forward-compat through load_trace).
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    cap.set_initial("q", "sys", ["get_ticker_news"])
    cap.record_tool_call(
        name="get_ticker_news",
        arguments={"ticker": "NVDA"},
        result="{}",
    )
    cap.record_final("ok", {})
    trace = load_trace(cap.save())
    assert trace.tool_calls[0].provider_tool_name is None


# ---------------------------------------------------------------------------
# P0.1 full-v1 commit 1: server-tool namespacing + introspection
# ---------------------------------------------------------------------------


def _make_server_trace(provider: str, kinds: list) -> Any:
    """Helper: synthesize a minimal trace claiming the given server tools."""
    base = load_trace(NO_TOOL_FIXTURE)
    base.provider = provider
    base.tools_available = kinds + ["get_ticker_news"]  # mix server + registry
    base.tool_calls = []
    return base


def test_validate_accepts_server_web_search_for_anthropic(real_registry):
    trace = _make_server_trace("anthropic", ["server:web_search"])
    result = validate_trace_against_registry(trace, real_registry)
    # Anthropic agent module currently wires _CLAUDE_WEB_SEARCH_TOOL → passes.
    assert result.passed is True, result.render()
    # No "server tool no longer wired" error.
    assert not any("server tool" in e for e in result.errors)


def test_validate_rejects_server_when_shared_helper_returns_empty(
    real_registry, monkeypatch,
):
    """If the shared source-of-truth (``anthropic_server_tools``) ever
    yields an empty list — e.g. Phase C drops the helper or moves
    hosted-tool wiring elsewhere — the validator must treat fixtures
    claiming ``server:web_search`` as a regression."""
    from src.agents.shared import server_tools as st
    monkeypatch.setattr(st, "anthropic_server_tools", lambda _config: [])

    trace = _make_server_trace("anthropic", ["server:web_search"])
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any("server tool" in e and "web_search" in e for e in result.errors)


def test_currently_wired_server_tools_unknown_provider_empty():
    # Defensive: unknown provider name must return empty set (no crash).
    assert _currently_wired_server_tools("vertex") == set()
    assert _currently_wired_server_tools("") == set()


def test_currently_wired_server_tools_reads_from_shared_source_of_truth(
    monkeypatch,
):
    """Sentinel test: ``_currently_wired_server_tools`` MUST consult
    ``server_tools.all_kinds_for_provider`` — not re-implement the
    introspection. Stubbing the shared module to return a sentinel kind
    must propagate to the validator."""
    sentinel = "server:test_only_sentinel_v1"
    from src.agents.shared import server_tools as st
    monkeypatch.setattr(
        st, "all_kinds_for_provider", lambda _p: {sentinel},
    )
    assert sentinel in _currently_wired_server_tools("anthropic")
    assert sentinel in _currently_wired_server_tools("openai")


def test_server_tool_mapping_forward_anthropic_constant_in_mapping():
    """Forward safeguard for the CAPTURE walker (not the validator):
    the live Anthropic web-search constant's ``type`` value must remain
    a key in ``_SERVER_TOOL_KINDS_BY_PROVIDER`` so capture-time tooling
    that walks ``tools=[]`` can still label a hosted tool as
    ``server:<kind>``. Validator's source of truth is now the shared
    ``server_tools`` helpers — this mapping survives only for the
    capture-side normalisation."""
    from src.agents.anthropic_agent.agent import _CLAUDE_WEB_SEARCH_TOOL
    raw_type = _CLAUDE_WEB_SEARCH_TOOL.get("type")
    assert raw_type, "_CLAUDE_WEB_SEARCH_TOOL must declare a 'type' key"
    assert raw_type in _SERVER_TOOL_KINDS_BY_PROVIDER["anthropic"], (
        f"Anthropic _CLAUDE_WEB_SEARCH_TOOL['type']={raw_type!r} drifted "
        f"out of sync with _SERVER_TOOL_KINDS_BY_PROVIDER['anthropic']"
    )


def test_server_tool_mapping_forward_openai_websearchtool_class_name():
    """Forward safeguard for the OpenAI capture walker
    (``_replay_tools_available_openai``): the SDK class name of
    ``WebSearchTool`` must remain a key in the OpenAI mapping. Catches
    SDK renames before capture-time labelling silently breaks."""
    pytest.importorskip("agents")
    from agents import WebSearchTool
    cls_name = WebSearchTool.__name__
    assert cls_name in _SERVER_TOOL_KINDS_BY_PROVIDER["openai"], (
        f"agents.WebSearchTool.__name__={cls_name!r} drifted out of sync "
        f"with _SERVER_TOOL_KINDS_BY_PROVIDER['openai']"
    )


# ---------------------------------------------------------------------------
# Sentinel safeguards: wiring MUST go through shared/server_tools.py
# ---------------------------------------------------------------------------


def test_anthropic_wiring_actually_uses_anthropic_server_tools(monkeypatch):
    """White-box safeguard: ``_build_anthropic_tools_list`` must
    physically iterate ``anthropic_server_tools(config)``'s output.

    Replaces the helper with a stub that returns a sentinel tool_def;
    if the wiring bypasses the helper (e.g. Phase C inlines
    ``_CLAUDE_WEB_SEARCH_TOOL``), the sentinel never reaches the
    returned tools list and this test fails."""
    sentinel_tool_def = {
        "type": "test_sentinel_tool_v1",
        "name": "sentinel",
    }

    def fake_helper(_config):
        return [("server:test_sentinel", sentinel_tool_def)]

    from src.agents.anthropic_agent import agent as a_mod
    monkeypatch.setattr(a_mod, "anthropic_server_tools", fake_helper)

    from types import SimpleNamespace
    config = SimpleNamespace(web_claude_search=True, web_claude_max_uses=5)
    tools_list = a_mod._build_anthropic_tools_list(config)

    assert sentinel_tool_def in tools_list, (
        "_build_anthropic_tools_list bypassed anthropic_server_tools — "
        "Phase C may have inlined hosted-tool wiring without going "
        "through the shared single source of truth."
    )


def test_anthropic_wiring_omits_hosted_when_flag_off():
    """Smoke test: with ``web_claude_search=False``, no hosted tool
    descriptor reaches the tools list. The list still contains regular
    registry tools (sanity that we didn't accidentally wipe them)."""
    from src.agents.anthropic_agent.agent import _build_anthropic_tools_list

    from types import SimpleNamespace
    config = SimpleNamespace(web_claude_search=False, web_claude_max_uses=5)
    tools_list = _build_anthropic_tools_list(config)

    assert len(tools_list) > 0
    # No hosted web_search descriptor present
    assert not any(
        isinstance(t, dict) and str(t.get("type", "")).startswith("web_search_")
        for t in tools_list
    )


def test_openai_wiring_actually_uses_openai_server_tools(monkeypatch):
    """White-box safeguard: ``_build_openai_all_tools`` must physically
    iterate ``openai_server_tools(config)``'s output. Stubbed sentinel
    must round-trip to the returned list."""

    class SentinelTool:
        pass

    sentinel_obj = SentinelTool()

    def fake_helper(_config):
        return [("server:test_sentinel", sentinel_obj)]

    from src.agents.openai_agent import agent as oa_mod
    monkeypatch.setattr(oa_mod, "openai_server_tools", fake_helper)

    from types import SimpleNamespace
    config = SimpleNamespace(web_openai_search=True)
    out = oa_mod._build_openai_all_tools([], config)

    assert sentinel_obj in out, (
        "_build_openai_all_tools bypassed openai_server_tools — "
        "Phase C may have inlined hosted-tool wiring without going "
        "through the shared single source of truth."
    )


def test_openai_wiring_omits_hosted_when_flag_off():
    from src.agents.openai_agent.agent import _build_openai_all_tools

    from types import SimpleNamespace
    config = SimpleNamespace(web_openai_search=False)
    base = ["dummy_a", "dummy_b"]
    out = _build_openai_all_tools(base, config)

    # Only base tools survive — no hosted appendage.
    assert out == base


def _file_references_target(py_path, target: str) -> bool:
    """Return True iff ``py_path`` imports or references ``target``.

    AST-based: catches three shapes — ``ImportFrom`` (``from x import target``),
    bare ``Name`` (``x = target``), and ``Attribute`` access
    (``a_mod.target``). Comments / docstrings mentioning the name are
    NOT flagged because they parse to ``ast.Constant`` strings.

    Returns False on read errors or syntax errors (best-effort scan;
    the architectural test still passes when an unrelated file is
    transiently broken).
    """
    import ast
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == target for alias in node.names):
                return True
        if isinstance(node, ast.Name) and node.id == target:
            return True
        if isinstance(node, ast.Attribute) and node.attr == target:
            return True
    return False


def test_claude_web_search_constant_only_imported_via_helper():
    """Architectural safeguard: ``_CLAUDE_WEB_SEARCH_TOOL`` is owned by
    ``anthropic_agent/agent.py`` and consumed by ``shared/server_tools.py``.
    Every other Anthropic wiring path (cli, subagent, future runners)
    MUST route through ``anthropic_server_tools(config)`` instead of
    importing the constant directly.

    This test pins single-source-of-truth across CLI / API / subagent —
    the sentinel-based wiring tests above only cover the API builders,
    so this AST scan acts as the architectural backstop. If a new path
    needs hosted tools, it imports the helper, not the constant.

    Uses AST so comments / docstrings mentioning the constant by name
    don't trigger a false positive — only actual import statements do.
    """
    from pathlib import Path

    repo_root = Path(__file__).parent.parent
    src_root = repo_root / "src" / "agents"

    target = "_CLAUDE_WEB_SEARCH_TOOL"
    allowed = {
        (src_root / "anthropic_agent" / "agent.py").resolve(),  # owns it
        (src_root / "shared" / "server_tools.py").resolve(),    # consumer
    }

    offenders: list[str] = []
    for py_file in src_root.rglob("*.py"):
        if py_file.resolve() in allowed:
            continue
        if _file_references_target(py_file, target):
            offenders.append(str(py_file.relative_to(repo_root)))

    assert not offenders, (
        f"Modules importing or referencing {target} outside the "
        f"single-source-of-truth path: {offenders}. Use "
        f"`from src.agents.shared.server_tools import anthropic_server_tools` "
        f"and iterate the (kind, tool_def) pairs instead."
    )


def test_guard_helper_detects_each_bypass_shape(tmp_path):
    """Lock the guard's behaviour against synthetic bypass shapes —
    ensures all three AST branches (ImportFrom / Name / Attribute) stay
    wired. If a future refactor accidentally removes a branch,
    ``_file_references_target`` would return False here and this test
    fails before the architectural scan can silently pass.
    """
    target = "_CLAUDE_WEB_SEARCH_TOOL"

    # 1. ImportFrom — direct import of the constant.
    f_import = tmp_path / "via_import_from.py"
    f_import.write_text(f"from x.y import {target}\n")
    assert _file_references_target(f_import, target), (
        "Guard missed ImportFrom — `from x.y import _CLAUDE_WEB_SEARCH_TOOL`"
    )

    # 2. Bare Name — the symbol used as a value (e.g. via a star import
    #    or after being bound elsewhere in the same module).
    f_name = tmp_path / "via_bare_name.py"
    f_name.write_text(f"def f():\n    return {target}\n")
    assert _file_references_target(f_name, target), (
        "Guard missed bare Name — `return _CLAUDE_WEB_SEARCH_TOOL`"
    )

    # 3. Attribute access — `a_mod._CLAUDE_WEB_SEARCH_TOOL` after
    #    importing the module. This is the bypass shape the original
    #    AST guard missed (Low review finding).
    f_attr = tmp_path / "via_attribute.py"
    f_attr.write_text(
        "from src.agents.anthropic_agent import agent as a_mod\n"
        f"def f():\n    return a_mod.{target}\n"
    )
    assert _file_references_target(f_attr, target), (
        "Guard missed Attribute — `a_mod._CLAUDE_WEB_SEARCH_TOOL`"
    )

    # 4. Negative control — a comment or docstring mentioning the name
    #    must NOT be flagged (we'd lose code-review-friendly
    #    documentation referring to the constant by name).
    f_comment = tmp_path / "comment_only.py"
    f_comment.write_text(
        f'"""Docstring mentions {target} as documentation."""\n'
        f"# Comment also mentions {target}\n"
        "x = 1\n"
    )
    assert not _file_references_target(f_comment, target), (
        "Guard false-positive on comment / docstring mention"
    )


# ---------------------------------------------------------------------------
# P0.1 full-v1 commit 2: opt-in trace fields + classifier + new fixtures
# ---------------------------------------------------------------------------


def test_existing_fixtures_load_with_new_fields_as_none():
    """Forward-compatibility: the 3 fixtures captured before commit 2's
    new schema fields must still load, with all opt-in fields == None.
    Catches a regression where ``load_trace`` would require the new
    keys instead of defaulting them."""
    for path in (NO_TOOL_FIXTURE, ONE_TOOL_FIXTURE, FIXTURE_DIR / "p1_4_l0_overflow.json"):
        trace = load_trace(path)
        assert trace.subagent_traces is None, f"{path}: subagent_traces should default None"
        assert trace.pinned_tool_names is None, f"{path}: pinned_tool_names should default None"
        assert trace.attachments_shape is None, f"{path}: attachments_shape should default None"


def test_load_openai_no_tool_fixture():
    trace = load_trace(OPENAI_NO_TOOL_FIXTURE)
    assert trace.provider == "openai"
    assert trace.tool_calls == []
    assert trace.subagent_traces is None
    assert trace.pinned_tool_names is None
    assert trace.attachments_shape is None


def test_load_openai_one_tool_fixture():
    trace = load_trace(OPENAI_ONE_TOOL_FIXTURE)
    assert trace.provider == "openai"
    assert len(trace.tool_calls) == 1
    call = trace.tool_calls[0]
    assert call.name == "get_ticker_news"
    # provider_tool_name preserves the OpenAI bridge prefix
    assert call.provider_tool_name == "tool_get_ticker_news"
    # pinned_tool_names locks only the tool the fixture's behaviour depends on
    assert trace.pinned_tool_names == ["get_ticker_news"]


def test_load_attachment_fixture_carries_shape():
    trace = load_trace(ATTACHMENT_FIXTURE)
    assert trace.attachments_shape is not None
    assert len(trace.attachments_shape) == 2
    pdf, img = trace.attachments_shape
    # Provider-native block kinds match what to_anthropic_blocks emits.
    assert pdf["type"] == "pdf" and pdf["block_kind"] == "document"
    assert img["type"] == "image" and img["block_kind"] == "image"
    # Required schema keys present for both entries
    for shape in trace.attachments_shape:
        assert {"type", "size_class", "mime", "content_digest", "block_kind"} <= shape.keys()


def test_load_subagent_fixture_anchors_delegate_at_parent():
    """Parent must anchor ``delegate_to_subagent`` directly — it's the
    spec's core Phase C failure mode. Without this anchor, dropping the
    bridge-side dispatch would not fail any fixture."""
    trace = load_trace(SUBAGENT_FIXTURE)
    assert "delegate_to_subagent" in trace.tools_available
    assert len(trace.tool_calls) == 1
    parent_call = trace.tool_calls[0]
    assert parent_call.name == "delegate_to_subagent"
    # Bridge-side dispatch arguments mirrored
    assert "subagent" in parent_call.arguments
    assert "task" in parent_call.arguments
    # Parent pins the dispatch tool — commit 3's unified resolver must
    # resolve every pinned name via ToolRegistry → server-tools →
    # provider bridge surface. ``delegate_to_subagent`` is bridge-only,
    # so it resolves through the bridge surface branch. Pin is REQUIRED
    # resolution, never skip-lookup.
    assert trace.pinned_tool_names == ["delegate_to_subagent"]


def test_load_subagent_fixture_carries_nested_traces():
    trace = load_trace(SUBAGENT_FIXTURE)
    assert trace.subagent_traces is not None
    assert len(trace.subagent_traces) == 1
    child = trace.subagent_traces[0]
    # Nested shape locked here so commit 3 can recurse: tools_available
    # + tool_calls keep the same vocabulary as the parent trace, plus an
    # opt-in pinned_tool_names so the child can pin its own dependency
    # rather than the parent duplicating it.
    assert {"role", "system_prompt_hash", "tools_available", "tool_calls",
            "final_answer_hash"} <= child.keys()
    assert child["role"] == "data_summarizer"
    assert child["tool_calls"], "Nested tool_calls must not be empty — commit 3 needs them to recurse"
    nested_call = child["tool_calls"][0]
    assert nested_call["name"] == "get_ticker_news"
    # Child pins its own behaviour-dependent tool — separates from parent's pin.
    assert child.get("pinned_tool_names") == ["get_ticker_news"]


def test_replay_capture_round_trips_new_fields(tmp_path):
    """White-box: ``set_initial`` accepts the new opt-in kwargs and they
    survive the JSON save/load round-trip. Regression guard for commit 2."""
    cap = ReplayCapture(
        provider="anthropic",
        model="claude-opus-4-7",
        entrypoint="test",
        output_dir=tmp_path,
    )
    shape = [
        {"type": "pdf", "size_class": "small", "mime": "application/pdf",
         "content_digest": "abc", "block_kind": "document"},
    ]
    cap.set_initial(
        question="q",
        system_prompt="sys",
        tools_available=["get_ticker_news"],
        attachments_shape=shape,
        pinned_tool_names=["get_ticker_news"],
    )
    cap.record_final("ok", {})
    trace = load_trace(cap.save())
    assert trace.attachments_shape == shape
    assert trace.pinned_tool_names == ["get_ticker_news"]
    # subagent_traces is hand-crafted only in v1 — capture path leaves it None.
    assert trace.subagent_traces is None


def test_size_class_thresholds():
    # Per spec §2.2.1
    assert _size_class(0) == "small"
    assert _size_class(32 * 1024) == "small"
    assert _size_class(32 * 1024 + 1) == "medium"
    assert _size_class(512 * 1024) == "medium"
    assert _size_class(512 * 1024 + 1) == "large"
    assert _size_class(8 * 1024 * 1024) == "large"
    assert _size_class(8 * 1024 * 1024 + 1) == "huge"


class _FakeAttachment:
    """Stand-in for ``shared.attachments.Attachment`` — the classifier
    only consults ``data`` / ``media_type`` / ``is_pdf`` / ``is_image``
    / ``is_text`` so a SimpleNamespace would also work; defining a class
    keeps the test self-documenting."""
    def __init__(self, *, data, media_type, is_pdf=False, is_image=False, is_text=False):
        self.data = data
        self.media_type = media_type
        self.is_pdf = is_pdf
        self.is_image = is_image
        self.is_text = is_text


def test_classify_attachments_anthropic_pdf_image_text():
    """Anthropic mapping mirrors ``to_anthropic_blocks`` exactly:
    pdf → document, image → image, text → text. Reviewer's directive:
    derive from real provider block shape, not a guess."""
    pdf = _FakeAttachment(data=b"%PDF-1.4..." * 100, media_type="application/pdf", is_pdf=True)
    img = _FakeAttachment(data=b"\x89PNG" + b"x" * 1000, media_type="image/png", is_image=True)
    txt = _FakeAttachment(data=b"hello world", media_type="text/plain", is_text=True)

    out = classify_attachments("anthropic", [pdf, img, txt])
    assert out is not None and len(out) == 3
    assert out[0]["type"] == "pdf" and out[0]["block_kind"] == "document"
    assert out[1]["type"] == "image" and out[1]["block_kind"] == "image"
    assert out[2]["type"] == "text" and out[2]["block_kind"] == "text"


def test_classify_attachments_openai_image_text_pdf_as_text():
    """OpenAI mirrors ``to_openai_blocks``: image → input_image,
    text → input_text, pdf → input_text (extracted, not native)."""
    pdf = _FakeAttachment(data=b"%PDF-1.4..." * 100, media_type="application/pdf", is_pdf=True)
    img = _FakeAttachment(data=b"\x89PNG" + b"x" * 1000, media_type="image/png", is_image=True)
    txt = _FakeAttachment(data=b"hello world", media_type="text/plain", is_text=True)

    out = classify_attachments("openai", [pdf, img, txt])
    assert out is not None and len(out) == 3
    # pdf falls through to input_text on OpenAI (no native PDF support)
    assert out[0]["type"] == "pdf" and out[0]["block_kind"] == "input_text"
    assert out[1]["type"] == "image" and out[1]["block_kind"] == "input_image"
    assert out[2]["type"] == "text" and out[2]["block_kind"] == "input_text"


def test_classify_attachments_returns_none_for_empty_or_missing():
    """Empty / None inputs leave ``attachments_shape`` unset — the field
    stays out of the JSON for the common no-attachment trace, keeping
    fixture diffs minimal."""
    assert classify_attachments("anthropic", None) is None
    assert classify_attachments("openai", []) is None


def test_classify_attachments_handles_unknown_kind_gracefully():
    """An attachment that's neither pdf/image/text is recorded as
    ``unknown`` rather than crashing. Mirrors the fallback path in
    ``AttachmentManager.to_anthropic_blocks`` which tries text decode."""
    weird = _FakeAttachment(
        data=b"\x00\x01\x02binary blob",
        media_type="application/octet-stream",
    )
    out = classify_attachments("anthropic", [weird])
    assert out is not None and len(out) == 1
    assert out[0]["type"] == "unknown"
    # Per attachments.py fallback, unknowns ride on the text block kind.
    assert out[0]["block_kind"] == "text"


def test_digest_bytes_matches_hashlib_prefix():
    """``digest_bytes`` must hash raw bytes via SHA256 — NOT the
    str(b'...') repr (the former-bug that ``digest_json(bytes)``
    silently fell into via ``default=str``).
    """
    import hashlib
    raw = b"hello world"
    expected = hashlib.sha256(raw).hexdigest()[:DIGEST_LEN]
    assert digest_bytes(raw) == expected


def test_digest_bytes_stable_and_distinguishes_content():
    """Same bytes → same digest; different bytes → different digest;
    digest length matches ``DIGEST_LEN``."""
    assert digest_bytes(b"abc") == digest_bytes(b"abc")
    assert digest_bytes(b"abc") != digest_bytes(b"abd")
    assert len(digest_bytes(b"x")) == DIGEST_LEN
    # bytearray accepted (caller may have mutable buffer)
    assert digest_bytes(bytearray(b"abc")) == digest_bytes(b"abc")


def test_digest_bytes_handles_non_bytes_safely():
    """Non-bytes input returns empty string rather than crashing —
    matches the rest of the capture path's exception-swallowing."""
    assert digest_bytes(None) == ""
    assert digest_bytes("string not bytes") == ""
    assert digest_bytes(42) == ""


def test_classify_attachments_uses_raw_byte_digest():
    """Regression guard for the Medium finding: ``content_digest`` must
    reflect the raw file bytes, NOT a serialized form. A future refactor
    that swapped ``digest_bytes`` back to ``digest_json`` would change
    the digest on the same bytes — this assertion catches that drift.
    """
    import hashlib
    raw = b"\x89PNG\r\n\x1a\n" + b"x" * 200
    img = _FakeAttachment(data=raw, media_type="image/png", is_image=True)
    out = classify_attachments("anthropic", [img])
    expected = hashlib.sha256(raw).hexdigest()[:DIGEST_LEN]
    assert out[0]["content_digest"] == expected


def test_classify_attachments_empty_bytes_uses_sha256_of_empty():
    """An attachment with ``data=b''`` must still produce a stable digest
    (SHA256 of the empty byte string), NOT a blank string. Blank string
    is ``digest_bytes``'s sentinel for non-bytes input — conflating "empty
    file" with "non-bytes" loses the ability to distinguish them.
    """
    import hashlib
    empty = _FakeAttachment(data=b"", media_type="text/plain", is_text=True)
    out = classify_attachments("anthropic", [empty])
    assert out is not None and len(out) == 1
    expected = hashlib.sha256(b"").hexdigest()[:DIGEST_LEN]
    assert out[0]["content_digest"] == expected
    assert out[0]["size_class"] == "small"


def test_validate_registry_only_new_fixtures_clean(real_registry):
    """The 3 fixtures whose tool_calls only reference core ``ToolRegistry``
    tools must validate clean today (no ``unknown_tool`` /
    ``unknown_arg`` / ``missing_required`` errors). Warnings such as
    "tools newly registered" are allowed."""
    for path in (OPENAI_NO_TOOL_FIXTURE, OPENAI_ONE_TOOL_FIXTURE,
                 ATTACHMENT_FIXTURE):
        trace = load_trace(path)
        result = validate_trace_against_registry(trace, real_registry)
        assert result.passed, f"{path.name} did not validate clean: {result.render()}"


def test_subagent_fixture_fails_today_pending_commit_3_resolver(real_registry):
    """The subagent fixture references ``delegate_to_subagent`` — which is
    bridge-only, NOT in ``ToolRegistry``. Today's validator reports it as
    ``unknown_tool``. This test pins THAT specific failure shape so commit
    3's UNIFIED RESOLVER has a concrete green-flip target.

    Commit 3's contract (per spec §2.3): pinning is a REQUIRED-RESOLUTION
    list, NOT a skip-list. The validator must consult, in order,
    ``ToolRegistry`` → server-tools → provider bridge surface. Once the
    bridge-surface branch lands, ``delegate_to_subagent`` resolves via
    the Anthropic bridge and the fixture validates clean — without ever
    bypassing per-call lookup. Skipping lookup would let Phase C silently
    drop the bridge tool while the pin keeps the fixture green; the
    resolver path closes that loophole.

    If the failure shape changes (e.g. ``delegate_to_subagent`` is added
    to ``ToolRegistry`` core, or the validator's error message format
    drifts), this test fails — by design — and commit 3 must update it
    alongside flipping the assertion to ``passed is True``.
    """
    trace = load_trace(SUBAGENT_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    # The single error must point at delegate_to_subagent specifically.
    assert any("delegate_to_subagent" in e for e in result.errors), (
        f"Expected unknown_tool error for delegate_to_subagent; got: {result.render()}"
    )