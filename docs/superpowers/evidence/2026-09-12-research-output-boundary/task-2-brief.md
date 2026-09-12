## Task 2: Registered Result Policies And Four Tool Adapters

**Files:** Create `src/tools/result_policy.py`, `tests/test_tool_output_policy.py`,
`tests/test_tool_output_channels.py`; modify `src/tools/registry.py`,
`src/agents/openai_agent/tools.py`, `src/agents/anthropic_agent/tools.py`,
`src/auth_drivers/chatgpt_oauth_driver.py`, `src/auth_drivers/claude_code_sdk_driver.py`.
Existing adapter fixture tests may need explicit policy declarations; enumerate
each changed expectation and its replacement owner, do not remove coverage.

**Consumes:** Task 1 `OutputGuard.check`, `output_scope`, `current_output_guard`.
**Produces:** trusted `ResultPolicy` and `ToolDefinition.result_policy`;
`admit_tool_result(result, *, policy, guard=None) -> str` returning canonical
lossless JSON or declared text, or `OutputBoundaryError` with closed codes;
`serialize_tool_result(result, *, tool_name) -> str` for API adapters. Registry
policies must not be selected by result content. Domain validator support has
no SEC import/branch. A source-only inventory decides existing public result
shapes and records every registered name plus bridge-only delegation.

Source inventory resolved all 54 definitions: 50 public JSON and four text
tools (`check_data_freshness`, `scan_alerts`, `get_economic_calendar`,
`get_macro_value`); bridge-only `delegate_to_subagent` returns public JSON.
Declare policies explicitly on each registration, leaving unknown policies
unadmitted. The four text functions are not JSON-string producers. Handle
native Pydantic/date/datetime/finite Decimal explicitly; arbitrary object
coercion and raw strings returned under JSON policy are errors. Set progressive
bounds at depth 64, 1,000,000 nodes and 32 MiB serialized output; preserve
existing smaller channel budgets. Closed validators must return literal True;
their exceptions or mutations cannot leak rejected values or bypass validation.

- [ ] Inventory return annotations and actual serialization paths without invoking tools or DAL; settle JSON/text/model/datetime/Decimal handling before implementation.
- [ ] Write RED tests invoking real four adapters with a registered synthetic public result containing long words, numeric TEXT, accession, URL, hash and cursor. After unwrapping channel envelopes:

```python
assert canonical(openai_data) == canonical(anthropic_data) == canonical(chatgpt_data) == canonical(claude_data)
assert json.loads(admitted)["value"] == "1234567890123456789.123"
```

- [ ] Add invalid JSON/NaN/foreign object/cycle/depth/unknown policy/closed-validator-extra-field and secrets in values AND keys; expect typed failure and no rejected value or repr.
- [ ] Watch RED, implement shared policy with admission before reducer/preview, retain diagnostic handling for exceptions. Normalize known native date/Decimal/Pydantic values explicitly, not `default=str`.
- [ ] Run all adapter/registry/subagent positives and inverse checks for bypassed policy, known-secret and credential-field checks. Unknown registered policy must not silently fall through.
- [ ] Commit and independent task review. SEC feature task remains parked and its four failed nodes are listed, not executed as this branch's tests.

