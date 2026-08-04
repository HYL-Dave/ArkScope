# Engineering Issue Register

> **Status**: ADOPTED - INDEPENDENT REVIEW GREEN 2026-07-25
> **Created**: 2026-07-25
> **Purpose**: Single owner for small, evidenced engineering debt that does not
> yet justify a dedicated workstream in `PROJECT_PRIORITY_MAP.md`.

## 1. Boundary

This register is not a second priority map and is not an exception list for
known failures. It owns only bounded issues that can be reproduced today and
can normally be repaired in a grouped maintenance batch.

The following do not belong here:

- product ideas or unverified reports;
- active slices and workstreams already owned by `PROJECT_PRIORITY_MAP.md`;
- permanent verification rules already owned by a spec or test;
- historical observations that have already been resolved; and
- contract violations, unresolved design decisions, database/schema changes,
  authority changes, or protected-boundary changes. Those must be promoted to
  a reviewed slice before implementation.

`PROJECT_PRIORITY_MAP.md` remains the resolver for what happens next. It links
here rather than duplicating individual small issues.

## 2. Admission And Lifecycle Rules

### 2.1 Admission requires evidence

An issue enters only when it has both:

1. a deterministic reproduction command or a stable `file:line` source fact;
2. a concrete impact statement.

An unverified observation remains outside the register until those facts
exist. A reviewer must be able to reproduce the evidence without relying on
conversation history.

### 2.2 Counts are dated observations

Every count, ID set, timestamp, or database-derived quantity records its
`observed_at` date. It is never an acceptance constant. The implementing batch
must rederive it before changing product code and stop if the issue shape has
materially changed.

### 2.3 Promotion is mechanical

Promote an entry to a separately reviewed slice when any one is true:

1. it violates an existing product or safety contract;
2. it needs a product/design decision;
3. it touches a byte-gated owner, authority source, database schema, migration,
   or another protected boundary.

Promotion removes the implementation details from this register. The entry
keeps only a link to its new canonical owner and moves to `promoted`.

### 2.4 Batching does not waive tests

Batching removes repeated spec/plan overhead. Every repaired behavior still
requires a named regression test or a documented reason why an existing named
test already owns it. A batch may not use this register to bypass review.

### 2.5 Closure requires evidence

An entry closes only with the commit that repaired or deliberately retired it,
the exact verification command, and the observed passing result. `Fixed`,
`cannot reproduce`, and `obsolete` without evidence are not closure states.

### 2.6 Open entries need a next owner

Every `open` entry has an owning batch or a concrete revalidation trigger plus
a next action. An entry with neither is invalid and must be promoted, closed,
or removed as unverified. This is the anti-graveyard rule.

## 3. Fields And Statuses

Each entry records:

| Field | Meaning |
|---|---|
| `id` | Stable `EIR-NNN` identifier. Never reuse a retired ID. |
| `status` | `open`, `promoted`, `closed`, or `invalidated`. |
| `observed_at` | Date of the currently cited observation. |
| `impact` | User, correctness, operability, or maintenance consequence. |
| `evidence` | Reproduction command and/or canonical source reference. |
| `owner` | Owning maintenance batch or promoted workstream. |
| `next_action` | Smallest concrete action that advances the entry. |
| `closure_evidence` | Empty while open; commit, command, and result at close. |

## 4. Entries

### EIR-001 - Retire unreachable `.page-head*` CSS

- `status`: `open`
- `observed_at`: `2026-07-25`
- `impact`: Dead selectors preserve a second, obsolete page-header vocabulary
  beside the shipped `.ui-page-header*` primitive and make responsive CSS
  audits noisier.
- `evidence`:
  - definitions remain in `apps/arkscope-web/src/styles.css:923-938` and
    `apps/arkscope-web/src/styles.css:1119-1125`;
  - I18N-6 independently recorded both selectors as dead in
    `docs/superpowers/specs/2026-07-25-i18n-6-release-design.md:622`;
  - reproduce the live-owner census with:

    ```bash
    rg -n 'className="page-head|className="page-head-actions' \
      apps/arkscope-web/src --glob '*.tsx' --glob '!*.test.tsx'
    ```

    Expected on the observation date: no output. `detailpage-head` and
    `.ui-page-header*` are different owners and do not count.
- `owner`: future frontend CSS hygiene batch.
- `next_action`: RED-first selector-absence coverage, remove both desktop and
  `max-width:760px` rules, then run frontend tests/build and the affected
  responsive visual gate.
- `closure_evidence`: none.

### EIR-002 - Eliminate the environment-dependent non-green backend baseline

- `status`: `closed`
- `observed_at`: `2026-07-31`
- `impact`: Before closure, the full backend suite was not green and changed
  classification across mounted-data/config environments. The native boundary
  had 27 known failures, forcing every change review to reconstruct
  failure-set equivalence and risking concealment of a new failure inside
  familiar noise.
- `evidence`:
  - `docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md:188-200`
    records matched implementer A/B at `30 failed / 7 errors` and matched
    data-bearing reviewer A/B at `31 failed / 0 errors`;
  - `docs/design/PROJECT_PRIORITY_MAP.md:527` records that the two 31-ID sets
    were byte-identical while the absolute classification was environment
    dependent;
  - rederive before work in two clean, equally configured archives with:

    ```bash
    pytest -q
    ```

    Capture normalized failed/error node IDs, environment inputs, and the run
    date. Neither `31` nor any historical family count is an allowlist.
  - a fresh native census at `3092fb4128dad9a2579f267e915519fa9cdf648c`
    collected `4739` nodes at SHA-256
    `a72bbd36dfad3d36aee2e6630e6024ec9fb4e910bebaf1363d44df8a1aa204dd`
    and reproduced exactly `27` non-passing IDs at SHA-256
    `7aafce5d2cba923480cc1fb6221bce4f5a33e0bf61c06cf94227cafefe227f15`;
  - 26 IDs trace to the 2026-02-05 real-repository-data tests in `74433f84`;
    one ID is the moving-window test introduced by `e6d99342`; and
  - the approved classification and disposition are now owned by
    `docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md`;
  - the Task 6 review packet at
    `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`
    records exact collection `4730/c34de9a0...`, native
    `4658 passed / 72 skipped / 0 failed`, an empty non-passing stream,
    protected anchors `94 passed / 18 skipped`, and exact artifact
    quarantine/restoration;
  - Task 7 fast-forwarded exact reviewed tip `99bc071e` and reproduced
    `4730/c34de9a0...` plus focused `123/123`. Main-root full admission then
    exposed one stale protected assertion only when ignored `config/.env`
    enabled the PG integration class:
    `tests/test_db_backend.py::TestFundamentalsDB::test_fundamentals_via_dal`
    reads nonexistent `FundamentalsResult.found`. The same node skips without
    that file. A real scheduler write during the run separately proved the
    production main root is not a frozen data boundary.
- `owner`: closed by the EIR-002 green-backend-baseline slice.
- `next_action`: none. Treat any later canonical non-passing node as a new
  regression or separately classified register item, not inherited debt.
- `closure_evidence`:
  - amendment `038f0c21` received independent GREEN review;
  - test-fix commit `c18f8eb0` changed only the stale `.found` assertion to
    `data_source == "none"` and the data-bearing owning node passed;
  - a fresh exact-tip worktree with no `config/.env`, empty `data/`, and only
    the pinned `node_modules` toolchain reproduced collection
    `4730/c34de9a0...`, focused `123/123`, native
    `4658 passed / 72 skipped / 0 failed`, protected
    `94 passed / 18 skipped`, and empty non-passing SHA `e3b0c442...`;
  - the full reporter recorded all `4730` nodes seen with exit status zero;
    and
  - all 638 generated repo-relative files were manifested and quarantined by
    exact path, with original/quarantined path-plus-SHA streams both
    `6ca72947...`; pre/restored status, ignored inventory, data inventory,
    symlinks, and toolchain identities matched.

### EIR-003 - Audit the 89 I18N-2-era Settings copy rewrites

- `status`: `open`
- `observed_at`: `2026-07-25`
- `impact`: These are copy-quality candidates, not known correctness defects.
  They predate the I18N-3 Traditional-Chinese byte-preservation rule, so awkward
  or unnecessary rewrites could remain without an explicit linguistic review.
- `evidence`:
  - `docs/design/PROJECT_PRIORITY_MAP.md:533` records the post-release audit and
    the dated `89` observation;
  - `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md:234-240`
    records that I18N-2 predates the general byte-preservation rule;
  - original visible literals remain recoverable from commit `ac578581`.
- `owner`: future bilingual copy-quality maintenance batch.
- `next_action`: regenerate the I18N-2 comparison from `ac578581`, produce an
  exact key-by-key ledger, classify each difference as intentional,
  terminology-required, recomposed, or review-needed, and change only the
  reviewed subset. Do not bulk-revert resources.
- `closure_evidence`: none.

### EIR-004 - Distinguish a calibration model refusal from a retryable outage

- `status`: `open`
- `observed_at`: `2026-07-25`
- `impact`: Calibration now preserves the durable typed `model_refusal`
  outcome, but the UI presents it with the same generic turn-failure title as
  transient responder errors. That can imply that repeating the unchanged
  request is useful even when the model deterministically declined it.
- `evidence`:
  - `src/api/routes/investor_profile_calibration.py` now returns HTTP `502`,
    stores `model_refusal`, and exposes only a fixed safe diagnostic; the named
    contract is
    `test_calibration_refusal_records_model_refusal_instead_of_generic_failure`;
  - `apps/arkscope-web/src/InvestorProfilePanel.tsx:153-164` maps every
    `ErrorScope` value of `turn` to
    `investor.workspace.errors.turn` without inspecting the typed code;
  - the only rendered copy is the generic string at
    `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts:921` and
    `apps/arkscope-web/src/i18n/resources/en/settings.ts:922`.
- `owner`: next Investor Profile-owned UI slice.
- `next_action`: define refusal-specific localized guidance and the retry or
  answer-edit action it permits, then add a named mounted UI contract. Do not
  expose raw model name, stop details, or Provider prose.
- `closure_evidence`: none.

### EIR-005 - Diagnose the intermittent full-suite TestClient portal stall

- `status`: `closed`
- `observed_at`: `2026-07-29`; independently revalidated `2026-07-30`;
  execution-boundary cause closed `2026-07-31`.
- `impact`: A backend run inside the Codex managed sandbox can stop before or
  during event-loop work because that boundary rejects Unix-socket self-pipe
  sends. This repeatedly blocked unrelated product verification. Native
  execution completes the same suite; no desktop startup defect was found.
- `evidence`:
  - three pre-experiment dumps and the frozen 80-trial matrix are recorded in
    `docs/superpowers/evidence/2026-07-29-lifespan-stall-causal-diagnosis.md`;
  - the independently reconstructed matrix selected
    `V6 ambient_or_machine_state_dominates`: every A/B and E/B cell produced
    `10/10` matching stalls, while E0 proved no leaker thread and E1 proved one;
  - the reviewer later observed three non-stall A0B0 replays, but supplied no
    raw coordinates, so that report is not the admission authority;
  - Section 13.2 of the evidence records a fresh exact-controller A0B0 replay
    with three further six-flag matching stalls and immutable nine-file
    manifest `ed2f1067...`; and
  - each fresh dump stops at
    `Future.result -> _spawn_task_from_thread -> start_task_soon ->
    TestClient.__enter__`, with the portal thread idle in `select()` and no
    pyrate-limiter thread;
  - the exact 942-byte wakeup probe at SHA-256 `10647c1e...` produced
    `callback_fired=false`, `_ready=1`, and zero wake bytes in `3/3` managed
    sandbox runs, while the identical bytes produced `true`, `_ready=0`, and
    zero residual bytes in `3/3` native runs;
  - direct `socket.socketpair().sendall()` returned
    `PermissionError: [Errno 1] Operation not permitted` only in the managed
    sandbox and completed natively; and
  - the unchanged price-v3 runner then completed all eight native tiers on
    their first attempts: `4722` admitted nodes, `27` known EIR-002
    non-passing nodes, SHA-256 `7aafce5d...`, and no unresolved tier.
- `owner`: closed. Backend admission that exercises cross-thread asyncio or
  AnyIO wakeups must use the native execution boundary, not the incompatible
  managed sandbox.
- `next_action`: none for EIR-005. If the sandbox policy changes, rerun the
  pinned wakeup probe before treating sandbox and native results as
  interchangeable. EIR-002 remains the independent owner of the 27 non-green
  data-fixture nodes.
- `closure_evidence`:
  - docs-only evidence and Task 0 commit
    `381de752dc40ceb61a37033ed090b25c95d1b140`;
  - exact sandbox/native probe and syscall artifacts verified `12/12` from
    `/tmp/eir005-sandbox-boundary-closeout-20260731/manifest.sha256`
    (`4806f3d6...`);
  - unchanged native v3 `run-side` returned `complete=true`, selected all
    eight first attempts, unresolved `[]`, non-passing `27/7aafce5d...`; and
  - canonical records:
    `docs/superpowers/evidence/2026-07-29-lifespan-stall-causal-diagnosis.md`
    Section 14 and
    `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
    Section 8.11.

### EIR-006 - Stop presenting a historical CSV close as a current valuation input

- `status`: `promoted`
- `observed_at`: `2026-07-31`
- `impact`: The registered `get_detailed_financials` agent tool can calculate
  market cap and related valuation ratios from the last close in a historical
  repository CSV while describing that value as current. On the observation
  date, the newest CSV bar was 2026-07-02. A cache miss can therefore turn a
  stale close into valuation output and persist the result in the 90-day
  financial cache without exposing price age or provenance.
- `evidence`:
  - `src/tools/analysis_tools.py:598-692` calls
    `FinancialMetricsCalculator.get_metrics_dict()` on a cache miss and uses
    its market-cap result;
  - `data_sources/financial_metrics_calculator.py:983-1040` calculates market
    cap from `_get_current_price_ibkr()` when the historical fundamentals
    snapshot lacks market cap;
  - `data_sources/financial_metrics_calculator.py:44-97` selects the newest
    matching file under `data/prices/15min` or `data/prices/hourly`, returns
    its final close, and labels it current without a freshness test; and
  - the 2026-07-31 read-only census found 225 15-minute CSVs for 150 tickers
    with a global latest timestamp of `2026-07-02T10:15:00-04:00`;
  - the 2026-08-01 consumer census found that `get_peer_comparison`,
    `daily_update`, and `FileBackend` also inherit or advertise the old price
    path, while current training does not consume the 300 price CSVs;
  - current training help, data/formula guides, and the canonical local-first
    workbench spec still advertise retired repository price paths or authority;
  - Settings, Ticker Detail, Dashboard through `GET /status`, and the registered
    ticker-coverage tool still project the retired `fundamentals` table even
    though the stored-only product route accepts only positive SEC annual cache
    rows, and Settings still includes a retired 2026-06-27 fundamentals sync
    row in its update summary;
  - the raw-ticker CSV view contained 2,314,293 unique 15-minute keys and 161
    apparent SQLite differences; after current aliases, the canonical view
    contained 2,298,763 unique keys, all represented in `market_data.db`, with
    176 conflicting duplicate keys and 43 SQLite differences (23 volume-only,
    20 including OHLC) left intentionally unreconciled under the
    SQLite-authority ruling; and
  - 75 hourly CSVs contain unique 2023 history, which the user explicitly
    chose to discard rather than migrate.
- `owner`:
  `docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md`.
- `next_action`: independently review the completed Task 8 exact deletion
  manifest at
  `docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/`. Its packet
  `SHA256SUMS` identity is
  `af5c090a4da72aa1204c6b8ffc13607b392e49d87acf38098a90f4bd2e24e4b6`,
  approval authority is
  `6096b988428a94d053baddd18493eb29077bc627d725a95fd53f75c4755b0dce`,
  and exact controller identity is
  `cd8980e891b4fb8713d008762d7740fd9f91009a37f501d0ee993557bd9933af`.
  Product truth cutover tip
  `ce88f72d9f9d710903533505371789d18cce953e` is merged and its fresh
  exact-master verification records `4581` collected/seen,
  `4509 passed / 72 skipped / 0 failed`, all four collection identities, and
  bounded read-only rollout observations. Physical old data remains present:
  225 15-minute CSVs, 75 hourly CSVs, their stale zero-row collection summary,
  19 retired detailed-financial cache rows, 130 legacy fundamentals rows, and
  one retired fundamentals sync row. Task 8 made no data change. Physical
  deletion remains Task 9 and is blocked until independent review clears these
  exact bytes and the user separately approves this exact authority, packet,
  and controller.
- `closure_evidence`: none.

## 5. Seed Triage: Items Not Opened

These observations were considered while creating the register and are not
duplicate entries:

| Observation | Canonical disposition |
|---|---|
| jsdom popup contrast gate must remain paired with real Chrome computed styles | Permanent release rule already recorded in `2026-07-25-sa-extension-reliability-control-clarity-design.md:101-107`. |
| Partial-status `#b45309` on `#fff3e0` measured `4.58:1` | Dated accepted boundary already recorded in the same spec at lines 98-99; changing either color must rerun its gate. |
| Identical zh/en resource values | Not admitted. A fresh recursive resource comparison reproduces `160` identical leaves. The review additionally reported `24` multi-word non-CJK leaves and proposed `2` aria, `6` routing, and `5` runtime candidates, but that exact key ledger and its classification rule are not persisted in the repo and therefore are not independently reproducible yet. Equal identifiers and professional terms may be deliberate. Persist and review the exact candidate keys before opening an issue; none of these counts is an acceptance constant. |
| SA evidence used different absolute full-suite summaries | Resolved and documented in the evidence packet and priority-map decision log; no open repair remains. |
| Coverage v2 blunt 15-minute threshold | Resolved in review-ready product tip `cb33a193`: the `_THIN_BAR_THRESHOLD` / maximum-relative owner is absent, and exact reviewed RTH slot identity now derives coverage. Independent implementation review and merge remain pending; see `docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md`. |
| Calibration Anthropic refusal seam | Existing-contract violation promoted directly to the dedicated micro-slice plan; it never enters this register. |
