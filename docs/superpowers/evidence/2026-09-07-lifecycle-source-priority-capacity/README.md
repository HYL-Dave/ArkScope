# Source Priority And Larger Local Capacity

This is an offline amendment to `2026-09-07-lifecycle-source-context`, on the
existing unmerged tracking-first worktree. `verification.json` and the final
seal are the admission record. Earlier packets are historical and unchanged.
This does not declare the production lifecycle workflow ready for hand testing.

## Product Meaning

- Massive/EODHD structured listing observations remain primary. Web/news research
  supplements unresolved tracking questions; it does not replace their authority.
- Search and analysis no longer require an SEC-first hop. Exchange/issuer notices
  and established financial reporting obtained by provider Web/news search are
  useful evidence of what actually happened. There is no mandatory publisher or
  SEC quota. Existing provider/auth/model routing and zero fallback remain intact.
- SEC proposals, conditions and warnings are useful prospectively. An explicit
  SEC completion notice can also support a retrospective conclusion. Filing,
  announcement and effective dates are separate; filing alone is not completion.
  This is consistent with the distinction between contract execution and
  consummation under Item 2.01 in the [SEC's Form 8-K guidance](https://www.sec.gov/rules-regulations/staff-guidance/compliance-disclosure-interpretations/exchange-act-form-8-k).
- Exact security identity, effective timing, active/OTC contradictions, source
  passage verification and explicit human adoption remain mandatory. No rule
  turns an acquisition announcement into delisting or an alias to the acquirer.

The existing blanket action block for any unread candidate reference is NOT
removed. The user has been asked whether a clearly disclosed, unread supplemental
reference may coexist with an otherwise adequately supported human decision.
Until answered, `unread_source_count > 0` still blocks adoption. That policy is
separate from capacity and source priority. The existing Web JSON identity/locator
rule is also unchanged; it does not restrict Massive/EODHD structured evidence.

## Resource Contract

New preflight approvals bind 32 MiB of encoded HTTP body and 128 MiB after
content decompression per source. HTTP headers, transfer chunk framing and
TCP/TLS overhead are not counted as document body. The four-source limit,
eight source requests, redirect budget and 180-second model timeout are unchanged.
The shared source-reading deadline increases from 45 to 180 seconds and is bound
into the confirmation along with capacity. It is one bounded phase, not a fresh
180 seconds for every URL. Stored old options retain their original budgets.
This revision does not add a model-token limit or guess an unknown model capacity.

Captured text, selected model text, native model tokens and journal storage are
different quantities. Existing relevant/contrary-passage selection remains
traceable to full retained sources. Unknown or densely relevant text remains a
full input. No prefix clipping, top-K deletion, model substitution or retry is
introduced. A real model may reject oversized context; the pipeline must report
that rather than silently drop content or claim that 512 MiB fits a model.

The Linux benchmark supervisor samples child RSS every 25 ms and stops a child
observed over 4 GiB or 600 seconds. It is not an OS-enforced hard limit: sampling
can observe a small overshoot. These measurements are not a whole-App, arbitrary
PC, Windows/macOS, SDK subprocess or live provider memory certification.

## Corrections Required By Measurement

1. Legacy escaped-JSON hashing allocated source-sized strings and byte copies.
   Page hashing now uses standard JSON escaping in bounded character chunks,
   preserving the exact old canonical digests. Page storage uses native Unicode
   JSON; both old escaped and new encodings read back with the same fingerprints.
2. Full-range context and final prompt serialization made additional full-size
   Unicode copies. Full coverage now reuses retained text; prompt JSON preserves
   Unicode directly without changing its parsed content or selected ranges.
3. Finalization held a journal write transaction during expensive validation.
   Immutable sources are now read in short transactions and validated outside
   them. Final commit rechecks worker ownership, lease, cancellation, both model
   terminals, header binding and the exact source index before saving a result.
4. A later real-progress test found that polling decoded all growing source
   bodies under a read transaction. Both jobs failed with
   `web_recording_unavailable`. Running progress and current-review projections
   now omit uncompleted bodies that their DTO never used. Complete-result reads
   retain source checks while releasing owned read transactions before expensive
   decoding/validation. Cursor iteration no longer holds an implicit source read
   lock between bodies. The explicit transaction supplied by human adoption is
   still owned by its caller; its atomicity is positively tested, not weakened.
5. One complete-result read took 15.845 seconds, exceeding the frontend's former
   15-second default. An initial 60-second local receipt budget was also falsified
   by a later 77.027-second complete-result read. The six source-validating local
   detail/result/review/receipt calls now wait up to 180 seconds. Fake-clock
   controls cover an 80-second success, a stalled call's 180-second stop, exactly
   one request, and unchanged preflight / launch defaults. This is independent
   of source or model execution budgets and does not delay a prompt response.
6. A repeated sparse run still failed on the original five-second SQLite busy
   wait. SQL timing then measured 1.268/1.872-second source INSERTs followed by a
   29.239-second commit; even small schema-creation statements took several
   seconds on that filesystem. This is observed I/O latency, not proof of which
   other workload caused it. The Web journal's owned connections now wait at most
   45 seconds for a competing lock, below the unchanged 60-second lease. Source
   cancellation, caller-owned transactions and unrelated stores remain unchanged.
   Real two-connection tests scale waiting by 1/100 and
   cover commit, cancellation and a persistently busy database. They do not
   replace the full-size filesystem measurement or make disk stalls unbounded.
7. The 45-second reader deadline was shared across all sources, including time
   spent persisting earlier sources. Repeated workloads admitted only three of
   four sources despite an analysis terminal. That is not full-capacity success.
   New preflights now expose/bind a 180-second shared reader budget. Both changed
   capacity and changed reading time invalidate the earlier confirmation; the
   model timeout, number of requests and absence of retry/fallback stay intact.

No DDL, journal checksum format, write authority or database mode is changed.
The scoped busy-wait calibration does not replace moving expensive Python
validation out of transactions. There is no migration for this amendment.

## What Was Measured

`capacity-results.json` contains final sparse and dense runs, bound to the same
non-document source manifest as the full regression suites. Each uses the real
controller, real heartbeat, two simultaneous jobs and one temporary shared
journal. Each job retains four nearly 128 MiB four-byte-Unicode HTML documents.
Two simulated UI readers poll real controller projections during execution.
HTTPS and model replies are fake; this is zero provider calls and zero production
data access. The final reports record RSS, elapsed time, disk size, all observed
polls, both terminal statuses and the two search/two analysis phases.
Pollers stop only after actually reading a terminal result, not after merely
observing that a local worker exited. Both case IDs must have a successful final
poll below the 180-second receipt budget for capacity admission.

The final source-bound observations are:

| Workload | Retained sources | Peak child RSS (bytes) | Supervised elapsed (s) | Slowest result read (s) |
| --- | --- | --- | --- | --- |
| Sparse relevance | 2 jobs x 4 | 2,758,881,280 | 291.108 | 48.535 |
| Dense relevance | 2 jobs x 4 | 3,021,426,688 | 258.838 | 49.649 |
| Sparse plus 29-second held commit | 2 jobs x 4 | 2,624,987,136 | 560.690 | 119.048 |

Peak RSS is the larger of the sampled value and the child's reported high-water
mark. All eight sources and both terminal receipts are required in each row;
SQL/poll errors are zero. The controlled run observes 32.783 seconds of SQL wait.
Regression suites were also active during these measurements. These are stress
observations, not normalized performance comparisons or usual UI latency.
Final sparse jobs each retain 536,634,160 bytes and supply 192,796 bytes of source
text. Dense jobs each retain and supply 536,642,908 bytes. Neither figure is a
native token count; the fake model is deliberately not a context-capacity test.

- Sparse input retains about 512 MiB per job but supplies only the relevant and
  contrary passages plus their context. The exact retained/supplied byte counts
  are measured, not estimates of token use.
- Dense input makes every paragraph relevant and retains/supplies the same text.
  This adversarial case exercises local full-input allocation, not native model
  context acceptance. Both cases include terminal persistence and readback.
- `wire-results.json` measures an actual 32 MiB identity-encoded body through the
  source reader. Text and the final active-OTC statement are preserved. A declared
  32 MiB plus one-byte response is rejected before body reading, with no prefix
  returned as evidence.
- `sql-control-results.json` deliberately holds the eighth real source INSERT
  transaction for 29 seconds before commit, with the same two jobs and UI pollers.
  Downloads are already complete, isolating lock tolerance from the independent
  reader deadline. Admission
  requires an actually observed competing SQL wait longer than five seconds,
  no SQL/poll errors, both terminal receipts and RSS below 4 GiB. This controlled
  pause distinguishes wait-policy correctness from a coincidentally faster disk
  on a later run; it is not a claim to reproduce every filesystem failure.
- Twelve bilingual browser scenarios cover widths 1440, 390 and 320, both
  source-selection and source-failure disclosures. All 24 screenshots are
  nonblank and checked for overlap, clipping, overflow and runtime errors.
  Browser responses are fixtures; the production App is not started.

## Failed Experiments And Test Ledger

Historical experiment files are deliberately separate from final admission:

- Merely raising constants first crossed 4 GiB (4,314,103,808 sampled bytes).
  That initial supervisor did not save a source manifest; it is a diagnostic,
  not source-bound final proof.
- Streaming fingerprints/compact journal JSON reduced memory but a real shared
  journal run still failed one worker. This revealed the finalization lock issue.
- Densely relevant input independently crossed 4 GiB (4,299,841,536 bytes).
  Avoiding duplicate full-context strings and ASCII expansion resolved that case.
- The first progress-poll workload failed BOTH jobs despite prior non-poll
  success. It is retained, not concealed behind the earlier passing suites.
- The initial completed backend campaign had 6,689 passed / 12 skipped, with
  2,024 focused and 2,843 integration nodes. It predates the progress-read repair
  and is NOT used as final admission for the repaired code.
- A second campaign was intentionally interrupted with its clone restored when
  the 15-second UI receipt mismatch was found. Its 22 reported mutations are
  historical, not a substitute for the complete final campaign. Frontend abort
  fixtures were also corrected for jsdom's error realm before repeating RED.
- The third backend campaign passed 6,697 / 12 skipped, with 2,032 focused and
  2,851 integration tests and 26 named-owned mutants. It predates the journal
  busy-wait calibration and is preserved as historical, not final admission.
- The earlier polling harness could stop on worker exit before fetching the
  terminal response. Correcting it exposed 25-second complete-result reads and
  requires both observed terminal responses. Its earlier passing measurements
  are retained as historical. The subsequent sparse lock failure and timed SQL
  reproduction are also retained; they are not erased by later passing runs.
  The first post-calibration timed SQL run had no long commit, so that passing
  observation alone does not establish recovery from the earlier 29-second stall.
  The separate held-commit control supplies that particular comparison.
- The first held-commit probe paused the first source, consumed the existing
  shared reader deadline, and retained only one source per job. Its SQL/poll
  waits were successful, but it is NOT full-capacity admission. The final probe
  delays the eighth source INSERT instead and requires all eight retained sources.
  A repeat that delayed the eighth INSERT never reached eight sources under the
  old 45-second reader budget. These experiments motivated the separately named
  shared-deadline correction; final capacity requires all eight sources under
  the new, explicit 180-second budget, not merely a succeeded analysis status.
- The fourth backend campaign was stopped after 26 reported named-owned mutants
  when the shared-reader deadline issue was confirmed. Its clone is restored;
  it is not substituted for final regression of the 180-second preflight.
- The 180-second UI-budget RED was first invoked from the wrong Vitest root and
  collected zero tests; that command is not RED evidence. The corrected run
  collected 15 tests and failed eight before the product timeout was changed.
- Incremental RED results include an initially incorrect exception-class
  assertion, followed by corrected RED. One corrected lock RED was still
  finishing while source linecache changed; it is not a source-bound campaign.
  The independent whole-focus mutations and real shared-journal failures provide
  the stronger ownership evidence. The first seven progress tests were run
  from an external file before moving into `tests/`; they failed five named
  owners with two positive controls already passing. The current-review
  entrypoint was then added as a second parameter of the progress owner.

Final baseline/restored/focus/integration/full node lists are compared with the
prior packet. No prior nodes may disappear. Every mutation runs the entire
affected backend focus or entire frontend suite, and must fail its named owner.
The sealer verifies XML/JSON counts, each shard's file set, restored source hashes,
unchanged schemas, byte-identical prior packets, source-bound browser/capacity
results, build/typecheck/i18n checks and a synthetic-fixture-aware secret scan.

Final regression results are 2,037 baseline/restored focus tests, 2,856 integration
tests, 6,702 passed / 12 skipped in the complete backend, and 1,562 baseline/restored
frontend tests. The backend emits the same three edgartools deprecation warnings.
All 29 backend and six frontend mutants fail their named owners. Relative to the
previous source-context packet, the backend adds 39 nodes and frontend adds ten;
no prior node is removed or renamed. The final non-document snapshot contains
1,068 files, with 14 changed files and two added test files relative to that packet.

## Reproduction And Remaining Work

Run `verify.py --help`, `run_capacity.py --help`, `measure_wire.py --help` and
`seal.py --help` for explicit new staging/output paths. Capacity admission uses
`run_capacity.py --runtime --polling --decoded-mib 128`; add `--dense` for the
full-input control, or `--sql-trace --hold-commit-seconds 29` for the contention
control. Outputs must be new directories; do not rewrite a sealed
packet. Tests use temporary stores and fake endpoints, with no credentials.

No additional application provider/LLM canary, production read/write, database
installation, App restart, commit, merge or push is performed here. A renewed
live investigation, model-usage calibration, authorized journal/population
cutover and merge/hand testing remain separate steps. The maximum-size benchmark
does not execute a human-confirmation write alongside another running model job;
that caller-owned atomic transaction's concurrency/latency still needs a separate
measurement before production cutover. A general SEC filing
resolver is not required to use non-SEC supplemental evidence and is not
represented as implemented by these source-format changes.
