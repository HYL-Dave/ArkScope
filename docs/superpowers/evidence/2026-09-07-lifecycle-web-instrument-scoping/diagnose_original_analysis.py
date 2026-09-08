"""One explicitly diagnosed analysis of recorded pages plus a public original.

This is not another live search/read investigation and does not rewrite the
completed non-actionable run. It separates missing source coverage from model
and citation-validation behavior.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.with_name("2026-09-07-lifecycle-web-usage-canary")))
import claude_canary as original
from diagnose_analysis import capture_analysis


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_final(value, schema):
    from jsonschema import Draft202012Validator
    from src.auth_drivers.lifecycle_web_models import validate_output, WebModelError
    result = {"result_type": type(value).__name__, "characters": len(value) if isinstance(value, str) else None}
    try:
        if not isinstance(value, str):
            raise WebModelError("model_output_invalid")
        validate_output(value, schema)
    except WebModelError as exc:
        result.update(host_schema_valid=False, code=str(exc))
    else:
        result["host_schema_valid"] = True
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            result["json_error"] = {"line": exc.lineno, "column": exc.colno, "reason": exc.msg}
        else:
            result["schema_errors"] = [{"keyword": str(error.validator), "path": list(error.absolute_path),
                                        "schema_path": list(error.absolute_schema_path)}
                                       for error in Draft202012Validator(schema).iter_errors(parsed)]
    return result


async def prepared_call(capture, document):
    from src.lifecycle_public_sources import PublicSourcePage, _capture_digest
    from src.lifecycle_web_store import LifecycleWebStore
    saved = json.loads((capture / "result.json").read_text())
    row = LifecycleWebStore(capture / "profile.sqlite").read(saved["run_id"])
    searches = json.loads((capture / "search-output.json").read_text())
    receipts = json.loads((capture / "metrics.json").read_text())["source_reads"]
    page = PublicSourcePage(**json.loads((document / "document-page.json").read_text()))
    assert _capture_digest(page) == page.capture_sha256
    metadata = json.loads((document / "metrics.json").read_text())
    assert metadata["status"] == "captured_primary_document"
    assert metadata["source_http_campaign_used"] == 9 and metadata["source_http_campaign_remaining"] == 15
    last = metadata["reads"][-1]
    assert (page.url, page.body_sha256, page.text_sha256, page.capture_sha256) == (
        last["url"], last["body_sha256"], last["text_sha256"], last["capture_sha256"])
    assert page.url not in searches["sources"]
    row["pages"] = {**row["pages"], f"source-{len(searches['sources']) + 1}": page}
    searches["sources"] = [*searches["sources"], page.url]
    receipts = [*receipts, {"url": page.url, "status": "captured", "document_sha256": page.body_sha256,
        "text_sha256": page.text_sha256, "capture_sha256": page.capture_sha256}]
    return row, await capture_analysis(row, searches, receipts)


async def execute(args):
    from claude_agent_sdk import ClaudeSDKClient
    from src.auth_drivers import lifecycle_web_claude as adapter
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential, WebModelError
    from src.auth_drivers.subscription_structured_output import _transport_child_pid
    from src.auth_drivers.token_store import get_token_store
    from src.security_lifecycle_web_contract import RunControl
    from src.lifecycle_source_context import select_source_context
    from src.security_lifecycle_web_finding import validate_finding, FindingFormatError

    admitted = original.require_sources(ROOT, HERE / "admission", args.seal)
    receipt = json.loads((HERE / "live-r1/verification.json").read_text())
    capture, document = Path("/tmp/lifecycle-instrument-live-r1"), Path("/tmp/lifecycle-instrument-document-r1")
    before = {name: sha(capture / name) for name in receipt["raw_files_sha256"]}
    assert before == receipt["raw_files_sha256"]
    document_before = {path.name: sha(path) for path in document.iterdir() if path.is_file()}
    row, call = await prepared_call(capture, document)
    metadata = original.selected_metadata(args.profile)
    plan = json.loads((capture / "authorized-plan.json").read_text())
    assert original.digest(metadata) == plan["credential_metadata_sha256"]
    assert call.selection.credential_id == f"local:{metadata['id']}" and call.selection.model == "claude-sonnet-5"
    assert call.phase == "analysis" and call.timeout_seconds == 600
    work = args.work.resolve()
    assert not work.exists() and work.is_relative_to(Path("/tmp"))
    work.mkdir(mode=0o700)
    os.umask(0o077)
    metrics = {"kind": "analysis_only_with_host_followed_public_original_not_fresh_end_to_end",
        "source_checkpoint": admitted, "harness_sha256": sha(Path(__file__)),
        "capture_files_sha256": before, "document_capture_sha256": document_before,
        "prompt_sha256": hashlib.sha256(call.prompt.encode()).hexdigest(),
        "started_at": datetime.now(timezone.utc).isoformat(), "sdk_submissions": 0, "source_http_requests": 0,
        "search_submissions": 0, "token_loads": 0, "events": [], "local_children_reaped": []}
    original.write_new_json(work / "prepared.json", metrics)
    tokens = get_token_store(dev_path=os.environ.get("ARKSCOPE_TOKEN_STORE_PATH") or args.profile.parent / "auth_tokens.json")
    secrets = []

    class SelectedStore:
        def get(self, identity):
            if identity != call.selection.credential_id or original.selected_metadata(args.profile) != metadata:
                raise ValueError("selected_credential_changed")
            return SimpleNamespace(**metadata, secret=None)

    class OneToken:
        def load(self, **kwargs):
            if metrics["token_loads"] or kwargs != {"provider": call.selection.provider,
                    "auth_mode": call.selection.auth_mode, "credential_id": call.selection.credential_id}:
                raise ValueError("selected_token_read_budget")
            metrics["token_loads"] += 1
            value = tokens.load(**kwargs)
            if value is not None:
                secrets.extend(item for item in (value.access_token, value.refresh_token) if item)
            return value

    credential = resolve_web_credential(call.selection, store=SelectedStore(), token_store=OneToken())

    class ObservedClient(ClaudeSDKClient):
        def __init__(self, options):
            if (options.model != "claude-sonnet-5" or options.fallback_model is not None or options.max_turns != 2
                    or options.tools != [] or options.output_format is not None or options.mcp_servers != {}
                    or options.setting_sources != [] or options.strict_mcp_config is not True
                    or options.env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL") != options.model
                    or options.env.get("ANTHROPIC_SMALL_FAST_MODEL") != options.model
                    or options.env.get("CLAUDE_CODE_MAX_RETRIES") != "0"
                    or options.env.get("ANTHROPIC_API_KEY") or options.env.get("ANTHROPIC_AUTH_TOKEN")):
                raise ValueError("diagnostic_envelope_changed")
            self.requested_session = options.session_id
            super().__init__(options=options)

        async def query(self, prompt, **kwargs):
            if metrics["sdk_submissions"] or prompt != call.prompt:
                raise ValueError("diagnostic_submission_budget")
            metrics["sdk_submissions"] += 1
            return await super().query(prompt, **kwargs)

        async def receive_response(self):
            from claude_agent_sdk import ResultMessage
            async for message in super().receive_response():
                metrics["events"].append(original.message_witness(message, self.requested_session))
                if isinstance(message, ResultMessage) and message.session_id == self.requested_session:
                    native = {"result_text": message.result, "structured_output": message.structured_output}
                    assert not any(secret in json.dumps(native) for secret in secrets)
                    original.write_new_json(work / "native-final.json", native)
                    metrics["native_final"] = inspect_final(message.result, call.output_schema)
                    metrics["native_final"]["private_capture_sha256"] = sha(work / "native-final.json")
                yield message

        async def disconnect(self):
            pid = _transport_child_pid(getattr(self, "_transport", None))
            try:
                return await super().disconnect()
            finally:
                reaped = None
                if pid is not None:
                    try:
                        os.kill(pid, 0)
                        reaped = False
                    except ProcessLookupError:
                        reaped = True
                metrics["local_children_reaped"].append(reaped)

    control = RunControl(selection=call.selection, max_model_requests=1)
    try:
        with patch.object(adapter, "_client", ObservedClient):
            reply = await adapter.call_claude_web(call, credential, control)
        assert not any(secret in json.dumps(reply.output) for secret in secrets)
        original.write_new_json(work / "analysis-output.json", reply.output)
        contexts = {key: select_source_context(row["request"], page).to_material() for key, page in row["pages"].items()}
        finding = validate_finding(row["request"], reply.output, row["pages"], unread_source_count=1, source_context=contexts)
        metrics.update(status="completed", usage=reply.usage, usage_observation=reply.usage_observation,
            validated_finding={"action": finding.action, "block_reasons": list(finding.block_reasons),
                "unique_passage_count": finding.unique_passage_count})
    except (WebModelError, FindingFormatError) as exc:
        metrics.update(status="failed", code=str(exc))
    finally:
        metrics.update(finished_at=datetime.now(timezone.utc).isoformat(), model_requests=control.model_requests,
            terminal_statuses=control.terminal_statuses, selected_metadata_unchanged=original.selected_metadata(args.profile) == metadata,
            original_capture_unchanged={name: sha(capture / name) for name in before} == before,
            document_capture_unchanged={name: sha(document / name) for name in document_before} == document_before)
        assert not any(secret in json.dumps(metrics) for secret in secrets)
        original.write_new_json(work / "metrics.json", metrics)
        secrets.clear()
    print(json.dumps({key: metrics.get(key) for key in ("status", "code", "sdk_submissions", "source_http_requests", "validated_finding")}))


def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--seal", required=True)
    args = parser.parse_args()
    return asyncio.run(execute(args))


if __name__ == "__main__":
    main()
