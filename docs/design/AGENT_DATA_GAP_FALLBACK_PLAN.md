# Agent Data-Gap Fallback Plan

**Status:** ACTIVE backlog  
**Created:** 2026-06-19  
**Owner area:** Agent tools + provider/data-source reliability  

## 1. Why This Exists

The agent already has many data tools, including SEC EDGAR tools and web-search
tools. The gap found on 2026-06-19 is not "no tool exists"; it is that a failed
data primitive does not always produce a structured reason or trigger a reliable
fallback path.

Concrete trigger:

- Sidecar log showed `SEC_CONTACT_EMAIL not set`.
- SEC lookup for `SNDK` failed with `Could not find CIK for SNDK`.
- SEC-dependent tools repeated `No SEC data found for SNDK`.
- Web search was available to the agent, but no deterministic workflow required
  it to resolve the missing CIK or fill the evidence gap.

For a research workbench, this must be explicit. Missing data is acceptable;
silent repetition, ambiguous empty results, and unsupported speculation are not.

## 2. Current Grounding

Current code behavior:

- `get_fundamentals_analysis()` tries stored/DAL fundamentals, then falls back to
  SEC EDGAR XBRL.
- `get_sec_filings()` calls SEC EDGAR directly.
- SEC ticker-to-CIK lookup currently returns empty on a miss and logs a warning.
- `SEC_CONTACT_EMAIL` is read from env/config and missing values use a
  placeholder User-Agent, which can be rejected or rate-limited by SEC.
- Tavily web tools and provider-native web-search tools are registered for the
  agent, but they are model-selected tools, not a forced tool-level fallback.

Current prompt behavior:

- The shared prompt tells the agent not to speculate when SEC filings are empty.
- It does not guarantee "SEC CIK miss -> resolve ticker identity -> retry SEC or
  web-search evidence".

## 3. Design Principle

Data primitives should return structured absence, not only empty arrays or stderr
logs. Agent orchestration can then decide whether to:

1. retry with a resolved identifier,
2. use a lower-fidelity web/evidence fallback,
3. show a visible data gap, or
4. stop and say the evidence is insufficient.

The agent may use web search, but critical fallback paths should not depend only
on the model remembering to do so.

## 4. Scope

### In Scope

- SEC User-Agent/contact hygiene.
- Structured SEC failure reasons.
- Ticker/CIK identity resolution.
- Web-search fallback for missing filings/fundamentals evidence.
- Per-turn deduping so the same failed SEC lookup is not repeated several times.
- Agent-facing evidence-gap messages that are visible in AI Research.
- Tests that prove fallback behavior without live SEC/web calls.

### Out of Scope

- Replacing SEC EDGAR.
- Letting web search overwrite structured SEC facts.
- Adding a new paid provider solely for this issue.
- Changing the AI Research run lifecycle architecture.
- Solving all ticker corporate-action history in one slice.

## 5. Proposed Slices

### Slice DG-0 — SEC Contact Hygiene

Goal: make missing `SEC_CONTACT_EMAIL` visible and easy to fix.

Tasks:

- Surface `SEC_CONTACT_EMAIL` missing in provider health / Settings data-source
  diagnostics.
- Keep the env/config fallback for now, consistent with
  `CONFIG_AUTHORITY_PLAN.md`.
- Add a test that missing contact produces a structured warning, not only a
  stderr line.

Acceptance:

- User can see "SEC contact missing" before a research turn fails.
- SEC tools still run in dev mode, but the warning is explicit.

### Slice DG-1 — Structured SEC Absence

Goal: replace ambiguous SEC empty results with typed reasons.

Tasks:

- Return machine-readable reasons such as:
  - `sec_contact_missing`
  - `cik_not_found`
  - `sec_rejected_or_rate_limited`
  - `no_filings`
  - `no_xbrl_statements`
- Preserve the existing list/result shapes for backwards compatibility where
  needed, but add a diagnostic envelope for agent-facing paths.
- Add tests with mocked SEC responses.

Acceptance:

- AI Research can distinguish "ticker not resolved" from "SEC has no filing
  data" from "SEC rejected the request".

### Slice DG-2 — Ticker Identity Resolver

Goal: give the agent/tool layer a deterministic first stop before web search.

Tasks:

- Add or adapt a resolver using local symbol catalog + SEC company ticker map.
- Return `{ticker, cik, company_name, confidence, source, aliases}`.
- If a ticker is not found, return `not_found` with suggested next action rather
  than guessing.
- Use this resolver in SEC filing/fundamental paths.

Acceptance:

- A CIK miss produces one resolver attempt, one structured result, and no repeated
  blind SEC retries in the same turn.

### Slice DG-3 — Web Evidence Fallback Policy

Goal: make web search a controlled fallback, not an accidental model choice.

Tasks:

- Add prompt/tool policy: if SEC returns `cik_not_found` or
  `sec_rejected_or_rate_limited` and the user asks for filings/fundamentals or an
  unexplained event, call web search or explicitly report insufficient evidence.
- Prefer source-specific queries such as `"<ticker> SEC CIK 10-K"` and company
  investor-relations pages before broad news queries.
- Keep web results lower confidence than structured SEC data.

Acceptance:

- A missing SEC identity can lead to a visible web-search attempt or a visible
  refusal to speculate.
- Web evidence is labeled as web-derived, not SEC-derived.

### Slice DG-4 — Data-Gap Telemetry

Goal: make data gaps queryable over time.

Tasks:

- Record provider/tool attempts with provider, operation, ticker, status,
  latency, failure reason, fallback source, and record count.
- Align with `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` Slice 5 provider-health
  telemetry instead of inventing a separate telemetry model.
- Add a compact UI/trace line in AI Research for repeated data gaps.

Acceptance:

- Repeated failures like "SNDK CIK not found" are visible as one diagnostic
  event, not repeated opaque stderr lines.

## 6. Priority

Recommended priority:

1. Immediate manual fix: set `SEC_CONTACT_EMAIL`.
2. Finish the current Slice 6 live-auth verification and Slice 7 decision.
3. Implement DG-0/DG-1 as a small hardening slice.
4. Implement DG-2/DG-3 before relying on the agent for broad event-explanation
   workflows.
5. Fold DG-4 into the provider-health telemetry work.

This is important, but it should not interrupt the current auth/run-lifecycle
closing work unless SEC/web evidence gaps become the main blocker in live use.

## 7. Related Docs

- `ARKSCOPE_TOOL_CATALOG.md` — current tool inventory and stable primitive rules.
- `ARKSCOPE_PROVIDER_CATALOG.md` — provider facts and limits.
- `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` — provider health telemetry and
  local data-source plan.
- `CONFIG_AUTHORITY_PLAN.md` — config/env fallback and Settings authority rules.
- `AI_RESEARCH_CONTEXT_MEMORY_PLAN.md` — evidence freshness and no-speculation
  principles for research turns.
- `AI_RESEARCH_RUN_LIFECYCLE_PLAN.md` — future server-owned run traces where
  data-gap diagnostics should appear.
