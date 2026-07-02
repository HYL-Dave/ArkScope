# IV Provider Proof Packet Plan

- **Date:** 2026-07-02
- **Status:** DRAFT for review
- **Scope:** read-only provider sampling + evidence document. No runtime code, no
  scheduler wiring, no ArkScope DB writes, no provider selection lock.
- **Parent:** `docs/design/PG_EXIT_REMAINDER_SCOPING.md` §7 / §12.5.
- **Goal:** Decide which provider payloads can feed ArkScope's provider-neutral IV
  snapshot model before S-D schema lock.
- **Architecture:** run isolated, runtime-external sampling helpers against temporary
  keys; store raw outputs only under local `scratchpad`; commit only the summarized
  evidence document and any plan updates.
- **Tech Stack:** Python scratch scripts/notebooks, provider REST APIs, local markdown
  evidence docs; no `src/`, scheduler, API route, or database migration changes.

## Goal

Produce a small, reproducible evidence packet that decides whether Massive/Polygon,
Alpha Vantage, and EODHD/Unicorn can feed the same provider-neutral IV snapshot shape
for ArkScope-owned IV computation. The packet must run before S-D locks the local IV
schema.

The packet answers four questions:

1. Can each provider supply enough retained raw/near-raw inputs to recompute ATM IV,
   term buckets, and VRP deterministically?
2. Can historical backfill be done at acceptable cost, rate limit, and completeness?
3. Do provider timestamps and underlying prices make cross-provider comparisons
   interpretable?
4. Can all viable providers fit one snapshot schema with `granularity` / provenance
   fields, instead of forcing separate EOD-vs-quote-history schemas?

## Non-Goals

- No subscription purchases without explicit sign-off.
- No permanent provider key storage.
- No edits to `config/.env`.
- No FieldDefs yet, except after a provider is selected in a later slice.
- No production collector, scheduler job, UI, or database migration.
- No attempt to preserve the old 24-row PG `iv_history`; it remains a drop candidate.

## Inputs

### Candidate Providers

1. **Massive / Polygon** — candidate A. Best raw quote-history / forward snapshot
   candidate if Advanced-tier access and 2022+ history are acceptable.
2. **Alpha Vantage** — candidate B. Historical backfill candidate with deep date
   support, but request limits and field completeness must be measured.
3. **EODHD / Unicorn** — candidate C. Low-cost EOD-history fallback; timestamp
   semantics and product maturity must be measured.

Reference-only providers:

- **IBKR** — S-E prototype/cross-check backend, not a full-universe daily backbone.
- **ORATS / Tradier** — reference/enrichment only; Tradier greeks are ORATS-derived and
  not independent ORATS validation.

### Sample Universe

Use a fixed, small set so packet results are reproducible:

- `SPY` — highly liquid ETF, dense chains, includes weeklies and 0DTE behavior.
- `AAPL` — liquid single-name baseline.
- `NVDA` — high IV / event-sensitive mega-cap.
- `TSLA` — event-heavy / wide-strike single-name.
- `SOFI` — lower-price, lower-liquidity optionable name to expose sparse chains.

If a provider cannot serve one ticker, record `provider_unavailable_for_ticker`; do not
substitute silently.

### Sample Dates

Use these logical buckets:

- latest available session;
- one week back;
- one month back;
- one year back;
- old date: `2017-11-15` for providers claiming deep history;
- earliest-provider date if the provider does not support 2017.

If a provider only supports EOD or delayed data, record that fact; do not compare it as
if it were a same-time realtime snapshot.

## Step 0: Cost / Authorization Gate

This is a gate before any paid or authenticated sampling.

### 0.1 Check Existing Key Presence

Run a names-only presence audit. Do not print values.

Managed / legacy names to check:

- `ALPHA_VANTAGE_API_KEY`
- `EODHD_API_KEY`
- `POLYGON_API_KEY`
- `MASSIVE_API_KEY` (if introduced by provider rebrand)

Allowed sources for this audit:

- `os.environ` names-only presence;
- `config/.env` names-only presence;
- `profile_state.db` provider config names-only presence.

The audit output must be:

```text
alpha_vantage: present|missing, source=env|config_env|app|missing
eodhd: present|missing, source=env|config_env|app|missing
polygon_or_massive: present|missing, source=env|config_env|app|missing
```

No key values, prefixes, lengths, or hashes.

### 0.2 Minimum Sampling Cost Table

Before any API call, write a table with:

- endpoint required for payload-shape sampling;
- endpoint required for historical sampling;
- free/delayed tier can answer which questions;
- paid tier needed for historical IV/greeks / quotes;
- monthly or request-rate cost boundary;
- account entitlement or exchange agreement requirement;
- sign-off needed: yes/no.

Known gating from S-C:

- Alpha Vantage `HISTORICAL_OPTIONS` is premium-gated; realtime options require higher
  request/minute premium tiers.
- Massive historical options quotes require Advanced-tier access; chain snapshots are
  delayed or realtime depending on options plan.
- EODHD/Unicorn options are a separate marketplace subscription.

### 0.3 Sign-Off Rule

If a provider requires a new subscription, upgrade, or marketplace purchase, stop and
produce a sign-off note:

```text
Provider: <name>
Minimum cost/tier: <amount/tier from provider page>
Questions unlocked by payment: <list>
Questions answerable before payment: <list>
Recommended action: approve|skip|defer
```

No paid action may be taken inside the packet without explicit user approval.

## Sampling Discipline

### Key Handling

- Pass keys only via one-shot CLI arg or temporary shell env for the packet command.
- Do not write packet keys to `config/.env`.
- Do not import packet keys into `profile_state.db`.
- Do not add FieldDefs until a provider is selected after the packet.
- Scrub provider URLs before logging if they contain query-string keys.

### Files

Allowed output paths:

- `scratchpad/iv_proof_packet/raw/<provider>/...json`
- `scratchpad/iv_proof_packet/summary/*.json`
- `docs/design/IV_PROVIDER_PROOF_PACKET.md`

The raw scratch files are local artifacts and should not be committed unless explicitly
approved. The committed output is the evidence doc only.

### Runtime Boundary

Sampling code, if needed, must live outside runtime:

- acceptable: `scratchpad/iv_proof_packet/*.py` or a notebook in `scratchpad`;
- not acceptable: `src/`, `data_sources/`, `scripts/collection/`, scheduler routes, or
  API routes.

## Measurements

For every provider/ticker/date sample, record:

- request status: `ok`, `auth_required`, `paid_tier_required`, `rate_limited`,
  `not_supported`, `empty`, `error`;
- endpoint and provider plan used;
- snapshot timestamp semantics: realtime, delayed, EOD, near-close, SIP quote
  timestamp, vendor aggregation, unknown;
- underlying price source and timestamp;
- contract identity fields;
- expiration enumeration completeness, especially weekly/0DTE vs monthly expiries;
- strike coverage near ATM and across moneyness;
- bid/ask/last/mid fields and timestamps;
- bid/ask sizes if present;
- volume and open interest fields;
- provider IV and greeks non-null coverage;
- DTE, moneyness, theoretical, and vendor-specific confidence fields if present;
- pagination count and request count;
- response payload size;
- schema anomalies, including duplicated symbols, missing expiries, impossible dates, or
  contract identifiers that cannot be round-tripped.

## Deterministic Recompute Experiment

For each successful provider sample, pick a deterministic subset:

- nearest expiration at or above 21 DTE;
- nearest expiration at or above 45 DTE;
- call and put nearest to ATM for each selected expiration;
- skip contracts with missing bid/ask or zero/negative midpoint;
- record skipped contracts with reasons.

Compute:

- `mid = (bid + ask) / 2` when both bid and ask are positive;
- time to expiry from provider expiration + snapshot timestamp;
- underlying from provider if present, otherwise an independent same-symbol quote with
  timestamp recorded;
- rate/dividend assumptions:
  - use a fixed placeholder assumption for packet comparison only, recorded as
    `packet_rate_dividend_assumption_v1`;
  - do not claim production IV accuracy from this packet assumption.

Then recompute Black-Scholes-Merton IV for the selected calls/puts and compare to
provider IV:

```text
provider_iv_present: true|false
arkscope_iv: number|null
absolute_diff: abs(arkscope_iv - provider_iv)
relative_diff: absolute_diff / provider_iv
within_tolerance:
  true if absolute_diff <= 0.03 OR relative_diff <= 0.15
```

This is not a final pricing model. It is a feasibility check for the "own the
computation" premise: the provider's retained inputs must be coherent enough for
ArkScope to derive a comparable IV on ordinary near-ATM contracts.

If a provider exposes only vendor IV/greeks and insufficient bid/ask/underlying timing
to recompute, mark it:

```text
own_compute_feasibility = failed_insufficient_inputs
```

## Snapshot Shape Hypothesis

The packet should test this S-D schema hypothesis:

> One provider-neutral raw snapshot schema is enough. EOD providers write close-anchored
> snapshots, realtime/delayed providers write chosen-time snapshots, and quote-history
> providers synthesize snapshots at a selected timestamp. Differences live in
> `provider`, `source_endpoint`, `snapshot_at`, `granularity`, `timestamp_semantics`,
> `raw_payload_ref`, and confidence/status fields.

Pass conditions:

- all selected provider candidates can produce rows with contract identity, expiration,
  strike, call/put, bid/ask or a defensible price input, underlying price/timestamp,
  volume or OI when available, and provider timestamp semantics;
- provider-specific fields can fit `raw_payload_ref` / auxiliary JSON without changing
  the core row identity;
- missing fields are explainable by provider granularity rather than schema mismatch.

Fail conditions:

- a provider only returns pre-derived surface metrics without enough contract-level
  inputs;
- a provider's historical payload cannot be tied to a specific snapshot time or EOD
  convention;
- the provider cannot enumerate enough expiries/strikes to support the planned DTE or
  delta bucket.

## Evidence Document Output

Create `docs/design/IV_PROVIDER_PROOF_PACKET.md` with these sections:

1. **Executive decision:** backfill viable? preferred provider candidate? forward-only
   fallback?
2. **Cost / authorization:** what was free, what required payment, what was skipped.
3. **Keys used:** names-only presence and source, no values.
4. **Provider results matrix:** one table per provider with coverage and request math.
5. **Payload shape notes:** fields observed, timestamp semantics, pagination, anomalies.
6. **Recompute experiment:** selected contracts, ArkScope IV vs provider IV, tolerance
   summary, skipped reasons.
7. **Snapshot schema decision:** whether S-D can proceed with one snapshot schema and
   which fields are mandatory/nullable.
8. **Gaps and non-results:** what could not be sampled and why.
9. **Recommendation:** S-D schema lock recommendation and whether S-F bulk backend is
   needed.

The evidence doc must be explicit about negative findings. "Not sampled because paid
tier not approved" is a valid result.

## Suggested Execution Tasks

### Task 1: Cost / Authorization Audit

Files:

- Create local-only script: `scratchpad/iv_proof_packet/audit_access.py`
- Create draft evidence doc: `docs/design/IV_PROVIDER_PROOF_PACKET.md`

Steps:

1. Write `audit_access.py` to emit names-only key presence and provider tier links.
2. Run it without printing values.
3. Fill the Cost / Authorization section.
4. Stop for sign-off on any paid tier.

### Task 2: Free / Existing-Key Payload Sampling

Files:

- Create local-only script: `scratchpad/iv_proof_packet/sample_payloads.py`
- Update: `docs/design/IV_PROVIDER_PROOF_PACKET.md`

Steps:

1. For providers with existing keys or free endpoints, collect sample payloads for the
   sample universe and latest available date.
2. Store raw samples under `scratchpad/iv_proof_packet/raw/`.
3. Summarize field presence, endpoint shape, pagination, and timestamp semantics.
4. Do not commit raw payloads unless explicitly approved.

### Task 3: Historical Coverage Sampling

Files:

- Modify: `scratchpad/iv_proof_packet/sample_payloads.py`
- Update: `docs/design/IV_PROVIDER_PROOF_PACKET.md`

Steps:

1. Sample the historical date buckets allowed by current access.
2. For paid-gated buckets, record `paid_tier_required` instead of failing the packet.
3. Compute non-null coverage for required fields.
4. Update request math and history viability.

### Task 4: Recompute IV Feasibility

Files:

- Create local-only script: `scratchpad/iv_proof_packet/recompute_iv.py`
- Update: `docs/design/IV_PROVIDER_PROOF_PACKET.md`

Steps:

1. Select near-ATM contracts deterministically.
2. Recompute IV with the packet-only assumptions.
3. Compare to provider IV with the packet tolerance.
4. Record skipped contracts and failure reasons.

### Task 5: Schema Recommendation

Files:

- Update: `docs/design/IV_PROVIDER_PROOF_PACKET.md`
- Optionally update: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`

Steps:

1. Decide whether one snapshot schema covers A/B/C.
2. List mandatory fields, nullable fields, and provider-specific raw JSON.
3. State whether S-D can lock schema, and what remains open.
4. Commit only docs unless the user explicitly approves committing helper scripts.

## Review Gate

Before S-D starts:

- user reviews `IV_PROVIDER_PROOF_PACKET.md`;
- no raw provider payload with secrets is committed;
- no key has been written to `config/.env` or `profile_state.db`;
- provider access costs are explicitly accepted or declined;
- S-D schema inputs are concrete, not inferred from marketing pages.
