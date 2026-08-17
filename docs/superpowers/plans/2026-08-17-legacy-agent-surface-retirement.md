# Legacy Agent Surface Retirement Implementation Plan

> **Status:** TASK 0 INDEPENDENTLY REVIEWED GREEN; TASK 1 IMPLEMENTED;
> INDEPENDENT TASK 1 REVIEW NEXT; TASK 2 BLOCKED
>
> **Date:** 2026-08-17
>
> **Source base:** `2dabe0f174627d4a454342a431999eeb99f36b49`
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-17-legacy-agent-surface-retirement-design.md`
> in this docs-only authority commit, SHA-256
> `8302cbfb706d950a48a9ed4ac5d77cae10594cc292b01d681bf69955311784e1`.
>
> **Roles:** The user owns the product ruling. Codex authors and, after
> independent review, executes the cutover. Fable independently reconstructs
> ledgers, staged identities, RED/GREEN evidence, mutations, and final
> admission. No merge, push, private configuration edit, live provider or
> Discord action, document upload, or destructive data action is authorized by
> this plan-review commit.

**Goal:** Remove the abandoned interactive Agent CLI, its terminal-only
controls, the inactive Discord agent/transport, and the entire unowned legacy
attachment implementation without weakening the independently owned Research,
model-tool, Card, monitor, compaction, replay, or Skills-registry contracts.

**Architecture:** Current capability owners remain explicit: HTTP/Desktop
Research and query routes, provider agents, tool registries, Card endpoints,
the monitor engine/scheduler with local console/log notifiers, automatic
compaction with durable overflow storage, and the Skills registry/resources.
The retired wrappers do not leave aliases, ignored parameters, disabled
launchers, transport stubs, or current documentation claims. Future Document
Intelligence, alert transports, Track B automation, model-catalog refresh, and
MCP/API convergence remain separate designs.

**Tech stack:** Git, Python 3.10.12, pytest 8.4.1 with the pinned EIR-002
reporter, standard-library `ast`/`json`/`tokenize`, ripgrep, GNU `sha256sum`,
Node 22.14.0, and Vitest 4.1.8 for unchanged frontend collection/admission.

## Global Constraints

- The exact source is `2dabe0f174627d4a454342a431999eeb99f36b49`.
  Re-grounding may advance only through this docs-only authority commit; any
  product drift before Task 0 is a stop and requires all identities to be
  rebuilt.
- Product decisions are binding: the current CLI and Discord surfaces retire;
  the current attachment implementation retires in full; model-callable
  capability owners, Card translation, monitoring core, automatic compaction,
  Skills registry/resources, and current Research history remain.
- This slice does not implement Document Intelligence, alerts, external agent
  harnesses, unattended Skills automation, model-catalog refresh, Card
  translation model selection, SDK upgrades, or interface convergence.
- This slice does not remove standalone collectors, audits, smoke tools,
  native hosts, or other operator entrypoints. They are unchanged pending the
  later runtime-owner/operator workflow, not preserved as CLI compatibility.
- No compatibility alias, re-export, tombstone module, ignored parameter,
  presence-based fallback, disabled config key, or no-op launcher is admitted.
- All manual edits use the exact path boundary in
  `2026-08-17-legacy-agent-surface-retirement/owned-paths.tsv`. Any other path
  is a stop unless it is a packet-local artifact under `/tmp`.
- Every RED is collected before its owning product implementation. A missing
  new module or deleted old module is an admissible RED only for a newly added
  negative contract; import errors in existing retained suites are not.
- Node streams are canonical pytest IDs, byte-sorted under `LC_ALL=C`, unique,
  and end with exactly one newline. Counts never substitute for row identity.
- Node collection precedes runtime tests at each stage. A staged collection
  mismatch is a stop even if all executed tests pass.
- Focused tests run with a fail-closed socket guard. Exact loopback tests may be
  split by canonical node ID, as in the reviewed PG no-tail protocol; there is
  no destination-wide localhost exception.
- Canonical native admission uses a fresh worktree, scratch `HOME`, scratch
  runtime/data roots, no `config/.env`, no private keys, and no production DB.
  It must not reuse the obsolete `.env` symlink procedure removed by PG
  no-tail.
- Node commands use the root hoisted toolchain only. Verify Vitest 4.1.8 and
  invoke the explicit root binary. `npx`, `npm exec`, package installation,
  downloads, and app-local fallback are forbidden.
- No provider request, Discord connection, browser registration, document
  upload, external harness installation, secret-value read, production-store
  open, merge, or push occurs in Tasks 0-6.
- A real P0 incident may preempt this sequence. Otherwise this retirement
  completes before the runtime-owner/CSS boundary line.

## 0. Authority, Ledgers, and Baselines

### 0.1 Exact ownership ledger

The tracked authority is:

```text
docs/superpowers/plans/2026-08-17-legacy-agent-surface-retirement/owned-paths.tsv
```

It has one header plus 69 unique path rows and SHA-256
`5415e88e75952d3d302ec917d9b3db48b17541d026a969dc4eb0289168e855af`.
It is the complete path authority, including temporary governance documents
that delete themselves at closeout. `action=modify` is not permission for an
arbitrary rewrite: each row's boundary and the task contracts below still
apply.

### 0.2 Canonical base

The exact merged-master baseline is:

| Stream | Rows/files | SHA-256 |
| --- | ---: | --- |
| backend collection | 4,278 | `ecafdab7a1cee8d6f64dd6763f017d2ef15dd414b80065950f949d8b471a09ce` |
| frontend collection | 1,177 / 101 files | `c570a551b64ed95155c02f83499e78eb3409f2cba66ea9d46862dffad0ea239b` |
| affected backend projection | 444 | `930619b9cfdaf06bbca56a42a1540eda8f758d6b4d97ffb4963bf74b173d36e6` |
| native report | 4,266 passed / 12 skipped / 0 failed | `599e595960c34afc76e05ae76e30256a23fcbcfc1aafc585b7fbc71afa7a0a42` |

The 444-node projection is the union of these ten base test files:

```text
tests/test_attachments.py
tests/test_compressor_integration.py
tests/test_compressor_layer5.py
tests/test_eir006_retired_data_boundaries.py
tests/test_model_capabilities.py
tests/test_monitor.py
tests/test_replay.py
tests/test_replay_fixtures.py
tests/test_skills.py
tests/test_tools.py
```

The complete projection passed `444/444` at the source base. Therefore all 157
removed nodes below are grounded passing nodes, not already-dead tests.

### 0.3 Exact node authorities

Global identity changes are literal files:

| Ledger | Rows | SHA-256 |
| --- | ---: | --- |
| `backend-removals.nodes` | 157 | `be42d241d4ea54054a7d023648c4770c16226259d6f4ad230bb1eec430e0e389` |
| `backend-additions.nodes` | 18 | `028063ee3252fef37ff6a6a9f9f00d74da9ede7b9a0ffa59339f398a4ba14c3d` |

Every removal occurs exactly once in the base stream. Every addition is absent
from the base. The sets are disjoint. Applying exact set subtraction/addition
and globally byte-sorting gives final backend collection:

```text
4,278 - 157 + 18 = 4,139
SHA-256 bec7fb2e6119aef35b0949e39f4ad4c518e8eb4e03e2ad4391aaa28581fd3528
```

The final affected projection is 305 rows at
`581f6d41c16343359ad1b50e6d0ab2bc093ae869c00f40ab945a87b62140fa33`.
The native target is exactly 4,127 passed / 12 skipped / 0 failed, 4,139 seen:

```text
4,266 passing - 157 grounded passing removals + 18 required passing additions
= 4,127 passing
```

### 0.4 Per-task identity partitions

Task partitions are deterministic projections of the two literal global
ledgers, not separately editable authorities.

**Task 1 removals:** all removal rows in `test_attachments.py`,
`test_compressor_integration.py`, `test_replay.py`,
`test_replay_fixtures.py`, and `test_tools.py`; all five
`tests/test_compressor_layer5.py::TestCompactCommand::*` rows; and the exact
row `tests/test_monitor.py::TestModelCatalogShared::test_cli_reexports`.

**Task 1 additions:** the addition in `test_compressor_integration.py`, plus the
five new contracts whose names contain `agent_query_signatures`,
`card_translation`, `interactive_cli`, `model_callable_research`, or
`obsolete_attachment`.

**Task 2 removals:** all removal rows in `test_monitor.py` and
`test_model_capabilities.py` except the exact `test_cli_reexports` row already
assigned to Task 1.

**Task 2 additions:** all additions in `test_model_capabilities.py`, plus the
four new contracts whose names contain `discord_runtime`, `monitor_engine`,
`monitor_router`, or `model_registry`.

**Task 3 removals/additions:** every remaining literal row.

| Stage | Remove/add | Full rows/SHA-256 | Focused rows/SHA-256 |
| --- | --- | --- | --- |
| Task 1 | `73/c9c9a470a240850ccd0540c58160660bdb2bbb25bca877bd7192762e9d61c980`, `6/07e002f0473a11bad2a974613fa640b4b9f6be22b69cf71818acd199462cee71` | `4211/51731bfd5148351f1a88a45bb6c1042c49879b1817985a4bae1779c9e0fcf566` | `377/0ab96c4fbfe3938eb81b5d3f3f4a29866df1acb61ce69a760640bf0bb3202c29` |
| Task 2 | `54/792708b98f17694074f805ae54d930d3d0e0f675058a86fb96a61be1b58db0a0`, `8/4203776bd4ac9747652b620e11f54d1c7c71e8b1a7f10c33b2b86fdeb5784c58` | `4165/ce6d66bc842df6225522b41315719a4c625a48e06581a086d1c48cfcb7a9cc9a` | `331/20162bde14c6395eaa24a634a2050811e5c3444cd28376c9fff05c897237596a` |
| Task 3 | `30/6ae1929d6165b9fddb2575991b1fefd63beca9843e3af2cdb654864f4d074e67`, `4/a252354de729e54baedb044b4034344bc7899f43503ff9a44a021f71fddfbf36` | `4139/bec7fb2e6119aef35b0949e39f4ad4c518e8eb4e03e2ad4391aaa28581fd3528` | `305/581f6d41c16343359ad1b50e6d0ab2bc093ae869c00f40ab945a87b62140fa33` |

Each pair hash is the SHA-256 of its globally byte-sorted row stream with one
trailing newline. The staged stream is `(previous - removals) union additions`
under the same normalization.

The review amendment moves every direct `src.agents.cli` test consumer into
Task 1, where that module retires. It also admits one additional Task 2 body
evolution for a retained registry-consistency node that directly imports the
terminal catalog. Global `157/18` authority and the final identities do not
change.

### 0.5 Existing node bodies allowed to evolve

The global ledgers own all ID changes. Existing IDs may change bodies only in
this closed list:

| Task | Existing node ID | Permitted evolution |
| --- | --- | --- |
| 1 | `tests/test_replay.py::test_existing_fixtures_load_with_new_fields_as_none` | Remove only the deleted attachment-field assertion; keep subagent/tool-pin compatibility. |
| 1 | `tests/test_replay.py::test_load_openai_no_tool_fixture` | Remove only the deleted attachment-field assertion. |
| 1 | `tests/test_replay.py::test_validate_all_new_fixtures_clean` | Remove only the deleted attachment fixture from the explicit fixture tuple and make its stale four-fixture prose truthful; retain clean validation for every remaining named fixture. |
| 1 | `tests/test_replay.py::test_replay_capture_round_trips_new_fields` | Retain the remaining opt-in field round trip without manufacturing an attachment replacement. |
| 2 | `tests/test_model_capabilities.py::test_new_generation_entries_present_with_task0_facts` | Remove only terminal-catalog assertions; retain every model fact/routing assertion. |
| 1 | `tests/test_eir006_retired_data_boundaries.py::test_current_runtime_consumer_census_is_closed_and_exact` | Remove the retired CLI path from the exact current-owner set. |
| 2 | `tests/test_model_capabilities.py::test_registry_and_helpers_agree_for_every_pre_consolidation_id` | Remove only the terminal-catalog `get_effort_options` import, its now-unused expected-tuple assignment, and its two helper assertions; retain context-limit, max-output, thinking-mode, compaction, and 1M-membership checks. |
| 3 | `tests/test_compressor_layer5.py::TestLayer5Firing::test_noop_does_not_burn_circuit_breaker` | Exercise the same automatic short-history no-op/circuit behavior without a force flag. |

Editing a ninth existing node body is a stop-and-amend event.

All retained `TestNotificationRouter`, monitor engine/scheduler, Skills
registry/resource-parsing, replay tool/subagent, automatic compaction, and Card
owner nodes remain behaviorally unchanged.

### 0.6 Protected current capability owners

The following 23 paths are byte-protected through Tasks 0-6:

```text
apps/arkscope-web/src/Research.tsx
apps/arkscope-web/src/api.ts
config/skills/.gitkeep
resources/skills/builtin/earnings-prep/SKILL.md
resources/skills/builtin/full-analysis/SKILL.md
resources/skills/builtin/portfolio-scan/SKILL.md
resources/skills/builtin/sector-rotation/SKILL.md
resources/skills/equity-research/catalyst-calendar/SKILL.md
resources/skills/equity-research/earnings-analysis/SKILL.md
resources/skills/equity-research/idea-generation/SKILL.md
resources/skills/financial-analysis/competitive-analysis/SKILL.md
resources/skills/financial-analysis/comps-analysis/SKILL.md
resources/skills/financial-analysis/dcf-model/SKILL.md
src/agents/anthropic_agent/tools.py
src/agents/openai_agent/tools.py
src/api/routes/analysis_cards.py
src/api/routes/query.py
src/api/routes/research.py
src/card_synthesis.py
src/investor_profile.py
src/model_routing.py
src/research_run_manager.py
src/tools/registry.py
```

Recipe: sort these paths under `LC_ALL=C`, run standard `sha256sum` from the
repository root in that path order, preserve the exact output bytes with one
row per path, then hash that row stream. The source aggregate is
`8843a3f1aa82ecbe1fb854d9c562088e2db134d9087993c192351e905309e1c2`.

No frontend path is owned. Therefore the entire frontend product/test tree is
also diff-protected, and its collection must remain 1,177 rows / 101 files /
`c570a551b64ed95155c02f83499e78eb3409f2cba66ea9d46862dffad0ea239b`.

### 0.7 Pinned execution tools

Task 0 copies and re-hashes the reviewed canonical helpers into its packet:

```text
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928  arkscope_eir002_reporter.py
955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac  eir006_vitest_list_normalizer.py
1c925f5224952912981221479b8db11db64b3b6a37ef56862c29908775b4240b  socket_guard.py
fcfbabcfffd82db9417a3833c7cde8180b441ac664a8d2057c649d99729c9717  socket_guard_by_node.py
5ef1580c2e1e34f3fcecfabf7fb3d0cc495fce18de7f8718fdefdee5ce4915d5  build_sanitized_site.py
```

Expected versions are Python 3.10.12, pytest 8.4.1, Node 22.14.0, and Vitest
4.1.8. Drift is a stop-and-amend event, not install or download authority.

## 1. Product Contracts

### 1.1 CLI and attachment no-tail

Task 1 deletes `src/agents/__main__.py`, `src/agents/cli.py`, the old attachment
module, attachment tests, and attachment replay fixture. It also:

- removes `attachments` from both provider-agent public signatures and all
  provider block conversion branches;
- removes `attachments_shape`, its classifier/digest/size helpers, capture
  plumbing, load/save handling, and validator branch;
- makes `ReplayCapture.entrypoint` explicit with no terminal default and sets
  the Anthropic API capture to `entrypoint="api"`;
- removes only `pymupdf` from dependencies; and
- removes current `python -m src.agents` documentation.

The replacement tests must prove public agent signatures and replay schema have
no obsolete attachment surface, current Research/tool owners remain, and Card
translation remains a one-shot owner independent of conversation history.

### 1.2 Discord transport and terminal model-view no-tail

Across Tasks 1-2, the cut deletes `src/monitor/discord_bot.py`, 51 Discord test
nodes, and four terminal model-catalog test nodes. The one direct CLI re-export
owner retires in Task 1; Task 2 removes the other 50 Discord nodes and all four
terminal model-catalog nodes. It removes only the Discord notifier, router
branch, injected-bot seam, export, dependency, tracked environment examples,
and disabled profile channel. Console/log routing, monitor engine, scheduler,
watchers, deduplication, and `scan_alerts` remain.

Because `src/agents/shared/model_catalog.py` is shared by the CLI and Discord,
it remains during Task 1 and retires atomically in Task 2 after both consumers
are gone. The same Task 2 cut removes `in_cli_catalog` from the model capability
schema and assignments, plus the four false terminal-view test identities,
without changing any remaining model fact or routing membership.

Retained monitor comments describe their actual event-loop/thread behavior and
do not name the removed gateway. A config channel with an unimplemented type
continues through the generic unknown-channel behavior; there is no special
Discord compatibility branch.

### 1.3 Skills and compaction no-tail

Task 3 retains `SkillDefinition`, metadata parsing (including `trigger` and
`auto_apply` as data), registry rebuilding, aliases, expansion, listing,
validation, and all packaged/custom resources. It removes only:

- `SkillMatchResult`, trigger matching, current auto-apply context injection,
  terminal suggestion rendering, terminal command parsing, `can_auto_apply`,
  and the unused `load_custom_skills` shim/export;
- the system-prompt claim that users can activate `/skill` commands, replacing
  it with an honest registered-workflow label that says no workflow is
  automatically applied; and
- the one-shot force-Layer-5 field/helper/branch and `/compact` ownership.

Automatic threshold-driven Layer 5 compaction, its circuit breaker, summary
caller, durable overflow store, and App/server compaction behavior remain.
Multiblock user content stays supported and receives truthful test names that
do not describe the removed attachment feature.

The retained prompt copy is exact in meaning: `Registered workflow definitions`
replaces `Available skills`, and the adjacent sentence states `They are not
automatically applied.` The prompt may describe behavior when an explicit
product workflow supplies a selected skill prompt; it may not name a terminal
command or imply an automatic producer exists.

### 1.4 Current documentation and governance

Task 4 rewrites only the current-authority files enumerated in the ownership
ledger, deletes the dated wrapper-oriented Skills research document, and keeps
future Track B/Document Intelligence/alerts/model-catalog work explicitly
unimplemented. In `PROJECT_PRIORITY_MAP.md`, the bounded current P0.1 replay,
P1.4 compaction, model-catalog/drift-site, and localization summaries must stop
claiming retired surfaces; dated decision-log history remains. Historical Git
commits are the archive.

At Task 7, the completed census, this design, this plan, and their three ledger
files delete themselves. `PROJECT_PRIORITY_MAP.md` keeps only a concise dated
decision/closeout record. The historical EIR evidence at
`docs/superpowers/evidence/2026-08-08-oauth-lifecycle-quota-truth.md` is a
named dated exclusion, not current product authority.

## 2. RED-First Tasks

### Task 0: Re-ground exact authority

1. Create a fresh implementation worktree from the reviewed docs authority.
2. Prove source base ancestry and zero product/test drift since
   `2dabe0f174627d4a454342a431999eeb99f36b49`.
3. Recollect backend/frontend streams without running test bodies and compare
   byte-for-byte with Section 0.2.
4. Rebuild both global ledgers, all three per-task partitions, staged streams,
   focused streams, owned-path ledger, and protected aggregate from literal
   plan rows. Do not trust copied `/tmp` artifacts.
5. Run the affected ten-file baseline: require `444 passed` under the network
   boundary.
6. Record the user ruling and any approved batch cadence at the top of the
   priority-map decision log.
7. Produce a manifested packet and a docs-only plan/map status commit. No
   tracked evidence file is created. Stop for the review cadence in force; no
   product bytes change.

**Execution status (2026-08-17):** complete at reviewed tip `7953e90e`. Fresh
collect-only streams match backend `4278/ecafdab7...` and frontend `1177` / 101
files / `c570a551...`; all global, staged, focused, ownership, and protection
identities reconstruct exactly; and the ten-file runtime gate is `444 passed`
with zero socket attempts. Packet
`/tmp/legacy-agent-surface-retirement-task0-7953e90e` contains 69 manifested
payloads with `SHA256SUMS` SHA-256
`852dac69415aa8d4ba556d2003112ea2b55d798d2c0e289158a03aed3759a7a2`.
The default per-task review cadence remains in force. Independent Task 0
review returned GREEN. Task 1 pre-edit grounding then found one retained replay
owner whose explicit fixture tuple still names the Task 1-deleted attachment
fixture. No product or test byte had changed. Section 0.5 now admits only that
bounded fifth Task 1 evolution. Focused review returned GREEN for amendment
`d8891e50` and unlocked Task 1.

### Task 1: Retire CLI and the attachment stack

1. Add the six Task 1 identities and apply the five Task 1 body evolutions
   before product implementation. Collection must equal
   `4211/51731bfd...`. Exact RED is `4 failed / 373 passed`: the three new
   absence owners `agent_query_signatures`, `interactive_cli`, and
   `obsolete_attachment`, plus the evolved EIR-006 exact current-owner census.
   The three truthful replacement/preservation additions remain GREEN; forcing
   them RED would be rejected evidence.
2. Delete/modify exactly the Task 1 paths in `owned-paths.tsv`.
3. Do not edit those five bodies again during product implementation; verify
   their final deltas remain exactly within Section 0.5.
4. Recollect exact full/focused identities. Run all 377 focused owners with a
   fail-closed socket boundary; require `377/377`.
5. Prove the provider-agent signatures, replay serialization, fixture schema,
   dependencies, README, and product source contain no current CLI/attachment
   tail. The still-live Discord product consumer and terminal model-view module
   remain byte-exact pending Task 2; only their direct CLI re-export test owner
   has already retired.
6. Recheck the 23 protected paths and unchanged frontend stream.
7. Commit product/tests atomically, then commit plan/map status separately;
   evidence remains in the manifested packet.

**Execution status (2026-08-17):** implemented at product/tests commit
`ae0856c8`. The staged collection is byte-identical to
`4211/51731bfd...`; exact RED is `4 failed / 373 passed`, with only the three
planned absence owners and evolved EIR-006 owner failing. The product commit
changes exactly the 22 Task 1 owned paths. Final focused runtime is `377/377`
with zero socket attempts, final backend collection remains
`4211/51731bfd...`, frontend remains `1177` / 101 files /
`c570a551...`, and the 23 protected rows remain byte-identical at aggregate
`8843a3f1...`. Self-review strengthened the new signature owner to inspect all
five public provider query functions; a bounded OpenAI `run_query` parameter
mutation made that owner RED, and the product file was restored byte-exactly
before all final gates reran. The Task 2 Discord/model-view product consumers
remain byte-exact. Packet
`/tmp/legacy-agent-surface-retirement-task1-d8891e50` contains 73 manifested
payloads with `SHA256SUMS` SHA-256
`cc9783e315c06921ca0702b95537334092c617349c84dd4e86752db693dc0ea2`.
Task 1 now stops for independent implementation review; Task 2, merge, push,
live/provider/Discord/document actions, and destructive operations remain
unauthorized.

### Task 2: Retire Discord implementation, transport, and terminal model view

1. Add the eight Task 2 identities and apply the two Task 2 body evolutions
   before implementation. At staged identity `4165/ce6d66bc...`, require exact
   RED `3 failed / 328 passed`:
   `discord_runtime_config_and_dependency_are_absent` and
   `monitor_router_retains_local_channels_without_retired_transport` fail,
   along with `model_registry_has_no_terminal_catalog_membership_axis`. The
   monitor preservation owner and four truthful model replacements stay GREEN.
2. Delete/modify exactly the Task 2 paths. Remove `discord.py` and tracked
   `DISCORD_*` examples without reading private `config/.env`.
3. Do not edit any retained `test_monitor.py` node body. Do not further edit
   either evolved model-capability body. The existing 41 non-Discord monitor
   nodes, the three monitor contracts, and the terminal-view replacements must
   all pass.
4. Require exact focused `331/331`, full collection identity, protected
   aggregate, unchanged frontend stream, and zero socket attempts.
5. Prove source/config/dependency/tests have no current Discord implementation,
   explicit router branch, terminal model catalog, or `in_cli_catalog` axis.
6. Commit product/tests atomically, then plan/map status separately; evidence
   remains in the manifested packet.

### Task 3: Retire terminal Skills and one-shot force controls

1. Add the four Task 3 identities and apply the one Task 3 body evolution
   before implementation. At exact final collection identity, require RED
   `3 failed / 302 passed`: the automatic-compaction, Skill-runtime, and
   system-prompt absence contracts fail while the truthful multiblock rename
   stays GREEN.
2. Remove only the runtime helpers and prose in Section 1.3. Preserve all
   registry/resource/metadata behavior.
3. Do not edit the evolved body again during product implementation. Its final
   delta must stay within Section 0.5, and the automatic short-history no-op
   must still avoid burning the circuit breaker.
4. Require exact focused `305/305`, full collection
   `4139/bec7fb2e...`, protected aggregate, unchanged frontend, and zero socket
   attempts.
5. Prove `/skill`, terminal trigger/auto-apply helpers, terminal suggestion,
   force-Layer-5 controls, and compatibility shim are absent from current
   product/test surfaces while registry/resources and automatic compaction are
   live.
6. Commit product/tests atomically, then plan/map status separately; evidence
   remains in the manifested packet.

### Task 4: Rewrite current authority and close the no-tail census

1. Update/delete exactly the T4 documentation rows. Do not edit historical
   evidence outside the named ownership ledger.
2. Run a three-axis no-tail scan over tracked source/tests/config/dependencies,
   unlocked current documentation, and backlinks. It must find zero current
   executable/config claims for:

   ```text
   src.agents.__main__
   src.agents.cli
   python -m src.agents
   src.monitor.discord_bot
   MindfulDiscordBot
   DiscordNotifier
   _discord_notifier
   set_discord_bot
   DISCORD_BOT_TOKEN
   in_cli_catalog
   src.agents.shared.model_catalog
   src.agents.shared.attachments
   AttachmentManager
   PDFProcessor
   attachments_shape
   import fitz
   pymupdf
   discord.py
   request_force_layer_5
   force_layer_5_once
   force_layer_5_next
   SkillMatchResult
   can_auto_apply
   match_skill_trigger
   build_auto_apply_context
   render_skill_suggestion_cli
   parse_skill_command
   load_custom_skills
   ```

3. Findings inside this temporary design/plan, the completed census authority,
   dated decision-log entries, and the named historical EIR evidence are
   classified explicitly. The priority map outside its dated decision log is
   current authority and cannot be excluded. A broad `docs/**` exclusion is
   forbidden.
4. Run targeted import/call-graph checks proving no product importer or
   launcher references a removed module and no dead dependency remains.
5. Commit current-authority changes, then plan/map status separately; evidence
   remains in the manifested packet.

### Task 5: Mutations and final admission

For each mutation, save the diff, run its named owner to RED, restore every
owner byte-for-byte, and prove pre/post SHA equality before continuing:

| Mutation | Change | Required RED owner |
| --- | --- | --- |
| M1 | restore the interactive package launcher/current command | `test_interactive_cli_modules_and_documented_command_are_absent` |
| M2 | restore an attachment module, public parameter, or replay field | `test_obsolete_attachment_pipeline_and_dependency_are_absent` and `test_agent_query_signatures_and_replay_schema_have_no_obsolete_attachment_surface` |
| M3 | restore `in_cli_catalog` or terminal model catalog | `test_model_registry_has_no_terminal_catalog_membership_axis` |
| M4 | restore Discord module/dependency/config | `test_discord_runtime_config_and_dependency_are_absent` |
| M5 | restore Discord notifier/router branch | `test_monitor_router_retains_local_channels_without_retired_transport` |
| M6 | restore one-shot force compaction | `test_automatic_compaction_remains_without_one_shot_force_controls` |
| M7 | restore terminal Skill command/auto-apply helper or prompt claim | `test_skill_registry_has_no_terminal_command_or_auto_apply_helpers` and `test_system_prompt_does_not_advertise_terminal_skill_commands` |
| M8 | remove a retained Research/tool registration owner | `test_model_callable_research_and_tool_owners_remain_registered` |
| M9 | remove Card translation route/function ownership | `test_card_translation_remains_independent_of_conversation_history` |
| M10 | remove monitor engine/scheduler owner | `test_monitor_engine_and_scheduler_remain_available` |

Then run:

1. final backend collection and exact 305-node focused projection;
2. focused `305/305` with socket guard;
3. frontend list and sequential full `1177/1177` using the explicit root Vitest
   binary;
4. canonical native twice in independent scratch roots, each exactly 4,127
   passed / 12 skipped / 0 failed, with byte-identical reporter JSON;
5. sanitized-site-packages import/startup proof with no `discord`, `fitz`, or
   removed module available;
6. dynamic `app.routes` census proving Research/query/Card routes remain and no
   retired wrapper route was invented;
7. exact protected aggregate, ownership ledger, node ledgers, and no-tail scan;
8. production asset pre/post equality and zero production-store openers; and
9. leak/process/runtime cleanup checks.

Commit plan/map status only. Evidence remains in the manifested packet. Stop
for complete implementation review.

### Task 6: Independent implementation review

Fable independently reconstructs, without using executor generators as primary
evidence:

- source-base and tip collection streams;
- the 157/18 global ledgers and all three staged identities;
- the eight authorized body evolutions and all actual path diffs;
- every retained model/Skills/tool/monitor capability owner named by the twelve
  new contracts, reconstructed from source and tests without relying on a
  prose summary count;
- M1-M10 RED/restoration evidence;
- both canonical native reports, frontend result, protected aggregate,
  no-tail census, production boundary, and packet manifest.

Review GREEN alone authorizes Task 7. It does not authorize push or private
configuration edits.

### Task 7: Fast-forward merge, exact-master replay, and self-retirement

1. Prove current master is an ancestor of the reviewed implementation tip.
   Master drift is a stop; never force or synthesize a merge.
2. Fast-forward only, without push.
3. In a fresh exact-master worktree, repeat final collections, focused tests,
   frontend full, one canonical native run, no-tail census, protected aggregate,
   route/import checks, and cleanup with new artifact names.
4. Record `last-containing.tsv` for every deleted tracked path and prove a
   bounded sample is recoverable with `git show <commit>:<path>` without
   writing it into the worktree.
5. Delete the completed census authority, this design/plan, and their ledger
   files exactly as listed in `owned-paths.tsv`; update only the top priority-map
   closeout entry. This final governance commit contains no product/test byte.
6. Stop for focused closeout review. Branch/worktree cleanup follows GREEN.

After closeout review, the optional operator step removes private `DISCORD_*`
keys from untracked `config/.env` by key name only, records only absence, never
records values, and asks the user to restart App/sidecar. It is not part of the
merge commit and is not pre-authorized by this plan.

## 3. Stop-and-Amend Protocol

### 3.1 A-class: record and continue

An amendment may continue to the next planned gate without focused review only
when all four facts are mechanically true:

1. the exact path and source/test coordinate already exist in the ownership or
   node authority;
2. collection, focused, staged, route, protected, and path identities do not
   change;
3. the fix adds no method, branch, parameter, capability, fallback, or new
   product surface and only replaces a dead reference with the already pinned
   current owner or updates a fixture to the pinned contract; and
4. no other stop condition is touched.

The numbered amendment, diff, reasoning, and evidence still enter the plan,
priority map, and packet. Task 6 reviews every A-class decision. Misclassification
is grounds to reject and replay that segment.

### 3.2 B-class: hard stop for focused review

Any of these requires a bounded amendment and independent review before resume:

- any node ID, node ledger, staged hash, route identity, path ledger, or
  protected set changes;
- more than one reasonable product fix exists;
- a new consumer, capability, method, parameter, branch, dependency, config,
  or current-authority path is needed;
- any provider/network/Discord/document-upload call, secret value, production
  asset open/mutation, or other evidence contamination occurs; or
- an A-class prerequisite cannot be proven mechanically.

## 4. Hard Stop Conditions

Stop before commit when any of the following occurs:

1. source base or master ancestry differs from the pinned topology;
2. a path outside `owned-paths.tsv` changes;
3. a listed modify path has no real required diff or an unlisted path is needed;
4. a removal is absent/multiple in base, or an addition already exists;
5. any staged/full/focused/frontend/route/protected identity differs;
6. an existing node outside Section 0.5 changes body;
7. an old node is renamed without an exact removal/addition pair;
8. a new node passes before its owning product cut for the wrong reason;
9. an existing retained suite has an import/collection error;
10. compatibility aliases, ignored parameters, tombstones, or presence-based
    fallbacks are proposed;
11. agent public signatures retain attachment parameters;
12. replay retains attachment schema/classification or a terminal default;
13. model registry/routing facts change beyond removal of `in_cli_catalog`;
14. Card translation, Research, query, model tool, or subscription owners drift;
15. any frontend byte or collection identity changes;
16. Discord-specific code/config/dependency remains in current authority;
17. console/log monitor routing, engine, scheduler, watcher, or dedup behavior
    regresses;
18. Skills resources, registry rebuild, aliases, explicit expansion, listing,
    validation, or metadata are removed;
19. automatic compaction, circuit breaker, summary caller, or overflow storage
    regresses;
20. current docs claim an unimplemented future document/alert/Track B/model
    feature is live;
21. no-tail scanning uses a broad docs exclusion or ciphertext as absence
    evidence;
22. test tooling uses `npx`, downloads a package, or resolves the wrong Vitest;
23. a socket attempt occurs outside an exact admitted loopback owner;
24. a provider, Discord, browser registration, document upload, external
    harness, or live model request occurs;
25. a private secret value or raw git-crypt plaintext enters an artifact;
26. a production DB/runtime asset is opened or changes;
27. a mutation owner stays GREEN or byte restoration is incomplete;
28. canonical runs differ from 4,127P/12S/0F or from each other;
29. process, link, scratch root, temporary config, or port cleanup is incomplete;
30. a drafting marker or ambiguous recipe remains, or a binding identity has
    no full-length hash in its authority section (later shorthand is allowed);
31. merge would not be a pure fast-forward; or
32. any push, private `.env` edit, or destructive action is attempted before
    its explicit later authorization.

## 5. Commit and Evidence Protocol

- Task 0 is docs-only. Tasks 1-4 use one atomic product/tests/current-authority
  commit followed by one plan/map status commit per task. Task 5 is plan/map
  status only. No tracked evidence file is created. Do not squash.
- Every packet is under a new `/tmp/legacy-agent-surface-retirement-*` root and
  contains commands, versions, source/tip identities, raw node streams,
  RED/GREEN transcripts, socket/process/asset witnesses, path/protected
  manifests, rejected attempts, cleanup receipts, and `SHA256SUMS`.
- Rejected evidence remains labelled with reason, boundary, and resolution. It
  is never silently promoted because a later command passed.
- Artifacts contain no secret values, raw document data, provider responses,
  private home paths, or production rows.
- The worktree is clean at every review gate. No required execution session is
  left running.

## 6. Handoff

Independent plan review must first reconstruct every Section 0 hash and verify
that the owned-path and protected sets match the design. Review must also check
that the eight existing-body evolutions are complete, the twelve new contracts
have genuine product owners, and each mutation can make a named owner RED.

Focused plan re-review and independent Task 0 review returned GREEN under the
default per-task review cadence. Task 1 product implementation remains blocked
until focused review accepts the bounded fifth Task 1 body evolution. Later
work order is:

```text
legacy-agent surface retirement
  -> runtime-owner/CSS boundary and schedule-read test hardening
  -> separately prioritized Document Intelligence / alerts / Track B /
     model-catalog and Card-translation work
```
