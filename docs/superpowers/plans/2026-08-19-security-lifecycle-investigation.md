# Security Lifecycle Investigation Implementation Plan

> **Status:** PLAN GREEN FOR TASKS 0-7 AT `1907af23`; TASK 8 LIVE-PREFLIGHT
> AMENDMENT GREEN AT `e958be2d`; TASK 0 SNAPSHOT-SELECTOR AMENDMENT GREEN AT
> `8a600ce0`; TASK 0 BOOTSTRAP-TOPOLOGY AMENDMENT GREEN AT `0e99314f`; TASK 0
> COMPLETE; TASK 1 IMPLEMENTATION AND INDEPENDENT REVIEW GREEN AT `e2f90f98`;
> TASK 2 COMPLETE; TASK 3 BRIDGE-OWNERSHIP AMENDMENT GREEN; 2026-08-21
> SOURCE/TIME/INTEGRITY AMENDMENT USER-AUTHORIZED; TASK 3 INDEPENDENT-REVIEW
> AMENDMENT USER-AUTHORIZED AND UNDER EXECUTOR REVIEW;
> TASK 4 CITATION/COUNT SEAM AMENDMENT AWAITS FOCUSED REVIEW; TASK 4 PRODUCT
> BYTES REMAIN UNCOMMITTED;
> TASKS 1-3 ARE
> NON-DEPLOYABLE STAGING UNTIL TASK 4 COMPLETES THE ROUTE/CONSUMER CUTOVER; LIVE
> MIGRATION, MERGE, PUSH, AND PROVIDER CALLS REMAIN UNAUTHORIZED
>
> **Date:** 2026-08-19
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-19-security-lifecycle-investigation-design.md`
> at `3ca5ed537d45b06eeadcc858ffc17877f0dd6e68`, SHA-256
> `e72ad6e7eebff2e1ecae1155d89a28a95767b5fcdce78068d8805bf909a25606`.
> That commit changes only the design authority and records the user's approved
> formal-event/market-impact, source, time, quota, and integrity boundaries.
>
> **Product grounding base:**
> `93ad444990fb856a6006ba4793b96a9c1a53625d` (docs-only design amendment
> over product tip `be263855`).

**Goal:** replace the dead-end SEC review table with a durable
observation/case/evidence/assessment/proposal workflow, add attended manual and
Tavily investigation, expose exactly two local read tools, and move the product
workflow from Settings to Universe without applying any tracking action.

---

## 0. Authority, grounding, and execution rules

### 0.1 Binding product rulings

The implementation carries these user decisions without reopening them:

1. A filing is provider evidence. Security-class wording is never relevance,
   severity, or an action decision.
2. Direct tracked-security impact, issuer-related impact, unrelated evidence,
   and insufficient evidence are distinct states. Insufficient evidence is an
   acknowledgement, not a fabricated assessment.
3. Search providers and agent harnesses are replaceable adapters. The durable
   product assets are case/evidence contracts and local HTTP/MCP/tool access.
4. Formal event truth and market-impact research are separate. Current v1 uses
   the structured provider observation as the required accepted-assessment
   anchor; web evidence corroborates or explains it. LLM drafts, hosted search,
   IBKR contract-state corroboration, and market-reaction analysis are follow-ons,
   not implicit Task 3 behavior.
5. Source absence is data integrity, not an investment conclusion. The ordinary
   queue excludes it while an explicit source-presence filter/count retains it;
   no absent-source assessment, acknowledgement, search, or proposal is allowed.
6. The first implementation is attended. Search requires an explicit click;
   action proposals are explanations only and have no executor.
7. Images, PDFs, OCR, model-assisted assessment, Notes, Alerts, and unattended
   investigation remain separately designed work.
8. Settings owns storage health and a link only. Universe owns lifecycle
   triage, investigation, evidence, assessment, acknowledgement, and proposal
   presentation.

Opus review findings are inputs, not authority. Any implementation choice that
changes the eight rulings above is a hard stop for user decision.

### 0.2 Authorization boundary

This plan commit is docs-only. It does not authorize:

- opening or changing a production SQLite database;
- reading `config/.env` values or changing `ARKSCOPE_SEC_USER_AGENT`;
- a Tavily, SEC, OpenAI, Anthropic, browser, or other provider request;
- an action executor, ticker remap, archive, hide, portfolio mutation, or SA
  mutation;
- an automatic investigation, retry, alert, or model assessment;
- dependency installation, `npx`, `npm exec`, lockfile change, merge, push, or
  history rewrite.

Tasks 0-6 run only after independent plan GREEN. Task 7 (fast-forward merge)
requires Task 6 GREEN. Task 8 (live two-database migration and optional provider
canary) is separately authorized after exact-master closeout; it is not implied
by implementation GREEN.

The sole pre-cutover production-read exception is Task 0 step 9. It becomes
available only when plan GREEN and explicit Task 0 execution authorization are
both present, and remains limited to the named `mode=ro` legacy-table capture.
It authorizes no write, provider request, profile DB access, or unrelated-table
read.

### 0.3 Pinned toolchain and isolation

```text
package-lock.json
7a97621bd0389ed039e93582402f19cb28e119cfdcbb445ff0f005b05e041b91
node_modules/.package-lock.json
0ee7ebb4fc2971d3e08e9c0928b8a347c68a93ae8d8f2410db73fe5e2dc5517f
Node v22.14.0
Vitest 4.1.8
/tmp/eir006_vitest_list_normalizer.py
955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
/tmp/eir002-green-baseline/run_native.sh
e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f
```

An implementation worktree links its `node_modules` to the repository-root
hoisted directory and invokes `../../node_modules/.bin/vitest` from
`apps/arkscope-web`. Verify `--version` is exactly `4.1.8` before collection or
execution. `npx`, `npm exec`, install, download, and app-local `.bin` fallback
are forbidden.

All test runs use scratch `HOME`, `TMPDIR`, XDG directories, market/profile DB
paths, lock directory, and provider configuration. Socket attempts are blocked
and recorded. The only canonical loopback exceptions are the existing six
OAuth callback nodes by exact node ID; this slice adds none. Tests must not read
an unlocked private configuration value or open a production database.

### 0.4 Fresh plan-author grounding

Collected at `93ad4449` on 2026-08-19:

| Projection | Count | SHA-256 |
|---|---:|---|
| backend canonical collection | 4,160 | `549c388a8c6c42c6fd8c5586cb72207182ad0524281f7e340c53f8ab0f92ecf1` |
| frontend decoded collection | 1,177 / 101 files | `c570a551b64ed95155c02f83499e78eb3409f2cba66ea9d46862dffad0ea239b` |
| T1 focused baseline | 127 | collection projection below |
| current lifecycle-only runtime | 127 passed | `tests/test_data_scheduler.py tests/test_sec_corporate_actions.py tests/test_security_lifecycle.py` |
| app routes | 173 | `5c1ab48808c5e57f748684d4856dedcfa003a7abccd196497c042e46335ee137` |
| registry names | 50 | `45de17f9a407238325540e322ed6776de3dfd59a80322a75715fe606346ef36d` |
| each research-driver allowlist | 13 | `c634f34989ab614555066cce3bb23397f91b4e5eea189ac42c14389c7d51223b` |

Collection used the pinned deterministic reporter with `seen=0`,
`nonpassing=0`, and zero socket attempts. The latest accepted canonical runtime
for these product bytes is 4,148 passed / 12 skipped / 0 failed. Task 0 must
produce a new native control; this plan does not reuse that runtime transcript.

The route stream is UTF-8 byte-sorted rows:

```text
METHOD<TAB>PATH
```

The registry and allowlist streams are UTF-8 byte-sorted names with one trailing
newline. The backend stream is the reporter's sorted pytest node IDs. The
frontend stream is the pinned normalizer's `relative_path<TAB>display_name`
rows.

### 0.5 Mechanical ledgers

All ledgers are literal, tracked inputs. No executor may reconstruct a different
scope from prose.

| Ledger | Rows | SHA-256 |
|---|---:|---|
| `...-backend-removals.nodes` | 14 | `064d38aa2be33a17477f91f78fc5332f89109e092d28066291d584f9771fdaf2` |
| `...-backend-additions.nodes` | 83 | `a99d98fee39c1a598d35b7b04cb5b7e7daabfb71019ec9a20a1712bfb113ad1c` |
| `...-frontend-removals.nodes` | 2 | `55e24459805b139ee6f2db3db3684c0eb4c3641c26e4e6fe522df0276dc75899` |
| `...-frontend-additions.nodes` | 26 | `52d3c8b268d3b2141fd6bcc26708c99c54d5932904140c9970683838d1f8cf7f` |
| `...-evolved-owners.tsv` | 55 data rows | `c9e4b4aedd7426586348d34688adc851e7499084919b9a5582d8355749077534` |
| `...-owned-paths.tsv` | 57 data rows | `ba8361a38f69247af4d6a327f2253c8a3d2007f91fa015f2009a8507683d4e77` |
| `...-focused-paths.tsv` | 25 data rows | `7be852db3dc34bf7c2fcfaf2a77bb72c758434e9e45e6e2d56281a88f238ee72` |
| `...-protected.paths` | 24 | `4d037a50c97365484e59637484b3c903dd6ac0077250f2147df5ffa672b91faa` |
| `...-route-removals.tsv` | 3 | `945f0ba83efa557dd9169743f0e5724ebfad5e22c8f061c11d98181dcc1a081f` |
| `...-route-additions.tsv` | 10 | `5ec2ef3b9f63bcbe8ceb2daf3937142a1372e6f4add4779389dc1e7786be272a` |

The abbreviated prefix is
`docs/superpowers/plans/2026-08-19-security-lifecycle-investigation`.

`owned-paths.tsv` is globally path-byte-sorted. Every `modify` row pins the
base line count and SHA-256; every `add` row must be absent at the base.
Implementation may touch no product/test/catalog path outside this ledger.
Governance status and per-task evidence packets are separately authorized.

The 24 protected paths are byte-identical to `93ad4449` through Task 7. Their
aggregate recipe is: consume the already byte-sorted path file, run standard
`sha256sum "$path"` from repository root for each row, concatenate those rows
with one trailing newline, then SHA-256 that byte stream. Expected aggregate:

```text
354a567d78bcff9b23f36c6b1c5e8b9e478c8ce51dec309735ad87ba15a01085
```

### 0.6 Staged collection identities

The exact backend addition partition is T1=31, T2=30, T3=22. All 14 removals
belong to T1. Frontend removal/addition belongs to T4.

| Stage | Algebra | Backend identity | Expected native |
|---|---|---|---|
| base | fixed | `4160 / 549c388a8c6c42c6fd8c5586cb72207182ad0524281f7e340c53f8ab0f92ecf1` | `4148P / 12S` |
| T1 | `4160 - 14 + 31` | `4177 / 91a6bde80392b9af7aec045ec784a4b2e391f11ddfa2e177720d3e78ce8b9e67` | `4165P / 12S` |
| T2 | `4177 + 30` | `4207 / b2d5e007bd34e7e9a7358bb7560776d63142efbd879a577d5c6fa30b489e3e10` | `4195P / 12S` |
| T3/final | `4207 + 22` | `4229 / e6fb7f6933eca0b3a67cd4347f7f1b421db4aeef5ce4066549267bcb0848e4f9` | `4217P / 12S` |

Frontend final algebra and identity:

```text
1177 - 2 + 26 = 1201
027ef443692d01c74175c1b9f603298ffbb38389b1399babad3399a5b894133b
103 test files
```

The final file count follows from two new test files and no removed test file,
but must still be recollected by the pinned normalizer; prose arithmetic alone
is not admission evidence.

Route algebra and identity:

```text
173 - 3 + 10 = 180
7ce3de41b1bc57cf2f60e897cc1a4a28c6fef996842e3cfeea7b30ac24e52782
```

Registry and bridge targets:

```text
registry names       50 -> 52
registry final SHA   4cbad6bdc7506a05307e10d051a8b3d904e66acb42a94ccbd7b702b370d3de44
analysis category    13 -> 15
generic bridges      51 -> 53 (registry plus delegate_to_subagent)
research allowlists  13 -> 15 in each driver
allowlist final SHA  03441fe299675fbccfa0f371b31d1406ffd8bfd86f49e88ecf5e91762adb0640
```

### 0.7 Runtime-focused identities

Collection identity and runtime admission are separate. Future-to-be-removed
tests may remain collectible but are never required to pass after their owner
contract has already changed.

| Gate | Files introduced through | Count | SHA-256 |
|---|---|---:|---|
| backend T1 | T1 | 144 | `42066ab8912f6d0b9621cfba044326238d0bc5983b6611115769a459538abdfa` |
| backend T2 | T2 | 174 | `d1ba8b1af1372010fbe9b6697dbe5ac13745204f2920257e67c2649027e8e378` |
| backend T3 | T3 | 535 | `a0c5235d67c94181168339e5b18875023a685ad126c321fb3a450c4ba6b5be03` |
| frontend base projection | T4 paths at base | 51 | `d57e048db0a44676fc3e75b59f7caaab14211d092fe0e4f8b6e93357c173ce99` |
| frontend final | T4 | 75 | `92fe008dae24af933aeb24b9201392db1293321af810ece9b34392928223e5bd` |

T1's base version of the three existing files was run independently: 127/127.
The staged 144 consists of 89 unchanged survivors, 24 body-evolved owners, and
31 additions. Twenty-three T1 evolutions must fail before implementation; the
scheduler adapter-shape owner is explicitly `must_pass` because its injected
fake already has the new DTO and the scheduler transparently preserves it.
T3's 23 body evolutions are exact count/name/route owners and all must fail
before implementation; this is not a license to rewrite unrelated assertions.

### 0.8 RED arithmetic

Test commits precede implementation commits. Tests import new owners inside the
test body so missing modules/functions produce discrete failures rather than a
collection error.

| Task | Expected RED | Why |
|---|---|---|
| T1 | `54 failed / 90 passed` | 31 additions + 23 `must_fail` evolutions; one evolved owner stays green |
| T2 | `30 failed / 144 passed` | 30 new investigation/search contracts |
| T3 | `45 failed / 490 passed` | 22 additions + 23 count/name/route owners |
| T4 | `26 failed / 49 passed` | 26 additions; two old Settings review IDs removed |

A RED run is admitted only when the failing node set is exactly the required
set. A test that errors during collection, a previously green survivor that
fails, or a required RED owner that stays green is a hard stop.

### 0.9 Commit, packet, and amendment discipline

Each product task uses two linear commits:

1. `test(...): define ...` contains removals/additions/evolved test owners and
   the exact RED packet.
2. `feat(...)` or `refactor(...)` contains product implementation and the GREEN
   packet.

No squash and no merge commit. Evidence packets stay outside tracked product
paths, contain a SHA256 manifest covering every payload, redact private paths
and secrets, and record rejected runs rather than replacing their history.

Amendments use the established two classes:

- **A:** may be recorded and execution may continue only when the exact path and
  coordinate are already in the owned ledger, every collection/focused/route/
  protected identity is unchanged, no method/branch/parameter/capability is
  added, and no other stop or external contact occurred.
- **B:** hard-stop for review when any identity, ledger, path, route, protected
  aggregate, or staged hash changes; more than one reasonable fix exists; an
  unowned surface is needed; or any unexpected provider/network/production
  contact occurs.

Calling a change "mechanical" is not sufficient for A classification; all four
A predicates must be machine-verifiable.

Task checkpoints are evidence boundaries, not release boundaries. Task 1
removes the legacy store review methods, Task 3 retires their routes, and Task 4
retires the frontend consumers. Therefore the implementation worktree after
Tasks 1-3 is intentionally non-deployable: do not run App acceptance against
those tips and do not merge, publish, or expose them as a runnable product.
Task 4 is the first runtime-admissible cutover candidate and must prove both the
old route absence and old consumer absence before any merge. Do not add a
temporary legacy method, summary shape, alias, or fallback merely to make an
intermediate tip runnable.

---

## 1. Exact product contract

### 1.1 Closed vocabularies

The schema module is the single definition site for these values. API models,
stores, projections, tools, and frontend types derive or test against them; no
second hand-maintained product vocabulary is allowed.

```text
observation kind
  merger_agreement | merger_proxy | acquisition_completed |
  listing_status_review | listing_removal_notice

case workflow projection
  unresolved | investigating | evidence_ready |
  reviewed_inconclusive | resolved

source presence
  present | source_missing

run trigger
  attended_user

run adapter
  manual | tavily

run status
  queued | running | succeeded | failed | cancelled

run failure
  adapter_unavailable | credential_missing | permission_denied |
  rate_limited | usage_limit_reached | network_error | extract_failed |
  unsupported_content

evidence kind
  web_search_result | web_page_excerpt | manual_url | manual_text |
  document_reference

document reference status
  not_inspected | extraction_needed

assessment status
  draft | accepted | superseded

assessment relevance
  undetermined | direct_tracked_security | issuer_related | unrelated

assessment confidence
  unknown | low | medium | high

assessment outcome
  undetermined | listing_ended | venue_transfer | symbol_changed |
  symbol_or_venue_changed | acquisition_cash | acquisition_stock |
  acquisition_mixed | acquisition_terms_unknown |
  issuer_security_change | no_tracked_security_change | other |
  not_applicable

assessment author
  human | legacy_review

acknowledgement reason
  evidence_insufficient

proposal action
  notify | keep_tracking | archive_manual_memberships |
  hide_from_active_universe | review_portfolio_position |
  remap_symbol | no_action

proposal status
  proposed | dismissed

proposal block reason (nullable)
  portfolio_position_open | successor_evidence_missing |
  source_context_unavailable | stale_assessment |
  action_executor_not_available

migration phase
  profile_written | market_written | complete
```

Retired product/schema/UI values are `pending_delisting`,
`inactive_confirmed`, and `renamed_or_transferred`. The last two may occur only
as bounded legacy input names in migration fixtures/tests; migration emits
`listing_ended` or `symbol_or_venue_changed` assessment outcomes. No production
compatibility alias, route, DTO, or UI label remains.

### 1.2 Market observation schema

`src/security_lifecycle_schema.py` owns deterministic SQL and independent
read-only schema verification. `SecurityLifecycleStore` consumes it; it may not
silently repair an unknown or partial schema during a read.

`security_lifecycle_observations`:

| Column | Contract |
|---|---|
| `id` | integer primary key, internal only |
| `ticker` | required normalized ticker, max 20 |
| `cik` | nullable 10 digits |
| `issuer_name` | required, max 240 |
| `filing_date` | required ISO date |
| `source` | required, max 64 |
| `source_ref` | required, max 160, rejects NUL |
| `filing_form` | required, max 30 |
| `filing_items_json` | canonical sorted unique string array, each max 20 |
| `evidence_url` | required HTTPS, max 1000 |
| `description` | bounded source evidence, max 1000 |
| `first_observed_at` | required UTC timestamp; immutable after insert |
| `last_observed_at` | required UTC timestamp; refreshed on re-observation |

Unique key: `(source, source_ref, ticker)`. Indexes: ticker/filing date and
source/source-ref/ticker. This table contains no kind, effective date, workflow,
review, relevance, outcome, or proposal column.

`security_lifecycle_observation_kinds`:

| Column | Contract |
|---|---|
| `observation_id` | FK to observation, `ON DELETE CASCADE` |
| `event_type` | closed observation-kind vocabulary |
| `effective_date` | nullable ISO date, hint owned by this kind |

Primary key: `(observation_id, event_type)`. Re-observation replaces the exact
kind set transactionally after validating the complete incoming set. It may
change kinds without changing observation ID or case ID. Unknown kinds fail
before either table changes.

The collector output is `SubmissionObservationBatch(observations=...)`.
Each observation carries a sorted tuple of kind payloads. The legacy
`CorporateRelationship`, `relationships`, `lifecycle_state`, and review-count
result fields retire; the collector result reports bounded
`observations_observed`, `kinds_observed`, ticker/error counts, and status.
Form 25 class text remains only in `description`.

### 1.3 Profile investigation schema

`src/security_lifecycle_investigation.py` owns a dedicated store over the
existing profile DB path and writer discipline. It creates only these tables
and indexes; it does not modify watchlists, memberships, notes, `ticker_meta`,
portfolio, SA, or scheduler tables.

`security_lifecycle_cases`:

```text
case_id TEXT PRIMARY KEY
source TEXT NOT NULL
source_ref TEXT NOT NULL
ticker TEXT NOT NULL
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
UNIQUE(source, source_ref, ticker)
```

It stores identity only, not filing prose, kinds, or mutable workflow state. A
read of an untouched market observation projects a case without inserting this
row.

All non-case public IDs are opaque lowercase text IDs generated by one helper
from a table-specific prefix plus UUID4 hex. Only case IDs are deterministic;
callers must not infer ordering or meaning from any other ID.

`security_lifecycle_investigation_runs`:

```text
run_id TEXT PRIMARY KEY
case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id)
trigger TEXT NOT NULL CHECK attended_user
adapter TEXT NOT NULL CHECK manual|tavily
status TEXT NOT NULL CHECK queued|running|succeeded|failed|cancelled
query_plan_json TEXT NOT NULL            -- canonical, max 6000 bytes
query_count INTEGER NOT NULL CHECK 0..3
result_count INTEGER                     -- required for succeeded, including 0
fetch_count INTEGER NOT NULL CHECK 0..5
usage_json TEXT NOT NULL                 -- canonical bounded object, max 4096
failure_code TEXT                        -- allowed only when failed
started_at TEXT
finished_at TEXT
created_at TEXT NOT NULL
```

State transitions are `queued -> running -> succeeded|failed|cancelled`.
Terminal rows are immutable. A failed retry cannot delete or supersede earlier
evidence.

`security_lifecycle_evidence`:

```text
evidence_id TEXT PRIMARY KEY
case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id)
run_id TEXT REFERENCES security_lifecycle_investigation_runs(run_id)
kind TEXT NOT NULL CHECK closed evidence vocabulary
source_url TEXT                         -- HTTPS when present, max 1000
title TEXT                              -- max 500
publisher TEXT                          -- max 240
domain TEXT                             -- max 253
source_published_at TEXT
retrieved_at TEXT
adapter TEXT NOT NULL CHECK manual|tavily
excerpt TEXT NOT NULL                   -- max 16000
content_sha256 TEXT NOT NULL
mime_type TEXT                          -- max 127
document_status TEXT                    -- only for document_reference
created_at TEXT NOT NULL
```

Rows are immutable. Manual text has no invented URL. A document reference has
`not_inspected` or `extraction_needed`; no v1 row claims extraction. Provider
answers, relevance scores, raw bodies, scripts, exception text, and secrets are
not persisted.

`source_published_at` is null, an exact ISO date, or an aware RFC 3339 instant;
normalization preserves date/minute/second/subsecond precision and never turns a
date into midnight. `retrieved_at` is the ArkScope UTC retrieval clock. Filing,
effective, publication, retrieval, and observation clocks are never substituted
for one another; market-reaction timestamps belong to the separate follow-on.

`security_lifecycle_assessments`:

```text
assessment_id TEXT PRIMARY KEY
case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id)
revision INTEGER NOT NULL CHECK revision >= 1
status TEXT NOT NULL CHECK draft|accepted|superseded
relevance TEXT NOT NULL CHECK closed relevance vocabulary
confidence TEXT NOT NULL CHECK closed confidence vocabulary
author TEXT NOT NULL CHECK human|legacy_review
conclusion TEXT NOT NULL                -- max 4000
impact_summary TEXT NOT NULL            -- max 4000
counterparty_name TEXT                  -- max 240
counterparty_ticker TEXT                -- max 20
counterparty_cik TEXT                   -- 10 digits
successor_ticker TEXT                   -- max 20
destination_venue TEXT                  -- max 120
effective_date TEXT                     -- ISO date
consideration_currency TEXT             -- ISO-like 3 uppercase characters
cash_per_security_decimal TEXT          -- canonical decimal string
exchange_ratio_decimal TEXT             -- canonical decimal string
observation_fingerprint_sha256 TEXT NOT NULL
evidence_set_sha256 TEXT NOT NULL
created_at TEXT NOT NULL
accepted_at TEXT
superseded_at TEXT
UNIQUE(case_id, revision)
```

`security_lifecycle_assessment_outcomes` has
`(assessment_id, outcome)` as its primary key and the closed outcome check.
`security_lifecycle_assessment_evidence` has an integer primary key,
`assessment_id`, `reference_kind=observation|evidence`, nullable `evidence_id`,
and the cited content hash. Its CHECK requires null evidence ID for the single
observation citation and a real same-case evidence FK for an evidence citation.

Accepting a conclusive assessment requires non-undetermined relevance, at least
one non-undetermined outcome, a current provider-observation citation,
conclusion, impact, and `author=human|legacy_review`. Profile evidence may be
additional corroboration but cannot replace the observation anchor. New UI/API writes cannot choose
`symbol_or_venue_changed`; only migration can. Acceptance supersedes the prior
accepted revision in one profile transaction and snapshots all cited hashes.

`security_lifecycle_case_acknowledgements`:

```text
acknowledgement_id TEXT PRIMARY KEY
case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id)
reason TEXT NOT NULL CHECK evidence_insufficient
note TEXT                           -- max 2000
author TEXT NOT NULL CHECK human
observation_fingerprint_sha256 TEXT NOT NULL
evidence_set_sha256 TEXT NOT NULL
acknowledged_at TEXT NOT NULL
reopened_at TEXT
```

At most one unreopened acknowledgement exists per case. Current/stale is a
projection from fingerprints and evidence digest, not a stored status. Reopen
sets `reopened_at` and does not delete history.

`security_lifecycle_action_proposals`:

```text
proposal_id TEXT PRIMARY KEY
case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id)
assessment_id TEXT NOT NULL REFERENCES security_lifecycle_assessments(assessment_id)
action_type TEXT NOT NULL CHECK closed proposal vocabulary
status TEXT NOT NULL CHECK proposed|dismissed
source_ticker TEXT NOT NULL
replacement_ticker TEXT
source_snapshot_json TEXT NOT NULL       -- canonical sorted active-source rows
reason TEXT NOT NULL                     -- max 2000
block_reason TEXT                        -- max 120, closed by generator
assessment_fingerprint_sha256 TEXT NOT NULL
proposal_dedupe_key TEXT NOT NULL UNIQUE -- canonical action/source/replacement key
created_at TEXT NOT NULL
dismissed_at TEXT
```

The dedupe key includes assessment ID, action, source ticker, and a normalized
empty-or-ticker replacement field. It avoids relying on SQLite NULL equality.
There is no applied/executed status and no executor method.

`security_lifecycle_migration_receipts`:

```text
migration_key TEXT PRIMARY KEY
market_snapshot_sha256 TEXT NOT NULL
legacy_mapping_sha256 TEXT NOT NULL
phase TEXT NOT NULL CHECK profile_written|market_written|complete
expected_legacy_rows INTEGER NOT NULL
expected_observations INTEGER NOT NULL
expected_kinds INTEGER NOT NULL
expected_legacy_assessments INTEGER NOT NULL
started_at TEXT NOT NULL
updated_at TEXT NOT NULL
completed_at TEXT
```

An incomplete receipt makes all lifecycle writes typed unavailable. Reads may
show migration status but may not fall back to old columns.

### 1.4 Identity, fingerprints, and read composition

Case ID is exactly:

```text
"slc_" + lowercase_hex(
  SHA256(UTF8("security-lifecycle-case-v1") + NUL +
         UTF8(source) + NUL + UTF8(source_ref) + NUL + UTF8(ticker))
)
```

The stored validated source values are hashed; there is no second case-ID
normalizer. NUL in any component fails before write or migration.

Observation fingerprint is SHA-256 over canonical JSON with sorted keys and
compact separators containing every source-owned field and a byte-sorted list
of `{event_type,effective_date}` payloads. It excludes internal integer ID,
`first_observed_at`, and `last_observed_at`. Evidence-set digest is SHA-256 over
byte-sorted `evidence_id<TAB>content_sha256` rows with one trailing newline.

List/detail reads:

1. read both stores independently without schema creation;
2. project every market observation as a case;
3. union profile case rows by deterministic case ID;
4. mark profile-only rows `source_missing` rather than hiding them;
5. derive workflow from current run/evidence/acknowledgement/assessment state;
6. mark accepted assessments, acknowledgements, and proposals stale when their
   fingerprint/digest no longer matches; and
7. return a typed store-unavailable error for a store-level failure, never an
   empty fallback from only one store.

Exact identity reappearance reattaches history. Identical fingerprint restores
current projection; changed fingerprint retains history but blocks proposal
generation until explicit revalidation.

The ordinary case list defaults to `source_presence=present` and returns a
separate `source_missing_count`; an explicit `source_presence=source_missing`
filter reads the data-integrity cohort. Source-missing detail/history remains
readable and manual evidence may be appended, but investigation, assessment
create/accept, acknowledgement, and proposal generation fail before permission
or persistence. No null/fabricated fingerprint or inferred absence cause exists.

### 1.5 Legacy migration contract

`tests/fixtures/security_lifecycle_legacy_37.json` is a public-field fixture for
the design-reviewed migration snapshot. It contains all 37 legacy rows and the
zero-row relationship-table fact, with literal old IDs and review values. It
contains no API key, private path, account identity, or unrelated database row.

Task 0 first freezes the fixture cohort from the Slice 1 correction boundary:
legacy rows whose immutable `first_observed_at` is strictly earlier than
`2026-08-18T07:34:00Z`. That boundary is carried by the local
`security-lifecycle-form25-20260818T073400Z` correction record; the local backup
is corroboration, not a portable fixture authority. Task 0 emits the resulting
36 exact `(source,source_ref,ticker)` keys and 37 selected old-row IDs as
byte-sorted ledgers plus a complete public-row digest. Focused Task 0 review
promotes those packet artifacts to the only input authority for the tracked T1
fixture. No executor may choose a cohort from current row count or ticker name.

Rows at or after the cutoff are current live observations, not fixture input.
They are recorded by key/count in a separate exclusion ledger with reason
`observed_after_fixture_cutoff`; they are neither deleted nor treated as drift.
An intentionally restored pre-cutoff row, a missing selected row, or a selected
cohort other than exact `37 rows / 36 identities / 37 kinds / 4 reviews` is
B-class because it changes the reviewed fixture rather than merely extending
live data.

Preflight emits deterministic, byte-sorted:

```text
legacy-row-map.tsv
old_id<TAB>case_id<TAB>observation_identity<TAB>event_type<TAB>effective_date<TAB>reviewed_state
```

Required result:

```text
37 input rows
36 exact provider observations
37 observation-kind rows
4 accepted legacy_review assessments
32 untouched projected unresolved cases
0 relationship rows
```

CCL's two rows collapse only after every core source field matches. Both kind
payloads and the acquisition effective-date hint survive. Conflicting core
fields, duplicate same-kind payloads, incompatible reviews, unknown review
value, missing required source field, NUL, count drift, or a non-empty
relationship table stops before either database changes.

The resumable coordinator uses the design's three phases:

1. profile transaction writes four case/assessment histories and a
   `profile_written` receipt bound to the market snapshot and mapping digest;
2. market transaction rebuilds observation/kind tables, removes the legacy
   relationship table, verifies counts, then updates receipt to
   `market_written` in a profile transaction;
3. cross-store IDs, fingerprints, FKs, schema, counts, and integrity checks pass
   before the receipt becomes `complete`.

Interruption after phase 1 or 2 resumes idempotently from the receipt. Restore
requires both coordinated backups to be verified and returned before either DB
is reopened. No code claims cross-database atomicity.

Unit/integration tests use only fixture-created scratch databases. Live
migration is Task 8 and requires separate user authorization, complete process
quiescence, durable non-`/tmp` backups, and pre/post manifests.

### 1.6 Attended investigation and search

`LifecycleSearchAdapter` is a typed protocol. It accepts a bounded query and
returns provider identity, attempt metadata, normalized URL-addressable results,
and optional fetched excerpts. It cannot receive a store, write evidence, create
an assessment, or generate a proposal.

The orchestrator owns:

- deterministic query families from case identity and observation kinds;
- the three-query, five-result-per-query, five-fetch maximum;
- `external_web_access` before every network run and `metered_spend` before the
  Tavily request;
- one attended run per explicit click, with no background retry;
- URL safety, result normalization, HTML/script removal, bounds, persistence,
  and typed failures; and
- preserving prior evidence when a new run fails.

The initial adapters are:

- `manual`: one HTTPS URL or bounded text, zero network;
- `tavily`: direct injected Tavily client transport. It does not call
  `ToolRegistry.execute`, `web_search`, `web_fetch`, an agent loop, or browser
  automation.

Query families are fixed and ordered:

1. official filing/exchange/issuer identity and event;
2. symbol, venue, delisting, and successor;
3. acquisition/merger consideration only when an M&A kind is present.

Tavily search uses `include_answer=false`; provider answers and scores are not
product facts. Results are stably deduplicated by canonical HTTPS URL. A fetch
follows at most five selected safe URLs. Redirect targets receive the same
scheme/host/IP checks. Literal localhost, loopback, private, link-local,
multicast, unspecified, and non-HTTPS targets fail before transport. DNS
resolution used for the request is dependency-injected and rechecked at each
redirect; a hostname resolving to a forbidden address is rejected.

A successful zero-result run stores `succeeded`, `result_count=0`, and no fake
evidence item. It can support an inconclusive acknowledgement. Provider/network
failure stores one closed failure code and safe bounded diagnostics; raw
exception strings and response bodies do not enter the database or API.

Tavily request throttling and account/plan exhaustion map to `rate_limited` and
`usage_limit_reached` respectively. Neither condition selects another paid
adapter. Hosted search remains outside this plan until its own normalized canary.

### 1.7 Assessment, acknowledgement, and proposal rules

API payload validation precedes permission or storage. Additive writes call
`require_db_write`; search additionally uses the two permissions above.

- Draft assessment may remain undetermined and cannot generate proposals.
- Accepted assessment meets every section 1.3 acceptance rule.
- Conflicting evidence is preserved. No adapter/model auto-accepts a conclusion.
- Acknowledgement requires manual evidence or a succeeded run, including zero
  results. Failed-only history is rejected.
- Adding evidence or changing the source fingerprint stales an acknowledgement.
  Reopen is a distinct command.
- Proposals are deterministic from the accepted assessment and the current
  `sources_by_ticker` snapshot. They do not mutate that snapshot.
- `issuer_related` yields `notify` and `keep_tracking`; `unrelated` yields
  `no_action`.
- Direct symbol/venue change may propose `notify` plus `remap_symbol` only when
  successor evidence exists.
- Direct listing end without successor uses source-aware proposal choices.
- An open portfolio position replaces hide/remap with
  `review_portfolio_position`.
- Unavailable active-universe context blocks proposal generation with
  `source_context_unavailable` but does not block evidence.
- Every proposal displays all source memberships it would affect. No proposal
  status means applied.

### 1.8 Exact API and local-tool surface

Retire exactly the three route rows in the removal ledger and add exactly the
ten rows in the additions ledger. No compatibility alias, integer-ID event
route, relationship route, or hidden old read remains. Stable ordering is
`filing_date DESC, case_id ASC` for cases and chronological-plus-ID ordering for
history.

The two tools are exactly:

```text
list_security_lifecycle_cases
get_security_lifecycle_case
```

Both are `category=analysis`, `requires_dal=false`, local-read-only, and perform
zero network and zero write. Their schemas expose bounded case/ticker/state
filters, including source presence, and a case ID respectively. List output is a
bounded summary; detail output bounds every history collection and excerpt while
reporting truncation counts. They return explicit `market` and `profile`
components plus composed workflow fields; they do not leak Tavily-specific raw
objects. Missing case/store is typed, not an empty invented record.

Register both in the central registry, the generic OpenAI and Anthropic bridges,
and both hard-coded research-driver allowlists. Do not add a write/apply/search
tool. Update the canonical tool catalog in the same task.

### 1.9 Universe and Settings workflow

Universe keeps its current inventory view and gains a `Lifecycle` tab through
the existing unmodified `ui/Tabs.tsx`. The exact navigation target is:

```text
{ view: "universe", tab: "lifecycle", caseId?: string }
```

Settings' lifecycle subsection shows only local storage availability, case
counts by derived workflow state, and a command that navigates to the Universe
Lifecycle tab. It contains no review button, evidence table, assessment control,
or proposal action. The existing `security_lifecycle` Settings cache key may
remain, but its loader/DTO becomes the compact case-health read; the generic
cache and registry are protected.

Lifecycle table columns prioritize ticker, filing/event evidence, source
presence, workflow state, relevance, latest investigation, and proposal state.
Filters cover workflow, relevance, kind, and proposal type. Opening a row uses
the existing unmodified `Drawer` and shows separate sections for source fact,
active-universe memberships, runs, evidence, acknowledgement, assessment, and
proposal.

Commands use existing icon buttons and familiar controls:

- `Investigate` opens controls but makes no request;
- `Search web with Tavily` is the only network command and names the provider;
- manual URL/text evidence uses an explicit add command;
- assessment controls require selected citations;
- acknowledgement and reopen are separate commands;
- proposal dismiss never looks like apply.

No visible copy says a filing is a delisting conclusion. No UI claims Notes,
Alerts, OCR, automatic action, or hosted search exists. Evidence prose is not
translated. New application copy is bilingual in the existing resource files.

At 1440x900 and 390x844, the table/drawer must not overlap or overflow. Fixed
toolbars and controls have stable dimensions. Browser admission inspects real
computed style and geometry, not screenshots alone. Opening, focus, refresh,
polling, locale change, tab change, and drawer open issue zero investigation
POSTs. Each explicit search click issues exactly one POST.

---

## 2. Task 0 - Re-ground and freeze the implementation worktree

**Files:** governance status and external evidence packet only. No owned product
or test path changes.

The 2026-08-20 step 9 amendment is B-class because it changes the sole
production-read selector. It changes no product/test byte, node/path/route/tool
ledger, staged identity, RED arithmetic, fixture target, or Tasks 1-8 product
contract. Focused review completed at `8a600ce0` before the user explicitly
authorized Task 0 on 2026-08-20. That ruling also permits continued task
execution under explicit self-review while no special issue or hard stop is
present; either condition pauses execution.

The 2026-08-20 bootstrap-topology amendment is B-class because reviewed
docs-only plan amendments necessarily moved main beyond the product grounding
base, making the former requirement that main both remain at `93ad4449` and
contain those amendments impossible. It changes no product/test byte,
node/path/route/tool ledger, staged identity, RED arithmetic, fixture target,
or Tasks 1-8 product contract. Focused review is required before Task 0 starts.
That review completed GREEN at `0e99314f`; the existing user authorization may
therefore be exercised.

1. Capture clean main HEAD after all reviewed plan amendments as
   `PLAN_AUTHORITY_TIP`, record its full hash, and create the implementation
   branch/worktree from that exact commit. Prove
   `PRODUCT_GROUNDING_BASE=93ad444990fb856a6006ba4793b96a9c1a53625d` is an
   ancestor of `PLAN_AUTHORITY_TIP`. The exact
   `PRODUCT_GROUNDING_BASE..PLAN_AUTHORITY_TIP` path set must be the 13 approved
   governance authorities only: the priority map, the design, this plan, and
   the ten section 0.5 companion ledgers. Prove product, test, runtime config,
   package, resource, script, and application bytes are identical to
   `PRODUCT_GROUNDING_BASE`. Leave main clean and exactly at
   `PLAN_AUTHORITY_TIP` throughout Task 0.
2. Link root `node_modules`; verify Node/Vitest and all pinned harness hashes.
3. Recollect backend and frontend streams in isolated collect-only mode. Assert
   exact byte equality with section 0.4, `seen=0`, and zero socket attempts.
4. Rebuild every removal/addition/evolved/focused/route set from literal ledger
   rows. Assert removals occur exactly once at base, additions are absent,
   evolved owners occur exactly once, and every node joins its base stream.
5. Verify every owned `modify` path's line count/SHA and every `add` path's
   absence. Verify all 24 protected paths and the aggregate.
6. Rebuild all staged full/focused streams using set algebra only; compare every
   count/hash in sections 0.6-0.7.
7. Collect registry names, both driver allowlists, and routes; compare the base
   streams and predicted final algebra.
8. Run the three-file 127-node T1 baseline with the socket guard; require
   127/127 and zero attempts.
9. After plan GREEN and explicit Task 0 authorization only, perform one bounded
   `mode=ro` transaction against the active market DB that reads only the two
   legacy lifecycle tables, their schema, row payloads, counts, and
   `integrity_check`. Parse every `first_observed_at` as an aware RFC 3339
   instant, normalize it to UTC, and partition rows mechanically at the section
   1.5 cutoff; never compare timestamp strings. Require every selected value to
   use the canonical `YYYY-MM-DDTHH:MM:SSZ` producer form. Do not select by
   current count, ticker, filing class, review state, or operator judgment. An
   invalid or noncanonical selected timestamp is B-class. The selected cohort
   must be exact
   `37 rows / 36 identities / 37 kinds / 4 reviewed rows`, preserve the known
   CCL two-kind group, contain only known review values and valid non-NUL core
   fields, and coexist with zero relationships. Emit its 36-key ledger,
   37-old-ID ledger, complete public-row projection/digest, and a separate
   key/count/reason ledger for every later live row. Later rows, including a
   scheduler re-observation of V or LLY, do not stop Task 0. A missing or extra
   selected row, changed grouping invariant, invalid selected value, restored
   pre-cutoff V/LLY row, nonzero relationship table, schema failure, or
   integrity failure is B-class. No profile DB or unrelated market table is
   read, and no fixture becomes authoritative before focused packet review.
10. Run a fresh canonical native control in a scratch runtime root. Require
   4,148 passed / 12 skipped / 0 failed and store the deterministic report.
11. Record only whether `ARKSCOPE_SEC_USER_AGENT` is configured with an
    operator-owned non-placeholder contact; never record its value. An invalid
    value does not block fake-adapter implementation, but it blocks live SEC
    evidence. A live Tavily canary is independently blocked until its own
    credential and explicit approval exist.
12. Record the batch/review ruling in the priority-map decision log. Default is
    per-task review; any batch authorization must come from the reviewer/user.

**Task 0 commit:** docs/evidence only. The user's 2026-08-20 ruling permits
continued execution under explicit self-review while no special issue or hard
stop is present; Task 1 may begin after the Task 0 packet passes that review.

---

## 3. Task 1 - Case kernel and recoverable two-store migration

**Owned files:** exactly the T1 and T1/T2 rows in `owned-paths.tsv` (11 paths).

### 3.1 RED commit

1. Remove the exact 14 old backend IDs.
2. Add the exact 31 T1 IDs: two collector replacements, eight observation/case
   contracts, sixteen migration contracts, and five schema contracts.
3. Evolve exactly the 24 T1 rows in `evolved-owners.tsv`. Their final names
   remain truthful; only their body changes from legacy event/state/relationship
   shape to observation/many-kind shape.
4. Update only module-level scheduler/collector fakes needed for the new result
   DTO; this does not authorize another node-body evolution.
5. Add the 37-row public-field fixture only by byte-projecting the focused-review
   GREEN Task 0 cohort. Its 36-key ledger, 37-old-ID ledger, and complete row
   digest must match the packet authorities exactly. A validator rejects
   extra/missing keys, duplicate old IDs, unknown review values, nonzero
   relationship count, NUL, and any count other than 37; Task 0's later-row
   exclusion ledger is not fixture input.
6. Collect exact staged identity
   `4177/91a6bde80392b9af7aec045ec784a4b2e391f11ddfa2e177720d3e78ce8b9e67`.
7. Run the 144-node focused stream against pre-implementation product bytes.
   Require exactly 54 failed / 90 passed. Required failures are all 31 T1
   additions plus the 23 T1 evolved rows marked `must_fail`; the one
   `must_pass` scheduler owner and every unchanged survivor stay green.

Commit: `test(lifecycle): define observation and migration contracts`.

### 3.2 Implementation commit

1. Add the exact schema authority and independent no-create verifier from
   sections 1.2-1.3.
2. Refactor the market store to one observation with a transactionally
   reconciled kind set. Remove review-state schema, relationship schema, legacy
   repair code, and review methods; no alias remains.
3. Refactor SEC parsing to `SubmissionObservationBatch` and exact observation
   kinds. Preserve Form 25 class evidence and the existing per-filing fetch
   failure isolation. Remove relationship regex inference and all result fields
   that claim relationship/review counts.
4. Add case-ID, fingerprint, profile lifecycle store, composition, schema
   availability, and write-blocking receipt primitives. Do not add search yet.
5. Add the explicit migration preflight/coordinator. It accepts injected scratch
   market/profile paths and deterministic clock/ID seams; it has no default that
   resolves production paths in tests.
6. Make migration generate the complete `legacy-row-map.tsv` and receipt data
   from input bytes. No winner rule is allowed for conflict.
7. Verify phase-1 and phase-2 interruption/resume, coordinated restore, schema
   drift rejection, and relationship hard stop with scratch DB copies.
8. Assert zero import/reference to retired product symbols outside bounded
   migration tests/fixture.
9. The SEC collector, as the only surviving product caller that writes market
   observations, must resolve the existing profile database, open it read-only
   when present, and pass that connection to the receipt guard for every market
   write. A missing receipt table means no migration has begun; an incomplete
   receipt blocks the write. An unreadable profile database must not be treated
   as permission to write.
10. Expand the existing
    `test_incomplete_receipt_blocks_all_lifecycle_writes` body to exercise the
    real collector caller in addition to both stores. This adds no test ID and
    changes no staged/focused identity. The test must fail if the collector
    omits the profile receipt guard.

### 3.3 GREEN gates

- 144/144 focused pass, zero socket attempts.
- Backend collection exact 4,177 and exact staged hash.
- Staged native 4,165 passed / 12 skipped / 0 failed.
- Fixture migration: 37 -> 36 observations + 37 kinds + 4 accepted legacy
  assessments, 32 projected unresolved cases, complete mapping.
- CCL has one case, two kinds, and the preserved acquisition date hint.
- Non-empty relationship preflight changes neither scratch DB byte.
- Every phase interruption is resumable or both-backup restorable.
- Protected aggregate remains exact; frontend stream remains byte-identical.
- No production SQLite open and no provider/network attempt.

Commit: `refactor(lifecycle): separate observations from investigation state`.

Stop for Task 1 review unless a reviewed batch ruling applies.

---

## 4. Task 2 - Attended manual and Tavily investigation

**Owned files:** exactly the T2 and T1/T2 rows (4 paths).

### 4.1 RED commit

1. Add exactly the 18 investigation and 12 search IDs in the additions ledger.
2. Do not change any existing node body or ID.
3. Collect exact staged identity
   `4207/b2d5e007bd34e7e9a7358bb7560776d63142efbd879a577d5c6fa30b489e3e10`.
4. Run the 174-node cumulative focused stream against the T1 product tip.
   Require exactly 30 failed / 144 passed, with the failures equal to the T2
   additions.

Commit: `test(lifecycle): define attended investigation contracts`.

### 4.2 Implementation commit

1. Implement immutable evidence, versioned assessments, acknowledgements,
   proposal generation, active-universe composition, and stale-fingerprint
   rules from sections 1.3-1.7.
2. Implement the manual adapter with zero network.
3. Implement the injected Tavily adapter and deterministic query planner. The
   adapter owns transport decoding only; the orchestrator owns permissions,
   budgets, safety, normalization, and persistence.
4. Call `external_web_access` then `metered_spend` before Tavily transport.
   Permission details include adapter, case ID, and bounded query count, never a
   key or query result.
5. Enforce explicit `attended_user` trigger and one run per command. There is no
   scheduler, focus, mount, retry loop, or automatic call site.
6. Normalize successful zero results without evidence invention. Preserve prior
   evidence on every failure.
7. Reject unsafe initial and redirect URLs before fetch; inject DNS/transport in
   tests so no actual resolver/socket is reached.
8. Generate proposals only from current accepted assessment plus current
   `sources_by_ticker`. No proposal method calls a profile mutator.

### 4.3 GREEN gates

- 174/174 cumulative focused pass, zero socket attempts.
- Backend collection exact 4,207 and exact staged hash.
- Staged native 4,195 passed / 12 skipped / 0 failed.
- Search fake records at most 3 queries, 5 results/query, and 5 fetches.
- Permission call order precedes transport; missing credentials produces
  `credential_missing` with no raw detail.
- Zero results are succeeded; failed retry preserves prior evidence.
- Acknowledgement, stale/reopen, assessment acceptance, and source-aware
  proposal tests pass without touching non-lifecycle profile tables.
- Protected aggregate and frontend stream remain exact.
- No production SQLite open and no provider/network attempt.

Commit: `feat(lifecycle): add attended evidence investigation`.

Stop for Task 2 review unless a reviewed batch ruling applies.

---

## 5. Task 3 - API and two local read tools

**Owned files:** exactly the 21 T3 rows.

The 2026-08-21 bridge-ownership amendment is B-class. The Task 3 RED proved
that `get_anthropic_tools()` and `create_openai_tools()` are hand-written
schema/dispatch surfaces rather than projections of the central registry, but
their two owner files were absent from the original ledger. The amendment adds
exactly `src/agents/anthropic_agent/tools.py` and
`src/agents/openai_agent/tools.py`, pinned to their product-grounding bytes.
It authorizes only the two lifecycle wrappers/schema rows and dispatch entries;
it does not authorize bridge refactoring or changes to any existing tool.
Collection, focused, route, registry, allowlist, protected, and RED identities
remain unchanged. Focused review is required before either newly owned product
file is edited.

The same pre-implementation check found two new sentinel assertions comparing
the store's existing `sqlite3.Row` values directly with tuples. Normalize only
those returned rows to tuples in the assertions, then replay the exact RED
against T2 product bytes. This changes no test ID, expected failure set, or
product contract.

The 2026-08-21 OpenAI bridge-name normalization is A-class. The new Task 3
contract originally compared the Agents SDK wrapper's literal `tool_...` name
with the provider-neutral registry name even though the retained bridge
contract requires every wrapper name to start with `tool_`. Normalize that
prefix only in the new contract and compare both hand-written bridge schemas'
property rows with the central parameter rows. The owned path, node ID, RED
failure set, collection/focused identities, and product capability surface are
unchanged.

The 2026-08-21 source/time/integrity amendment is B-class because it tightens
Task 2 schema/acceptance behavior and Task 3 API/tool behavior after their
original RED contracts were written. It is user-authorized and changes no file,
route, tool-name, node-ID, collection, focused, protected, allowlist, or path
ledger identity. It authorizes only these bounded changes within already owned
paths:

1. add `usage_limit_reached` to the closed run-failure vocabulary and keep it
   distinct from `rate_limited`, with no paid-provider fallback;
2. normalize source publication values without manufacturing time precision;
3. require a current observation citation before assessment acceptance;
4. default list reads to present observations, add an explicit source-presence
   filter plus source-missing data-integrity count, and reject absent-source
   search/assessment/acknowledgement/proposal work before permission or write;
5. make missing/partial lifecycle schemas typed unavailable without creating a
   database, validate assessment payload shape before permissions, bound both
   local read-tool outputs, and pin the resolved public address used by fetched
   HTTPS evidence rather than resolving independently after validation; and
6. correct Task 5's stale owned-path count from 53 to 55.

The amendment may evolve only existing added test bodies in
`test_security_lifecycle_schema.py`, `test_security_lifecycle_investigation.py`,
`test_security_lifecycle_search.py`, `test_security_lifecycle_routes.py`, and
`test_security_lifecycle_tools.py`; it adds/removes no node. Before product edits,
run those exact owners against the current pre-amendment implementation and retain
the complete failing-node/reason ledger. Any additional product path, route, tool,
test ID, source-presence state, acknowledgement reason, LLM writer, IBKR call,
market-impact record, or capability-manifest implementation is another B-class
stop.

The 2026-08-21 independent-review amendment is A-class under the user's
self-review ruling: every affected path and surface is already owned, no route,
tool, node ID, state vocabulary, provider, or capability is added, and the fixes
only make the approved contracts executable at their existing boundaries. It
authorizes existing Task 3 test bodies to pin these seven regressions before the
corresponding product edits:

1. atomically create the profile case row with the first persisted run, manual
   evidence item, or assessment for an otherwise projected market case;
2. require successful two-store composition before manual evidence persistence,
   while retaining manual evidence for a valid `source_missing` case;
3. compose the complete market-observation set rather than silently treating
   observations beyond a reader limit as absent;
4. reject malformed bounded text and non-HTTPS manual URLs before permission;
5. return the newest bounded history rows in explicit chronological-plus-ID
   order for every local-tool detail collection;
6. disable redirects on the fixed Tavily search endpoint and classify any 3xx as
   unsupported content; and
7. preserve real source-supplied fractional-second precision beyond six digits.

The amendment must retain the exact 4,229-node collection and 535-node focused
identity. A new node, product path, route, provider call, state, or capability is
B-class. Task 4 remains blocked until the amended Task 3 implementation receives
independent review.

The 2026-08-21 post-GREEN adapter-classification amendment is A-class. Independent
review confirmed that broad terminal `except Exception` handlers can mislabel an
adapter programming error as `network_error`. Evolve only the existing
`test_adapter_failure_is_typed_and_keeps_prior_evidence` body to require
`TypeError` and `AttributeError` at the Tavily client/adapter seams to use the
already-closed `adapter_unavailable` failure code, while transport/runtime errors
remain `network_error`. The amendment changes no node, route, tool, schema,
failure vocabulary, provider, permission, or owned path.

The 2026-08-21 Task 4 post-RED assertion-ceiling amendment is A-class. The
approved Settings handoff removes the old event/relationship tables and replaces
their six-field review summary with two storage-health facts, but four retained
`SettingsLocalStorage.test.ts` bodies also assert those superseded headings. Evolve
only `renders only current local storage panels in normal settings navigation`,
`lists_the_active_data_group_and_its_stable_subsections`, `renders English market
data and storage outcomes`, and `keeps corrected single-locale headings` to assert
the approved lifecycle-health title and two health fields. Also narrow the added
`records successful zero-result runs without claiming no impact` assertion to the
rendered run-history row; filter option labels are not claims about that run. This
amendment changes no node, route, DTO, command, state, provider, capability, or
owned path.

### 5.1 RED commit

1. Add exactly 14 route and 8 tool IDs.
2. Evolve exactly the 23 T3 rows in `evolved-owners.tsv`: registry 50->52,
   analysis 13->15, bridges 51->53, exact names, app status 50->52, and routes
   173->180. No other test body changes.
3. Collect exact final backend identity
   `4229/e6fb7f6933eca0b3a67cd4347f7f1b421db4aeef5ce4066549267bcb0848e4f9`.
4. Run the 535-node cumulative focused stream against the T2 product tip.
   Require exactly 45 failed / 490 passed. Failure set is the 22 additions plus
   the 23 evolved owners.

Commit: `test(lifecycle): define API and local-tool contracts`.

### 5.2 Implementation commit

1. Add one lifecycle router with exactly the ten route rows. Mount it once.
2. Remove the three old market-data routes and all imports/DTOs used only by
   those routes. `market_data.py` retains unrelated market APIs byte-for-byte
   outside the bounded removal hunk.
3. Add dependency factories for the lifecycle market reader, profile store,
   composition service, and injected search adapter. Test overrides use scratch
   paths and fakes. Missing paths and missing/partial schemas are typed
   unavailable; no dependency or read service creates them.
4. Call `db_write` for every additive write before persistence. Search route
   then follows Task 2's external permissions. Reads call no permission.
5. Add exactly two `analysis`, no-DAL local tools. Register both in the central
   registry; add their bounded wrappers and dispatch to both hand-written
   generic bridges; and add them to the two 15-name research allowlists.
6. Keep tool output provider-neutral and bounded. Tool handlers call composition
   directly; they do not call HTTP routes, Tavily, or profile mutations.
7. Update the canonical tool catalog with the two rows and explicit local-read
   boundary.
8. Prove no route/tool named apply, execute, hide, archive, or remap was added.

### 5.3 GREEN gates

- 535/535 cumulative focused pass, zero socket attempts.
- Backend collection 4,229 and final exact hash.
- Native 4,217 passed / 12 skipped / 0 failed.
- Route stream 180 and exact final route hash; all three old rows absent.
- Registry 52/exact hash, analysis 15, generic bridges 53, both allowlists
  15/exact hash.
- Tool calls issue zero network, zero write, and no database creation on missing
  paths.
- Default list reads exclude `source_missing` from the ordinary queue while
  returning its data-integrity count; the explicit source-presence filter and
  detail read retain the complete bounded history.
- Source-missing search, assessment create/accept, acknowledgement, and proposal
  generation fail before permission or persistence; manual evidence and reads
  remain available.
- Accepted assessments require the current provider-observation citation;
  evidence-only drafts cannot be accepted.
- Date-only publication/effective values remain date-only, request throttling and
  usage exhaustion are distinct, and neither invokes a fallback provider.
- Every write route calls `db_write`; investigation additionally proves the two
  egress permission calls before fake transport.
- Protected aggregate and frontend stream remain exact.
- No production SQLite open or provider request.

Commit: `feat(lifecycle): expose cases through API and local tools`.

Stop for Task 3 review unless a reviewed batch ruling applies.

---

## 6. Task 4 - Universe lifecycle workflow and Settings handoff

The 2026-08-21 full-suite ownership amendment is B-class. The exact final
frontend collection was already `1,201/103/027ef443...`, and the 75-node
focused stream was green, but the first full sequential run exposed five
retained failures that the original focused owner set could not see:

1. the visible-literal scanner rejects the dynamic
   `$.lifecycle.confidence[value]` key in the already owned
   `LifecycleView.tsx`; replace it with a closed explicit mapping inside that
   owner, with no resource or node change;
2. one `SettingsWorkspace.test.tsx` node still expects the retired lifecycle
   review directory label; and
3. three `i18n/resources.test.ts` nodes still pin the pre-T4 exact Explore,
   Settings, total, and Settings lifecycle-key inventories.

The latter two test files were absent from the original ownership ledger, so
the original `20 T4 rows` and the required `1,201/1,201` gate were mutually
inconsistent. This amendment adds exactly those two base-pinned test owners and
exactly the four retained node bodies to the evolved ledger. It changes no test
ID, route, DTO, product capability, dependency, protected byte, or collection/
focused identity. The revised Settings directory expectation replaces only the
retired review surface label with the lifecycle health/handoff owner.

Before the implementation commit, apply those four test-body changes to the
pre-T4 product bytes and require exactly four failures for the four newly
listed `must_fail` owners. Then replay them against the implementation tip and
require four passes before rerunning the full sequential suite. The rejected
full-suite run is diagnostic only; its five failures are not admission
evidence.

The 2026-08-21 visible-copy closure amendment is B-class. Replaying the newly
owned resource tests exposed the already owned global visible-literal scanner:
after replacing the first dynamic confidence key, it found the dynamic outcome
key and then the hard-coded bilingual maps in `lifecyclePresentation.ts`.
Hiding those strings behind a different runtime object would satisfy neither
the scanner nor the Task 4 bilingual-resource contract. Move the complete
bounded copy surface into the existing English and Traditional Chinese Explore
resource owners:

- five workflow-state labels;
- one additional source-presence label beside the existing source-missing
  label;
- six proposal labels;
- four investigation-run status labels;
- one acknowledgement-reason label; and
- five typed/fallback error messages.

This is exactly 22 additional Explore leaves. Final resource inventory is
therefore Explore `483`, Settings `796`, lifecycle subtree `99`, and all
reviewed namespaces `1,982` leaves per locale. Presentation functions keep
their existing signatures and outputs but select only bundled resource values;
`LifecycleView` uses the same proposal/run/acknowledgement resources and does
not expose raw enum identifiers as UI copy. Compose provider-owned drawer title
parts structurally and render revalidation/run separators structurally rather
than adding source-content allowlist debt. No allowlist, scanner, test ID,
route, DTO, capability, dependency, path ledger, protected byte, or collection/
focused identity changes. The preceding four-node RED used the pre-closure
resource counts, so it is not admission evidence for the final test bodies.
First update those bodies to the final `483/796/99/1,982` resource contract and
replay them against otherwise pre-T4 product bytes, before adding the 22
product-resource leaves. Require the failure set to remain exactly those four
evolved owners. A fifth inventory failure is another ownership stop, not an
allowed consequence. Then add the 22 leaves and require all four owners to
pass; requiring the resource-count owners to remain red after those leaves
exist would contradict their contract.

The 2026-08-21 Task 4 citation/count seam amendment is B-class. Final
self-review found two cross-stage contract failures that the focused UI mocks
could not expose:

1. the Settings health panel requests `limit=1` and displays `count`, while the
   Task 3 read service currently defines `count` as the number of returned
   rows. A nonempty production store therefore displays one present-source case
   instead of the complete filtered count; and
2. the Task 4 assessment form can emit only evidence citations, while Task 3
   acceptance correctly requires a citation bound to the current provider-
   observation fingerprint. No successful UI path to an accepted assessment
   exists because case detail does not expose that fingerprint.

Keep list payloads bounded, but define `count` as the full filtered count before
the page limit. Add the current `observation_fingerprint_sha256` to present-
source case detail only; source-missing detail returns null. The UI must require
the user to select that current observation, submit its exact fingerprint as an
`observation` citation, and may add same-case evidence citations as additional
corroboration. Do not synthesize the citation server-side, compute a duplicate
frontend fingerprint algorithm, weaken acceptance, or make evidence replace the
observation anchor.

This amendment adds T4 phase ownership to exactly three existing T3 paths and
evolves exactly four already existing test nodes. It changes no path row count,
test ID, route, tool, schema table, resource leaf, dependency, provider,
permission, protected byte, collection identity, or focused identity. Before
the fix, require those four evolved owners to fail against the current Task 4
implementation bytes for the stated reasons and all other 535 backend and 75
frontend focused owners to retain their prior result. After the fix, require
all four to pass and replay both focused suites.

**Owned files:** exactly the 25 T4 rows.

### 6.1 RED commit

1. Remove exactly the two old Settings review IDs.
2. Add exactly the 26 frontend IDs.
3. Add new DTO mocks/fixtures without removing the old exports needed by the
   pre-T4 product during RED. Final cleanup of old mock exports occurs with the
   implementation commit. No retained test node body may change unless
   separately amended.
4. Recollect final frontend identity before running tests. Require 1,201 nodes,
   103 test files, and
   `027ef443692d01c74175c1b9f603298ffbb38389b1399babad3399a5b894133b`.
5. Run the 75-node final focused stream against pre-T4 product bytes. Require
   exactly 26 failed / 49 passed.

Commit: `test(lifecycle): define Universe investigation workflow`.

### 6.2 Implementation commit

1. Add the Lifecycle tab, triage table, presentation functions, and detail
   drawer under Universe. Reuse protected Tabs/Drawer/Button components.
2. Add the exact navigation target and Settings link. Deep-link case ID opens
   the Lifecycle tab and drawer; locale switch preserves target.
3. Replace old frontend DTO/functions with the ten-route case API. No old
   integer review API remains.
4. Reduce Settings lifecycle UI to health/counts/link and remove all review
   controls and relationship/event tables.
5. Implement filters, evidence/run history, manual evidence, explicit Tavily
   click, assessment citation selection, acknowledgement/reopen, and proposal
   dismissal. The default task table shows present observations; source-missing
   count/filter is a distinct data-integrity view with investigation/assessment/
   acknowledgement controls absent. There is no apply control.
6. Add bilingual copy in the existing resource owners. Provider evidence stays
   verbatim.
7. Add scoped CSS only for lifecycle-owned classes. Do not modify protected UI
   components or perform the deferred runtime-owner/CSS refactor.
8. Browser fixture intercepts local lifecycle API and records method/path/phase.
   It must support desktop and mobile, nonempty and empty states, source missing,
   legacy assessment, zero results, typed failure, and blocked proposal.

### 6.3 GREEN gates

- Frontend focused 75/75.
- Frontend full sequential 1,201/1,201, 103 files, exact stream/hash.
- Typecheck and production build pass with no dependency/lockfile change.
- Backend remains 4,229/exact hash and the 535 backend owners remain green.
- Browser matrix at 1440x900 and 390x844: zero console errors, no overlap or
  horizontal overflow, drawer remains operable, and computed geometry is
  recorded.
- Mount/focus/refresh/tab/locale/drawer phases issue zero investigation POSTs.
  One explicit Tavily command issues exactly one investigation POST per
  viewport. Manual evidence POST occurs only after its own explicit command.
- Settings contains no old review action/copy; Universe displays all separated
  concepts and no apply action.
- Source-missing cases do not inflate the ordinary investment-event queue, remain
  reachable through their data-integrity count/filter, and expose no command that
  requires an observation fingerprint.
- Protected aggregate remains exact; no provider or production DB is touched.

Commit: `feat(lifecycle): move investigation workflow into Universe`.

Stop for Task 4 review unless a reviewed batch ruling applies.

---

## 7. Task 5 - Mutation proof and final admission

Task 5 changes no product behavior. Each mutation runs from a clean T4 tip,
records preimage SHA, applies one bounded patch, proves the exact owner RED,
restores bytes, proves preimage==postimage, and reruns the owner GREEN. A failed
or overbroad mutation is retained as rejected evidence and does not count.

The 2026-08-21 M1 owner correction is B-class. Preflight proved that appending a
representative `event_type` to the case-ID hash bytes fails
`test_case_id_rejects_embedded_nul_and_hashes_literal_provider_identity`, while
the former owner
`test_observation_upsert_reconciles_many_kinds_without_changing_case_identity`
remains green because both of its `case_id_for(source, source_ref, ticker)` calls
have identical inputs. The former owner still protects observation-kind
reconciliation, but it cannot own the literal case-ID byte contract. This
correction changes only the required M1 RED owner; it changes no product/test
byte, test ID, mutation count, path/node/route/tool ledger, collection/focused
identity, protected path, or Task 5 admission target.

The 2026-08-21 M2 owner correction is B-class. Clearing only the
`effective_date` of CCL's `acquisition_completed` kind during
`_observation_from_group()` fails both
`test_migration_collapses_ccl_only_after_core_fields_match`, which owns the
preflight collapse result, and
`test_migration_preserves_every_source_field_kind_date_and_old_row_mapping`,
which owns final persistence and the complete legacy-row mapping. The original
table named only the latter even though the former independently pins the same
CCL kind/date. The complete focused replay produced exactly those two failures,
zero socket attempts, and no third failure; the rejected single-owner attempt
is retained in the Task 5 packet. This correction changes only M2's required
RED owner set; it changes no product/test byte, test ID, mutation count,
path/node/route/tool ledger, collection/focused identity, protected path, or
Task 5 admission target.

The 2026-08-21 M5/M8/M14 owner-set correction is B-class. A preflight audit of
the remaining table applied the literal mutation at the shared product seam,
replayed all 535 backend owners, and restored each preimage byte-for-byte:

- M5 hides every profile-only case at composition. It fails the core
  composition, source reattachment, HTTP detail, and local-tool detail owners;
  all four are independent public projections of the same source-missing
  history contract.
- M8 makes `succeed_investigation_run(result_count=0, ...)` return
  `fail_investigation_run(..., failure_code="extract_failed", usage=usage,
  fetch_count=fetch_count, at=at)` before writing the success row. It does not
  mutate the orchestrator or add a failure code. It fails the run-state
  vocabulary, inconclusive acknowledgement, search orchestration, and
  provider-neutral tool-detail owners; each independently requires a successful
  zero-result run.
- M14 remounts `GET /market-data/security-lifecycle`. It fails the local-runtime
  180-route census, the exact lifecycle route surface, and the dedicated legacy
  route absence owner.

The exact replays were respectively `4 failed / 531 passed`, `4 failed / 531
passed`, and `3 failed / 532 passed`, each with zero socket attempts and no
additional owner. Their preflight attempts remain rejected evidence because
the former table named incomplete owner sets. This correction changes only
those three required RED owner sets; it changes no product/test byte, test ID,
mutation count, path/node/route/tool ledger, collection/focused identity,
protected path, or Task 5 admission target.

### 7.1 Required mutations

| ID | Mutation | Required RED owner |
|---|---|---|
| M1 | put `event_type` back into case-ID bytes | `test_case_id_rejects_embedded_nul_and_hashes_literal_provider_identity` |
| M2 | clear the CCL `acquisition_completed` kind's `effective_date` during collapse, without dropping the kind | `test_migration_collapses_ccl_only_after_core_fields_match` and `test_migration_preserves_every_source_field_kind_date_and_old_row_mapping` |
| M3 | allow a non-empty relationship table | `test_migration_rejects_nonempty_relationship_table_before_either_store_changes` |
| M4 | allow writes with incomplete receipt | `test_incomplete_receipt_blocks_all_lifecycle_writes` |
| M5 | hide profile history when source row is absent | `test_read_composition_keeps_profile_history_visible_when_source_is_missing`, `test_source_reattachment_restores_identical_fingerprint_and_revalidates_changed_content`, `test_source_missing_case_detail_remains_queryable`, and `test_detail_tool_is_local_read_only_and_returns_source_missing_history` |
| M6 | include `last_observed_at` in source fingerprint | `test_source_reattachment_restores_identical_fingerprint_and_revalidates_changed_content` |
| M7 | allow failed-only acknowledgement | `test_failed_run_alone_cannot_acknowledge_a_case` |
| M8 | in `succeed_investigation_run`, route `result_count == 0` through `fail_investigation_run` with existing code `extract_failed` while preserving `usage`, `fetch_count`, and `at` | `test_run_lifecycle_is_attended_and_uses_the_closed_status_vocabulary`, `test_successful_zero_result_run_can_support_inconclusive_acknowledgement`, `test_successful_zero_result_search_is_succeeded_not_failed`, and `test_tools_return_observation_and_profile_facts_without_provider_fields` |
| M9 | remove one pre-egress permission call | `test_search_calls_external_and_metered_permissions_before_egress` |
| M10 | let adapter output create a proposal | `test_adapter_output_cannot_write_an_assessment_or_proposal` |
| M11 | allow a private/redirect URL | `test_unsafe_local_private_and_redirect_urls_are_rejected` |
| M12 | allow hide/remap with open position | `test_open_portfolio_position_blocks_hide_and_remap_proposals` |
| M13 | make one local tool call transport | `test_tool_reads_issue_zero_network_calls` |
| M14 | remount `GET /market-data/security-lifecycle` | `test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes`, `test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes`, and `test_old_integer_event_and_relationship_routes_are_absent` |
| M15 | accept a stale assessment for proposal | `test_stale_assessment_blocks_existing_and_new_proposals` |
| M16 | search on mount/focus instead of click | `opening refreshing focusing and switching tabs issue zero investigation requests` |
| M17 | restore one Settings review command | `shows lifecycle storage health and opens the Universe workflow without review actions` |
| M18 | accept an evidence-only assessment | `test_accepting_assessment_requires_conclusion_citation_and_human_author` |
| M19 | collapse usage exhaustion into rate limiting | `test_adapter_failure_is_typed_and_keeps_prior_evidence` |
| M20 | allow a source-missing assessment or acknowledgement | `test_source_missing_case_detail_remains_queryable` |
| M21 | turn a date-only publication value into midnight | `test_normalization_drops_provider_answers_scores_scripts_and_raw_bodies` |
| M22 | resolve the validated evidence hostname again during connect | `test_unsafe_local_private_and_redirect_urls_are_rejected` |

Each mutation must fail exactly its named owner within the declared focused
suite. An additional failing node is a B-class stop unless the plan is amended
to explain why the owner was not independent.

### 7.2 Final mechanical admission

1. Recollect backend 4,229/exact hash and frontend 1,201/103 files/exact hash.
2. Rebuild all removal/addition/evolution ledgers from base and tip. Prove final
   stream is exactly base minus removals plus additions; no third change.
3. Rebuild 180 routes/exact hash, 52 tools/exact hash, analysis 15, bridges 53,
   and both allowlists 15/exact hash.
4. Verify all 57 owned paths have the declared final action and every changed
   product/test/catalog path is owned. Verify all 24 protected paths and
   aggregate.
5. AST-scan retained test bodies: changes equal the 55 evolved-owner rows and no
   others. Module-level fixture edits remain inside the named test files and
   contain no new test ID.
6. Scan product and UI for retired routes, relationship API/table ownership,
   review methods, and old product-state vocabulary. Bounded migration
   fixture/tests may name legacy input values; runtime/schema/UI may not.
7. Run independent schema verifiers on fresh scratch DBs and migrated 37-row
   fixtures. Verify no verifier creates a missing DB.
8. Run the exact migration interruption/restore matrix and compare pre/post
   source-field/mapping streams byte-for-byte.
9. Run final backend focused 535/535 and frontend focused 75/75.
10. Run canonical native twice in independent scratch roots: each must be
    4,217 passed / 12 skipped / 0 failed, and reporter JSON must be byte-equal.
11. Run frontend full sequential twice: 1,201/1,201 and identical list stream.
12. Run typecheck and production build using explicit root binaries.
13. Start the app under a sanitized declared-dependency import root with scratch
    DBs and no provider credentials. Enumerate all 180 routes dynamically. One
    provider-free scheduler tick succeeds; no Tavily/SEC/provider call occurs.
14. Run the browser explicit-click matrix with a fixture server. Assert method,
    path, phase, count, computed geometry, focus recovery, and bilingual copy.
15. Run `strace -f` with exact production SQLite paths and assert zero
    `open/openat/creat` by tests, startup, tools, and browser fixture.
16. Compare pre/post SHA/size/mtime manifests for active production databases
    and tracked local assets after external writers are quiesced. Any external
    write makes the whole production-boundary run inadmissible and requires a
    fresh stable pre-manifest pair.
17. Leak scan all packets for home paths, tokens, keys, private config values,
    provider raw errors/bodies, and non-fixture personal identifiers.
18. Verify the worktree is clean and replay every packet manifest.

No real Tavily or SEC call is part of Task 5. Fake transport evidence is the
admission authority for implementation; real provider canaries are Task 8 and
require configuration plus separate approval.

**Task 5 evidence commit:** evidence/governance only; no product change.

---

## 8. Task 6 - Independent implementation review gate

The reviewer independently reconstructs, without using executor generators as
primary evidence:

1. base and final backend/frontend streams and all staged/focused identities;
2. node removals/additions, all 55 evolved owners, and path ownership;
3. market/profile schemas, closed vocabularies, and no-create verifiers;
4. 37-row mapping, 36/37 output, CCL multi-kind survival, four legacy reviews,
   relationship hard stop, interruption/resume, and coordinated restore;
5. source-missing/reattachment and current/stale fingerprint behavior;
6. explicit-click search, zero-result success, permission ordering, URL safety,
   failure preservation, and absence of provider-specific durable fields;
7. assessment/acknowledgement/proposal separation and source-aware policy;
8. exact 180-route and 52-tool surfaces, both driver allowlists, and zero local
   tool I/O;
9. Universe/Settings ownership, browser request ledger, computed geometry, and
   absence of apply controls;
10. M1-M22 RED owners and byte restoration;
11. canonical native/frontend reports, protected aggregate, production-open
    traces, leak audit, packet manifests, topology, and clean trees.

GREEN authorizes Task 7 only. Any product defect, unowned path, identity drift,
or incomplete evidence is corrected under the A/B rules before merge.

---

## 9. Task 7 - Fast-forward merge and exact-master closeout

1. Prove main still equals/descends from the grounding base and is an ancestor
   of the reviewed implementation tip. Any unrelated master drift is a hard stop
   for re-grounding; do not merge around it.
2. Fast-forward only. Do not push.
3. Create a fresh exact-master worktree with the pinned root dependency link,
   scratch environment, Node on PATH, and no production/config access.
4. Repeat all final collection, focused, canonical native, frontend, route,
   registry/allowlist, schema/migration, mutation-restoration, browser,
   protected, no-production-open, leak, and packet-manifest gates under new
   artifact names.
5. Run the git-crypt absence/preservation checks only from the unlocked main
   tree; ciphertext is never absence evidence.
6. Update design/plan/priority-map status in one docs-only closeout commit. No
   live migration or provider canary is represented as complete.
7. Stop for focused closeout review. Branch/worktree cleanup occurs only after
   GREEN. Push remains a user operation or separately explicit authorization.

---

## 10. Task 8 - Separately authorized live cutover

Task 8 is not unlocked by this plan or by Task 7 merge. It requires an explicit
user command after closeout GREEN.

The 2026-08-20 live-preflight amendment is B-class because it changes a live
migration gate. It changes no Task 0-7 identity, ledger, product scope, test
contract, or implementation authorization; focused review is required before
Task 8, not before Task 0.

### 10.1 Preconditions

- Desktop, sidecar, scheduler, SEC collector, browser extension, and every
  process holding either active DB are stopped and verified.
- `ARKSCOPE_SEC_USER_AGENT` is an operator-owned non-placeholder contact. Its
  value is not recorded.
- Fresh read-only preflight emits a complete byte-sorted legacy-row map and
  derives `expected_legacy_rows`, `expected_observations`, `expected_kinds`,
  `expected_legacy_assessments`, and unresolved count from the current
  quiesced input. It validates known review values, every exact filing-key
  group, core-field equality, same-kind payload compatibility, NUL absence,
  zero relationships, both schemas, and integrity.
- The operator reviews and explicitly approves the exact live-preflight
  manifest and digest before any database write. Approval names the derived
  counts and every old-row-to-case mapping; it is not inferred from Task 0 or
  merge GREEN.
- Timestamped backups of both active DB files live under a durable local backup
  directory outside `/tmp`; SHA-256/size/mtime manifest and per-file restore
  probes pass.
- The operator accepts the visible post-cutover change: old Settings review
  controls disappear and the same history appears under Universe Lifecycle.

The fixed 37-row fixture and its exact `36 observations / 37 kinds / 4 legacy
assessments / 32 unresolved` result remain the Tasks 1-7 implementation and
recovery authority. They are not a live-count target. A different live count is
admissible when the complete preview satisfies the same shape invariants and
the operator approves its exact manifest. Unknown vocabulary, conflicting
groups, missing source fields, NUL, a nonzero relationship table, or a mapping
that requires guessing is B-class and requires amendment. Any input change
after manifest approval invalidates that approval and requires a fresh preview
and explicit approval; never force live data to match fixture counts.

### 10.2 Migration

1. Capture two stable pre-manifests while quiesced, then rerun the read-only
   preflight and require byte equality with the explicitly approved manifest.
2. Run the coordinator once with exact active market/profile paths.
3. Verify the complete receipt against every approved live-preflight expected
   count and mapping, including observations, kinds, migrated accepted
   assessments, derived unresolved projections, zero relationship table,
   route/API composition, FKs, and both integrity checks.
4. Compare authorized-table row/schema manifests and assert every unrelated
   table/file is byte/row equivalent.
5. Restart the app only after phase is complete. If interrupted or invalid,
   keep lifecycle writes unavailable and either resume by receipt or restore
   both verified backups before reopen.
6. Perform user-visible smoke: Settings health link -> Universe Lifecycle ->
   legacy history and unresolved cases. Opening/focus makes zero provider calls.

### 10.3 Optional live Tavily canary

This is another explicit approval, not part of migration. Use one selected case,
one click, a one-query/one-result/no-fetch tightened budget, and node-aware
network ledger. Confirm permission audit order, normalized citation, bounded
usage, no raw provider answer/error, and no product write outside lifecycle
profile tables. A failed canary remains a typed run and does not alter prior
evidence.

OpenAI/Anthropic hosted search, browser automation, document ingestion, model
assessment, action execution, Alerts, Notes, and unattended operation remain
out of scope after Task 8.

---

## 11. Hard stops

Stop before commit and issue a bounded amendment when any condition holds:

1. Any baseline, staged, focused, route, registry, allowlist, file-count, path,
   or protected identity differs.
2. A removal is absent/duplicated, an addition already exists, or an evolved
   owner is missing/edited outside its bounded reason.
3. A RED failure set is not exact, a required owner stays green, or collection
   errors replace discrete RED.
4. A product/test/catalog path outside `owned-paths.tsv` must change.
5. A protected byte changes, including generic Tavily tools, permissions,
   active-universe owner, generic cache/registry, or shared UI controls.
6. More than the exact 14 backend or 2 frontend IDs must retire, more than the
   exact 83/26 IDs must be added, or a new truthful replacement is needed.
7. A retained test body outside the 55-row evolved ledger must change.
8. A legacy row cannot map literally, CCL core fields conflict, same-kind
   payloads conflict, a review value is unknown, or any identity contains NUL.
9. The relationship table is non-empty in the migration input.
10. A read verifier or tool creates a missing DB/schema, or one store silently
    substitutes for the other.
11. Case identity needs event type, date similarity, issuer-name matching, or a
    model/heuristic merge.
12. Form 25 class text changes relevance, outcome, proposal, suppression, or
    workflow severity.
13. An inconclusive acknowledgement can be created from failed-only history or
    generates an assessment/proposal.
14. A source-missing case/evidence/assessment disappears from list/detail, or
    changed source content silently reactivates stale judgment, or an absent
    source can be searched, assessed, acknowledged, or used for proposal
    generation.
15. A provider/harness-specific field enters durable case/evidence/assessment/
    proposal contracts.
16. Search requires parsing free-form model prose for citations, browser
    automation, arbitrary file access, binary upload, OCR, or an unbounded plan.
17. Any mount/focus/refresh/poll/scheduler/background path starts investigation.
18. URL safety cannot reject and recheck redirects/private resolution before
    transport, or the connect path resolves a validated hostname independently
    instead of using its admitted public address.
19. Any raw provider exception/body, secret, private path, or chain-of-thought
    reaches a product record, API response, log packet, or UI.
20. A proposal is executed or mutates watchlists, active-universe state,
    `ticker_meta`, portfolio, SA, aliases, market history, or another DB.
21. A tool performs network/write or an apply/search tool is needed.
22. Settings must retain review controls or UI completion requires inventing
    Notes, Alerts, OCR, model-assessment, or action-executor ownership.
23. A test/startup/browser run opens production storage or contacts a real
    provider. Any unexpected external contact is B-class even when harmless.
24. `npx`, install/download fallback, wrong Vitest, app-local `.bin`, or a
    no-smudge/ciphertext absence argument is used.
25. A canonical run is split/reused after environmental failure, lacks exit
    status, changes test order, or omits Node/root dependency linkage.
26. Live migration sees non-stable writers, input drift, invalid SEC contact,
    backup/restore failure, non-complete receipt, integrity error, or unrelated
    table/file change.
27. Product behavior requires a non-logical user choice not already present in
    design section 1.1. Stop and ask the user; reviewer preference is not a
    product ruling.
28. An accepted assessment can omit the current provider-observation citation,
    a date-only value is promoted to a fabricated instant, usage exhaustion is
    collapsed into throttling, or one paid adapter silently falls back to another.

---

## 12. Reproducible verification commands

Commands are shown as protocols; packet scripts pin exact paths/hashes and
record exit status. Never substitute `npx`.

```bash
# Backend collect only (pinned reporter; zero test bodies)
pytest --collect-only -q

# T1 current/final owner surface
pytest -q \
  tests/test_data_scheduler.py \
  tests/test_sec_corporate_actions.py \
  tests/test_security_lifecycle.py \
  tests/test_security_lifecycle_migration.py \
  tests/test_security_lifecycle_schema.py

# T2 cumulative owner surface
pytest -q \
  tests/test_data_scheduler.py \
  tests/test_sec_corporate_actions.py \
  tests/test_security_lifecycle.py \
  tests/test_security_lifecycle_migration.py \
  tests/test_security_lifecycle_schema.py \
  tests/test_security_lifecycle_investigation.py \
  tests/test_security_lifecycle_search.py

# T3 cumulative owner surface is reconstructed from focused-paths.tsv and the
# canonical node stream; pass the files, not byte-sorted node IDs as argv.

# Frontend collection/runtime from apps/arkscope-web
../../node_modules/.bin/vitest --version
../../node_modules/.bin/vitest list --json
../../node_modules/.bin/vitest run --maxWorkers=1 --minWorkers=1

# Canonical native
/tmp/eir002-green-baseline/run_native.sh <STAGE>
```

Focused execution preserves each source file's native collection order. A
byte-sorted node stream is an identity artifact, not an argv sequence.

Route reconstruction imports `create_app()` under socket guard with all DB/env
paths redirected to scratch, then emits sorted `METHOD<TAB>PATH` rows. Tool and
allowlist reconstruction imports only the named local modules under the same
guard and emits sorted names. Import-based probing must not execute a provider,
scheduler tick, or database resolver.

---

## 13. Plan review handoff

Independent review must rebuild, from literal rows and design text rather than
executor tools:

1. the nine non-evolution ledgers plus the 55-row evolved-owner ledger and
   every SHA/count;
2. base/staged/final full and focused identities, including T1's corrected
   24-owner evolution and RED arithmetic;
3. 173-3+10 route algebra and 50+2 registry/13+2 allowlist algebra;
4. owned path base SHA/line rows and protected aggregate recipe;
5. exact market/profile schema, closed vocabularies, case/fingerprint bytes,
   and no-read-side-write composition;
6. 37-row migration, CCL multi-kind group, four legacy assessments, 32
   unresolved projections, relationship hard stop, and resumable phases;
7. attended/manual/Tavily boundaries, permission order, URL safety, zero-result
   semantics, and provider-neutral durable data;
8. route/tool/UI ownership and absence of action execution or future-feature
   claims;
9. M1-M22's ability to kill the exact contract; and
10. separation of implementation admission, ff merge, live migration, and live
    provider authorization.

Plan GREEN unlocks Task 0 only. Default cadence is per-task review until the
reviewer/user explicitly authorizes a bounded batch.
