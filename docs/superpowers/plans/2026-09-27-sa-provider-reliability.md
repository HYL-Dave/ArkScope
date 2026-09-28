# SA and Provider Reliability Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. Inline execution was approved by the user.

**Goal:** Repair interrupted SA acquisition and expose provider-specific collection outcomes without changing schedules, sources or payment policy.

**Architecture:** Keep the existing native admission authority. Treat proven missing browser tabs as interrupted, safely cleaned work, while retaining uncertain-navigation protection. Preserve request-owned IBKR diagnostics and display existing structured Finnhub results.

**Tech Stack:** Python, SQLite, WebExtension JavaScript, React/TypeScript, pytest, Vitest, Playwright.

**Spec:** User-approved scope in this conversation: SA stopping/cleanup and stuck-task status; IBKR denial/timeout/unknown and collapsible issues; compact health/FRED tables; Finnhub failed symbols and partial-success counts. LLM article classification is explicitly deferred.

## Global Constraints

- Isolated worktree; production reads only until a fresh cutover pause is confirmed.
- No schedule, quota, provider, credential, payment, or subscription changes.
- No live requests to SA, IBKR or Finnhub during offline verification.
- No automatic age-based release of unknown native work; terminal evidence or explicit recovery is required.
- Preserve partial stored results; never turn unknown completion into success.
- Independent review and frozen full regression before integration; do not push.

## Review Focus

- Firefox and Chrome missing-tab errors must match the owned tab, not unrelated error text.
- Ambiguous tab-removal failures must retain the ownership/recovery guard.
- Late IBKR callbacks from another request must not establish this request's completion.
- Successful empty Finnhub responses must not be classified as failures.
- Narrow tables must remain readable without clipping status or changing numeric values.

## Task 1: SA Interruptions and Status

Files: `extensions/sa_alpha_picks/background.js`, acquisition popup, `src/sa/company_collector.py`, acquisition status API/types, `SAAcquisitionNotice.tsx`, targeted SA tests.

- [x] Reproduce missing-tab cleanup and 90-second polling in failing tests.
- [x] Recognize exact browser missing-tab errors; stop before further navigation; release only confirmed cleanup.
- [x] Add sanitized outstanding-task status and tests. Absence of live browser evidence must not imply running or idle.
- [x] Run SA Python and real browser regressions, then commit independently (`882b8daf`).

## Task 2: IBKR Request Outcomes

Files: `data_sources/ibkr_source.py`, `src/news_normalized/ibkr_runtime.py`, IBKR adapter tests, `NewsStorageSection.tsx` and tests/locales.

- [x] Add offline real-wrapper tests for denied requests, timeout, successful empty responses, and late unrelated callbacks.
- [x] Preserve request-specific outcome codes and partial headlines without retries or increased request rate.
- [x] Display typed reasons; make the issue list collapsible and initially closed.
- [x] Run IBKR worker and UI regressions; backend committed separately (`783a910f`).

## Task 3: Provider and Macro Display

Files: `DataSourcesSection.tsx`, `MacroStorageSection.tsx`, settings CSS, locales, component/browser tests.

- [x] Add tests for Finnhub per-symbol outcomes, empty success and partial storage counts.
- [x] Render structured request summaries and failed symbols; improve table density without altering values.
- [x] Verify desktop/narrow screenshots, component tests and build; commit separately (`8af5c262`). Full translations gate is part of frozen verification.

## Task 4: Frozen Verification and Cutover

- [x] Update acquisition documentation and evidence with exact findings and remaining limitations.
- [x] Independent branch review, targeted corrections and re-verification, including the final `4b4d2c9d` compatibility fix.
- [x] Freeze product commits at `4b4d2c9d`; complete offline backend (13,842 passed / 11 live skips), frontend (2,097), desktop (8), browser (24 + 16), build and i18n gates passed.
- [x] Fresh operator pause, latest backup/integrity checks and local fast-forward integration completed; formal Firefox rebuilt and post-merge smoke passed. See the 2026-09-28 cutover receipt.
- [ ] Restore collection promptly and distinguish local verification from observed production completion.
