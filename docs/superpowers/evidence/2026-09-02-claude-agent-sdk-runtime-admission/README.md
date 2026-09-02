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
no MCP servers. The write marker remained absent. The measured total was two
sessions and three model turns, with zero application retries and no fallback.

Post-run calibration found that three other false-valued observations in the
JSON are not independent evidence of configuration suppression. The project
`.mcp.json` and `CLAUDE.md` traps were written under a sibling of the actual
child `cwd`; the settings hook was written under `$HOME/.claude` even though
the child used a separate `CLAUDE_CONFIG_DIR`. Consequently,
`trap_mcp_started=false` and `ambient_instruction_observed=false` accurately
record what happened but do not prove that populated project/user sources are
ignored. The harness has since been corrected and has an offline binding test,
but was not run again because the two-session authorization was exhausted.
These files are developer-local Claude Code inputs that ArkScope deliberately
excludes, not configuration required by the App. The limitation therefore
narrows the adversarial test claim without blocking the observed product path.

The artifact intentionally excludes the setup-token, credential and account
identifiers, local paths, process environment, prompts, raw SDK messages, and
model prose. The observation verifies the exact runtime/auth identity, the
positive allowed-MCP path, the exact init tool/server inventories, the absent
forbidden write, and the two-session/no-retry/no-fallback budget. Together with
the product's fresh empty per-call `cwd` and `CLAUDE_CONFIG_DIR`, it supports
the current product path. It does not independently live-validate
`setting_sources=[]` or `strict_mcp_config=True` against populated source
directories, claim OS-level filesystem or network isolation, or validate
Fable 5.1 through OAuth.

## Offline gates

- Claude SDK/Auth focus at the live implementation commit: `90 passed`.
- Post-run harness-calibration focus: `92 passed`.
- Repository suite at the live implementation commit, excluding the
  independently reproduced stale historical packet node: `5347 passed, 12 skipped`.
- Post-run harness-calibration repository suite under the same exclusion:
  `5373 passed, 12 skipped, 1 deselected`.
- Remaining tests in that historical packet: `24 passed, 1 deselected`.
- The deselected node also fails on unmodified `master` because its sealed
  shadow script predates the required `execution_owner_id` argument.
