"""Conditional usage/source canary. Offline preparation is not live permission."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
CHECKPOINT = ROOT / "docs/superpowers/evidence/2026-09-07-lifecycle-web-usage"
CHECKPOINT_SEAL = None
INVENTORY_HELPERS = ROOT / "docs/superpowers/evidence/2026-09-07-lifecycle-web-oauth-canary"
sys.path.insert(0, str(INVENTORY_HELPERS))
from read_inventory import digest, read_connection, write_new_json


def selected_metadata(profile):
    with read_connection(profile) as (conn, _):
        rows = conn.execute("SELECT id,provider,auth_type,active,updated_at,expires_at FROM llm_credentials "
                            "WHERE provider='anthropic' AND auth_type='claude_code_oauth' AND active=1 ORDER BY id").fetchall()
    if len(rows) != 1:
        raise ValueError("active_claude_oauth_ambiguous")
    return dict(zip(("id", "provider", "auth_type", "active", "updated_at", "expires_at"), rows[0]))


def sec_contact(profile):
    # Exact non-secret contact field only. No .env loading or provider key reads.
    conn = sqlite3.connect(Path(profile).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute("SELECT value FROM data_provider_config WHERE provider='sec_edgar' AND field='user_agent'").fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def options():
    from src.security_lifecycle_web_pipeline import WebInvestigationOptions
    return WebInvestigationOptions(max_sources=4, max_source_requests=8, max_redirects=2,
        max_source_bytes=32 * 1024**2, max_decoded_source_bytes=128 * 1024**2,
        source_timeout_seconds=180, model_timeout_seconds=180,
        max_search_uses=4, output_token_limit=None, effort="medium")


def public_case(as_of):
    from src.security_lifecycle_web_contract import PublicInvestigationInput
    return PublicInvestigationInput(ticker="TA", issuer_name="TravelCenters of America Inc.",
        security_class="common stock", venue="NASDAQ", question="listing_status", as_of=as_of)


def require_sources(root, checkpoint, expected_seal):
    seal_path = checkpoint / "files.sha256.json"
    if hashlib.sha256(seal_path.read_bytes()).hexdigest() != expected_seal:
        raise ValueError("offline_checkpoint_changed")
    seal = json.loads(seal_path.read_text())
    if any(not (checkpoint / name).is_file() or hashlib.sha256((checkpoint / name).read_bytes()).hexdigest() != expected
           for name, expected in seal["files"].items()):
        raise ValueError("offline_checkpoint_changed")
    path = checkpoint / "source-manifest.json"
    payload = json.loads(path.read_text())
    changed = [name for name, expected in payload["files"].items()
               if not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected]
    changed += [name for name in payload["deleted_files"] if (root / name).exists()]
    if changed:
        raise ValueError("offline_admitted_source_changed")
    return {"seal_sha256": expected_seal, "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "matched_files": len(payload["files"])}


def source_identity():
    if not isinstance(CHECKPOINT_SEAL, str) or re.fullmatch(r"[a-f0-9]{64}", CHECKPOINT_SEAL) is None:
        raise ValueError("explicit_offline_checkpoint_required")
    return require_sources(ROOT, CHECKPOINT, CHECKPOINT_SEAL)


def prepared_plan(profile, as_of):
    from src.auth_drivers.claude_agent_sdk_runtime import require_reviewed_claude_agent_runtime
    from src.security_lifecycle_web_contract import validate_selection
    admitted_source = source_identity()
    runtime = require_reviewed_claude_agent_runtime()
    metadata = selected_metadata(profile)
    selected = validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", f"local:{metadata['id']}")
    return {
        "authority": "Conditional one-shot Sonnet 5 Claude OAuth envelope: separate user confirmation required; preparation is not dispatch permission",
        "as_of": as_of, "public_input": public_case(as_of).model_dump(),
        "execution": {key: getattr(selected, key) for key in ("provider", "auth_mode", "model")},
        "credential_metadata_sha256": digest(metadata),
        "credential_selection": "unique currently active Claude Code OAuth credential; no credential change",
        "options": asdict(options()), "max_model_submissions": 2,
        "max_cli_internal_turns": {"search": 6, "analysis": 2},
        "local_completion_deadline_seconds": 660,
        "no_retry": True, "no_fallback": True, "no_profile_action": True,
        "runtime": {key: value for key, value in asdict(runtime).items() if key != "cli_path"},
        "cli_binary_sha256": hashlib.sha256(runtime.cli_path.read_bytes()).hexdigest(),
        "helper_model_policy": "both current and legacy overrides must equal claude-sonnet-5; no Haiku",
        "offline_source": admitted_source,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "production_writes": False, "production_route_change": False,
        "oracle": {
            "auth": "Every phase must observe literal apiKeySource=none and the selected model.",
            "protocol": "Real search, at least one captured public page, complete analysis and durable readback.",
            "safety": "No executable/file/MCP tool, substitute credential/model or automatic human confirmation.",
            "quality": "TA must bind TravelCenters common stock, not senior notes or a generic abbreviation. Acquisition alone is not delisting; BP is not an alias. Nonessential unread sources are disclosed; missing essential proof or contrary active/OTC evidence blocks action.",
        },
        "limits_not_claimed": ["Exact native/hidden provider HTTP count", "No hidden provider-internal retry", "Other auth channels are live verified"],
    }


def _literal(value, allowed):
    return value if isinstance(value, str) and value in allowed else "unreviewed"


def _model(value):
    return value if isinstance(value, str) and re.fullmatch(r"claude-[a-z0-9-]{1,100}", value) else "unreviewed"


def usage_witness(value):
    if value is None:
        return {"shape": "absent", "models": []}
    if not isinstance(value, dict):
        return {"shape": "invalid", "models": []}
    fields = {"inputTokens": "input_tokens", "outputTokens": "output_tokens",
              "cacheReadInputTokens": "cache_read_input_tokens",
              "cacheCreationInputTokens": "cache_creation_input_tokens", "webSearchRequests": "web_search_requests"}
    models = []
    for model, counts in value.items():
        row = {"model": _model(model), "shape": "object" if isinstance(counts, dict) else "invalid"}
        invalid = []
        for raw_name, name in fields.items():
            count = counts.get(raw_name) if isinstance(counts, dict) else None
            row[name] = count if type(count) is int and count >= 0 else None
            if isinstance(counts, dict) and raw_name in counts and row[name] is None:
                invalid.append(name)
        row["invalid_fields"] = invalid
        models.append(row)
    return {"shape": "object", "models": models}


def message_witness(message, requested_session_id):
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, ToolUseBlock
    if isinstance(message, SystemMessage) and message.subtype == "init":
        data = message.data if isinstance(message.data, dict) else {}
        auth = "absent" if "apiKeySource" not in data else "null" if data["apiKeySource"] is None else _literal(data["apiKeySource"], {"none", "user", "project", "environment", "apiKey"})
        tools = data.get("tools")
        return {"kind": "init", "api_key_source": auth, "model": _model(data.get("model")),
                "session_matches_request": isinstance(data.get("session_id"), str) and data["session_id"] == requested_session_id,
                "tools": [_literal(name, {"WebSearch", "StructuredOutput", "Bash", "Read", "Write", "Edit", "Task", "Agent", "WebFetch", "ToolSearch"}) for name in tools] if isinstance(tools, list) else None,
                "mcp_server_count": len(data["mcp_servers"]) if isinstance(data.get("mcp_servers"), list) else None}
    if isinstance(message, AssistantMessage):
        return {"kind": "assistant", "model": _model(message.model), "error_present": message.error is not None,
                "tool_names": [_literal(block.name, {"WebSearch", "StructuredOutput"}) for block in message.content if isinstance(block, ToolUseBlock)]}
    if isinstance(message, ResultMessage):
        return {"kind": "result", "subtype": _literal(message.subtype, {"success", "error_during_execution", "error_max_turns"}),
                "session_matches_request": isinstance(message.session_id, str) and message.session_id == requested_session_id,
                "terminal_reason": _literal(message.terminal_reason, {"completed", "aborted_streaming", "aborted_tools", "max_turns"}),
                "is_error": message.is_error is True, "num_turns": message.num_turns if type(message.num_turns) is int else None,
                "model_usage_models": [_model(model) for model in message.model_usage] if isinstance(message.model_usage, dict) else None,
                "model_usage": usage_witness(message.model_usage),
                "permission_denial_count": len(message.permission_denials or []),
                "has_structured_output": message.structured_output is not None}
    return {"kind": _literal(type(message).__name__, {"UserMessage", "SystemMessage", "RateLimitEvent", "StreamEvent"})}


def execute(profile, plan, work):
    from claude_agent_sdk import ClaudeSDKClient
    from src.auth_drivers import lifecycle_web_claude
    from src.auth_drivers.lifecycle_web_models import credential_generation, resolve_web_credential
    from src.auth_drivers.subscription_structured_output import _transport_child_pid
    from src.auth_drivers.token_store import get_token_store
    from src.lifecycle_public_sources import PublicSourceReader
    from src.lifecycle_web_controller import LifecycleWebController
    from src.lifecycle_web_sec_sources import SecSourcePolicy
    from src.lifecycle_web_store import LifecycleWebStore, install_web_journal
    from src.security_lifecycle_schema import create_profile_schema
    from src.security_lifecycle_web_contract import validate_selection
    from src.security_lifecycle_web_pipeline import investigate

    if work.exists() or not any(work.resolve().is_relative_to(base) for base in (Path("/tmp"), Path("/dev/shm"))):
        raise ValueError("canary_requires_new_private_temporary_directory")
    if prepared_plan(profile, plan["as_of"]) != plan:
        raise ValueError("canary_plan_changed")
    metadata = selected_metadata(profile)
    selected = validate_selection("anthropic", "claude_code_oauth", plan["execution"]["model"], f"local:{metadata['id']}")
    work.mkdir(mode=0o700)
    os.umask(0o077)
    write_new_json(work / "authorized-plan.json", plan)
    metrics = {"started_at": datetime.now(timezone.utc).isoformat(), "sdk_query_submissions": 0,
               "token_loads": 0, "sessions": [], "source_reads": [], "stages": [], "phase_replies": [], "local_children_reaped": []}
    sensitive = []

    class ReadOnlySelectedStore:
        def get(self, identity):
            current = selected_metadata(profile)
            if identity != selected.credential_id or current != metadata:
                raise ValueError("selected_credential_changed")
            # OAuth resolution does not consume CredentialStore.secret.
            return SimpleNamespace(**current, secret=None)

    token_store = get_token_store(dev_path=os.environ.get("ARKSCOPE_TOKEN_STORE_PATH") or profile.parent / "auth_tokens.json")
    metrics["token_backend"] = token_store.backend

    class OneTokenRead:
        def load(self, **kwargs):
            if metrics["token_loads"] or kwargs != {"provider": selected.provider, "auth_mode": selected.auth_mode, "credential_id": selected.credential_id}:
                raise ValueError("canary_credential_read_budget")
            metrics["token_loads"] += 1
            record = token_store.load(**kwargs)
            if record is not None:
                sensitive.append(record.access_token)
                if record.refresh_token:
                    sensitive.append(record.refresh_token)
            return record

    class ObservedClient(ClaudeSDKClient):
        def __init__(self, *, options):
            expected_model = plan["execution"]["model"]
            if (options.model != expected_model or expected_model != "claude-sonnet-5" or options.fallback_model is not None
                    or options.env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL") != expected_model
                    or options.env.get("ANTHROPIC_SMALL_FAST_MODEL") != expected_model):
                raise ValueError("canary_helper_model_not_pinned")
            super().__init__(options=options)
            self.requested_session_id = options.session_id
            self.events = []
            metrics["sessions"].append({"model": options.model, "tools": options.tools,
                "helper_model_overrides": {"current": options.env["ANTHROPIC_DEFAULT_HAIKU_MODEL"],
                                           "legacy": options.env["ANTHROPIC_SMALL_FAST_MODEL"]},
                "allowed_tools": options.allowed_tools, "disallowed_tools": options.disallowed_tools,
                "strict_mcp_config": options.strict_mcp_config, "setting_sources": options.setting_sources,
                "max_turns": options.max_turns, "fallback_model": options.fallback_model,
                "permission_mode": options.permission_mode,
                "api_key_env_empty": not options.env.get("ANTHROPIC_API_KEY"),
                "api_token_env_empty": not options.env.get("ANTHROPIC_AUTH_TOKEN"),
                "cli_max_retries": options.env.get("CLAUDE_CODE_MAX_RETRIES"),
                "auto_compact_disabled": options.env.get("DISABLE_AUTO_COMPACT"), "events": self.events})

        async def query(self, prompt, **kwargs):
            if metrics["sdk_query_submissions"] >= 2:
                raise ValueError("canary_model_budget")
            metrics["sdk_query_submissions"] += 1
            return await super().query(prompt, **kwargs)

        async def receive_response(self):
            async for message in super().receive_response():
                self.events.append(message_witness(message, self.requested_session_id))
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

    contact = sec_contact(profile)
    metrics["sec_contact_configured"] = bool(contact)

    class ObservedReader(PublicSourceReader):
        def __init__(self, limits):
            # A missing contact remains a typed SEC rejection, never an env fallback.
            super().__init__(limits, sec_policy=SecSourcePolicy(user_agent=contact or ""))

        def read(self, url):
            started = self.request_count
            value = {"url": url, "requests_before": started}
            metrics["source_reads"].append(value)
            try:
                page = super().read(url)
                value.update(status="captured", url=page.url, document_sha256=page.body_sha256,
                             text_sha256=page.text_sha256, capture_sha256=page.capture_sha256, text_characters=len(page.text))
                return page
            except Exception as exc:
                from src.lifecycle_public_sources import SourceReadError
                value.update(status="failed", code=str(exc) if isinstance(exc, SourceReadError) else "source_read_failed")
                raise
            finally:
                value["requests_after"] = self.request_count
                value["observations"] = [asdict(item) for item in self.observations if item.request_index > started]

    async def observed_runner(request, credential, control, **kwargs):
        stage = kwargs.pop("on_stage")
        journal_reply = kwargs.pop("on_reply")
        def record_stage(value):
            metrics["stages"].append(value)
            stage(value)
        def reply(call, result):
            journal_reply(call, result)
            metrics["phase_replies"].append({"phase": call.phase, "usage": result.usage,
                                            "usage_observation": result.usage_observation})
            if any(secret and secret in json.dumps(result.output) for secret in sensitive):
                raise ValueError("canary_redaction_gate")
            write_new_json(work / (call.phase + "-output.json"), result.output)
        return await investigate(request, credential, control, on_stage=record_stage, on_reply=reply, **kwargs)

    def before_dispatch():
        if selected_metadata(profile) != metadata:
            raise ValueError("selected_credential_changed")

    path = work / "profile.sqlite"
    at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as conn:
        create_profile_schema(conn)
        conn.execute("INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)", ("canary-TA", "listing_authority", "listing:TA", "TA", at, at))
        conn.commit()
        install_web_journal(conn, at=at)
    store = LifecycleWebStore(path)
    original_factory = lifecycle_web_claude._client
    lifecycle_web_claude._client = lambda options: ObservedClient(options=options)
    controller = LifecycleWebController(store, before_dispatch=before_dispatch, reader_factory=ObservedReader,
        runner=observed_runner, credential_loader=lambda selection: resolve_web_credential(selection, store=ReadOnlySelectedStore(), token_store=OneTokenRead()))
    try:
        request = public_case(plan["as_of"])
        run = controller.start(case_id="canary-TA", observation_sha256=digest(request.model_dump()), request=request,
            selection=selected, options=options(), request_key="one-explicit-canary",
            credential_generation=credential_generation(SimpleNamespace(**metadata, secret=None)))
        deadline = time.monotonic() + plan["local_completion_deadline_seconds"]
        while controller.is_local_running(run["run_id"]) and time.monotonic() < deadline:
            time.sleep(0.1)
        if controller.is_local_running(run["run_id"]):
            controller.cancel(run["run_id"])
        controller.close()
        value = controller.read(run["run_id"])
        metrics["finished_at"] = datetime.now(timezone.utc).isoformat()
        metrics["journal_calls"] = {key: {"terminal": item["terminal"]} for key, item in store.read(run["run_id"])["calls"].items()}
        metrics["journal_model_submissions"] = value["model_submissions"]
        metrics["result_status"] = value["status"]
        metrics["failure_code"] = value["failure_code"]
        metrics["selected_metadata_unchanged"] = selected_metadata(profile) == metadata
        metrics["source_http_requests"] = max((row["requests_after"] for row in metrics["source_reads"]), default=0)
        with sqlite3.connect(path) as conn:
            metrics["human_assessments_created"] = conn.execute("SELECT COUNT(*) FROM security_lifecycle_assessments").fetchone()[0]
            metrics["human_adoptions_created"] = conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0]
        for body in (value, metrics):
            encoded = json.dumps(body)
            if any(secret and secret in encoded for secret in sensitive):
                raise ValueError("canary_redaction_gate")
        write_new_json(work / "result.json", value)
        write_new_json(work / "metrics.json", metrics)
        print(json.dumps({"status": value["status"], "failure_code": value["failure_code"],
            "model_submissions": metrics["sdk_query_submissions"], "source_http_requests": metrics["source_http_requests"],
            "human_adoptions": metrics["human_adoptions_created"]}, indent=2), flush=True)
        return 0 if value["status"] == "succeeded" else 1
    finally:
        controller.close()
        lifecycle_web_claude._client = original_factory
        sensitive.clear()


def main():
    global CHECKPOINT_SEAL
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--checkpoint-seal", required=True)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approval-sha256")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    CHECKPOINT_SEAL = args.checkpoint_seal
    if args.prepare:
        plan = prepared_plan(args.profile, datetime.now(timezone.utc).date().isoformat())
        write_new_json(args.prepare, plan)
        print(json.dumps({"approval_sha256": digest(plan), "execution": plan["execution"], "max_model_submissions": 2}))
        return 0
    if not args.plan or not args.work or not args.approval_sha256:
        raise ValueError("explicit_canary_plan_required")
    plan = json.loads(args.plan.read_text())
    if digest(plan) != args.approval_sha256:
        raise ValueError("canary_plan_changed")
    return execute(args.profile.resolve(), plan, args.work)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"harness_error_type": type(exc).__name__}))
        sys.exit(1)
