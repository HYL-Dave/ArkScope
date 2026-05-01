#!/usr/bin/env python
"""Static validator for replay fixtures (P0.1 full-v1).

Usage:
    python scripts/replay_run.py tests/replay_fixtures/one_tool_turn.json
    python -m pytest tests/test_replay_fixtures.py    # parametrised gate

Reads a captured turn fixture and validates against the current
``ToolRegistry`` + bridge surface + attachment-handling code. Does
NOT call any LLM. Does NOT replay tool execution. Does NOT compare
full tool results.

Validation goes through the unified resolver (per spec §2.3):
``ToolRegistry`` → ``shared/server_tools.py`` (``server:*`` hosted
tools) → ``shared/bridge_tools.py`` (bridge-only tools like
``delegate_to_subagent``). Each name is resolved against all three
sources before ``unknown_tool`` is reported. Argument-shape gates
fire identically for registry and bridge tools.

Checks:
  - all captured tool names resolve via the unified resolver
  - captured argument keys are still accepted by the resolved tool's schema
  - currently-required arguments are present in the capture
  - ``pinned_tool_names`` REQUIRED-RESOLUTION (NOT skip-list) — every
    pinned name must resolve through the same resolver
  - ``attachments_shape``: each ``(type, block_kind)`` pair must be
    producible by ``AttachmentManager`` for the trace's provider
  - subagent_traces[i] recursed via the same resolver under the parent's
    provider; child errors prefixed with ``subagent_traces[i] (<role>): ``
  - system_prompt_hash drift (warning only — content drift is expected)

Exit codes:
  0 — passed (no errors; warnings allowed)
  1 — failed (one or more errors)
  2 — usage error (bad path, malformed fixture)

For automation use ``tests/test_replay_fixtures.py`` — that module
parametrises every fixture under ``tests/replay_fixtures/`` and is the
load-bearing regression vector for Phase C. This script is the
ad-hoc developer-friendly entry point.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without install
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.agents.shared.replay import (  # noqa: E402
    load_trace,
    validate_trace_against_registry,
)


def _build_registry():
    from src.tools.registry import create_default_registry
    return create_default_registry()


def _build_current_system_prompt() -> str | None:
    """Render the current system prompt for hash drift detection.

    Returns None if rendering fails (do not block validation on this).
    """
    try:
        from src.agents.shared.prompts import build_system_prompt
        return build_system_prompt("")
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("fixture", help="path to a replay fixture JSON file")
    parser.add_argument(
        "--no-prompt-check",
        action="store_true",
        help="skip system_prompt_hash drift warning",
    )
    args = parser.parse_args(argv)

    path = Path(args.fixture)
    if not path.exists():
        print(f"ERROR: fixture not found: {path}", file=sys.stderr)
        return 2

    try:
        trace = load_trace(path)
    except Exception as exc:
        print(f"ERROR: failed to load fixture {path}: {exc}", file=sys.stderr)
        return 2

    registry = _build_registry()
    current_prompt = None if args.no_prompt_check else _build_current_system_prompt()

    result = validate_trace_against_registry(
        trace,
        registry,
        current_system_prompt=current_prompt,
    )

    print(f"Fixture: {path}")
    print(f"Captured at: {trace.captured_at}")
    print(f"Provider/Model: {trace.provider} / {trace.model}")
    print(f"User input: {trace.user_input[:80]}{'...' if len(trace.user_input) > 80 else ''}")
    print(f"Tool calls: {len(trace.tool_calls)} | Tools available at capture: {len(trace.tools_available)}")
    print()
    print(result.render())

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())