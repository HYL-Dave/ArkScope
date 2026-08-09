# Phase D Analysis Pipeline Sketch

> **Status:** HISTORICAL DESIGN RECORD - IMPLEMENTATION RETIRED 2026-08-09
> **Authority:** The former scaffold, route, CLI entry, and scheduled job are
> absent. Git history preserves their implementation. This document is not a
> current runbook or a reusable scaffold.

## 1. Why it was retired

The deferred implementation assembled recommendation-shaped technical,
fundamental, sentiment, and risk strategies without the evidence and validation
required for a product decision. It also depended on the retired legacy score
and composite signal semantics. Keeping only part of the package would leave an
importable but misleading capability surface.

The entire implementation therefore retired atomically with the legacy scoring
and training lineage. Generic scheduler, report, raw-data, and agent
infrastructure remain under their current owners.

## 2. Product goal that remains

ArkScope may still add on-demand or scheduled analysis. A future design should:

1. accept a normalized request with an explicit `as_of` time;
2. gather source-labelled facts through current data contracts;
3. distinguish facts, calculations, hypotheses, and unavailable evidence;
4. produce a typed evidence artifact before prose rendering;
5. preserve partial failures instead of fabricating placeholders;
6. record provenance, freshness, source coverage, and evidence references; and
7. avoid buy/hold/sell output unless a separately reviewed and validated
   decision product explicitly requires it.

These principles are design input only. No current module, route, command, or
schedule is implied by this document.

## 3. Restart gate

Future implementation requires a new product spec and RED-first plan based on
the then-current agent, data, profile, and UI contracts. It must not recover the
retired package merely to obtain class names or module layout from history.

At minimum, the new spec must decide:

- the user-visible artifact and its edit/export lifecycle;
- evidence and citation shape;
- freshness and degradation semantics;
- interactive versus scheduled ownership;
- model/provider and spend policy;
- validation and kill criteria; and
- how the feature differs from the future Signals research line.

## 4. Historical record

The detailed April 2026 proposal and partial scaffold can be inspected through
Git history before the Tranche B retirement commit. It remains useful for
understanding why the original goal existed, but it is not authority for future
implementation choices.
