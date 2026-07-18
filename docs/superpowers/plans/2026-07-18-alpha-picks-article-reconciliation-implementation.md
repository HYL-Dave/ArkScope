# Alpha Picks Article Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to execute this plan task by task. Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:test-driven-development` for every behavior change, and
> `superpowers:verification-before-completion` before review-ready claims.
> Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** REVIEWED / CLEARED FOR IMPLEMENTATION. Round 2 confirmed the
> bounded MF-A revision, exact `+78/-0` accounting, and disposable live-gate
> boundary. Task 0 must branch from the dedicated clearance commit containing
> this status, not from behavior base `848ffd4`.

**Goal:** Automatically preserve Alpha Picks list/detail ticker evidence and
associate entry and exit events with the correct bounded-date article, while
keeping ambiguous cases reviewable and demoting raw URL paste to an
event-scoped Advanced escape hatch.

**Architecture:** Schema v2 separates lifecycle-stable pick lineages from
captured current/closed rows, and stores accepted article relationships plus
rejection history independently from the legacy compatibility projection. A
pure deterministic matcher owns date bands, role phrases, ticker provenance,
tie handling, and URL validation; a focused SQLite persistence module owns
lineage/event queries, atomic link replacement, projection, and the derived
review queue. The browser extension captures explicit list/detail ticker facts,
commits article data before a separate bounded reconciliation pass, and renders
the review queue in its popup. The two legacy nearest/same-ticker writers retire
in the same product change, so no dual-writer window exists.

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
  backfill, provider evidence columns, link/decision constraints.
- `src/tools/backends/sa_capture_backend.py` - resolve lineage during pick
  refresh, persist source-specific article metadata, delegate reconciliation,
  and remove both legacy mutation paths.
- `src/tools/backends/db_backend.py` - retired-PG compatibility stubs for the
  new DAL method surface; no PG access.
- `src/tools/data_access.py` - capture-first pick/article/body orchestration,
  scan-scoped normal cache work, and additive reconciliation/review DTOs.
- `src/sa_native_host.py` - additive queue/event-resolve/accept/reject actions,
  post-pick-capture reconciliation, detail ticker propagation, and read-only
  compatibility audit action.
- `extensions/sa_alpha_picks/scrape_articles_list.js` - explicit list ticker
  capture with the confirmed optional-time grammar.
- `extensions/sa_alpha_picks/scrape_detail.js` - independent security-header
  ticker capture.
- `extensions/sa_alpha_picks/background.js` - ordered helper injection,
  bounded enrichment, event-scoped manual flow, and review actions.
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

### Task 8: Migration Preview, Full Verification, Live Gate, and Review Handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-07-18-alpha-picks-article-reconciliation-implementation.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Do not modify the approved spec until implementation review; then change only
  its status/implementation ledger.

**Interfaces:**
- Consumes: Tasks 1-7 complete product stack.
- Produces: copied-DB migration evidence, exact automated accounting,
  no-dual-writer proof, real extension BTSG/current-pick proof, and a
  review-ready branch. No merge occurs in this task.

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

Expected: focused `239 passed`; full collection exact `4490`, raw node diff
`+78/-0` from `848ffd4`.

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
- suspicious distant legacy links appear in preview/review rather than being
  silently accepted;
- a second preview is byte-identical and read-only.

Delete only the `/tmp` copy after recording aggregate evidence.

- [ ] **Step 5: Run canonical backend A/B from virgin archives**

Create symmetric virgin archives at base `848ffd4` and the final product tip.
Run full `pytest -q` sequentially in the same environment. Require:

```text
base collect 4412
head collect 4490
raw node diff +78/-0
failure/error identity diff empty in both directions
base 4301 passed -> head 4379 passed, if the known families remain unchanged
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
6. run one normal Alpha Picks refresh. Do not paste a `TICKER URL` line and do
   not alter DB rows manually; and
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
   successful refresh and is not recorded as a provider refresh failure.

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
9. popup privacy/accessibility and no raw-ID exposure; and
10. canonical A/B plus real extension evidence.

## Post-Review Merge Closeout

After independent GREEN and user merge approval only:

1. fast-forward merge the reviewed branch;
2. re-run focused `239`, merged extension fixture gates, no-PG smoke, and one
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
