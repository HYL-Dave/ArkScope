"""Verify the declared JSON analysis transport across the whole affected set."""

from verify_turns import verifier


mutation = verifier.mutation
CLAUDE = "src/auth_drivers/lifecycle_web_claude.py"
MODEL = "src/auth_drivers/lifecycle_web_models.py"
verifier.MUTATIONS["backend"] = tuple(item for item in verifier.MUTATIONS["backend"]
    if item["name"] != "malformed_structured_output_is_accepted") + (
    mutation("json_analysis_skips_output_validation", "test_claude_analysis_rejects_invalid_final_json_without_repair_or_retry", CLAUDE,
             "output = validate_output(value, call.output_schema)", "output = value"),
    mutation("json_analysis_reenables_native_schema", "test_claude_analysis_declares_final_json_without_native_output_tool", CLAUDE,
             'output_format={"type": "json_schema", "schema": call.output_schema} if call.phase == "search" else None,',
             'output_format={"type": "json_schema", "schema": call.output_schema},'),
    mutation("json_analysis_accepts_ambiguous_native_payload", "test_claude_analysis_never_chooses_between_native_and_final_json", CLAUDE,
             "if message.structured_output is not None or not isinstance(message.result, str):",
             "if not isinstance(message.result, str):"),
    mutation("json_analysis_accepts_non_text_final_result", "test_claude_analysis_rejects_invalid_final_json_without_repair_or_retry", CLAUDE,
             "if message.structured_output is not None or not isinstance(message.result, str):",
             "if message.structured_output is not None:"),
    mutation("json_analysis_pretool_allows_native_output", "test_claude_analysis_denies_structured_output_tool_at_every_boundary", CLAUDE,
             'elif name != "StructuredOutput" or self.call.phase != "search":', 'elif name != "StructuredOutput":'),
    mutation("json_analysis_init_allows_native_output", "test_claude_analysis_denies_structured_output_tool_at_every_boundary", CLAUDE,
             'expected = {"StructuredOutput", "WebSearch"} if call.phase == "search" else set()',
             'expected = {"StructuredOutput", "WebSearch"} if call.phase == "search" else {"StructuredOutput"}'),
    mutation("json_analysis_notification_allows_native_output", "test_claude_analysis_denies_structured_output_tool_at_every_boundary", CLAUDE,
             'elif isinstance(block, ToolUseBlock) and block.name == "StructuredOutput" and call.phase == "search":',
             'elif isinstance(block, ToolUseBlock) and block.name == "StructuredOutput":'),
    mutation("json_analysis_duplicate_keys_become_last_value_wins", "test_claude_analysis_nested_json_duplicate_keys_are_not_last_value_wins", MODEL,
             'if key in result:\n                raise ValueError("duplicate key")',
             'if False:\n                raise ValueError("duplicate key")'),
    mutation("search_silently_falls_back_to_final_json", "test_claude_search_does_not_fall_back_to_analysis_json_mode", CLAUDE,
             "value = message.structured_output", "value = message.structured_output or message.result"),
)


if __name__ == "__main__":
    verifier.main()
