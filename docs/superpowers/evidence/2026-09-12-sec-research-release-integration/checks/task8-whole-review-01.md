# Task8 Whole-Change SEC Release Review

## Verdict

**Source assessment: needs fixes. Ready to merge: with fixes and the pending frozen verification gate, not approval to merge now.**

Findings: **0 Critical, 1 Important (new), 1 Minor (deferred M1 retained)**. Diagnostic/build observations below are not additional product findings. The Important finding breaks a supported delegated SEC invocation path despite the three tools being present in its inventory.

Reviewed range: `c997a6c9817b80857ba7211989cdf6412d3b1003..a77a7c2e7cb1bb1b8d2b92cd4cfb129f299f6687` in `/tmp/arkscope-research-output-boundary`. HEAD was read back as the requested head before report publication. `W` below means `.superpowers/sdd/2026-09-12-sec-research-release-integration`.

## Findings

### Important I1: Make Delegated SEC Dispatch Safe Inside The Anthropic Parent Loop

**Primary location:** [src/agents/anthropic_agent/tools.py:1315](/tmp/arkscope-research-output-boundary/src/agents/anthropic_agent/tools.py:1315), the synchronous fallback from `execute_tool_async`; related new SEC sync entry at `src/agents/anthropic_agent/tools.py:1727`.

The main Anthropic producer now correctly awaits direct SEC tools, but its delegation branch still enters the synchronous subagent runner on that same event-loop thread. When `deep_researcher` is configured to use an Anthropic model and the child calls any of the three SEC tools, the child reaches the new `asyncio.run(execute_tool_async(...))` bridge while the parent's event loop is running. Python rejects that call before `invoke_sec_tool` can execute. The surrounding exception handler converts the failure to an error result for the child, so inventory inclusion does not provide working SEC research on this supported route.

Static call-path evidence:

1. `src/agents/anthropic_agent/agent.py:549`: `run_query_stream` executes `await execute_tool_async(tool_name, tool_input, dal)`.
2. `src/agents/anthropic_agent/tools.py:1315`: a non-SEC name, including `delegate_to_subagent`, immediately calls synchronous `execute_tool` without an executor or an awaitable child dispatch.
3. `src/agents/anthropic_agent/tools.py:1541` and `:1273`: the delegation mapping calls `_dispatch_subagent`, then synchronous `dispatch_subagent`.
4. `src/agents/shared/subagent.py:298` and `:309`: configured `subagent_models` overrides are supported. The `deep_researcher` inventory includes all three new SEC names. `dispatch_subagent` selects `_run_anthropic_subagent` inside inherited output/auth scopes.
5. `src/agents/shared/subagent.py:439` and `:529`: that child imports and calls synchronous Anthropic `execute_tool` for the returned tool-use block.
6. `src/agents/anthropic_agent/tools.py:1727`: the new SEC branch calls `asyncio.run`, still on the parent's event-loop thread.

**Impact and calibration:** This is an invocation failure for an admitted configuration, not a hypothetical missing registration. It violates the replacement/invocation requirement, including spec acceptance item 11. It does not establish damage to captures, credential exposure, broken direct SEC calls, or failure of every provider/model combination. The default `deep_researcher` model is OpenAI; the specific trigger here is an Anthropic parent with an Anthropic-configured child. Pre-existing synchronous delegation limitations for other combinations are not counted as new findings.

**Why the retained tests do not settle it:** `tests/test_subagent.py:56` constructs and checks both filtered inventories but does not invoke a required SEC tool through the parent/child loop. Its child tool-loop test at `:379` patches `execute_tool`. The real Anthropic adapter helper in `tests/test_sec_research_tool_adapters.py:49` deliberately runs the sync entry through `asyncio.to_thread`; the new release workflow uses that helper. `tests/test_sec_research_native_dispatch.py:21` exercises real direct parent SEC calls, not delegated calls. Those are useful distinct owners, but none exercises this failing composition.

**Proposed repair:** Preserve the configured provider/model/auth/effort choices and required tool inventory. Give delegated execution an owned async path, or move the entire synchronous child run into a context-propagating worker with explicit cancellation, resource cleanup and join semantics. Do not solve this by dropping SEC tools, changing model defaults, permitting nested loops, or abandoning a worker when the parent terminates.

**Proposed focused verification, not executed:** Use the existing isolated auth/generated-store fixtures and injected Anthropic SDK responses to run the actual async parent, a `delegate_to_subagent` turn, and an Anthropic child making each of the three real SEC calls. Keep production parent/child/tool dispatch intact. Assert that complete expected SEC envelopes reach the child model, stored/pinned calls enter neither acquisition factory nor transport, and direct calls/optional-tool filtering remain positive controls. If the repair introduces an executor, also check inherited output/auth authority and cancellation joining before the parent operation lease is released. Coordinate this owner with the controller before executing anything; no reviewer probe or runner was launched.

**Confidence:** High from the complete static call path; not represented as a newly reproduced runtime failure.

### Minor M1: Count Factory Entries In The Interrupted Stored-Read Workflow

**Locations:** `tests/test_sec_research_release_workflow.py:87` and `:251`.

The workflow acquisition context manager has no entry counter. Following the interrupted refresh, the test snapshots and compares metadata transport calls, but it would still pass if a stored read entered and closed acquisition without issuing a request. That misses one part of the explicit zero-acquisition contract in this particular interrupted-state composition.

**Disposition:** Retain as a nonblocking coverage improvement, not a demonstrated product defect. I read the full workflow and the existing owners rather than relying on its earlier approval. `tests/test_sec_research_tool_service.py:59` counts both acquisition entries and transport calls for healthy stored/pinned facts; `:85` does so for cursor continuation, and `:271` forbids configuration/permission acquisition on the absent stored-only runtime. The service's lazy acquisition branches also separate stored/pinned queries from refresh. These controls materially limit the risk, but do not make the interrupted workflow's missing assertion disappear.

**Proposed repair:** Record entries in this fixture's `acquire`, snapshot that count after the failed refresh, and assert no increase through stored reads and retained-citation reopening. Keep the existing transport, orphan accounting, candidate-set and exact-value assertions. No source or test was edited during this review.

## Scope And Method

The brief was read first. I used the supplied current-source package, its 210-path inventory and 74-commit list, then bounded changed-hunk and current-source reads across the ownership groups below. I did not regenerate the diff or move the checkout. The smaller package excludes only the 1,685 archived evidence/scratch paths from the unfiltered package; it is not a last-task-only source selection.

This is a broad interaction review, **not a claim that every line of the 37,371-line current-source package, every old deleted implementation, every test body, or every byte of the approximately 16.7 MB unfiltered evidence package received literal review**. Runtime owners and risky compositions received the deepest reads. Test bodies, collateral removals, current ancillary documentation and retained evidence were sampled or searched where indicated. Prior task approvals informed navigation, not a presumption that their code could not be wrong.

Requirements/context read included the current substrate spec, the current integration plan and task gates, `docs/design/SEC_RESEARCH_OPERATIONS.md`, all current release `RULINGS.md` entries, relevant progress/ruling history, and the indicated publication, Task7/fix/rereview, Task8 workflow/report and census adjudication reports. The new `W/task8-cross-task-validation.md` and `W/task8-final-proof-readback.json` were also read. Their distinction between ownership mapping, retained inverse binding and a pending complete-run result is appropriate. Ancillary output-boundary/citation and cleanup documentation was consulted selectively; not every historical plan/report was read in full.

Review actions were static file/diff/search reads, read-only Git status/HEAD checks, JSON evidence projections, raw-log readbacks/counts and two existing screenshot views. No subagents, imports/execution of product code, collection, suites, behavioral probes, provider/model/network calls, database opening, configuration/environment/token reading, installation, server/browser launch, runtime activation or App action occurred. The only authorized write is this report. Git source/index/branch state was not changed.

## Checks And Assessment By Area

### Issuer, Tool And Query Contracts

- Read `issuer_store`, `issuers`, `tool_service`, `runtime`, `tool_execution`, the new tool wrappers and changed query/service/store paths. Ticker resolution remains issuer metadata with explicit absent/mismatch/ambiguous outcomes, not a lifecycle rename writer. Inputs are validated before resolution/acquisition, and continuation retains the original issuer/snapshot/filter binding.
- The three tools are registered under `analysis` and use the closed six-field result policy. The new adapters, both OAuth allowlists, subagent inventory changes, current skill replacements and tool-catalog changes were checked. Required inventory presence is covered independently; I1 is the important distinction between that presence and executable composition.
- Stored/pinned/continuation paths avoid the lazy acquisition branch; refresh cannot retarget pins and failed refreshes do not borrow an earlier success. Current SEC acquisition uses the managed profile transport path, not a newly introduced SEC environment credential fallback.
- Reviewed exact-value preservation in the SEC query/result/citation path: numeric fact values remain Decimal-derived TEXT, source hashes and snapshot references remain intact, and document ranges are UTF-8 half-open ranges. No general bridge output-budget increase was found in the changed reducer/admission paths.
- Document transfer limits remain 32 MiB wire/128 MiB decoded. The scheduled metadata limit is separately bounded and is not a global document/bridge cap change. The adjustable 100 GiB capture default remains a budget, not an allocation or a whole-application disk ceiling.

### Output Boundary And Four Direct Channels

- Read shared output-boundary/event policy owners and changed Anthropic/OpenAI API, ChatGPT OAuth, Claude SDK OAuth, auth-binding and model-catalog integration. Successful structured tool output is admitted by declared result policy; diagnostics are treated separately. Unknown/coercion-prone output is rejected rather than accepted by `str` fallback. Exact in-scope credential checks do not rely on high-entropy-looking public identifiers being secrets.
- Read the independent 56-tool policy roster and representative positive/negative policy tests. The explicit ordinary JSON, SEC envelope and declared-text policies retain legitimate decimal strings, URLs, hashes, cursors and dates while rejecting malformed/untrusted output. This is scoped policy review, not a comprehensive new security scan.
- Read the compressor reducer/transcript/summary changes. SEC envelopes are retained whole or become explicit bounded failures, rather than arbitrary head/tail JSON fragments. Credential/output authority follows summary and child scopes without changing routing/default selection in the inspected changes.
- Traced complete direct-channel tool outputs into citation extraction before preview slicing. OpenAI's owned hooks/queue drain retain completed evidence through later cancellation and join the same worker before terminal completion. Checked native-dispatch and selected trace/test owners as well as source; this does not prove the untested delegated composition in I1.

### Citations, Persistence And UI

- Read citation validation/reopening, references, tool trace, Research run/thread persistence and both executor/legacy-query lifetime changes. Fact/catalog references validate original source/hash/pointer bindings; document references validate immutable capture, extraction and byte bounds. Reload does not silently substitute latest observations.
- Durable tool identity uses call IDs, including same-name concurrent/end-only completions; legacy ID-less rows have a separate fallback rather than consuming identified calls. Terminal recovery consults retained events, not only a preview or a limited page of recent events.
- Read operation-lease coverage through tool-result, event and assistant-message publication. The selected test body `test_research_result_lease_reaches_durable_commit` checks exclusion at all three phases for normal/error/cancel outcomes. Retained-reference readers include archived/message/event-only evidence and fail closed on malformed or incomplete roots.
- Read changed frontend API citation encoding, reducer, evidence selection and citation reader behavior. References are independent of the 500-character preview; source selection follows its owning transcript/run; invalid/missing source data is not replaced with refreshed content. Source text is rendered as text, not active filing HTML.
- The combined Task8 workflow uses production extraction, actual event/message stores, real export/restore and cleanup with generated inputs. Independent decimal/UTF-8/hash checks and positive cleanup controls prevent an empty self-consistent round trip from being sufficient. Its event/model harness is not a live full-producer run or a four-channel proof.

### TOC And Document Boundaries

- Read structural TOC recognition and the query/extraction changes. Exclusion requires bounded structural evidence and heading/link relationships; it does not select duplicate headings solely by position or relax ambiguity checks. Full extracted text remains available.
- Extraction v4 applies to new captures; retained prior-version evidence is not rewritten. Passage sizing/continuation preserves complete citation data and bounded UTF-8 passages rather than truncating serialized envelopes.

### Capture Recovery, Export And Maintenance

- Read the operation lock, publication recovery, portable operations, maintenance, references, schema administration and CLI owners. Shared/exclusive admission is owner-aware across thread/task/process boundaries; copied context does not grant another owner lock reentrancy. No startup schema reset/migration lane is introduced.
- Publication alias recovery is restricted to the proven canonical object/staging hardlink relationship, including identity/hash/link-count/path checks and rechecks. The strict general inventory is not weakened to accept arbitrary hardlinks. Accounting preserves interrupted/orphan charges, and cleanup remains explicit.
- Export takes SQLite backup contents, then derives/verifies its inventory from the backup, not a racing live database. Read-only source backup handling protects a stranded WAL; source/output overlap and sidecar namespace checks precede publication. Create-only destination/final-marker handling avoids claiming success for partial bundles.
- Bundle scope is the whole market SQLite database plus SEC capture objects. Independent profile/SA stores are not silently bundled. Retained Research profile references can reopen a moved market/capture root, but that is not whole-installation portability or disaster-recovery validation for a real user store.
- Cleanup re-observes approved state under an exclusive root lease, checks all retained reference classes and fresh profile state, and preserves protection through failure auditing. The selected retention test includes historical facts, issuer maps, archived Research and event-only references plus an unreferenced positive control. Unknown/partial roots fail closed rather than being treated as an empty namespace.
- Long hash/copy/unlink/directory durability work is outside the ordinary market writer transaction; short validation/accounting/schema mutations retain transaction protection. Current schedule checkpoints are now part of the bundle/admin verifier, closing the cross-task contract addition identified in the current inverse readback.
- Reset/uninstall is explicit, backed up and restricted to known owned objects/dependencies. Unknown owned schemas may produce an approved raw safety backup but remain blocked, never acquiring prefix-based DROP authority. Profile/market output-file and sidecar collisions remain protected. No destructive HTTP/model/UI maintenance interface was added.

### Schedule And Settings

- Read scheduled execution, checkpoint validation, recent/full receipt changes, runtime/scheduler/audit integration, Settings schedule observation and completion refresh behavior. The new schedule remains off by default at 1,440 minutes; it does not inherit the retired enabled flag or get enabled by a capacity edit.
- Current membership is freshly observed, bounded and distinguished from SEC issuer syntax. Unsupported observed symbols such as `BRK B` remain accounted unresolved members without causing arbitrary normalization or discarding independent valid issuers. Scheduled resolution uses its captured issuer-map observation rather than a later map.
- The 500-issuer/1,001-admitted-request/900-second bounds, remaining-deadline checks and managed governor apply to recent submissions/facts only. Historical traversal/document acquisition are not introduced by the scheduler. These are application attempt/deadline limits, not a claim of measured live throughput or instantaneous preemption.
- Independently checked the repaired first-matching storage stop reason, map binding and terminal membership/CIK partition rules. Read the actual interleaved-map test body and runtime/test inventories. A partial batch retains successful observations and independent last-completed state; the current job audit uses its existing failed terminal vocabulary rather than recording partial as succeeded.
- Schedule completion refreshes stored status/capacity without clearing reader pins, pagination, selected issuer or dirty capacity draft. Settings and schedule status make scoped counts and partial/unresolved results visible instead of declaring whole-universe completion.

### Collateral Removal And Scope Control

- Inspected changed removal boundaries for the retired SEC filing tool, unused source classes/factory, the unused file backend, local backend/DAL construction and the ineffective local-news routing switch. Current normalized/legacy-local news writers remain explicit; latest ingest telemetry replaces stale mirrors even if later health work fails. The SEC removal does not imply deletion of prices/news/SA/financial-cache contents or lifecycle/history records.
- Registry counts are supporting assertions, not the sole replacement evidence. Current subagent defaults were explicitly checked and not treated as license to change them to bypass I1. Source provider removals are not evidence that related actual stored settings/rows have been disposed of.
- Current-source census remains `review_required`, not automatically clean. I read the final checkpoint adjudication: 70 new candidates have current locale consumers or intentional CLI/scheduler entrypoints; 671 uncertainty IDs include 541 positional mappings and 130 remaining records. The latter include 80 SQL modeling records, not 80 demonstrated runtime SQL failures. Five coverage reductions correspond to the named earlier physical removals; no dependency metadata drift is claimed by the reconciliation.
- C12/C15/C20, CENSUS-I18N-001, CENSUS-SQL-001, deferred C21 and actual-store disposition remain independent open work. Neither heuristic candidates nor earlier acceptance grants deletion authority. This review does not close those queues.

## Evidence Readback And Limits

The following are **retained results**, not suites executed by this reviewer. I read the named worker/reviewer reports and the final raw log summaries for these rows; I did not independently re-count every JUnit node or hash every archived artifact.

| Retained evidence | Observed result | Meaning/limit |
| --- | --- | --- |
| `W/task6-publication-covering-frozen-01/output.log` | 1,092 passed | Publication covering checkpoint, not the pending final whole backend |
| `W/task7-fix1-27-backend-cover/output.log` | 2,493 passed | Current schedule fix covering run |
| `W/task7-fix1-28-settings-cover/output.log` | 449 passed, 28 files | Affected frontend coverage, not an independent added release total |
| `W/task8-workflow-focused-final-01/output.log` | 9 passed | Two combined workflows and seven existing owners |
| `W/task8-controller-frontend-full/output.log` | 1,833 passed, 126 files | Fresh complete frontend receipt; diagnostics retained |
| `W/task8-final-typecheck/output.log` and `task8-final-build/output.log` | Typecheck/build commands complete in retained receipts; Vite built output | No fresh build by this reviewer; chunk warning remains |
| `W/task8-final-proof-readback.json` | Current-source binding of 13 schedule inverses and publication proof; 39 existing maintenance definitions preserved | Readback of retained proofs, not newly run mutations |
| `W/task8-cross-task-validation.md` | Explicit mapping to retained complete-gate owners | Mapping is not a gate result; collected/executed identities and 12 live-only skips still require final reconciliation |

The Task8 report retains its two fixture setup mistakes: paragraph-only document index versus text-page status expectations. They are not relabeled product REDs. Passing focused counts above overlap and must not be summed into a full-suite claim.

For `W/task7-fix1-29-browser-final/browser/browser-results.json`, I read the scope/error fields and projected measurements for all four locale/viewport cases. Retained results report no console/page/external-request errors, no measured clipping/overlap, stable dirty budget and partial schedule status. I visually inspected only `zh-Hant-390x844-status.png` and `en-1280x960-controls-source.png`: the inspected SEC content was legible without incoherent overlap. I did not inspect all 16 images, rerun Playwright, independently validate every request/body hash, or certify all Settings health. Mobile schedule horizontal scrolling is an intentional existing table behavior in this evidence.

## Deferred Diagnostics And Build Observations

**N1 / React act:** A read-only count of the final full frontend raw log finds **1,016** lines matching the act-environment/unwrapped-update warnings. Sample contexts include existing overlay and PortfolioActivity owners; this does not assign every warning to an unchanged component. These warnings reduce confidence that every asynchronous UI assertion is synchronized and make failures harder to notice, but the sampled messages do not identify a specific SEC state, citation or schedule defect. Retain as nonblocking test-harness debt, with targeted owner attribution and awaited updates as follow-up; do not suppress them or call the output clean. Earlier rulings were not used as immunity.

**i18next diagnostics:** The inspected messages are initialization/language-change diagnostics. No concrete new missing-key or wrong-locale failure was established by these samples; current locale consumers and two rendered samples support the affected paths. Keep the raw output. Neither that observation nor the passing frontend summary resolves the broader census i18n uncertainty.

**Build size:** The final raw build log reports **1,201.53 kB JavaScript, 360.97 kB gzip**, and the greater-than-500-kB chunk warning; CSS is 104.03 kB. This is a real loading/parse-cost concern, not a clean build-output claim. No measured launch/interaction budget violation or new functional SEC failure was supplied or established in this static review. It remains nonblocking performance debt for measured splitting of substantial screens/dependencies, not grounds to raise the warning threshold or perform unrelated refactoring in this review.

**Browser scope:** Earlier omitted unrelated fixture endpoints are not product repairs. The final fixture explicitly substitutes generated unrelated responses and supports SEC/shared-scheduler behavior only. This distinction remains necessary even though final retained console/page errors are empty.

## Strengths

- The implementation generally places authority and durability checks in shared owners rather than relying on UI conventions: explicit schema verification, lazy acquisition, closed result admission and complete retained references.
- Publication/maintenance boundaries consider partial failure, source identity, foreign dependencies and audit durability. Quota exhaustion is not treated as authorization to delete retained evidence.
- The verification structure contains meaningful real-store/service/adapter paths, independent exact-value assertions, adversarial/inverse owners and disclosed failed attempts. The cross-task validation note correctly leaves the complete gate pending instead of manufacturing it from reviewed examples.

## Recommendations And Final Assessment

1. Have a separate source worker address I1 and retain its real parent/child invocation regression owner. Coordinate any focused probe before execution. A passing unchanged complete suite alone would not refute the missing composition described here.
2. M1 may remain explicitly deferred; it does not need to block the source repair or become an invented acquisition bug. Retain the diagnostic, build and census limitations with their existing owners.
3. After any repair and review, let the controller run the single frozen complete backend suite alone, reconcile exact node/skip identities and bind final evidence to the resulting source. Do not report a final whole-backend pass before that occurs. Current frontend/census/inverse readbacks are acknowledged as complete controller work, not pending solely because this reviewer did not rerun them.
4. Keep implementation acceptance separate from merge, actual-store backup/reset/disposal, SQLite/runtime activation, enabling acquisition, and any live SEC/model canary. None is authorized by this report, and actual stores were not examined.

**Assessment:** The broad source design and inspected recovery/citation/schedule interactions are substantially aligned with the current requirements, but I1 prevents an unconditional source-ready verdict. With that repair, its focused evidence, and the controller's frozen complete verification still outstanding, this review grants neither release/merge readiness nor deployment authority.

No blocking ambiguity remains for delivery of this report. No source fix, test runner, database/runtime operation or branch/index mutation was performed. At the final pre-publication readback, Git still showed only the controller's three modified docs and two untracked evidence directories; this report is the reviewer's sole file write.
