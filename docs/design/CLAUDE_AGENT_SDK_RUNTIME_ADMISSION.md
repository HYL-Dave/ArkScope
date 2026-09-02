# Claude Agent SDK Runtime Admission

**Status:** ACTIVE current authority. Offline admission and the bounded live
security gate are complete for `claude-agent-sdk==0.2.151` with bundled
Claude Code CLI 2.1.258. Evidence is retained at
`docs/superpowers/evidence/2026-09-02-claude-agent-sdk-runtime-admission/`.

This document supersedes only the *current runtime* claims in
`SLICE_7B3_SDK_DRIVER_DESIGN.md`. That document remains the historical design
and preserves the 0.2.105 / CLI 2.1.183 probe record.

## Runtime identity

ArkScope admits exactly one reviewed pair:

- Python distribution and `claude_agent_sdk._version`: `0.2.151`;
- `claude_agent_sdk._cli_version` and the bundled binary: `2.1.258`;
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
Fable 5.1 and does not require an account upgrade.

Session A must positively prove the allowed in-process MCP tool works while a
trap working directory and settings tree remain isolated. Session B requests
built-in and off-list tools and must show an exact init inventory with no trap
side effect. Across both sessions, retain only bounded non-secret facts:
runtime versions and binary hash, literal `apiKeySource`, init tool/server
inventory, tool-call names and counts, terminal/result counts, model turns,
usage counters, and trap-file booleans. Never retain the token, raw prompts,
raw model prose, or environment values.

Model behavior cannot positively prove enforcement merely by declining to call
a tool. Admission therefore combines exact init inventory and side-effect traps
with the positive allowed-tool control. A failed or ambiguous observation does
not become a pass.

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
