"""Prove terminal counting without increasing native tool or billing budgets."""

from verify_prompt import verifier

mutation = verifier.mutation
CLAUDE = "src/auth_drivers/lifecycle_web_claude.py"
verifier.MUTATIONS["backend"] += (
    mutation("completion_is_mistaken_for_extra_tool_round_trip", "test_claude_completed_result_includes_final_turn_after_tool_budget", CLAUDE,
             "max_total_turns = _tool_round_trip_limit(call) + 1", "max_total_turns = _tool_round_trip_limit(call)"),
    mutation("terminal_allowance_is_unbounded", "test_claude_terminal_allowance_does_not_accept_extra_or_malformed_turns", CLAUDE,
             "max_total_turns = _tool_round_trip_limit(call) + 1", "max_total_turns = 100"),
    mutation("native_turn_budget_accidentally_increases", "test_claude_completed_result_includes_final_turn_after_tool_budget", CLAUDE,
             "max_turns=_tool_round_trip_limit(call), session_id=session_id,", "max_turns=_tool_round_trip_limit(call) + 1, session_id=session_id,"),
)


if __name__ == "__main__":
    verifier.main()
