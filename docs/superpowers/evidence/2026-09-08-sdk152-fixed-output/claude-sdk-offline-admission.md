# Claude Agent SDK 0.2.152 Offline Admission

**Status:** OFFLINE GREEN; BOUNDED LIVE GATE PENDING.

This report covers only the Claude Agent SDK runtime readmission from Python
SDK 0.2.151 / bundled Claude Code CLI 2.1.258 to SDK 0.2.152 / CLI 2.1.259.
No provider call or live SDK session was made while producing this report.

## Root causes

1. The installed environment contained SDK 0.2.152 and bundled CLI 2.1.259,
   while ArkScope's requirement and four runtime identity owners still admitted
   only 0.2.151 / 2.1.258. The fail-closed runtime check therefore rejected the
   installed pair before downstream test doubles could exercise Claude auth
   behavior.
2. The live gate requested `LIVE_MODEL` and recorded `fallback_model: null`, but
   did not inspect `AssistantMessage.model`. An unrequested model could therefore
   produce a structurally valid receipt without failing the gate.

## Installed identity

- Python distribution: `0.2.152`
- `claude_agent_sdk._version`: `0.2.152`
- `claude_agent_sdk._cli_version`: `2.1.259`
- bundled binary `--version`: `2.1.259 (Claude Code)`
- bundled binary location: package-relative `_bundled/claude`
- bundled binary SHA-256:
  `f7dd62ae415378018cd21dd950eb3bac174ab085830304d3b8b098146bfd47b6`

The runtime gate continues to compare all four version observations and accepts
only a binary resolved inside the SDK's `_bundled` directory. There is no PATH
fallback.

## Upstream review

Primary sources:

- https://github.com/anthropics/claude-agent-sdk-python/compare/v0.2.151...v0.2.152
- https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.152
- https://github.com/anthropics/claude-code/releases/tag/v2.1.259

The official SDK comparison contains three release commits and modifies four
files: `CHANGELOG.md`, `pyproject.toml`, `_version.py`, and `_cli_version.py`.
The Python transport and option-type files have identical Git blobs at the two
tags. SDK 0.2.152 therefore introduces no Python API or transport behavior for
ArkScope to adopt; its runtime change is the bundled CLI bump.

The CLI 2.1.259 release includes managed HTTP/SSE MCP settings,
`--permission-prompts none`, broader Bash `Read()` deny handling, and MCP and
managed-settings reliability fixes. ArkScope did not enable a new option or
widen an allowlist. The existing `tools=[]`, named disallow list,
`setting_sources=[]`, `strict_mcp_config=True`, `dontAsk`, fresh directories,
closed child environment, exact init inventory, and literal
`apiKeySource == "none"` owners remain in force.

## RED evidence

All test commands used `/home/hyl/.virtualenvs/llm_app/bin/python`, removed
`PYTHONPATH`, and ran through the immutable
`docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py`
wrapper. Each run reported only loopback, `ENETUNREACH` for the external probe,
and `inherited_credentials: false`.

The new literal admitted-identity test failed before the runtime update:

```text
FAILED test_reviewed_claude_runtime_admits_sdk_0_2_152_with_cli_2_1_259
AssertionError: assert '0.2.151' == '0.2.152'
1 failed
```

The new model-receipt tests then failed before the harness update with the
expected missing behaviors: no `observed_model` receipt, no rejection of an
alternate model, no rejection when no assistant model was observed, and no
closed-schema ownership for the new field (`4 failed`).

## Offline GREEN evidence

Final command:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python \
  docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py \
  pytest -q \
  tests/test_auth_drivers.py \
  tests/test_auth_factory.py \
  tests/test_claude_agent_sdk_runtime.py \
  tests/test_claude_agent_sdk_live_gate.py \
  tests/test_claude_code_sdk_driver.py \
  tests/test_claude_oauth_probe.py \
  tests/test_subscription_structured_output.py \
  --tb=short
```

Result: `144 passed in 2.09s`.

This includes the four independent version-drift rejections, bundled-only path
checks, closed child-environment checks, literal auth-source owners, live-gate
budget and evidence-shape checks, and both session owners for exact
`observed_model`. The harness now rejects every assistant frame whose model is
not exactly `LIVE_MODEL`, rejects a session with no observed assistant model,
retains the exact model in each session receipt, and explicitly configures no
fallback model.

No credential, production database, `.env`, or developer Claude configuration
was read or modified. Prior sealed evidence was inspected but not modified. No
live session was started.

## Outstanding live properties

The main agent's bounded two-session gate must still establish:

1. Both sessions use SDK 0.2.152 and the hashed bundled CLI 2.1.259.
2. Both init frames contain literal `apiKeySource == "none"` and exactly the
   expected tool and MCP server inventories.
3. Every assistant frame in both sessions reports exactly the requested
   `LIVE_MODEL`, and each closed session receipt contains that value as
   `observed_model`.
4. The positive session invokes only `mcp__ark__admission_probe`, exactly once;
   the locked session invokes no tool.
5. No hostile project/config trap starts, no forbidden write occurs, and no
   ambient instruction is observed.
6. Exactly two ArkScope SDK sessions start, each reports one or two model turns,
   ArkScope performs zero retries, and no fallback model is configured or
   observed.

The session count measures ArkScope `query()` invocations. `num_turns` is the
CLI result's model-turn count, and `application_retries == 0` covers ArkScope
session retries. These receipts do not observe or prove the absence of internal
HTTP retries below the SDK/CLI boundary.
