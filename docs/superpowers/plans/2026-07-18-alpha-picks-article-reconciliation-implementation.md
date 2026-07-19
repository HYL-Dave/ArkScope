# Alpha Picks Article Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to execute this plan task by task. Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:test-driven-development` for every behavior change, and
> `superpowers:verification-before-completion` before review-ready claims.
> Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** LIVE COMPLETE as of 2026-07-19. Independent canonical A/B is
> exact at `4412 -> 4513` (`+101/-0`) with unchanged known non-passing families;
> copied-DB migration/state-machine and source-pinned repeated-Quick evidence
> are GREEN. The reviewed stack fast-forwarded to `master` through `bf378f1`.
> Merged-tree focused `262`, extension fixtures `24`, no-PG, popup/privacy, and
> native-host gates passed before the stopped-service production migration.
> Production `sa_capture.db` is now schema v2, integrity/FK clean, with all
> legacy logical facts preserved; the desktop app and installed Chrome
> extension were restarted from merged `master`.

**Goal:** Automatically preserve Alpha Picks list/detail ticker evidence and
associate entry and exit events with the correct bounded-date article, while
keeping ambiguous cases reviewable and demoting raw URL paste to an
event-scoped Advanced escape hatch; comment refreshes track new provider
observations without retrying inaccessible lifetime-history gaps forever.

**Architecture:** Schema v2 separates lifecycle-stable pick lineages from
captured current/closed rows, and stores accepted article relationships plus
rejection history independently from the legacy compatibility projection. A
pure deterministic matcher owns date bands, role phrases, ticker provenance,
tie handling, and URL validation; a focused SQLite persistence module owns
lineage/event queries, atomic link replacement, projection, and the derived
review queue. The browser extension captures explicit list/detail ticker facts,
commits article data before a separate bounded reconciliation pass, and renders
the review queue in its popup. The two legacy nearest/same-ticker writers retire
in the same product change, so no dual-writer window exists. A nullable provider
comment-count checkpoint records the last usable bounded scan. A frozen
pre-upsert comment-row watermark distinguishes recoverable post-enable
continuity gaps from waived historical deficits: Quick may raise or evidence-
clear pending, Full parks after two usable misses without terminalizing, and
Backfill alone may stop chasing a gap after explicit stable-bottom evidence.

**Tech Stack:** Python 3.11, SQLite/WAL, pytest, JavaScript MV3/WebExtension,
Chrome/Firefox native messaging, Node.js + jsdom fixture tests, and the existing
`sa_capture.db` local authority.

## Global Constraints

1. The design authority is
   `docs/superpowers/specs/2026-07-17-alpha-picks-article-reconciliation-design.md`.
   This plan may refine implementation shape but may not weaken its lineage,
   provenance, date-window, ambiguity, capture-independence, or single-writer
   decisions.
2. Alpha Picks relationship identity is `(symbol_key, picked_date)` lineage.
   `sa_alpha_picks.id` remains one captured membership row and must not appear
   in link, rejection, manual-action, or review-queue identity.
3. Entry anchors to `picked_date`; each distinct non-null `closed_date` is a
   separate exit event. Changed `picked_date` creates a new lineage and is never
   symbol-only migrated or merged in V1.
4. Provider ticker evidence is source-specific. List and detail scrapers write
   only `list_ticker*` and `detail_ticker*`, respectively. A user-supplied symbol
   never populates either provider field and is never interpolated into a
   synthetic article title/body fallback that the matcher could mistake for
   captured content evidence.
5. Automatic acceptance is deterministic and local: no LLM, web search,
   arbitrary uppercase-page scan, ticker-prefix identity, article-type-only
   identity, unbounded nearest date, or stable-ID tie-break.
6. The reviewed date band is exact day first, then at most three calendar days
   on either side. Missing/unparseable event dates are unmatchable. Relative
   `Today`/`Yesterday` grammar is not implemented without new captured evidence.
7. Pick refresh, article-list metadata, and article body/comment capture each
   commit before a separate reconciliation call. Matcher, projection, queue,
   or review failure must not roll back or misreport any captured provider
   fact. In particular, a successful pick refresh remains `status='ok'` and
   must not be recorded as a refresh failure merely because reconciliation
   failed afterward.
8. `_sync_canonical_to_picks()` and the mutating branch of
   `audit_unresolved_symbols()` retire in this slice. Only accepted `entry`
   links may write legacy `canonical_article_id`/`detail_report`; exit links
   never overwrite that projection.
9. Normal body-cache work is explicitly scan-scoped: every mode may request a
   missing body only for an article ID present in that refresh's list scrape;
   `quick` scans recent cards while `full`/`backfill` scan their wider list
   windows. It may not resurrect every historical body-less DB row. Candidate
   enrichment is a second, additive, deduplicated work leg bounded per refresh:
   `quick=4`, `full=12`, `backfill=20`. The cap applies only to this matcher-
   requested leg and does not reorder the normal scan-scoped work.
10. Manual acceptance binds one explicit `(symbol, role, event_anchor_date)`
    resolved to one lineage event. Only canonical
    `https://seekingalpha.com/alpha-picks/articles/<digits>[-slug]` URLs are
    accepted. A mismatch or replacement requires a visible second action.
11. The popup never displays database row IDs, lineage IDs, session material,
    or raw native-host exceptions. Native-host payloads retain existing
    credential/session sanitization.
12. AGX is not accepted as an evidence fixture or expected link. BTSG is the
    sole live ticker claim approved by the supplied screenshots; another live
    current pick may replace BTSG only if BTSG naturally rolls out before the
    live gate.
13. General SA market news, the NEWS content-availability feature, score
    archives, DB-derived universe/`tickers_core.json` retirement, Alpha Picks
    cadence, and general holdings are out of scope.
14. The user's unrelated `config/tickers_core.json` modification is protected.
    Never copy, stage, revert, rewrite, export over, or include it in a commit.
15. The pre-merge provider gate never migrates or opens the production
    `sa_capture.db` with branch v2 code. It runs the final product tip from a
    second disposable detached worktree against a SQLite online-backup copy,
    with a `0600` temporary native-host config selected through
    `ARKSCOPE_SA_NATIVE_HOST_CONFIG`. This also contains the still-live legacy
    ticker export inside the disposable checkout instead of touching either
    the implementation worktree or the user's dirty main checkout. Production
    migration occurs only after independent GREEN and merge, with every v1
    sidecar/native-host/browser process stopped first.
16. Provider lifetime comment count, one browser DOM's exposed recent comments,
    and ArkScope's cumulative deduplicated inventory are separate facts. Comment
    work is scheduled from an explicit provider-count observation versus the
    last usable-scan checkpoint, never from provider count minus inventory.
    A usable zero-overlap count-change scan with pre-existing comments freezes
    the maximum pre-upsert comment row ID. Quick may raise or clear pending;
    Full parks after two usable misses and has no terminal authority; Backfill
    alone may terminalize after five stable-bottom rounds. Unusable scans cannot
    mutate recovery state. No mode promises lifetime completeness or invents a
    fixed age cutoff.

---

## Authority, Base, and Exact Accounting

- Canonical behavior/A-B base: `848ffd4`
  (`docs: close Alpha Picks reconciliation review`). This remains the code
  baseline because subsequent plan/map commits are documentation-only.
- Implementation worktree branch point: the exact docs tip that receives
  independent plan-review GREEN. Record it as
  `PLAN_REVIEW_CLEARANCE_COMMIT` in this ledger before Task 0; it must descend
  from `848ffd4` and contain this plan plus any reviewed plan-only corrections.
  Never branch implementation directly from `848ffd4`, which would omit its
  own execution authority.
- Resolved `PLAN_REVIEW_CLEARANCE_COMMIT`:
  `59e473bbfffb579825de94371657201255d07639`. Isolated implementation branch:
  `codex/alpha-picks-article-reconciliation` at
  `/tmp/arkscope-alpha-picks-reconciliation`. The initial single-step checkout
  stopped before materialization because linked-worktree git-crypt metadata was
  absent; the retry used `--no-checkout`, copied only the repository's existing
  worktree key into Git metadata, and populated `HEAD` with `git read-tree`.
  Final implementation worktree status was clean; no main-worktree file was
  copied.
- Canonical behavior baseline collected on 2026-07-18:

  ```text
  4412 tests collected
  4301 passed / 30 failed / 74 skipped / 7 errors / 18 warnings
  ```

  The non-passing families are pre-existing. Canonical A/B must compare virgin
  archives sequentially and require identical failure/error node identities,
  not merely identical counts.
- Focused baseline:

  ```bash
  pytest --collect-only -q \
    tests/test_sa_capture_store.py \
    tests/test_sa_capture_backend.py \
    tests/test_sa_tools.py \
    tests/test_sa_extension_alpha_picks.py \
    tests/test_sa_local_readers.py \
    tests/test_sa_native_host_telemetry.py \
    tests/test_db_backend_retired_pg_sa.py
  ```

  Expected: `161 tests collected`.
- Web-app baseline is byte-protected because this slice changes the extension,
  not `apps/arkscope-web`: `60 files / 572 tests`.
- Reviewed target accounting is exact backend/extension pytest `+78/-0`:

  | New file | Nodes |
  |---|---:|
  | `tests/test_sa_article_reconciliation_schema.py` | 11 |
  | `tests/test_sa_article_reconciliation.py` | 15 |
  | `tests/test_sa_article_reconciliation_backend.py` | 20 |
  | `tests/test_sa_reconciliation_native_host.py` | 9 |
  | `tests/test_sa_extension_article_identity.py` | 8 |
  | `tests/test_sa_extension_reconciliation_flow.py` | 7 |
  | `tests/test_sa_extension_reconciliation_ui.py` | 8 |
  | **Total** | **78** |

  Therefore focused collection is `161 -> 239`; canonical collection is
  `4412 -> 4490`; if existing families remain identical, passed is
  `4301 -> 4379`. Existing nodes may be strengthened in place but may not be
  removed or renamed. Any accounting difference is a stop condition requiring
  a node-ID ledger before proceeding.
- No web-app test node is added or removed; its target remains exact
  `60 files / 572 tests` plus typecheck/build.
- Live-gate corrections after the original `+78/-0` target added exactly seven
  focused nodes without removing one: current-portfolio parser `+3`, article
  body/settle behavior `+3`, and English production-copy ratchet `+1`. At
  `18fcfb4`, focused is `246` and full collection is `4497`.
- Task 8 adds exactly `+16/-0` named nodes:

  | Existing test file | Added nodes |
  |---|---:|
  | `tests/test_sa_article_reconciliation_schema.py` | 1 |
  | `tests/test_sa_capture_backend.py` | 9 |
  | `tests/test_sa_extension_article_identity.py` | 1 |
  | `tests/test_sa_tools.py` | 2 |
  | `tests/test_sa_reconciliation_native_host.py` | 1 |
  | `tests/test_sa_extension_reconciliation_flow.py` | 2 |
  | **Task 8 total** | **16** |

  Final reviewed targets become focused `262`, canonical collection `4513`,
  and behavior-base delta `+101/-0` from `848ffd4`. Any different node delta is
  a stop condition requiring an exact node-ID ledger.

## File Map

**Create**

- `src/sa_article_reconciliation.py` - pure domain types, normalization, phrase
  authority, URL parsing, candidate evaluation, and unique-winner decision.
- `src/sa_article_reconciliation_store.py` - SQLite lineage/event reads,
  candidate/review projection, accepted-link transactions, rejection history,
  legacy preview, and idempotent reconciliation.
- `src/audit/sa_article_reconciliation.py` - explicit copied-DB/live read-only
  preview CLI; never an automatic writer.
- `extensions/sa_alpha_picks/article_identity.js` - browser-safe list/detail
  ticker extraction helpers shared by both injected scrapers.
- `extensions/sa_alpha_picks/reconciliation_ui.js` - popup review rendering,
  Advanced manual parser, and confirmation state without browser dialogs.
- `tests/fixtures/sa_alpha_picks/btsg_articles_list_card.html` - sanitized real
  BTSG list-card DOM captured before selector implementation.
- `tests/fixtures/sa_alpha_picks/btsg_article_detail_header.html` - sanitized
  real BTSG detail-header DOM captured before selector implementation.
- `tests/js/run_sa_extension_fixture.mjs` - deterministic jsdom harness that
  loads helpers/scrapers/UI without live SA access.
- Seven exact test files listed in the accounting table.

**Modify**

- `src/sa_capture_store.py` - schema v2, transactional v1 migration, lineage
  backfill, provider evidence columns, comment observation/checkpoint and
  continuity-recovery columns, and link/decision constraints.
- `src/tools/backends/sa_capture_backend.py` - resolve lineage during pick
  refresh, persist source-specific article metadata, pre-upsert comment-row
  watermarks, checkpoints, and recovery transitions, delegate reconciliation,
  and remove both legacy mutation paths.
- `src/tools/backends/db_backend.py` - retired-PG compatibility stubs for the
  new DAL method surface; no PG access.
- `src/tools/data_access.py` - capture-first pick/article/body orchestration,
  scan-scoped normal cache work, checkpoint/recovery-state comment scheduling,
  and additive reconciliation/review DTOs.
- `src/sa_native_host.py` - additive queue/event-resolve/accept/reject actions,
  post-pick-capture reconciliation, detail ticker and provider-comment-count
  propagation, and read-only compatibility audit action.
- `extensions/sa_alpha_picks/scrape_articles_list.js` - explicit list ticker
  capture with the confirmed optional-time grammar and an observed-versus-
  unknown comment-count distinction.
- `extensions/sa_alpha_picks/scrape_detail.js` - independent security-header
  ticker capture.
- `extensions/sa_alpha_picks/background.js` - ordered helper injection,
  bounded enrichment, checkpoint-aware comment refresh accounting, stable-
  bottom scan evidence, event-scoped manual flow, and review actions.
- `extensions/sa_alpha_picks/popup.html` / `popup.js` - default review queue and
  collapsed Advanced URL escape hatch.
- `tests/test_sa_capture_store.py`, `tests/test_sa_capture_backend.py`,
  `tests/test_sa_tools.py`, `tests/test_sa_local_readers.py`, and
  `tests/test_db_backend_retired_pg_sa.py` - evolve existing nodes without
  renaming/removal.
- `docs/design/PROJECT_PRIORITY_MAP.md` and this plan - status/ledger only.

**Must remain byte-identical to `848ffd4`**

- `config/tickers_core.json`
- `apps/arkscope-web/**`
- NEWS/IBKR normalized body retry and entitlement owners
- SA score/import/cutover modules
- general portfolio/holdings owners

---

### Task 0: Isolated Worktree, Baselines, and Real BTSG DOM Fixtures

**Files:**
- Create: `tests/fixtures/sa_alpha_picks/btsg_articles_list_card.html`
- Create: `tests/fixtures/sa_alpha_picks/btsg_article_detail_header.html`
- Create: `tests/js/run_sa_extension_fixture.mjs`
- Modify: this plan's implementation ledger only

**Interfaces:**
- Consumes: recorded `PLAN_REVIEW_CLEARANCE_COMMIT`, behavior base `848ffd4`,
  user's live authenticated SA browser, the two supplied BTSG screenshots, and
  existing extension pages.
- Produces: a clean isolated worktree, exact baseline evidence, and sanitized
  structural fixtures that Task 5 tests consume. No selector may be written
  before these fixtures exist.

- [x] **Step 1: Create the isolated implementation worktree**

Invoke `superpowers:using-git-worktrees`, then create:

```bash
PLAN_REVIEW_CLEARANCE_COMMIT="$(git rev-parse HEAD)"  # run only on the reviewed docs tip
git worktree add /tmp/arkscope-alpha-picks-reconciliation \
  -b codex/alpha-picks-article-reconciliation "$PLAN_REVIEW_CLEARANCE_COMMIT"
```

Write the resolved hash into the ledger and verify `git merge-base --is-ancestor
848ffd4 "$PLAN_REVIEW_CLEARANCE_COMMIT"`. If HEAD contains unrelated product
work or the plan is not review-cleared, stop instead of guessing another base.

Do not copy the main worktree's dirty `config/tickers_core.json`. If git-crypt
requires the repository's existing linked-worktree setup, copy only its key
through the established worktree mechanism and prove tracked files are clean.

- [x] **Step 2: Re-run and record exact baselines**

Run in the isolated worktree:

```bash
pytest --collect-only -q
pytest --collect-only -q tests/test_sa_capture_store.py tests/test_sa_capture_backend.py tests/test_sa_tools.py tests/test_sa_extension_alpha_picks.py tests/test_sa_local_readers.py tests/test_sa_native_host_telemetry.py tests/test_db_backend_retired_pg_sa.py
npm test --workspace apps/arkscope-web -- --run
npm run typecheck --workspace apps/arkscope-web
```

Expected: `4412`, `161`, and `60 files / 572 tests`; typecheck PASS. A changed
baseline is a stop condition: reconcile it against commits after `848ffd4`
before writing RED tests.

Recorded from the clean clearance worktree on 2026-07-18: full collection
`4412`, focused collection `161`, frontend `60 files / 572 tests`, and
TypeScript typecheck PASS. `npm install` materialized only ignored dependencies;
its audit reported the repository's existing `1 moderate / 3 high` dependency
advisories, which are outside this slice and were not auto-mutated.

- [x] **Step 3: Capture the real BTSG list-card DOM without credentials**

On the live `https://seekingalpha.com/alpha-picks/articles` page, run this exact
DevTools-console expression and inspect the returned clone before saving it:

```javascript
(() => {
  const link = [...document.querySelectorAll('a[href*="/alpha-picks/articles/"]')]
    .find((node) => /BTSG|Top Health Care Services/i.test(node.innerText || ""));
  const source = link && (link.closest("article") || link.parentElement?.parentElement);
  if (!source) throw new Error("BTSG list card not found");
  const clone = source.cloneNode(true);
  clone.querySelectorAll("script,style,img,svg,button,input,textarea").forEach((n) => n.remove());
  clone.querySelectorAll("*").forEach((n) => {
    [...n.attributes].forEach((a) => {
      const keep = a.name === "data-testid" || a.name === "data-test-id" ||
        (a.name === "href" && /\/alpha-picks\/articles\//.test(a.value));
      if (!keep) n.removeAttribute(a.name);
      if (a.name === "href") n.setAttribute("href", new URL(a.value, location.origin).pathname);
    });
  });
  return clone.outerHTML;
})()
```

Use `apply_patch` to add only the returned structural fragment as the sole body
child of a minimal HTML document. It must retain the
visible `Jul 15, 2026, 12:00 PM`, `BTSG`, `265 Comments`, article title, and
canonical article path, while containing no cookies, account identity, tokens,
tracking query parameters, unrelated recommendations, or full article body.

Captured from the user's authenticated browser on 2026-07-18. The sanitized
fragment retained the provider's real `data-test-id` structure, exact date,
ticker, comment count, title, and canonical path. A negative scan found no
cookie, authorization, token, account, session, or unrelated-content material.

- [x] **Step 4: Capture the real BTSG detail-header DOM independently**

On the BTSG article detail page run:

```javascript
(() => {
  const h1 = document.querySelector("h1");
  if (!h1) throw new Error("article h1 not found");
  let source = h1.parentElement;
  while (source && !/BrightSpring Health Services, Inc\. \(BTSG\) Stock/.test(source.innerText || "")) {
    source = source.parentElement;
  }
  if (!source) throw new Error("BTSG security header not found near h1");
  const clone = source.cloneNode(true);
  clone.querySelectorAll("script,style,img,svg,button,input,textarea").forEach((n) => n.remove());
  clone.querySelectorAll("*").forEach((n) => {
    [...n.attributes].forEach((a) => {
      const keep = a.name === "data-testid" || a.name === "data-test-id";
      if (!keep) n.removeAttribute(a.name);
    });
  });
  return clone.outerHTML;
})()
```

Save only the heading, published-date line, and the exact provider security
header. Do not include Summary/body text, account/session material, share
links, or comments. If either live fixture cannot be captured, stop Task 0;
screenshots or invented DOM are not substitutes.

Captured independently from the authenticated BTSG detail page on 2026-07-18.
The provider ancestor contained the whole article, so the fixture deliberately
retained only its real heading, date, and primary-ticker nodes; the summary,
body, author, actions, disclosures, and comments were discarded before any repo
write. The same privacy and unrelated-content negative scan passed.

- [x] **Step 5: Add the deterministic jsdom runner**

Create `tests/js/run_sa_extension_fixture.mjs` with a JSON-lines contract:

```javascript
import fs from "node:fs";
import vm from "node:vm";
import { JSDOM } from "jsdom";

const [fixturePath, ...scriptPaths] = process.argv.slice(2);
const dom = new JSDOM(fs.readFileSync(fixturePath, "utf8"), {
  url: "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
  runScripts: "outside-only",
});
Object.defineProperty(dom.window.HTMLElement.prototype, "innerText", {
  get() { return this.textContent || ""; },
});
let result;
for (const scriptPath of scriptPaths) {
  result = vm.runInContext(fs.readFileSync(scriptPath, "utf8"), dom.getInternalVMContext());
}
process.stdout.write(JSON.stringify(result));
```

The Python tests invoke this runner with the complete command shape below and
parse one JSON value. No live network is available to fixture tests.

```python
completed = subprocess.run(
    ["node", str(RUNNER), str(fixture), str(IDENTITY), str(scraper)],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
)
payload = json.loads(completed.stdout)
```

- [ ] **Step 6: Commit the evidence-only task**

```bash
git add tests/fixtures/sa_alpha_picks/btsg_articles_list_card.html \
  tests/fixtures/sa_alpha_picks/btsg_article_detail_header.html \
  tests/js/run_sa_extension_fixture.mjs \
  docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md
git commit -m "test: capture Alpha Picks ticker evidence fixtures"
```

---

### Task 1: Schema v2 and Lifecycle-Stable Lineages

**Files:**
- Modify: `src/sa_capture_store.py`
- Modify: `tests/test_sa_capture_store.py`
- Modify: `tests/test_sa_local_readers.py`
- Create: `tests/test_sa_article_reconciliation_schema.py`

**Interfaces:**
- Consumes: current v1 `sa_capture.db` and canonical `canon_date()`/`now_ts()`.
- Produces: `SCHEMA_VERSION = 2`; `sa_pick_lineages`; non-null
  `sa_alpha_picks.lineage_id`; provider ticker observation columns;
  `sa_pick_article_links`; `sa_pick_article_decisions`; transactional and
  cross-process-safe v1 migration.

- [ ] **Step 1: Write the 11 schema/migration RED nodes**

Create the following exact nodes in
`tests/test_sa_article_reconciliation_schema.py`:

- `test_fresh_v2_schema_has_lineage_link_decision_and_provider_evidence_contract`
  inspects tables, columns, checks, partial indexes, and FK delete actions.
- `test_v1_migration_backfills_one_lineage_for_current_and_closed_rows`
  requires one lineage for the RCL current/closed rows.
- `test_v1_migration_preserves_distinct_closed_events` requires both reviewed
  close dates after migration.
- `test_v1_migration_creates_distinct_lineage_for_changed_picked_date` requires
  a second lineage for the changed source picked date.
- `test_v1_migration_does_not_grandfather_legacy_canonical_values` requires zero
  accepted links while preserving the legacy field.
- `test_active_entry_and_exit_uniqueness_retains_revoked_history` inserts one
  active link, proves a second active row fails, revokes the first, and proves a
  replacement can be inserted.
- `test_link_and_decision_foreign_keys_restrict_history_deletion` proves article
  and lineage deletes fail while history references them.
- `test_future_pick_rows_require_lineage` attempts a raw null-lineage insert and
  requires `sqlite3.IntegrityError`.
- `test_v1_to_v2_migration_is_idempotent` is one node with two arms. The first
  snapshots all new authority rows, reconnects twice, and requires
  byte-identical results. The second creates a valid v2 DB, deliberately resets
  only `PRAGMA user_version` to `1`, then requires reconnect to fail closed on
  the v1-marker/v2-artifact mismatch without rebuilding or changing any row,
  table, index, trigger, or marker.
- `test_v1_to_v2_migration_is_serialized_across_two_real_processes` races two
  real Python processes and checks one coherent v2 result.
- `test_v1_to_v2_migration_failure_rolls_back_v1_byte_state` injects invalid
  migration SQL and proves version/data/schema rollback.

The core lineage assertion is concrete:

```python
rows = conn.execute(
    "SELECT p.id, p.closed_date, l.lineage_id, l.symbol_key, l.picked_date "
    "FROM sa_alpha_picks p JOIN sa_pick_lineages l USING(lineage_id) "
    "WHERE p.id IN (807, 116511, 122696) ORDER BY p.id"
).fetchall()
assert {row["lineage_id"] for row in rows} == {rows[0]["lineage_id"]}
assert {row["closed_date"] for row in rows} == {None, "2025-10-29", "2026-06-02"}
assert all(row["symbol_key"] == "RCL" for row in rows)
assert all(row["picked_date"] == "2024-03-15" for row in rows)
```

The v1 fixture creates the reviewed current schema's relevant tables and
indexes with `PRAGMA user_version=1`, then seeds:

```python
RCL_ROWS = [
    (807, "RCL", "2024-03-15", None, "current", 1, "legacy-entry"),
    (116511, "RCL", "2024-03-15", "2025-10-29", "closed", 0, None),
    (122696, "RCL", "2024-03-15", "2026-06-02", "closed", 0, None),
    (130000, "RCL", "2026-07-01", None, "current", 0, None),
]
```

Assert the first three rows share one lineage, the changed picked date gets a
second lineage, both closed dates remain present, `legacy-entry` remains only
the compatibility field, and `sa_pick_article_links` stays empty. The
two-process node launches two real `sys.executable -c` processes against the
same v1 file and requires version `2`, `integrity_check='ok'`, zero null
lineages, and no duplicate lineage. The failure node temporarily replaces one
statement in `_V1_TO_V2_STATEMENTS` with invalid SQL and requires
`user_version=1`, the original row digest unchanged, and no partially visible
v2 table.

- [ ] **Step 2: Run RED and confirm the version/schema failures**

```bash
pytest -q tests/test_sa_article_reconciliation_schema.py tests/test_sa_capture_store.py tests/test_sa_local_readers.py -x
```

Expected: new nodes fail because schema version is `1`, lineage/link tables and
columns are absent, and the v1 migration path does not exist. Existing nodes
remain green until direct inserts are updated in the implementation step.

- [ ] **Step 3: Define the exact v2 schema**

Move lineage creation before `sa_alpha_picks` in the fresh schema and add:

```sql
CREATE TABLE IF NOT EXISTS sa_pick_lineages (
    lineage_id   INTEGER PRIMARY KEY,
    symbol_key   TEXT NOT NULL CHECK(symbol_key <> '' AND symbol_key = UPPER(TRIM(symbol_key))),
    picked_date  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    UNIQUE(symbol_key, picked_date)
);

-- sa_alpha_picks gains:
lineage_id INTEGER NOT NULL REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT

-- sa_articles gains:
list_ticker                TEXT,
list_ticker_observed_at    TEXT,
detail_ticker              TEXT,
detail_ticker_observed_at  TEXT

CREATE TABLE IF NOT EXISTS sa_pick_article_links (
    link_id             INTEGER PRIMARY KEY,
    lineage_id          INTEGER NOT NULL REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
    article_id          TEXT NOT NULL REFERENCES sa_articles(article_id) ON DELETE RESTRICT,
    role                TEXT NOT NULL CHECK(role IN ('entry', 'exit', 'update')),
    event_anchor_date   TEXT,
    link_source         TEXT NOT NULL CHECK(link_source IN ('auto', 'user')),
    evidence_codes      TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(evidence_codes)),
    supersedes_link_id  INTEGER REFERENCES sa_pick_article_links(link_id) ON DELETE RESTRICT,
    linked_at           TEXT NOT NULL,
    revoked_at          TEXT,
    CHECK(role = 'update' OR event_anchor_date IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_pick_links_active_entry
    ON sa_pick_article_links(lineage_id)
    WHERE role = 'entry' AND revoked_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_pick_links_active_exit
    ON sa_pick_article_links(lineage_id, event_anchor_date)
    WHERE role = 'exit' AND revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS sa_pick_article_decisions (
    decision_id        INTEGER PRIMARY KEY,
    lineage_id         INTEGER NOT NULL REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
    article_id         TEXT NOT NULL REFERENCES sa_articles(article_id) ON DELETE RESTRICT,
    role               TEXT NOT NULL CHECK(role IN ('entry', 'exit')),
    event_anchor_date  TEXT NOT NULL,
    decision           TEXT NOT NULL CHECK(decision = 'rejected'),
    reason_code        TEXT NOT NULL,
    decided_at         TEXT NOT NULL,
    UNIQUE(lineage_id, role, event_anchor_date, article_id)
);
```

Add indexes on `(lineage_id, portfolio_status, is_stale)`, article list/detail
ticker fields, link event lookup, and decision event lookup. There is no
`ON DELETE CASCADE` in any new observation/relationship foreign key.

- [ ] **Step 4: Implement a truly transactional v1 -> v2 migration**

Set `SCHEMA_VERSION = 2`. Keep fresh-database `_SCHEMA` idempotent, but do not
use `executescript()` for v1 migration because it commits the caller's
transaction. Define `_V1_TO_V2_STATEMENTS: tuple[str, ...]` and execute each
statement under one `BEGIN IMMEDIATE` after a version re-check:

```python
def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version == SCHEMA_VERSION:
            conn.commit()
            return
        if version != 1:
            raise RuntimeError(f"unsupported sa_capture schema version: {version}")
        if conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sa_pick_lineages'"
        ).fetchone() is not None:
            raise RuntimeError(
                "sa_capture schema marker mismatch: v1 marker with v2 artifacts"
            )
        for statement in _V1_TO_V2_STATEMENTS:
            conn.execute(statement)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now_ts()),
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

The ordered statements must:

1. create `sa_pick_lineages`;
2. insert one lineage per `UPPER(TRIM(symbol)), picked_date`;
3. rebuild `sa_alpha_picks` with `lineage_id NOT NULL` after dropping/recreating
   its named indexes;
4. add the four source-specific columns to `sa_articles`;
5. create link/decision tables and indexes; and
6. assert zero null lineage rows before commit.

The marker/artifact check is inside the same `BEGIN IMMEDIATE` transaction and
precedes every migration statement. It is load-bearing: current v1
`ensure_schema()` can open a v2 database, run its old idempotent DDL, and write
`PRAGMA user_version=1` while leaving `sa_pick_lineages` present. Branch code
must reject that mixed state instead of treating it as a clean v1 database and
attempting a second rebuild. The strengthened idempotence node proves both the
normal v2 reconnect and this fail-closed arm without adding a test node.

`ensure_schema()` uses the existing idempotent fresh path for version `0`, the
new transactional path for version `1`, and a cheap fast return for version
`2`. Its docstring must state these two distinct guarantees accurately.

- [ ] **Step 5: Evolve direct-insert fixtures without changing node IDs**

Update `tests/test_sa_capture_store.py::_pick` and the seed in
`tests/test_sa_local_readers.py` to insert/resolve a lineage first:

```python
conn.execute(
    "INSERT OR IGNORE INTO sa_pick_lineages(symbol_key, picked_date, created_at) VALUES (?, ?, ?)",
    (symbol.strip().upper(), picked, scs.now_ts()),
)
lineage_id = conn.execute(
    "SELECT lineage_id FROM sa_pick_lineages WHERE symbol_key=? AND picked_date=?",
    (symbol.strip().upper(), picked),
).fetchone()[0]
```

Then include `lineage_id` in the existing insert. Do not weaken the fresh
schema's non-null contract merely to preserve old test helpers.

- [ ] **Step 6: Run GREEN and schema integrity probes**

```bash
pytest -q tests/test_sa_article_reconciliation_schema.py tests/test_sa_capture_store.py tests/test_sa_local_readers.py
python - <<'PY'
import sqlite3, tempfile
from src.sa_capture_store import connect
p = tempfile.mktemp(suffix='.db')
c = connect(p)
assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert c.execute('PRAGMA foreign_key_check').fetchall() == []
assert c.execute('PRAGMA user_version').fetchone()[0] == 2
c.close()
PY
```

Expected: exact new schema file `11 passed`; all evolved existing nodes pass;
integrity/FK probes print nothing and exit `0`.

- [ ] **Step 7: Commit schema v2**

```bash
git add src/sa_capture_store.py tests/test_sa_capture_store.py \
  tests/test_sa_local_readers.py tests/test_sa_article_reconciliation_schema.py
git commit -m "feat: add stable Alpha Picks article lineage schema"
```

---

### Task 2: Pure Deterministic Matching Authority

**Files:**
- Create: `src/sa_article_reconciliation.py`
- Create: `tests/test_sa_article_reconciliation.py`

**Interfaces:**
- Consumes: normalized source symbol, role/event anchor, article date, separate
  list/detail ticker observations, title/body, and rejected article IDs.
- Produces:

  ```python
  normalize_symbol(value: object) -> str | None
  parse_alpha_picks_article_id(url: str) -> str | None
  evaluate_candidate(event: PickEvent, article: ArticleEvidence) -> CandidateEvaluation
  decide_reconciliation(event: PickEvent, articles: Sequence[ArticleEvidence], *, rejected_article_ids: AbstractSet[str] = frozenset()) -> ReconciliationDecision
  ```

- [ ] **Step 1: Write the exact 15 pure RED nodes**

Create these exact nodes, with the assertion after each name as their contract:

- `test_normalize_symbol_is_trim_upper_only_and_preserves_provider_punctuation`:
  `" brk.b " -> "BRK.B"`, empty -> `None`, and no punctuation rewrite.
- `test_canonical_alpha_picks_url_parser_rejects_wrong_hosts_paths_and_non_digits`:
  accept only the canonical HTTPS host/path and return the numeric article ID.
- `test_date_bands_are_exact_near_outside_or_missing`: loop over distances
  `0, 1, 3, 4` plus invalid dates and assert exact/near/near/outside/missing.
- `test_exact_list_ticker_and_entry_phrase_is_auto_eligible`: BTSG exact date,
  list ticker, and `Stock Buy` yields strength `3`.
- `test_exact_detail_ticker_is_independent_of_generic_title_and_body`: generic
  title with detail BTSG and an entry phrase in role evidence still retains
  detail provenance without a title ticker token.
- `test_matching_list_and_detail_tickers_retain_both_provenance_codes`: equal
  explicit fields yield both evidence codes.
- `test_list_detail_ticker_conflict_is_review_only`: `BTSG` versus `AGX` yields
  `ticker_metadata_conflict` and no acceptance.
- `test_within_three_days_requires_explicit_ticker_and_strong_role_phrase`:
  distance three passes only with both required legs.
- `test_four_days_never_auto_accepts`: otherwise valid evidence at distance four
  stays review-only.
- `test_fallback_symbol_or_full_company_mention_requires_exact_date_and_role`:
  loop over symbol/full-company positives and missing-leg negatives.
- `test_article_type_and_ticker_prefix_cannot_supply_missing_identity_legs`:
  `analysis`, `commentary`, and `BTSG-OLD` do not become exact identity.
- `test_same_strength_tie_remains_unresolved_despite_article_id_order`: two
  strength-three rows have no accepted ID.
- `test_rejected_candidate_is_not_proposed_again`: the rejected strongest ID is
  excluded and rejection does not silently promote an equal ambiguous tie.
- `test_entry_and_exit_use_their_supplied_event_anchor_without_role_substitution`:
  entry/exit date calculations remain independent.
- `test_unreviewed_agx_locking_gains_title_is_not_invented_as_entry_or_exit`:
  the supplied AGX wording matches neither locked phrase family.

The BTSG positive must use a complete assertion rather than only checking a
truthy result:

```python
decision = decide_reconciliation(
    PickEvent(1, "BTSG", "BrightSpring Health Services, Inc.", "entry", "2026-07-15"),
    [ArticleEvidence(
        "6316639", "2026-07-15",
        "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth",
        None, "analysis", "BTSG", None, False,
    )],
)
assert decision.accepted_article_id == "6316639"
assert decision.candidates[0].strength == 3
assert decision.candidates[0].evidence_codes == (
    "date_exact", "ticker_list_exact", "role_entry_strong",
)
```

Use loops inside these functions rather than `pytest.mark.parametrize`, so the
file collects exactly `15` nodes. The BTSG positive title is exactly
`Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth`.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_sa_article_reconciliation.py -x
```

Expected: collection error `ModuleNotFoundError: src.sa_article_reconciliation`.

- [ ] **Step 3: Implement immutable domain types and phrase authority**

Create these public shapes:

```python
Role = Literal["entry", "exit"]
DateBand = Literal["exact", "near", "outside", "missing"]

@dataclass(frozen=True)
class PickEvent:
    lineage_id: int
    symbol_key: str
    company: str
    role: Role
    event_anchor_date: str | None

@dataclass(frozen=True)
class ArticleEvidence:
    article_id: str
    published_date: str | None
    title: str
    body_markdown: str | None
    article_type: str | None
    list_ticker: str | None
    detail_ticker: str | None
    has_content: bool

@dataclass(frozen=True)
class CandidateEvaluation:
    article_id: str
    date_band: DateBand
    date_distance_days: int | None
    evidence_codes: tuple[str, ...]
    strength: int
    auto_eligible: bool
    reason_code: str | None
    needs_enrichment: bool

@dataclass(frozen=True)
class ReconciliationDecision:
    accepted_article_id: str | None
    candidates: tuple[CandidateEvaluation, ...]
    reason_code: str | None
```

Centralize reviewed full-word patterns. The initial exact authority is:

```python
ENTRY_ROLE_PATTERNS = (
    re.compile(r"\bstock buy\b", re.I),
    re.compile(r"\b(?:initiat(?:e|es|ed|ing|ion)|initial stake)\b", re.I),
    re.compile(r"\bnew (?:position|stake)\b", re.I),
    re.compile(r"\b(?:add|adds|added|adding)\b.{0,40}\b(?:position|stake|shares?)\b", re.I),
)
EXIT_ROLE_PATTERNS = (
    re.compile(r"\bstock sell\b", re.I),
    re.compile(r"\b(?:sell|sells|sold|selling)\b", re.I),
    re.compile(r"\bclos(?:e|es|ed|ing)(?: out)?\b", re.I),
    re.compile(r"\bremov(?:e|es|ed|ing)\b", re.I),
    re.compile(r"\bexit(?:s|ed|ing)?\b", re.I),
)
```

Do not include `locking in gains`, generic `analysis`, `commentary`, `initial
stake` as exit, or arbitrary sentiment language.

- [ ] **Step 4: Implement evidence evaluation and unique-winner policy**

Strength is deterministic:

```text
3 = exact date + explicit non-conflicting provider ticker + role phrase
2 = distance 1..3 + explicit non-conflicting provider ticker + role phrase
1 = exact date + no explicit ticker + role phrase + unambiguous symbol/full-company mention
0 = review-only/unmatchable
```

Both explicit fields present and unequal yields only
`ticker_metadata_conflict`; fallback text may not override it. Symbol fallback
uses token boundaries, so `MU` never matches `MUR`. Company fallback requires
the complete normalized company string, not one short token. Stable article ID
sorts equal review rows but cannot choose among equal strongest candidates.
Rejected IDs are removed before deciding. `needs_enrichment=True` only for an
exact-date role-bearing candidate with no explicit ticker and no stored body.

- [ ] **Step 5: Run GREEN**

```bash
pytest -q tests/test_sa_article_reconciliation.py
```

Expected: `15 passed`.

- [ ] **Step 6: Commit the pure matcher**

```bash
git add src/sa_article_reconciliation.py tests/test_sa_article_reconciliation.py
git commit -m "feat: define deterministic Alpha Picks article matching"
```

---

### Task 3: SQLite Reconciliation Store and Backend Wiring

**Files:**
- Create: `src/sa_article_reconciliation_store.py`
- Create: `src/audit/sa_article_reconciliation.py`
- Modify: `src/tools/backends/sa_capture_backend.py`
- Create: `tests/test_sa_article_reconciliation_backend.py`
- Modify: `tests/test_sa_capture_backend.py`

**Interfaces:**
- Consumes: Task 1 schema, Task 2 pure matcher, and backend `_sa_conn()`.
- Produces connection-scoped functions:

  ```python
  resolve_lineage(conn, *, symbol: str, picked_date: str) -> int
  reconcile_events(conn, *, lineage_ids: Collection[int] | None, article_ids: Collection[str] | None, max_events: int, enrichment_limit: int) -> dict
  list_review_queue(conn, *, limit: int) -> dict
  resolve_event(conn, *, symbol: str, role: str, event_anchor_date: str) -> dict
  accept_link(conn, *, lineage_id: int, role: str, event_anchor_date: str, article_id: str, link_source: str, evidence_codes: Sequence[str], replace_link_id: int | None = None) -> dict
  reject_candidate(conn, *, lineage_id: int, role: str, event_anchor_date: str, article_id: str, reason_code: str) -> dict
  preview_legacy_links(conn, *, limit: int) -> dict
  ```

  `SACaptureDatabaseBackend` exposes transaction-owning wrappers with the same
  semantic names prefixed `reconcile_sa_articles`,
  `query_sa_article_review_queue`, `accept_sa_article_link`,
  `reject_sa_article_candidate`, `resolve_sa_reconciliation_event`, and
  `preview_sa_legacy_article_links`. The wrapper accepts stable
  `(symbol,picked_date)` keys for post-pick reconciliation and resolves them to
  lineage IDs inside SQLite; browser callers never manufacture lineage IDs.

- [ ] **Step 1: Write the exact 20 persistence/backend RED nodes**

Create these exact nodes:

- `test_article_list_and_detail_ticker_observations_persist_independently`
- `test_list_detail_conflict_keeps_both_values_and_legacy_projection_is_not_evidence`
- `test_null_observation_does_not_erase_prior_explicit_provider_ticker`
- `test_refresh_current_and_closed_rows_resolve_one_lineage`
- `test_refresh_changed_picked_date_resolves_new_lineage`
- `test_exact_unique_entry_auto_link_projects_to_every_lineage_row`
- `test_exit_auto_link_uses_closed_date_and_never_overwrites_entry_projection`
- `test_multiple_closed_dates_receive_distinct_exit_links`
- `test_missing_closed_date_is_unmatchable_and_visible`
- `test_same_strength_tie_stays_in_review_queue`
- `test_outside_window_legacy_projection_is_reported_not_grandfathered`
- `test_repeated_symbol_lineages_reconcile_independently`
- `test_reconciliation_rerun_is_idempotent`
- `test_rejected_candidate_is_durable_and_not_reproposed`
- `test_replacement_revokes_old_link_and_requires_expected_link_id`
- `test_manual_link_never_populates_provider_ticker_observations`
- `test_article_body_capture_survives_reconciliation_failure_byte_for_byte`
- `test_pick_capture_survives_reconciliation_failure_byte_for_byte`
- `test_matcher_requested_enrichment_is_deduped_and_bounded`
- `test_legacy_preview_and_review_queue_are_read_only`

Each name maps one-to-one to the corresponding Global Constraint and later
implementation step. The first four persistence assertions must use exact
stored values, for example:

```python
backend.upsert_sa_articles_meta([_article(
    "6316639",
    title="Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth",
    ticker="BTSG",
    list_ticker="BTSG",
    list_ticker_observed_at="2026-07-18T01:00:00Z",
)])
backend.save_article_with_comments(
    "6316639",
    "captured body",
    [],
    detail_ticker="BTSG",
    detail_ticker_observed_at="2026-07-18T01:05:00Z",
)
article = backend.get_sa_article_with_comments("6316639")
assert article["list_ticker"] == "BTSG"
assert article["detail_ticker"] == "BTSG"
assert article["list_ticker_observed_at"] == "2026-07-18T01:00:00+00:00"
assert article["detail_ticker_observed_at"] == "2026-07-18T01:05:00+00:00"
```

The RCL fixture uses one lineage with two exit dates. The repeated-symbol
fixture uses two lineages with different picked dates and one article per
window. Digest tests hash pick/article/comment rows before an injected matcher
exception and require identical captured facts afterward.

Strengthen existing nodes in place, without renaming:

- `test_save_article_with_comments_shape_and_pick_sync` now proves body/comments
  save without same-transaction pick mutation; retain the historical node name
  for accounting and explain it in a comment.
- `test_audit_unresolved_symbols_exact_and_like_fallback` now proves the
  compatibility audit is read-only and returns event-scoped review data; retain
  the node name for accounting.
- direct `sync_picks=False` call sites remove the retired argument.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_sa_article_reconciliation_backend.py tests/test_sa_capture_backend.py -x
```

Expected: new store module/methods are absent; existing mutation-shape nodes
fail once strengthened.

- [ ] **Step 3: Resolve lineage inside the pick refresh transaction**

Before each `sa_alpha_picks` insert, call:

```python
lineage_id = reconciliation_store.resolve_lineage(
    conn,
    symbol=str(pick.get("symbol") or ""),
    picked_date=store.canon_date(pick.get("picked_date")) or "",
)
```

Include `lineage_id` in both insert and conflict-update paths. Resolution is
`INSERT OR IGNORE` plus exact `(symbol_key,picked_date)` lookup in the same
`BEGIN IMMEDIATE` transaction. Empty symbol/date fails before stale marking can
commit. Current/closed rows share identity; distinct closed dates do not create
new lineages.

- [ ] **Step 4: Persist source-specific article observations**

Evolve article metadata upsert to accept `list_ticker` and
`list_ticker_observed_at`; body save accepts `detail_ticker` and
`detail_ticker_observed_at`. Each source uses `COALESCE(new, old)` so a transient
null extraction never erases previously captured explicit metadata. After each
write, refresh legacy `ticker` only when exactly one source is present or both
normalize equal:

```sql
UPDATE sa_articles
SET ticker = CASE
  WHEN list_ticker IS NOT NULL AND detail_ticker IS NOT NULL
       AND UPPER(TRIM(list_ticker)) = UPPER(TRIM(detail_ticker)) THEN UPPER(TRIM(list_ticker))
  WHEN list_ticker IS NOT NULL AND detail_ticker IS NULL THEN UPPER(TRIM(list_ticker))
  WHEN detail_ticker IS NOT NULL AND list_ticker IS NULL THEN UPPER(TRIM(detail_ticker))
  ELSE ticker
END
WHERE article_id = ?
```

The matcher reads only the source-specific fields. Existing legacy `ticker`
rows are not backfilled into them.

- [ ] **Step 5: Implement event reads, accepted links, and projection**

`list_events()` derives one entry event per lineage and one exit event per
distinct non-null closed date. It also emits a visible
`missing_event_anchor` row for a live closed observation with null/unparseable
date, but that row cannot be accepted. Candidate reads are bounded to reviewed
date windows plus any existing legacy article used for migration preview.

`accept_link()` runs under `BEGIN IMMEDIATE` and follows this sequence:

1. re-read lineage/event and article;
2. re-evaluate the candidate using Task 2;
3. if the same active link exists, return it idempotently;
4. if a different active link exists, require `replace_link_id` to equal it;
5. revoke the old link, insert the new link with `supersedes_link_id`;
6. for `entry` only, project `canonical_article_id` to all lineage rows and
   copy body/detail time only when the accepted article has body content; and
7. commit link and compatibility projection together.

User acceptance may choose a review-only candidate, but the response must carry
`warnings` for date/role/ticker mismatch. Automatic acceptance may use only
`auto_eligible=True`. Exit never touches compatibility projection.

- [ ] **Step 6: Implement idempotent reconciliation and review projection**

Set module constants:

```python
MAX_EVENTS_PER_RECONCILIATION = 100
MAX_CANDIDATES_PER_EVENT = 20
```

`reconcile_events()` excludes accepted and explicitly rejected candidates,
auto-links only a unique reviewed winner, and returns:

```python
{
    "status": "ok",
    "events_scanned": int,
    "auto_linked": int,
    "review_required": int,
    "enrichment": [{"article_id": str, "url": str}],
}
```

Enrichment is stable `(published_date DESC, article_id DESC)`, deduped, and
limited by the caller's explicit cap. `list_review_queue()` returns no raw pick
row IDs and this additive stable shape:

```python
{
  "events": [{
    "lineage_id": int,
    "symbol": str,
    "company": str,
    "role": "entry" | "exit",
    "event_anchor_date": str | None,
    "reason_code": str,
    "current_link": {"link_id": int, "article_id": str} | None,
    "candidates": [{
      "article_id": str,
      "url": str,
      "published_date": str | None,
      "title": str,
      "evidence_codes": ["date_exact", "ticker_list_exact", "role_entry_strong"],
      "reason_code": str | None,
      "content_state": "complete" | "missing" | "failed",
      "requires_confirmation": bool,
    }],
  }],
  "total": int,
}
```

`possible_picked_date_correction` is informational when the same symbol has
multiple lineages; it never migrates links.

`resolve_event()` is a strict read: normalize the supplied symbol, require one
exact lineage/event for `(symbol, role, event_anchor_date)`, and return the
internal lineage ID only when unambiguous. It does not fall back by ticker
prefix, nearest date, current row ID, or a different closed date.

- [ ] **Step 7: Retire both legacy writers in the backend**

Delete `_sync_canonical_to_picks()`, remove `sync_picks` from
`save_article_with_comments()`, and make body/comment saving capture-only. Turn
`audit_unresolved_symbols()` into a compatibility alias that calls the
read-only review projection and returns:

```python
{
    "unresolved_symbols": sorted({event["symbol"] for event in queue["events"]}),
    "resolved_by_fulltext": 0,
    "review_queue": queue,
}
```

No SQL in that method may begin a write transaction. Only
`sa_article_reconciliation_store.py::accept_link` may update legacy canonical
fields.

- [ ] **Step 8: Add the explicit audit CLI**

Create:

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--preview-legacy", action="store_true")
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)
    backend = SACaptureDatabaseBackend("postgresql://disabled", sa_db=args.db)
    payload = (
        backend.preview_sa_legacy_article_links(limit=args.limit)
        if args.preview_legacy
        else backend.query_sa_article_review_queue(limit=args.limit)
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0
```

The CLI never accepts `--apply`, never clears links, and never touches PG. Its
first normal store open may migrate an explicitly supplied copied v1 DB in the
schema owner's one-time DDL transaction. Once schema v2 exists, queue/preview
queries start no write transaction and create no links or decisions. This same
boundary applies to the popup's first queue read: "read-only" means no business
mutation, not "skip the required v1-to-v2 schema migration."

- [ ] **Step 9: Run GREEN and the single-writer static gate**

```bash
pytest -q tests/test_sa_article_reconciliation_backend.py tests/test_sa_capture_backend.py
rg -n '_sync_canonical_to_picks|sync_picks' src tests
rg -n 'UPDATE sa_alpha_picks SET.*canonical_article_id|canonical_article_id = \?' src/tools src/sa_article_reconciliation_store.py
```

Expected: exact new backend file `20 passed`; existing file green. First `rg`
has no production hit. The second may hit only
`src/sa_article_reconciliation_store.py` and explicit tests; any backend/DAL
writer is a stop condition.

- [ ] **Step 10: Commit store/backend reconciliation**

```bash
git add src/sa_article_reconciliation_store.py src/audit/sa_article_reconciliation.py \
  src/tools/backends/sa_capture_backend.py tests/test_sa_article_reconciliation_backend.py \
  tests/test_sa_capture_backend.py
git commit -m "feat: reconcile Alpha Picks articles by stable events"
```

---

### Task 4: Capture-First DAL and Native-Host Contracts

**Files:**
- Modify: `src/tools/data_access.py`
- Modify: `src/tools/backends/db_backend.py`
- Modify: `src/sa_native_host.py`
- Modify: `tests/test_sa_tools.py`
- Modify: `tests/test_db_backend_retired_pg_sa.py`
- Create: `tests/test_sa_reconciliation_native_host.py`

**Interfaces:**
- Consumes: Task 3 backend methods.
- Produces native actions `get_reconciliation_queue`,
  `resolve_reconciliation_event`, `accept_reconciliation_link`, and
  `reject_reconciliation_candidate`; additive capture response field
  `reconciliation` on pick/article/body capture; read-only compatibility
  `audit_unresolved`; no PG fallback.

- [ ] **Step 1: Write the exact nine native/DAL RED nodes**

Create exactly one node for each contract below:

- `test_pick_refresh_and_article_meta_capture_commit_before_separate_reconciliation`
- `test_save_article_content_commits_before_reconciliation_failure_and_stays_ok`
- `test_save_article_content_passes_detail_ticker_without_manual_symbol_injection`
- `test_get_reconciliation_queue_action_is_read_only_and_sanitized`
- `test_resolve_and_accept_reconciliation_link_validates_exact_event_and_canonical_url`
- `test_accept_reconciliation_link_requires_confirmation_for_mismatch_or_replacement`
- `test_reject_reconciliation_candidate_is_event_scoped_and_idempotent`
- `test_compatibility_audit_returns_queue_without_mutation`
- `test_retired_pg_reconciliation_methods_never_connect`

The first node is one table-driven node with two arms: `_handle_refresh`
records `capture_picks -> reconcile(stable pick keys)`, while article metadata
records `capture_meta -> reconcile(article IDs)`. In the pick arm,
reconciliation failure must leave `status='ok'`, the saved `count`, and the
refresh success metadata intact; `record_sa_refresh_failure` is never called.
The body matcher-failure node records concrete calls and asserts the capture
result independently:

```python
assert calls == [
    ("capture_body", "6316639", "body", "BTSG"),
    ("reconcile", ("6316639",), 100, 4),
]
assert response["status"] == "ok"
assert response["article_id"] == "6316639"
assert response["reconciliation"] == {
    "status": "failed",
    "error_code": "reconciliation_failed",
    "enrichment": [],
}
assert "synthetic sql failure" not in json.dumps(response)
```

Use fake DALs that record strict call order (`capture` before `reconcile`) and
raise in reconciliation. The response must remain `status='ok'` for captured
pick/body/meta facts with nested `reconciliation.status='failed'`; raw exception
text does not enter the extension response. The article-meta arm also seeds a
historical body-less row not present in the current scan and proves it is not in
normal `need_content`; the currently scanned body-less row remains present.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_sa_reconciliation_native_host.py tests/test_sa_tools.py tests/test_db_backend_retired_pg_sa.py -x
```

Expected: new actions/methods absent and old `synced_picks`/mutating-audit
contracts fail once evolved.

- [ ] **Step 3: Add retired-PG no-op surface and DAL wrappers**

`DatabaseBackend` methods return honest unavailable/empty values without
opening PG:

```python
def reconcile_sa_articles(self, **kwargs) -> dict:
    return {"status": "unavailable", "reason": "pg_sa_retired", "enrichment": []}

def query_sa_article_review_queue(self, limit: int = 50) -> dict:
    return {"events": [], "total": 0}

def resolve_sa_reconciliation_event(self, **kwargs) -> dict:
    return {"status": "unavailable", "reason": "pg_sa_retired"}

def accept_sa_article_link(self, **kwargs) -> dict:
    return {"status": "unavailable", "reason": "pg_sa_retired"}

def reject_sa_article_candidate(self, **kwargs) -> dict:
    return {"status": "unavailable", "reason": "pg_sa_retired"}
```

Remove `sync_picks` and `synced_picks` from the retired body-save stub. Evolve
the existing one-node retired-PG test in place and also exercise it through the
new native-host test node; no node rename.

- [ ] **Step 4: Make all three capture paths reconcile only after commit**

Keep `DataAccessLayer.apply_sa_refresh()` returning its existing integer so
legacy callers remain compatible. In `_handle_refresh`, first complete
`apply_sa_refresh()` (including refresh-success metadata), then invoke a
separate DAL reconciliation wrapper with deduped stable pick keys:

```python
reconciliation = dal.reconcile_sa_articles(
    pick_keys=[
        (str(p.get("symbol") or ""), str(p.get("picked_date") or ""))
        for p in picks
    ],
    article_ids=None,
    max_events=100,
    enrichment_limit=4,
)
```

Catch only this second call and return a sanitized nested failed result. Do not
enter `_handle_refresh`'s capture-failure branch, call
`record_sa_refresh_failure`, undo ticker sync, or change `count`. Both current
and closed refreshes use this path, so a new entry/exit event is compared with
already captured articles even when no article write occurs in that refresh.

In `DataAccessLayer.save_sa_articles_meta`, first upsert and compute the normal
cache lists. Compute normal `need_content` only from IDs in
`normalized_articles`; the list scraper's mode controls how wide that set is.
Do not query every historic body-less DB row into normal work. Then call:

```python
reconciliation = self._backend.reconcile_sa_articles(
    article_ids=[a["article_id"] for a in normalized_articles if a.get("article_id")],
    max_events=100,
    enrichment_limit={"quick": 4, "full": 12, "backfill": 20}.get(mode, 4),
)
```

Wrap only this second call; failure produces a sanitized nested failed result
without altering `saved`, `need_content`, or `need_comments`. In
`save_sa_article_with_comments`, add keyword-only `detail_ticker` and
`detail_ticker_observed_at`, first call the capture-only backend method, then
reconcile the one article the same way. `_handle_save_article_content` passes
only these scraper-returned fields. Return the capture stats plus
`reconciliation`. None of the three capture/reconciliation pairs share a
transaction.

- [ ] **Step 5: Implement validated native actions**

Add dispatcher cases and handlers. Advanced manual input first resolves its
stable event without exposing row IDs:

```python
{
  "action": "resolve_reconciliation_event",
  "symbol": "BTSG",
  "role": "entry",
  "event_anchor_date": "2026-07-15",
}
```

Require exactly one event; return a sanitized `ambiguous_event` or
`event_not_found` code otherwise. A successful response may include
`lineage_id` for background-to-native follow-up, but popup text never renders
it. The subsequent accept payload is:

```python
{
  "action": "accept_reconciliation_link",
  "lineage_id": int,
  "role": "entry" | "exit",
  "event_anchor_date": "YYYY-MM-DD",
  "article_id": str,
  "article_url": str,
  "replace_link_id": int | None,
  "confirm_warnings": bool,
}
```

Validate role/date/positive lineage ID and require
`parse_alpha_picks_article_id(article_url) == article_id`. A first response with
mismatch/replacement warnings is:

```python
{
    "status": "confirmation_required",
    "warnings": ["date_mismatch"],
    "candidate": {"article_id": "6316639", "published_date": "2026-07-15"},
}
```

Only `confirm_warnings=True` authorizes that reviewed user link. The reject
action accepts the same stable event key plus `article_id` and a code-owned
`reason_code='user_rejected'`. Native errors are logged and returned as
`{"status":"error","error_code":"reconciliation_failed"}` without raw DB
paths, SQL, cookies, or credentials.

`get_reconciliation_queue` and `resolve_reconciliation_event` open the normal
schema-owning SA connection. A v1 database may undergo the reviewed one-time v2
migration; after v2 they perform no DML, create no links/decisions, and are
therefore read-only at the product-data level. The queue test starts from v1,
asserts migration completes, and still requires zero accepted/rejected rows.

- [ ] **Step 6: Keep `audit_unresolved` additive and read-only**

Retain the action name for old popup compatibility, but update its handler log
to `review_required` rather than `resolved_by_fulltext`. It calls only the DAL
queue read, returns `resolved_by_fulltext: 0`, and cannot invoke accept/reject.

- [ ] **Step 7: Run GREEN**

```bash
pytest -q tests/test_sa_reconciliation_native_host.py tests/test_sa_tools.py tests/test_db_backend_retired_pg_sa.py
```

Expected: new file `9 passed`; all existing nodes green with no collection
delta outside the reviewed nine.

- [ ] **Step 8: Commit DAL/native contracts**

```bash
git add src/tools/data_access.py src/tools/backends/db_backend.py src/sa_native_host.py \
  tests/test_sa_tools.py tests/test_db_backend_retired_pg_sa.py \
  tests/test_sa_reconciliation_native_host.py
git commit -m "feat: expose Alpha Picks reconciliation through native host"
```

---

### Task 5: Explicit List and Detail Ticker Capture

**Files:**
- Create: `extensions/sa_alpha_picks/article_identity.js`
- Modify: `extensions/sa_alpha_picks/scrape_articles_list.js`
- Modify: `extensions/sa_alpha_picks/scrape_detail.js`
- Modify: `extensions/sa_alpha_picks/background.js`
- Create: `tests/test_sa_extension_article_identity.py`
- Modify: `tests/test_sa_extension_alpha_picks.py`

**Interfaces:**
- Consumes: Task 0 real DOM fixtures.
- Produces browser global `ArkScopeArticleIdentity` with
  `extractListTicker(card, dateText)` and `extractDetailTicker(document, h1)`;
  scraper fields `list_ticker`, `list_ticker_observed_at`, `detail_ticker`, and
  `detail_ticker_observed_at`.

- [ ] **Step 1: Write the exact eight DOM/parser RED nodes**

Create exactly these eight nodes:

- `test_btsg_real_list_fixture_extracts_ticker_after_optional_time_and_separator`
- `test_btsg_list_fixture_keeps_date_comments_and_article_id_intact`
- `test_list_ticker_bearing_node_wins_over_normalized_text_fallback`
- `test_list_parser_does_not_scan_unrelated_uppercase_page_text`
- `test_btsg_real_detail_fixture_extracts_security_header_ticker`
- `test_detail_ticker_is_independent_of_generic_title_and_absent_body_mention`
- `test_unreviewed_relative_date_shape_returns_null_instead_of_guessing`
- `test_list_and_detail_scrapers_emit_distinct_observation_fields`

The first fixture assertion is exact:

```python
payload = run_fixture(
    "btsg_articles_list_card.html",
    "article_identity.js",
    "scrape_articles_list.js",
)
assert len(payload) == 1
assert payload[0]["article_id"] == "6316639"
assert payload[0]["url"].startswith(
    "https://seekingalpha.com/alpha-picks/articles/6316639"
)
assert payload[0]["title"] == (
    "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth"
)
assert payload[0]["ticker"] == payload[0]["list_ticker"] == "BTSG"
assert payload[0]["date"] == "Jul 15, 2026"
assert payload[0]["comments_count"] == 265
assert payload[0]["article_type"] == "analysis"
assert payload[0]["list_ticker_observed_at"].endswith("Z")
```

Use the Task 0 runner and fixtures. Synthetic near-miss fixtures may be built
inside tests, but the two BTSG positives must execute the sanitized real DOM
files. The relative-date test is negative only.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_sa_extension_article_identity.py tests/test_sa_extension_alpha_picks.py -x
```

Expected: helper absent and BTSG list/detail results have no source-specific
ticker fields.

- [ ] **Step 3: Implement browser-safe identity helpers**

`article_identity.js` is a plain IIFE with no module/bundler requirement:

```javascript
(function (root) {
  "use strict";
  const TICKER = "[A-Z][A-Z.]{0,9}";
  function normalizeTicker(value) {
    const text = String(value || "").trim().toUpperCase();
    return new RegExp("^" + TICKER + "$").test(text) ? text : null;
  }
  function extractListTicker(card, dateText) {
    const scoped = card || null;
    if (!scoped || !dateText) return null;
    const nodes = scoped.querySelectorAll(
      '[data-testid*="ticker" i], [data-test-id*="ticker" i], a[href*="/symbol/"]'
    );
    for (const node of nodes) {
      const exact = normalizeTicker(node.textContent);
      if (exact) return exact;
    }
    const text = String(scoped.innerText || scoped.textContent || "").replace(/\s+/g, " ").trim();
    const at = text.indexOf(dateText);
    if (at < 0) return null;
    const tail = text.slice(at + dateText.length);
    const match = tail.match(
      /^\s*,?\s*(?:\d{1,2}:\d{2}\s*(?:AM|PM)(?:\s+ET)?\s*)?(?:[•·|]\s*)?([A-Z][A-Z.]{0,9})(?=\s*(?:[•·|]|\d+\s*Comments?\b|$))/i
    );
    return match ? normalizeTicker(match[1]) : null;
  }
  function extractDetailTicker(doc, h1) {
    if (!doc || !h1) return null;
    let scope = h1.parentElement;
    for (let depth = 0; scope && depth < 4; depth += 1, scope = scope.parentElement) {
      const text = String(scope.innerText || scope.textContent || "").replace(/\s+/g, " ");
      const match = text.match(/\(([A-Z][A-Z.]{0,9})\)\s+Stock\b/);
      if (match) return normalizeTicker(match[1]);
    }
    return null;
  }
  root.ArkScopeArticleIdentity = { normalizeTicker, extractListTicker, extractDetailTicker };
})(typeof globalThis !== "undefined" ? globalThis : this);
```

If Task 0's real DOM requires a narrower explicit selector, add only that
fixture-grounded selector. Do not broaden to arbitrary page text.

- [ ] **Step 4: Evolve both injected scrapers**

The list scraper uses the helper, keeps the existing local `ticker` only for
article-type detection and old-sidecar reverse compatibility, and emits:

```javascript
const observedAt = new Date().toISOString();
articles.push({
  article_id: articleId,
  url: href,
  title: text.substring(0, 200),
  ticker: ticker,
  list_ticker: ticker,
  list_ticker_observed_at: ticker ? observedAt : null,
  date: date,
  comments_count: commentsCount,
  article_type: articleType,
});
```

The detail scraper emits only independently observed detail identity:

```javascript
const detailTicker = ArkScopeArticleIdentity.extractDetailTicker(document, h1);
return {
  title,
  author,
  publish_date: publishDate,
  detail_ticker: detailTicker,
  detail_ticker_observed_at: detailTicker ? new Date().toISOString() : null,
  body_markdown: bodyMd,
  url: location.href,
  scraped_at: new Date().toISOString(),
};
```

- [ ] **Step 5: Inject the helper before each scraper**

Use ordered `files` arrays:

```javascript
files: ["article_identity.js", "scrape_articles_list.js"]
files: ["article_identity.js", "scrape_detail.js"]
```

Strengthen the existing structural extension test in place to pin both orders.
Do not add a manifest content script or broaden host permissions.

- [ ] **Step 6: Run GREEN**

```bash
pytest -q tests/test_sa_extension_article_identity.py tests/test_sa_extension_alpha_picks.py
```

Expected: new file `8 passed`; existing structural nodes pass.

- [ ] **Step 7: Commit provider ticker capture**

```bash
git add extensions/sa_alpha_picks/article_identity.js \
  extensions/sa_alpha_picks/scrape_articles_list.js \
  extensions/sa_alpha_picks/scrape_detail.js \
  extensions/sa_alpha_picks/background.js \
  tests/test_sa_extension_article_identity.py tests/test_sa_extension_alpha_picks.py
git commit -m "fix: preserve Alpha Picks provider ticker evidence"
```

---

### Task 6: Bounded Reconciliation Flow and Event-Scoped Manual Fetch

**Files:**
- Modify: `extensions/sa_alpha_picks/background.js`
- Create: `tests/test_sa_extension_reconciliation_flow.py`

**Interfaces:**
- Consumes: additive native-host responses from Task 4 and source fields from
  Task 5.
- Produces bounded detail-enrichment merge, read-only end-of-refresh queue,
  stable event-scoped candidate actions, and manual fetch that never injects a
  user symbol into provider observations.

- [ ] **Step 1: Write the exact seven flow RED nodes**

Create exactly these seven nodes:

- `test_reconciliation_enrichment_limits_are_quick_4_full_12_backfill_20`
- `test_normal_cache_work_and_reconciliation_enrichment_dedupe_by_article_id`
- `test_detail_save_forwards_only_scraped_detail_ticker_observation`
- `test_end_of_refresh_audit_reads_queue_and_never_requests_legacy_auto_write`
- `test_manual_fetch_requires_symbol_role_anchor_and_canonical_article_url`
- `test_manual_fetch_never_copies_user_symbol_into_provider_or_content_evidence`
- `test_capture_success_survives_nested_reconciliation_failure`

The dedupe node executes `mergeArticleFetchWork` and requires this exact order:

```javascript
const normal = [{ article_id: "a1" }, { article_id: "a2" }];
const extra = [
  { article_id: "a2" }, { article_id: "a3" }, { article_id: "a4" },
  { article_id: "a5" }, { article_id: "a6" }, { article_id: "a7" },
];
assert.deepEqual(
  mergeArticleFetchWork(normal, extra, "quick").map((item) => item.article_id),
  ["a1", "a2", "a3", "a4", "a5", "a6"],
);
```

These tests may inspect source structure and execute extracted pure helpers in
Node, but must assert call order/payloads, not merely substring presence.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_sa_extension_reconciliation_flow.py -x
```

Expected: limits/helpers/event payloads absent and manual path still injects
`ticker: item.symbol`.

- [ ] **Step 3: Merge only bounded extra enrichment**

Add:

```javascript
const RECONCILIATION_ENRICHMENT_LIMITS = { quick: 4, full: 12, backfill: 20 };

function mergeArticleFetchWork(normalWork, extraWork, mode) {
  const result = [];
  const seen = new Set();
  for (const item of normalWork || []) {
    if (!item || !item.article_id || seen.has(item.article_id)) continue;
    seen.add(item.article_id);
    result.push(item);
  }
  const cap = RECONCILIATION_ENRICHMENT_LIMITS[mode] || 4;
  let added = 0;
  for (const item of extraWork || []) {
    if (added >= cap) break;
    if (!item || !item.article_id || seen.has(item.article_id)) continue;
    seen.add(item.article_id);
    result.push(item);
    added += 1;
  }
  return result;
}
```

Use `metaResult.reconciliation?.enrichment` as the extra list. Do not cap or
reorder the normal scan-scoped `need_content` list. The DAL owns the rule that
normal work contains only IDs returned by this list scan; the extension owns
only deduplication and the separate enrichment cap. Strengthen the existing
DataAccess article-meta node in place to prove `quick` excludes an older
body-less DB row absent from the scrape while retaining a scanned body-less
row. This is an intent-strengthening edit with no node-count delta.

- [ ] **Step 4: Pass detail evidence and preserve capture truth**

Every `save_article_content` message adds:

```javascript
detail_ticker: detail.detail_ticker || null,
detail_ticker_observed_at: detail.detail_ticker_observed_at || null,
```

Count the article as fetched when `saveResult.ok` is true even if nested
`saveResult.reconciliation.status === 'failed'`. Surface review reconciliation
failure in the returned detail summary without relabeling captured body/comments
as failed.

- [ ] **Step 5: Replace mutating audit semantics with review discovery**

The existing end-of-refresh `audit_unresolved` call remains for reverse
compatibility but consumes only `review_queue`/`unresolved_symbols`. No action
or payload named `force`, `sync`, `closest`, or `fulltext` is sent. The popup
refresh result stores a sanitized review count, not database IDs.

- [ ] **Step 6: Make manual fetch event-scoped**

Manual items have this exact shape:

```javascript
{
  symbol: "BTSG",
  role: "entry",
  event_anchor_date: "2026-07-15",
  url: "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
  replace_link_id: null,
}
```

Reject items missing role/date/canonical URL before opening a tab, then request
`resolve_reconciliation_event` with the explicit symbol/role/date. If
resolution is absent or ambiguous, do not open or accept anything. When saving
metadata, remove `ticker: item.symbol`; pass only scraper-returned
`detail_ticker*` on body save. Also remove the current
`detail.title || item.symbol + " analysis"` fallback: use the scraped title,
an existing stored provider title, or the neutral `Alpha Picks article <id>`;
never interpolate `item.symbol` into title/body/raw provider fields. After
capture, pass the resolver's exact internal
`lineage_id` to `accept_reconciliation_link`. Queue-driven items may already
carry that internal ID; Advanced text never does and the background may not
infer it from a transient pick row. If the native host returns
`confirmation_required`, return that candidate to the popup and leave the link
unchanged. A second explicit UI action resends with `confirm_warnings: true`.
Clear only the accepted event, never all same-symbol events.

- [ ] **Step 7: Run GREEN**

```bash
pytest -q tests/test_sa_extension_reconciliation_flow.py
```

Expected: `7 passed`.

- [ ] **Step 8: Commit extension orchestration**

```bash
git add extensions/sa_alpha_picks/background.js tests/test_sa_extension_reconciliation_flow.py
git commit -m "feat: run bounded Alpha Picks article reconciliation"
```

---

### Task 7: Popup Review Queue and Advanced Escape Hatch

**Files:**
- Create: `extensions/sa_alpha_picks/reconciliation_ui.js`
- Modify: `extensions/sa_alpha_picks/popup.html`
- Modify: `extensions/sa_alpha_picks/popup.js`
- Create: `tests/test_sa_extension_reconciliation_ui.py`

**Interfaces:**
- Consumes: native review-queue and candidate action contracts.
- Produces default compact review rows, inline confirmation, accept/reject
actions, and collapsed event-scoped manual parsing.

- [ ] **Step 1: Write the exact eight popup RED nodes**

Create exactly these eight nodes:

- `test_review_queue_renders_event_role_anchor_title_and_provenance`
- `test_review_queue_renders_ticker_conflict_and_content_state_honestly`
- `test_use_candidate_action_sends_exact_stable_event_key_without_displaying_ids`
- `test_reject_action_removes_only_the_exact_event_candidate`
- `test_mismatch_or_replacement_uses_inline_second_confirmation_not_window_confirm`
- `test_advanced_manual_section_is_collapsed_by_default`
- `test_manual_parser_requires_symbol_role_iso_date_and_canonical_sa_url`
- `test_unresolved_queue_does_not_prefill_legacy_ticker_url_lines`

The manual parser node uses one positive and four negatives:

```javascript
const good = ui.parseAdvancedLines(
  "BTSG entry 2026-07-15 https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy"
);
assert.equal(good.errors.length, 0);
assert.deepEqual(good.items[0], {
  symbol: "BTSG",
  role: "entry",
  event_anchor_date: "2026-07-15",
  url: "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
});
for (const bad of [
  "BTSG https://seekingalpha.com/alpha-picks/articles/6316639-x",
  "BTSG update 2026-07-15 https://seekingalpha.com/alpha-picks/articles/6316639-x",
  "BTSG entry Today https://seekingalpha.com/alpha-picks/articles/6316639-x",
  "BTSG entry 2026-07-15 https://example.com/alpha-picks/articles/6316639-x",
]) {
  assert.equal(ui.parseAdvancedLines(bad).items.length, 0);
}
```

Run the popup helper in jsdom with fake action callbacks. Assert visible copy
and payload values. Assert `lineage_id`/`link_id` values from fixtures do not
appear in `textContent`.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_sa_extension_reconciliation_ui.py -x
```

Expected: helper/UI absent and raw textarea is still the default unresolved
workflow.

- [ ] **Step 3: Implement a pure popup renderer and parser**

Expose:

```javascript
ArkScopeReconciliationUI = {
  renderQueue(container, queue, handlers),
  parseAdvancedLines(text),
};
```

`parseAdvancedLines` accepts exactly:

```text
SYMBOL entry YYYY-MM-DD https://seekingalpha.com/alpha-picks/articles/123-slug
SYMBOL exit  YYYY-MM-DD https://seekingalpha.com/alpha-picks/articles/456-slug
```

It returns `{items, errors}` with line numbers; no two-field legacy syntax is
silently accepted. Review rows show Chinese user-facing labels for role,
anchor, evidence, and body state; they do not expose internal reason codes
without mapping them to concise copy.

- [ ] **Step 4: Replace the default manual section with review-first UI**

In `popup.html`, add an unframed `#reconciliationSection` with a compact list
and load `reconciliation_ui.js` before `popup.js`. Move the textarea under:

```html
<details id="manualAdvanced">
  <summary>進階：指定文章網址</summary>
  <label for="manualInput">每行：標的 事件 日期 文章網址</label>
  <textarea id="manualInput" rows="3"></textarea>
  <button id="manualBtn">擷取並檢查</button>
</details>
```

Do not add nested cards, horizontal scrolling, placeholder dead controls, or a
browser-native confirmation dialog. Keep popup controls readable at the
existing 320px width; long titles/URLs wrap.

- [ ] **Step 5: Wire queue lifecycle and inline confirmation**

On popup open and after refresh/accept/reject, send
`get_reconciliation_queue`. One failed read preserves the previous queue and
shows a retryable compact error; it does not invent an empty queue. Candidate
buttons send internal stable IDs but display only symbol/role/date/article.
`confirmation_required` expands a warning row with explicit `仍要使用` and
`取消`; it does not auto-resend.

- [ ] **Step 6: Remove legacy prefill behavior**

Delete `unresolved.map(function (t) { return t + " "; })`. Status may show
`待檢視 N 個事件`; it must not show a symbol-only `Missing:` list as though
one URL resolves every same-symbol event. Preserve an existing user draft only
inside the collapsed Advanced section.

- [ ] **Step 7: Run GREEN and static UI gates**

```bash
pytest -q tests/test_sa_extension_reconciliation_ui.py
rg -n 'window\.confirm|Paste missing article URLs|unresolved\.map.*return t' extensions/sa_alpha_picks
```

Expected: `8 passed`; static scan has no production hit.

- [ ] **Step 8: Commit popup review workflow**

```bash
git add extensions/sa_alpha_picks/reconciliation_ui.js \
  extensions/sa_alpha_picks/popup.html extensions/sa_alpha_picks/popup.js \
  tests/test_sa_extension_reconciliation_ui.py
git commit -m "feat: add Alpha Picks article review queue"
```

---

### Task 8: Live-Gate Comment Continuity Recovery

**Files:**
- Modify: `src/sa_capture_store.py`
- Modify: `src/tools/backends/sa_capture_backend.py`
- Modify: `src/tools/backends/db_backend.py`
- Modify: `src/tools/data_access.py`
- Modify: `src/sa_native_host.py`
- Modify: `extensions/sa_alpha_picks/scrape_articles_list.js`
- Modify: `extensions/sa_alpha_picks/background.js`
- Modify: `tests/test_sa_article_reconciliation_schema.py`
- Modify: `tests/test_sa_capture_backend.py`
- Modify: `tests/test_sa_tools.py`
- Modify: `tests/test_sa_reconciliation_native_host.py`
- Modify: `tests/test_sa_extension_article_identity.py`
- Modify: `tests/test_sa_extension_reconciliation_flow.py`

**Interfaces:**
- Consumes: section 3.5 of the design, the existing `comments_count`,
  `comments_fetched_at`, deduplicated comment store, Quick/Full/Backfill mode
  bounds, insert-only comment rows, and the list/detail native-host path.
- Produces: explicit count-observation provenance, a nullable provider-count
  checkpoint, a frozen pre-upsert row-ID watermark, persistent
  repaired/pending/terminal state, bounded Full parking, Backfill-only terminal
  evidence, and atomic usable-scan updates. Scheduling never treats an
  inaccessible historical inventory difference as pending work.
- Does not add a fixed age cutoff, delete old comments, change capture cadence,
  promise lifetime completeness, or alter the web app.

- [ ] **Step 1: Write ten failing schema/backend continuity tests**

Add exactly these nodes.

In `tests/test_sa_article_reconciliation_schema.py`:

```python
def test_v1_migration_seeds_comment_checkpoint_without_recovery_flag(
    tmp_path,
):
    path = tmp_path / "comments-v1.db"
    _create_v1(path)
    raw = sqlite3.connect(path)
    raw.execute(
        "UPDATE sa_articles SET comments_count=41, comments_fetched_at=? "
        "WHERE article_id='legacy-entry'",
        ("2026-07-18T00:00:00+00:00",),
    )
    raw.execute(
        "INSERT INTO sa_articles(article_id,url,title,comments_count) "
        "VALUES ('never-scanned','https://sa/never','Never scanned article',18)"
    )
    raw.commit()
    raw.close()

    conn = scs.connect(str(path))
    rows = {
        row["article_id"]: dict(row)
        for row in conn.execute(
            "SELECT article_id, comments_count_observed_at, "
            "provider_comments_count_at_last_scan, comment_recovery_state, "
            "comment_recovery_started_at, "
            "comment_recovery_baseline_max_row_id, "
            "comment_recovery_full_miss_count, comment_recovery_parked_at, "
            "comment_recovery_last_terminal_at, "
            "comment_recovery_last_terminal_reason FROM sa_articles"
        )
    }
    assert rows["legacy-entry"] == {
        "article_id": "legacy-entry",
        "comments_count_observed_at": None,
        "provider_comments_count_at_last_scan": 41,
        "comment_recovery_state": "repaired",
        "comment_recovery_started_at": None,
        "comment_recovery_baseline_max_row_id": None,
        "comment_recovery_full_miss_count": 0,
        "comment_recovery_parked_at": None,
        "comment_recovery_last_terminal_at": None,
        "comment_recovery_last_terminal_reason": None,
    }
    assert rows["never-scanned"] == {
        "article_id": "never-scanned",
        "comments_count_observed_at": None,
        "provider_comments_count_at_last_scan": None,
        "comment_recovery_state": "repaired",
        "comment_recovery_started_at": None,
        "comment_recovery_baseline_max_row_id": None,
        "comment_recovery_full_miss_count": 0,
        "comment_recovery_parked_at": None,
        "comment_recovery_last_terminal_at": None,
        "comment_recovery_last_terminal_reason": None,
    }
    assert conn.execute("SELECT COUNT(*) FROM sa_articles").fetchone()[0] == 2
    conn.close()
```

In `tests/test_sa_capture_backend.py`:

```python
def test_comment_scan_checkpoint_advances_only_on_usable_observation(backend):
    backend.upsert_sa_articles_meta([
        _article("positive"), _article("zero"), _article("empty"),
        _article("zero-pending"),
    ])

    positive = backend.update_article_comments(
        "positive", _comments(), provider_comments_count=12
    )
    zero = backend.update_article_comments(
        "zero", [], provider_comments_count=0
    )
    empty = backend.update_article_comments(
        "empty", [], provider_comments_count=7
    )
    backend.update_article_comments(
        "zero-pending", [_comment("zero-old")], provider_comments_count=1
    )
    backend.update_article_comments(
        "zero-pending", [_comment("zero-new")], provider_comments_count=2
    )
    zero_pending = backend.update_article_comments(
        "zero-pending", [], provider_comments_count=0
    )

    rows = {row["article_id"]: row for row in backend.query_sa_articles()}
    assert positive["comment_scan_usable"] is True
    assert rows["positive"]["provider_comments_count_at_last_scan"] == 12
    assert positive["prepared_comments"] == 2
    assert zero["comment_scan_usable"] is True
    assert rows["zero"]["provider_comments_count_at_last_scan"] == 0
    assert empty["comment_scan_usable"] is False
    assert rows["empty"]["provider_comments_count_at_last_scan"] is None
    assert rows["empty"]["comments_fetched_at"] is None
    assert zero_pending["comment_scan_usable"] is True
    assert rows["zero-pending"]["provider_comments_count_at_last_scan"] == 0
    assert rows["zero-pending"]["comment_recovery_state"] == "repaired"
    assert rows["zero-pending"]["comment_recovery_started_at"] is None
    assert rows["zero-pending"]["comment_recovery_baseline_max_row_id"] is None
    assert rows["zero-pending"]["comment_recovery_full_miss_count"] == 0
    assert rows["zero-pending"]["comment_recovery_parked_at"] is None


def test_body_capture_commits_when_comment_scan_is_unusable(backend):
    backend.upsert_sa_articles_meta([_article("body-only")])
    result = backend.save_article_with_comments(
        "body-only", "Provider body", [], provider_comments_count=9
    )
    article = backend.get_sa_article_with_comments("body-only")
    assert result["ok"] is True
    assert result["comment_scan_usable"] is False
    assert article["body_markdown"] == "Provider body"
    assert article["detail_fetched_at"] is not None
    assert article["comments_fetched_at"] is None
    assert article["provider_comments_count_at_last_scan"] is None
```

Add a non-test helper beside `_comments()`:

```python
def _comment(comment_id: str) -> dict:
    return {
        "comment_id": comment_id,
        "parent_comment_id": None,
        "commenter": f"user-{comment_id}",
        "comment_text": f"text-{comment_id}",
        "upvotes": 0,
        "comment_date": "2026-07-19T00:00:00Z",
    }
```

Add these seven backend nodes, for ten new storage/schema nodes total:

```python
def test_first_comment_scan_establishes_baseline_without_pending_recovery(backend):
    backend.upsert_sa_articles_meta([_article("first")])
    result = backend.update_article_comments(
        "first", [_comment("first-c1")],
        provider_comments_count=1, comment_scan_mode="quick",
    )
    row = backend.query_sa_articles()[0]
    assert result["comment_scan_usable"] is True
    assert row["comment_recovery_state"] == "repaired"
    assert row["comment_recovery_baseline_max_row_id"] is None


def test_recovery_watermark_is_pre_upsert_and_new_generation_cannot_self_repair(backend):
    backend.upsert_sa_articles_meta([_article("gap")])
    backend.update_article_comments(
        "gap", [_comment("old")],
        provider_comments_count=1, comment_scan_mode="quick",
    )
    raised = backend.update_article_comments(
        "gap", [_comment("new")],
        provider_comments_count=2, comment_scan_mode="quick",
    )
    with backend._sa_read() as conn:
        ids = {
            row["comment_id"]: row["id"]
            for row in conn.execute(
                "SELECT id, comment_id FROM sa_article_comments "
                "WHERE article_id='gap'"
            )
        }
    row = next(a for a in backend.query_sa_articles() if a["article_id"] == "gap")
    assert raised["comment_recovery_state"] == "pending"
    assert row["comment_recovery_baseline_max_row_id"] == ids["old"]
    assert ids["new"] > row["comment_recovery_baseline_max_row_id"]

    repeated = backend.update_article_comments(
        "gap", [_comment("new")],
        provider_comments_count=2, comment_scan_mode="full",
    )
    assert repeated["comment_recovery_state"] == "pending"
    assert repeated["comment_scan_baseline_overlap_count"] == 0


def test_any_mode_overlap_repairs_pending_recovery(backend):
    for mode in ("quick", "full", "backfill"):
        article_id = f"repair-{mode}"
        backend.upsert_sa_articles_meta([_article(article_id)])
        backend.update_article_comments(
            article_id, [_comment(f"{mode}-old")],
            provider_comments_count=1, comment_scan_mode="quick",
        )
        backend.update_article_comments(
            article_id, [_comment(f"{mode}-new")],
            provider_comments_count=2, comment_scan_mode="quick",
        )
        if mode == "quick":
            for _ in range(2):
                backend.update_article_comments(
                    article_id, [_comment(f"{mode}-new")],
                    provider_comments_count=2, comment_scan_mode="full",
                )
        repaired = backend.update_article_comments(
            article_id, [_comment(f"{mode}-new"), _comment(f"{mode}-old")],
            provider_comments_count=2, comment_scan_mode=mode,
        )
        assert repaired["comment_recovery_state"] == "repaired"
        assert repaired["comment_scan_baseline_overlap_count"] == 1
        assert repaired["comment_recovery_parked"] is False


def test_unusable_scan_freezes_comment_recovery_state(backend):
    backend.upsert_sa_articles_meta([_article("frozen")])
    backend.update_article_comments(
        "frozen", [_comment("frozen-old")],
        provider_comments_count=1, comment_scan_mode="quick",
    )
    backend.update_article_comments(
        "frozen", [_comment("frozen-new")],
        provider_comments_count=2, comment_scan_mode="quick",
    )
    before = next(a for a in backend.query_sa_articles() if a["article_id"] == "frozen")
    result = backend.update_article_comments(
        "frozen", [], provider_comments_count=3,
        comment_scan_mode="backfill", comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5,
    )
    after = next(a for a in backend.query_sa_articles() if a["article_id"] == "frozen")
    assert result["comment_scan_usable"] is False
    for key in (
        "comments_fetched_at", "provider_comments_count_at_last_scan",
        "comment_recovery_state", "comment_recovery_started_at",
        "comment_recovery_baseline_max_row_id",
        "comment_recovery_full_miss_count", "comment_recovery_parked_at",
        "comment_recovery_last_terminal_at",
        "comment_recovery_last_terminal_reason",
    ):
        assert after[key] == before[key]


def test_two_usable_full_misses_park_without_terminalizing(backend):
    backend.upsert_sa_articles_meta([_article("park")])
    backend.update_article_comments(
        "park", [_comment("park-old")],
        provider_comments_count=1, comment_scan_mode="quick",
    )
    backend.update_article_comments(
        "park", [_comment("park-new")],
        provider_comments_count=2, comment_scan_mode="quick",
    )
    raised_row = next(
        a for a in backend.query_sa_articles() if a["article_id"] == "park"
    )
    frozen_watermark = raised_row["comment_recovery_baseline_max_row_id"]
    frozen_started_at = raised_row["comment_recovery_started_at"]
    assert frozen_watermark is not None
    assert frozen_started_at is not None

    first = backend.update_article_comments(
        "park", [_comment("park-new")],
        provider_comments_count=2, comment_scan_mode="full",
    )
    second = backend.update_article_comments(
        "park", [_comment("park-new")],
        provider_comments_count=2, comment_scan_mode="full",
    )
    assert first["comment_recovery_full_miss_count"] == 1
    assert first["comment_recovery_parked"] is False
    assert second["comment_recovery_full_miss_count"] == 2
    assert second["comment_recovery_parked"] is True
    assert second["comment_recovery_state"] == "pending"

    quick = backend.update_article_comments(
        "park", [_comment("park-new"), _comment("park-latest")],
        provider_comments_count=3, comment_scan_mode="quick",
    )
    assert quick["net_new_comments"] == 1
    assert quick["comment_recovery_state"] == "pending"
    assert quick["comment_recovery_full_miss_count"] == 2
    assert quick["comment_recovery_parked"] is True
    after_quick = next(
        a for a in backend.query_sa_articles() if a["article_id"] == "park"
    )
    assert after_quick["comment_recovery_baseline_max_row_id"] == frozen_watermark
    assert after_quick["comment_recovery_started_at"] == frozen_started_at


def test_backfill_terminal_requires_five_stable_bottom_rounds(backend):
    backend.upsert_sa_articles_meta([_article("terminal")])
    backend.update_article_comments(
        "terminal", [_comment("terminal-old")],
        provider_comments_count=1, comment_scan_mode="quick",
    )
    backend.update_article_comments(
        "terminal", [_comment("terminal-new")],
        provider_comments_count=2, comment_scan_mode="quick",
    )
    for reason, rounds in (("timeout", 5), ("stable_bottom", 4)):
        result = backend.update_article_comments(
            "terminal", [_comment("terminal-new")],
            provider_comments_count=2, comment_scan_mode="backfill",
            comment_scan_stop_reason=reason,
            comment_scan_stable_bottom_rounds=rounds,
        )
        assert result["comment_recovery_state"] == "pending"
    result = backend.update_article_comments(
        "terminal", [_comment("terminal-new")],
        provider_comments_count=2, comment_scan_mode="backfill",
        comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5,
    )
    assert result["comment_recovery_state"] == "unreachable_terminal"
    assert result["comment_recovery_last_terminal_reason"] == "provider_bottom_unbridged"


def test_terminal_reanchors_future_epoch_and_preserves_audit(backend):
    backend.upsert_sa_articles_meta([_article("epoch")])
    backend.update_article_comments(
        "epoch", [_comment("epoch-old")],
        provider_comments_count=1, comment_scan_mode="quick",
    )
    backend.update_article_comments(
        "epoch", [_comment("epoch-new")],
        provider_comments_count=2, comment_scan_mode="quick",
    )
    terminal = backend.update_article_comments(
        "epoch", [_comment("epoch-new")],
        provider_comments_count=2, comment_scan_mode="backfill",
        comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5,
    )
    terminal_at = terminal["comment_recovery_last_terminal_at"]
    incidental = backend.update_article_comments(
        "epoch", [_comment("epoch-old"), _comment("epoch-new")],
        provider_comments_count=2, comment_scan_mode="backfill",
    )
    assert incidental["comment_recovery_state"] == "unreachable_terminal"
    assert incidental["comment_recovery_last_terminal_at"] == terminal_at

    current = backend.update_article_comments(
        "epoch", [_comment("epoch-new"), _comment("epoch-latest")],
        provider_comments_count=3, comment_scan_mode="quick",
    )
    assert current["comment_recovery_state"] == "repaired"
    assert current["comment_recovery_last_terminal_at"] == terminal_at
    assert current["comment_recovery_last_terminal_reason"] == "provider_bottom_unbridged"
```

The watermark test is load-bearing: `_fetch_existing_article_comments()` must
select `id`, and the watermark must be computed from that pre-upsert list. A
post-upsert `MAX(id)` implementation is forbidden even if every other assertion
passes.

- [ ] **Step 2: Run the schema/backend tests and prove RED**

```bash
pytest -q \
  tests/test_sa_article_reconciliation_schema.py::test_v1_migration_seeds_comment_checkpoint_without_recovery_flag \
  tests/test_sa_capture_backend.py::test_comment_scan_checkpoint_advances_only_on_usable_observation \
  tests/test_sa_capture_backend.py::test_body_capture_commits_when_comment_scan_is_unusable \
  tests/test_sa_capture_backend.py::test_first_comment_scan_establishes_baseline_without_pending_recovery \
  tests/test_sa_capture_backend.py::test_recovery_watermark_is_pre_upsert_and_new_generation_cannot_self_repair \
  tests/test_sa_capture_backend.py::test_any_mode_overlap_repairs_pending_recovery \
  tests/test_sa_capture_backend.py::test_unusable_scan_freezes_comment_recovery_state \
  tests/test_sa_capture_backend.py::test_two_usable_full_misses_park_without_terminalizing \
  tests/test_sa_capture_backend.py::test_backfill_terminal_requires_five_stable_bottom_rounds \
  tests/test_sa_capture_backend.py::test_terminal_reanchors_future_epoch_and_preserves_audit
```

Expected: all ten fail because the additive columns, scan-evidence keyword
arguments, and transition logic do not exist. The critical watermark test must
fail before it can mistake newly inserted rows for baseline; no failure may come
from malformed fixture SQL or helper data.

- [ ] **Step 3: Extend not-yet-shipped schema v2**

Keep `SCHEMA_VERSION = 2`: production is still v1, and every pre-addendum v2
file is a disposable live-gate artifact that must be recreated. Add to fresh
`sa_articles` and `_V1_TO_V2_STATEMENTS`:

```sql
comments_count_observed_at           TEXT,
provider_comments_count_at_last_scan INTEGER
    CHECK(provider_comments_count_at_last_scan IS NULL
          OR provider_comments_count_at_last_scan >= 0),
comment_recovery_state               TEXT NOT NULL DEFAULT 'repaired'
    CHECK(comment_recovery_state IN
          ('repaired', 'pending', 'unreachable_terminal')),
comment_recovery_started_at          TEXT,
comment_recovery_baseline_max_row_id INTEGER
    CHECK(comment_recovery_baseline_max_row_id IS NULL
          OR comment_recovery_baseline_max_row_id >= 0),
comment_recovery_full_miss_count     INTEGER NOT NULL DEFAULT 0
    CHECK(comment_recovery_full_miss_count >= 0),
comment_recovery_parked_at           TEXT,
comment_recovery_last_terminal_at    TEXT,
comment_recovery_last_terminal_reason TEXT
```

```sql
ALTER TABLE sa_articles ADD COLUMN comments_count_observed_at TEXT;
ALTER TABLE sa_articles ADD COLUMN provider_comments_count_at_last_scan INTEGER
  CHECK(provider_comments_count_at_last_scan IS NULL
        OR provider_comments_count_at_last_scan >= 0);
ALTER TABLE sa_articles ADD COLUMN comment_recovery_state TEXT NOT NULL
  DEFAULT 'repaired' CHECK(comment_recovery_state IN
    ('repaired', 'pending', 'unreachable_terminal'));
ALTER TABLE sa_articles ADD COLUMN comment_recovery_started_at TEXT;
ALTER TABLE sa_articles ADD COLUMN comment_recovery_baseline_max_row_id INTEGER
  CHECK(comment_recovery_baseline_max_row_id IS NULL
        OR comment_recovery_baseline_max_row_id >= 0);
ALTER TABLE sa_articles ADD COLUMN comment_recovery_full_miss_count INTEGER
  NOT NULL DEFAULT 0 CHECK(comment_recovery_full_miss_count >= 0);
ALTER TABLE sa_articles ADD COLUMN comment_recovery_parked_at TEXT;
ALTER TABLE sa_articles ADD COLUMN comment_recovery_last_terminal_at TEXT;
ALTER TABLE sa_articles ADD COLUMN comment_recovery_last_terminal_reason TEXT;
UPDATE sa_articles
SET provider_comments_count_at_last_scan = COALESCE(comments_count, 0)
WHERE comments_fetched_at IS NOT NULL;
```

Do not seed `pending`, a row-ID watermark, miss count, parked timestamp, or
terminal audit. The migration structurally waives every pre-v2 inventory
difference while preserving all article/comment rows. Extend the existing v2-
artifact mismatch guard: a file that advertises v1 but already contains any new
continuity column must fail closed instead of rerunning the rebuild.

The list-metadata upsert writes `comments_count` only when
`comments_count_observed_at` is non-null; unknown input preserves the prior
count and observation timestamp:

```sql
comments_count = CASE
  WHEN excluded.comments_count_observed_at IS NOT NULL
    THEN excluded.comments_count
  ELSE sa_articles.comments_count
END,
comments_count_observed_at = COALESCE(
  excluded.comments_count_observed_at,
  sa_articles.comments_count_observed_at
)
```

- [ ] **Step 4: Implement the atomic backend transition owner**

Add one backend normalization seam and use it in both save methods:

```python
def _provider_comment_count(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _comment_scan_usable(prepared_count: int, provider_count: int | None) -> bool:
    return prepared_count > 0 or provider_count == 0
```

Normalize scan evidence through allowlists:

```python
_COMMENT_SCAN_MODES = frozenset({"quick", "full", "backfill"})
_COMMENT_TERMINAL_STOP_REASON = "stable_bottom"
_COMMENT_TERMINAL_BOTTOM_ROUNDS = 5
_COMMENT_FULL_MISS_LIMIT = 2


def _comment_scan_mode(value) -> str:
    return value if value in _COMMENT_SCAN_MODES else "quick"


def _stable_bottom_rounds(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)
```

Evolve signatures in `sa_capture_backend.py`, `db_backend.py`, and DAL:

```python
def save_article_with_comments(
    self, article_id, body_markdown, comments, *,
    detail_ticker=None, detail_ticker_observed_at=None,
    provider_comments_count=None, comment_scan_mode="quick",
    comment_scan_stop_reason=None, comment_scan_stable_bottom_rounds=0,
) -> dict: ...

def update_article_comments(
    self, article_id, comments, *, provider_comments_count=None,
    comment_scan_mode="quick", comment_scan_stop_reason=None,
    comment_scan_stable_bottom_rounds=0,
) -> dict: ...
```

Refactor `_fetch_existing_article_comments()` to select `id` as well as the
existing identity/content fields. Call it exactly once after `BEGIN IMMEDIATE`
and before preparing or inserting comments. Refactor `_upsert_article_comments`
so the caller supplies that preloaded list and receives the normalized prepared
comments; it must not perform a second read that can blur the generation
boundary.

Inside the transaction, derive these sets before upsert:

```python
existing_by_comment_id = {
    row["comment_id"]: row for row in existing_rows if row.get("comment_id")
}
prepared_ids = {
    row["comment_id"] for row in prepared_comments if row.get("comment_id")
}
existing_overlap_ids = prepared_ids & existing_by_comment_id.keys()
pre_upsert_max_row_id = max(
    (int(row["id"]) for row in existing_rows), default=None
)
```

For a pending row, baseline overlap is restricted to rows at or below the
frozen watermark:

```python
baseline_overlap_ids = {
    comment_id for comment_id in existing_overlap_ids
    if int(existing_by_comment_id[comment_id]["id"])
       <= int(article["comment_recovery_baseline_max_row_id"])
}
```

Apply this transition table only when `_comment_scan_usable(...)` is true:

| Current fact | Evidence | Transition |
|---|---|---|
| any | explicit provider zero | current state `repaired`; clear pending watermark/miss/park; keep terminal audit |
| `pending` | `baseline_overlap_ids` nonempty | `repaired`; clear pending watermark/miss/park |
| `pending` | usable Quick miss | remain pending; miss counter unchanged |
| `pending` | usable Full miss #1 | remain pending; miss count `1` |
| `pending` | usable Full miss #2 or later | remain pending; saturate miss count at `2`; set/preserve parked timestamp |
| `pending` | usable Backfill miss without terminal evidence | remain pending/parked unchanged |
| `pending` | Backfill + `stable_bottom` + rounds >= `5` | `unreachable_terminal`; retain terminal audit; clear pending watermark/miss/park and re-anchor |
| `repaired` or `unreachable_terminal` | explicit count changed, prior rows exist, zero existing overlap | raise `pending`, freezing `pre_upsert_max_row_id`; a Full raising scan starts miss count at `1`; a qualifying Backfill may terminalize in the same transaction |
| `repaired` or `unreachable_terminal` | first scan or explicit count changed and scan overlaps prior rows | current epoch `repaired`; terminal audit remains |
| `unreachable_terminal` | provider count unchanged, with or without overlap | remain terminal; insert any newly visible comments but do not relabel the prior stop decision |

If a pending epoch receives another count change, its original watermark and
start timestamp stay frozen. The current scan may repair from overlap but may
not re-anchor a miss. Invalid/unknown mode is normalized to Quick and therefore
can neither increment Full misses nor terminalize.

Only a usable scan updates `comments_fetched_at`; only a usable scan with a
non-null normalized provider count updates the checkpoint. An unusable scan
may still commit a valid article body/detail ticker, but it cannot raise, clear,
park, terminalize, re-anchor, or alter any prior recovery field.

Return only numeric/sanitized diagnostics, never comment identities:

```python
{
    "comment_scan_usable": usable,
    "comment_scan_existing_overlap_count": len(existing_overlap_ids),
    "comment_scan_baseline_overlap_count": len(baseline_overlap_ids),
    "comment_scan_identity_overlap_rate": (
        len(existing_overlap_ids) / len(prepared_ids) if prepared_ids else 0.0
    ),
    "comment_recovery_state": state,
    "comment_recovery_full_miss_count": full_misses,
    "comment_recovery_parked": parked_at is not None,
    "comment_recovery_last_terminal_at": last_terminal_at,
    "comment_recovery_last_terminal_reason": last_terminal_reason,
}
```

Log a sanitized warning when a previously overlapping article abruptly yields
zero identity overlap; this is a parser-identity diagnostic only and cannot
change the transition table.

- [ ] **Step 5: Run GREEN, compatibility shapes, and commit the storage half**

```bash
pytest -q \
  tests/test_sa_article_reconciliation_schema.py \
  tests/test_sa_capture_backend.py \
  tests/test_db_backend_retired_pg_sa.py
git add src/sa_capture_store.py src/tools/backends/sa_capture_backend.py \
  src/tools/backends/db_backend.py tests/test_sa_article_reconciliation_schema.py \
  tests/test_sa_capture_backend.py tests/test_db_backend_retired_pg_sa.py
git commit -m "fix: track Alpha Picks comment continuity"
```

Expected: all selected tests PASS; read-shape key sets include every additive
field; schema remains version `2`; no article/comment row is removed; the
watermark test proves rows inserted by the raising scan cannot repair
themselves.

- [ ] **Step 6: Write six failing parser/scheduler/transport tests**

Add exactly these nodes:

1. `tests/test_sa_extension_article_identity.py::test_comment_count_observation_distinguishes_zero_from_unknown`
2. `tests/test_sa_tools.py::TestDataAccessArticleMeta::test_quick_comment_work_uses_observation_checkpoint_not_inventory_gap`
3. `tests/test_sa_tools.py::TestDataAccessArticleMeta::test_full_and_backfill_prioritize_recovery_state_with_park_boundary`
4. `tests/test_sa_reconciliation_native_host.py::test_save_comments_only_forwards_recovery_scan_evidence`
5. `tests/test_sa_extension_reconciliation_flow.py::test_comment_refresh_counts_only_usable_checkpointed_scan`
6. `tests/test_sa_extension_reconciliation_flow.py::test_comment_scroll_reports_stable_bottom_evidence`

The parser node is:

```python
def test_comment_count_observation_distinguishes_zero_from_unknown(tmp_path):
    fixture = tmp_path / "comment-counts.html"
    fixture.write_text(
        """<article><h3><a href='/alpha-picks/articles/10-zero'>
        A sufficiently long zero comments article title</a></h3>
        <span>Jul 19, 2026, 12:00 PM</span><a>0 Comments</a></article>
        <article><h3><a href='/alpha-picks/articles/11-unknown'>
        A sufficiently long unknown comments article title</a></h3>
        <span>Jul 18, 2026, 12:00 PM</span></article>""",
        encoding="utf-8",
    )
    payload = _run_fixture(fixture, IDENTITY, LIST_SCRAPER)
    by_id = {item["article_id"]: item for item in payload}
    explicit_zero = by_id["10"]
    unknown = by_id["11"]

    assert explicit_zero["comments_count"] == 0
    assert explicit_zero["comments_count_observed_at"].endswith("Z")
    assert unknown["comments_count"] == 0
    assert unknown["comments_count_observed_at"] is None
```

Strengthen the existing BTSG fixture node to require its explicit `265` count
has an observation timestamp. Strengthen
`test_articles_meta_upsert_and_query` in place: an upsert with no observation
timestamp may update unrelated metadata but must preserve the prior provider
count and count-observation timestamp.

The Quick node table-drives six rows in one pytest node:

```python
def test_quick_comment_work_uses_observation_checkpoint_not_inventory_gap(self):
    cases = [
        # provider, checkpoint, inventory, observed, state, parked, scheduled
        (983, 983, 592, True, "repaired", None, False),
        (984, 983, 592, True, "repaired", None, True),
        (982, 983, 592, True, "repaired", None, True),
        (0, None, 0, True, "repaired", None, False),
        (983, 982, 592, False, "repaired", None, False),
        (984, 983, 592, True, "pending", "2026-07-19T00:00:00Z", True),
    ]
    for provider, checkpoint, inventory, observed, state, parked, scheduled in cases:
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.reconcile_sa_articles = MagicMock(
            return_value={"status": "ok", "enrichment": []}
        )
        dal._backend.query_sa_articles = MagicMock(return_value=[{
            "article_id": "a1", "url": "https://example.com/a1",
            "has_content": True, "comments_count": provider,
            "comments_count_observed_at": (
                "2026-07-19T00:00:00+00:00" if observed else None
            ),
            "provider_comments_count_at_last_scan": checkpoint,
            "stored_comments_count": inventory,
            "comments_fetched_at": "2026-07-18T00:00:00+00:00",
            "comment_recovery_state": state,
            "comment_recovery_parked_at": parked,
        }])
        incoming = {
            "article_id": "a1", "url": "https://example.com/a1",
            "comments_count": provider,
            "comments_count_observed_at": (
                "2026-07-19T00:00:00+00:00" if observed else None
            ),
        }
        result = dal.save_sa_articles_meta([incoming], mode="quick")
        expected = ([{
            "article_id": "a1", "url": "https://example.com/a1",
            "provider_comments_count": provider,
        }] if scheduled else [])
        assert result["need_comments"] == expected
```

For each case, the article is in the current scan and has content. The unknown-
count case has `comments_count_observed_at=None`; the others use an ISO
timestamp. The last case proves a parked pending article remains eligible on a
fresh count change. Assert the scheduled item, when present, includes
`provider_comments_count=<provider>` and never derives work from `inventory`.

The Full/Backfill node supplies unparked/parked pending rows, a fresh
`983/983/592` historical difference, a TTL-stale repaired row, and a TTL-stale
terminal row. It proves pending priority, Full parking, Backfill inclusion,
terminal exclusion, and absence of gap-magnitude work:

```python
def test_full_and_backfill_prioritize_recovery_state_with_park_boundary(self):
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    rows = [
        {
            "article_id": "pending", "url": "https://example.com/pending",
            "has_content": True, "comments_count": 20,
            "comments_count_observed_at": recent,
            "provider_comments_count_at_last_scan": 20,
            "stored_comments_count": 12, "published_date": "2026-07-18",
            "comments_fetched_at": recent,
            "comment_recovery_state": "pending",
            "comment_recovery_parked_at": None,
        },
        {
            "article_id": "parked", "url": "https://example.com/parked",
            "has_content": True, "comments_count": 30,
            "comments_count_observed_at": recent,
            "provider_comments_count_at_last_scan": 30,
            "stored_comments_count": 12, "published_date": "2026-07-17",
            "comments_fetched_at": recent,
            "comment_recovery_state": "pending",
            "comment_recovery_parked_at": recent,
        },
        {
            "article_id": "fresh-gap", "url": "https://example.com/fresh",
            "has_content": True, "comments_count": 983,
            "comments_count_observed_at": recent,
            "provider_comments_count_at_last_scan": 983,
            "stored_comments_count": 592, "published_date": "2026-07-19",
            "comments_fetched_at": recent,
            "comment_recovery_state": "repaired",
            "comment_recovery_parked_at": None,
        },
        {
            "article_id": "stale-new", "url": "https://example.com/new",
            "has_content": True, "comments_count": 40,
            "comments_count_observed_at": old,
            "provider_comments_count_at_last_scan": 40,
            "stored_comments_count": 20, "published_date": "2026-07-18",
            "comments_fetched_at": old,
            "comment_recovery_state": "repaired",
            "comment_recovery_parked_at": None,
        },
        {
            "article_id": "terminal", "url": "https://example.com/terminal",
            "has_content": True, "comments_count": 50,
            "comments_count_observed_at": old,
            "provider_comments_count_at_last_scan": 50,
            "stored_comments_count": 20, "published_date": "2026-07-16",
            "comments_fetched_at": old,
            "comment_recovery_state": "unreachable_terminal",
            "comment_recovery_parked_at": None,
        },
    ]
    expected = {
        "full": ["pending", "stale-new"],
        "backfill": ["pending", "parked", "stale-new"],
    }
    for mode, expected_ids in expected.items():
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.query_sa_articles = MagicMock(return_value=rows)
        dal._backend.reconcile_sa_articles = MagicMock(
            return_value={"status": "ok", "enrichment": []}
        )
        with patch(
            "src.agents.config.get_agent_config",
            return_value=SimpleNamespace(
                sa_comments_cache_days=7,
                sa_comments_backfill_per_full_scan=2,
                sa_comments_backfill_per_backfill_scan=3,
            ),
        ):
            result = dal.save_sa_articles_meta([{
                "article_id": "fresh-gap", "url": "https://example.com/fresh",
                "comments_count": 983,
                "comments_count_observed_at": recent,
            }], mode=mode)
        assert [item["article_id"] for item in result["need_comments"]] == expected_ids
        assert "fresh-gap" not in expected_ids
        assert "terminal" not in expected_ids
```

Recovery rows consume the mode's comment budget before TTL rows; count-delta
work for the current scan remains ahead of both and is deduplicated. Full skips
parked pending rows; Backfill includes them. Keep the existing TTL and mutual-
exclusion tests and evolve the old top-gap tests in place without renaming their
node IDs.

The native-host node is:

```python
def test_save_comments_only_forwards_recovery_scan_evidence():
    dal = MagicMock()
    dal.save_sa_comments_only.return_value = {
        "prepared_comments": 0, "stored_comments_total": 592,
        "net_new_comments": 0, "comment_scan_usable": False,
        "comment_recovery_state": "pending",
    }
    result = host._handle_save_comments_only(dal, {
        "article_id": "a1", "comments": [], "provider_comments_count": 12,
        "comment_scan_mode": "backfill",
        "comment_scan_stop_reason": "stable_bottom",
        "comment_scan_stable_bottom_rounds": 5,
    })
    dal.save_sa_comments_only.assert_called_once_with(
        "a1", [], provider_comments_count=12,
        comment_scan_mode="backfill",
        comment_scan_stop_reason="stable_bottom",
        comment_scan_stable_bottom_rounds=5,
    )
    assert result["status"] == "ok"
    assert result["comment_scan_usable"] is False
    assert result["comment_recovery_state"] == "pending"
```

The extension-flow node supplies one scheduled comment item with an empty
scraper result:

```python
def test_comment_refresh_counts_only_usable_checkpointed_scan():
    result = _run_background(
        _DETAIL_FLOW_SETUP
        + r"""
        scrollToComments = async function () {
          return {
            stop_reason: "stable_bottom", stable_bottom_rounds: 5,
            comments_loaded: 0, rounds: 5, elapsed_ms: 10,
          };
        };
        sendNativeMessage2 = async function (message) {
          calls.push(message);
          if (message.action === "save_articles_meta") return {
            status: "ok", saved: 1, need_content: [],
            need_comments: [{
              article_id: "a1", url: "https://seekingalpha.com/alpha-picks/articles/1-a",
              provider_comments_count: 12,
            }],
            unresolved_symbols: [], reconciliation: {status: "ok", enrichment: []},
          };
          if (message.action === "save_comments_only") return {
            status: "ok", comment_scan_usable: false, net_new_comments: 0,
          };
          return {status: "ok", unresolved_symbols: [], review_queue: {total: 0, events: []}};
        };
        var summary = await doDetailFetch(1, [], "quick");
        return {calls: calls, summary: summary};
        """
    )
    save = next(
        item for item in result["calls"] if item["action"] == "save_comments_only"
    )
    assert save["provider_comments_count"] == 12
    assert save["comment_scan_mode"] == "quick"
    assert save["comment_scan_stop_reason"] == "stable_bottom"
    assert save["comment_scan_stable_bottom_rounds"] == 5
    assert result["summary"]["comments_refreshed"] == 0
    assert result["summary"]["failed"] == 1
```

The stable-bottom node drives the real `scrollToComments()` loop with five
unchanged bottom observations and no loader/control. Override only `sleep` and
the browser execution seam; do not replace the function under test:

```python
def test_comment_scroll_reports_stable_bottom_evidence():
    result = _run_background(
        r"""
        sleep = async function () {};
        chrome.scripting.executeScript = async function () {
          return [{result: {
            comments: 12, atBottom: true, clicked: false, loading: false,
          }}];
        };
        var stats = await scrollToComments(1, {
          mode: "backfill", articleId: "a1",
        });
        return stats;
        """
    )
    assert result["stop_reason"] == "stable_bottom"
    assert result["stable_bottom_rounds"] == 5
    assert result["comments_loaded"] == 12
```

Strengthen this node in place with a second invocation where
`loading: true` on every round; it must end by `max_scrolls` or timeout and
report fewer than five stable-bottom rounds. A visible loader therefore cannot
manufacture terminal evidence. Add a third invocation whose count is stable for
two rounds, grows once, and is then stable for five rounds. It must stop only
after all five post-growth rounds, proving that growth resets rather than merely
pauses the terminal counter.

Strengthen the existing successful refresh node to return
`comment_scan_usable: true` and retain its existing ordering assertion.
Also strengthen the existing body-content native-host and background-flow nodes
to pass one provider count plus scan mode/stop reason/stable-bottom rounds from
a `need_content` work item through `save_article_content` into
`save_sa_article_with_comments`; these are in-place contract upgrades and add
no node.

- [ ] **Step 7: Run the six tests and prove RED for the reviewed reasons**

```bash
pytest -q \
  tests/test_sa_extension_article_identity.py::test_comment_count_observation_distinguishes_zero_from_unknown \
  tests/test_sa_tools.py::TestDataAccessArticleMeta::test_quick_comment_work_uses_observation_checkpoint_not_inventory_gap \
  tests/test_sa_tools.py::TestDataAccessArticleMeta::test_full_and_backfill_prioritize_recovery_state_with_park_boundary \
  tests/test_sa_reconciliation_native_host.py::test_save_comments_only_forwards_recovery_scan_evidence \
  tests/test_sa_extension_reconciliation_flow.py::test_comment_refresh_counts_only_usable_checkpointed_scan \
  tests/test_sa_extension_reconciliation_flow.py::test_comment_scroll_reports_stable_bottom_evidence
```

Expected: parser observation is absent, Quick still schedules from `983 > 592`,
Full/Backfill still rank inventory gaps without pending/park semantics, recovery
scan evidence is not forwarded, an empty positive-count scan is falsely counted
refreshed, and the scroll loop exposes no reviewed stable-bottom proof. Any
unrelated fixture or harness failure must be fixed before implementation.

- [ ] **Step 8: Implement observed counts, state-aware scheduling, and scan evidence**

In `scrape_articles_list.js`, make count extraction return both value and
certainty. Preserve the compatibility numeric `comments_count` while adding a
timestamp only for an explicit match:

```javascript
var comments = extractCommentsCount(card, cardText, date);
var commentsObservedAt = comments.observed ? new Date().toISOString() : null;
// payload
comments_count: comments.value,
comments_count_observed_at: commentsObservedAt,
```

The helper returns `{value: 0, observed: false}` for absent/unparseable text and
`{value: n, observed: true}` for an exact provider label, including explicit
zero. `_sanitize_sa_article_meta()` retains the timestamp and never treats a
missing timestamp as a new zero observation.

In `save_sa_articles_meta()` build current-scan count observations from
`normalized_articles`, not from the persisted row's possibly older timestamp.
Quick schedules only current scanned/content-ready rows where an explicit count
is positive with null checkpoint, or differs from a non-null checkpoint. A
count decrease is work; explicit zero with a null checkpoint is not. Unknown
count is not work. Pending alone does not make a Quick run repeat the same
shallow page when the provider count is stable; a parked article remains
eligible whenever a fresh count change occurs.

For Full/Backfill, add current-scan count-delta work first. Spend the remaining
mode comment budget on recovery rows before TTL rows: Full selects pending rows
with null `comment_recovery_parked_at`; Backfill selects all pending rows. Then
select TTL-stale, content-ready, non-duplicate rows whose recovery state is not
`unreachable_terminal`, ordered by
`(published_date, article_id)` descending. The configured per-mode limit bounds
the combined recovery+TTL leg. Remove all use of `remote_count - stored_count`,
gap magnitude sorting, and inventory-gap backlog. Keep `need_content`
precedence. Add `provider_comments_count` to work items only when an explicit
observation is available.

Update `scrollToComments()` so every injected round also returns whether a
visible loading indicator exists below the page midpoint. Track consecutive
rounds where all of these are true:

```javascript
var grew = check.comments > bestCount;
if (grew) bestCount = check.comments;

check.atBottom === true &&
grew === false &&
check.clicked === false &&
check.loading === false
```

Reset the counter on growth, load-more activation, leaving the bottom, or a
visible loader. Stop with `stop_reason: "stable_bottom"` only when the mode's
existing `staleRounds` threshold is reached; return the actual
`stable_bottom_rounds` in the stats. Backfill's existing threshold is five.
Quick/Full may also report stable-bottom stats, but the backend allowlist gives
terminal authority only to Backfill with rounds >= five.

Forward provider count plus all three scan-evidence fields through both
background save actions, native host, DAL, compatibility stubs, and backend:

```javascript
provider_comments_count: item.provider_comments_count,
comment_scan_mode: scrollMode,
comment_scan_stop_reason: scrollStats.stop_reason,
comment_scan_stable_bottom_rounds: scrollStats.stable_bottom_rounds || 0,
```

In the comment-only loop:

```javascript
if (saveCommentsOnlyResult && saveCommentsOnlyResult.status === "ok") {
  if (saveCommentsOnlyResult.comment_scan_usable === true) {
    commentsRefreshed++;
    netNewComments += saveCommentsOnlyResult.net_new_comments || 0;
  } else {
    failed++;
  }
}
```

Add an `else { failed++; }` for a missing/non-ok native response. The body loop
forwards the same field but retains body success when
`comment_scan_usable === false`; checkpoint and recovery state remain unchanged.

The native host response may expose the reviewed numeric/state diagnostics but
never baseline row IDs, comment IDs, raw provider DOM, or terminal internals
beyond the allowlisted reason. Log overlap rate only as a numeric diagnostic.

Exceptions in the comment-only loop also increment `failed`. Body capture keeps
its independent success semantics; an unusable comment leg cannot roll back or
mislabel a valid body save.

- [ ] **Step 9: Run GREEN, exact accounting, and semantic ratchets**

```bash
pytest -q \
  tests/test_sa_capture_store.py \
  tests/test_sa_capture_backend.py \
  tests/test_sa_tools.py \
  tests/test_sa_article_reconciliation_schema.py \
  tests/test_sa_reconciliation_native_host.py \
  tests/test_sa_extension_article_identity.py \
  tests/test_sa_extension_reconciliation_flow.py \
  tests/test_db_backend_retired_pg_sa.py
pytest --collect-only -q
rg -n 'remote_count\s*-\s*stored_count|remote_count\s*>\s*stored_count|backfill_candidates.*gap' \
  src/tools/data_access.py
rg -n 'comment_recovery_baseline_max_row_id\s*=.*MAX|MAX\(id\).*comment_recovery' \
  src/tools/backends/sa_capture_backend.py
git diff --exit-code 848ffd4 -- apps/arkscope-web config/tickers_core.json
```

Expected: the literal eight-file command above passes exact `182`; the broader
Task 9 focused command passes `262`. Full collection is exact `4513`, semantic delta
`+101/-0` from `848ffd4`; inventory-gap trigger and post-upsert watermark scans
have zero production hit; web app and the protected ticker file remain byte-
identical. Run `git diff --check`.

- [ ] **Step 10: Commit the scheduling/transport half and stop for review**

```bash
git add src/tools/data_access.py src/sa_native_host.py \
  extensions/sa_alpha_picks/scrape_articles_list.js \
  extensions/sa_alpha_picks/background.js tests/test_sa_tools.py \
  tests/test_sa_reconciliation_native_host.py \
  tests/test_sa_extension_article_identity.py \
  tests/test_sa_extension_reconciliation_flow.py \
  docs/superpowers/specs/2026-07-17-alpha-picks-article-reconciliation-design.md \
  docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md
git commit -m "fix: recover bounded Alpha Picks comment gaps"
```

Do not rerun the paid/provider live gate or merge yet. Request independent code
review of the addendum first. After GREEN, recreate the disposable v2 DB copy
from production v1 and perform one normal Quick run plus a second unchanged
Quick run: the first may acknowledge current counts; the second must not rescan
stable historical differences. Separately replay the fixture-backed continuity
sequence on a disposable DB: pre-gap baseline -> Quick zero-overlap pending ->
new-generation-only Full miss remains pending -> second Full miss parks ->
Backfill stable-bottom terminalizes. A naturally changed live provider count is
eligible exactly once. Dynamic counts are evidence, never acceptance constants.

#### Task 8 implementation ledger (2026-07-19)

- Written-review clearance is `7df2c82`. The schema/backend half is `3149623`;
  parser, scheduler, native-host transport, and scroll evidence are `821b2f3`.
- The first RED batch added ten nodes. All ten failed on the reviewed missing
  schema or scan-evidence contracts before implementation. The second RED batch
  added six nodes. They failed on absent zero-vs-unknown provenance, the legacy
  inventory-gap scheduler, missing native evidence forwarding, false refresh
  success, and absent stable-bottom evidence. Both batches are GREEN.
- Exact addendum accounting is `+16/-0`: full collection advanced from the
  locked core baseline `4497` to `4513`. The literal eight-file command printed
  in Task 8 Step 9 collects and passes `182`; its original `262` expectation was
  copied from the broader fourteen-file Task 9 focused command, which passes
  the intended `262`. This command-label correction does not alter node
  accounting. The three adjacent reconciliation/UI files pass `44` in isolation.
- The implementer HEAD full run produced `4408 passed / 31 failed / 74 skipped /
  18 warnings` over `4513` collected nodes. The additional visible failure is
  `test_route_wires_universe_and_db`, whose hard-coded 2026-06-22 date is outside
  its current six-day window on 2026-07-19; the route, owner, and test are byte-
  identical to `848ffd4`. Symmetric virgin canonical A/B remains an independent
  reviewer gate and is not claimed here.
- Compile checks, both JavaScript syntax checks, `git diff --check`, the two
  semantic `rg` ratchets, and byte identity for `apps/arkscope-web` plus
  `config/tickers_core.json` pass. A test-created untracked risk-free-rate cache
  was removed and is not part of the branch.
- No copied production DB, browser profile, native-host config, provider call,
  production schema, or paid live gate was touched during implementation. Those
  gates intentionally follow independent implementation review.

#### Task 9 independent review and pre-merge gate ledger (2026-07-19)

- Independent review GREEN at implementation/docs tip `b321a14`: symmetric
  virgin canonical A/B against `848ffd4` collected exact `4412 -> 4513`, with
  raw node diff `+101/-0`, bidirectionally identical existing failure/error
  identities, and unchanged `30 failed / 74 skipped / 18 warnings / 7 errors`.
  Head passed `4402` after supplying the exact same-lockfile workspace-hoisted
  `jsdom` dependency. Focused execution passed `262/262`.
- Review SF-2 is closed in docs commit `9e4f945`: canonical archives must run
  root `npm ci` or attach an exact same-lockfile root `node_modules`, because 24
  backend-collected extension fixture nodes import workspace-hoisted `jsdom`.
  A virgin archive without that prerequisite is an environment setup failure,
  not a product failure or permitted skip.
- SQLite online backup created separate preview and state-machine copies from
  production schema v1. Preview migration reached schema 2 with
  `integrity_check='ok'`, zero FK violations, and unchanged legacy aggregates
  (`114` picks, `400` articles, `42,794` comments, `2` refresh-meta rows). It
  produced `103` lineages, zero accepted links/decisions, `15` legacy-preview
  rows, and a `166`-event review queue (`103` entry / `63` exit). All 400
  migrated articles were `repaired`; no recovery flag, watermark, park, or
  terminal state was seeded. A second preview was read-only and identical.
- The isolated synthetic copy passed the full public-method transition:
  repaired baseline -> Quick pending -> Full miss one -> Full miss two/parked
  -> nested Quick with frozen watermark -> Quick baseline-overlap repair -> new
  pending -> Backfill timeout -> stable-bottom four pending -> stable-bottom
  five terminal -> unchanged old overlap remains terminal -> future changed-
  count/current-baseline repair with prior terminal audit retained. Native-
  shaped results exposed neither comment IDs nor watermark values.
- The provider gate used a second disposable detached worktree at exact docs
  tip `9e4f945`, an online-backup DB copy migrated to schema 2 before refresh,
  a `0600` ephemeral native-host config/token, a scheduler-disabled sidecar on
  `8423`, and a fresh Chrome profile on CDP `9224`. Native ping identified the
  disposable root and branch sidecar; auto-sync alarms were absent.
- Two preliminary Quick runs were excluded from product acceptance after
  source inspection proved Chrome had retained an old MV3 service worker from
  `18fcfb4`: it lacked `provider_comments_count`, rescanned four articles twice,
  and left their checkpoints stale. This was an environment arbitration, not a
  product-tip result. `chrome.runtime.reload()` was followed by source pins for
  the reviewed `provider_comments_count` and `stable_bottom` code before any
  acceptance run.
- The first valid product-tip Quick completed in `86.8s`, saved the 60 scanned
  article rows, refreshed four comment sets, added zero comments, failed zero,
  and advanced all four checkpoints exactly to current provider counts
  (`929`, `279`, `67`, `69`) in repaired/unparked state. The immediate unchanged
  Quick completed in `18.9s` with `comments_refreshed=0`,
  `net_new_comments=0`, and `failed=0`: stable historical inventory was not
  requeued. Popup/native inspection found no watermark or comment-identity key.
- Cleanup is complete: gate Chrome, sidecar, and native-host children stopped;
  ports `9224` and `8423` refuse connections; temporary token/config, DB/profile
  copies, scripts, and disposable worktree were removed. Formal config SHA-256
  remains `dade42f4740ca011ca4323fbe13a9bbe2f47b6356716b11eed4609bcc2301503`;
  production DB SHA-256 remains
  `811e2908b84badf52b344d51d60373f1a5f2dfb6a28127284afa0de4d3a4c9d4`, at
  schema v1 with integrity OK, zero FK violations, and the same four logical
  aggregates. The implementation worktree is clean and the main checkout still
  contains only the protected user modification to `config/tickers_core.json`.

All pre-merge gates are closed. No further provider replay is required before
user-approved fast-forward merge; production migration remains a distinct
post-merge stopped-service operation.

---

### Task 9: Migration Preview, Full Verification, Live Gate, and Review Handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Section 3.5 is the sole pre-review live-gate addendum. After Task 8 written
  review, do not modify design semantics during implementation; after code
  review, change only status/implementation ledger unless a new stop condition
  returns to design.

**Interfaces:**
- Consumes: Tasks 1-8 complete product stack.
- Produces: copied-DB migration evidence, exact automated accounting,
  no-dual-writer proof, real extension BTSG/current-pick proof, and a
  review-ready branch. No merge occurs in this task.
- Separate live finding retained: pre-fix nonempty disclosure-only body caches
  are still considered populated. Task 8 neither invalidates those rows nor
  claims that issue resolved; Task 9 may not declare final merge-ready until it
  receives an explicit bounded disposition and test/live evidence.

- [ ] **Step 1: Run the exact focused suite and accounting**

```bash
pytest -q \
  tests/test_sa_capture_store.py \
  tests/test_sa_capture_backend.py \
  tests/test_sa_tools.py \
  tests/test_sa_extension_alpha_picks.py \
  tests/test_sa_local_readers.py \
  tests/test_sa_native_host_telemetry.py \
  tests/test_db_backend_retired_pg_sa.py \
  tests/test_sa_article_reconciliation_schema.py \
  tests/test_sa_article_reconciliation.py \
  tests/test_sa_article_reconciliation_backend.py \
  tests/test_sa_reconciliation_native_host.py \
  tests/test_sa_extension_article_identity.py \
  tests/test_sa_extension_reconciliation_flow.py \
  tests/test_sa_extension_reconciliation_ui.py
pytest --collect-only -q
```

Expected: focused `262 passed`; full collection exact `4513`, raw node diff
`+101/-0` from `848ffd4`.

- [ ] **Step 2: Run web-app and protected-boundary gates**

```bash
npm test --workspace apps/arkscope-web -- --run
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
git diff --exit-code 848ffd4 -- apps/arkscope-web config/tickers_core.json
```

Expected: exact `60 files / 572 tests`, typecheck/build PASS except the existing
chunk warning, and byte-identity diff empty.

- [ ] **Step 3: Run single-writer, privacy, and scope ratchets**

```bash
rg -n '_sync_canonical_to_picks|sync_picks' src extensions tests
rg -n 'UPDATE sa_alpha_picks SET.*canonical_article_id|canonical_article_id = \?' src extensions
rg -n 'ticker:\s*item\.symbol|list_ticker:\s*item\.symbol|detail_ticker:\s*item\.symbol|title:.*item\.symbol' extensions/sa_alpha_picks
rg -n 'Today|Yesterday' extensions/sa_alpha_picks/article_identity.js extensions/sa_alpha_picks/scrape_articles_list.js
rg -n 'placeOrder|cancelOrder|modifyOrder|exerciseOptions' src/sa_article_reconciliation*.py
```

Expected: retired writer/argument zero; canonical projection write only in the
reviewed store owner; manual-symbol injection zero; relative-date invention
zero; order API zero. Test fixtures/comments may be excluded explicitly, but a
production hit is a stop condition.

- [ ] **Step 4: Migrate and inspect a copied real DB**

Close no user service for this read/copy step. Use SQLite online backup from
the configured real `sa_capture.db` into `/tmp/arkscope-sa-reconciliation.db`,
then run:

```bash
python -m src.audit.sa_article_reconciliation \
  --db /tmp/arkscope-sa-reconciliation.db --preview-legacy --limit 500
python -m src.audit.sa_article_reconciliation \
  --db /tmp/arkscope-sa-reconciliation.db --queue --limit 500
```

Record dynamic counts, not acceptance constants. Verify:

- copied DB reaches schema `2`, integrity/FK checks pass, and every pick row has
  a lineage;
- RCL-like same `(symbol,picked_date)` rows share lineage while distinct close
  dates remain distinct exit events;
- legacy canonical/detail/body/comment/pick facts are byte-identical except the
  additive lineage column/schema;
- no accepted link was created by migration alone;
- every migrated article has `comment_recovery_state='repaired'`, zero Full
  misses, and null watermark/park/terminal fields; only rows with an existing
  `comments_fetched_at` receive a provider-count checkpoint;
- suspicious distant legacy links appear in preview/review rather than being
  silently accepted;
- a second preview is byte-identical and read-only.

Create a second disposable copy for a state-machine probe; never mutate the
preview copy above. Insert one unmistakably synthetic article/comment baseline,
then execute through the public backend methods:

```text
Quick changed-count/no-overlap -> pending + pre-upsert watermark
Full new-generation-only miss -> pending, miss=1
Full new-generation-only miss -> pending, miss=2, parked
Quick new-generation-only count change -> new comments captured, still parked
Quick frozen-baseline overlap -> repaired despite park
new pending -> Backfill timeout -> pending
Backfill stable_bottom/4 -> pending
Backfill stable_bottom/5 -> unreachable_terminal + retained audit
unchanged-count scan exposing an older row -> still unreachable_terminal
future changed-count/current-baseline overlap -> repaired current epoch,
                                                  prior terminal audit retained
```

Record numeric overlap diagnostics and row counts; assert no comment ID or row
watermark appears in the native-host-shaped response. Delete both `/tmp` copies
after recording aggregate evidence.

- [ ] **Step 5: Run canonical backend A/B from virgin archives**

Create symmetric virgin archives at base `848ffd4` and the final product tip.
Before pytest, run `npm ci` at each archive's repository root (or attach the
exact same-lockfile root `node_modules`). The backend collection includes 24
extension fixture nodes whose harness imports workspace-hoisted `jsdom`; a
virgin archive without root npm dependencies is an environment setup failure,
not a product failure or a permitted skip. Run full `pytest -q` sequentially in
the same environment. Require:

```text
base collect 4412
head collect 4513
raw node diff +101/-0
failure/error identity diff empty in both directions
base 4301 passed -> head 4402 passed, if the known families remain unchanged
74 skipped / 18 warnings / 30 failed / 7 errors unchanged
```

If environment-dependent counts drift, compare node identities and document
the exact family. Do not declare PASS from count equality alone.

- [ ] **Step 6: Run no-PG/import/privacy smoke**

Run the repository's existing no-PG smoke gate and extension native-host ping
against a disposable profile. Require `ok:true`, `pg_attempts:[]`, and no
credential/session values in queue/native responses or logs.

- [ ] **Step 7: Run the real-provider extension gate on an isolated DB copy**

This is a live Seeking Alpha/browser/provider gate, but deliberately not a
pre-merge production-schema migration. Use this exact process boundary:

1. close the desktop app, every master/branch sidecar, every supported browser
   process using the extension profile, and every extant SA native-host child;
   record the PID/port proof before proceeding;
2. make a timestamped SQLite online backup of the configured production v1
   `sa_capture.db` into `/tmp`, then record the source/copy logical aggregates,
   source `user_version`, and backup digest. A filesystem copy of a live WAL DB
   is forbidden;
3. create a second disposable detached worktree at the exact final product tip.
   Do not use the implementation worktree: `_try_ticker_sync()` still writes
   `config/tickers_core.json` relative to the native host's project root, and
   that legacy write must be contained in the disposable checkout;
4. create a `0600` temporary native-host config. Read only the configured
   `python_path` from the normal config; set `project_root` and `host_script` to
   the disposable worktree and set `api_base`/`api_token` to a separately
   launched branch sidecar with a fresh ephemeral token. Never copy, print, or
   log the production token. Launch both the sidecar and a fresh browser
   process with `ARKSCOPE_SA_DB` pointing to the backup copy and the browser
   additionally carrying
   `ARKSCOPE_SA_NATIVE_HOST_CONFIG=<temporary-config>` so its native-host child
   inherits the override;
5. load the unpacked extension from the disposable product-tip worktree.
   Require native-host ping to identify that exact root and branch-sidecar
   target, and separately query the copied DB to require schema `2` before the
   first refresh. Any fallback to the normal config, port, main checkout,
   implementation worktree, or production DB is a stop condition;
6. run two consecutive normal Quick refreshes. Do not paste a `TICKER URL` line
   and do not alter DB rows manually. The first may acknowledge naturally
   changed counts; on the second, a stable count must not reschedule an old
   provider-versus-inventory difference. If a count naturally changes between
   runs, identify that exact article instead of claiming a global zero; and
7. after evidence is recorded, stop the gate browser/sidecar/native host,
   inspect the disposable checkout diff (a generated ticker snapshot is
   allowed only there), remove the temporary config/copy/worktree, and verify
   the normal config digest, production DB `user_version`, production logical
   aggregates, main checkout, and implementation worktree are unchanged.

No v1 process may open the copied v2 database during this window. Because the
production DB remains v1 throughout pre-merge review, a failed gate or failed
implementation review requires cleanup of only the disposable artifacts, not
a risky production restore.

Primary evidence target is BTSG. If BTSG has naturally rolled off the captured
list, use the latest current pick that visibly exposes ticker metadata on both
the listing and detail page; record the substitution and do not claim BTSG
runtime coverage.

Prove:

1. list capture lands an explicit `list_ticker` and detail capture independently
   lands `detail_ticker` when that page exposes it;
2. the extension payload contains no user-injected symbol for those fields;
3. one unique date/role match auto-links and projects entry compatibility only;
4. a conflict/tie/out-of-window or unreviewed phrase remains in the queue;
5. AGX is not asserted or auto-linked merely from `Locking In Additional Gains`;
6. popup default workflow shows event/date/candidate evidence, while Advanced
   stays collapsed;
7. accept/reject affects only one exact event and survives popup/browser restart;
8. a matcher failure simulation on a copied/disposable DB leaves captured
   article/body/comments intact; and
9. a successful pick capture followed by an injected matcher failure remains a
   successful refresh and is not recorded as a provider refresh failure;
10. the repeated Quick run does not chase a stable historical inventory
    difference, while changed-count work remains eligible; and
11. no native-host/popup payload exposes the frozen row-ID watermark or comment
    identities used to prove overlap.

No live gate fetches every historical article. Record normal-cache work and
extra enrichment separately and verify the extra count does not exceed the
mode's cap.

- [ ] **Step 8: Run responsive popup screenshots**

Use Chromium and Firefox extension popups where available. At the native popup
width and a widened DevTools popup, verify long titles/URLs wrap, buttons do not
overlap, Advanced remains collapsed, conflict warnings are readable, and no raw
IDs appear. Inspect screenshots before recording PASS. Do not generate fake
production data; fixture-backed queue interception is acceptable for a conflict
visual if the live queue has none.

- [ ] **Step 9: Reconcile the implementation ledger and commit review-ready docs**

Record every RED failure reason, task commit, exact node delta, copied-DB
aggregates, performance/latency observations, live substitution (if any),
process/port cleanup, and deviations approved during implementation. Change
plan status to `IMPLEMENTED FOR REVIEW`; keep spec status approved, not LIVE.
Update the priority map with product/docs tips and the next review gate.

```bash
git add docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: record Alpha Picks reconciliation implementation gates"
```

- [ ] **Step 10: Stop and request independent implementation review**

Do not merge, mark the spec LIVE, retire the manual Advanced path, begin
DB-universe/JSON retirement, or start a sentiment/Signals implementation. The
reviewer focus is:

1. v1->v2 cross-process transaction and rollback;
2. lineage identity across current/closed/multiple close dates;
3. exact list/detail evidence provenance and conflict handling;
4. deterministic date/role/tie/rejection behavior;
5. capture-before-reconcile failure semantics;
6. single canonical writer and no legacy mutation path;
7. event-scoped replacement/manual confirmation;
8. bounded enrichment versus normal cache work;
9. popup privacy/accessibility and no raw-ID exposure;
10. explicit comment-count provenance, pre-upsert row-ID watermark, and usable-
    scan atomicity;
11. Quick raise/repair, Full two-miss park, Backfill-only five-round terminal,
    terminal TTL exclusion plus unchanged-count stability, terminal re-anchor/
    audit retention, and absence of provider-versus-inventory retry logic; and
12. canonical A/B plus copied-DB/repeated-Quick real extension evidence.

## Post-Review Merge Closeout

After independent GREEN and user merge approval only:

1. fast-forward merge the reviewed branch;
2. re-run focused `262`, merged extension fixture gates, no-PG smoke, and one
   merged-tree popup smoke before touching production state;
3. close the desktop app, all browsers using the extension, all sidecars, and
   every native-host child. Make and retain a timestamped SQLite online backup
   of the real v1 `sa_capture.db`, verify that all launcher/config paths now
   resolve to merged master, and use only merged v2 code to perform the real
   migration. Require `user_version=2`, `integrity_check='ok'`, an empty
   `foreign_key_check`, reviewed logical aggregates, and a successful merged
   native-host ping before restarting normal services. If any check fails,
   stop all merged processes before restoring the recorded backup; never let
   v1 code reopen a production v2 DB;
4. change spec to `IMPLEMENTED / LIVE` and plan to `LIVE COMPLETE` with merge,
   production-migration, and live evidence;
5. update the priority map/memory, including the separately deferred
   per-(ticker,time) evidence-strength/stance Signals design discussion without
   reviving per-article scoring;
6. reload the installed extension and restart the desktop app only after the
   migration checks pass;
7. remove the implementation worktree after verifying it contains no untracked
   evidence; and
8. return to the reviewed sequence. DB-universe/`tickers_core.json` retirement
   remains a separate slice, and the Advanced URL escape hatch remains until
   observed automatic coverage justifies a later removal decision.

### Post-review merged production closeout ledger (2026-07-19)

- User-approved fast-forward integration moved `master` to reviewed docs tip
  `bf378f1`; no product bytes changed after reviewed product tip `821b2f3`.
- Before touching production, merged-tree verification passed focused `262`,
  dedicated extension fixtures `24`, and no-PG smoke with `ok:true` and
  `pg_attempts:[]`. The isolated merged popup displayed `166` review events,
  kept Advanced collapsed, exposed no lineage/link/comment/watermark identity,
  and used only a disposable online-backup copy.
- All app/browser/sidecar/native-host processes were stopped. This also found
  and terminated stale PID `2289588`, whose cwd and data paths both belonged to
  a deleted 2026-07-18 disposable gate. The reviewed old `/tmp` DB copies,
  WAL/SHM shells, native-host configs, and queue-evidence JSON were removed.
- The retained mode-0600 production backup is
  `data/backups/sa_capture-v1-pre-alpha-reconciliation-20260719T025246Z.db`.
  It is schema v1, integrity/FK clean, and contains the exact pre-migration
  aggregates: `114` picks, `400` articles, `42,794` comments, and `2` refresh
  metadata rows.
- Only merged code opened the stopped production DB. Independent read-only
  verification reports `user_version=2`, `integrity_check=ok`, zero FK errors,
  `103` lineages, zero picks without lineage, zero accepted links/decisions,
  all `400` articles seeded `repaired` with checkpoints, and zero non-default
  recovery rows. Multiset digests for every pre-existing table matched the v1
  backup exactly.
- The merged desktop app restarted on Vite `8430` with sidecar `41017`; health
  and the installed native-host framed ping both returned `ok` and identified
  `/mnt/md0/PycharmProjects/ArkScope` as the project root. Chrome Profile 1's
  installed unpacked extension path resolves to the same merged-main tree.
  The user's unrelated `config/tickers_core.json` edit remained unstaged and
  byte-untouched throughout.
