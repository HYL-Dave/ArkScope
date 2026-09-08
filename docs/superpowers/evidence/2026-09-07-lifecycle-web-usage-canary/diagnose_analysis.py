"""One authorized analysis-only diagnostic using sealed public captures."""

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_canary as original


class AnalysisCaptured(Exception):
    def __init__(self, call):
        self.call = call


async def capture_analysis(row, search_output, source_reads):
    from src.auth_drivers.lifecycle_web_models import ModelReply, WebCredential
    from src.lifecycle_public_sources import SourceReadError
    from src.security_lifecycle_web_contract import RunControl
    from src import security_lifecycle_web_pipeline as pipeline

    captured = {page.url: page for page in row["pages"].values()}
    pages, failures = {}, {}
    for candidate, receipt in zip(search_output["sources"], source_reads, strict=True):
        if receipt["status"] == "captured":
            page = captured[receipt["url"]]
            if (receipt["document_sha256"] != page.body_sha256 or receipt["text_sha256"] != page.text_sha256
                    or receipt["capture_sha256"] != page.capture_sha256):
                raise ValueError("capture_receipt_changed")
            # A frozen redirect receipt binds the requested URL to the final page.
            pages[candidate] = page
        elif receipt["status"] == "failed" and receipt["url"] == candidate:
            failures[candidate] = receipt["code"]
        else:
            raise ValueError("capture_receipt_changed")

    class CapturedReader:
        request_count = 0
        observations = ()

        def __init__(self, limits):
            pass

        def read(self, url):
            if url in failures:
                raise SourceReadError(failures[url])
            if url not in pages:
                raise ValueError("uncaptured_source_requested")
            return pages[url]

        def request_stop(self):
            pass

    async def replay_search(call, credential, control):
        if call.phase == "analysis":
            raise AnalysisCaptured(call)
        if call.phase != "search":
            raise ValueError("unexpected_offline_phase")
        control.reserve_model_request(call.call_id)
        control.bind_remote_id(call.call_id, "offline-search-replay")
        control.observe_terminal(call.call_id, response_id="offline-search-replay", status="completed", selection=call.selection)
        return ModelReply("offline-search-replay", search_output, {"input_tokens": None, "output_tokens": None})

    with patch.object(pipeline, "call_lifecycle_web_model", replay_search):
        try:
            await pipeline.investigate(row["request"], WebCredential(row["selection"]),
                RunControl(selection=row["selection"], max_model_requests=2), options=row["options"], reader_factory=CapturedReader)
        except AnalysisCaptured as captured:
            return captured.call
    raise ValueError("analysis_not_reached")


class Diagnostics:
    def __init__(self, schema, session, token, *, final_json=False):
        from jsonschema import Draft202012Validator
        self.validator = Draft202012Validator(schema)
        self.session = session
        self.token = token
        self.owned_tools = set()
        self.final_json = final_json

    def text(self, value):
        from src.auth_drivers.claude_code_sdk_driver import _redact_bridge
        value = _redact_bridge(value, self.token).replace(self.session, "[SESSION]")
        for identity in self.owned_tools:
            value = value.replace(identity, "[TOOL]")
        return value

    def message(self, message):
        from claude_agent_sdk import AssistantMessage, ResultMessage, ToolResultBlock, ToolUseBlock, UserMessage
        result = original.message_witness(message, self.session)
        if isinstance(message, AssistantMessage):
            outputs = []
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name == "StructuredOutput":
                    self.owned_tools.add(block.id)
                    errors = [{"keyword": str(error.validator), "schema_path": list(error.absolute_schema_path),
                               "instance_path": list(error.absolute_path), "message": self.text(error.message)}
                              for error in self.validator.iter_errors(block.input)]
                    outputs.append({"schema_valid": not errors, "schema_errors": errors})
            result["structured_output_attempts"] = outputs
        elif isinstance(message, UserMessage):
            result["owned_tool_results"] = []
            for block in message.content if isinstance(message.content, list) else []:
                if isinstance(block, ToolResultBlock) and block.tool_use_id in self.owned_tools:
                    result["owned_tool_results"].append({"is_error": block.is_error,
                        "content": self.text(json.dumps(block.content, ensure_ascii=True))})
        elif isinstance(message, ResultMessage):
            result["errors"] = [self.text(item) for item in message.errors or []]
            if (self.final_json and message.session_id == self.session and message.subtype == "success"
                    and message.terminal_reason == "completed" and not message.is_error):
                from src.auth_drivers.lifecycle_web_models import validate_output, WebModelError
                try:
                    if not isinstance(message.result, str) or message.structured_output is not None:
                        raise WebModelError("model_output_invalid")
                    output = validate_output(message.result, self.validator.schema)
                except WebModelError:
                    result["final_json_schema_valid"] = False
                else:
                    if self.token and self.token in json.dumps(output):
                        raise ValueError("diagnostic_redaction_gate")
                    result.update(final_json_schema_valid=True, native_output=output,
                                  native_output_is_observation_not_host_acceptance=True)
        return result


def snapshot(directory):
    names = ("authorized-plan.json", "search-output.json", "result.json", "metrics.json", "profile.sqlite")
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in names}


async def execute(profile, capture, work, checkpoint_seal, admission=None):
    from claude_agent_sdk import ClaudeSDKClient
    from src.auth_drivers import lifecycle_web_claude as adapter
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential, WebModelError
    from src.auth_drivers.subscription_structured_output import _transport_child_pid
    from src.auth_drivers.token_store import get_token_store
    from src.lifecycle_web_store import LifecycleWebStore
    from src.security_lifecycle_web_contract import RunControl
    from src.security_lifecycle_web_finding import FindingFormatError

    if admission is None:
        original.CHECKPOINT_SEAL = checkpoint_seal
        admitted = original.source_identity()
        capture_source = admitted
        expected_capture = None
    else:
        admitted = original.require_sources(original.ROOT, admission, checkpoint_seal)
        verification = json.loads((admission / "verification.json").read_text())
        capture_source = verification.get("prior_source")
        expected_capture = verification.get("original_capture_files")
    if work.exists() or not work.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("new_temporary_output_required")
    capture = capture.resolve()
    if not capture.is_relative_to(Path("/tmp")):
        raise ValueError("temporary_capture_required")
    before = snapshot(capture)
    if admission is not None and "analysis_capture_receipts" in verification:
        matches = [receipt for receipt in verification["analysis_capture_receipts"] if receipt["files"] == before]
        if len(matches) != 1:
            raise ValueError("original_capture_changed")
        capture_source = matches[0]["source_checkpoint"]
        expected_capture = matches[0]["files"]
    if capture_source is None or (admission is not None and expected_capture is None):
        raise ValueError("capture_binding_absent")
    if expected_capture is not None and before != expected_capture:
        raise ValueError("original_capture_changed")
    prior_metrics = json.loads((capture / "metrics.json").read_text())
    prior_result = json.loads((capture / "result.json").read_text())
    plan = json.loads((capture / "authorized-plan.json").read_text())
    if plan["offline_source"] != capture_source or prior_result["failure_code"] != "model_result_incomplete":
        raise ValueError("unexpected_capture")
    metadata = original.selected_metadata(profile)
    if original.digest(metadata) != plan["credential_metadata_sha256"]:
        raise ValueError("selected_credential_changed")
    row = LifecycleWebStore(capture / "profile.sqlite").read(prior_result["run_id"])
    if row["selection"].credential_id != f"local:{metadata['id']}":
        raise ValueError("selected_credential_changed")
    call = await capture_analysis(row, json.loads((capture / "search-output.json").read_text()), prior_metrics["source_reads"])
    if call.phase != "analysis" or call.selection.model != "claude-sonnet-5":
        raise ValueError("unexpected_model_call")
    work.mkdir(mode=0o700)
    os.umask(0o077)
    metrics = {"kind": "analysis_only_diagnostic_not_new_end_to_end_run", "source_checkpoint": admitted,
        "capture_source_checkpoint": capture_source,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "capture_files_sha256": before,
        "prompt_sha256": hashlib.sha256(call.prompt.encode()).hexdigest(), "schema_sha256": original.digest(call.output_schema),
        "started_at": datetime.now(timezone.utc).isoformat(), "sdk_submissions": 0, "source_http_requests": 0,
        "search_submissions": 0, "token_loads": 0, "events": [], "local_children_reaped": []}
    original.write_new_json(work / "prepared.json", metrics)
    tokens = get_token_store(dev_path=os.environ.get("ARKSCOPE_TOKEN_STORE_PATH") or profile.parent / "auth_tokens.json")
    secrets = []

    class SelectedStore:
        def get(self, identity):
            if identity != call.selection.credential_id or original.selected_metadata(profile) != metadata:
                raise ValueError("selected_credential_changed")
            return SimpleNamespace(**metadata, secret=None)

    class OneToken:
        def load(self, **kwargs):
            if metrics["token_loads"] or kwargs != {"provider": call.selection.provider, "auth_mode": call.selection.auth_mode,
                                                    "credential_id": call.selection.credential_id}:
                raise ValueError("selected_token_read_budget")
            metrics["token_loads"] += 1
            record = tokens.load(**kwargs)
            if record is not None:
                secrets.extend(value for value in (record.access_token, record.refresh_token) if value)
            return record

    credential = resolve_web_credential(call.selection, store=SelectedStore(), token_store=OneToken())

    class ObservedClient(ClaudeSDKClient):
        def __init__(self, options):
            if (options.model != "claude-sonnet-5" or options.fallback_model is not None or options.max_turns != 2
                    or options.tools != [] or options.output_format is not None
                    or options.mcp_servers != {} or options.setting_sources != []
                    or options.strict_mcp_config is not True or options.permission_mode != "dontAsk"
                    or options.env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL") != options.model
                    or options.env.get("ANTHROPIC_SMALL_FAST_MODEL") != options.model
                    or options.env.get("CLAUDE_CODE_MAX_RETRIES") != "0"):
                raise ValueError("diagnostic_envelope_changed")
            super().__init__(options=options)
            self.diagnostic = Diagnostics(call.output_schema, options.session_id, credential.token_record.access_token, final_json=True)
            _, separator, embedded = options.system_prompt.partition("\nOutput schema:\n")
            metrics["options"] = {"system_prompt_sha256": hashlib.sha256(options.system_prompt.encode()).hexdigest(),
                "output_mode": "final_json", "native_output_format": options.output_format,
                "output_schema_sha256": original.digest(call.output_schema),
                "prompt_schema_matches_contract": bool(separator) and json.loads(embedded) == call.output_schema,
                "max_turns": options.max_turns, "tools": options.tools, "model": options.model,
                "fallback_model": options.fallback_model, "cli_max_retries": options.env.get("CLAUDE_CODE_MAX_RETRIES")}

        async def query(self, prompt, **kwargs):
            if metrics["sdk_submissions"] or prompt != call.prompt:
                raise ValueError("diagnostic_submission_budget")
            metrics["sdk_submissions"] += 1
            return await super().query(prompt, **kwargs)

        async def receive_response(self):
            async for message in super().receive_response():
                metrics["events"].append(self.diagnostic.message(message))
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
            result = await adapter.call_claude_web(call, credential, control)
        metrics.update(status="completed", usage=result.usage, usage_observation=result.usage_observation)
        encoded = json.dumps(result.output)
        if any(secret in encoded for secret in secrets):
            raise ValueError("diagnostic_redaction_gate")
        original.write_new_json(work / "analysis-output.json", result.output)
        from src.lifecycle_source_context import select_source_context
        from src.security_lifecycle_web_finding import validate_finding
        contexts = {identity: select_source_context(row["request"], page).to_material()
                    for identity, page in row["pages"].items()}
        finding = validate_finding(row["request"], result.output, row["pages"],
            unread_source_count=sum(item["status"] == "failed" for item in prior_metrics["source_reads"]),
            source_context=contexts)
        metrics["validated_finding"] = {"action": finding.action, "block_reasons": finding.block_reasons,
            "unique_passage_count": finding.unique_passage_count, "event_kind": finding.finding.event_kind}
    except WebModelError as exc:
        metrics.update(status="failed", failure_code=exc.code)
    except FindingFormatError as exc:
        metrics.update(status="failed", failure_code=str(exc), failure_stage="finding_validation")
    finally:
        metrics.update(finished_at=datetime.now(timezone.utc).isoformat(), model_requests=control.model_requests,
            terminal_statuses=control.terminal_statuses, stop_state=control.stop_state,
            selected_metadata_unchanged=original.selected_metadata(profile) == metadata,
            original_capture_unchanged=snapshot(capture) == before)
        if any(secret in json.dumps(metrics) for secret in secrets):
            raise ValueError("diagnostic_redaction_gate")
        original.write_new_json(work / "metrics.json", metrics)
        secrets.clear()
    print(json.dumps({key: metrics.get(key) for key in ("status", "failure_code", "sdk_submissions", "source_http_requests")}))
    return 0 if metrics["status"] == "completed" else 1


def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--checkpoint-seal", required=True)
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()
    return asyncio.run(execute(args.profile.resolve(), args.capture, args.work, args.checkpoint_seal, args.admission))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"harness_error_type": type(exc).__name__}))
        sys.exit(1)
