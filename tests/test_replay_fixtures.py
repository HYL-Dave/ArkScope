"""P0.1 full-v1 commit 3: parametrised pytest replay gate.

This module IS the spec's main contribution — it re-validates every
fixture under ``tests/replay_fixtures/`` against the live
``ToolRegistry`` whenever pytest runs. A PR that renames a tool,
deletes a registry entry used by a fixture, drops
``delegate_to_subagent`` from the bridge surface, or removes an
attachment block-kind handler fails this gate with a message naming
the offending fixture and drift.

There is no automatic CI / pre-commit infrastructure today (per spec
§2.3). When future CI lands, wiring this module is a one-line
addition. Until then, the gate is a developer-discipline regression
vector — same status as every other test in the repo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.shared.replay import load_trace, validate_trace_against_registry

FIXTURE_DIR = Path(__file__).parent / "replay_fixtures"
FIXTURE_FILES = sorted(FIXTURE_DIR.glob("*.json"))


@pytest.fixture(scope="module")
def real_registry():
    from src.tools.registry import create_default_registry
    return create_default_registry()


@pytest.mark.parametrize(
    "fixture_path",
    FIXTURE_FILES,
    ids=[p.name for p in FIXTURE_FILES],
)
def test_fixture_validates_clean(fixture_path, real_registry):
    """Every fixture under ``tests/replay_fixtures/`` must validate
    clean against the current registry. Warnings (e.g. "tools newly
    registered") are allowed; errors are not.
    """
    trace = load_trace(fixture_path)
    result = validate_trace_against_registry(trace, real_registry)
    assert result.passed, (
        f"{fixture_path.name} failed validation:\n{result.render()}"
    )


def test_fixture_directory_is_non_empty():
    """Sanity guard — if someone deletes the fixture directory or
    accidentally renames the glob, the parametrised gate above
    becomes a silent no-op. Catch that.
    """
    assert FIXTURE_FILES, (
        f"No JSON fixtures found in {FIXTURE_DIR} — replay gate would "
        f"silently pass."
    )