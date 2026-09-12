"""Focused marker-composition probe against the immutable Task 1 commit."""

from pathlib import Path
import subprocess
import types

import pytest


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "2f0cedeb62c6663e1d55ebf82e8623833c631095"
SOURCE_PATH = "src/agents/shared/output_boundary.py"


@pytest.fixture(scope="module")
def boundary():
    source = subprocess.run(
        ["git", "show", f"{COMMIT}:{SOURCE_PATH}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    module = types.ModuleType("task1_reviewer_pinned_boundary")
    exec(compile(source, f"{COMMIT}:{SOURCE_PATH}", "exec"), module.__dict__)
    return module


@pytest.mark.parametrize("mode", ["prose", "characters", *range(6)])
def test_marker_cannot_create_another_registered_secret(boundary, mode):
    source_secret = "xyz"
    composite_secret = "a[REDACTED]b"
    raw = "axyzb"
    guard = boundary.OutputGuard([source_secret, composite_secret])
    assert composite_secret not in raw
    assert guard.prose("public!") == "public!"
    with pytest.raises(boundary.OutputBoundaryError, match="known_secret"):
        guard.check(composite_secret)

    try:
        if mode == "prose":
            output = guard.prose(raw)
        else:
            stream = guard.stream()
            chunks = list(raw) if mode == "characters" else [raw[:mode], raw[mode:]]
            output = "".join(stream.feed(chunk) for chunk in chunks) + stream.finish()
    except boundary.OutputBoundaryError as error:
        assert error.code == "redaction_marker_conflict"
        return

    assert composite_secret not in output, "redaction created another registered credential"
