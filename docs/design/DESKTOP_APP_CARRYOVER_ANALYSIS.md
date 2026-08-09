# Desktop App Carry-over Analysis

> **Status:** CURRENT POST-RETIREMENT AUTHORITY
> **Updated:** 2026-08-09
> **History:** The pre-retirement component matrix remains available in Git.
> This version records only the current product boundary.

## 1. Current boundary

ArkScope keeps the local-first research workbench, its agent runtime, and its
evidence-oriented data layer. The following capabilities remain current:

- the tool registry, typed schemas, provider routing, subagents, attachments,
  context compression, token tracking, skills, reports, and memory;
- raw news retrieval and storage, deterministic news-volume observations, and
  title/date event sequences;
- provider-native sentiment fields and investor-profile risk fields, which are
  distinct from the retired ArkScope 1-5 article score;
- prices, fundamentals, macro data, Seeking Alpha evidence, portfolio tools,
  and caller-supplied option-pricing mathematics; and
- the local profile, scheduler infrastructure, job receipts, health views, and
  current desktop Settings surfaces.

Storage-specific owners must continue to follow the current local SQLite and
profile contracts. PostgreSQL remains an archive/import boundary, not an
application runtime authority.

## 2. Retired implementations

The following implementations are retired from the working tree and are not
scaffolds, compatibility layers, or dormant product capabilities:

- the disconnected offline RL and training lineage;
- the legacy article-scoring producers, consumers, score-based API/tool
  contracts, and composite recommendation semantics;
- the former Signals implementation and its recommendation-shaped routes; and
- the deferred Phase D analysis implementation, route, CLI entry, and scheduled
  job.

Git history is the record. No archive copy, disabled package, re-export, alias,
or tombstone is retained in the current tree.

Production score rows and the local scoring credential file are not part of
this source cutover. Their physical disposition requires a separate manifest
and explicit user approval. Nothing in this document grants runtime authority
to those disconnected bytes.

## 3. Future capabilities

The original product goals are still valid, but their old implementations are
not reusable contracts:

- a future Signals product requires a written hypothesis, source-labelled
  inputs, explicit freshness, out-of-sample validation, and kill criteria;
- future RL research starts from a new reviewed design and current data
  contracts, not restored training code or old checkpoints;
- future on-demand analysis starts from a new typed evidence-card contract,
  without resurrecting the retired recommendation scaffold; and
- provider-backed option estimates require a current provider, entitlement,
  provenance, freshness, and spend decision. Existing pure option mathematics
  remains available when the caller supplies the market inputs.

These are roadmap intentions, not claims that an implementation currently
exists.

## 4. Durable carry-over rules

1. Preserve current raw-data and evidence contracts when adding new research
   capability.
2. Do not infer sentiment, direction, impact, or recommendation values from an
   absent retired score. Typed unavailable output is preferable to a fabricated
   neutral value.
3. Do not reconnect production score rows through a convenience fallback.
4. New capability work owns its schema, provenance, freshness, UI, tests, and
   operational schedule from the start.
5. Historical documents describe dated decisions only. Current implementation
   claims come from this document, the Workbench Product Spec, and the Tool
   Catalog.

## 5. Related authorities

- [ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md](ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md)
- [ARKSCOPE_TOOL_CATALOG.md](ARKSCOPE_TOOL_CATALOG.md)
- [SCRIPTS_RETIREMENT_DECISION.md](SCRIPTS_RETIREMENT_DECISION.md)
- [PHASE_D_ANALYSIS_PIPELINE_SKETCH.md](PHASE_D_ANALYSIS_PIPELINE_SKETCH.md)
- [RL_COLLAPSE_FINDINGS.md](RL_COLLAPSE_FINDINGS.md)
