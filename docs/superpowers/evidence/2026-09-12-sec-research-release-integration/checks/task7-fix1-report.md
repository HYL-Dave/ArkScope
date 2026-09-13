# Task7 Fix Round 1

Commit: `883b0185b1b044ff6a94a7690cb85253fc7c82e5`
Fix base: `936ede10f04c370bf2322ee70833f9e0f29b7a44`; branch: `codex/sec-research-integration`.
Original Task7 context remains in [task-7-report.md](task-7-report.md). This report addresses adopted review I1-I3 only.

## Scope And Contracts

Exactly five committed files: `src/sec_research/{issuer_store,schedule_store,scheduled}.py`, `tests/test_sec_research_schedule.py`, and `tests/test_sec_research_schedule_runtime.py`. Full paths, tested/committed hashes and index readback: [task7-fix1-handoff.json](task7-fix1-handoff.json).

- I1: choose the first *matching* storage gap as stop reason. Real submissions rate-limit followed by Company Facts capture-budget/free-space rejection now durably records `failed` or `partial`, preserves both source gaps, earlier acquisition and independent last-completed status, and leaves subsequent CIKs deferred.
- I2: `IssuerStore.resolve(issuer, *, observation=None)` uses the supplied observation; omission preserves latest-map behavior for existing callers. Scheduled resolution supplies the exact returned refresh observation recorded by the batch. Twelve interleavings cover successful/failed captured maps against changed/failed/interrupted foreign maps, immediately after refresh and between members. Dispatch, ambiguity/missing gaps and counters remain bound to the captured map. This issuer-store interface is the one additionally required production boundary; no lock or identifier relaxation was added.
- I3: available terminal membership must equal resolved rotation members plus unique unresolved members; resolved CIKs must equal attempted plus deferred CIKs. Rotation members are unique; explicit CIK aliases must match their row CIK. Existing outcome partition then makes nonempty `succeeded` require every current member to be confirmed. Well-shaped uncovered membership is rejected by validator, record/status, admin/export and scheduler adapter (`sec_schedule_batch_invalid` / `sec_schedule_result_invalid`).
- Running checkpoints remain exempt from terminal completeness. CIK dedup, unresolved `BRK B`, and failed-map historical rotation remain valid. Resolution abort before dispatch explicitly accounts every affected member as unresolved; existing map-lease contention produces `issuer_map_busy`, zero requests, retained fair rotation, and no fabricated map ID. Invalid prior records are rejected, not silently repaired.
- Unchanged bounds: default-off 1440-minute schedule; fresh bounded observed membership; 500 issuers, 1001 admitted metadata attempts, 900-second deadline; 16 MiB per response and remaining-deadline timeout. Admission/checkpoint cancellation is not instantaneous hard preemption. Recent submissions/facts only; full-history receipt continuation stays separate. Metadata attempts are not confirmed live HTTP. Stored latest reads, pinned IDs and dirty budget remain stable. No schema/job enum/new generic lock, old-key inheritance, Task6 publication or Task8 change.

## Serial RED/GREEN And Covering

All 29 create-only runner receipts, including 14 nonzero exits, exact commands, command hashes, XML/log hashes, failed case names, dispositions and explanations are in [task7-fix1-receipts.json](task7-fix1-receipts.json). Every raw failure is retained; guards unchanged.

| Proof | Receipts | Result |
| --- | --- | --- |
| I1 corrected real mixed stop | 03 -> 04 | 4F -> 5P |
| I2 immutable map interleaving | 05 -> 06 | 12F -> 33P |
| I3 terminal witness and abort accounting | 07 -> 08 | 28F/1P -> 100P |
| Final focused backend, 43 files | 27-backend-cover | 2493P |
| Actual Settings/shared schedule affected frontend, 28 files | 28-settings-cover | 449P |
| Existing actual-service browser, restored fix source | 29-browser-final | 4 cases, 16 screenshots |

Receipts 01 (4F) and 02 (3F/2P) retain initial fixture limitations: budget=0 was invalid configuration rather than real admission exhaustion, and repeated identical bytes correctly retained five catalog observations, not ten. Corrected test setup used budget=1/free-space=0 and repeated original-source RED before GREEN. No runner modification or suppression.

Added 45 cases in seven test functions: core 36 -> 77; runtime 19 -> 23. Existing test ASTs unchanged, no test removal. [task7-fix1-proof-readback.json](task7-fix1-proof-readback.json) contains exact test inventory and guard hashes. Focused backend includes all SEC service/store/query/tool/document/operations/admin/reference owners plus transport, active universe, scheduler/state and macro integration/outcomes. No full backend/frontend, build or literal rerun in this backend-only fix; controller owns the final integration gate.

## Inverse Provenance

- [task7-fix1-inverses.json](task7-fix1-inverses.json): five new final-source inverses, receipts 09-18, targeting mixed-stop selection, dispatch argument, resolver observation, terminal coverage, and aborted-membership accounting.
- [task7-fix1-refreshed-inverses.json](task7-fix1-refreshed-inverses.json): four changed-target final-source refreshes, receipts 19-26, targeting actual historical-pointer traversal, erased last acquisition, stale membership reuse, and rejected observed space symbol.
- [task7-fix1-inverse-artifacts/](task7-fix1-inverse-artifacts/): nine exact replacement recipes with selectors and 20 immutable original/mutant source artifacts (ten pairs). Every mutant failed its intended assertion; each exact restored source passed. Recipe substitution, source artifacts, before/mutant/restored hashes and exits were read back.
- Earlier `enable-by-default`, `drop-partial`, `reset-pins`, `reset-draft` target sources are unchanged. Their original Task7 recipes/artifacts and command hashes/exits were explicitly read back in [task7-fix1-proof-readback.json](task7-fix1-proof-readback.json), not reexecuted. Original checkpoint proofs remain separate from these restored fix-source executions.

## Browser Freeze

[task7-fix1-29-browser-final/browser/](task7-fix1-29-browser-final/browser/) retains results, API request inventory, source/body inventory, server command, logs and all screenshots. [task7-fix1-browser-proof.json](task7-fix1-browser-proof.json) gives source/helper/file hashes, verified body hashes/lengths and exact collection command. Existing workflow rerun once: en/zh-Hant at 1280x960 and 390x844; actual Settings SEC panel/shared scheduler with real API/service/stores and injected bytes.

Same toggle/interval/RunNow, dirty-budget=150, pin/capture/text/catalog and no-completion-issuer-read assertions passed. Each schedule has 5 admitted metadata attempts, 2 attempted CIKs, 1 confirmed, 1 failed/partial, 1 unresolved, 52 filings/45 facts, and zero history/document requests. Total inventory: 23 metadata attempts (3 separate full-history seed + 4x5 recent), 2 seed document attempts, 20 generated bodies and 5 typed failures; 168 loopback API responses were 200. No external browser requests, console errors or page errors. Live confirmed HTTP: zero.

Viewed zh-Hant mobile/desktop status, en desktop controls and mobile pinned screenshots; no SEC overlap/clipping. The existing mobile schedule table scrolls horizontally. Unrelated original Task7 run23 request-failure/loading noise was omitted fixture endpoints, not repaired product. The unchanged neutral fixture declares twelve generated unrelated endpoints in results/proof, including price coverage, provider, news and macro endpoints. This is SEC/shared scheduler evidence, not whole Settings health. Existing generic RunNow `started` notice remains.

## Handoff And Limits

N1 retained: focused frontend emitted 37 act-environment warnings, same mechanism as accepted earlier evidence; controller reports old/new full runs each had 1016 warnings. Raw diagnostics remain; no suppression, frontend infrastructure rewrite or new size claim.

No remaining concrete I1-I3 issue found. Scoped independent re-review, Task8 integration and final frozen full gate remain controller work. No live throughput/production behavior claim, production DB/config/credentials/provider access, installation, App restart, live destructive action, merge or push.

Commit uses per-command disabled hooks only. [task7-fix1-handoff.json](task7-fix1-handoff.json) verifies commit parent, exact five-file scope, tested/worktree/committed source equality, all receipt hashes/exits, clean owned source and empty index. Only controller docs/evidence remain dirty, untouched and unstaged. All runner sessions finished and fixture servers stopped; sole runner/index ownership returns to controller.
