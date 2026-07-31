# EIR-005 Machine-State Observer Design

> **Status:** DRAFT - INDEPENDENT SPEC REVIEW NEXT
>
> **Date:** 2026-07-31
>
> **Grounding commit:** `5ff3608a979519b7aee8b68dc9863ca852ac1ce1`
>
> **Parent diagnosis:** `EIR-005` and
> `docs/superpowers/specs/2026-07-29-lifespan-stall-causal-diagnosis-design.md`
>
> **Blocked caller:** price-collection partial-truth Task 0, runner-v3 summary
> `a5686da09e1715e1ea81b618826c956b96649bf12075ccf230a387c87782b198`

## 1. Purpose And User Boundary

The price-collection partial-truth product fix is blocked before product RED
because five of eight backend verification tiers repeatedly stop inside event
loops. Runner v3 now bounds, classifies, cleans up, and banks those attempts
correctly. It does not identify why an event loop sometimes remains in
`select()` while work expected by the calling thread does not complete.

This slice performs one bounded machine-state observation campaign. It answers:

1. while a matching stall is active, is the target loop's cross-thread wakeup
   byte queued, is a callback already in `_ready`, and is the receiving socket
   still registered with the selector;
2. does the same state occur in both a TestClient/AnyIO portal surface and a
   bare `asyncio.run()` surface;
3. is an apparent common mechanism supported, surface-specific, perturbed by
   the observer, or still not reduced; and
4. how does kernel-visible process, file-descriptor, signal, and scheduler
   state align with the in-process snapshot.

The purpose is not to make tests look quiet. Trustworthy verification protects
user-facing work: a green release gate must not be manufactured by removing
real startup coverage, ignoring unfinished tests, or waiting indefinitely for
a favorable machine window.

This design therefore imposes a hard progress boundary:

- the core campaign is at most four paired blocks per surface, sixteen
  scheduled attempts plus no more than two controller-invalid replacements;
- it ends with a closed verdict even when the cause remains unknown;
- it does not authorize a fourth runner generation or another broad diagnosis
  matrix; and
- after the campaign and its review, price-tier banking returns to the next
  product gate. A full root-cause fix is not a prerequisite for resuming that
  reviewed verification path.

The observer is diagnostic only. It does not alter desktop behavior, product
code, application tests, pytest admission, or the official price runner/bank.

## 2. Grounded Current State

### 2.1 Prior causal result

The frozen 2026-07-29 experiment selected
`V6 ambient_or_machine_state_dominates`:

- all eight counterbalanced cells produced `10/10` matching stalls;
- removing the `edgar` import and pyrate-limiter leaker did not remove stalls;
- adding that import did not uniquely create stalls; and
- later exact replays moved between stall and non-stall states without a
  machine reboot.

That result selected no SEC import, TestClient, lifespan, dependency, or
product seam. The machine-state observer was explicitly reserved as the next
diagnostic stage if matching stalls continued.

### 2.2 Runner v3 trigger

Runner v3 is fixed at these identities:

| Artifact | SHA-256 |
|---|---|
| runner/plugin | `bb5d2245071aa48f8f0ad4e28a0966aa26744f213dcec65a69d947a383fd9de9` |
| reporter | `09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928` |
| tier builder | `0f0421f86f46265427914bce7bbede694beaa8d04b5d3b2ea9562d27cd7c8d9c` |
| tier map | `3d7adb7e1db7b92b25b3ae83fe56ec182c6b070802cd45d95e091c673115994a` |

The authorized base run had no invalid attempt. T3, T4, and T7 completed and
were banked. T0, T1, T2, T5, and T6 each stalled at the same active node in
both its initial attempt and sole retry:

| Tier | Surface | Stable active node | Progress events | SIGINT result |
|---|---|---|---:|---|
| T0 | TestClient request portal | `tests/test_trading_day_coverage.py::test_route_rejects_unreviewed_interval_with_typed_422` | 1173 | SIGKILL required |
| T1 | bare `asyncio.run()` | `tests/test_monitor.py::TestRunAgentQuery::test_successful_query` | 567 | SIGINT exited |
| T2 | bare `asyncio.run()` plus pyrate loop | `tests/test_investor_profile_calibration.py::test_anthropic_calibration_raises_structured_refusal_before_text_extraction` | 769 | SIGINT exited |
| T5 | TestClient lifespan portal | `tests/test_portfolio_activity_routes.py::test_get_activity_http_limit_uses_typed_400[0]` | 685 | SIGKILL required |
| T6 | module TestClient lifespan portal | `tests/test_api.py::TestHealth::test_status` | 31 | SIGKILL required |

The atomic summary is incomplete, with selected tiers `{3,4,7}` and unresolved
tiers `[0,1,2,5,6]`. Its SHA-256 is the grounding summary named in the header.
The 3,262-file evidence manifest is
`ff189a4433b571c671ef7e4db82e63c94071d869e4ed48410f2a65c25e622f75`.

These observations establish a repeatable per-surface shape within that
window. They do not establish that every surface has one root cause.

### 2.3 Relevant scheduling mechanism

The grounded interpreter is CPython 3.10.12. In its selector event loop,
`call_soon_threadsafe()`:

1. appends a handle to `_ready`; then
2. calls `_write_to_self()`; and
3. sends one null byte through `_csock` to `_ssock`.

The selector registers `_ssock` for reads. The event loop drains `_ssock` when
the selector returns, then runs callbacks already in `_ready`.

The public asyncio contract requires cross-thread callers to use
`call_soon_threadsafe()`. The private `_ready`, `_scheduled`, `_selector`,
`_ssock`, and `_csock` fields are implementation-specific diagnostics, not
ArkScope runtime contracts. The exact interpreter and source identities must
therefore be pinned by the later plan.

A thread stack stopped in `selector.select()` is not enough to prove a missed
wakeup. The observer must distinguish at least:

- a queued wake byte with the receiving FD correctly registered;
- a ready callback with no queued byte;
- a missing, closed, or unregistered self-pipe endpoint;
- no ready callback and no queued wake evidence; and
- a different waiting boundary on the two selected surfaces.

### 2.4 Host observation capabilities

Grounded host versions are Linux `6.8.0-134-generic`, pytest 8.4.1, AnyIO
4.9.0, Starlette 0.47.2, and HTTPX 0.28.1.

The following boundaries were checked on 2026-07-31:

1. `/proc/<pid>/fdinfo/<fd>` exposes flags and inode for a Unix socket. It does
   not expose that socket's receive/send queue length. For an epoll FD it does
   expose each watched target FD through `tfd` records. This matches the Linux
   [`proc_pid_fdinfo(5)`](https://man7.org/linux/man-pages/man5/proc_pid_fdinfo.5.html)
   interface.
2. A non-consuming in-process `FIONREAD` ioctl reports queued bytes on the
   self-pipe receiver.
3. `ss -x -a -n -m -e -p` reports Unix-socket `Recv-Q`/`Send-Q` and socket
   inode. A local socketpair probe with three unread bytes showed `Recv-Q=3`
   on the receiving endpoint. The observer must join this output by inode; it
   must not assume `/proc/net/unix` contains queue lengths.
4. The host has `kernel.yama.ptrace_scope=1`. `strace -p` from a sibling
   controller was denied even outside the filesystem sandbox. Launching a
   process under `strace -f` succeeded.

The last result changes the handoff design. Attach-time strace is not a
mandatory gate. Launch-under-strace is a timing-perturbing, conditional
qualifier described in LD 10.

## 3. Locked Decisions

### LD 1 - Separate diagnostic authority

The machine-state campaign uses a new scratch artifact root and separately
reviewed exact-source controller/plugin/verifier.

It must not:

- modify or import banked results into `/tmp/price-truth-tier-v3`;
- change the official v3 runner, reporter, builder, map, records, or bounds;
- update the price branch's selected tiers;
- produce a price base/tip non-passing union; or
- act as product-test admission.

The official v3 source and manifest identities are checked before and after
the campaign. Any drift stops the observer line.

### LD 2 - Paired control and observed arms

An observer thread changes process scheduling. Its effect cannot be dismissed
by assertion.

Each block therefore contains two adjacent fresh-process attempts over the
same surface and hermetic environment:

- `C`: existing progress/reporter control, no machine-state observer; and
- `O`: the same command plus the machine-state observer plugin.

Block order alternates `C/O`, then `O/C`. A plan may counterbalance the first
order between surfaces, but it may not run every control first and every
observed arm later.

Control and observed arms must have byte-identical collected node IDs for
their surface. Neither arm may derive node accounting from transcript text.

### LD 3 - Two fixed surfaces

The core campaign owns exactly two surfaces:

1. **Portal/lifespan surface P:** the existing T6 selection, with target
   `tests/test_api.py::TestHealth::test_status`.
2. **Bare-asyncio surface A:** the existing T1 selection, with target
   `tests/test_monitor.py::TestRunAgentQuery::test_successful_query`.

The complete existing tier selections preserve predecessor context. Running
only the target node is not an equivalent experiment.

The grounded identities are:

| Surface | Paths SHA-256 | Node-manifest SHA-256 |
|---|---|---|
| A / T1 | `d222b59322f5936607676b21163b06ecf3e6eb74df7e3df538b7b87245a86cc9` | `d74b9a2bf40a3b13a873be7337f4ad5da7e9e14865f795c0053820b083e2ee30` |
| P / T6 | `9f04af18ffdb255646a2ac294b4e8beb825657d86fdafa253a12008d7ebf93ad` | `b6979e10b7d72b2b70b69e14ab8b8e4dd70b2e10484aa72e8c1d5ac92547500c` |

T0, T2, and T5 remain corroborating historical surfaces. Expanding the core
campaign to them requires a reviewed amendment and is not the default response
to an inconclusive result.

### LD 4 - Finite campaign

Each surface receives at most four paired blocks: eight scheduled attempts per
surface, sixteen scheduled attempts total. A surface stops early after two
qualifying paired stall blocks.

A qualifying paired stall block requires:

- both C and O reach the pinned target;
- both produce the existing current-window faulthandler dump;
- both breach the reviewed no-progress deadline;
- both are cleaned up by the controller's reviewed signal sequence; and
- neither has an identity, data-boundary, reporter, progress, or transport
  invalidation.

At most one controller-invalid attempt per surface may be replaced for the
same arm and slot. The absolute launch cap is therefore eighteen. A second
invalid attempt on one surface stops the campaign; it does not increase either
cap.

When the budget ends, the verifier must select a closed result. It may not
request more blocks merely because a preferred causal answer was not found.

### LD 5 - Observation, never intervention

The observer may read loop and process state. It may not:

- wrap or replace `call_soon_threadsafe`, `_write_to_self`, `_run_once`,
  selector methods, AnyIO portals, TestClient, `asyncio.run`, or event-loop
  policy/factory methods;
- call `recv()`, `send()`, `_read_from_self()`, `_write_to_self()`, `stop()`,
  `wake()`, or `call_soon_threadsafe()` on a target loop;
- add, cancel, or await a target task;
- change loop debug mode;
- close, duplicate into the child, or alter target FDs;
- install a signal handler in the pytest process; or
- patch product or test code.

Loop discovery uses read-only object enumeration. A sampling race is recorded
as a typed snapshot error; it is not repaired by retrying inside the target
loop.

### LD 6 - In-process closed snapshot

The O arm loads one scratch pytest plugin. It starts one named daemon observer
thread and writes a closed-schema JSONL stream to a dedicated inherited FD.
The plugin contributes zero tests.

For every discovered selector loop, a snapshot records:

- trial, surface, arm, target node, trigger, sequence, wall time, and monotonic
  time;
- loop label assigned within the trial, concrete loop class, running/closed
  flags, Python thread ident, native TID, and matching thread name;
- `_ready` count and callback qualified names;
- `_scheduled` count, earliest relative deadline, and callback qualified
  names;
- selector class and registrations as FD, event mask, and callback qualified
  name;
- `_ssock` and `_csock` FD, inode, open/blocking state, socket family/type,
  buffer sizes, and non-consuming queued-byte observations;
- task count, state, cancellation state, and coroutine qualified names from
  `asyncio.all_tasks(loop)`; and
- filename/function/line-only stacks for process threads.

No callback arguments, task locals, exception prose, object `repr`, HTTP
content, credentials, prompts, user data, absolute home paths, or raw object
addresses may enter an artifact. Unknown callback/coroutine types become a
stable module-qualified type name, not a `repr`.

The snapshot must identify its target loop by thread and stack evidence. It
must not silently select "the first asyncio loop"; T2 already proves that more
than one loop may exist.

### LD 7 - Out-of-process cross-check

The parent controller independently captures:

- `/proc/<pid>/status` and `/proc/<pid>/task/<tid>/status`, including
  `SigPnd`, `ShdPnd`, context-switch counts, and thread state;
- task `wchan`, syscall, and stat where readable;
- `/proc/<pid>/fd` links and every relevant `fdinfo`, including epoll `tfd`
  registrations;
- target-inode rows from `/proc/<pid>/net/unix`;
- `ss -x -a -n -m -e -p` rows joined to observed socket inodes;
- process FD/thread counts and limits;
- `/proc/loadavg`, `/proc/pressure/{cpu,io,memory}`, and
  `/proc/sys/fs/file-nr`; and
- controller signal-send and child-exit timing.

`ss` capability is a preflight requirement for the O arm. If the execution
environment denies its netlink query, the campaign stops before behavioral
attempts and requests an approved execution handoff. It does not relabel
`fdinfo` as queue evidence.

The controller filters namespace-wide socket tables in memory and persists
only rows joined to the target process's observed socket inodes. FD links are
stored as type/inode plus a trial-relative path where relevant; unrelated
absolute paths and unrelated process/socket rows are not retained.

### LD 8 - Sampling schedule and signal boundary

The exact-source plan pins one schedule relative to target `logstart`.
At minimum it includes:

- immediate target-start state;
- one early state after one second;
- stable pre-dump observations;
- observations immediately before and after the 120-second dump boundary;
- one late observation before the 150-second no-progress breach;
- a pre-SIGINT kernel snapshot; and
- bounded post-SIGINT snapshots until natural exit or the existing SIGKILL
  boundary.

The observer thread's receive time is authoritative for in-process samples.
The controller's monotonic clock is authoritative for `/proc`, `ss`, and
signal events. Cross-process clocks are not compared as if they shared one
origin.

The existing `120/150/10` dump/deadline/grace semantics remain the diagnostic
classification boundary. Observer sampling must not extend them.

### LD 9 - Healthy and stalled evidence stay distinct

A naturally completed target is useful control evidence. It is not a stall
snapshot and cannot be pooled with late stall samples.

Every attempt is classified independently as:

- `matching_stall`;
- `complete_natural`;
- `terminated_nonstall_failure`; or
- `invalid`.

Partial transcripts and pre-target process snapshots never count as a
completed or stalled node result.

### LD 10 - Strace is conditional and non-authoritative

`strace -p` attach is not part of this design because the grounded host denies
that relationship. If the core campaign reaches a mechanistic ambiguity that
syscall ordering can resolve, the evidence may request one separately
SHA-pinned launch-under-`strace -f` arm per surface.

That handoff:

- is executed only after core evidence review;
- may be run by the user or an external reviewer when Codex execution policy
  is narrower;
- traces only a predeclared syscall set relevant to selector wait and
  self-pipe reads/writes;
- uses the same hermetic data and process cleanup boundaries;
- is explicitly timing-perturbing; and
- can qualify, but cannot independently establish, a causal verdict.

The absence of strace evidence does not make an otherwise complete core
campaign invalid.

### LD 11 - Closed result, no preselected fix

For each qualifying O stall, the verifier builds a late-state vector from at
least two valid samples after the dump and before the no-progress deadline:

```text
selector_waiting
self_pipe_open
self_pipe_registered
ready_callbacks_pending
receive_bytes_pending
send_queue_nonempty
```

Two trials have the same load-bearing state only when this vector matches; the
phrase "and/or" cannot collapse a ready-only state and a receive-byte-only
state into one result.

The independent verifier then selects exactly one result:

| ID | Result | Minimum meaning |
|---|---|---|
| `O1` | `shared_pending_wakeup_state_supported` | both surfaces have qualifying O stalls and repeatedly show the same pending-ready and/or queued-wakeup state while the correctly registered target loop remains in selector wait |
| `O2` | `shared_self_pipe_integrity_failure_supported` | both surfaces repeatedly show the same missing, closed, or unregistered target self-pipe boundary |
| `O3` | `surface_specific_state_supported` | qualifying stalls exist on both surfaces, but their load-bearing loop/wakeup state differs |
| `O4` | `observer_perturbation_supported` | on either surface, at least two adjacent blocks have C matching stalls and O natural completions, with no reverse block on that surface where O stalls and C completes |
| `O5` | `matching_stalls_observed_but_mechanism_not_reduced` | qualifying O stalls are captured, but no closed shared or surface-specific invariant meets the required evidence |
| `O6` | `matching_window_not_obtained` | the finite campaign does not obtain the required paired stalls |

Precedence is `O4`, `O2`, `O1`, `O3`, `O5`, then `O6`.

`O1`, `O2`, and `O3` require at least two qualifying paired stall blocks per
surface. `O2` requires the same integrity-failure vector on both surfaces.
`O1` requires open, registered self-pipes and the same pending-wakeup vector on
both surfaces. `O3` requires a stable vector within each surface and a
difference between surfaces. `O5` applies when at least one valid O stall was
captured but those thresholds were not met. `O6` applies when no valid O stall
was captured. A single snapshot or one surface cannot support O1-O3.

No result authorizes a fix. A later user-approved fix gate must name:

1. the observed seam;
2. whether the proposed change affects test infrastructure, product runtime,
   or both;
3. the real startup/async coverage retained; and
4. the user-facing verification benefit and rollback.

### LD 12 - Product progress does not wait for certainty

The observer exists because unstable verification is repeatedly blocking a
live price-data correctness fix. It is not an open-ended infrastructure
project.

After reviewed result `O1` through `O6`:

- the observer campaign closes;
- exact existing price-tier bank identities are revalidated;
- the price line may seek authorization for its next bounded banking run or
  product RED gate under the already-reviewed protocol; and
- any deeper machine investigation must be justified by new evidence, not by
  dissatisfaction with `O5` or `O6`.

### LD 13 - Real desktop failure remains a separate escalation

Current evidence establishes a pytest/test-runtime defect, not a desktop
startup defect. If a normal ArkScope desktop startup produces the same
observable failure, EIR-005 is immediately promoted to a product incident.
That event does not wait for this campaign and must not be hidden by a
test-only fix.

## 4. Experimental Shape

### 4.1 Block schedule

The plan must generate and hash a schedule before behavior runs. For each
surface it contains at most:

```text
block 1: C O
block 2: O C
block 3: C O
block 4: O C
```

The second surface starts with the opposite order unless plan review proves a
different counterbalance. Early stopping is applied only after a complete
block.

### 4.2 Hermetic process contract

Both arms inherit the price runner's reviewed environment allowlist and
isolated data paths. Provider credentials, ambient database overrides, normal
home/cache state, and the main worktree's `data/` do not enter the child.

Each attempt:

- uses a fresh home, temp, cache, locks, and database directory;
- launches in an owned process group;
- records PID/PGID/SID before observation;
- verifies the exact controller/plugin/reporter/manifests before and after
  launch;
- uses the structural progress pipe for target identity and bounds;
- owns SIGINT, grace, SIGKILL, and descendant cleanup; and
- proves its isolated `data/` boundary is clean before the next attempt.

### 4.3 Snapshot triggers

The observer stream must show why every sample was taken. Trigger values are a
closed enum such as:

```text
target_start
early
pre_dump
post_dump
pre_deadline
pre_sigint
post_sigint
target_finish
```

Missed scheduled samples are evidence. They are recorded as missing with a
typed reason; timestamps must not be fabricated after process death.

### 4.4 Wakeup-state derivation

Raw snapshots remain primary. Derived booleans are recomputed by the
independent verifier:

- `selector_waiting`;
- `self_pipe_open`;
- `self_pipe_registered`;
- `ready_callbacks_pending`;
- `receive_bytes_pending`;
- `send_queue_nonempty`;
- `target_tasks_pending`;
- `sigint_kernel_pending`; and
- `signal_exit_observed`.

The verifier does not trust those values if the controller writes them into a
record.

`receive_bytes_pending` requires in-process `FIONREAD` and/or inode-matched
`ss` `Recv-Q`. `/proc/fdinfo` alone cannot satisfy it.

## 5. RED-First Plan Requirements

The later exact-source plan must prove its observer before a real campaign.

### 5.1 Required probes

1. **Plugin identity:** loading the observer changes zero collected node IDs
   and contributes no helper beginning with `test_`.
2. **Healthy loop:** a controlled selector loop reports open registered
   self-pipe endpoints, zero queued receive bytes, and the expected ready/task
   shape.
3. **Queued wake:** a controlled, non-running selector loop receives one
   thread-safe callback; the observer detects the pending ready callback and
   unread wake byte without consuming either. The original loop can then run
   and complete the callback.
4. **Kernel join:** known socket/epoll inodes join correctly across in-process
   FDs, `/proc` fdinfo, and `ss` queues.
5. **Multiple loops:** two loops in different threads are both recorded and
   identified by their owning thread; the observer does not select by creation
   order.
6. **Sanitization:** callback arguments, locals, exception prose, credentials,
   and absolute home paths cannot appear in JSONL.
7. **Signal timeline:** an interruptible hang and an ignored-SIGINT hang
   exercise natural post-SIGINT exit and SIGKILL cleanup without changing the
   verdict schema.
8. **Paired verifier:** removing either C or O from a block prevents that block
   from qualifying.
9. **Frozen price root:** changing one byte in a copied v3 identity causes
   preflight refusal before a behavioral attempt.

### 5.2 Required mutation sensitivity

Each mutation runs only its owning probe and is reverted with a source-hash
check:

1. force queued-byte output to zero;
2. omit the self-pipe selector registration;
3. collapse multiple loops into "first loop";
4. include raw callback/task `repr` or frame locals;
5. trust a controller-derived verdict instead of recomputing raw evidence;
6. permit a one-arm block to qualify;
7. downgrade unavailable `ss` to an empty queue; and
8. let an observer attempt write into or import the official v3 bank.

Every mutation must turn its owning probe RED for the intended reason.

### 5.3 Static non-intervention proof

The plan must scan the exact observer source and fail if it invokes or assigns
any prohibited event-loop/selector/portal operation from LD 5. This is a
supplement to behavioral probes, not a substitute for source review.

## 6. Evidence And Review Contract

Review must be reconstructable from raw artifacts:

- exact controller, observer plugin, reporter, and independent verifier source
  with byte count, line count, and SHA-256;
- predeclared schedule and surface manifests;
- preflight/probe/mutation records;
- one directory per attempt containing command, environment-name allowlist,
  progress, transcript, reporter result, in-process JSONL, `/proc` snapshots,
  `ss` snapshots, signal timeline, and final record;
- independently recomputed attempt classifications and O1-O6 result;
- complete artifact manifest validated before review;
- before/after official v3 runner/bank/manifest identities;
- before/after protected product/test/dependency path checks; and
- explicit statement that diagnostic process partitioning and observer
  scheduling differ from official tiered admission.

Evidence prose may summarize but cannot replace raw reconstruction.

## 7. Owned And Protected Paths

### 7.1 Spec-stage tracked owners

- this design;
- `docs/design/PROJECT_PRIORITY_MAP.md`.

### 7.2 Future plan/evidence owners

A reviewed plan may add:

- one observer implementation plan;
- one observer evidence packet; and
- scratch exact-source controller/plugin/verifier and artifacts under a fresh
  `/tmp` root.

No scratch runtime source is installed into `src/`, `tests/`, `conftest.py`, or
the official price runner root.

### 7.3 Protected boundaries

The following remain byte-identical:

- all `src/**`, `tests/**`, frontend, extension, desktop, dependency, and
  configuration files;
- `/tmp/price-truth-tier-v3` and every banked attempt;
- `codex/price-collection-truth` at `5ff3608a...`;
- production databases and provider/Gateway state; and
- the two known untracked main-worktree drafts,
  `docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md` and
  `docs/design/SCRIPTS_RETIREMENT_DECISION.md`.

## 8. Stop Conditions

Stop and report without improvising if:

1. an observer requires patching a target loop, selector, portal, policy, test,
   or product;
2. control and observed collection identities differ;
3. either pinned surface no longer reaches the grounded target under its
   reviewed selection;
4. a snapshot contains user data, credentials, callback arguments, locals,
   raw exception prose, or unsanitized paths;
5. `ss` queue capability is unavailable after the approved execution
   preflight;
6. a process identity, data boundary, reporter, progress, or cleanup check is
   invalid twice;
7. an attempt writes to the main worktree, production data, or official v3
   root;
8. the campaign reaches sixteen scheduled attempts or eighteen total launches
   without satisfying an early result;
9. a proposed interpretation treats absence of a wake byte as proof that no
   wake was attempted;
10. a result relies on one snapshot, one surface, or strace alone;
11. a reviewer asks for another broad matrix or runner generation without new
    evidence and a user-approved scope change; or
12. the normal desktop exhibits the same failure.

Budget exhaustion produces `O5` or `O6`; it is not permission to continue
sampling indefinitely.

## 9. Execution Responsibility

Codex owns the reviewed standard campaign where local execution permissions
allow it. If a required host capability is available to the user/reviewer but
not to Codex, the plan must provide:

- one exact SHA-pinned command;
- expected artifact root and identities;
- a no-secret environment allowlist;
- bounded signal/cleanup behavior; and
- an independent verifier command.

The user or reviewer returns the artifact manifest, not a prose-only result.
This handoff is an execution boundary, not a change in evidentiary standard.

## 10. Next Gate

Independent full-document review is next.

After GREEN:

1. write one exact-source RED-first observer plan;
2. independently review its probes, mutations, schedule, and bounds;
3. run the finite two-surface campaign;
4. reconstruct raw evidence and select O1-O6;
5. close the observer campaign; and
6. return to the reviewed price-truth banking/product gate.

No observer runtime, strace arm, product/test change, or unchanged price-v3
rerun is authorized by this draft alone.
