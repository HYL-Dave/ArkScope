# Legacy Agent Surface Retirement Design

> **Status:** DRAFT FOR INDEPENDENT REVIEW; DOCS-ONLY; NO PRODUCT OR TEST
> EDIT AUTHORIZED BY THIS COMMIT
>
> **Source base:** `2dabe0f174627d4a454342a431999eeb99f36b49`
>
> **Census authority:** `docs/design/legacy_agent_cli_census/` as merged and
> exact-master verified at the source base.

## 1. Decision and objective

The interactive terminal agent and the current Discord bot are no longer
ArkScope product surfaces. Their wrappers, presentation grammar, inactive
transport, wrapper-only controls, tests, dependencies, configuration examples,
and current-availability claims shall be retired without compatibility aliases,
tombstone modules, no-op settings, or placeholder launchers.

The objective is not to remove model-driven research. It is to remove obsolete
delivery surfaces while preserving capabilities that already have an
independent current owner:

- Research HTTP and desktop workflows;
- model-callable tools exposed through the in-process registries and bounded
  subscription bridges;
- Card synthesis and Card translation;
- monitoring engine, scheduler, local alert representation, console/log
  notifiers, and deduplication;
- automatic context compaction and its durable overflow store;
- the Skills registry, parsers, packaged resources, and Track B metadata; and
- the current replay/tool/subagent contracts that do not depend on the retired
  attachment path.

MCP, HTTP, and in-process tools remain acceptable capability interfaces.
Whether they should converge is a later architecture decision, not a
precondition for this retirement.

This ruling applies to commands owned by the abandoned interactive Agent and
Discord surfaces. Standalone collectors, audits, smoke tools, native hosts, and
other operator entrypoints are not wrapper compatibility and are unchanged in
this slice. That is a scope boundary, not a permanent retain ruling: their
ownership and delivery model belongs to the later runtime-owner/operator
workflow line.

## 2. Grounded current state

### 2.1 Entrypoints

The completed census contains 80 canonical entrypoints. Exactly three rows are
`fold_into_app_then_retire`:

1. `src/agents/__main__.py::python_module::src.agents`;
2. `src/agents/cli.py::python_script::main`; and
3. `src/monitor/discord_bot.py::python_script::MindfulDiscordBot`.

The terminal wrapper is documented but has no App launcher or importer. The
Discord implementation is test-only: there is no non-test constructor or
`start_bot()` caller. Tests and installed dependencies prove that code can be
constructed; they do not prove a live product.

### 2.2 Capability ownership

The census measured 42 terminal/Discord capabilities: 14 full App equivalents,
12 partial equivalents, and 16 with no current App equivalent. The product
ruling is capability-specific:

| Capability group | Ruling |
| --- | --- |
| Research query, model/provider/effort selection, thread history, reports, memory, monitoring, save, delegation | Retain the independently owned App/API/tool contracts; remove terminal/Discord presentation. |
| Terminal help/completion, verbose switch, temporary no-history mode, raw overflow inspection, one-shot force compaction, dead code-model selector | Retire deliberately; no replacement required. |
| Manual skill command, trigger matching, auto-apply, terminal suggestions | Retire the current producers. Keep registry/resources and Track B metadata; unattended automation is redesigned separately. |
| Discord delivery, buttons, commands, formatting, manage-guild policy | Retire the current implementation. Future alert transport starts from a new authorization/delivery design. |
| Current attachment input | Retire the entire old implementation; future document understanding starts from a new design. |

### 2.3 The attachment path is not shared product infrastructure

Static caller reconstruction at the source base found that only
`src/agents/cli.py` passes a non-empty `attachments=` value. The Research and
query routes do not expose an attachment request field. The generic agent
signatures, `AttachmentManager`, `attachments_shape` replay schema, attachment
fixture, and `pymupdf` dependency therefore form a dead terminal-owned path,
not a current App contract.

That path shall be removed atomically:

- `src/agents/shared/attachments.py` and its whole-file tests;
- attachment parameters and provider block conversion branches in both agent
  implementations;
- attachment classification, digest/size helpers, replay field, validator
  branch, fixture, and attachment-only tests; and
- the `pymupdf` requirement and current documentation claims.

The future Document Intelligence feature is not a restoration of this path.
It needs a new source-to-page pipeline, explicit ownership, security limits,
provenance, and model policy.

### 2.4 Model facts and terminal presentation are distinct

`src/model_capabilities.py` is the current model-fact registry and remains.
`src/model_routing.py` derives live routing choices from `in_routing_seed` and
remains. By contrast, `src/agents/shared/model_catalog.py` is explicitly the
terminal/Discord presentation view, and `in_cli_catalog` is an obsolete
membership axis. Both shall retire.

This slice does not update provider model inventories, credential visibility,
or Card translation routing. Those changes require separate evidence:

- official model-registry facts;
- credential-visible candidates;
- an exact-task canary proving the selected credential and transport can
  execute the Card translation contract; and
- a Traditional Chinese quality evaluation.

`GPT-5.3-Codex-Spark` remains a ChatGPT-subscription-specific Card translation
candidate, not a generic API seed or default. The desired Anthropic and OpenAI
catalog refresh also remains a separate line. An SDK upgrade is justified only
by a demonstrated SDK/request-shape incompatibility.

### 2.5 Skills metadata and current automatic behavior are distinct

The following remain because they are the substrate for later Track B work:

- `SkillDefinition` and its descriptive metadata, including `trigger` and
  `auto_apply` fields;
- deterministic registry rebuilding and tier precedence;
- aliases, packaged/custom resource parsing, listing, explicit expansion, and
  validation; and
- `resources/skills/`, `config/skills/`, and profile/trace contracts.

The following retire because their only product consumers are the two retiring
surfaces:

- `SkillMatchResult` and the runtime trigger index;
- terminal command parsing;
- current natural-language trigger matching and auto-apply context injection;
- terminal suggestion rendering; and
- the unused `load_custom_skills()` compatibility shim.

The system prompt must not advertise `/skill` or imply that automatic skill
application is currently active. It may keep the registry's names and
descriptions only when the copy labels them as registered workflow definitions
that are not automatically applied. This does not decide future Track B
policy.

### 2.6 Monitoring core and Discord transport are distinct

The monitor engine, scheduler, watchers, alert data type, deduplicator,
console/log notifiers, and model-callable `scan_alerts` tool remain. The
Discord-specific notifier, router branch, injected-bot seam, bot module,
dependency, environment template entries, and disabled profile channel retire.

Comments in retained monitor code shall describe the actual event-loop/thread
contract without naming a removed Discord gateway.

## 3. Target architecture

### 3.1 Product surfaces after cutover

After cutover, model-driven work enters through explicit current contracts:

```text
Desktop / HTTP request
        |
        v
Research or query route
        |
        +--> API-key agent implementation
        +--> subscription driver
        |
        v
model-callable tool registry / bounded bridge
```

There is no terminal interaction loop, slash-command grammar, Discord gateway,
or hidden wrapper that starts those paths.

### 3.2 No compatibility tail

The final tree must not contain:

- aliases or re-exports for removed modules/classes/functions;
- ignored terminal/Discord/attachment parameters;
- environment settings that are read but intentionally do nothing;
- comments or current docs claiming the retired surfaces are available; or
- generic fallbacks that infer behavior from the presence of old methods.

Git history is the implementation archive. The evidence packet records the
last commit containing each retired tracked path before deletion.

### 3.3 Card translation independence

Card translation remains a one-shot operation owned by
`POST /analysis/cards/{run_id}/translate` and `translate_card()`. It does not
need terminal conversation history. This slice preserves that contract
byte-for-byte except for documentation references that falsely bind it to the
retired wrapper.

### 3.4 Current history behavior

The App's persisted Research thread history remains. Retiring the terminal
`--no-history` mode does not force every future task to use history. A future
translation or document workflow may define an explicit stateless request or
bounded context/glossary contract. No generic terminal session mode is retained
for that possibility.

## 4. Explicitly separate follow-up designs

### 4.1 Document Intelligence

The next attachment/document design may evaluate
`https://github.com/firecrawl/pdf-inspector`, but no technical claim about that
project is adopted until a separate grounding spike. The desired product
contract must compare at least these modes:

1. automatic hybrid: detect text-bearing pages, tables, figures, and pages that
   need OCR, then apply the cheapest adequate path;
2. provider-native document input when the selected model and credential prove
   support;
3. all-pages vision for explicit fidelity overrides; and
4. local extraction only.

The design must allow a vision-capable OCR model to be selected, or inherit a
Research/Notes model only when that model supports images. It must define file
limits, page limits, temporary-file lifetime, secret/PII handling, page-level
provenance, table/figure evidence, cost estimates, cancellation, retries, and
partial-failure truth. Research and the future Notes workflow are likely
consumers; neither is implemented by this retirement slice.

### 4.2 Alert transport and external harnesses

Future unattended alerts may target Discord or another channel. OpenClaw,
Hermes Agent, DeepSeek harnesses, and similar systems are architecture
candidates, not current dependencies. A later design must decide trigger
authority, tool permissions, confirmation policy, delivery retries,
multi-user authorization, auditability, and failure isolation before choosing
a transport or harness.

### 4.3 Track B and Skills

Future skill suggestions, explicit activation, or automatic application must
be designed with the unattended-research policy. The retained registry is data
and parsing infrastructure, not evidence that auto-apply is live.

### 4.4 Interface convergence

An interface inventory may later decide whether HTTP, MCP, and in-process tool
contracts should converge. This retirement only proves that current required
capabilities remain reachable through at least one explicit product owner.

## 5. Configuration, secrets, and data

- Tracked Discord examples are removed in the product cutover.
- A post-merge operator step removes `DISCORD_*` keys from the private
  untracked `config/.env`, if present. The operation records key absence only,
  never values, and then asks the operator to restart the App/sidecar.
- No provider request, Discord connection, document upload, production DB
  mutation, push, or external harness installation belongs to this line.
- Existing Research threads, cards, reports, monitor state, and Skills resources
  are not migrated or deleted.

## 6. Verification contract

The implementation plan must provide:

1. exact pre/post backend collection streams and an unchanged frontend stream;
2. literal removal/addition ledgers for every node identity change;
3. RED-first negative contracts for each retired surface;
4. runtime regressions proving Research/tool/Card/monitor/compaction/Skills
   owners remain live;
5. a final source/config/dependency/current-doc no-tail census;
6. socket-guarded focused and canonical native runs with no live provider or
   Discord traffic;
7. mutations that revive each retired surface and make a named owner RED;
8. byte restoration after every mutation;
9. protected frontend and production-asset boundaries; and
10. a fresh exact-master replay before cleanup.

Any unexpected current consumer, identifier drift, external contact, secret
exposure, production mutation, or need for a compatibility fallback is a stop
and requires a bounded amendment.

## 7. Rejected alternatives

### A. Keep wrappers disabled for possible future reuse

Rejected. Disabled executable surfaces, config, and dependencies remain import
and maintenance liabilities. Git history preserves recovery.

### B. Preserve the current attachment stack for the future document feature

Rejected. It has no current App caller and encodes the wrong architecture:
provider-specific direct conversion, unconditional text extraction for one
provider, and no page-level routing/provenance policy. Retaining it would bias
the new design and leave dead dependencies alive.

### C. Reuse the current Discord bot for future alerts

Rejected as a default. Its command, authorization, action, and delivery model
predates the unattended automation design. Setup lessons may be recovered from
history, but the code does not retain product status.

### D. Delete all Skills infrastructure with the wrappers

Rejected. Registry/resources are independently relevant to future Track B and
model-callable workflows. Only the terminal/Discord producers retire.

### E. Update model catalogs in the same commit

Rejected. Provider facts, credential visibility, canary execution, SDK
compatibility, and translation quality require different evidence and can fail
independently.

## 8. Handoff

After this design and its RED-first plan pass independent review, implementation
may proceed in bounded tasks. Product implementation, merge, push, private
configuration edits, and live calls remain unauthorized until the plan's own
gates grant them.
