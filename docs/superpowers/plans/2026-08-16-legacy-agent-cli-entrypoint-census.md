# Legacy-Agent CLI and Entrypoint Census Implementation Plan

> **Status:** TASKS 0-4 COMPLETE; LOCALLY MERGED AT `e7851975`; EXACT-MASTER
> VERIFIED; FOCUSED CLOSEOUT REVIEW NEXT; NOT PUSHED; NO RETIREMENT AUTHORIZED
>
> **Date:** 2026-08-16
>
> **Product/census source base:**
> `241ccdba6dc7c2cf1b162dd254ada88f25b6a9b0`
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-16-legacy-agent-cli-entrypoint-census-design.md`
> at commit `8321207cf5f15baa0b70f9394ed6d3ae30135206`, SHA-256
> `575b5b567282e8ae43fff59ec024a25c20a394d09445165c6e82cf8c1a49c8c8`.
>
> **Roles:** Codex authors and executes this docs-only census after independent
> plan review. Fable independently reconstructs candidate sets, classifications,
> projections, hashes, and admission evidence. The user alone owns any later
> Track B, skill-policy, Discord, retirement, merge, push, live-command, secret,
> or destructive-data ruling.

**Goal:** Produce a complete, mechanically reconstructable census of every
tracked ArkScope entrypoint and command surface, with a symbol-level comparison
of the legacy interactive CLI and Discord agent against the current app. The
result provides recommendations and an explicit decision packet; it changes no
product or test bytes and authorizes no retirement.

**Architecture:** Static extractors read exact Git blobs and structured manifests
without importing product modules. One canonical `entrypoints.jsonl` ledger owns
logical entrypoints and their present role, reachability, owner, tests, side
effects, app equivalence, recommendation, and decision gate. Raw candidate
observations live in manifested packets and close to either one canonical row or
one closed exclusion. Normalized consumer, capability, test, and invocation
authorities are generated in the same deterministic pass and cross-reference the
ledger; `recommendations.tsv` is its lossless projection. CLI/Discord capabilities
are analyzed by symbol and call site, not inferred from file ownership or test
presence.

**Tech stack:** Git, Python 3.10.12 standard-library `ast`/`json`/`tokenize`,
structured JSON/package/extension-manifest parsing, ripgrep, GNU `sha256sum`,
`jq`, pytest 8.4.1 collect-only with the pinned EIR-002 reporter, Node 22.14.0,
and Vitest 4.1.8 list JSON with the pinned normalizer.

## Global Constraints

- The exact product and candidate source is
  `241ccdba6dc7c2cf1b162dd254ada88f25b6a9b0`. Design, plan, evidence, and
  generated inventory docs are not candidate inputs and cannot recursively
  enlarge the census.
- This line is docs-only. No Python, JavaScript, TypeScript, shell, manifest,
  package, dependency, config, test, README, or other product/current-authority
  byte may change.
- The census never imports, executes, invokes with `--help`, or uses `runpy` on
  `src.agents.__main__`. That module calls `main()` unconditionally at line 17;
  importing it launches an interactive long-running process. Its delegated
  `src.agents.cli` module calls `_load_env()` at import time on line 72 and may
  read `config/.env`. Its canonical row must therefore include both
  `long_running_process` and `credential_read` even though no census process is
  permitted to trigger either side effect.
- No interactive CLI, Discord bot, collector, audit, native host, browser,
  desktop shell, sidecar lifespan, scheduler, provider CLI, package script, or
  tracked entrypoint is executed. No provider/network request, browser
  registration, production-store open, or credential-value read is authorized.
- Test discovery is collect-only in a fresh worktree with no `config/.env`, a
  scratch `HOME`, scratch runtime paths, a fail-closed network boundary, and an
  exact import blocker for `src.agents.__main__`. Test bodies do not run.
- Node commands use the root hoisted toolchain only: link worktree
  `node_modules` to the main root `node_modules`, verify Vitest exactly 4.1.8,
  and invoke `../../node_modules/.bin/vitest` explicitly from
  `apps/arkscope-web`. `npx`, `npm exec`, install, download, and app-local
  `node_modules` fallback are forbidden.
- The three git-crypt documents are scanned as plaintext only in the unlocked
  main tree after proving their Git blobs equal the source base. Artifacts may
  retain only normalized command tokens, path, and line; no surrounding
  plaintext or secret value may enter a packet.
- Every canonical JSON record is emitted with
  `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)`.
  Every JSONL/TSV/row stream is globally sorted by UTF-8 bytes, unique by its
  specified key, and ends with exactly one newline.
- Recommendations are not dispositions. The legacy CLI and Discord rows must
  retain a non-`none` decision gate. Information gaps produce a documented
  user/Track B gate, never an executor choice to retain or delete.
- A real P0 incident may preempt this sequence. Otherwise the census completes
  before any retirement plan or runtime-owner/CSS boundary work.
- No merge or push is authorized by this plan review.

---

## 0. Authority, Files, Schemas, and Baselines

### 0.1 Scope

This plan implements only the reviewed docs-only census. It does not modify or
retire an entrypoint, converge Track B, change skill auto-apply policy, start
Discord, clean `config/.env`, touch the private PG dump, or implement the later
runtime-owner/CSS line.

### 0.2 Tracked file ownership

Create during execution:

```text
docs/design/LEGACY_AGENT_CLI_ENTRYPOINT_CENSUS.md
docs/design/legacy_agent_cli_census/entrypoints.jsonl
docs/design/legacy_agent_cli_census/consumers.tsv
docs/design/legacy_agent_cli_census/capabilities.tsv
docs/design/legacy_agent_cli_census/tests.tsv
docs/design/legacy_agent_cli_census/current_invocations.tsv
docs/design/legacy_agent_cli_census/recommendations.tsv
docs/design/legacy_agent_cli_census/candidate_exclusions.tsv
docs/design/legacy_agent_cli_census/MANIFEST.sha256
docs/superpowers/evidence/2026-08-16-legacy-agent-cli-entrypoint-census.md
```

Modify only for process/status synchronization:

```text
docs/superpowers/plans/2026-08-16-legacy-agent-cli-entrypoint-census.md
docs/superpowers/specs/2026-08-16-legacy-agent-cli-entrypoint-census-design.md
docs/design/PROJECT_PRIORITY_MAP.md
```

Any other tracked path is a stop-and-amend event. Current documentation claims
are inventoried; this line does not correct them.

### 0.3 Canonical `entrypoints.jsonl` schema

Each line contains exactly these keys. This example fixes the known identity and
import-side-effect fields; all other classification values are schema examples,
not predicted Task 2 conclusions:

```json
{
  "app_equivalence": "unknown",
  "capability_ids": ["research_query", "skill_auto_apply"],
  "consumer_ids": ["consumer:README.md:61:documented"],
  "decision_gate": "track_b_skill_policy",
  "entry_kind": "python_module",
  "entrypoint_id": "src/agents/__main__.py::python_module::src.agents",
  "evidence": ["candidate:python_module_wrapper:src/agents/__main__.py:-:-:module:src.agents", "src/agents/__main__.py:9:delegate", "src/agents/__main__.py:17:unconditional_call"],
  "invocation": "python -m src.agents",
  "owner": "src/agents/cli.py:main",
  "product_role": "legacy_agent_product",
  "reachability": "documented_manual",
  "recommendation": "needs_product_decision",
  "side_effects": ["credential_read", "long_running_process"],
  "symbol_or_script_name": "src.agents",
  "test_node_ids": [],
  "tracked_path": "src/agents/__main__.py"
}
```

Rows are sorted by UTF-8 bytes of `entrypoint_id`, which is exactly:

```text
{tracked_path}::{entry_kind}::{symbol_or_script_name}
```

Required keys are exact; extra or missing keys fail validation. Arrays are
byte-sorted and duplicate-free. `tracked_path` is a tracked source-base path.
For an external binary or service declared by a tracked caller, it is the
declaration/caller path, `entry_kind` is `external_manifest_target`, and the
symbol is prefixed `external:`. This preserves the design's closed kind set and
identity without pretending an untracked binary is a repository file.

`owner` is a concrete `tracked_path:symbol`, `external:<contract>`, or
`unowned:<bounded reason>`. A row may not say merely `unknown`. Evidence entries
are either `candidate:<candidate_id>` bindings or normalized `path:line:kind`
references and never include arbitrary source text or secret values.

The closed `entry_kind`, `product_role`, `reachability`, `side_effects`,
`app_equivalence`, `recommendation`, and `decision_gate` values are copied
verbatim from design Sections 3.2-3.7. Validators reject any extension.

The specific `src.agents` module row above has immutable safety requirements:

```text
tracked_path = src/agents/__main__.py
entry_kind = python_module
symbol_or_script_name = src.agents
side_effects includes exactly credential_read and long_running_process among
  all other statically grounded effects
decision_gate != none
```

Dropping either side effect is a stop even if the module was never executed.

### 0.4 Candidate observations and closure

Raw observations are packet-local compact JSONL rows with exact keys:

```text
candidate_id
column
detail
kind
line
path
source_family
symbol
```

Candidate ID is:

```text
{source_family}:{path}:{line-or--}:{column-or--}:{kind}:{symbol-or--}
```

The source-family vocabulary is closed:

```text
python_module_wrapper
python_main_guard
python_parser
file_executable_mode
file_shebang
shell_path
npm_script
desktop_manifest
browser_manifest
python_subprocess_target
javascript_subprocess_target
generated_native_manifest_contract
documented_command
test_consumer
```

Logical kind resolution is deterministic:

1. tracked `__main__.py` wrappers use `python_module`;
2. other tracked Python launch targets use `python_script`;
3. shell targets use `shell_script`;
4. each package-script declaration remains its own `npm_script` wrapper;
5. the Electron main/dev targets use `desktop_launcher`;
6. the SA Python host and stable shell launcher use `native_host`;
7. tracked browser-manifest targets and other tracked non-Python launch targets
   use `external_manifest_target`;
8. a manifest/subprocess external target uses `external_manifest_target` with
   the declaring tracked path and `external:` symbol; and
9. `documented_command` is created only when a current documented invocation
   cannot resolve to another row.

The strongest applicable rule wins for the implementation target, while each
wrapper remains a separate row. Thus the `src/api/__main__.py` main-guard
observation supports its `python_module` row, the root npm `start` wrapper and
Electron main target remain distinct, and Chrome/Firefox observations may both
support one tracked background target without duplicate rows.

Every raw candidate ID must occur exactly once either as
`candidate:<candidate_id>` in one canonical row's tracked `evidence` array or
in tracked `candidate_exclusions.tsv`. Candidate IDs cannot map to two rows.
The closure therefore remains reconstructable from Git after external packets
are removed.

`candidate_exclusions.tsv` columns are:

```text
candidate_id	reason	evidence
```

Closed reasons are:

```text
historical_or_governance_invocation
```

Overlapping main-guard/parser/shebang/mode/manifest observations all bind to the
same logical row through distinct candidate evidence; none is discarded as a
duplicate. A stale command advertised by current authority is not an exclusion;
it becomes a `stale_documented_surface` row. Historical plan or decision-log
examples may use `historical_or_governance_invocation` only with line-level
authority evidence.

### 0.5 Projection contracts

`consumers.tsv`:

```text
consumer_id	entrypoint_id	consumer_kind	path	line	symbol	evidence
```

Closed consumer kinds:

```text
application_call
subprocess_launch
package_delegation
external_manifest
documented_invocation
test_import
test_execution
```

`capabilities.tsv`:

```text
capability_id	surface	entrypoint_id	owner_symbol	shared_owner	app_owner	app_equivalence	track_b_sensitive	side_effects	loss_if_removed
```

`surface` is `legacy_cli` or `discord`; `track_b_sensitive` is literal
`true`/`false`. `loss_if_removed` is a bounded sentence with no tab/newline.

`tests.tsv`:

```text
entrypoint_id	test_node_id	relationship	suite
```

Closed relationships are `direct_import`, `launch_contract`,
`capability_owner`, and `documentation_contract`; suite is `backend` or
`frontend`.

`current_invocations.tsv`:

```text
entrypoint_id	authority_path	line	invocation	status
```

Status is `current`, `stale`, `historical`, or `test_fixture`.

`recommendations.tsv` is a lossless projection of:

```text
entrypoint_id	product_role	reachability	app_equivalence	recommendation	decision_gate
```

#### 0.5a Normalized-authority amendment (2026-08-17)

The original sentence claimed every TSV could be regenerated solely from
`entrypoints.jsonl` plus the candidate join. That is impossible under the fixed
schema: the JSON ledger stores consumer, capability, and test IDs, but not the
detail columns required by those TSVs (`consumer_kind`, capability owners and
loss, or test relationship). Pretending otherwise would make validator item 20
non-discriminating and violate stop condition 30.

The authority model is therefore:

- `entrypoints.jsonl` is canonical for one-row-per-logical-entrypoint facts;
- `consumers.tsv`, `capabilities.tsv`, `tests.tsv`, and
  `current_invocations.tsv` are normalized detail authorities generated in the
  same pass from the exact source base, Task 1 candidates/test joins, and the
  reviewed classification rules;
- `candidate_exclusions.tsv` is the closed candidate-closure authority;
- `recommendations.tsv` is the only pure lossless projection of
  `entrypoints.jsonl`; and
- every detail row must foreign-key to the ledger, while each ledger ID array
  must equal the corresponding normalized-authority projection.

No authority file is hand-edited. Two independent complete generation runs must
be byte-identical, and Task 3 independently reconstructs all normalized
authorities from source facts rather than trusting the Task 2 generator. This
amendment changes no schema, candidate ID, candidate count, source base, tracked
file set, product byte, or recommendation authority.

### 0.6 Exact base and tool identities

The source base has:

| Stream | Count | SHA-256 |
|---|---:|---|
| backend collection | 4,278 | `ecafdab7a1cee8d6f64dd6763f017d2ef15dd414b80065950f949d8b471a09ce` |
| frontend collection | 1,177 / 101 files | `c570a551b64ed95155c02f83499e78eb3409f2cba66ea9d46862dffad0ea239b` |
| four CLI/Discord owner files | 209 | `a57b4414d626d15ba37c21326e40c78dce70b76e55e212d8a72c674e1cedab0a` |
| Discord owner file | 92 | `30ce40ca6db5e2bd6d139351b2b06a8c0643529189255f2f6cb25386fb8012d0` |

The 209-node owner projection is the byte-sorted union of:

```text
tests/test_compressor_integration.py  39
tests/test_compressor_layer5.py        55
tests/test_monitor.py                  92
tests/test_tools.py                    23
```

These are collection identities, not claims that all 209 nodes directly own a
CLI/Discord behavior. Task 2 must identify exact direct nodes rather than grant
file-level ownership.

Pinned helper hashes:

```text
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928  arkscope_eir002_reporter.py
955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac  eir006_vitest_list_normalizer.py
```

Expected tools are Python 3.10.12, pytest 8.4.1, Node 22.14.0, and Vitest
4.1.8. Version drift is a stop-and-amend event, not an install authorization.

### 0.7 Literal plan-author grounding streams

All rows below are UTF-8 byte-sorted with one trailing newline. The five
design-review streams are literal and overlapping by design.

#### Non-test direct `__main__` guards: 16 / `2a3fe77398bf40d399781c1fdd25cc0a27a383b75a55ea54d51eda54647b42c6`

```text
data_sources/financial_metrics_calculator.py
data_sources/sec_earnings_releases.py
data_sources/sec_insider_trades.py
extensions/sa_alpha_picks/build_firefox.py
src/agents/cli.py
src/api/__main__.py
src/audit/ibkr_news_catchup_audit.py
src/audit/sa_article_reconciliation.py
src/audit/universe_retirement.py
src/collectors/finnhub_news.py
src/collectors/polygon_news.py
src/daily_update.py
src/news_normalized/ibkr_cli.py
src/options_math/option_pricing.py
src/prices_runtime.py
src/sa_native_host.py
```

Three test paths also contain direct guards, making the all-tracked stream
19 / `e6d94b2fa319b7fab587bf372af9d6b3a8b6b3a02465680e65a9cf0de4e41b7c`:

```text
tests/live/smoke_fred.py
tests/test_ibkr_scanner.py
tests/test_option_pricing.py
```

#### Parser-construction paths: 10 / `9dc2361e00fac587f9a6b7af6de3a32c80204d52d89268193000e1c646218df8`

```text
extensions/sa_alpha_picks/build_firefox.py
src/agents/cli.py
src/audit/ibkr_news_catchup_audit.py
src/audit/sa_article_reconciliation.py
src/audit/universe_retirement.py
src/collectors/finnhub_news.py
src/collectors/polygon_news.py
src/daily_update.py
src/news_normalized/ibkr_cli.py
src/prices_runtime.py
```

#### Shell paths: 4 / `c7bf1f1a5751addec5f12e046563202bcd58d00d1d2c2af54a5871e8e9b4924a`

```text
extensions/sa_alpha_picks/install.sh
extensions/sa_alpha_picks/install_firefox.sh
extensions/sa_alpha_picks/native_host_launcher.sh
extensions/sa_alpha_picks/uninstall.sh
```

#### Package manifests: 3 / `1726c5e1f94cfca45b519de6998d3487a8fb118605ef984ba5f8effa664e0d30`

```text
apps/arkscope-desktop/package.json
apps/arkscope-web/package.json
package.json
```

#### Executable-mode paths: 2 / `c51acae446809281a36386c05cfb83e94249f4613ea60f3e578628c5e603831e`

```text
extensions/sa_alpha_picks/install_firefox.sh
src/sa_native_host.py
```

Additional required streams:

- package `__main__.py`: 2 /
  `720781cd2667caa075a8c6c4c6268584af5892a84ee832e699ae284a9ffc075a`
  (`src/agents/__main__.py`, `src/api/__main__.py`);
- shebang paths: 15 /
  `3f53bfa0d770fb38e8dea167fe345f1f4b69d78b6434a15a3429289d8c45bf63`;
- npm scripts: 12 /
  `2d60d0890af322f01a077f050c4215020619770a066403b2095a748db48057fb`;
- desktop/browser/test-fixture manifest targets: 13 /
  `efcb8df26aadea16204d7fcd140e2b06afeabd4db5c017daed089c27ce05130b`;
- current README command tokens: 8 /
  `f5ad84174df725b22c94ba6b5d7f30d20d78714169193d1b8982fe2edd4642ef`;
- command-shaped rows from non-superpowers tracked Markdown, including the
  unlocked encrypted document: 52 across 15 paths /
  `9a36d3138ec8ee6dea90ab60539ad323d639aab0ffe3ef93296d6519e8e4ba8a`;
  path stream SHA
  `37906c5b4e37b9d4b0d0dfdf73912df4817a540a016d21890117edd3cf7c68f9`;
- five required current launch edges /
  `e8474c73b3d7f867ede01a14ad938f0ccfec4719fb96b081e6313e5676feeb88`.

The Markdown command stream reads exact source-base blobs from every tracked
`*.md` path except `docs/superpowers/plans/**`,
`docs/superpowers/evidence/**`, and `docs/superpowers/specs/**`. Under
`LC_ALL=C`, it emits every non-overlapping match of this POSIX ERE as
`path:line:match`, then byte-sorts uniquely with one trailing newline:

```text
python(3)?[[:space:]]+-m[[:space:]]+[A-Za-z0-9_.-]+|python(3)?[[:space:]]+[A-Za-z0-9_./-]+\.py|npm[[:space:]]+(run|start|test|install)([[:space:]][A-Za-z0-9_:./@-]+)?|bash[[:space:]]+[A-Za-z0-9_./-]+\.sh|\./[A-Za-z0-9_./-]+\.sh
```

The three encrypted paths are removed from the locked input and scanned with
the same matcher in the unlocked main tree only after blob equality. The 15
command-bearing paths are exactly:

```text
README.md
data_sources/IBKR_GUIDE.md
data_sources/PAID_SUBSCRIPTION_EVALUATION.md
docs/analysis/SCORING_VALIDATION_METHODOLOGY.md
docs/data/IBKR_NEWS_API_LIMITATIONS.md
docs/data/NEWS_DATA_INVENTORY.md
docs/design/DESKTOP_SHELL_SPIKE_PLAN.md
docs/design/P0_1_FULL_V1_SPEC.md
docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md
docs/design/PROJECT_PRIORITY_MAP.md
docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md
docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md
docs/design/SA_EXTENSION_ROADMAP.md
extensions/sa_alpha_picks/FIREFOX.md
tests/live/README.md
```

The eight normalized README command tokens are exactly:

```text
bash extensions/sa_alpha_picks/install.sh
bash extensions/sa_alpha_picks/install_firefox.sh
npm install
npm run dev:desktop
npm run dev:web
python -m src.agents
python -m src.api
python -m src.daily_update
```

The npm rows are exactly:

```text
apps/arkscope-desktop/package.json	start	electron .
apps/arkscope-web/package.json	build	tsc --noEmit && vite build
apps/arkscope-web/package.json	check:i18n-literals	node scripts/i18n/visible-literal-scanner.mjs check
apps/arkscope-web/package.json	dev	vite
apps/arkscope-web/package.json	preview	vite preview
apps/arkscope-web/package.json	test	vitest run
apps/arkscope-web/package.json	test:watch	vitest
apps/arkscope-web/package.json	typecheck	tsc --noEmit
package.json	build	npm run build --workspace apps/arkscope-web
package.json	dev:desktop	node apps/arkscope-desktop/dev.js
package.json	dev:web	npm run dev --workspace apps/arkscope-web
package.json	start	npm run build && npm run start --workspace apps/arkscope-desktop
```

The 15 shebang paths are exactly:

```text
apps/arkscope-desktop/dev.js
apps/arkscope-web/scripts/i18n/visible-literal-scanner.mjs
data_sources/financial_metrics_calculator.py
extensions/sa_alpha_picks/build_firefox.py
extensions/sa_alpha_picks/install.sh
extensions/sa_alpha_picks/install_firefox.sh
extensions/sa_alpha_picks/native_host_launcher.sh
extensions/sa_alpha_picks/uninstall.sh
src/collectors/finnhub_news.py
src/collectors/polygon_news.py
src/daily_update.py
src/sa_native_host.py
tests/live/smoke_fred.py
tests/test_ibkr_scanner.py
tests/test_option_pricing.py
```

The 13 structured manifest targets are exactly:

```text
apps/arkscope-desktop/package.json	main	main.js
extensions/sa_alpha_picks/manifest.firefox.json	action.default_popup	popup.html
extensions/sa_alpha_picks/manifest.firefox.json	background.scripts	background.js
extensions/sa_alpha_picks/manifest.firefox.json	background.scripts	compat_firefox.js
extensions/sa_alpha_picks/manifest.firefox.json	background.scripts	extension_diagnostics.js
extensions/sa_alpha_picks/manifest.firefox.json	background.scripts	extension_run_protocol.js
extensions/sa_alpha_picks/manifest.firefox.json	background.scripts	extension_telemetry.js
extensions/sa_alpha_picks/manifest.json	action.default_popup	popup.html
extensions/sa_alpha_picks/manifest.json	background.service_worker	background.js
tests/fixtures/sa_extension/packaging/manifest.firefox.json	action.default_popup	popup.html
tests/fixtures/sa_extension/packaging/manifest.firefox.json	background.scripts	background.js
tests/fixtures/sa_extension/packaging/manifest.firefox.json	background.scripts	compat_firefox.js
tests/fixtures/sa_extension/packaging/manifest.firefox.json	content_scripts.js	content.js
```

The five current launch-edge floor rows are:

```text
apps/arkscope-desktop/dev.js	112	npm:apps/arkscope-desktop:start
apps/arkscope-desktop/dev.js	82	npm:apps/arkscope-web:dev
apps/arkscope-desktop/main.js	108	python-module:src.api
src/service/data_scheduler.py	1212	python-module:src.news_normalized.ibkr_cli
src/service/data_scheduler.py	1269	python-module:src.prices_runtime
```

These are floors, not a claim that no additional literal subprocess target
exists. Task 1 performs an uncapped structured scan. A missing floor row is a
stop; a newly grounded row is classified rather than rejected for changing a
prediction.

### 0.8 Legacy CLI/Discord capability floor

The comparison matrix contains at least these 28 IDs, sorted stream SHA-256
`d799dbab042593f149a851fdd3ddc17783dcd90559f8eecbc4429d05b0b2d2f7`:

```text
alpha_picks_commands
attachment_input
code_backend_control
compaction_control
context_window_control
conversation_history
discord_alert_delivery
discord_effort_control
discord_follow_up
discord_model_control
discord_query
effort_control
extended_thinking
manual_skill
memory_commands
model_selection
monitor_commands
overflow_inspection
provider_selection
reasoning_control
report_commands
research_query
scratchpad_inspection
session_clear
skill_auto_apply
status_and_token_usage
subagent_control
tool_turn_limit
```

This is a required floor, not a closed final capability set. Task 2 adds any
additional symbol-grounded CLI/Discord capability and records why it is not an
alias of an existing row.

### 0.9 Grounded source and import-trap identities

| Path | Lines | SHA-256 |
|---|---:|---|
| `src/agents/__main__.py` | 17 | `d8e01a84c6db85b2ed8294b3ba3ad2b0f14f039600f2ff0e4e75ee24a5d91fd2` |
| `src/agents/cli.py` | 2,781 | `fc04e1ac849026a69b0632531d39c744a6a8f7b9f77213b36f07dacb63a53301` |
| `src/monitor/discord_bot.py` | 1,048 | `00cfa50ac8e694f98ec366e8ef135eb9bc856d45519be907185da7939ffced9d` |
| `src/agents/shared/skills.py` | 652 | `95b75a33e89a41113cc97e59a06c9f3049e9f89e767bbf63f4b2bdf87ffce68b` |
| `src/monitor/notifiers.py` | 154 | `98f2db0b918cdb4236794086ecfb3bdeed03cdb6ac8d9b2704d781839aa7c158` |
| `README.md` | 102 | `b0783fba6ac648cbbb03019eaaa1870e3dbfa374fb501c652cce992fec77da25` |
| `requirements.txt` | 40 | `0c8316f34079632ce2cadca7a5663ff6bdda29d1631e9b10330bb0051714912e` |
| `config/.env.template` | 192 | `9a1ad601d5d5b3264d0fdc8fef795a1f9fb02c973c24c82a0f76cac3dc56d9fe` |

Static census at the base finds no importer of `src.agents.__main__`, no
non-test caller of `MindfulDiscordBot.start_bot()`, and no non-test constructor
or launcher for `MindfulDiscordBot`. `src/monitor/notifiers.py` contains a
typed/duck-typed bot attachment seam but does not start the bot. These are
dated grounding facts; Task 2 must reproduce the uncapped caller census.

### 0.10 Git-crypt boundary

The exact encrypted set and source-base blob IDs are:

```text
d07ce126266e3df2f03fed97a94364d6679e8a31  data_sources/DATA_SOURCES_EVALUATION.md
a1bc22836444f3582b41b74ca7ea3934a8fdd441  data_sources/IBKR_INVESTOR_DATA_VALUE.md
1622c6010cb9b7323507ca5d4617d594e3a9c0b7  data_sources/PAID_SUBSCRIPTION_EVALUATION.md
```

The final document-command grounding contains two normalized command rows from
`PAID_SUBSCRIPTION_EVALUATION.md`; that fact may be retained, but no surrounding
plaintext may leave the unlocked tree.

### 0.11 Protected aggregate

From the exact source base, take `git ls-tree -r --full-tree`, exclude only the
existing mutable `docs/design/PROJECT_PRIORITY_MAP.md`, and serialize every
remaining base path as:

```text
mode<TAB>blob<TAB>path
```

The result is 942 rows, SHA-256
`76665c8a39b514e1896613edeb416c0fded416944c9cfc44c89f9fa1750a0eea`.
The design did not yet exist at the source base, so it does not appear in this
aggregate. Every listed row is byte/mode protected throughout execution.
Newly created census docs are separately constrained by Section 0.2.

### 0.12 Review gates

Default execution stops after every task. A later user batch ruling may reduce
review frequency but cannot relax packets, commits, stop conditions, or the
Task 3 combined implementation review. Task 4 merge requires that review to be
GREEN and remains no-push.

---

## 1. Execution Tasks

### Task 0: Re-ground the exact docs-only baseline

**Files:**
- Create: `docs/superpowers/evidence/2026-08-16-legacy-agent-cli-entrypoint-census.md`
- Modify: this plan
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Produces:** immutable baseline packet, exact backend/frontend node streams,
all Section 0.7 source streams, protected aggregate, import-trap witness, and a
Task 0 docs commit.

- [x] **Step 1: Create a fresh implementation worktree**

Branch `codex/legacy-agent-cli-entrypoint-census` from the exact independently
reviewed plan tip. Prove that source base `241ccdba..PLAN_TIP` changes only the
reviewed design, this plan, and priority-map status. Stop on master drift,
merge-base mismatch, dirty tracked state, or any product-byte difference.

- [x] **Step 2: Establish the isolated packet and toolchain**

Use packet root `/tmp/legacy-agent-cli-census-task0-241ccdba`. Set scratch
`HOME`, XDG directories, token/store paths, profile DB paths, and lock paths
under that root. Ensure the worktree has no `config/.env`, no link to main
`data/`, and an empty real `data/` directory only if import discovery requires
it.

Copy the two pinned collection helpers from the retained accepted PG no-tail
packet and verify Section 0.6 hashes. Link only worktree root `node_modules` to
the main root. Confirm app-local `apps/arkscope-web/node_modules` is absent.
Run the explicit root Vitest binary's `--version`; reject any download/cache
mutation or version other than 4.1.8.

- [x] **Step 3: Install a census import blocker**

Create a packet-local pytest plugin whose `MetaPathFinder.find_spec()` raises a
distinct census error when `fullname == "src.agents.__main__"`. It records only
an attempted module name, never environment values. Add a synthetic negative
self-test proving the blocker fires before module execution.

Do not preload a harmless replacement into `sys.modules`; that would hide an
accidental import. Do not import `src.agents.cli` as a probe. Static AST is the
only admitted product inspection.

- [x] **Step 4: Recollect backend and frontend without test bodies**

Run pytest collect-only with both the pinned reporter and import blocker. The
report must state zero test bodies executed and produce exactly
4,278 / `ecafdab7...`.

From `apps/arkscope-web`, run explicit
`../../node_modules/.bin/vitest list --json=<packet path>` and the pinned
normalizer. Require exactly 1,177 nodes, 101 files, and `c570a551...`.
Rebuild the 209/92 owner projections from the backend stream.

- [x] **Step 5: Reconstruct every literal grounding stream**

From exact source-base Git blobs, independently reconstruct Section 0.7's
16/19 main-guard, 10 parser, 4 shell, 3 package, 2 executable-mode, 2 module,
15 shebang, 12 npm-script, 13 manifest-target, 8 README-command, 52/15
document-command, and five required launch-edge streams. Compare every stream
byte-for-byte, not only by count.

Main-guard extraction uses Python AST and accepts either operand ordering,
single/double quotes, and arbitrary indentation. Parser extraction recognizes
`argparse.ArgumentParser`, Click group/command decorators, Typer construction,
and `fire.Fire` through resolved import aliases. Regex-only main/parser evidence
is rejected.

- [x] **Step 6: Re-prove the dangerous-module and git-crypt facts**

Using AST/call-site search only, confirm line 17's unconditional `main()` and
line 72's `_load_env()` call; confirm zero importers of
`src.agents.__main__`. Rebuild the encrypted path set/blob IDs from the unlocked
main tree. Extract only normalized command tokens from encrypted plaintext and
discard source lines immediately.

- [x] **Step 7: Rebuild protected rows and write evidence**

Recreate the 942-row protected aggregate and compare byte-for-byte. Record
accepted/rejected artifacts, exact commands, tool versions, no-import witness,
runtime isolation, and explicit zero live/runtime/provider/credential activity.
Add a newest-first map entry recording the review protocol.

Commit only the evidence, plan status, and map:

```bash
git commit -m "docs: ground legacy-agent entrypoint census"
```

Stop for Task 0 review unless a recorded batch ruling applies.

---

### Task 1: Extract the complete raw candidate universe

**Files:**
- Modify: census evidence
- Modify: this plan status
- Modify: priority map

**Produces:** packet-local canonical candidate observations, extractor tools,
coverage joins, negative self-tests, and a Task 1 docs status commit. It does
not yet create recommendations or edit product bytes.

- [x] **Step 1: Write the structured Python scanner from the plan**

In a detached read-only worktree at exact source base, parse tracked Python
blobs with `ast.parse`. Emit module wrappers, every direct main guard, parser
construction, and literal subprocess/module target. Resolve aliases
structurally; never import a module. Normalize `sys.executable -m NAME` to
`python-module:NAME`, literal executable commands to `external:NAME`, and
dynamic targets to a candidate whose `detail` names the unresolved AST shape.
An unresolved reachable dynamic launch is a stop in Task 2, not silently
excluded.

- [x] **Step 2: Parse mode, shebang, shell, packages, and manifests**

Read executable mode from `git ls-tree`, first-line shebangs from exact Git
blobs, shell paths from the tracked path set, package scripts with `json`, and
desktop/browser/test-fixture manifests with structured JSON access. Follow
manifest targets into tracked HTML/JS imports as consumer edges. Parse only
executable launch targets; CSS/icons/static resources are outside the candidate
universe and are neither emitted nor used as absence evidence.

Parse install scripts structurally enough to identify the generated native
manifest's host ID and stable launcher/host target. Do not execute shell,
generate a manifest, inspect the user's installed browser manifests, or access
`~/.config`/`~/.mozilla`.

- [x] **Step 3: Extract JavaScript and subprocess launch targets**

Use a bounded lexical/AST-like scanner over tracked JS/MJS/TS/TSX for
`spawn`, `execFile`, and package-script delegations. Require the five launch
edge floor rows. Record external provider CLIs and inline-code runners as
caller-owned external rows rather than pretending they are tracked targets.

Search Python and JavaScript call sites without a result cap. A wrapper such as
`_run_subprocess(argv)` does not close the target; trace literal argv builders
to the wrapper call. Dynamic-only target construction requires a concrete
consumer trace or a stop.

- [x] **Step 4: Extract current-document command observations**

Scan tracked Markdown outside `docs/superpowers/{plans,evidence,specs}` from
the exact source base. Use the pinned command-token grammar for Python module,
Python script, npm, bash, and executable-shell invocations. Reproduce the
52-row/15-path plan-author stream. Current README/operator commands become
consumer evidence. Historical decision-log/spec examples remain raw candidates
until Task 2 gives the exact closed exclusion; stale commands in current
authority become rows, not exclusions.

- [x] **Step 5: Discover test consumers without promoting helpers**

Join AST imports, patch targets, subprocess invocations, and documentation
assertions in tests to candidates already discovered by Steps 1-4. Tests do
not independently promote arbitrary helpers into entrypoints. Every test ID
must join exactly to the pinned backend/frontend collection streams.

- [x] **Step 6: Run extractor negative self-tests**

Packet-local synthetic fixtures must prove at least:

1. single/double-quoted and reversed main guards are found;
2. an unconditional module-level call is distinguished from a main guard;
3. parser aliasing is found without import;
4. overlapping main/parser/shebang/mode observations remain distinct raw IDs;
5. npm aliases and workspace delegations retain separate script identities;
6. Chrome service worker and Firefox script arrays both parse;
7. test fixture manifests remain identifiable as test fixtures;
8. Python `sys.executable -m` and JS `spawn` literal targets parse;
9. a dynamic launch target is emitted, not discarded;
10. a current stale documented command is not called historical merely because
    its target is absent;
11. encrypted extraction retains only command token/path/line; and
12. attempting to import `src.agents.__main__` is rejected before execution.

Each mutation of a required extractor branch must make the corresponding
self-test fail. Self-tests use synthetic packet files only.

- [x] **Step 7: Close raw-source coverage and commit status**

Run two independent scanner processes and require byte-identical candidate
JSONL. Emit per-family counts/hashes, overlap groups, unresolved-dynamic rows,
and source path coverage. Every Section 0.7 literal row must be present.

Manifest the packet, update evidence/map, and commit only docs status:

```bash
git commit -m "docs: census legacy-agent entrypoint candidates"
```

Stop for Task 1 review unless a recorded batch ruling applies.

---

### Task 2: Classify entrypoints and compare CLI/Discord capabilities

**Files:**
- Create all `docs/design/legacy_agent_cli_census/*` authority files
- Create `docs/design/LEGACY_AGENT_CLI_ENTRYPOINT_CENSUS.md`
- Modify census evidence, plan status, design status, and priority map

**Produces:** complete canonical ledger, deterministic projections, human
census, user decision packet, validator/negative tests, and Task 2 docs commit.

- [x] **Step 1: Trace every consumer and reachability edge**

For every candidate, perform uncapped AST/text/manifest/package/document/test
caller census. Record concrete call chains and choose the strongest design
reachability state only after all edges are present. No app caller does not
imply unreferenced until external contracts, docs, subprocesses, and tests have
been checked.

Reproduce the zero-caller facts for `src.agents.__main__` and
`MindfulDiscordBot.start_bot()`. Treat notifier bot attachment as a consumer
edge only to the symbols it actually calls; do not infer a bot launcher.

- [x] **Step 2: Build exact test ownership**

Map direct imports, launch-contract tests, capability tests, and documentation
tests to exact node IDs. File-level test ownership is forbidden. The 209-node
projection is only the search ceiling; `tests.tsv` contains exact direct nodes.

- [x] **Step 3: Build the legacy CLI capability matrix**

Parse all function/class definitions, slash-command dispatch branches, parser
flags, shared-owner calls, and local writes in `src/agents/cli.py`. Populate
every Section 0.8 floor ID and any additional distinct capability. For each
row record CLI symbol, shared owner, exact current app/API/UI owner, equivalence,
tests, side effects, Track B sensitivity, and bounded loss if the wrapper alone
were removed.

Do not infer all imported symbols must remain or all local helpers may retire.
Compatibility re-exports, presentation, import-time env loading, query runners,
stores, and shared domain functions are distinct ownership questions.

- [x] **Step 4: Build the Discord capability and liveness matrix**

Trace Discord query/follow-up/model/effort/skill/notification/admin symbols,
shared agent owners, notifier seams, config/dependency declarations, and exact
tests. Record the lack or presence of a real launcher independently from code
executability. Tests and the `discord.py` dependency do not establish a live
product.

The skill auto-apply rows for CLI and Discord must both carry
`decision_gate=track_b_skill_policy`. Wrapper disposition cannot be inferred
until the user rules.

- [x] **Step 5: Classify all non-agent entrypoints**

Classify current app runtime, operator, integration host/install, dev/build,
diagnostic, and stale documented surfaces. Operator commands do not become
retirement candidates merely because the desktop does not invoke them.
Generated native-host contracts and browser manifests remain external
contracts with their exact owner chain.

- [x] **Step 6: Write canonical rows and candidate closure**

Create `entrypoints.jsonl`. Persist every admitted raw candidate exactly once as
candidate evidence on its canonical row; put only true exclusions in the
tracked exclusions TSV. Generate the four normalized detail authorities in the
same deterministic pass, enforce both directions of every ledger foreign-key,
and derive `recommendations.tsv` losslessly from the canonical ledger.
Create `MANIFEST.sha256` over every authority file in path-byte order, excluding
the manifest itself.

- [x] **Step 7: Implement validator and negative self-tests**

The packet-local validator rejects at least:

1. missing/extra JSON keys;
2. unsorted/duplicate rows or arrays;
3. unknown closed-vocabulary values;
4. malformed entrypoint identity;
5. zero/multiple candidate closure;
6. exclusion without allowed reason/evidence;
7. unresolved current invocation;
8. reachable row without a consumer chain;
9. test ID absent from base streams;
10. app equivalence without exact app owner;
11. operator retirement inferred solely from no desktop caller;
12. Discord liveness inferred solely from tests/dependency;
13. CLI/Discord decision gate set to `none`;
14. missing capability-floor ID;
15. alias capability row without distinct owner/meaning;
16. hidden side effect on a non-default branch;
17. `src.agents` missing `credential_read` or `long_running_process`;
18. historical command exclusion applied to a current stale authority;
19. admitted candidate evidence absent from tracked canonical authority;
20. recommendation bytes not reproducible from canonical authority, normalized
    detail bytes not reproducible from exact source/candidate inputs, or a
    ledger/detail foreign-key mismatch; and
21. manifest self-inclusion or missing payload.

- [x] **Step 8: Write the human census and decision packet**

The human document summarizes exact counts and presents:

- definitely current surfaces;
- stale surfaces independent of Track B;
- app-equivalent capabilities;
- capabilities lost by CLI/Discord wrapper retirement;
- shared code that remains regardless of wrapper decision;
- smallest coherent convergence/retirement options; and
- explicit unresolved facts.

It states that census completion is final even if the user defers disposition.
It must not open or imply an implementation plan.

- [x] **Step 9: Validate, manifest, and commit**

Run validator plus all negative self-tests, regenerate the entire authority set
twice,
verify protected rows, leak scan artifacts, and commit only authorized docs:

```bash
git commit -m "docs: complete legacy-agent entrypoint census"
```

Stop for Task 2 review unless a recorded batch ruling applies.

---

### Task 3: Independent reconstruction and census admission

**Files:**
- Modify census evidence, implementation-plan status, design-spec status,
  human-census status, and priority map only

**Produces:** independent admission packet and combined implementation-review
surface. Canonical authority bytes cannot change during this task.

- [x] **Step 1: Rebuild with independent tools**

Create fresh detached worktrees at exact source base and Task 2 tip. Write a
second scanner, closure validator, and projection generator directly from this
plan; do not copy/import Task 1-2 executor tools. Recollect backend/frontend,
rebuild all raw families, consumer edges, test joins, and projection bytes.
Executor tools may run only as a secondary control.

- [x] **Step 2: Compare all admitted artifacts byte-for-byte**

Require equality for candidate observations, per-family streams, overlap
groups, entrypoints authority, all projections, exclusions, capability floor
and additions, test joins, current invocations, human-summary count tables, and
`MANIFEST.sha256`. Count-only equality is insufficient.

- [x] **Step 3: Re-prove safety and product immutability**

Rebuild the 942-row protected aggregate; verify every source-base blob/mode.
Confirm no `src.agents.__main__` import attempt, no CLI/Discord/process launch,
no test body, no provider/network/production-store/secret action, and no main
runtime link. Verify git-crypt blob equality and bounded plaintext extraction.

- [x] **Step 4: Leak-audit packet and tracked artifacts**

Scan for home paths, credential values, email addresses, tokens/JWTs, private
env lines, arbitrary encrypted plaintext, URLs containing credentials, and
production database paths. Repository-relative paths, public command names,
package versions, and reviewed fixture values are allowed.

- [x] **Step 5: Commit status and stop for combined review**

Mark Tasks 0-3 complete and `IMPLEMENTATION REVIEW NEXT` without changing any
canonical inventory file. Manifest the admission packet and commit status docs:

```bash
git commit -m "docs: admit legacy-agent entrypoint census"
```

Fable independently rebuilds and judges classification quality, especially
operator protection, Discord liveness, CLI symbol ownership, app equivalence,
side effects, and recommendation gates. Task 4 remains blocked until GREEN and
explicit user merge authorization.

---

### Task 4: Fast-forward merge and exact-master closeout

**Files:**
- Modify census evidence, implementation-plan status, design-spec status,
  human-census status, and priority map only

**Produces:** exact-master docs authority and the user decision gate. It does
not start a retirement plan automatically.

- [x] **Step 1: Prove linear ancestry and clean boundaries**

Verify source base is ancestor of reviewed tip, zero merge commits, clean main
and implementation trees, and every changed path is one authorized docs path.
Master drift is a stop and requires re-grounding.

- [x] **Step 2: Fast-forward local master without push**

Use `git merge --ff-only <reviewed-tip>`. No rebase, force, or push.

- [x] **Step 3: Rebuild from fresh exact master**

Repeat Task 3 with new tools/packet name from exact master. Require every
candidate, canonical authority, projection, protected aggregate, and safety
witness byte-identical to the reviewed tip.

- [x] **Step 4: Commit docs-only closeout and stop**

Record merged commit, exact-master packet manifest, review ruling, no push, and
the decision state. Commit only status/evidence docs:

```bash
git commit -m "docs: close legacy-agent entrypoint census"
```

Stop for focused closeout review. After GREEN, branch/worktree cleanup is
allowed. A retirement/convergence plan opens only after a separate user ruling;
deferral is a valid closed outcome. Runtime-owner/CSS remains the next separate
architecture line unless the user first authorizes CLI/Discord work or a P0
incident preempts.

---

## 2. Hard Stop Conditions

Stop immediately and write a bounded docs-only amendment if any occurs:

1. exact source base, design hash, merge base, or product bytes differ;
2. a tracked path outside the authorized docs set changes;
3. backend/frontend collection count or hash differs;
4. a test body executes during collect-only discovery;
5. Vitest is resolved by `npx`, app-local fallback, install, or a version other
   than 4.1.8;
6. `src.agents.__main__` is imported, executed, run with `--help`, or passed to
   `runpy`;
7. `src.agents.cli` is imported by a census probe rather than encountered only
   through admitted static/test-collection behavior;
8. interactive CLI, Discord, desktop, sidecar, scheduler, native host, browser,
   collector, audit, provider CLI, or package script is launched;
9. a network/provider call, production-store open, browser registration, or
   credential-value read occurs;
10. encrypted blob set/identity differs or ciphertext is used as absence
    evidence;
11. arbitrary encrypted plaintext or a private env RHS enters an artifact;
12. any Section 0.7 literal grounding row is missing;
13. an extractor family is capped, path-order dependent, locale dependent, or
    implemented by importing product code;
14. a raw candidate has zero or multiple closure outcomes;
15. a parser/main/shebang/mode overlap creates duplicate logical entrypoints;
16. an unresolved reachable dynamic launch target is silently excluded;
17. a current invocation lacks a canonical row or concrete consumer edge;
18. a stale current command is mislabeled historical merely because its target
    is absent;
19. reachability is inferred from file age, name, or directory alone;
20. a definition is called unreferenced without uncapped callers across code,
    manifests, package scripts, docs, and tests;
21. test/dependency presence is used to call Discord live;
22. one physical file is treated as one capability without symbol analysis;
23. app equivalence lacks an exact current app/API/UI owner;
24. a side effect is omitted because a default branch avoids it;
25. the `src.agents` row lacks `credential_read` or
    `long_running_process`;
26. a capability-floor row is absent or merged without owner-level evidence;
27. CLI/Discord receives `decision_gate=none`;
28. an operator/integration command becomes a retirement candidate solely
    because desktop does not invoke it;
29. a recommendation is represented as user authorization;
30. recommendations cannot regenerate byte-for-byte from canonical authority,
    any normalized detail authority cannot regenerate byte-for-byte from exact
    source/candidate inputs, or a ledger/detail foreign key does not close;
31. protected aggregate, packet manifest, or leak audit fails;
32. canonical authority is edited during Task 3 status closeout;
33. execution proceeds into product fixes, Track B, retirement, merge, push,
    live action, `.env` cleanup, private dump handling, or runtime-owner/CSS
    work without its later gate.

## 3. Review Handoff

Independent plan review must reconstruct and judge at least:

1. exact design/base/tool identities and docs-only boundary;
2. literal 16/10/4/3/2 streams plus module/shebang/npm/manifest/doc/launch
   streams;
3. dangerous `src.agents.__main__` import and `cli._load_env` side effects;
4. canonical row schema, closed vocabularies, and candidate closure;
5. all static extractors and their negative self-tests;
6. git-crypt plaintext minimization and protected aggregate;
7. full backend/frontend and exact test-node joins;
8. symbol-level CLI/Discord capability floor and addition rule;
9. Discord liveness, operator protection, and app-equivalence evidence;
10. recommendation versus user-decision separation;
11. independent Task 3 reconstruction and no-live admission; and
12. Task 4 ff-only/no-push/user-ruling closeout.

Implementation remains blocked until that review is GREEN.
