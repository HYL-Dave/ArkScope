# Repo Hygiene B4/B5 — Docker Archive-Only + Docs Deep Sweep Implementation Plan

> **Status: REVIEWED — cleared for B4a/B4b/B5a; B5b gated on the disposition-table
> approval checkpoint.** 2026-07-06 review folded in: MF1 `config/.env.template` secret
> purge added to Task 1; MF2 root `README.md` "current stack" quickstart added to Task 1;
> MF3 internal IP generalized to `<archive-pg-host>` per publication policy; SF decision-log
> acceptance reworded append-only; SF audit §1 stale registry row superseded-noted.
> B1–B3 already executed directly (`ff538b4`/`17bcf00`/`1c076bf`; deletion record in
> `REPO_HYGIENE_AUDIT_2026_07.md` §8).
> Authority: that audit's §7 answered rulings + §4 docs classification;
> governance = `REFACTOR_PROTECTION_SMOKE_GATES.md` + the ⑤-era 4-col-table method.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use
> checkbox syntax. B5 Task 1 ends at an APPROVAL CHECKPOINT — do not delete any doc
> before the owner approves the disposition table.

**Goal:** (B4) docker becomes an explicitly archive-access-only tool with **no secret in
the repo** and the compromised password rotated; (B5) docs get the owner-ruled deeper
sweep — every design doc carries an explicit tier verdict, completed HOW is
folded-then-deleted, and nothing misleading survives.

**Non-goals:** no runtime code changes anywhere; no config/ deletions (db-ification is a
separate future migration); decision-log entries are never edited or deleted; `sql/`
stays (schema lineage).

## Decisions Locked (from the 2026-07-06 rulings)

1. **Docker = archive-access-only.** Not a dev quickstart (app runtime has zero PG). The
   only consumer is `data/pg_archive/*` restore/inspection.
2. **No secret in the repo, ever.** Compose stops hardcoding the password:
   `POSTGRES_PASSWORD: ${ARKSCOPE_ARCHIVE_PG_PASSWORD:?set in your environment}` — no
   default value. The new password is never written to any tracked file; agents never
   generate or type it — **rotation is user-executed** with prepared commands.
3. **Docs 4-tier rule**: keep+update canonical / fold-summary-then-delete completed HOW /
   status-header big-migration evidence / decision log untouchable.
4. **Fold-then-delete is verified per file** (NewsExtraction ③ discipline): each deletion
   names where the residual value now lives; uncertain absorption → defer to KEEP.
5. **Live-law relocation before disposal**: sections of "completed" docs that are current
   law move to a canonical home first — named cases: `PG_EXIT_REMAINDER_SCOPING.md` §5
   survivor table (scripts rule authority), `SA_CUTOVER_3D_RUNBOOK.md` native-host
   write-path detail (→ boundary doc or provider catalog §3.9).
6. **Link integrity**: after every deletion batch, grep the deleted filenames repo-wide
   and fix dangling references (`f652ea1` precedent). git-crypt caveat: `docs/design/**`
   diffs show as binary — review with `git diff --text`.

## Stop-Loss

- Absorption unclear for a doc → KEEP with a status header; never delete on uncertainty.
- Any step that would edit a §10 decision-log entry → STOP (append-only law).
- Rotation verification fails (archive DB unreachable with new credential) → STOP, do not
  disable the old credential path until read-back works.

## Task 1 (B4a): compose de-hardcode + README repurpose + secret purge

**Files:** `docker/docker-compose.yml`, `docker/README.md`, **`config/.env.template`**
(MF1: lines 150+152 still carried the compromised dev password), **root `README.md`** (MF2: `:39`
still frames docker as "current stack" quickstart), `docs/PUBLICATION_REVIEW.md`
(status note only).

- [ ] **Step 1:** compose: password → `${ARKSCOPE_ARCHIVE_PG_PASSWORD:?...}` (no default);
  container/network names unchanged (archive restore parity). Gate:
  `docker compose -f docker/docker-compose.yml config` parses with a dummy env value and
  FAILS with the `:?` message when unset (both asserted).
- [ ] **Step 2:** `config/.env.template`: replace the two compromised-dev-password lines with
  a COMMENTED archive-only example using placeholders only —
  `# DATABASE_URL=postgresql://postgres:<archive-pg-password>@<archive-pg-host>:15432/mindfulrl`
  — plus one line stating the app runtime needs no PG.
- [ ] **Step 3:** root `README.md`: drop the "# 2. database (current stack)" quickstart
  step (renumber); PG/docker mention moves to a one-liner pointing at `docker/README.md`
  for archive access only.
- [ ] **Step 4:** `docker/README.md` rewrite: "the app does NOT need docker; this compose
  exists only to restore/inspect `data/pg_archive/*` dumps" + minimal restore/inspect
  recipe (mirror the n9 gate CLIs' two-stage restore-proof pattern) + rotation pointer.
- [ ] **Step 5:** Gate: repo-wide grep for the old dev-password string = ZERO tracked hits (string deliberately not repeated here; it lives only in git history);
  repo-wide grep shows no doc presenting docker as runtime/dev quickstart. Commit
  `chore: repurpose docker to archive-access-only (B4a)`.

## Task 2 (B4b): password rotation — USER-EXECUTED, approval-gated

- [ ] **Step 1:** prepare (do not run) the exact user steps: `ALTER USER ... PASSWORD` on
  the remote container at `<archive-pg-host>` (real host lives in the user's private
  operational context + `config/.env`, never in tracked docs — publication policy), update
  `config/.env` `DATABASE_URL`, update the MCP postgres server config, export
  `ARKSCOPE_ARCHIVE_PG_PASSWORD` where compose is used. Agents never see/choose the new
  value.
- [ ] **Step 2 (user):** execute rotation.
- [ ] **Step 3 (verify):** read-only connectivity check to the archive DB with the new
  credential (e.g., `SELECT count(*) FROM agent_queries` via MCP) succeeds; old password
  refused; `PUBLICATION_REVIEW.md` compromised-password item flipped to ROTATED with
  date. Commit `docs: record archive PG rotation (B4b)`.

## Task 3 (B5a): docs disposition table — then STOP for approval

**Scope:** all tracked `docs/**` (60 design + 9 data + top-level guides + features/
history/notes/analysis/figures) + `docs/superpowers/plans/*` (expected verdict: keep as
completed-record; confirm headers). Method: ⑤-era 4-col table per file —
`file / verdict (keep-current | keep-record+header | fold-then-delete | relocate-then-delete) /
why / absorption-or-inbound-link evidence` (inbound links via repo-wide grep of the
filename, NOT just intuition).

- [ ] **Step 1:** produce the table (append as audit doc §9 or a standalone
  `DOCS_SWEEP_DISPOSITION_2026_07.md`). Uncapped inventory — no head/tail. The table also
  inventories **publication-policy violations** (internal IPs/hosts per
  `PUBLICATION_REVIEW.md`) — two known pre-existing `192.168.0.153` instances in older
  plan docs (`2026-06-28-news-normalization…:1297`, `2026-07-04-data-sources…:451`) get a
  generalize-or-keep verdict alongside the tier verdict.
- [ ] **Step 2: APPROVAL CHECKPOINT.** Owner reviews/edits verdicts. No deletion before
  approval.

## Task 4 (B5b): execute the approved table in small commits

- [ ] **Step 1:** relocations first (live-law sections → canonical homes; each commit
  names source§ → destination§).
- [ ] **Step 2:** status-header batch (completed records gain/verify a one-line header).
- [ ] **Step 3:** fold-then-delete batch(es) — each deleted file's commit line records the
  absorption target; after each batch run the dangling-link grep and fix hits.
- [ ] **Step 4:** canonical stale-copy fixes surfaced by the sweep (e.g., docs still
  teaching `scripts/collection` paths, PG-first flows, `use_local_*` toggles).
- [ ] **Step 5:** closeout — audit doc status flip, map §10 entry, user-facing-content
  list (「使用者該知道但埋在內部文件」) handed to P2.5, memory sync.

## Review Gates

- Gate 1 (after Task 1): compose config parse both ways; grep zero runtime-quickstart
  framing.
- Gate 2 (after Task 2): live read-back with new credential; old credential refused.
- Gate 3 (after each B5b batch): dangling-link grep = zero; `git diff --text` reviewed.
- No pytest/A-B needed anywhere: zero runtime code in scope (if any step wants to touch
  `src/`/`tests/`, it is out of scope — stop and re-plan).

## Acceptance Criteria

- Repo contains no PG secret; compose fails loudly without the env var; README says the
  app needs no docker.
- Rotation live-verified; PUBLICATION_REVIEW item closed.
- Every tracked doc has an explicit tier verdict; approved deletions executed with named
  absorption targets; zero dangling links; **existing decision-log entries byte-identical
  (new closeout entries are allowed — append-only)**.
- P2.5 receives the user-facing-content list as input.
