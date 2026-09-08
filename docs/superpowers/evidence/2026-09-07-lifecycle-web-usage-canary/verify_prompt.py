"""Whole affected-set owners for the analysis schema prompt amendment."""

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
path = HERE.parent / "2026-09-07-lifecycle-web-usage/verify.py"
spec = importlib.util.spec_from_file_location("usage_verifier", path)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
verifier = prior.verifier
mutation = verifier.mutation
CLAUDE = "src/auth_drivers/lifecycle_web_claude.py"
verifier.MUTATIONS = {"frontend": (), "backend": (
    mutation("analysis_schema_prompt_not_dispatched", "test_claude_analysis_prompt_binds_exact_schema_without_repair_or_more_tools", CLAUDE,
             "            system_prompt=system_prompt,", '            system_prompt="Investigate only the public listing question.",'),
    mutation("analysis_schema_prompt_disagrees_with_validator", "test_claude_analysis_prompt_binds_exact_schema_without_repair_or_more_tools", CLAUDE,
             'json.dumps(call.output_schema, ensure_ascii=True, allow_nan=False, separators=(",", ":"))',
             'json.dumps({}, ensure_ascii=True, allow_nan=False, separators=(",", ":"))'),
    mutation("analysis_reenables_web_search", "test_claude_analysis_has_no_web_or_filesystem_tools", CLAUDE,
             'tools = ["WebSearch"] if call.phase == "search" else []', 'tools = ["WebSearch"]'),
    mutation("malformed_structured_output_is_accepted", "test_claude_analysis_never_unwraps_invalid_provider_arguments", CLAUDE,
             "output = validate_output(message.structured_output, call.output_schema)", "output = message.structured_output"),
)}


if __name__ == "__main__":
    verifier.main()
