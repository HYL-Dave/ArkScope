# Credential Management Plan — file-vs-DB, manual switch, export/import

**Status:** DESIGN (awaiting user approval before Slices 3–6). Slices 0–1 +
Supabase hygiene already landed (see §9). Companion to
`LLM_AUTH_DRIVER_PLAN.md` (the driver/auth-mode matrix); this doc covers *where
credentials live*, *how the user switches them*, and *the `.env` round-trip*.

**Config-authority scope:** this doc is the LLM credential implementation plan.
The cross-cutting rules for DB-first Settings, file/env fallback, and retirement
gates live in `CONFIG_AUTHORITY_PLAN.md`; this plan should follow that authority
when deciding whether `.env`, DB, token-store, or Settings owns a behavior.

**Origin:** user wants ≥2 independent keys per provider (multiple accounts, each
with a daily free-tier limit) with **manual switching** (key↔key AND key↔OAuth),
and asked whether credential deps should keep living in the `.env` *file* or move
to the *DB*, while preserving **export→`.env` / import←`.env`** for portability.
Derived from a 3-approach design panel + adversarial review (verdict
`needs-revision`; all must-fixes folded in below).

---

## 1. Decision: Approach 3 (Hybrid), corrected

**DB is authoritative for SELECTION (which credential is active) + holds api_key
secrets; the token-store holds OAuth tokens; `.env` is a supported
import/export format AND a day-one fallback; the live loop **will** resolve the
active credential through the `AuthDriver` (the S5/Slice-6 wire-in — NOT yet
wired; today the live agents still read keys from `os.environ`).**

Chosen over the alternatives **against the code as-built**:

- It matches what already exists: `_resolve_api_credential` (`model_credentials.py:559`)
  is **already** DB-row-first → env-fallback, and `api_key_drivers._resolve_secret`
  already calls it. "DB-authoritative selection, `.env` as live fallback +
  portability port" is the as-built contract — not net-new.
- **Reject Approach 1** (TOML as source of truth): introduces a *third* secret
  store + fussy format-preserving write-back on every set-active, and contradicts
  the "DB holds selection" framing. Salvage only its **alias ergonomics** (below).
- **Reject Approach 2** (DB-canonical, `.env` demoted to port-only): drops the
  shipped set-if-absent env fallback, so an empty DB would break today's behavior.
  Approach 3 keeps the fallback → day-one nothing breaks. Borrow its export
  varname scheme.

**Honest residual posture:** api_key secrets stay **plaintext-at-rest** in
`llm_credentials.secret` (DB `0o600`) — same exposure class as today's `.env`,
NOT a hardening win. Only OAuth gets keyring-first (token-store). Moving api_key
secrets onto the keyring is a deliberate **later** pass (open question §10).

---

## 2. What each store holds

| Store | Holds | Notes |
|---|---|---|
| `llm_credentials` (SQLite `profile_state.db`) | api_key metadata **+ secret**, `active` flag, alias | single-active-per-provider invariant already enforced (`model_credentials.py:353`); `0o600` |
| token-store (keyring → plaintext `0o600` dev fallback) | OAuth / setup tokens | `add_oauth_credential` inserts `secret=NULL`; token NEVER in `llm_credentials.secret` (guarded at `:322`/`:344`) |
| `config/.env` | import source + export target + **fallback** for api_key | data-source keys (FINNHUB/POLYGON/…) stay here untouched, out of the credential model |

---

## 3. Live-loop resolution — the S5 crux (corrected)

One new resolver: `resolve_active_driver(provider) -> AuthDriver` =
`ensure_env_loaded()` → read the active `llm_credentials` row for the provider →
`build_driver(provider, auth_mode=row.auth_type, credential=row, token_store=…)`.
The driver owns the secret; **loop bodies, `AgentEvent` vocab, and `query.py`
persistence are untouched.** Wire-in touches ONLY client construction.

**Do NOT mutate `os.environ`** (that's the implicitness we're removing, and a
process-global can't express "this construction uses account B").

- **Anthropic — pass `api_key=` to a SYNC client.** The live sites are
  **synchronous** (`Anthropic()` → `client.messages.stream`/`.beta.messages.stream`,
  `client.messages.create`). ⚠️ **Mandatory amendment:** the S2 driver currently
  returns `AsyncAnthropic` (`api_key_drivers.py:135`) — wrong for these sites. Add
  a **`client_sync()`** accessor that builds `Anthropic(api_key=<resolved>)`.
  **There are 7 live bare `Anthropic()` sites** to swap (review-corrected count):
  `agent.py:215`, `cli.py:611`, `subagent.py:406`, `summary_callers.py:96`,
  `card_synthesis.py:145` & `:463`, `code_generator.py:160`.
  **EXCLUDE `model_credentials.py:722`** — it already injects `api_key=` and is a
  *dependency of the resolver* (swapping it would be circular).
  For `claude_code_oauth`, `client_sync()` cannot return an `Anthropic()` at all
  (probe P3b proves the token is rejected as `x-api-key`) — the call site
  **branches on `driver.auth_mode`**: `api_key` → in-process sync SDK; OAuth →
  `driver.stream_llm()` via `claude -p`/Agent SDK (generalize
  `code_generator._call_claude_cli`), yielding the SAME `AgentEvent` vocab.

- **OpenAI — register the driver's client as the SDK default.** The Agents-SDK
  `Runner` takes no client arg; the only injection point is the SDK global.
  ✅ **Review correction:** `set_default_openai_client` / `set_default_openai_key`
  **already exist** in the installed SDK — S5 just *calls* the existing setter,
  it does not author it. Use `set_default_openai_client(resolve_active_driver('openai').client())`
  (a *client*, not a key, so a future `chatgpt_oauth` driver can swap `base_url`).
  **Set per-run, immediately before `Runner.run`** — it's a process-global; an
  in-flight `Runner` must not have it swapped underneath. (Orthogonal to the
  existing `set_default_openai_responses_transport` global; ArkScope now leaves
  that transport at HTTP by default and uses
  `ARKSCOPE_OPENAI_RESPONSES_TRANSPORT=websocket` only as an explicit opt-in.)

---

## 4. OpenAI multi-key plan (kills the `[0]/[1]` confusion)

The `OPENAI_API_KEYS` comma-pool → **≥2 first-class `api_key` rows**, each with a
stable editable **alias** (never positional `OPENAI_API_KEYS[idx]`). **Alias
default = source-aware** (gpt-5.5, not generic A/B): `OPENAI_API_KEY` → "OpenAI
primary"; the distinct pool key → "OpenAI scoring/free-tier" — editable in Settings.

1. **Explode + dedup on import** (single pass — review fix): gather every key
   from `OPENAI_API_KEY` + `OPENAI_API_KEYS` into one list, collapse to a dict
   keyed by **exact secret** (first source/alias wins), UPSERT each distinct
   secret once. The verified duplicate (`OPENAI_API_KEYS[1] == OPENAI_API_KEY`)
   collapses to ONE row. First imported row per provider set active iff none is.
2. **Retire `api_key_pool` to read-only compat.** The factory already collapses
   `api_key_pool` → the `api_key` driver, so no driver change. ⚠️ **Review fix —
   enforce, don't assert:** make `CredentialStore.add()` **reject**
   `auth_type='api_key_pool'` (a stored `local:N` pool row is unresolvable —
   `_resolve_api_credential:587-592` parses a pool *index* off the id and indexes
   an env var). Pool stays only as an env-compat *read* representation.
3. **Daily-free-tier rotation = explicit manual set-active** between named rows
   ("A exhausted → click B"), NOT an opaque round-robin — exactly what was asked.

---

## 5. Export / import (corrected for the duplicate-row bug)

Net-new (no exporter/importer exists today). DB is source of truth; `.env` is the
portable port + fallback.

**Import ←`.env`** (`creds import --from-env` + first-run shim): parse via the
Slice-0 `unquote_env_value`; single-pass explode+dedup (§4.1); idempotent UPSERT
keyed by `(provider, secret)` (re-import updates alias / keeps active, never
dups). OAuth env *placeholders* are NOT imported as credentials; an actual OAuth
*token* sitting in `.env` triggers a one-time "import into the token-store?"
prompt, never a silent `llm_credentials` row.

**Export →`.env`** (`creds export --env`): regenerate from DB api_key rows. ONE
canonical individually-quoted line per key — no comma-pools, no `[idx]`.

🔴 **MAJOR review fix — do not regenerate the duplicate.** Exporting the active
key to bare `OPENAI_API_KEY` while `provider_credentials()` *unconditionally*
appends env-derived rows makes the same secret show as TWO inventory rows (the
exact confusion we're killing). **Fix (load-bearing, ship before export):** when
an active DB api_key row exists for a provider, **suppress/dedup the env-derived
rows by secret** in `provider_credentials()` (a cosmetic provenance label is not
enough). Test: a post-export reload shows each secret as **exactly one** row.

**OAuth excluded from plaintext export — by design.** A token in a flat `.env` is
the exact leak class we already got burned by, and violates "tokens live only in
the token-store, never echoed." Export emits a **commented stub** per OAuth row
("machine-local; re-run `claude setup-token` on the new box"). Portability for
OAuth = re-auth on the target machine. (An explicit, separate, `0o600` token
bundle is possible but default-OFF and deferred — open question §10.)
Exported `.env` is gitignored + `chmod 0600` + header warning; the exporter has
**no code path that reads token-store material** (asserted by a security test:
no token bytes ever appear in the exported file).

---

## 6. Adversarial-review must-fixes (folded in)

1. ✅ **Export dedup** — suppress env rows when an active DB row exists; one-row test (§5).
2. ✅ **Scoring key safe move** — `--api-keys-file` ALREADY exists (`score_ibkr_news.py:746`); its *default* reads `OPENAI_API_KEYS` and the common documented invocations pass no key flag. Removing the distinct scoring key would make default runs silently fall back to `OPENAI_API_KEY` (the duplicate account, lost rotation, no error). So **either** change the scorer's default to read a scorer-private key file **or** keep the scoring key out of the inventory by another mechanism — **plus a regression test on a default `--mode sentiment` run**. (§10.2 decision: scorer-private `config/scoring_keys.txt`, read as default-when-present.)
3. ✅ **Enforce no `api_key_pool` DB rows** — reject in `add()` (§4.2).
4. ✅ **Factual corrections** — `set_default_openai_client` exists (call it); 7 sync Anthropic sites, exclude `model_credentials.py:722` (§3).
5. ✅ **Single-pass import dedup** (§4.1, §5).
6. ✅ **Supabase out of scope** — done as standalone hygiene (§9), not gated to this feature.
7. ✅ `client_sync()` amendment kept as the verified strong catch (§3).

---

## 7. Settings surface (manual switch)

Already present: `CredentialList` + `onSetActive` → `PUT /config/credentials/{id}
{active:true}` (`config_routes.py:344`). Add: per-row **alias edit**;
**set-active that works identically across `api_key` and `claude_code_oauth`
rows** (one single-active operation = the key↔OAuth switch); per-row **Verify**
(`driver.test()`); an **env-fallback provenance label** ("served from DB
credential; `.env` is fallback only") to kill stale-shadow confusion. Optional:
partial unique index `(provider) WHERE active=1` to harden the invariant against
races. No auth_type *mutation* — switching mode = pick a different row + set
active (mode is immutable per credential; create/import the other mode first).

---

## 8. What was actually wrong with the old `.env` format (answering the "why")

- Comma-pool `OPENAI_API_KEYS` is positional, dedup-blind, and quote-fragile
  (`python-dotenv` can't parse `"a","b"`), so the same key became both the single
  `OPENAI_API_KEY` row and pool `[1]`.
- It was read ONLY by the Settings display — "which pool key is active" was never
  real (the live loop never consumed the pool).
- OAuth env placeholders advertised env vars nothing reads, clashing with the real
  token-store import path.
The hybrid model fixes all three at the root: one named row per key, dedup by
secret, active is a real DB flag the live loop **will** honor once wired (Slice 6;
today it drives the Settings inventory, not the live agents), OAuth lives only in the
token-store.

---

## 9. Sequencing (gated, TDD, well-split commits)

| Slice | Scope | Status |
|---|---|---|
| **0** `.env` unquote hygiene | `unquote_env_value` + route ALL production loaders (env_keys, cli, db_config via helper; collectors/training inlined) | ✅ `074e227` (helper + EODHD) + sweep `41b4aaf` (rest of production). ⚠️ 9 test-local `load_env` helpers left as separate hygiene |
| **1** drop Anthropic OAuth env placeholders | keep `OPENAI_OAUTH_TOKEN` signpost | ✅ `b821633` |
| **(hygiene)** dead-config removal | Supabase block + reader-less FMP value removed from gitignored `.env`; secret-bearing backup DELETED | ✅ done (`.env` ignored, no commit). ⚠️ user must revoke Supabase service-role key + DB pw server-side |
| **3** import ←`.env` core | reject `api_key_pool` in `add()` `7e55624` (C3a); `import_env_credentials()` single-pass explode+dedup → named rows `519820c` (C3b); scorer defaults to `config/scoring_keys.txt` `b877fb2` (C3c). Pre-commit `ed22355` (gitignore scoring_keys). | ✅ core done (TDD, 122 tests). ⏳ route/CLI/first-run **shim** + the real apply step (write `scoring_keys.txt`, edit real `.env`, run import on profile DB → counts/labels only) deferred to the wire-in |
| **4** export →`.env` + round-trip | env-vs-DB dedup `0fca212` (C4a); `export_env_credentials` + importer reads `ARKSCOPE_*` `b8ee880` (C4b/C4c). Format = **interop** (user-chosen): active → bare `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`, extras → `ARKSCOPE_<PROVIDER>_KEY__<slug>`, OAuth → commented stub (no token; export has no token-store access). Aliases on own comment line (loader doesn't strip inline `#`). | ✅ core done (TDD, 140 tests). ⏳ thin file-writer (chmod 0600) + CLI/route wiring deferred to the shim |
| **4-hardening** legacy pool inert | `5a68a11`: a stored `api_key_pool` row no longer resolves / shows usable / exports (resolve+inventory+export all api_key-only); env-compat `[idx]` read path intact | ✅ done (TDD, 153 tests; verified inert across resolve/discover/test/inventory/export) |
| **shim part 1** (plumbing) | `6244605`+`71af447`+`354f26a`+`ea05783`: `write_env_export` (0600 secure-create + tighten existing + `O_NOFOLLOW` symlink refusal) returns counts/labels; `import_env_credentials(dry_run=)` preview; `POST /config/credentials/import-env {dry_run}` + `POST /config/credentials/export-env {path}` (0600; `islink`→400, realpath clobber-guard vs live `config/.env`→400); responses carry no secret. `env_keys.env_file_path()` helper. **Boundary is CODE-ENFORCED:** real writes (non-dry-run import, any export) refused 403 unless `ARKSCOPE_CREDENTIAL_APPLY_ENABLED` is set — the routes are **preview/plumbing only** until apply is explicitly enabled (`require_profile_state_write` is a no-op audit log today, so logging alone would not gate). | ✅ done (TDD, 217 tests; temp file/fake env/temp DB only — real data untouched) |
| **shim part 2** (apply) | set `ARKSCOPE_CREDENTIAL_APPLY_ENABLED=1`, then: import against the real profile DB + write the real scoring_keys.txt + drop the migrated key from real `config/.env` | ⛔ **USER-GATED (now code-enforced, default OFF)** — counts/labels output only; preview first via `import-env {dry_run:true}` |
| **5** Settings named-row workflow | step1 partial-unique `(provider) WHERE active=1` index + heal-first migration `88c6720`; step2 route switch-guarantee tests (key↔key, key↔OAuth single-active) `88c6720`; step3 Settings polish (active badge + provenance copy) `d91e241`. Index applied to the real DB (idempotent, heal no-op). | ✅ steps 1-3 done (TDD; backend 212+, FE build clean). ⏳ **step 4 = USER GUI hand-test** (rename OAuth alias · set OpenAI pool 1 active↔primary · set Anthropic key active↔Claude OAuth · reload persists · no `[0]/[1]`). UI not yet runtime-verified by me — build-clean + data-verified only. |
| **6** S5 wire-in (api_key only) | 6a `78f2808` `client_sync()` + `live_resolver`; 6b `1a96d32` swap 7 sync `Anthropic()` sites + OpenAI bootstrap in `_build_agent`; review `22729bf` reset the sticky OpenAI global on fallback (was leaving a stale DB client) + wire the 3 direct `OpenAI()` sites (card_synthesis×2, code_generator) via `live_openai_client()` for full symmetry. **ALL direct LLM client construction (both providers) now honors the active credential / explicit env fallback.** | ✅ api_key wire-in done (user-approved; wiring smoke on real state: OpenAI active→SDK default SET, Anthropic OAuth→explicit env fallback). ⏳ **full live agent query (paid surface) = user confirmation / on-request.** Anthropic-OAuth-active runs on env key, NOT the subscription. |
| **7** Claude-subscription Research driver | the `claude_code_oauth` live path (Agent SDK / `claude -p`): `stream_llm`→AgentEvent, tool-loop/trace parity, history, streaming/cancel, usage/errors, CLI lifecycle, don't mix ArkScope vs Claude-Code tools. | ⏳ separate slice (user-deferred). What actually runs Research on the Claude subscription. |

---

## 10. Decisions (resolved with gpt-5.5 — locked for Slices 3–6)

1. **Alias defaults** — ✅ source-aware, NOT generic A/B: `OPENAI_API_KEY` →
   "OpenAI primary"; the distinct pool key → "OpenAI scoring/free-tier". Editable.
2. **Scoring-key path** — ✅ scorer owns its key in `config/scoring_keys.txt`
   (gitignored), read by `score_ibkr_news.py` as the **default when present**
   (before the `OPENAI_API_KEY` fallback). Regression test: a default
   `--mode sentiment` run picks that file, not `OPENAI_API_KEY`.
8. **`scoring_keys.txt` contents** (decided 2026-06-17) — **BOTH** `OPENAI_API_KEYS`
   entries go into `config/scoring_keys.txt`, not just the distinct one. Rationale:
   `OPENAI_API_KEYS` was the scorer's rotation pool (2 keys); putting both in the
   file is the **semantic-equivalent migration** (keeps batch-scoring capacity;
   moving only the distinct key would silently halve rotation). The research key
   `OPENAI_API_KEY` thus serves BOTH research (as `OpenAI primary` in the DB) and
   scoring (in the file) — the first concrete "same key, multiple purposes" case
   (§12). When per-purpose binding (§12) lands, scoring can be pulled back into
   the DB with an explicit `purpose=scoring` tag.
3. **Secret rotation** — ✅ backup DELETED + Supabase/FMP values removed from
   `.env` this turn. ⚠️ remaining USER action: revoke `SUPABASE_SERVICE_ROLE_KEY`
   + the old DB password on the Supabase side (I can't reach it).
4. **api_key at-rest** — ✅ keep plaintext `0o600` DB for now; keyring-for-api_key
   is a later hardening slice AFTER S5 wire-in is stable.
5. **Mid-session OpenAI switch** — ✅ next-query only; never mutate an in-flight Runner.
6. **OAuth portability** — ✅ default NO (re-auth with `claude setup-token` on the
   new machine); a `0o600` token-bundle export stays explicit + OFF by default.
7. **External `OPENAI_API_KEYS` readers** — only the scorer (being moved to its own
   key file). ⚠️ re-confirm before Slice 3 if any other external tool reads the comma form.

---

## 13. Apply — ✅ EXECUTED 2026-06-17 (user said go; verified)

Ran with `ARKSCOPE_CREDENTIAL_APPLY_ENABLED=1` (session-only, not persisted) +
DB-file & `.env` rollback backups (both gitignored, 0600). **All 3 verifications
passed:** `config/scoring_keys.txt` = 0600 + gitignored + 2 keys; `.env` has
`OPENAI_API_KEY` (and `ANTHROPIC_API_KEY`/`DATABASE_URL`) but NOT
`OPENAI_API_KEYS`; inventory = **2 named openai rows (`local:2` active +
`local:3` inactive), no `[0]/[1]`**, Anthropic api_key (`local:4`) inactive,
Claude OAuth (`local:1`) active; scorer reads `scoring_keys.txt` (2 keys,
rotation preserved). All touched files gitignored → no commit. Rollback backups:
`data/profile_state.db.preapply-backup-*` + `config/.env.preapply-backup-*`.

The plan that was executed, for reference:

1. **Backup-export** the current DB to a separate 0600 file (NOT the live `.env`).
2. **Import** the current `.env` → profile DB: openai dedups to **2 named rows**
   `OpenAI primary`(=`OPENAI_API_KEY`, active) + `OpenAI pool 1`(the distinct
   pool key, inactive); `Anthropic primary` (inactive — Claude OAuth stays active,
   import never steals active).
3. **Write `config/scoring_keys.txt`** (0600, gitignored) with **BOTH**
   `OPENAI_API_KEYS` entries (decision §10.8).
4. **Edit `.env`**: remove the `OPENAI_API_KEYS` line, **keep `OPENAI_API_KEY`**.

All steps report **counts/labels only — never a key value.**

**Pre/post-apply verifications (user-required, must all hold):**
- `config/scoring_keys.txt` mode is `0600` AND gitignored (`git check-ignore`).
- `.env` no longer has `OPENAI_API_KEYS`; still has `OPENAI_API_KEY`.
- Settings inventory: OpenAI = **2 named local rows, no `OPENAI_API_KEYS[0]/[1]`**;
  Anthropic API key **inactive**, Claude OAuth **active**.

Then **Slice 5** (Settings GUI) — the real GUI hand-test point. **Slice 6** stays
hard-gated.

---

## 12. Future direction — per-purpose credential binding (user request, not yet built)

User wants **different features to use different keys, and to optionally share a
key** ("不同功能…不同的 key…也要允許…相同的 key"). This generalizes today's
per-provider single-active flag into a **purpose → credential** map:

```
purpose       -> credential
research       -> OpenAI primary (or an OAuth credential)
scoring        -> OpenAI scoring   (config/scoring_keys.txt is the FIRST instance today)
fundamentals   -> (shared) OpenAI primary
```

- The scoring-key file split (C3c) is the first concrete instance of per-purpose keys.
- Same credential allowed for multiple purposes; unset purpose → falls back to the
  provider's active key.
- Interacts with the S5 driver resolution (`resolve_active_driver` would become
  `resolve_driver(provider, purpose)`).
- **Design slice AFTER Settings GUI (Slice 5) + the live-loop wire-in (Slice 6)** —
  recorded so it isn't lost; not in the current sequence.

---

## 11. Slice 4 known round-trip behaviors (verified, accepted)

Two empirical skeptics attacked the exporter; **security verdict: export cannot
leak a token** (it takes only the store — no token-store access — and renders
OAuth rows as comment stubs; proven against a token in a separate store and a
legacy non-NULL-secret OAuth row). Findings fixed in `f196da3` (control-char +
quote-wrapped rejection at the store boundary). Two behaviors are **accepted by
design**, documented so they aren't mistaken for bugs:

- **Active key's alias normalizes on re-import.** The active key is exported to
  the bare `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` var (the interop choice) — a
  vanilla env var has no alias — so on re-import it becomes "`<Provider> primary`".
  **Secrets and which-key-is-active round-trip faithfully**; only the active
  key's display name is lost. *Optional enhancement if wanted:* emit a parseable
  `ARKSCOPE_ACTIVE_<PROVIDER>_ALIAS=<alias>` data line and have import apply it —
  deferred unless you want it (adds a var to the interop format).
- **A none-active store auto-activates the first key on import** (C3b's documented
  behavior: set active iff the provider has none). So export(none-active) → import
  yields one active. Acceptable since a real store always has one active per
  provider; flagged for awareness.
