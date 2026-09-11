"""Exercise offline-runner path classification without spawning a process."""
import importlib.util
import json
from pathlib import Path
import sys


source = Path(__file__).with_name(sys.argv[1])
spec = importlib.util.spec_from_file_location("offline_scope_probe", source)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
fixtures = runner.FIXTURES.resolve()
cases = (
    ("fixture_codex", fixtures / "nvm/bin/codex", True),
    ("fixture_claude", fixtures / "sdk/claude", True),
    ("outside_codex", fixtures.parent / "codex", False),
    ("outside_claude", fixtures.parent / "claude", False),
    ("dotdot_escape", fixtures / "../codex", False),
)
results = []
for name, executable, expected in cases:
    try:
        runner._audit("subprocess.Popen", (str(executable), [str(executable), "app-server"]))
        admitted = True
    except PermissionError:
        admitted = False
    results.append({"case": name, "admitted": admitted, "expected": expected})
print(json.dumps(results, indent=2))
raise SystemExit(0 if all(row["admitted"] == row["expected"] for row in results) else 1)
