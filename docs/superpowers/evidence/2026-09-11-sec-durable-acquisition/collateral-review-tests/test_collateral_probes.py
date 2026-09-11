"""Read-only product checks and direct, no-spawn audit classification probes."""
import ast
from collections import Counter
import json
import os
from pathlib import Path
import subprocess

import pytest

SCRATCH = Path(__file__).resolve().parent
PLAN = SCRATCH.parent
ROOT = PLAN.parents[2]


def _runner_scope(filename, workspace, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_OFFLINE_TEST_WORKSPACE", workspace)
    path = PLAN / filename
    tree = ast.parse(path.read_text())
    # Exercise the exact audit function without installing cumulative global hooks.
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "addaudithook"
    )]
    scope = {"__file__": str(path), "__name__": "review_scope"}
    exec(compile(tree, str(path), "exec"), scope)
    return scope


@pytest.mark.parametrize("filename", ["offline_pytest_initial.py", "offline_pytest.py"])
@pytest.mark.parametrize("relative", [False, True])
def test_runner_scope_matrix(filename, relative, monkeypatch):
    workspace = str(SCRATCH / "fixtures")
    if relative:
        workspace = os.path.relpath(workspace, ROOT)
    scope = _runner_scope(filename, workspace, monkeypatch)
    fixtures = scope["FIXTURES"].resolve()
    legacy_relative = relative and filename == "offline_pytest_initial.py"
    cases = [
        ("fixture_codex", fixtures / "nvm/bin/codex", not legacy_relative),
        ("fixture_claude", fixtures / "sdk/claude", not legacy_relative),
        ("outside_codex", fixtures.parent / "codex", False),
        ("outside_claude", fixtures.parent / "claude", False),
        ("dotdot_escape", fixtures / "../codex", False),
        ("prefix_sibling", Path(str(fixtures) + "-outside") / "claude", False),
        ("bare_codex", Path("codex"), False),
        ("bare_claude", Path("claude"), False),
    ]
    results = []
    for name, executable, expected in cases:
        try:
            scope["_audit"]("subprocess.Popen", (str(executable), [str(executable), "app-server"]))
            admitted = True
        except PermissionError:
            admitted = False
        results.append({"case": name, "admitted": admitted, "expected": expected})
    (SCRATCH / f"scope-{filename}-{'relative' if relative else 'absolute'}.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    assert all(row["admitted"] == row["expected"] for row in results)


def test_runner_rejects_symlink_escape(tmp_path, monkeypatch):
    scope = _runner_scope("offline_pytest.py", str(SCRATCH / "fixtures"), monkeypatch)
    link = tmp_path / "codex"
    link.symlink_to(SCRATCH / "outside-fixtures" / "codex")
    with pytest.raises(PermissionError, match="real provider CLI session"):
        scope["_audit"]("subprocess.Popen", (str(link), [str(link), "app-server"]))


def test_route_delta_exactly_sec_routes():
    import src.api.app as current

    baseline = subprocess.check_output(
        ["git", "show", "737f438d:src/api/app.py"], cwd=ROOT, text=True
    )
    scope = dict(current.__dict__)
    exec(compile(baseline, "737f438d:src/api/app.py", "exec"), scope)

    def rows(app):
        return Counter(
            (tuple(sorted(route.methods or ())), route.path,
             route.endpoint.__module__, route.endpoint.__qualname__)
            for route in app.routes
        )

    old_app = scope["create_app"]()
    new_app = current.create_app()
    old, new = rows(old_app), rows(new_app)
    added = new - old
    removed = old - new
    expected = Counter({
        (("GET",), "/sec-research/{cik}", "src.api.routes.sec_research", "stored_status"): 1,
        (("POST",), "/sec-research/{cik}/refresh", "src.api.routes.sec_research", "refresh"): 1,
    })
    assert added == expected
    assert not removed
    assert (sum(old.values()), sum(new.values())) == (216, 218)
    old_pairs = {(m, r.path) for r in old_app.routes for m in r.methods or () if m not in {"HEAD", "OPTIONS"}}
    new_pairs = {(m, r.path) for r in new_app.routes for m in r.methods or () if m not in {"HEAD", "OPTIONS"}}
    assert (len(old_pairs), len(new_pairs)) == (216, 218)
    assert old_pairs <= new_pairs
    assert new_pairs - old_pairs == {("GET", "/sec-research/{cik}"), ("POST", "/sec-research/{cik}/refresh")}
    (SCRATCH / "route-delta.json").write_text(json.dumps({
        "baseline_routes": sum(old.values()), "current_routes": sum(new.values()),
        "baseline_method_path_pairs": len(old_pairs), "current_method_path_pairs": len(new_pairs),
        "added": list(added.elements()), "removed": list(removed.elements()),
    }, indent=2) + "\n")
