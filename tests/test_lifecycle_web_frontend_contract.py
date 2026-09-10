import json
from pathlib import Path
import subprocess

import pytest

from src.lifecycle_web_schema import RUNNING, TERMINAL
from src.auth_drivers.lifecycle_web_usage import USAGE_BASES, USAGE_COVERAGE


def test_web_frontend_runtime_states_match_backend_in_both_directions():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["node", str(root / "tests/typescript_vocabulary_authority.cjs"),
        str(root / "apps/arkscope-web/src/lifecycle/webContract.ts"),
        json.dumps({"states": {"kind": "array", "name": "WEB_RUN_STATES"}, "phases": {"kind": "array", "name": "WEB_PHASES"},
                    "usage_bases": {"kind": "array", "name": "WEB_USAGE_BASES"},
                    "usage_coverage": {"kind": "array", "name": "WEB_USAGE_COVERAGE"}})],
        check=True, capture_output=True, text=True, timeout=20)
    value = json.loads(result.stdout)
    assert len(value["states"]) == len(set(value["states"]))
    assert set(value["states"]) == set(RUNNING) | set(TERMINAL) | {"cancelling"}
    assert set(value["phases"]) == set(RUNNING)
    assert set(value["usage_bases"]) == USAGE_BASES and len(value["usage_bases"]) == len(USAGE_BASES)
    assert set(value["usage_coverage"]) == USAGE_COVERAGE and len(value["usage_coverage"]) == len(USAGE_COVERAGE)


@pytest.mark.parametrize("failure", [None, "sources", "lost"])
def test_persisted_usage_projection_roundtrips_actual_typescript_reader(tmp_path, failure):
    from src.lifecycle_web_projection import project_web_run
    from tests.test_lifecycle_web_usage_journal import saved_usage_receipt
    from tests.test_lifecycle_web_store import AT

    store, identity = saved_usage_receipt(tmp_path, failure=failure)
    value = project_web_run(store.read(identity), at=AT)
    root = Path(__file__).resolve().parents[1]
    javascript = """
const fs = require('node:fs'), ts = require('typescript');
const source = fs.readFileSync(process.argv[1], 'utf8');
const code = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}}).outputText;
const exports = {};
new Function('exports', code)(exports);
process.stdout.write(JSON.stringify(exports.parseWebRun(JSON.parse(fs.readFileSync(0, 'utf8')))));
"""
    result = subprocess.run(["node", "-e", javascript, str(root / "apps/arkscope-web/src/lifecycle/webContract.ts")],
                            cwd=root, input=json.dumps(value), capture_output=True, text=True, timeout=20, check=True)
    assert json.loads(result.stdout) == value
