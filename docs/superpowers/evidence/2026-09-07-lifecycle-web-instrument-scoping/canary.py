"""One current-code TA canary with a renewed, larger subscription envelope."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-07-lifecycle-web-usage-canary"))
import claude_canary as original


def current_options():
    from src.security_lifecycle_web_pipeline import default_investigation_options
    return default_investigation_options("claude_code_oauth", effort="medium", output_token_limit=None)


def amend_plan(value):
    options = current_options()
    if (options.max_search_uses, options.max_sources, options.max_source_requests,
            options.max_redirects, options.model_timeout_seconds, options.source_timeout_seconds) != (12, 8, 24, 2, 600, 180):
        raise ValueError("authorized_budget_changed")
    result = dict(value)
    result.pop("max_cli_internal_turns")
    result.update(
        authority="User renewed source reads and permitted several-fold bounds; TA only, selected Sonnet 5 subscription, no other channel or profile action",
        options=asdict(options), max_model_submissions=2,
        max_cli_tool_round_trips={"search": 14, "analysis": 2},
        max_reported_total_turns={"search": 15, "analysis": 3},
        local_completion_deadline_seconds=1500,
        source_http_campaign_budget={"limit": 24, "already_used": 0, "this_run_maximum": 24},
        analysis_output_mode="final_json_validated_by_shared_parser",
        renewed_harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    return result


def configure(admission):
    base_plan = original.prepared_plan
    original.CHECKPOINT = admission.resolve()
    original.options = current_options
    original.prepared_plan = lambda profile, as_of: amend_plan(base_plan(profile, as_of))


def observed_client(base):
    class OutputModeWitness(base):
        def __init__(self, *, options):
            analysis = options.tools == []
            if analysis:
                if (options.output_format is not None or "StructuredOutput" not in options.disallowed_tools
                        or options.max_turns != 2):
                    raise ValueError("analysis_output_mode_changed")
            else:
                if options.tools != ["WebSearch"] or options.max_turns != 14 or options.output_format is None:
                    raise ValueError("search_output_mode_changed")
            self.analysis = analysis
            super().__init__(options=options)

    return OutputModeWitness


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--admission", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    configure(args.admission)
    sys.argv = [sys.argv[0], *remaining]
    import claude_agent_sdk
    with patch.object(claude_agent_sdk, "ClaudeSDKClient", observed_client(claude_agent_sdk.ClaudeSDKClient)):
        return original.main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"harness_error_type": type(exc).__name__}))
        sys.exit(1)
