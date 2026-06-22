# Config Authority Plan — DB-first settings, file fallback, retirement gates

**Status:** ACTIVE decision record. This is the cross-cutting authority for
where ArkScope configuration should live and when file/env-backed settings can
be retired. Feature-specific plans still own their implementation details; this
doc owns the source-of-truth rules.

**Related docs:**

- `CREDENTIAL_MANAGEMENT_PLAN.md` implements these rules for LLM credentials,
  OAuth tokens, `.env` import/export, and active key selection.
- `LLM_AUTH_DRIVER_PLAN.md` owns provider/auth-mode driver architecture.
- `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` and `LOCAL_STORAGE_TOPOLOGY.md`
  own data-storage topology. This doc only decides configuration authority, not
  storage topology.

---

## 1. Decision

ArkScope should move toward **DB-first app settings**, not "no config files".

The rule:

> Any setting a normal user should change inside the app must eventually be
> stored, displayed, validated, and switched through Settings/profile DB. File
> and env config remain only for bootstrap, dev/CI, emergency fallback, and
> explicit import/export.

The product meaning of "config" is therefore:

> Config files are **transfer artifacts**. They are produced by export so a user
> can back up, inspect, move, or reinstall ArkScope, and consumed by import so DB
> / Settings can take over again. They are not the normal live authority for
> mutable app behavior after import.

This avoids the current split-brain pattern where `.env`, `user_profile.yaml`,
local DB rows, and Settings can each appear to own the same behavior.

---

## 2. Authority Classes

| Class | Authority | Examples | File/env role |
|---|---|---|---|
| User-facing runtime settings | DB / Settings | active LLM credential, model route, AI Research effort, data-source enablement, schedule toggles | transfer artifact + fallback until migration is complete |
| Secrets and OAuth tokens | Credential DB + token-store | API keys, Claude setup-token, future ChatGPT OAuth token | bootstrap/import only; API keys may export for portability; OAuth tokens should not be plaintext-exported by default |
| Source catalogs reviewed in PR | Files | curated macro series, fixed sector/event taxonomies, checked-in model catalog seeds | primary source, because reviewability matters |
| Local bootstrap and rescue | Files/env | profile DB path, emergency disable flags, dev ports, CI overrides | remains valid permanently |
| Generated or user data | Local DBs/files by domain | captured SA data, research threads, caches, local market DBs | not covered by this doc except where config points to them |

The important distinction: **configuration that changes product behavior for a
user should be visible and editable in the product**. Static catalogs and rescue
flags are allowed to stay file-backed.

Exported config should round-trip back into the DB where possible. Import should
not leave shadow settings that silently keep influencing runtime after the DB
setting exists; if a fallback remains, it must be labeled as fallback in UI/logs.

---

## 3. Retirement Gate

A file/env setting may be retired only after all gates pass:

1. **DB schema exists** for the setting, with migrations and idempotent upgrades.
2. **Settings UI exists** to view and edit it, including current effective value.
3. **Runtime reads DB first** and logs or displays an explicit fallback if it uses
   file/env.
4. **Import path exists** from the old file/env shape into DB.
5. **Export/backup path exists** if portability matters.
6. **Tests cover** migration, fallback, effective-value resolution, and no-secret
   response behavior where secrets are involved.
7. **User-facing state is understandable**: no hidden duplicate rows, positional
   `[0]`/`[1]` labels, or "active" flags that do not affect runtime.
8. **Rollback story is explicit** for at least one release/slice: fallback remains
   available or a backup is created before destructive cleanup.

Until these gates pass, the file/env value is not "wrong"; it is a fallback or
legacy authority that must be labeled honestly.

---

## 4. Current Authority Map

### LLM Credentials

**Target:** DB/token-store authoritative, `.env` fallback/import/export.

Current status:

- OpenAI API keys: DB rows are imported/named; active DB key is wired into live
  OpenAI client construction.
- Anthropic API key: DB row exists. Claude `claude_code_oauth` (subscription)
  Research is **live-validated** (Slice 7B Research-stream consumer, commits
  `5f0ea35`→`9131f7f`) — NOT env fallback. The sync `live_anthropic_client`
  accessor intentionally stays fail-closed for OAuth-active; the live path is the
  C-2 Research `stream_llm` consumer (see `SLICE_7B3_SDK_DRIVER_DESIGN.md` §8).
- Claude setup-token: token-store import/probe works; subscription Research is live.
- `.env`: no longer the intended day-to-day switch surface, but still fallback
  and portability format.

Next gate:

- AI Research model-route UI: DONE (Slice B1 backend + B2 full-stack — `ai_research`
  is in TaskId/TASKS/`/config/runtime`/`/config/model-catalog`, Settings → Models
  renders+saves it, and the Research header + send-area chip show the resolved
  route). Slice 6 cheap live test: ✅ DONE 2026-06-19 (live `run_query_stream`
  calls — DB-only OpenAI key resolved + answered on HTTP transport; OpenAI
  switch affected the live run; Anthropic Claude-OAuth → explicit env fallback
  note). Live credential routing confirmed.
- DONE (Slice 7B): `claude_code_oauth` runs Research through the subscription path
  (live-validated), not env fallback. The remaining OAuth-execution gap is OpenAI
  `chatgpt_oauth` — login/token/probe/discovery are built but EXECUTION is
  fail-closed (`live_resolver.py`) pending the P1/P2 backend probe.

### Model Routing

**Target:** Settings/DB authoritative for task routes; built-in defaults are only
seeds.

Current status:

- Card task routes exist.
- `ai_research` backend route exists, but the Settings/UI surface is not complete
  until B2.
- Built-in default/advanced tiers are fixed seeds; ArkScope should not silently
  auto-select "latest" at runtime.

Next gate:

- B2 (expose `AI 研究` in Settings model routing + show the active route in
  Research): **DONE**. Next: migrate the per-task routes (`{ai_research,
  card_synthesis,card_translation}_{provider,model,effort}`) from
  `user_profile.local.yaml` to **profile-DB authority** (the active slice — §6.6),
  yaml/env demoted to fallback + import/export. Mirror the env-bridge precedence in
  `data_provider_config.py` (`real env var > app-stored DB value > config file`).

### Scoring / Per-Purpose Credentials

**Target:** purpose-specific credential bindings.

Current status:

- `config/scoring_keys.txt` is a gitignored bridge for the scorer's rotation pool.
- It is intentionally outside the main "one active provider credential" model
  until per-purpose binding is designed.

Next gate:

- Add purpose binding after Settings + live-loop credential routing are stable:
  `research`, `scoring`, `summary`, `filtering`, `data_extraction`, etc. The same
  credential may be bound to multiple purposes.

### Data-Source Keys and Schedules

**Target:** Settings/token-store authoritative for user-managed data-source keys,
source enablement, and schedules.

Current status:

- Many provider keys still live in `.env`.
- Some schedules and enablement flags are still file/config driven.
- This is acceptable until the LLM credential path proves the DB-first pattern.

Next gate:

- Run a data-source config audit after the LLM config authority work stabilizes.
- Move keys and schedules incrementally, source by source, with the same
  retirement gate.

### Local Storage and PG Retirement

**Target:** runtime storage selection should be DB/local-first, with PG fallback
only where explicitly retained.

Current status:

- SA capture has completed the hard cutover to SQLite.
- Broader PG retirement is tracked in storage docs, not here.

Next gate:

- Use this doc's authority rules for config flags and migration switches, while
  storage topology remains governed by `LOCAL_STORAGE_TOPOLOGY.md`.

---

## 5. What Must Stay File/Env-Backed

Some settings should not be forced into DB:

- Path to the profile DB or workspace-local state root.
- Dev server ports and local development overrides.
- CI-only overrides.
- Emergency kill switches that must work even if DB open/migration fails.
- Checked-in static catalogs where PR review is the real control mechanism.
- One-shot apply gates for dangerous migrations, such as temporary environment
  variables that must not persist.

These are not technical debt. They are bootstrap and rescue controls.

---

## 6. Sequencing

> **Status reconciliation (2026-06-22):** Steps 1–4 are DONE — B1 drift fixed, B2
> model-route UI shipped, Slice 6 live verification ✅ (2026-06-19), and Claude
> `claude_code_oauth` subscription Research is **live-validated** (Slice 7B). The
> remaining OAuth-execution gap is **OpenAI `chatgpt_oauth`**: login/token/probe/
> discovery are built but EXECUTION is **fail-closed** (`live_resolver.py`) pending
> the P1/P2 backend probe. **The active config-authority slice is step 6 reframed:**
> migrate the per-task model routes to profile-DB authority — NOT a fresh framework
> audit (§2/§3/§5 already specify the framework; the per-setting classes are known).

1. **Fix B1 drift**: update stale tests and persist resolved model on stream
   error turns.
2. **B2 model-route UI**: expose `AI 研究` in Settings and show the active route
   in Research.
3. **Slice 6 live verification**: confirm DB-selected OpenAI key affects live
   Research and Anthropic fallback is explicit.
4. **Slice 7 Claude OAuth Research driver**: make `claude_code_oauth` an actual
   Research runtime, not only a Settings/probe row.
5. **AI Research run lifecycle**: follow `AI_RESEARCH_RUN_LIFECYCLE_PLAN.md` so
   Settings owns the default AI Research route while the Research surface can
   make explicit per-run model/effort overrides.
6. **LLM config authority audit**: list every remaining LLM/model/profile/env
   setting and classify it by §2.
7. **LLM file-retirement pass**: retire or relabel legacy `.env`/YAML fields only
   after §3 gates pass.
8. **Data-source config audit**: repeat the same process for provider keys,
   schedules, source enablement, and alert settings.

---

## 7. Rules for Future Features

New features should declare their config authority at design time:

- Is this a user-facing setting? If yes, design the Settings/DB path from day one.
- Is this a secret? If yes, avoid plaintext export unless explicitly chosen.
- Is this a reviewed static catalog? If yes, a file may be the correct authority.
- Is this an emergency or bootstrap flag? If yes, file/env can remain primary.
- Does runtime fallback exist? If yes, the UI/logs must say it is fallback, not
  silently pretend DB is active.

The goal is not fewer files. The goal is **one honest authority per behavior**.
