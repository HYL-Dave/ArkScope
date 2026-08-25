# Trusted Lifecycle Automation Real-Source Repair Plan

**Goal:** Make the deterministic SEC fact extractor consume the four exact
public filing bodies captured by the authorized canary without weakening the
existing evidence, citation, or transition gates.

**Authority:** Product/test base `7cb479a8058793dc29cbb75bb4ab98b9d6a6f231`;
canary executor commit `f6a7e12987f3614d1be1fb17afd8ecc0f1c9f96f`.
The live run is consumed and may not be repeated without new authorization.

## Boundaries

- Owned non-governance paths are exactly the two rows in
  `2026-08-25-trusted-lifecycle-automation-real-source-repair-owned-paths.tsv`.
- New test nodes are exactly the four rows in
  `2026-08-25-trusted-lifecycle-automation-real-source-repair-additions.nodes`.
- The four captured SEC response bodies are immutable public evidence fixtures:
  HAPN `48ebd4ef...b732f`, QBTS `bf1046a3...bc43`, CCL
  `892bb9f6...39a8`, and BLBD `14bc6500...298e`.
- No provider/network call, production database operation, schema change,
  scheduler/worker/policy/UI change, merge, push, or cutover is authorized.

## Required Semantics

1. A Section 12(b) cover row may establish the current registered symbol and
   source venue only when the symbol equals an existing case alias.
2. Explicit filing prose may declare a previously unknown successor. HAPN must
   resolve `LC -> HAPN`, `NYSE -> NASDAQ`, effective when Nasdaq trading begins
   on `2026-06-22`; the successor must not be inserted into aliases first.
3. QBTS must resolve a same-symbol venue transfer, `NYSE -> NASDAQ`, effective
   when Nasdaq trading begins on `2026-07-27`, with no symbol transition.
4. An explicit completed dual-listed-company unification plus same-share/current
   registered-symbol continuity resolves CCL as no tracked-security identity
   change.
5. An explicit asset-purchase agreement plus current registered-symbol
   continuity resolves BLBD as an asset acquisition with no registrant identity
   change. Extract the named counterparty as partial terms; do not invent
   per-security cash, exchange ratio, or an identity effective date.
6. Dates are extracted only from clauses that bind the date to the tracked
   identity/listing event. A different agreement's `effective` clause may not
   become the security transition date.

## RED / GREEN

1. Add the four real-source tests and run them against `7cb479a8` product bytes.
   They must fail on missing/wrong facts, not fixture setup.
2. Make the smallest extractor-only change that passes all four real-source
   tests and all existing SEC/decision/shadow tests.
3. Re-run the complete backend and frontend gates because these facts feed the
   already-shipped automation/UI surfaces. No provider call is permitted.
4. Rebuild the Stage 5 evidence packet against the repaired product authority;
   retain the canary report and exact source bytes in a separate manifest.
