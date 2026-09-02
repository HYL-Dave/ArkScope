# Claude Agent SDK 0.2.151 Runtime Admission Evidence

This packet records the bounded live gate for implementation commit
`d5117a1e931b5e33e83cc8064752898c337e9e30`.

## Authorized boundary

- Exactly two OAuth-backed Claude Agent SDK sessions were permitted.
- Each session was capped at two model turns.
- ArkScope retries and model/provider fallback were disabled.
- The gate used `claude-sonnet-5`, not Fable 5.1, and required no account
  upgrade.
- Profile credential metadata was read through SQLite `mode=ro`; the setup-token
  was loaded from the system keyring. Neither value is retained here.

## Measured result

`live-admission.json` is the complete retained output. Both sessions reported
`apiKeySource="none"`. The positive session exposed and called exactly one
in-process `mcp__ark__admission_probe`; the locked session exposed no tools and
no MCP servers. Ambient instruction, MCP-launch, hook-launch, and write traps
all remained false. The measured total was two sessions and three model turns,
with zero application retries and no fallback.

The artifact intentionally excludes the setup-token, credential and account
identifiers, local paths, process environment, prompts, raw SDK messages, and
model prose. This admission verifies the Claude Code tool/configuration and
inherited-secret controls. It does not claim OS-level filesystem or network
isolation, and it does not validate Fable 5.1 through OAuth.

## Offline gates

- Claude SDK/Auth focus: `90 passed`.
- Repository suite excluding the independently reproduced stale historical
  packet node: `5347 passed, 12 skipped`.
- Remaining tests in that historical packet: `24 passed, 1 deselected`.
- The deselected node also fails on unmodified `master` because its sealed
  shadow script predates the required `execution_owner_id` argument.
