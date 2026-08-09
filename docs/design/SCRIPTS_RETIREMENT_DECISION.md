# Scripts Retirement Decision

> **Status:** CURRENT AUTHORITY - TRANCHE A COMPLETE; TRANCHE B CUTOVER
> **Updated:** 2026-08-09
> **History:** The reviewed 748-line Tranche A authority and the pre-cutover
> Tranche B analysis remain available in Git history. This concise authority
> supersedes their working-tree implementation claims.

## 1. Decision

The root scripts package is retired and absent. Git history is the only archive;
the repository keeps no compatibility package, disabled command, re-export,
tombstone, or copied implementation.

Tranche A removed obsolete migration, diagnostic, visualization, testing, and
operator CLIs after their consumers and replacement owners were reviewed.
Tranche B completes the product-level retirement of the legacy score lineage,
the disconnected training lineage, the former composite Signals implementation,
and the recommendation-shaped Phase D analysis scaffold.

This is an intentional product boundary, not a temporary file move.

## 2. Exact Tranche B source boundary

The atomic cutover has the following reviewed accounting:

- 263 backend test nodes retire and 18 replacement contract nodes enter;
- 109 retired nodes belong to the training-only lineage;
- 138 retired nodes belong to legacy score and signal behavior;
- 16 retired nodes belong to the recommendation-shaped Phase D surface; and
- the exact training family consists of 53 implementation files, eight
  dedicated test files, and one manual yfinance smoke.

The current tree retains no root scripts package, training package, former
Signals package, Phase D implementation package, or executable legacy score
producer/consumer.

## 3. Preserved product behavior

Retirement does not remove these current capabilities:

- raw news, source breakdown, and deterministic morning briefs;
- raw news-volume observations and title/date event sequences;
- provider-native sentiment and investor-profile risk data;
- current price, fundamentals, macro, portfolio, report, memory, and scheduler
  infrastructure;
- caller-supplied option-pricing mathematics; and
- current agent bridges and Tool Catalog entries that remain in the registry.

No retired score is replaced with a default neutral value. Where an old numeric
impact has no honest successor, the current contract uses typed unavailable
state or removes the unsupported field.

## 4. Data and secret boundary

This source retirement does not delete or mutate production
`news_article_scores` rows. It also does not read, copy, change, hash, disclose,
or delete the contents of `config/scoring_keys.txt`.

Those disconnected bytes have no runtime authority after the cutover. Their
physical deletion or any justified research-only preservation requires a fresh
exact manifest and separate explicit user approval. Runtime reconnection is not
an allowed disposition.

## 5. Future re-entry gates

Future RL, Signals, provider-backed option estimates, or on-demand analysis
must begin from a new reviewed design and current data/provider contracts. They
must not restore old modules merely as scaffolding.

A future Signals design requires at least:

1. a written hypothesis and target decision;
2. source-labelled and freshness-aware inputs;
3. reproducible training/evaluation data;
4. out-of-sample validation;
5. explicit kill criteria; and
6. evidence and UI contracts that distinguish facts from inference.

Provider-backed estimates additionally require current entitlement, pricing,
provenance, scheduling, and spend-control decisions.

## 6. Durable gates

- Current source, tests, app code, configuration, and runbooks contain no
  runnable reference to the retired implementations.
- Historical documents may retain dated paths only when clearly historical;
  they cannot serve as current operator instructions.
- Default collection and canonical runtime remain green under the reviewed
  `+18/-263` ledger.
- Production databases and local secrets remain outside source-retirement
  commits.
- Any future re-entry is a new capability slice with its own specification,
  RED/GREEN tests, provider/data truth, and user-facing semantics.

## 7. Evidence chain

The exact consumer inventory, product rulings, node streams, mutations, and
admission artifacts are recorded in:

- [SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md](SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md)
- [2026-08-08-scripts-tranche-b-product-decision-design.md](../superpowers/specs/2026-08-08-scripts-tranche-b-product-decision-design.md)
- [2026-08-08-scripts-tranche-b-legacy-score-retirement.md](../superpowers/plans/2026-08-08-scripts-tranche-b-legacy-score-retirement.md)
- [2026-08-08-scripts-tranche-b-legacy-score-retirement.md](../superpowers/evidence/2026-08-08-scripts-tranche-b-legacy-score-retirement.md)

Git commit history supplies the removed bytes and their review lineage; no
working-tree archive is needed.
