# Claude Agent SDK Runtime Admission

**Status:** ACTIVE current authority. Offline review and the bounded live gate
are complete for `claude-agent-sdk==0.2.152` and bundled Claude Code CLI 2.1.259.
The September 8 gate observes two Sonnet 5 sessions / three model turns, exact
model receipts, literal subscription auth, and both positive and negative tool
controls. Current evidence is in
`docs/superpowers/evidence/2026-09-08-sdk152-fixed-output/`.
The completed 0.2.151 / CLI 2.1.258 evidence is
historical and remains sealed at
`docs/superpowers/evidence/2026-09-02-claude-agent-sdk-runtime-admission/`; it
does not substitute for the new pair's admission.

This document supersedes only the *current runtime* claims in
`SLICE_7B3_SDK_DRIVER_DESIGN.md`. That document remains the historical design
and preserves the 0.2.105 / CLI 2.1.183 probe record.

## Runtime identity

The candidate branch's fail-closed runtime gate accepts exactly one pair:

- Python distribution and `claude_agent_sdk._version`: `0.2.152`;
- `claude_agent_sdk._cli_version` and the bundled binary: `2.1.259`;
- executable: `claude_agent_sdk/_bundled/claude` (or `claude.exe` on Windows).

`src/auth_drivers/claude_agent_sdk_runtime.py` checks all four version
observations, executes the bundled binary's `--version`, and returns its exact
path. Both OAuth consumers pass that path through `ClaudeAgentOptions.cli_path`.
There is no PATH fallback. A mismatch fails before token-store access or an SDK
session starts.

The upgrade was chosen instead of reverting to 0.2.105. The upstream SDK and
CLI contain later reliability and security fixes; accepting them requires a
new admission, not pretending the old pin still describes the installed
runtime. Upstream records:

- https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md
- https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md

The reviewed 0.2.105 to 0.2.151 interval includes command/input hardening for
resume identifiers, Windows launchers, and skill names; subprocess, background
task, malformed-message, and MCP 2.x fixes; and newer result metadata such as
terminal reasons and typed model usage. It also adds broader session controls
such as conversation reset, rewind, and origin metadata. ArkScope does not
automatically expose those new controls: the closed options contract below
keeps every unadopted surface at its inert default.

The official `v0.2.151...v0.2.152` comparison changes only `CHANGELOG.md`,
`pyproject.toml`, `_version.py`, and `_cli_version.py`. The Python transport and
option types are unchanged; 0.2.152 updates the bundled CLI from 2.1.258 to
2.1.259. CLI 2.1.259 adds managed HTTP/SSE MCP configuration and a new
`--permission-prompts none` mode, changes Bash `Read()` deny handling, and
includes MCP/startup reliability fixes. ArkScope adopts none of those new
surfaces automatically: it continues to use the existing options below and
requires exact init tool/server inventory in the live gate. Exact
upstream records:

- https://github.com/anthropics/claude-agent-sdk-python/compare/v0.2.151...v0.2.152
- https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.152
- https://github.com/anthropics/claude-code/releases/tag/v2.1.259

## Locked execution contract

Both AI Research and subscription structured-output calls must use:

- `tools=[]` plus the reviewed built-in `disallowed_tools` list;
- only the task-specific `allowed_tools` and MCP servers;
- `setting_sources=[]`, `strict_mcp_config=True`, and `permission_mode="dontAsk"`;
- a fresh empty per-call `cwd` and `CLAUDE_CONFIG_DIR`;
- no resume/session state, fallback model, additional directories, settings,
  plugins, subagents, skills, or extra CLI arguments;
- the setup-token in `options.env`, with every reviewed higher-precedence or
  rerouting Anthropic auth variable overwritten with an empty value;
- a closed child environment overlay that preserves only launch, locale, and
  TLS prerequisites and blanks every other parent variable before the SDK
  merges `options.env` with `os.environ`.

The init frame must contain `apiKeySource == "none"`. Missing, null, malformed,
or any other value is unverified and terminates the call. Absence is never
recorded as successful subscription authentication.

The shipped posture uses `dontAsk` and does not use bypass permissions. A
`PreToolUse` hook is not part of the shipped path and therefore is not a release
gate for this admission. The Python MCP bridge retains its independent exact
allowlist at execution time.

These controls constrain the Claude Code tool, configuration, and inherited
secret surface. This does not constitute an OS sandbox: the SDK child still has
host filesystem and network access. Stronger egress and filesystem isolation
remains separate security work.

## Live admission gate

The user authorized exactly two OAuth Agent SDK sessions, each limited to two
model turns, with zero ArkScope retry and zero model/provider fallback. The gate
uses a model already available to the current subscription; it does not use
Fable 5.1 and does not require an account upgrade. Every assistant frame must
report the exact requested model, and each session receipt retains that value
as `observed_model`; an absent or different model fails the gate.

Session A must positively prove the allowed in-process MCP tool works. Session
B requests built-in and off-list tools and must show an exact init inventory
with no forbidden write. A correctly calibrated gate also places a hostile
project `.mcp.json` and `CLAUDE.md` in the actual child `cwd`, and hostile user
settings in the actual `CLAUDE_CONFIG_DIR`. Across both sessions, retain only
bounded non-secret facts:
runtime versions and binary hash, literal `apiKeySource`, requested and observed
model, init tool/server inventory, tool-call names and counts, terminal/result
counts, model turns, usage counters, and trap-file booleans. Never retain the
token, raw prompts, raw model prose, or environment values.

The session budget counts ArkScope `query()` invocations, and `num_turns` is the
CLI result's model-turn count. `application_retries == 0` proves that this gate
does not retry a failed ArkScope session. These fields do not observe or claim
the absence of internal HTTP retries below the CLI/SDK boundary.

Model behavior cannot positively prove enforcement merely by declining to call
a tool. Admission therefore combines exact init inventory and side-effect traps
with the positive allowed-tool control. A failed or ambiguous observation does
not become a pass.

The 2026-09-02 run used the intended fresh empty product directories and its
exact init inventories passed, but its hostile project files were under a
sibling directory and its hook was outside the overridden `CLAUDE_CONFIG_DIR`.
Those files are developer-local Claude Code inputs that ArkScope must never
consume; they are not required App configuration. Their false trap values do
not independently validate suppression against deliberately populated source
directories, but that stronger adversarial check is not needed to establish
the shipped empty-directory path. The future harness now binds the traps to the
actual SDK paths and an offline test owns that binding. No additional provider
call was made for that 0.2.151 admission. Reusing a project, home, or non-empty
configuration directory in the product path would be a new security decision
and would require readmission.

On September 8, the corrected gate passed with 0.2.152 / CLI 2.1.259. Both
sessions report `apiKeySource == "none"` and `observed_model=claude-sonnet-5`.
The positive session exposes and calls only the in-process probe; the negative
session exposes zero tools and MCP servers. The deliberately populated test
directories are now bound to the real SDK paths, and all three trap observations
are false. These synthetic files are test inputs, not a new App configuration
requirement. This is evidence for the combined locked configuration, not proof
that each overlapping CLI control independently enforces every restriction.

## Publication boundary

This setup-token integration is restricted to operator-local self-use. ArkScope
must not market or ship it as a general third-party Claude.ai sign-in or route
Free/Pro/Max credentials on behalf of other users. A distributable end-user
subscription feature requires a separate legal/product review or an Anthropic
agreement; the ordinary distributable provider path is an API key or supported
cloud credential. Current official references:

- https://code.claude.com/docs/en/authentication
- https://code.claude.com/docs/en/legal-and-compliance

## Upgrade rule

Any SDK or bundled CLI change starts a new admission. Update the requirement and
reviewed constants together, rerun the offline drift/shape tests, inspect the
upstream changelogs, and repeat the bounded live gate before enabling the new
pair. Do not widen an allowlist merely to preserve compatibility.
