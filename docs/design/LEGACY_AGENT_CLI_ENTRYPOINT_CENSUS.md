# Legacy-Agent CLI and Entrypoint Census

> **Status:** TASK 2 COMPLETE; INDEPENDENT CLASSIFICATION REVIEW PENDING
>
> **Observed source:** `241ccdba6dc7c2cf1b162dd254ada88f25b6a9b0`
>
> **Scope:** Static, docs-only inventory and recommendations. This document
> authorizes no product/test edit, entrypoint retirement, skill-policy change,
> Discord launch, merge, push, or live command.

## 1. Executive finding

ArkScope still contains a documented interactive agent CLI and an executable
Discord agent implementation, but neither is part of the current application
runtime:

- `python -m src.agents` remains documented in `README.md`, but no tracked
  product module imports `src.agents.__main__`. Importing it would immediately
  start the long-running CLI after `src.agents.cli` reads environment config.
- `src/monitor/discord_bot.py` has configuration, a dependency, and extensive
  tests, but no non-test constructor or `start_bot()` caller. The notifier has
  an injected bot seam; it does not launch the bot.
- The current workbench, Research HTTP API, agent tool registries, and
  subscription drivers already own many of the underlying capabilities. The
  terminal and Discord wrappers do not own those shared implementations.

The census recommendation is therefore to **fold any still-required wrapper-only
behavior into explicit App/model-callable contracts, then retire the two legacy
CLI entrypoints and the inactive Discord surface**. This is a recommendation,
not deletion authority. Track B skill behavior and the future alert/Discord
architecture still require a user decision and a separately reviewed plan.

The user's product direction is recorded as follows:

- preserve useful capabilities behind explicit model-callable interfaces;
- MCP and HTTP API are both acceptable delivery mechanisms;
- deciding whether those mechanisms should converge is a separate architecture
  decision;
- a future alert system may use a redesigned Discord integration rather than
  reuse this bot; and
- skills and unattended automation remain future product work, not reasons to
  preserve obsolete wrappers.

## 2. Canonical authority

The tracked authority is `docs/design/legacy_agent_cli_census/`. One
deterministic classification pass generated the ledger and normalized detail
authorities. Two complete runs were byte-identical.

```text
raw candidates               295
canonical entrypoints         80
consumer edges               244
CLI/Discord capabilities      42
exact test relations         499
current invocation rows       32
closed exclusions             20
```

`entrypoints.jsonl` owns entrypoint identity, role, reachability, side effects,
equivalence, recommendation, and decision gate. `consumers.tsv`,
`capabilities.tsv`, `tests.tsv`, and `current_invocations.tsv` are normalized
co-authorities generated from the same source facts. Every ledger ID array and
every normalized row close in both directions. `recommendations.tsv` is the
lossless ledger projection. `candidate_exclusions.tsv` closes the raw candidate
universe.

| Authority | SHA-256 |
| --- | --- |
| `entrypoints.jsonl` | `d8180e88e7da79b1e0adfe3afe450902ca6dc84b4d29024eee9369650ea76e28` |
| `consumers.tsv` | `b7655fa5686594208df5b4bc1b6f8c5c39c37a23e8af345fd4e394e691fa23bb` |
| `capabilities.tsv` | `f1827a5eb2412ec0693cb3329bb4d39269eab9efc7860d01164706c1e80c6080` |
| `tests.tsv` | `fecdb7ea384e0031e184bb0764711f54c4b14ad82b84618f08954db51413e003` |
| `current_invocations.tsv` | `0e5f642159e35b8ad30cdc74fab3e80d903ecc0cf4073f5cf76c4fe79b47b67e` |
| `recommendations.tsv` | `796e01c7d77e54a78f0d6303f5bad2088688f9dad244af3bf14445bdcf3ed67a` |
| `candidate_exclusions.tsv` | `94d29bca84203a8c079e06b370b893ae716b58d9ae587e8442e80f0989c7703a` |

## 3. Current entrypoint surface

| Product role | Count | Census treatment |
| --- | ---: | --- |
| Current App runtime | 10 | Retain. These are live desktop/API/tool-driver launch contracts. |
| Current operator command | 12 | Retain in this census. Desktop non-use is not retirement evidence. |
| Development/build tool | 27 | Retain. |
| Integration install/host | 16 | Retain external/browser/native-host contracts. |
| Legacy agent product | 2 | Fold required gaps into explicit contracts, then retire; user/Track B gated. |
| Legacy notification surface | 1 | Redesign before future alerts; user/Track B gated. |
| Stale documented surface | 5 | Remove stale invocations in a later bounded docs cleanup. |
| Unowned diagnostic | 7 | Retirement candidates requiring a later owner-specific plan. |

The twelve operator rows include current audit, collector, daily-update,
price/news runtime, and live-smoke commands. They are deliberately separate
from the abandoned interactive agent product. A later decision to replace
operator commands with App or natural-language workflows needs its own
capability/operability analysis.

The Polygon and Finnhub scheduler paths illustrate why entrypoint and library
ownership must remain separate. The scheduler imports provider classes and
functions from those modules; it does not execute their guarded CLI `main()`
blocks. Their command entrypoints are operator surfaces, not App-started CLI
processes.

## 4. Legacy interactive CLI

The two canonical rows are the package wrapper
`src/agents/__main__.py::python_module::src.agents` and the delegated
`src/agents/cli.py::python_script::main`. Their only current non-test invocation
is the README command. The CLI row owns 30 measured capabilities:

| App equivalence | Count | Capability IDs |
| --- | ---: | --- |
| Full | 9 | `alpha_picks_commands`, `conversation_history`, `effort_control`, `model_selection`, `provider_selection`, `reasoning_control`, `report_commands`, `research_query`, `session_clear` |
| Partial | 11 | `code_backend_control`, `compaction_control`, `context_window_control`, `extended_thinking`, `memory_commands`, `monitor_commands`, `save_command`, `scratchpad_inspection`, `status_and_token_usage`, `subagent_control`, `tool_turn_limit` |
| None | 10 | `attachment_input`, `code_model_control`, `command_help_and_completion`, `debug_logging_control`, `force_compaction`, `history_mode_control`, `manual_skill`, `overflow_inspection`, `skill_auto_apply`, `skill_suggestion` |

`none` does not mean every item should be rebuilt. Terminal presentation,
debug switches, completion, and local session conveniences can be deliberately
retired. Manual/automatic skill behavior and skill suggestions are Track B
decisions. Attachment input, compaction/overflow controls, and other research
workflow gaps should be judged by current App needs before wrapper removal.

Shared owners such as the model catalog, compressor, memory/report/monitor
tools, subagent dispatcher, attachment manager, skill implementation, and
research stores are not retirement candidates merely because the CLI calls
them. A retirement plan must cut wrapper reachability at symbol level and
retain every independently owned capability.

## 5. Discord surface

The Discord row has twelve measured capabilities: five full App equivalents,
one partial equivalent, and six with no current equivalent.

| App equivalence | Capability IDs |
| --- | --- |
| Full | `discord_effort_control`, `discord_follow_up`, `discord_model_control`, `discord_query`, `reasoning_control` |
| Partial | `monitor_commands` |
| None | `discord_admin_authorization`, `discord_alert_actions`, `discord_alert_delivery`, `manual_skill`, `skill_auto_apply`, `skill_suggestion` |

Configuration and tests prove that the implementation is buildable; they do
not prove a live product. No production launcher exists. The injected notifier
seam can call an already-supplied bot but cannot construct or start one.

Future alerts need explicit channel, authorization, delivery, retry, and action
ownership. The current setup/development knowledge can inform that design, but
the census does not require reuse of `MindfulDiscordBot`. OpenClaw, Hermes,
DeepSeek harnesses, or another orchestration layer are future alternatives and
were not evaluated here.

## 6. Model-callable capability boundary

Wrapper retirement must preserve model access where it is already a product
contract:

- the Research HTTP API owns run creation, history, model/provider/effort
  selection, and thread lifecycle;
- the in-process agent registry exposes shared financial, memory, monitor,
  report, save, and delegation tools to current agent paths;
- the Claude subscription driver exposes a hard-coded 13-tool read-only
  allowlist through its in-process `ark` MCP server; and
- the ChatGPT subscription driver applies the same 13-tool read-only allowlist
  in its managed tool loop.

The 13 read-only tools are `get_sa_feed`, `get_sa_digest`,
`get_sa_alpha_picks`, `get_ticker_news`, `get_news_brief`,
`search_news_advanced`, `get_ticker_prices`, `get_current_quote`,
`get_price_change`, `get_ticker_data_coverage`,
`get_fundamentals_analysis`, `get_sec_filings`, and
`get_economic_calendar`.

This is not a claim that every internal tool is exposed through MCP or HTTP.
Tool/API coverage and possible convergence need a separate interface inventory
if they become a prerequisite for wrapper retirement.

## 7. Independent cleanup candidates

Five stale command surfaces appear in three current documents:

- IBKR fundamentals collection in `PAID_SUBSCRIPTION_EVALUATION.md`;
- three retired scoring commands in `NEWS_DATA_INVENTORY.md`; and
- the retired SA density-analysis command in `SA_EXTENSION_ROADMAP.md`.

Seven executable-shaped diagnostics have no current product owner. They include
three standalone data-source calculators/readers, the superseded Claude CLI
driver target, two unreachable dynamic command helpers, and the option-pricing
script entrypoint. Their shared library behavior and tests must be separated
from their command wrappers in any later cleanup.

Twenty historical/governance command observations are closed exclusions rather
than current invocations. They remain provenance and are not stale product
surface.

## 8. Decision packet

| Question | Measured fact | Current recommendation | Gate |
| --- | --- | --- | --- |
| Interactive CLI | README-documented, no App launcher/importer; 20/30 capabilities already full or partial | Fold only required gaps into explicit contracts, then retire both wrappers | User + Track B skill policy |
| Discord bot | Test-only; no non-test constructor or launcher | Preserve useful setup knowledge, redesign future alert transport, then retire this surface if not selected | User + Track B skill/alert policy |
| Skills | Manual, auto-apply, and suggestion behavior have no current App producer | Do not infer retention or deletion; settle Track B and unattended automation first | Track B |
| Model-callable tools | HTTP, in-process registry, and bounded subscription tool bridges are live | Preserve explicit contracts; evaluate MCP/API convergence separately | Separate architecture slice |
| Operator commands | Twelve current surfaces have concrete maintenance/collection roles | Retain in this census | Separate operator-workflow ruling |
| Stale docs/diagnostics | Five stale command surfaces and seven unowned diagnostics | Bounded cleanup/retirement candidates | Later reviewed plan |

Census completion is valid even if the user defers any disposition. No row in
this document is an implementation authorization.

## 9. Method and limitations

- All analysis is static at the pinned source commit. Product modules,
  entrypoints, test bodies, providers, browsers, schedulers, and production
  stores were not executed.
- Candidate closure covers 295 observations across 14 source families and 90
  paths. Every admitted candidate maps to exactly one canonical row; every true
  exclusion has a closed reason and evidence row.
- Seven dynamic launch observations were traced rather than dropped: two
  current Codex launch sites, one current SA native-host launch, one injected
  test-only Claude diagnostic seam, and three unreachable helper observations.
- Tests establish exact current contracts but do not establish product
  liveness. This rule is load-bearing for Discord and unowned diagnostics.
- Importing `src.agents.__main__` was explicitly forbidden because it starts the
  CLI and can read credentials. Its side effects were established by AST only.
- Product/test/current-authority bytes remained protected. The only tracked
  changes in this task are this census, its machine authorities, and governance
  status.
