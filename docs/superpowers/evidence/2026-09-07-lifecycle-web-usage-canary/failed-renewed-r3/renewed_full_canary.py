"""Renew the full live gate with only the four remaining source HTTP attempts."""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import claude_canary as original


HTTP_LIMIT = 8
R1_SOURCE_REQUESTS = 4


def configure(admission):
    prior = Path(__file__).with_name("failed-live-r1")
    seal_path = prior / "files.sha256.json"
    if hashlib.sha256(seal_path.read_bytes()).hexdigest() != "a7df8829579c6069ae4b5b2136f825864aead543b6a5caf1ee20b170c9d50093":
        raise ValueError("prior_live_receipt_changed")
    receipt = json.loads(seal_path.read_text())
    if any(hashlib.sha256((prior / name).read_bytes()).hexdigest() != expected for name, expected in receipt["files"].items()):
        raise ValueError("prior_live_receipt_changed")
    metrics = json.loads((prior / "live-metrics.json").read_text())
    if metrics["source_http_requests"] != R1_SOURCE_REQUESTS:
        raise ValueError("source_budget_changed")
    base_options, base_plan = original.options, original.prepared_plan
    original.CHECKPOINT = admission.resolve()
    original.options = lambda: replace(base_options(), max_source_requests=HTTP_LIMIT - R1_SOURCE_REQUESTS)

    def plan(profile, as_of):
        value = base_plan(profile, as_of)
        limits = value.pop("max_cli_internal_turns")
        value.update(
            authority="User-authorized necessary additional Sonnet 5 verification; same subscription only; no automatic retry or fallback",
            renewal_harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            source_http_campaign_budget={"limit": HTTP_LIMIT, "already_used": R1_SOURCE_REQUESTS,
                                         "this_run_maximum": HTTP_LIMIT - R1_SOURCE_REQUESTS},
            max_cli_tool_round_trips=limits,
            max_reported_total_turns={phase: limit + 1 for phase, limit in limits.items()},
        )
        return value
    original.prepared_plan = plan


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--work", type=Path)
    args, remaining = parser.parse_known_args()
    configure(args.admission)
    if args.work is not None:
        remaining += ["--work", str(args.work)]
    sys.argv = [sys.argv[0], *remaining]
    from claude_agent_sdk import ClaudeSDKClient, ResultMessage
    import claude_agent_sdk
    from diagnose_analysis import Diagnostics
    from jsonschema import Draft202012Validator
    from unittest.mock import patch
    observations = []

    class DiagnosticClient(ClaudeSDKClient):
        def __init__(self, *, options):
            super().__init__(options=options)
            self.phase = "search" if options.tools else "analysis"
            self.token = options.env.get("CLAUDE_CODE_OAUTH_TOKEN")
            self.session = options.session_id
            self.validator = Draft202012Validator(options.output_format["schema"])
            self.diagnostic = Diagnostics(options.output_format["schema"], self.session, self.token)

        async def receive_response(self):
            async for message in super().receive_response():
                event = {"phase": self.phase, **self.diagnostic.message(message)}
                if (isinstance(message, ResultMessage) and message.session_id == self.session
                        and message.subtype == "success" and not message.is_error
                        and self.validator.is_valid(message.structured_output)):
                    body = json.dumps(message.structured_output)
                    if self.token and self.token in body:
                        raise ValueError("canary_redaction_gate")
                    event["native_output"] = message.structured_output
                observations.append(event)
                yield message
    try:
        with patch.object(claude_agent_sdk, "ClaudeSDKClient", DiagnosticClient):
            return original.main()
    finally:
        if args.work is not None and args.work.is_dir() and observations:
            original.write_new_json(args.work / "native-diagnostics.json", {"events": observations,
                "native_output_is_observation_not_host_acceptance": True})


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"harness_error_type": type(exc).__name__}))
        sys.exit(1)
