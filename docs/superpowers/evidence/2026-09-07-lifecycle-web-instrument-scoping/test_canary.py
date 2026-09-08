from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location("instrument_canary", Path(__file__).with_name("canary.py"))
canary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(canary)


def test_canary_budget_comes_from_the_product_and_remains_bounded():
    from src.security_lifecycle_web_pipeline import default_investigation_options
    plan = canary.amend_plan({"max_cli_internal_turns": {"search": 6, "analysis": 2}})
    assert plan["options"] == asdict(default_investigation_options("claude_code_oauth", effort="medium", output_token_limit=None))
    assert plan["source_http_campaign_budget"] == {"limit": 24, "already_used": 0, "this_run_maximum": 24}
    assert plan["max_model_submissions"] == 2 and plan["local_completion_deadline_seconds"] == 1500
    assert plan["max_cli_tool_round_trips"] == {"search": 14, "analysis": 2}
    assert "max_cli_internal_turns" not in plan


@pytest.mark.parametrize("field", ["max_search_uses", "max_sources", "max_source_requests", "max_redirects", "model_timeout_seconds", "source_timeout_seconds"])
def test_canary_rejects_unapproved_budget_change_before_execution(monkeypatch, field):
    options = canary.current_options()
    monkeypatch.setattr(canary, "current_options", lambda: replace(options, **{field: getattr(options, field) + 1}))
    with pytest.raises(ValueError, match="^authorized_budget_changed$"):
        canary.amend_plan({"max_cli_internal_turns": {}})


def test_canary_enforces_the_analysis_and_search_output_modes():
    class Base:
        def __init__(self, *, options):
            self.options = options

    wrapped = canary.observed_client(Base)
    analysis = SimpleNamespace(tools=[], output_format=None, disallowed_tools=["StructuredOutput"], max_turns=2)
    search = SimpleNamespace(tools=["WebSearch"], output_format={"schema": {"type": "object"}}, max_turns=14)
    assert wrapped(options=analysis).analysis is True
    assert wrapped(options=search).analysis is False
    analysis.output_format = {"schema": {"type": "object"}}
    with pytest.raises(ValueError, match="^analysis_output_mode_changed$"):
        wrapped(options=analysis)
    search.max_turns = 15
    with pytest.raises(ValueError, match="^search_output_mode_changed$"):
        wrapped(options=search)


def test_larger_product_preflight_roundtrips_the_actual_frontend_parser(tmp_path, monkeypatch):
    from tests.test_lifecycle_web_preflight import setup
    from tests.test_lifecycle_web_review import context
    from tests.test_security_lifecycle_web_finding import public_input

    c = context(tmp_path)
    service, _, _ = setup(c, provider="anthropic", auth="claude_code_oauth")
    monkeypatch.setattr(service, "_public_input", lambda *args, **kwargs: public_input())
    packet = service.prepare(c["case_id"], question="listing_status")
    root = Path(__file__).resolve().parents[4]
    script = """
const fs = require('node:fs'), ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(process.argv[1], 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}
}).outputText;
const exports = {};
new Function('exports', code)(exports);
process.stdout.write(JSON.stringify(exports.parseWebPreflight(JSON.parse(fs.readFileSync(0, 'utf8')))));
"""
    result = subprocess.run(["node", "-e", script, str(root / "apps/arkscope-web/src/lifecycle/webContract.ts")],
        cwd=root, input=json.dumps(packet), capture_output=True, text=True, timeout=20, check=True)
    assert json.loads(result.stdout) == packet
    assert packet["limits"]["source_requests"] == 24 and packet["limits"]["search_uses"] == 12


def test_cross_instrument_result_stays_unactionable_after_journal_reopen_and_review(tmp_path):
    from src.lifecycle_web_store import LifecycleWebStore
    from src.lifecycle_web_projection import project_web_run
    from tests.test_lifecycle_web_review import context, prepare, rows
    from tests.test_lifecycle_web_instrument_scope import IDENTITY, citation
    from tests.test_security_lifecycle_web_finding import finding_payload, source_page

    c = context(tmp_path, auth="claude_code_oauth")
    store = c["web"]
    previous = store.read(c["run_id"])
    identity = store.start(case_id=c["case_id"], observation_sha256=previous["observation_sha256"],
        request=previous["request"], selection=previous["selection"], options=previous["options"],
        owner="worker-2", request_key="cross-instrument-readback")["run_id"]
    control = store.control(identity, owner="worker-2")
    for phase in ("search", "analysis"):
        control.reserve_model_request(phase + "-1")
        control.bind_remote_id(phase + "-1", "offline-" + phase)
        control.observe_terminal(phase + "-1", response_id="offline-" + phase, status="completed", selection=previous["selection"])
    notes = "Issuer Old Inc senior notes (OLDN) were delisted from NASDAQ effective September 1, 2026."
    for source_id, page in (("source-1", source_page(IDENTITY)),
                            ("source-2", source_page(notes, "https://ir.example.com/notes"))):
        store.add_page(identity, owner="worker-2", source_id=source_id, page=page)
    store.complete(identity, owner="worker-2", payload=finding_payload(citations=[citation(IDENTITY, ["security_identity"]),
        citation(notes, ["listing_ended", "effective_date"], "source-2")]), source_failures={}, source_requests=2,
        usage={"input_tokens": 20, "output_tokens": 40})
    reopened = LifecycleWebStore(c["profile"], clock=lambda: c["now"][0]).read(identity)
    projection = project_web_run(reopened, at=c["now"][0])
    assert reopened["finding"].action is None and "listing_change_not_supported" in reopened["finding"].block_reasons
    assert projection["finding"]["action"] is None
    c["run_id"] = identity
    before = rows(c)
    packet = prepare(c)
    assert not packet["ready"] and "web_finding_not_actionable" in packet["block_reasons"]
    assert rows(c) == before and "OLD" in c["sources"]()
