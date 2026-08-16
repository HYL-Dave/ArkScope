# Legacy-Agent CLI and Entrypoint Census Design

> **Status:** DESIGN + PLAN REVIEWED GREEN; TASK 0 COMPLETE; TASK 0 REVIEW NEXT
> **Date:** 2026-08-16
> **Product base:** `241ccdba6dc7c2cf1b162dd254ada88f25b6a9b0`
> **Scope:** docs-only inventory and recommendations; no product or test edits
> **Roles:** Codex authors and executes the census; Fable independently reviews
> **Binding sequence:** PG no-tail closeout -> this census -> user disposition ->
> optional retirement plan -> runtime-owner/CSS boundary work. A real P0 incident
> may preempt the sequence.

## 0. Decision being implemented

ArkScope was considered as a command-line product roughly a year ago. That product
direction was abandoned about six months ago in favor of the desktop/web workbench.
The user has ruled that the old interactive CLI does not need to survive merely for
compatibility: if it constrains the current application or creates maintenance burden,
full retirement is acceptable.

That ruling authorizes a census, not deletion. The census must first distinguish:

1. the legacy interactive agent product;
2. the Discord agent surface coupled to the same pre-workbench skill policy;
3. current application runtimes and externally invoked integration contracts;
4. operator commands that still perform supported maintenance or collection work;
5. development/build tools; and
6. unowned diagnostics or stale documented commands.

The census is complete even if the user is not yet ready to decide Track B, skill,
or Discord disposition. A later retirement plan remains gated on that product ruling.
Insufficient information is not evidence to retain or retire a surface.

## 1. Grounded current state

### 1.1 Product authority

`docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` Section 11 explicitly defers
"legacy-agent command-line product disposition" to a separate reviewed design.
`docs/design/PROJECT_PRIORITY_MAP.md` already places this census immediately after
the PostgreSQL no-tail closeout and before runtime-owner/CSS consolidation.

`docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md` records a live policy split:

- workbench/web research paths do not use trigger matching or automatic skill
  application;
- the legacy CLI and Discord paths do; and
- Track B must settle both call sites rather than let them remain a parallel policy.

The census therefore cannot decide CLI deletion from file age alone. It must measure
the capability and policy overlap first.

### 1.2 Measured entrypoint surface at the base

Static grounding at the exact base establishes:

- `src/agents/cli.py`: 2,781 lines, interactive chat plus slash-command routing;
- `src/agents/__main__.py`: 17 lines and an unconditional delegation to
  `src.agents.cli.main()` for `python -m src.agents`;
- `src/monitor/discord_bot.py`: 1,048 lines, with bot construction and `start_bot()`
  but no non-test application consumer that starts it;
- `README.md` still documents `python -m src.agents` as a supported invocation;
- `config/.env.template` and `requirements.txt` still expose Discord configuration
  and dependency declarations;
- 16 tracked non-test Python files contain direct `__main__` execution blocks;
- 10 tracked non-test Python files construct command-line parsers;
- 4 tracked shell entrypoints exist under the Seeking Alpha extension;
- 3 tracked `package.json` files define root, desktop, and web commands; and
- exactly 2 tracked paths have executable mode: the Firefox installer and the SA
  native host.

These counts overlap. They are grounding facts, not the final number of logical
entrypoints. The implementation plan must pin literal candidate rows and deduplicate
them by a reviewed identity, not add these counts together.

### 1.3 Known reachability facts

At the base:

- `src/agents/__main__.py` is the direct wrapper for the legacy interactive CLI;
- current app code does not import or start that wrapper;
- tests import selected CLI handlers and state types directly;
- Discord has substantial direct test coverage and notifier integration types, but
  no current app/bootstrap consumer starts `MindfulDiscordBot`;
- the desktop root command builds the web app and starts Electron;
- `src/api/__main__.py` is the local sidecar module entrypoint;
- the SA native host and install/uninstall scripts are external integration
  contracts, not alternate ArkScope products; and
- collector/audit/update commands may be operator surfaces even when they are not
  called by the desktop process.

"No current app consumer" and "safe to delete" are different claims. External
manifests, documented operator usage, subprocess call sites, and tests must all be
measured before reachability is assigned.

### 1.4 Current CLI-specific risks to measure

The interactive CLI currently:

- loads `config/.env` during module import;
- directly owns command parsing, prompt interaction, and presentation;
- exposes model, effort, reasoning, thinking, context, compaction, subagent,
  attachment, report, memory, monitor, and code-backend controls;
- calls shared provider runners and local capability/storage owners;
- auto-applies a uniquely matched skill before a query; and
- contains compatibility re-exports and CLI-specific output paths.

The census must separate wrapper/presentation ownership from shared application
capabilities. A future retirement plan may remove a wrapper while retaining a shared
runner, store, or domain function used by the app.

## 2. Census authority

### 2.1 Candidate universe

The implementation must derive candidates from tracked base bytes using independent,
closed extractors for all of these families:

1. every Python `__main__.py` module;
2. every Python `if __name__ == "__main__"` execution block;
3. every tracked Python command parser construction;
4. every tracked file with executable mode or an executable shebang;
5. every tracked shell script;
6. every script in each tracked `package.json`;
7. desktop, native-host, browser-extension, or similar external launch manifests;
8. literal subprocess/module targets launched by current product code;
9. current README/operator-document invocations; and
10. test consumers of candidates found by items 1-9, including direct imports of a
    candidate's launch function when no production caller exists.

Candidate extraction is lexical/structural. Classification happens later. A parser in
a library, a test-only wrapper, or a stale documented command is still emitted and
then adjudicated; the extractor may not silently decide that it is irrelevant.
Tests do not independently promote arbitrary library helpers into entrypoints; handler
and helper coverage belongs in the capability/test projections for an already grounded
candidate.

Generated, ignored, vendored, build-output, and packet files are outside the tracked
candidate universe. Any exclusion must have a closed reason and a literal path or
mechanically reproducible predicate.

### 2.2 Logical entrypoint identity

One logical entrypoint row is identified by:

```text
{tracked_path}::{entry_kind}::{symbol_or_script_name}
```

Multiple extractors may support one row. They must be recorded as evidence rather
than emitted as duplicate logical entrypoints. A module wrapper and the delegated
implementation remain distinct rows because they have different deletion and
documentation boundaries.

### 2.3 Machine-readable single source of truth

The census creates:

```text
docs/design/legacy_agent_cli_census/
  entrypoints.jsonl
  consumers.tsv
  capabilities.tsv
  tests.tsv
  current_invocations.tsv
  recommendations.tsv
  candidate_exclusions.tsv
  MANIFEST.sha256
```

`entrypoints.jsonl` is the authority. Every projection must be regenerated from it or
from a separately named raw grounding stream. Human prose may summarize the ledger
but may not introduce an untracked entrypoint, capability, consumer, or recommendation.

The human-readable result is:

```text
docs/design/LEGACY_AGENT_CLI_ENTRYPOINT_CENSUS.md
```

Execution evidence lives in a docs-only evidence file and an external packet. The
future implementation plan must pin exact paths, row counts, hashes, and generation
commands so an independent reviewer can rebuild every set from the base tree.

## 3. Closed row contract

### 3.1 Required entrypoint fields

Every `entrypoints.jsonl` row contains:

```text
entrypoint_id
tracked_path
entry_kind
symbol_or_script_name
invocation
product_role
reachability
owner
consumer_ids
test_node_ids
capability_ids
side_effects
app_equivalence
recommendation
decision_gate
evidence
```

Lists are sorted and duplicate-free. Evidence points to exact tracked call sites,
manifest keys, package scripts, or test nodes. A prose statement such as "probably
unused" is invalid evidence.

### 3.2 Closed entry kinds

```text
python_module
python_script
shell_script
npm_script
desktop_launcher
native_host
external_manifest_target
documented_command
```

`documented_command` is used only when current authority documents advertise a command
that no longer resolves to another candidate. Otherwise the document is a consumer of
the real entrypoint.

### 3.3 Closed product roles

```text
current_app_runtime
current_operator_command
integration_install_or_host
development_or_build_tool
legacy_agent_product
legacy_notification_surface
unowned_diagnostic
stale_documented_surface
```

Role answers what the entrypoint is for now. It does not decide whether it remains.

### 3.4 Closed reachability states

```text
app_started
external_contract
documented_manual
test_only
import_only
unreferenced
```

Reachability must account for Python calls, subprocess arguments, package scripts,
extension/native-host manifests, current documents, and tests. The strongest observed
state wins according to the order above, while all individual edges remain in
`consumers.tsv`.

### 3.5 Side-effect vocabulary

```text
provider_request
external_network
credential_read
local_state_read
local_state_write
filesystem_write
child_process
long_running_process
browser_or_extension_registration
none
```

The field records statically reachable capability, not a claim that the census ran the
command. `none` is exclusive.

### 3.6 App equivalence

```text
full
partial
none
not_applicable
unknown
```

Equivalence requires an exact current app/API/component/shared-owner witness. Similar
names or shared imports do not establish equivalence. `unknown` requires a stated
missing fact and cannot be converted silently to retention.

### 3.7 Recommendation and decision gate

Recommendations are closed:

```text
retain_current
retain_but_rehome_owner
fold_into_app_then_retire
retirement_candidate
remove_stale_invocation
needs_product_decision
```

Decision gates are closed:

```text
none
user_product_ruling
track_b_skill_policy
external_integration_confirmation
```

The census may recommend retirement, but it does not authorize deletion. The legacy
interactive CLI and Discord policy rows cannot have `decision_gate=none`. A current
operator command cannot become a retirement candidate merely because the desktop app
does not invoke it.

## 4. Legacy-agent capability comparison

### 4.1 Required comparison matrix

The census must decompose the legacy CLI and Discord surfaces into user-visible or
operational capabilities, including at least:

- provider/model selection;
- reasoning, effort, thinking, and context controls;
- interactive research query execution;
- manual skill invocation;
- implicit skill trigger/auto-apply behavior;
- attachments;
- conversation history;
- scratchpad, overflow, and compaction controls;
- reports and memory;
- Alpha Picks and monitor commands;
- code model/backend controls;
- token/status presentation;
- Discord query, follow-up, model, effort, and notification controls; and
- each local write or configuration mutation reachable from those controls.

For each capability, record:

1. the CLI/Discord owning symbol;
2. the shared backend/domain owner, if any;
3. the current app/API/UI equivalent and whether it is full, partial, or absent;
4. direct tests;
5. side effects and credentials;
6. whether Track B changes its policy meaning; and
7. what would be lost if only the wrapper were removed.

### 4.2 No file-level deletion inference

The ledger may not infer that every symbol in `src/agents/cli.py` is CLI-only or that
every symbol imported by the CLI must survive. Symbol consumers and current app owners
must be measured. Re-export compatibility, presentation helpers, and import-time setup
are separate from shared provider/domain capabilities.

### 4.3 Discord liveness

Tests prove that Discord code is executable; they do not prove that it is a live product
surface. The census must separately establish:

- a product/bootstrap consumer, if one exists;
- an external deployment or operator invocation, if documented;
- notifier coupling that does or does not require a running bot;
- dependency and credential ownership; and
- the Track B skill-policy overlap.

If no live launch edge exists, the result is `test_only`, `import_only`, or
`unreferenced` as grounded. It is not automatically deleted by this slice.

## 5. Safety and evidence boundaries

### 5.1 Static, provider-free census

The census must not launch interactive CLI, Discord, collectors, native hosts, desktop,
or provider commands. It must not read credential values, open production databases,
register browser integrations, or contact a network endpoint.

Safe evidence sources are tracked bytes, AST/structured manifest parsing, Git mode
metadata, isolated test collection, and current call graphs. Test collection runs only
in a fresh worktree with no `config/.env`, scratch `HOME`/stores, and the established
no-network boundary; no test body is required to discover node IDs. A `--help`
execution is unnecessary when static parser structure is available and is rejected for
modules with import-time side effects.

### 5.2 Secrets and git-crypt

Tracked encrypted paths are inspected only from the unlocked main worktree. Artifacts
may record path, field name, and structural match, never a secret value. Ciphertext
search is not absence evidence. Encrypted blobs must remain byte-identical because this
line is docs-only.

### 5.3 No product drift

All Python, TypeScript, JavaScript, shell, manifest, package, config, requirement, and
test paths are byte-protected for this census. Only the design, plan, map entry,
inventory authority, human census, and evidence paths are editable.

The census may identify a broken command or a P0 issue. It records the finding and
stops; it does not repair product code under an inventory commit.

## 6. Completion contract

The docs-only census is complete only when:

1. every raw candidate has exactly one logical entrypoint row or one closed exclusion;
2. every row uses only closed vocabulary values;
3. all extractor overlaps reconcile without information loss;
4. every current README/package/manifest/subprocess invocation resolves to one row;
5. every row has explicit reachability, owner, tests, side effects, app equivalence,
   recommendation, and decision gate;
6. all legacy CLI and Discord capabilities have a symbol-level comparison matrix;
7. consumer and test claims are grounded at real call sites/nodes;
8. recommendations do not claim authorization to edit or delete;
9. an independent implementation can regenerate every set and hash from the exact base;
10. product/test/dependency/config bytes equal the base; and
11. artifacts pass a path/secret leak audit and record zero provider/network/runtime
    execution.

The human census ends with a compact decision packet for the user:

- what is definitely current and should remain;
- what is stale independent of Track B;
- what the app already replaces;
- what capability would be lost by CLI/Discord retirement;
- what shared code remains even if wrappers retire; and
- the smallest coherent retirement/convergence choices.

If the user defers the decision, the census still closes successfully. No retirement
plan is opened until the user rules.

## 7. Hard stops for the implementation plan

Stop and amend before continuing if:

1. exact master differs from the reviewed base;
2. a candidate family in Section 2.1 cannot be represented by the row identity;
3. an entrypoint is excluded by executor judgment rather than a closed rule;
4. a current invocation, subprocess target, external manifest, or test consumer is
   unresolved;
5. reachability is inferred from naming or file location alone;
6. app equivalence lacks an exact current owner witness;
7. a side effect is hidden because the default branch usually avoids it;
8. one physical file is treated as one capability without symbol-level analysis;
9. Discord liveness is inferred from tests or dependency presence;
10. a recommendation silently becomes a product disposition;
11. any product, test, dependency, config, or runtime byte changes;
12. any live command, provider, network, production store, credential value, or external
    registration is touched; or
13. generated/ignored/ciphertext content is used as tracked absence evidence.

## 8. Alternatives rejected

### A. Delete `src/agents/cli.py` immediately

Rejected for this slice. Full retirement is an allowed eventual outcome, but immediate
deletion would mix the product decision with discovery and could accidentally remove a
shared owner or a capability not yet present in the app.

### B. Census only `src/agents/cli.py`

Rejected. The wrapper, README invocation, `src/agents/__main__.py`, Discord skill-policy
peer, tests, dependencies, config, subprocess consumers, and operator commands define
the real boundary.

### C. Preserve every CLI-shaped command

Rejected. Operator and integration commands may be current, while a legacy product or
unowned diagnostic may be pure maintenance cost. CLI syntax is not a product role.

### D. Merge this work into runtime-owner/CSS consolidation

Rejected. This census is docs-only and supports a user product ruling. Runtime ownership
and CSS boundaries are code architecture work and follow the census decision.

## 9. Handoff

After independent design review GREEN, Codex writes a RED-free/docs-only implementation
plan with literal candidate streams, reconstruction tools, validators, negative
self-tests, protected aggregates, per-task packets, and an independent final rebuild.
Fable reviews that plan before census execution.

After the census closes, the user may:

1. authorize a bounded retirement plan for the legacy CLI and/or Discord wrapper;
2. require Track B convergence before retirement;
3. retain a specifically justified surface; or
4. defer disposition and proceed only when explicitly ready.

Whichever choice is made, operator commands and current external integrations are not
collateral. The later runtime-owner/CSS boundary line remains separate.
