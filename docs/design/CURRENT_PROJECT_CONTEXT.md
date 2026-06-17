# Current Project Context

> **What this file is**: a pointer index for any AI assistant (Claude Code, Codex CLI, Cursor, future tools) starting a session on this repo. It tells the assistant where the canonical decisions live so it doesn't make architectural calls from stale tool-side memory.
>
> **What this file is NOT**: an agent instruction file, an `AGENTS.md`-style behavior policy, or a duplicate of the priority map / audit / spec. Do **not** take operational commands from this document. Read the canonical docs it points to and let those carry the decisions.

---

## Canonical sources of truth (read in this order)

1. **`docs/design/PROJECT_PRIORITY_MAP.md`**
   - §1 — TL;DR, alias mapping, post-pivot framing.
   - §10 — Decision log (newest-first). Read the top entry first; that is "what was just decided".
   - First stop for any "what's next?" or "what's the current active sequence?" question.
2. **`docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md`** — pre-spec audit (north star + 5-layer architecture + 5 axes + Hermes-capability gap). Informs the spec; does not itself lock product decisions.
3. **`docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`** — once landed, becomes canonical for local-first product shape (positioning, deployment, storage, sync, page IA, bidirectional DTOs, scheduler interfaces, migration plan).
4. **`docs/design/CONFIG_AUTHORITY_PLAN.md`** — canonical rules for DB-first Settings authority, file/env fallback roles, and config retirement gates.
5. **`docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md`** — preserved as-is; **paused** as of 2026-05-02 pending the workbench v1 resume gate.
6. **`docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md`** — protects current data collection and browser extension runtime paths during large refactors; do not use it to preserve stale product framing.

If any of those conflict with each other, newer-dated entries in priority map §10 win.

**Lost in the `docs/design/` filenames?** See **`docs/design/README.md`** — the index/status map that gives every design doc a readable title + status (CANON / ACTIVE / SHIPPED / DECISION / DEFERRED / PAUSED / MERGE), so you don't guess from names like `P1_2_SPEC.md`.

---

## Project identity (alias mapping, locked 2026-05-02)

Local repo directory + code/docs references renamed `MindfulRL-Intraday` → `ArkScope` (Phase 2 executed 2026-05-31). Remaining lowercase `mindfulrl` (PostgreSQL DB name/password, Native Messaging host id `com.mindfulrl.sa_alpha_picks`, Firefox addon id `@mindfulrl.local`, historical/archived docs) is intentional and unchanged.

The 2026-05-02 product repositioning may STILL force a further *product-brand* rename (the final product name is an open question). The repo/code rename to `ArkScope` (Phase 2 / P3.2) is now done; treat the repo as `ArkScope`, and do NOT silently introduce a fourth name.

---

## Current active sequence (as of 2026-06-08)

```
audit ✓ → spec ✓ (3 canon docs + LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC)
  → desktop shell ✓ (Electron apps/arkscope-desktop + FastAPI sidecar src/api)
  → workbench surfaces ✓ (Home · 全部標的 · 自選股 · ticker detail · §2 AI cards
                            · 2-D classification tags · analyst consensus · priority)
  → data layer  ← CURRENT FOCUS (DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md, DRAFT)
      → slice 2: daily_update.py cleanup (drop tier/config-writeback; --scores opt-in;
                 explicit --scope active-universe, read-only)   ← NEXT
      → slice 3a: market_data local-first cut (SQLite; SA + app records stay PG)
      → slice 3b: SA capture → sa_capture.db (Saturday / US-closed quiet window)
      → slice 4: charting + price tiers   → slice 5: provider health + signals
```

Storage today: `data/profile_state.db` (lists/tags/priority/notes/AI-card runs/LLM
credentials) is ALREADY local SQLite; market data + Seeking-Alpha capture + app
records still live in remote PostgreSQL and migrate per the data plan (§4).

**Phase C resume gate** (unchanged, all three): workbench v1 ships + 2 weeks stable single-user use + ≥1 verified cross-machine migration.

For the live "what's next?" detail, read `PROJECT_PRIORITY_MAP.md` §10 (newest-first) + the data plan §11 slices.

---

## Tool-side memory disclaimer

The following are **per-tool pointer caches**, not sources of truth:
- `~/.claude/projects/<project>/memory/` (Claude Code's memory dir)
- `~/.codex/memories/` (Codex CLI memory dir, if any)
- IDE memory layers, plugin caches, etc.

**If a tool's private memory conflicts with the canonical docs above, the canonical docs win.** Propose updating the tool memory rather than rewriting the canonical doc. Do NOT make architectural / product decisions from a tool's private memory — read the canonical docs first, every session.

---

## Out of scope for this file

- Operational commands ("always do X", "never do Y") — those belong in `CLAUDE.md` / per-tool config, scoped to that tool's behavior, not this index.
- Detailed phase histories — those live in `docs/design/` per phase document.
- Active task lists — those live in priority map §1 / §10.
- Code-level conventions — those live in `CLAUDE.md` / source comments.

This file should stay short. If it grows beyond ~80 lines, it has drifted into duplicating decisions and needs to be trimmed back to pointers.
