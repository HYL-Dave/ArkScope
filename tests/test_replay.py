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


def test_validate_all_new_fixtures_clean(real_registry):
    """All 4 commit-2 fixtures must validate clean against commit 3's
    unified resolver — including ``subagent_turn`` whose
    ``delegate_to_subagent`` resolves through the bridge-surface branch.
    Warnings such as "tools newly registered" are allowed; errors are not.
    """
    for path in (OPENAI_NO_TOOL_FIXTURE, OPENAI_ONE_TOOL_FIXTURE,
                 ATTACHMENT_FIXTURE, SUBAGENT_FIXTURE):
        trace = load_trace(path)
        result = validate_trace_against_registry(trace, real_registry)
        assert result.passed, f"{path.name} did not validate clean: {result.render()}"


def test_subagent_fixture_validates_via_unified_resolver(real_registry):
    """``subagent_turn`` fixture's parent tool call ``delegate_to_subagent``
    is bridge-only (NOT in ``ToolRegistry``). The unified resolver must
    find it via ``shared/bridge_tools.py`` (resolver step 3). The child
    trace's ``get_ticker_news`` resolves via ``ToolRegistry`` (step 1).

    This test was the pinned-failure target before commit 3 (see
    ``test_subagent_fixture_fails_today_pending_commit_3_resolver`` in git
    history) — flipped to pass-case once the bridge branch landed.
    """
    trace = load_trace(SUBAGENT_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed, (
        f"subagent fixture must validate clean via unified resolver: "
        f"{result.render()}"
    )
    # Subagent recursion happened: nested trace has 1 tool call, no errors.
    assert trace.subagent_traces is not None
    assert len(trace.subagent_traces) == 1


# ---------------------------------------------------------------------------
# P0.1 full-v1 commit 3: unified resolver regression tests
# ---------------------------------------------------------------------------


def _fake_registry(tools_by_name):
    """Build a minimal registry shim accepted by the validator.

    ``tools_by_name`` maps name → object exposing ``parameters`` (each
    with ``.name`` + ``.required``). Used to construct registry deltas
    (added / removed tools) without touching the live registry.
    """
    from types import SimpleNamespace

    def _param(name, required=False):
        return SimpleNamespace(name=name, required=required)

    class _Reg:
        def __init__(self, table):
            self._table = dict(table)

        def list_names(self):
            return list(self._table.keys())

        def get(self, name):
            return self._table.get(name)

    return _Reg(tools_by_name), _param


def test_pinned_tool_names_respects_registry_additions(real_registry):
    """Adding an unrelated tool to the registry must not fail a fixture
    whose pin only names tools it actually uses. This is the
    "expected-diff pass" acceptance from spec §4.2.
    """
    trace = load_trace(ONE_TOOL_FIXTURE)
    # Pin only the actually-called tool.
    trace.pinned_tool_names = ["get_ticker_news"]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed, result.render()


def test_pinned_tool_names_rejects_when_pinned_tool_removed(real_registry):
    """Removing a pinned tool from the registry must produce an
    ``unknown_tool``-style error naming the pin. Spec §4.2 expected-diff
    fail acceptance.
    """
    trace = load_trace(ONE_TOOL_FIXTURE)
    # Pin a name we'll then strip from a stub registry.
    trace.pinned_tool_names = ["get_ticker_news"]

    stripped, _ = _fake_registry({})  # registry that knows zero tools
    result = validate_trace_against_registry(trace, stripped)
    assert result.passed is False
    assert any(
        "pinned_tool_names" in e and "get_ticker_news" in e
        for e in result.errors
    ), f"Expected pinned_tool_names error for get_ticker_news; got: {result.render()}"


def test_bridge_drop_makes_subagent_fixture_fail(monkeypatch, real_registry):
    """LOAD-BEARING for spec §2.3 resolver contract: pinning is
    REQUIRED-RESOLUTION, NOT skip-lookup.

    If pinning were "trust and skip lookup," dropping
    ``delegate_to_subagent`` from the bridge surface would still leave
    ``subagent_turn`` validating green (Phase C silently breaks
    subagent dispatch with no test signal). Because the unified
    resolver actually consults the bridge surface, removing the bridge
    entry produces ``unknown_tool`` for ``delegate_to_subagent``.
    """
    monkeypatch.setattr(
        "src.agents.shared.bridge_tools.all_bridge_specs_for_provider",
        lambda provider: {},
    )
    trace = load_trace(SUBAGENT_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any(
        "delegate_to_subagent" in e for e in result.errors
    ), f"Expected unknown_tool for delegate_to_subagent; got: {result.render()}"


def test_bridge_arg_shape_missing_required_fails(real_registry):
    """Bridge tools must use the SAME arg-shape gate as registry tools.
    A ``delegate_to_subagent`` call missing the required ``task`` arg
    must fail with ``missing_required``-style error. Without this,
    Phase C could rename ``task`` → ``prompt`` and the fixture would
    still validate green.
    """
    trace = load_trace(SUBAGENT_FIXTURE)
    # Mutate first tool call to drop ``task``.
    bad_call = trace.tool_calls[0]
    bad_call.arguments = {"subagent": "data_summarizer"}
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any(
        "delegate_to_subagent" in e and "task" in e and "requires" in e
        for e in result.errors
    ), f"Expected missing-required error for 'task'; got: {result.render()}"


def test_bridge_arg_shape_unknown_arg_fails(real_registry):
    """Symmetric to ``missing_required``: a captured arg not in the
    bridge spec must fail with ``unknown_arg`` shape — catches Phase C
    accepting a deprecated arg name silently.
    """
    trace = load_trace(SUBAGENT_FIXTURE)
    bad_call = trace.tool_calls[0]
    bad_call.arguments = {
        "subagent": "data_summarizer",
        "task": "summarize",
        "obsolete_arg": "x",
    }
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any(
        "delegate_to_subagent" in e and "obsolete_arg" in e and "no longer accepted" in e
        for e in result.errors
    ), f"Expected unknown-arg error for 'obsolete_arg'; got: {result.render()}"


def test_attachment_pair_passes_clean(real_registry):
    """``attachment_turn`` ships ``("pdf", "document")`` and
    ``("image", "image")`` pairs — both are produced by the current
    Anthropic ``AttachmentManager.to_anthropic_blocks``, so the
    validator must accept the fixture clean.
    """
    trace = load_trace(ATTACHMENT_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed, result.render()


def test_attachment_pair_fails_when_pair_removed(monkeypatch, real_registry):
    """Spec §4.2 attachment-fail acceptance: monkeypatching the
    supported-pair helper to drop ``("pdf", "document")`` makes
    ``attachment_turn`` fail with an attachment-shape diff. The pair
    granularity (NOT just block_kind) is what catches mis-classified
    entries — see ``test_attachment_pair_check_is_pair_not_just_block_kind``.
    """
    from src.agents.shared import replay as replay_mod

    monkeypatch.setattr(
        replay_mod,
        "_supported_attachment_pairs",
        lambda provider: {("image", "image"), ("text", "text")},  # drops pdf/document
    )
    trace = load_trace(ATTACHMENT_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any(
        "attachments_shape" in e and "'pdf'" in e and "'document'" in e
        for e in result.errors
    ), f"Expected pair-mismatch error for (pdf, document); got: {result.render()}"


def test_attachment_pair_check_is_pair_not_just_block_kind(real_registry):
    """A fixture-style entry with mismatched type/block_kind
    (``{"type":"pdf","block_kind":"image"}``) must fail — even though
    "image" is a valid block_kind on its own. Validates that the gate
    is on the PAIR, not on each axis independently.
    """
    trace = load_trace(ATTACHMENT_FIXTURE)
    # Forge a mis-classified entry: pdf with image block_kind.
    trace.attachments_shape = [{
        "type": "pdf",
        "size_class": "small",
        "mime": "application/pdf",
        "content_digest": "0" * 16,
        "block_kind": "image",
    }]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any(
        "attachments_shape" in e and "'pdf'" in e and "'image'" in e
        for e in result.errors
    ), f"Expected pair-mismatch error; got: {result.render()}"


def test_attachment_unknown_type_opts_out(real_registry):
    """Per spec §6 risk register: ``type == "unknown"`` is the explicit
    opt-out — the validator skips the pair check rather than failing.
    Reviewers reject ``unknown`` fixtures unless intentional.
    """
    trace = load_trace(ATTACHMENT_FIXTURE)
    trace.attachments_shape = [{
        "type": "unknown",
        "size_class": "small",
        "mime": "application/octet-stream",
        "content_digest": "0" * 16,
        "block_kind": "definitely_not_real",
    }]
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed, result.render()


def test_availability_diff_excludes_bridge_resolved_names(real_registry):
    """Resolver-aware availability diff: ``delegate_to_subagent`` is
    bridge-only and lives outside ToolRegistry, so it MUST NOT appear
    in the "Tools no longer registered" warning. Before this fix, the
    ad-hoc ``scripts/replay_run.py`` printed a misleading warning for
    every fixture that anchored a bridge-only tool — even though the
    tool resolved cleanly through the bridge branch.

    This test pins the warning text so the fix can't silently regress.
    """
    trace = load_trace(SUBAGENT_FIXTURE)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed, result.render()
    for warning in result.warnings:
        if "no longer registered" in warning:
            assert "delegate_to_subagent" not in warning, (
                f"Bridge-resolved name leaked into removed-from-registry "
                f"warning: {warning}"
            )


def test_availability_diff_still_flags_truly_removed_names(real_registry):
    """Symmetric guard for the resolver-aware diff: a name that resolves
    through NONE of the three resolver sources (typo, deleted from
    registry AND bridge) MUST still appear in the removed-from-registry
    warning. The fix narrows the diff, doesn't silence it.
    """
    trace = load_trace(ONE_TOOL_FIXTURE)
    # Inject a name that won't resolve anywhere.
    trace.tools_available = list(trace.tools_available) + ["definitely_gone_tool"]
    result = validate_trace_against_registry(trace, real_registry)
    assert any(
        "no longer registered" in w and "definitely_gone_tool" in w
        for w in result.warnings
    ), f"Expected removed-from-registry warning for stray name; got: {result.render()}"


def test_subagent_recursion_emits_role_prefixed_errors(real_registry):
    """Errors inside ``subagent_traces`` must be prefixed with the
    role for traceability. Ensures commit 3's recursion isn't a silent
    no-op: corrupt the child's tool name and confirm the error names
    the subagent role.
    """
    trace = load_trace(SUBAGENT_FIXTURE)
    # Corrupt the child's tool call to a non-existent name.
    trace.subagent_traces[0]["tool_calls"][0]["name"] = "definitely_not_a_tool"
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed is False
    assert any(
        "subagent_traces[0]" in e
        and "data_summarizer" in e
        and "definitely_not_a_tool" in e
        for e in result.errors
    ), f"Expected role-prefixed child error; got: {result.render()}"


# ---------------------------------------------------------------------------
# Forward safeguards — keep helper tables in sync with live code paths
# ---------------------------------------------------------------------------


def test_bridge_helper_stays_in_sync_with_anthropic_surface(real_registry):
    """Forward safeguard: the names exposed by Anthropic's bridge but
    NOT in ``ToolRegistry`` must equal the keys in
    ``anthropic_bridge_tool_specs``. Phase C adding a new bridge-only
    tool without updating the helper fails this test.

    Server-tool kinds (``server:*``) are stripped because they live
    in ``shared/server_tools.py``, not the bridge spec table.
    """
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.shared.bridge_tools import anthropic_bridge_tool_specs

    # Force-on hosted-tool config so ``get_anthropic_tools`` includes
    # everything the bridge can wire — we want the maximal surface,
    # then we subtract registry + server-tool stand-ins.
    surface_names = {t["name"] for t in get_anthropic_tools()}
    registry_names = set(real_registry.list_names())

    bridge_only = surface_names - registry_names
    helper_names = set(anthropic_bridge_tool_specs().keys())
    assert bridge_only == helper_names, (
        f"Anthropic bridge surface drift — surface_only={bridge_only}, "
        f"helper={helper_names}. Update shared/bridge_tools.py to match."
    )


def test_bridge_helper_stays_in_sync_with_openai_surface(real_registry):
    """Symmetric forward safeguard for OpenAI. The agents SDK exposes
    each function's ``__name__`` to the model with a ``tool_`` prefix,
    so we strip it before comparing to the canonical helper.
    """
    from src.agents.openai_agent.tools import create_openai_tools
    from src.agents.shared.bridge_tools import openai_bridge_tool_specs

    # ``create_openai_tools`` needs a DAL; it's only used for closure
    # over data access, not for listing names — pass a dummy.
    class _DummyDAL:
        pass

    bridge_objs = create_openai_tools(_DummyDAL())
    raw_names = set()
    for t in bridge_objs:
        # @function_tool wrappers expose ``.name`` (FunctionTool) or
        # the underlying function's ``__name__``.
        name = getattr(t, "name", None) or getattr(t, "__name__", "")
        raw_names.add(name)
    # Strip bridge prefix so we compare canonical names.
    canonical = {n[len("tool_"):] if n.startswith("tool_") else n for n in raw_names}
    registry_names = set(real_registry.list_names())

    bridge_only = canonical - registry_names
    helper_names = set(openai_bridge_tool_specs().keys())
    assert bridge_only == helper_names, (
        f"OpenAI bridge surface drift — surface_only={bridge_only}, "
        f"helper={helper_names}. Update shared/bridge_tools.py to match."
    )


def _probe_attachments():
    """Build canonical PDF / PNG / text ``Attachment`` instances for
    forward-safeguard tests. ``AttachmentManager`` accepts pre-built
    ``Attachment`` objects; the bytes are minimal-valid since
    ``to_anthropic_blocks`` only base64-encodes them, and
    ``to_openai_blocks``'s PDF extraction is monkeypatched at call site.
    """
    from src.agents.shared.attachments import Attachment

    return [
        Attachment(
            path="/tmp/probe.pdf",
            filename="probe.pdf",
            media_type="application/pdf",
            data=b"%PDF-1.4\n" + b"x" * 100,
        ),
        Attachment(
            path="/tmp/probe.png",
            filename="probe.png",
            media_type="image/png",
            data=b"\x89PNG\r\n\x1a\n" + b"x" * 100,
        ),
        Attachment(
            path="/tmp/probe.txt",
            filename="probe.txt",
            media_type="text/plain",
            data=b"hello world",
        ),
    ]


def test_supported_attachment_pairs_match_anthropic_attachment_manager():
    """Forward safeguard for the (type, block_kind) registry: every
    pair the live ``AttachmentManager.to_anthropic_blocks`` actually
    produces must appear in ``_supported_attachment_pairs("anthropic")``.

    Drift in ``attachments.py`` (e.g. PDF moves from ``document`` to
    ``url``) breaks this test before any fixture silently passes.
    """
    from src.agents.shared.attachments import AttachmentManager
    from src.agents.shared.replay import _supported_attachment_pairs

    blocks = AttachmentManager.to_anthropic_blocks(_probe_attachments())
    supported = _supported_attachment_pairs("anthropic")
    # Probe order tracks emitted order. Anthropic emits a block per
    # attachment (no decoding required), so all 3 are present.
    assert len(blocks) == 3
    expected_types = ["pdf", "image", "text"]
    for canonical_type, block in zip(expected_types, blocks):
        block_kind = block.get("type")
        assert (canonical_type, block_kind) in supported, (
            f"Anthropic block ({canonical_type!r}, {block_kind!r}) emitted "
            f"by AttachmentManager but not in _supported_attachment_pairs."
        )


def test_supported_attachment_pairs_match_openai_attachment_manager(monkeypatch):
    """Symmetric forward safeguard for OpenAI. PDF on OpenAI extracts
    to ``input_text`` via ``PDFProcessor.extract_text`` — we patch the
    extractor to a stub since the probe bytes aren't a real PDF; the
    test gates on the BLOCK KIND, not the extracted content.
    """
    from src.agents.shared import attachments as attachments_mod
    from src.agents.shared.attachments import AttachmentManager
    from src.agents.shared.replay import _supported_attachment_pairs

    monkeypatch.setattr(
        attachments_mod.PDFProcessor,
        "extract_text",
        staticmethod(lambda data, pages="": "stub-extracted text"),
    )

    blocks = AttachmentManager.to_openai_blocks(_probe_attachments())
    # OpenAI emit order: image-first PDF/text fallthrough — the manager
    # iterates in the original list order, so emission order = probe
    # order = pdf, image, text.
    assert len(blocks) == 3
    supported = _supported_attachment_pairs("openai")
    expected_types = ["pdf", "image", "text"]
    for canonical_type, block in zip(expected_types, blocks):
        block_kind = block.get("type")
        assert (canonical_type, block_kind) in supported, (
            f"OpenAI block ({canonical_type!r}, {block_kind!r}) emitted "
            f"by AttachmentManager but not in _supported_attachment_pairs."
        )