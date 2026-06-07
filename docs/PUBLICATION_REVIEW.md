# Publication Review Policy

ArkScope's design docs are being **unlocked from git-crypt and made public** (the
repo is open-source). This file is the policy for keeping them publishable. The
goal is **honest, clean public docs** — not hiding work.

> Most docs are NOT sensitive. The concern is rarely "this can't be open-sourced";
> it's "this idea isn't proven yet" or "this approach was abandoned." So the rules
> below are mostly about **labeling maturity** and **pruning dead approaches**,
> with a small **secrets/PII hygiene** floor.

---

## 1. Secrets & PII hygiene (hard floor — never publish)
- **No secrets.** No API keys, tokens, passwords, or DSNs with embedded creds.
  Use the env-var **name** only (`POSTGRES_PASSWORD`, `FRED_API_KEY`, …); real
  values live in `config/.env` (gitignored).
- **No internal infra.** Generalize internal IPs/hosts: `<postgres-host>:<port>`,
  `<ibkr-gateway-host>:<port>`. (Generic, public port conventions are fine.)
- **No personal absolute paths.** `~/…` for runnable snippets; `<repo-root>` /
  `<workspace>` / `<data-root>` for layout references — keep the meaningful suffix
  so "where things live" still reads.
- **No personal identifiers** (OS username, personal email, real name).
- Intentional public identifiers are fine to keep: the native-messaging host id
  `com.mindfulrl.sa_alpha_picks`, addon id `sa-alpha-picks@mindfulrl.local`, the
  bare DB name `mindfulrl`, the local dev port `8420`.
- Paid-provider pricing must carry a `verified_at:` date (prices go stale).

## 2. Maturity labeling (the real point)
A public design doc may describe an **unproven** idea — that's fine, **as long as
it's labeled as such and not overclaimed**.
- Every design doc should carry a status (see **`docs/design/README.md`** — the
  index/status map): CANON / ACTIVE / SHIPPED / DECISION / DEFERRED / PAUSED / MERGE.
- Do **not** present a sketch or hypothesis as a shipped, validated feature. If a
  scoring/signal/strategy idea hasn't been shown to work out-of-sample, say so
  ("proposed", "unvalidated", "deferred") rather than implying it's proven.
- When the underlying code is open-sourced, the features it contains are public
  anyway — so the matching design doc being public is consistent. The honesty bar
  is *accuracy about maturity*, not concealment.

## 3. Prune abandoned approaches
- Remove HOW-docs for approaches no longer used (even if once implemented) rather
  than leaving them to read as current. Provenance worth keeping goes to
  `docs/history/` (small WHAT/WHY records) or is recoverable via git.
- Superseded process journals (audits, consolidation logs) fold into the canonical
  doc or history; they are not standalone authority.

## 4. Stays ENCRYPTED for now (per-file review before unlocking)
These are kept under git-crypt not because they're "secret" but because they hold
**personal strategy / purchasing decisions / unvalidated value judgments** the
author wants to release deliberately, per-file, when ready:
- `docs/strategy/**` — personal investing strategy / methodology.
- `data_sources/PAID_SUBSCRIPTION_EVALUATION.md` — paid-plan purchasing analysis.
- `data_sources/*_VALUE.md` — data-value judgments.

Unlocked now: **`docs/design/**` + `docs/features/**`** (after the §1 sanitization).
To unlock more later: sanitize per §1, confirm maturity-labeled per §2, then remove
the `filter=git-crypt` line from `.gitattributes` and `git add --renormalize`.
