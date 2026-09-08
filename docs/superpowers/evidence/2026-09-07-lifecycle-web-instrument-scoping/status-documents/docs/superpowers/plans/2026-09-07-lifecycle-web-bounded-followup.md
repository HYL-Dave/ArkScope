# Lifecycle Web Bounded Follow-Up

Status: proposed after measured Claude OAuth calibration; schema decision
requested, not assumed. No production migration, installation or new dispatch.

## Why Larger Search Limits Alone Are Insufficient

The September 7 instrument-scoping run used only two of twelve searches and five
of twenty-four HTTP attempts. It returned a non-actionable finding. Its CapEdge
8-K page explicitly supplied only a preview ending in Item 1.02. No transport or
RAM bound was reached. The visible original link led to a public SEC filing
index, whose typed primary-document row led to the full 8-K. That document
contained the relevant common-stock trading cessation paragraph in Item 3.01.
The host diagnostic, not the product agent, followed those references.

The two analysis-only follow-ups used the same current product prompt with the
additional captured document. One output failed the JSON contract without raw
output diagnostics; the next was valid JSON but still non-actionable. It put a
statement explicitly saying debt was NOT a contradiction into `contradictions`,
omitted the instrument-definition span from an event using `Company Stock`, and
had citation/date-support gaps. These are not successful user confirmations.
An explicitly hand-constructed, exact-quotation positive control passes against
the very same captured source and actual selected context. It is not presented
as model output. Full source capacity is not the bottleneck.

## Proposed Contract

- Permit at most three search/read/analysis rounds and six host model calls.
  Keep one global twelve-search, eight-new-source, twenty-four-HTTP budget for
  the entire run, including redirects and followed public references. State the
  derived overall deadline in preflight; do not reset counters each round.
- Successful but incomplete analysis may request a named follow-up: missing
  original source, missing instrument scope, or citation/format correction.
  A transport, auth, model-identity, timeout or quota failure still stops. An
  owned completed reply rejected for output shape may get a named, bounded
  correction only after the rejection and observed usage are retained. It is
  not an accepted finding and is not a transport retry. No model, credential or
  billing fallback. Follow-up reasons and every extra submission must be visible
  in the durable phase history.
- Give the next search the actual source coverage, remaining gaps and already
  visited URLs. Expose and follow explicit public original-document references
  with the existing pinned HTTPS/SSRF and source-byte protections. A source
  reference is not an HTTP redirect and must not be recorded as one. Do not log
  into the preview site, bypass its access gate, assume its preview is complete,
  or force SEC as the authority for every case.
- Stop on an action-ready supported finding, a supported active result, no new
  relevant source or improved grounding, or the run ceiling. Do not fill quotas
  just to use them, loop over the same URLs, or ask the user to repeat research.
- Keep stock, debt, preferred stock and option identities separate. Allow a
  source-bound definition/identity chain without treating issuer identity alone
  as security identity. Review the single-quotation identity requirement and
  defined-term handling against both genuine stock notices and misleading debt
  notices before changing it.
- Prefer source-bound passage references to making a model reproduce long
  whitespace-sensitive quotations. Any revised output shape must retain exact
  original text, coverage, date and instrument provenance, and legacy readback.
  Do not silently repair or discard an unsupported claim to make a run green.
- Restrict `contradictions` to genuinely incompatible facts about the target
  security. Irrelevant instruments and explanations of non-contradiction belong
  in neither a veto list nor a fabricated conflict. Keep optional announcement
  information separate from the evidence needed to decide collection status.

## Required Schema And Cross-Module Work

`lifecycle_web_calls.call_id` has a CHECK permitting only `search-1` and
`analysis-1`. The store, controller, usage ledger, consent/read DTO and tests also
bind those identities. Increasing only RunControl or an SDK turn limit would
break persisted accounting. A versioned schema/read contract is therefore real
work, not a silent constant bump. Preserve old journals, including failed and
non-actionable runs, with explicit supported-version handling. The last
authorized production inventory found no installed Web journal; that is an
observation at that time, not permission to inspect or install now.

After the schema decision, write RED owners for second-round success, bounded
no-progress exit, cumulative search/HTTP/call accounting, failures after earlier
successful phases, cancel/restart readback, immutable earlier findings, stale
human approval, genuine debt/stock separation and the real partial-source shape.
Run the full focused set, named reverse mutants, integration/backend and actual
UI parser/browser paths. Claude OAuth calibration remains first; the other three
transports must consume the same contract and must not be declared live verified
because Claude succeeds. Production migration, installation, adoption, restart,
merge and push remain separate actions.
