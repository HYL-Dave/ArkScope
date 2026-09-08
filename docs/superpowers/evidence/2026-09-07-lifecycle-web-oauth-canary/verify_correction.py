"""Incremental correction admission using the full existing affected test sets."""

import importlib.util
from pathlib import Path


PACKET = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "oauth_correction_verifier",
    PACKET.parent / "2026-09-07-lifecycle-web-runtime/scripts/verify.py",
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
mutation = verifier.mutation
CLAUDE = verifier.CLAUDE
PIN_OWNER = "test_claude_web_pins_internal_helper_models_to_exact_selected_model"

verifier.MUTATIONS = {
    "backend": (
        mutation(
            "background_model_override_removed", PIN_OWNER, CLAUDE,
            "        environment.update(ANTHROPIC_DEFAULT_HAIKU_MODEL=call.selection.model,\n"
            "                           ANTHROPIC_SMALL_FAST_MODEL=call.selection.model)",
            "        environment.update(ANTHROPIC_SMALL_FAST_MODEL=call.selection.model)",
        ),
        mutation(
            "legacy_helper_override_removed", PIN_OWNER, CLAUDE,
            "        environment.update(ANTHROPIC_DEFAULT_HAIKU_MODEL=call.selection.model,\n"
            "                           ANTHROPIC_SMALL_FAST_MODEL=call.selection.model)",
            "        environment.update(ANTHROPIC_DEFAULT_HAIKU_MODEL=call.selection.model)",
        ),
        mutation(
            "rejection_erases_remote_completion",
            "test_claude_mixed_model_result_is_durable_failure_without_analysis_or_fallback", CLAUDE,
            "                        control.observe_terminal(call.call_id, response_id=session_id, status=status, selection=call.selection)\n"
            "                        _validate_result(message, call=call, status=status)",
            "                        _validate_result(message, call=call, status=status)\n"
            "                        control.observe_terminal(call.call_id, response_id=session_id, status=status, selection=call.selection)",
        ),
        mutation(
            "mixed_model_usage_accepted",
            "test_claude_owned_completed_result_rejection_does_not_erase_remote_terminal", CLAUDE,
            "        for model in usage:\n            require_response_model({\"model\": model}, call.selection.model)",
            "        for model in ():\n            require_response_model({\"model\": model}, call.selection.model)",
        ),
        mutation(
            "foreign_result_becomes_owned_terminal",
            "test_claude_unowned_or_absent_terminal_still_leaves_remote_outcome_unknown", CLAUDE,
            "def _result_status(message: ResultMessage, *, call: ModelCall, session_id: str) -> str:\n"
            "    if message.session_id != session_id:",
            "def _result_status(message: ResultMessage, *, call: ModelCall, session_id: str) -> str:\n"
            "    if False:",
        ),
    ),
    "frontend": (),
}


if __name__ == "__main__":
    verifier.main()
