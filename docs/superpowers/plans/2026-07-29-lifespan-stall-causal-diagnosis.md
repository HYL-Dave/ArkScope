# Full-Suite Lifespan Stall Causal Diagnosis Experiment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task-by-task. This is one
> stateful experiment; do not distribute trial cells across concurrent agents.
> Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** DIAGNOSIS REVIEW GREEN - CLOSEOUT REVIEW NEXT
>
> **Spec authority:**
> `docs/superpowers/specs/2026-07-29-lifespan-stall-causal-diagnosis-design.md`
>
> **Reviewed spec tip:** `222636a7`
>
> **Behavior base:** `2edf12e11a8ff9299a9b65b900309c8ed218b717`
>
> **Blocked price tip:**
> `f7458727b8c7828e9372be29e7698b986e1db757`

**Goal:** Produce a reproducible causal verdict for the intermittent
full-suite lifespan stall without changing product code, tests, dependencies,
or meaningful startup coverage.

**Architecture:** A SHA-pinned scratch controller runs two sequential,
counterbalanced `2 x 2` matrices in fresh pytest subprocesses. Phase 1 varies
SEC-test collection and the real-app mount predecessor; Phase 2 replaces SEC
collection with an identical-plugin `edgar` import control. Every trial is
hermetic, time-bounded after a faulthandler dump, classified from a closed
outcome set, and preserved as an immutable artifact.

**Tech Stack:** Python 3.10 standard library, pytest 8.4.1,
Starlette/FastAPI `TestClient`, AnyIO, JSON, SHA-256, git.

## Global Constraints

- The experiment may produce a verdict only. It authorizes no fix.
- Tracked changes are limited to the approved spec, this plan, the final
  evidence document, and `docs/design/PROJECT_PRIORITY_MAP.md`.
- **User-approved closeout scope amendment (2026-07-30):**
  `docs/design/ENGINEERING_ISSUE_REGISTER.md` may change only to transfer the
  unresolved V6 incident owner; this does not authorize an observer or any
  product, test, dependency, or harness change.
- Do not modify `src/`, `data_sources/`, `tests/`, `tests/conftest.py`,
  requirements, installed packages, or pytest configuration.
- Do not convert or exclude another `TestClient` family.
- Do not mount production data to make `/status` assertions pass.
- The price branch remains byte-frozen at `f7458727` throughout this plan.
- The two main-worktree untracked drafts remain untracked and untouched.
- Every subprocess uses a unique temporary root, an empty diagnosis-worktree
  `data/`, isolated DB paths, and `ARKSCOPE_DISABLE_SCHEDULER=1`.
- No provider, Gateway, HTTP, browser, production DB, or scheduler action is
  allowed.
- `faulthandler_timeout=60` emits diagnostics but does not terminate; the
  controller owns the later interrupt.
- Only the complete portal-spawn signature counts as a matching stall.
- No partial experiment output is a substitute for the price line's blocked
  full-suite baseline.
- Phase 2 runs even if Phase 1 does not reproduce a stall.
- Early truncation is allowed only by the exact Section 3 thresholds at
  complete 10- or 15-block checkpoints.

---

## 1. Owned Files And Scratch Interfaces

### 1.1 Tracked authority

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-29-lifespan-stall-causal-diagnosis-design.md`
- Create:
  `docs/superpowers/plans/2026-07-29-lifespan-stall-causal-diagnosis.md`
- Create during execution:
  `docs/superpowers/evidence/2026-07-29-lifespan-stall-causal-diagnosis.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

No other tracked file is owned.

### 1.2 Scratch files

The executor creates one unique root:

```text
$DIAG_ROOT/
  preflight.json
  schedule-phase1.json
  schedule-phase2.json
  scratch/
    diagnosis_controller.py
    arkscope_edgar_import_probe.py
    independent_verifier.py
  trials/
    $trial_id/
      stdout.txt
      stderr.txt
      record.json
      threads.json              # Phase 2 only
      home/
      tmp/
      locks/
      edgar/
      pytest-tmp/
      pytest-cache/
  summary-phase1-b10.json
  summary-phase1-b15.json       # only if reached
  summary-phase1-b20.json       # only if reached
  summary-phase2-b10.json
  summary-phase2-b15.json       # only if reached
  summary-phase2-b20.json       # only if reached
```

The staging copies used to prepare this root also live under `/tmp`. They are
not imported from either worktree.

### 1.3 Pinned scratch identities

Appendices A, B, and C are exact source, not illustrative pseudocode.

```text
diagnosis_controller.py
  bytes: 20056
  SHA-256: d069de2236851e89ac6271e24589ca00ab328ef35c338a5cd092be1970ddd200

arkscope_edgar_import_probe.py
  bytes: 1235
  SHA-256: 4103a8ed21309b846e1a9ac7bfb249759ce4e3bc5638eb5495e95f6b64e35c17

independent_verifier.py
  bytes: 8694
  SHA-256: 645a0c528c3f0693d4bfbdf327d5871ce681f5fbee90f5e3e26884e823d4e40c

schedule-phase1.json
  seed: 20260729
  SHA-256: cf2c9fef4c4a546205587ee0c4aa0692208ab538ea4951ec8ef66a1b7df0d419

schedule-phase2.json
  seed: 20260730
  SHA-256: 892ea2a562ff0691ec01738b73f2feec552da7ea7ee6a835263b5713815c5c4d
```

Each 20-block schedule uses five copies of a four-order Latin square, then
shuffles block order with the pinned seed. Every cell appears exactly five
times in each ordinal position.

## 2. Baseline And Collection Ledger

### 2.1 Repository control

| Control | Expected |
|---|---|
| diagnosis branch base | descends from `2edf12e1` |
| approved design | `222636a7` present |
| price worktree HEAD | exact `f7458727b8c7828e9372be29e7698b986e1db757` |
| diagnosis worktree data files | `0` |
| main worktree tracked changes | `0` |
| main worktree untracked drafts | exactly the two protected files |
| product/test/dependency diff from behavior base | empty |

### 2.2 Backend identity

```text
full collection:
  4722 nodes
  fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0
```

Phase 1:

| Cell | Nodes | SHA-256 |
|---|---:|---|
| A0B0 | 1 | `4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f` |
| A0B1 | 2 | `c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc` |
| A1B0 | 7 | `a3af106460307042ae13af1a2b6759c34e25788102cee94b3115346a8afcb484` |
| A1B1 | 8 | `7d7b4d75fee81eb9305cb3651c7940e7ca87afe3539a198d5ec45eefea547644` |

Phase 2 loads the identical plugin in every cell:

| Cell | Nodes | SHA-256 |
|---|---:|---|
| E0B0 | 1 | `4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f` |
| E0B1 | 2 | `c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc` |
| E1B0 | 1 | `4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f` |
| E1B1 | 2 | `c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc` |

Backend node accounting is exactly `+0/-0`. Scratch plugins and controllers
must never become collected repository nodes.

## 3. Closed Trial And Early-Stop Contract

### 3.1 Matching stall

A trial counts as `stall_matching_portal_signature` only when all of these are
present after the outer 75-second timeout:

```text
Timeout (0:01:00)!
tests/test_api.py::TestHealth::test_status
concurrent/futures/_base.py ... in result
_spawn_task_from_thread
start_task_soon
starlette/testclient.py ... in __enter__
```

The controller sends `SIGINT` only after the 60-second dump window. If the
process does not exit within five more seconds, it sends `SIGKILL`. A timeout
without the full signature is a stop condition, not a matching stall.

### 3.2 Other outcomes

```text
pass
terminated_nonstall_failure
invalid_trial
timeout_without_expected_dump
```

The isolated `/status` assertion may fail because no production market corpus
is mounted. That is a valid `terminated_nonstall_failure` and does not weaken
the lifespan observation.

A Phase 2 attempt is invalid if the control has the target leaker before/after,
or treatment does not move from zero target leakers before import to exactly one
after import. An operator interrupt is also recorded as invalid after the
controller terminates the child process group, then stops the current command.
On deliberate resume, one predeclared replacement attempt is allowed for the
same schedule slot. Two invalid attempts stop the phase. Both attempts remain
in evidence.

### 3.3 Early-truncation flags

At block 10 and block 15, and only there, a phase may stop early when one of
these exact flags is true:

**First-factor main effect (`A` or `E`):**

```text
factor-0 B0 stalls == 0
factor-0 B1 stalls == 0
factor-1 B0 stalls >= 3
factor-1 B1 stalls >= 3
pooled factor-1 stalls >= 8
```

**Mount main effect:**

```text
B0 stalls in both first-factor levels == 0
B1 stalls in each first-factor level >= 3
pooled B1 stalls >= 8
```

**Interaction:**

```text
factor-1 B1 stalls >= 6
all other cells == 0
```

**Ubiquitous/non-isolating:**

```text
every cell has >= 2 stalls
```

These are operational reproducibility thresholds, not population estimates or
p-values. `first_factor_not_necessary` and `mount_not_necessary` are factual
qualifiers, not early-stop permissions. No-stall observations never stop a
phase early.

## 4. Task 0: Re-ground Before Any Behavioral Trial

**Files:**

- Read: approved spec and this plan
- Read: `tests/test_api.py`
- Read: `tests/test_sec_filings.py`
- Read: `tests/test_sec_user_agent.py`
- Read: `data_sources/sec_filings.py`
- Read: installed package metadata
- Do not create tracked evidence yet

- [ ] **Step 1: Confirm branch and protected worktrees.**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor \
  2edf12e11a8ff9299a9b65b900309c8ed218b717 HEAD
git -C /tmp/arkscope-price-collection-truth rev-parse HEAD
git -C /tmp/arkscope-price-collection-truth status --short
git -C /mnt/md0/PycharmProjects/ArkScope status --short
```

Expected:

- diagnosis worktree has only reviewed authority changes;
- behavior base is an ancestor;
- price is exact `f7458727...` and clean;
- main has no tracked change and exactly the two protected untracked drafts.

Any other result stops Task 0.

- [ ] **Step 2: Prove product, test, dependency, and isolated-data boundaries.**

Run:

```bash
git diff --quiet \
  2edf12e11a8ff9299a9b65b900309c8ed218b717 -- \
  src data_sources tests requirements.txt requirements-dev.txt pyproject.toml
test -z "$(find data -type f -o -type l 2>/dev/null)"
test ! -e docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md
test ! -e docs/design/SCRIPTS_RETIREMENT_DECISION.md
pgrep -af 'pytest|diagnosis_controller.py'
```

Expected: diff and file tests exit `0`; process scan contains no live diagnosis
or pytest worker. The two drafts are absent from this isolated worktree by
design.

- [ ] **Step 3: Reproduce package and import facts.**

Run the exact package fingerprint:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -c \
  "from importlib.metadata import version; print(*(f'{n}={version(n)}' for n in ('edgartools','httpxthrottlecache','pyrate-limiter','httpx','starlette','anyio','pytest')), sep='\n')"
```

Run:

```bash
rg -n \
  '(from|import)[[:space:]]+data_sources\.sec_filings|from[[:space:]]+data_sources[[:space:]]+import[[:space:]]+sec_filings' \
  --glob '*.py' .
rg -l 'with TestClient\(' tests --glob '*.py' | LC_ALL=C sort
```

Expected versions and import/lifespan inventories must match spec Section 3.
The `sec_filings.py` docstring example is not an executable import site.

- [ ] **Step 4: Reproduce the complete normalized collection.**

Run:

```bash
ARKSCOPE_DISABLE_SCHEDULER=1 \
EDGAR_LOCAL_DATA_DIR=/tmp/arkscope-lifespan-plan-collect-edgar \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/arkscope-lifespan-plan-full.nodes \
  | sha256sum
wc -l /tmp/arkscope-lifespan-plan-full.nodes
```

Expected: exact `4722 / fcdb1b7d...`.

- [ ] **Step 5: Reproduce all four Phase 1 identities.**

Run:

```bash
ARKSCOPE_DISABLE_SCHEDULER=1 \
EDGAR_LOCAL_DATA_DIR=/tmp/arkscope-lifespan-plan-a0b0-edgar \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee /tmp/arkscope-lifespan-plan-a0b0.nodes | sha256sum

ARKSCOPE_DISABLE_SCHEDULER=1 \
EDGAR_LOCAL_DATA_DIR=/tmp/arkscope-lifespan-plan-a0b1-edgar \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee /tmp/arkscope-lifespan-plan-a0b1.nodes | sha256sum

ARKSCOPE_DISABLE_SCHEDULER=1 \
EDGAR_LOCAL_DATA_DIR=/tmp/arkscope-lifespan-plan-a1b0-edgar \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_sec_filings.py \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee /tmp/arkscope-lifespan-plan-a1b0.nodes | sha256sum

ARKSCOPE_DISABLE_SCHEDULER=1 \
EDGAR_LOCAL_DATA_DIR=/tmp/arkscope-lifespan-plan-a1b1-edgar \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_sec_filings.py \
  tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee /tmp/arkscope-lifespan-plan-a1b1.nodes | sha256sum

wc -l /tmp/arkscope-lifespan-plan-a?b?.nodes
```

Expected identities are exactly `1/2/7/8` and their pinned hashes.

This step is collection-only. Do not run `TestHealth`.

- [ ] **Step 6: Record a Task 0 clearance packet before scratch creation.**

Choose and print one fresh path:

```bash
export TASK0_PACKET="/tmp/arkscope-lifespan-stall-task0-$(date -u +%Y%m%dT%H%M%SZ).md"
test ! -e "$TASK0_PACKET"
printf '%s\n' "$TASK0_PACKET"
```

Create that packet with `apply_patch`. It must contain command text, outputs,
collection artifacts and hashes, package versions, worktree statuses, and an
explicit statement that no behavioral trial or product action occurred.
Preserve the printed path in the operator handoff.

Task 1 may begin only if every Task 0 fact reproduces.

## 5. Task 1: Build And Pin The Scratch Experiment

**Files:**

- Create outside repo: `$STAGING/diagnosis_controller.py`
- Create outside repo: `$STAGING/arkscope_edgar_import_probe.py`
- Create outside repo: `$STAGING/independent_verifier.py`
- Create outside repo: `$DIAG_ROOT/...`
- Test: syntax, source hashes, schedules, collection identity, thread snapshots

**Interfaces:**

- Consumes: behavior base, cell selectors, hashes, thresholds in Sections 2-3
- Produces: immutable `preflight.json`, two schedules, controller, plugin,
  verifier

- [ ] **Step 1: Choose fresh staging and result roots.**

Create one UTC timestamp and export the exact paths:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
export STAGING="/tmp/arkscope-lifespan-stall-diagnosis-${STAMP}-staging"
export DIAG_ROOT="/tmp/arkscope-lifespan-stall-diagnosis-${STAMP}"
test ! -e "$STAGING"
test ! -e "$DIAG_ROOT"
mkdir "$STAGING"
printf '%s\n%s\n' "$STAGING" "$DIAG_ROOT"
```

Both absence checks must pass. If either exists, choose a new timestamp; do not
delete or reuse it. Preserve the two printed paths in the Task 0 clearance
packet so a resumed shell restores the exact values rather than generating a
second root. Freeze and hash the packet after appending those paths and before
creating any scratch source.

- [ ] **Step 2: Create the exact Appendix A, Appendix B, and Appendix C sources.**

Use `apply_patch`, not shell redirection, to create all three staging files. Do not
reformat, annotate, or change constants. Verify:

```bash
wc -c "$STAGING/diagnosis_controller.py" \
      "$STAGING/arkscope_edgar_import_probe.py" \
      "$STAGING/independent_verifier.py"
sha256sum "$STAGING/diagnosis_controller.py" \
          "$STAGING/arkscope_edgar_import_probe.py" \
          "$STAGING/independent_verifier.py"
```

Expected: exact bytes and hashes from Section 1.3.

- [ ] **Step 3: Compile all three scratch sources.**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m py_compile \
  "$STAGING/diagnosis_controller.py" \
  "$STAGING/arkscope_edgar_import_probe.py" \
  "$STAGING/independent_verifier.py"
```

Expected: exit `0`, no output.

- [ ] **Step 4: Create the immutable root and schedules.**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python \
  "$STAGING/diagnosis_controller.py" prepare \
  --root "$DIAG_ROOT" \
  --controller-source "$STAGING/diagnosis_controller.py" \
  --plugin-source "$STAGING/arkscope_edgar_import_probe.py" \
  --verifier-source "$STAGING/independent_verifier.py"
```

Read `preflight.json`. Expected source and schedule hashes are exact Section
1.3 values. From this point onward, use only
`$DIAG_ROOT/scratch/diagnosis_controller.py`.

- [ ] **Step 5: Prove schedule balance mechanically.**

Run this independent data-only check:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -c "
import collections, hashlib, json, pathlib, sys
for raw in sys.argv[1:]:
    path = pathlib.Path(raw)
    payload = json.loads(path.read_text())
    blocks = payload['blocks']
    cells = sorted(blocks[0]['cells'])
    assert len(blocks) == 20
    assert all(sorted(block['cells']) == cells for block in blocks)
    positions = collections.Counter(
        (cell, position)
        for block in blocks
        for position, cell in enumerate(block['cells'], 1)
    )
    assert all(positions[(cell, position)] == 5 for cell in cells for position in range(1, 5))
    print(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), positions)
" \
  "$DIAG_ROOT/schedule-phase1.json" \
  "$DIAG_ROOT/schedule-phase2.json"
```

This must independently establish:

- 20 blocks;
- each block contains every cell once;
- each cell appears 20 times;
- each cell occupies positions 1, 2, 3, and 4 exactly five times; and
- file SHA matches `preflight.json`.

A script that imports the controller to derive the expected answer is
tautological and forbidden. Read the JSON as data with a separate stdlib
one-liner or scratch verifier.

- [ ] **Step 6: Prove the plugin control and treatment.**

Run collection-only E0B0 and E1B0:

```bash
PYTHONPATH="$DIAG_ROOT/scratch" \
ARKSCOPE_DIAG_IMPORT_EDGAR=0 \
ARKSCOPE_DIAG_THREAD_SNAPSHOT="$DIAG_ROOT/e0b0-preflight-threads.json" \
EDGAR_LOCAL_DATA_DIR="$DIAG_ROOT/e0b0-preflight-edgar" \
ARKSCOPE_DISABLE_SCHEDULER=1 \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  -p arkscope_edgar_import_probe \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee "$DIAG_ROOT/e0b0-preflight.nodes" | sha256sum

PYTHONPATH="$DIAG_ROOT/scratch" \
ARKSCOPE_DIAG_IMPORT_EDGAR=1 \
ARKSCOPE_DIAG_THREAD_SNAPSHOT="$DIAG_ROOT/e1b0-preflight-threads.json" \
EDGAR_LOCAL_DATA_DIR="$DIAG_ROOT/e1b0-preflight-edgar" \
ARKSCOPE_DISABLE_SCHEDULER=1 \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  -p arkscope_edgar_import_probe \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee "$DIAG_ROOT/e1b0-preflight.nodes" | sha256sum
```

Give each arm a distinct temporary `EDGAR_LOCAL_DATA_DIR` and
`ARKSCOPE_DIAG_THREAD_SNAPSHOT`.

Expected:

- both collect exact `1 / 4e385828...`;
- E0 before/after contains no target leaker;
- E1 before has none and after has exactly one daemon
  `PyrateLimiter's Leaker`;
- plugin bytes are identical because both arms load the same pinned path.

Run the mount-present pair:

```bash
PYTHONPATH="$DIAG_ROOT/scratch" \
ARKSCOPE_DIAG_IMPORT_EDGAR=0 \
ARKSCOPE_DIAG_THREAD_SNAPSHOT="$DIAG_ROOT/e0b1-preflight-threads.json" \
EDGAR_LOCAL_DATA_DIR="$DIAG_ROOT/e0b1-preflight-edgar" \
ARKSCOPE_DISABLE_SCHEDULER=1 \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  -p arkscope_edgar_import_probe \
  tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee "$DIAG_ROOT/e0b1-preflight.nodes" | sha256sum

PYTHONPATH="$DIAG_ROOT/scratch" \
ARKSCOPE_DIAG_IMPORT_EDGAR=1 \
ARKSCOPE_DIAG_THREAD_SNAPSHOT="$DIAG_ROOT/e1b1-preflight-threads.json" \
EDGAR_LOCAL_DATA_DIR="$DIAG_ROOT/e1b1-preflight-edgar" \
ARKSCOPE_DISABLE_SCHEDULER=1 \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  -p arkscope_edgar_import_probe \
  tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app \
  tests/test_api.py::TestHealth::test_status \
  | sed -n '/^tests\/.*::/p' | LC_ALL=C sort \
  | tee "$DIAG_ROOT/e1b1-preflight.nodes" | sha256sum
```

Both must collect exact `2 / c5743e0d...`; thread transitions remain `0 -> 0`
and `0 -> 1`.

- [ ] **Step 7: Recheck all protected boundaries.**

Run `git status`, the behavior-base protected diff, empty `data/`, main
worktree status, and price HEAD again. Task 2 starts only from a clean result.

## 6. Task 2: Execute Phase 1

**Files:**

- Read/execute: pinned scratch controller
- Write only: `$DIAG_ROOT/trials`, Phase 1 summaries, external command logs
- Do not create tracked evidence until the phase is terminal

**Interfaces:**

- Consumes: `schedule-phase1.json`, A-by-B selectors
- Produces: 10, 15, or 20 complete valid blocks and one terminal Phase 1 summary

- [ ] **Step 1: Run through block 10.**

Run the pinned copied controller:

```bash
set -o pipefail
/home/hyl/.virtualenvs/llm_app/bin/python \
  "$DIAG_ROOT/scratch/diagnosis_controller.py" run-phase \
  --repo /tmp/arkscope-lifespan-stall-diagnosis \
  --root "$DIAG_ROOT" \
  --phase phase1 \
  --through-block 10 \
  2>&1 | tee "$DIAG_ROOT/controller-phase1-b10.log"
```

The pipeline must exit `0`; `pipefail` preserves controller failure.

The command may take more than ten minutes when matching stalls occur. Keep
the user updated at least every 30 seconds; do not interrupt before the
controller's 75-second bound.

- [ ] **Step 2: Audit the block-10 packet before deciding.**

Independently verify:

- exactly ten valid slots per cell;
- every scheduled block/position/cell matches the schedule;
- every invalid attempt has at most one immediate replacement;
- no `timeout_without_expected_dump`;
- every matching stall has all six signature flags;
- Phase 2 does not yet exist;
- worktree `data/` remains empty; and
- source/plugin/schedule hashes still match preflight.

If `early_stop_eligible=true`, record the exact qualifying flag and stop Phase
1 at block 10. Otherwise continue.

- [ ] **Step 3: If required, run and audit through block 15.**

Use the same command with `--through-block 15`. The controller must skip the
already valid first ten blocks. Write controller output to
`controller-phase1-b15.log`. Apply the same audit and only the exact Section
3.3 early rule.

- [ ] **Step 4: If still required, run and audit through block 20.**

Use `--through-block 20`. No early-stop claim is needed at the terminal budget.
Write `controller-phase1-b20.log`; record all flags and raw cell totals even
when no flag qualifies.

- [ ] **Step 5: Freeze the Phase 1 artifact set.**

Record:

- terminal block;
- summary path/hash;
- every trial record/stdout/stderr hash;
- invalid replacements;
- matching and nonmatching outcomes;
- exact early-stop decision; and
- post-phase product/data/process boundary checks.

Do not rename or edit a completed trial artifact.

## 7. Task 3: Execute Mandatory Phase 2

**Files:**

- Read/execute: same pinned controller and plugin
- Write only: Phase 2 trial directories and summaries

**Interfaces:**

- Consumes: `schedule-phase2.json`, identical E0/E1 plugin, B control
- Produces: independent import-only matrix

- [ ] **Step 1: Revalidate plugin identity and Phase 1 immutability.**

Rehash controller, plugin, verifier, both schedules, and all terminal Phase 1 records.
Any drift stops execution.

- [ ] **Step 2: Run through Phase 2 block 10.**

Run:

```bash
set -o pipefail
/home/hyl/.virtualenvs/llm_app/bin/python \
  "$DIAG_ROOT/scratch/diagnosis_controller.py" run-phase \
  --repo /tmp/arkscope-lifespan-stall-diagnosis \
  --root "$DIAG_ROOT" \
  --phase phase2 \
  --through-block 10 \
  2>&1 | tee "$DIAG_ROOT/controller-phase2-b10.log"
```

The pipeline must exit `0`. Apply the same runtime/update discipline as Phase 1.

- [ ] **Step 3: Audit both causal and exposure contracts.**

In addition to the Phase 1 audit, every E0 record must prove target leaker count
`0 -> 0`, and every E1 record must prove `0 -> 1`. A leaker mismatch is
`invalid_trial`, not evidence for or against H-E.

Stop at block 10 only if the exact Phase 2 early flag qualifies.

- [ ] **Step 4: If required, continue through block 15 and then block 20.**

Use the same incremental commands and audits. No Phase 1 result may be used to
change Phase 2 thresholds, order, or maximum.

Write controller output to `controller-phase2-b15.log` and
`controller-phase2-b20.log` respectively.

- [ ] **Step 5: Freeze the complete experiment root.**

After Phase 2 is terminal:

- no controller or plugin process remains;
- every trial has a record and hashed logs;
- both phase summaries are immutable;
- worktree data remains empty;
- production/main/price boundaries still match Task 0; and
- no bare-pyrate or machine-state observer has been run.

## 8. Task 4: Derive The Verdict Without Upgrading Evidence

**Files:**

- Create:
  `docs/superpowers/evidence/2026-07-29-lifespan-stall-causal-diagnosis.md`
- Modify status only:
  approved spec, this plan, priority map

**Interfaces:**

- Consumes: immutable root, terminal summaries, spec verdict enum
- Produces: one review-ready evidence packet and one bounded verdict

- [ ] **Step 1: Independently reconstruct cell totals.**

Run the pinned Appendix C verifier, which does not import the controller:

```bash
PHASE1_TERMINAL=$(
  /home/hyl/.virtualenvs/llm_app/bin/python -c \
  "from pathlib import Path; print(max(int(path.stem[-2:]) for path in Path('$DIAG_ROOT').glob('summary-phase1-b*.json')))"
)
PHASE2_TERMINAL=$(
  /home/hyl/.virtualenvs/llm_app/bin/python -c \
  "from pathlib import Path; print(max(int(path.stem[-2:]) for path in Path('$DIAG_ROOT').glob('summary-phase2-b*.json')))"
)

/home/hyl/.virtualenvs/llm_app/bin/python \
  "$DIAG_ROOT/scratch/independent_verifier.py" \
  --root "$DIAG_ROOT" \
  --phase phase1 \
  --through-block "$PHASE1_TERMINAL"

/home/hyl/.virtualenvs/llm_app/bin/python \
  "$DIAG_ROOT/scratch/independent_verifier.py" \
  --root "$DIAG_ROOT" \
  --phase phase2 \
  --through-block "$PHASE2_TERMINAL"
```

Both derived values must be exactly `10`, `15`, or `20`. The verifier must
recompute from `record.json` files:

- scheduled/actual cell order;
- valid and invalid attempts;
- all outcome counts;
- signature completeness;
- thread transition counts;
- early-stop flags;
- artifact hashes; and
- terminal block per phase.

Its totals must match controller summaries exactly.

- [ ] **Step 2: Apply this verdict precedence.**

Use the first applicable rule, preserving all mixed qualifiers:

1. missing/inconsistent artifacts, repeated invalid slots, or a boundary
   violation -> `V8 experiment_invalid_or_inconclusive`;
2. Phase 2 `main_first_factor` -> `V1
   edgar_import_contributor_supported`;
3. Phase 2 `interaction` -> `V4 sec_mount_interaction_supported`, explicitly
   qualified as an E-by-B interaction;
4. Phase 1 `main_first_factor` without Phase 2 first-factor support -> `V2
   sec_collection_association_not_reduced_to_edgar`;
5. Phase 1 `interaction` without Phase 2 interaction -> `V4
   sec_mount_interaction_supported`, explicitly not reduced to edgar;
6. a mount main-effect flag with no mount-absent stall in either phase -> `V3
   mount_predecessor_contributor_supported`;
7. ubiquitous flags or non-isolating matching stalls across both matrices ->
   `V6 ambient_or_machine_state_dominates`;
8. zero matching stalls in both phases -> `V7
   bounded_trials_did_not_reproduce`;
9. a factor-absent matching stall with no stronger rule -> `V5
   tested_factor_not_necessary`;
10. every other mixed finite sample -> `V8
    experiment_invalid_or_inconclusive`.

`V1` and `V4` do not prove the named leaker thread is the mechanism. `V7` does
not mean fixed. `V5` does not mean the factor has zero effect.

- [ ] **Step 3: Write the evidence document from observed artifacts.**

Required sections:

1. status and exact authority SHAs;
2. environment/package fingerprint;
3. Task 0 identity and boundary packet;
4. pinned controller/plugin/verifier sources and hashes plus schedule seeds and
   hashes;
5. Phase 1 trial table, summary, early decision, and limitations;
6. Phase 2 trial table, exposure proof, summary, early decision, and
   limitations;
7. independent reconstruction comparison;
8. selected verdict and every factual qualifier;
9. refreshed import-site and non-binding seam inventory;
10. production/user implications and the four-question product fix gate;
11. deviations, invalid attempts, and things not tested; and
12. exact artifact-root manifest plus reproducible read-only commands.

Do not paste secrets, provider keys, production content, raw user paths beyond
the reviewed repository/worktree roots, or a causal mechanism not established
by the matrices.

- [ ] **Step 4: Update authority status without opening a fix.**

Set the plan/evidence status to `DIAGNOSIS REVIEW-READY - INDEPENDENT REVIEW
NEXT`; retain the spec as approved. Add a newest-first priority-map entry that
states the exact verdict, trial budgets, invalid count, artifact hashes, and
that no fix or price restart is authorized.

- [ ] **Step 5: Re-run final static controls.**

Verify:

```text
backend collection = 4722 / fcdb1b7d...
node comm from behavior base = empty
product/test/dependency diff = empty
diagnosis worktree data files = 0
price HEAD = exact f7458727...
main tracked changes = 0
main untracked drafts = exact protected two
scratch controller/plugin/verifier/schedule hashes = pinned
no pytest/controller process remains
```

- [ ] **Step 6: Commit only review-ready authority/evidence.**

Stage only the approved spec status, plan status, evidence, and priority map.
Run cached `diff --check` and name-status. Commit with a docs-only message.

Do not merge, push, rebase price, write a fix spec, or run a full-suite baseline.

## 9. Task 5: Independent Diagnosis Review Gate

**Files:**

- Read only: review tip and immutable `/tmp` artifact root

- [ ] **Step 1: Provide reviewer coordinates.**

Supply:

- behavior base and review tip;
- approved spec and this plan;
- artifact root and preflight hash;
- terminal summary paths/hashes;
- evidence path;
- exact protected-boundary commands; and
- explicit notice that behavior trials can be reconstructed without touching
  production data.

- [ ] **Step 2: Require independent raw reconstruction.**

Review must not rely only on the evidence prose. The reviewer must recompute
cell totals, signature classification, plugin transitions, schedules, early
flags, and verdict applicability from raw records.

- [ ] **Step 3: Stop at verdict review.**

A GREEN diagnosis review authorizes only the next user decision under the
spec's product fix gate. It does not authorize a seam, implementation, merge,
price restart, dependency change, or SEC capability decision.

## 10. Plan Stop Conditions

Stop immediately if:

1. Task 0 cannot reproduce any identity or protected boundary;
2. a scratch source or schedule misses its pinned hash;
3. a schedule is not position-balanced;
4. Phase 2 E0/E1 collection identity differs;
5. E0 creates the leaker or E1 does not create exactly one;
6. a trial resolves any worktree `data/` file or production path;
7. provider/Gateway/network/browser/scheduler activity occurs;
8. the controller, plugin, verifier, schedule, threshold, or cell order changes
   after the first behavioral result;
9. a timeout lacks the full dump/signature;
10. two attempts for one slot are invalid;
11. a completed trial artifact changes;
12. an early stop is proposed outside block 10/15 or outside Section 3.3;
13. Phase 2 would be skipped;
14. evidence requires a bare-leaker or machine-state observer;
15. a product/test/dependency edit appears;
16. a new runtime `SECFilingsClient` consumer appears;
17. the price branch or either protected main draft changes; or
18. the work is paused without transferring ownership to EIR.

## Appendix B: Exact Diagnosis Controller

Create `diagnosis_controller.py` with exactly the source in the following code
block. The source is intentionally standard-library-only and stateful;
parallelizing cells or replacing it with ad hoc shell loops is unauthorized.

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PYTHON = Path("/home/hyl/.virtualenvs/llm_app/bin/python")
PLUGIN_MODULE = "arkscope_edgar_import_probe"
TARGET = "tests/test_api.py::TestHealth::test_status"
MOUNT = "tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app"
SEC_FILE = "tests/test_sec_filings.py"
OUTER_TIMEOUT_SECONDS = 75
INTERRUPT_GRACE_SECONDS = 5
LEAKER_NAME = "PyrateLimiter's Leaker"

LATIN_ORDERS = (
    ("00", "11", "01", "10"),
    ("10", "01", "11", "00"),
    ("01", "10", "00", "11"),
    ("11", "00", "10", "01"),
)

PHASES: dict[str, dict[str, Any]] = {
    "phase1": {
        "seed": 20260729,
        "prefix": "A",
        "selectors": {
            "A0B0": [TARGET],
            "A0B1": [MOUNT, TARGET],
            "A1B0": [SEC_FILE, TARGET],
            "A1B1": [SEC_FILE, MOUNT, TARGET],
        },
        "expected": {
            "A0B0": (1, "4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f"),
            "A0B1": (2, "c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc"),
            "A1B0": (7, "a3af106460307042ae13af1a2b6759c34e25788102cee94b3115346a8afcb484"),
            "A1B1": (8, "7d7b4d75fee81eb9305cb3651c7940e7ca87afe3539a198d5ec45eefea547644"),
        },
    },
    "phase2": {
        "seed": 20260730,
        "prefix": "E",
        "selectors": {
            "E0B0": [TARGET],
            "E0B1": [MOUNT, TARGET],
            "E1B0": [TARGET],
            "E1B1": [MOUNT, TARGET],
        },
        "expected": {
            "E0B0": (1, "4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f"),
            "E0B1": (2, "c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc"),
            "E1B0": (1, "4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f"),
            "E1B1": (2, "c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc"),
        },
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _worktree_data_files(repo: Path) -> list[str]:
    data = repo / "data"
    if not data.exists():
        return []
    return sorted(
        str(path.relative_to(repo))
        for path in data.rglob("*")
        if path.is_file() or path.is_symlink()
    )


def _schedule_payload(phase: str) -> dict[str, Any]:
    config = PHASES[phase]
    orders = [list(order) for _ in range(5) for order in LATIN_ORDERS]
    random.Random(config["seed"]).shuffle(orders)
    blocks = []
    for block_number, order in enumerate(orders, start=1):
        cells = [
            f'{config["prefix"]}{code[0]}B{code[1]}'
            for code in order
        ]
        blocks.append({"block": block_number, "cells": cells})
    return {
        "schema_version": 1,
        "phase": phase,
        "seed": config["seed"],
        "blocks": blocks,
    }


def prepare(root: Path, controller: Path, plugin: Path, verifier: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    scratch = root / "scratch"
    scratch.mkdir()
    copied_controller = scratch / "diagnosis_controller.py"
    copied_plugin = scratch / f"{PLUGIN_MODULE}.py"
    copied_verifier = scratch / "independent_verifier.py"
    copied_controller.write_bytes(controller.read_bytes())
    copied_plugin.write_bytes(plugin.read_bytes())
    copied_verifier.write_bytes(verifier.read_bytes())
    schedules: dict[str, dict[str, object]] = {}
    for phase in PHASES:
        path = root / f"schedule-{phase}.json"
        _atomic_json(path, _schedule_payload(phase))
        schedules[phase] = {
            "path": str(path),
            "sha256": _sha256(path),
        }
    _atomic_json(
        root / "preflight.json",
        {
            "schema_version": 1,
            "python": str(PYTHON),
            "controller": {
                "path": str(copied_controller),
                "bytes": copied_controller.stat().st_size,
                "sha256": _sha256(copied_controller),
            },
            "plugin": {
                "path": str(copied_plugin),
                "bytes": copied_plugin.stat().st_size,
                "sha256": _sha256(copied_plugin),
            },
            "verifier": {
                "path": str(copied_verifier),
                "bytes": copied_verifier.stat().st_size,
                "sha256": _sha256(copied_verifier),
            },
            "schedules": schedules,
        },
    )


def _minimal_env(root: Path, trial: Path, phase: str, cell: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for name in ("PATH", "LANG", "LC_ALL", "TZ"):
        if value := os.environ.get(name):
            env[name] = value
    home = trial / "home"
    tmp = trial / "tmp"
    for directory in (home, tmp, trial / "locks", trial / "edgar"):
        directory.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "HOME": str(home),
            "TMPDIR": str(tmp),
            "XDG_CACHE_HOME": str(trial / "xdg-cache"),
            "PYTHONHASHSEED": "0",
            "PYTHONUNBUFFERED": "1",
            "ARKSCOPE_DISABLE_SCHEDULER": "1",
            "ARKSCOPE_LOCK_DIR": str(trial / "locks"),
            "ARKSCOPE_PROFILE_DB": str(trial / "profile_state.db"),
            "ARKSCOPE_MARKET_DB": str(trial / "market_data.db"),
            "ARKSCOPE_MACRO_CALENDAR_DB": str(trial / "macro_calendar.db"),
            "ARKSCOPE_SA_DB": str(trial / "sa_capture.db"),
            "ARKSCOPE_CONSENSUS_DB": str(trial / "consensus.db"),
            "EDGAR_LOCAL_DATA_DIR": str(trial / "edgar"),
        }
    )
    if phase == "phase2":
        env["PYTHONPATH"] = str(root / "scratch")
        env["ARKSCOPE_DIAG_IMPORT_EDGAR"] = "1" if cell.startswith("E1") else "0"
        env["ARKSCOPE_DIAG_THREAD_SNAPSHOT"] = str(trial / "threads.json")
    return env


def _pytest_args(root: Path, trial: Path, phase: str, cell: str) -> list[str]:
    args = [
        str(PYTHON),
        "-m",
        "pytest",
        "-vv",
        "--tb=short",
        "-o",
        "faulthandler_timeout=60",
        "-o",
        f"cache_dir={trial / 'pytest-cache'}",
        "--basetemp",
        str(trial / "pytest-tmp"),
    ]
    if phase == "phase2":
        args.extend(["-p", PLUGIN_MODULE])
    args.extend(PHASES[phase]["selectors"][cell])
    return args


def _verify_snapshot(path: Path, cell: str) -> tuple[bool, dict[str, Any] | None]:
    if not path.is_file():
        return False, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    before = [row["name"] for row in payload.get("before", [])]
    after = [row["name"] for row in payload.get("after", [])]
    expected_enabled = cell.startswith("E1")
    valid = (
        payload.get("import_edgar") is expected_enabled
        and LEAKER_NAME not in before
        and after.count(LEAKER_NAME) == (1 if expected_enabled else 0)
    )
    return valid, payload


def _run_attempt(
    repo: Path,
    root: Path,
    phase: str,
    block: int,
    position: int,
    cell: str,
    attempt: int,
) -> dict[str, Any]:
    data_files_before = _worktree_data_files(repo)
    if data_files_before:
        raise RuntimeError(f"worktree data is not empty: {data_files_before}")
    trial_id = f"{phase}-b{block:02d}-p{position}-{cell}-a{attempt}"
    trial = root / "trials" / trial_id
    trial.mkdir(parents=True, exist_ok=False)
    env = _minimal_env(root, trial, phase, cell)
    args = _pytest_args(root, trial, phase, cell)
    stdout_path = trial / "stdout.txt"
    stderr_path = trial / "stderr.txt"
    started_wall = time.time()
    started_mono = time.monotonic()
    timed_out = False
    interrupted = False
    killed = False
    operator_interrupted = False
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        process = subprocess.Popen(
            args,
            cwd=repo,
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=OUTER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            interrupted = True
            os.killpg(process.pid, signal.SIGINT)
            try:
                returncode = process.wait(timeout=INTERRUPT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                killed = True
                os.killpg(process.pid, signal.SIGKILL)
                returncode = process.wait(timeout=INTERRUPT_GRACE_SECONDS)
        except KeyboardInterrupt:
            operator_interrupted = True
            interrupted = True
            os.killpg(process.pid, signal.SIGINT)
            try:
                returncode = process.wait(timeout=INTERRUPT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                killed = True
                os.killpg(process.pid, signal.SIGKILL)
                returncode = process.wait(timeout=INTERRUPT_GRACE_SECONDS)
    ended_wall = time.time()
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    combined = f"{stdout_text}\n{stderr_text}"
    signature = {
        "dump": "Timeout (0:01:00)!" in combined,
        "target": TARGET in combined,
        "future_result": "concurrent/futures/_base.py" in combined and " in result" in combined,
        "spawn": "_spawn_task_from_thread" in combined,
        "portal": "start_task_soon" in combined,
        "testclient": "starlette/testclient.py" in combined and " in __enter__" in combined,
    }
    snapshot_valid = True
    snapshot = None
    if phase == "phase2":
        snapshot_valid, snapshot = _verify_snapshot(trial / "threads.json", cell)
    data_files_after = _worktree_data_files(repo)
    boundary_violation = bool(data_files_after)
    if operator_interrupted or boundary_violation or not snapshot_valid:
        outcome = "invalid_trial"
    elif timed_out and all(signature.values()):
        outcome = "stall_matching_portal_signature"
    elif timed_out:
        outcome = "timeout_without_expected_dump"
    elif returncode == 0:
        outcome = "pass"
    else:
        outcome = "terminated_nonstall_failure"
    record = {
        "schema_version": 1,
        "trial_id": trial_id,
        "phase": phase,
        "block": block,
        "position": position,
        "cell": cell,
        "attempt": attempt,
        "command": args,
        "env_names": sorted(env),
        "pid": process.pid,
        "started_at_epoch": started_wall,
        "ended_at_epoch": ended_wall,
        "duration_seconds": time.monotonic() - started_mono,
        "returncode": returncode,
        "timed_out": timed_out,
        "interrupted": interrupted,
        "killed": killed,
        "operator_interrupted": operator_interrupted,
        "signature": signature,
        "snapshot_valid": snapshot_valid,
        "snapshot": snapshot,
        "worktree_data_files_before": data_files_before,
        "worktree_data_files_after": data_files_after,
        "boundary_violation": boundary_violation,
        "outcome": outcome,
        "stdout_sha256": _sha256(stdout_path),
        "stderr_sha256": _sha256(stderr_path),
    }
    _atomic_json(trial / "record.json", record)
    return record


def _load_schedule(root: Path, phase: str) -> dict[str, Any]:
    return json.loads((root / f"schedule-{phase}.json").read_text(encoding="utf-8"))


def _verify_preflight(root: Path, phase: str) -> None:
    preflight = json.loads((root / "preflight.json").read_text(encoding="utf-8"))
    controller = Path(preflight["controller"]["path"])
    plugin = Path(preflight["plugin"]["path"])
    verifier = Path(preflight["verifier"]["path"])
    schedule = Path(preflight["schedules"][phase]["path"])
    expected = (
        (controller, preflight["controller"]["sha256"]),
        (plugin, preflight["plugin"]["sha256"]),
        (verifier, preflight["verifier"]["sha256"]),
        (schedule, preflight["schedules"][phase]["sha256"]),
    )
    for path, digest in expected:
        if not path.is_file() or _sha256(path) != digest:
            raise RuntimeError(f"preflight artifact changed: {path}")
    if Path(__file__).resolve() != controller.resolve():
        raise RuntimeError("run the copied controller recorded in preflight.json")


def _slot_records(
    root: Path,
    phase: str,
    block: int,
    position: int,
    cell: str,
) -> list[dict[str, Any]]:
    prefix = f"{phase}-b{block:02d}-p{position}-{cell}-a"
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "trials").glob(f"{prefix}*/record.json"))
    ]


def run_phase(repo: Path, root: Path, phase: str, through_block: int) -> None:
    if through_block not in {10, 15, 20}:
        raise ValueError("through_block must be 10, 15, or 20")
    _verify_preflight(root, phase)
    schedule = _load_schedule(root, phase)
    (root / "trials").mkdir(exist_ok=True)
    for block_entry in schedule["blocks"][:through_block]:
        block = int(block_entry["block"])
        for position, cell in enumerate(block_entry["cells"], start=1):
            existing = _slot_records(root, phase, block, position, cell)
            if any(record["boundary_violation"] for record in existing):
                raise RuntimeError(f"existing worktree data boundary violation: {phase}/{block}/{cell}")
            if any(record["outcome"] == "timeout_without_expected_dump" for record in existing):
                raise RuntimeError(f"existing unexpected timeout: {phase}/{block}/{cell}")
            valid = [record for record in existing if record["outcome"] != "invalid_trial"]
            if len(valid) > 1:
                raise RuntimeError(f"multiple valid records: {phase}/{block}/{cell}")
            if valid:
                continue
            attempted = {int(record["attempt"]) for record in existing}
            if not attempted.issubset({0, 1}):
                raise RuntimeError(f"unexpected attempt number: {phase}/{block}/{cell}")
            for attempt in (0, 1):
                if attempt in attempted:
                    continue
                record = _run_attempt(repo, root, phase, block, position, cell, attempt)
                if record["operator_interrupted"]:
                    raise RuntimeError(f"operator interrupted trial: {record['trial_id']}")
                if record["boundary_violation"]:
                    raise RuntimeError(f"worktree data boundary violation: {record['trial_id']}")
                if record["outcome"] == "timeout_without_expected_dump":
                    raise RuntimeError(f"unexpected timeout: {record['trial_id']}")
                if record["outcome"] != "invalid_trial":
                    break
            else:
                raise RuntimeError(f"two invalid attempts for {phase} block {block} {cell}")
    summary(root, phase, through_block)


def _records(root: Path, phase: str, through_block: int) -> list[dict[str, Any]]:
    records = []
    for path in sorted((root / "trials").glob(f"{phase}-*/record.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if int(record["block"]) <= through_block:
            records.append(record)
    return records


def summary(root: Path, phase: str, through_block: int) -> dict[str, Any]:
    records = _records(root, phase, through_block)
    cells = sorted(PHASES[phase]["selectors"])
    counts = {
        cell: {
            outcome: sum(
                1
                for row in records
                if row["cell"] == cell and row["outcome"] == outcome
            )
            for outcome in (
                "pass",
                "terminated_nonstall_failure",
                "stall_matching_portal_signature",
                "timeout_without_expected_dump",
                "invalid_trial",
            )
        }
        for cell in cells
    }
    stalls = {
        cell: counts[cell]["stall_matching_portal_signature"]
        for cell in cells
    }
    prefix = PHASES[phase]["prefix"]
    flags = {
        "main_first_factor": (
            stalls[f"{prefix}0B0"] == 0
            and stalls[f"{prefix}0B1"] == 0
            and stalls[f"{prefix}1B0"] >= 3
            and stalls[f"{prefix}1B1"] >= 3
            and stalls[f"{prefix}1B0"] + stalls[f"{prefix}1B1"] >= 8
        ),
        "main_mount_factor": (
            stalls[f"{prefix}0B0"] == 0
            and stalls[f"{prefix}1B0"] == 0
            and stalls[f"{prefix}0B1"] >= 3
            and stalls[f"{prefix}1B1"] >= 3
            and stalls[f"{prefix}0B1"] + stalls[f"{prefix}1B1"] >= 8
        ),
        "interaction": (
            stalls[f"{prefix}1B1"] >= 6
            and all(
                stalls[cell] == 0
                for cell in (f"{prefix}0B0", f"{prefix}0B1", f"{prefix}1B0")
            )
        ),
        "ubiquitous": all(stalls[cell] >= 2 for cell in cells),
        "first_factor_not_necessary": any(
            stalls[cell] > 0 for cell in (f"{prefix}0B0", f"{prefix}0B1")
        ),
        "mount_not_necessary": any(
            stalls[cell] > 0 for cell in (f"{prefix}0B0", f"{prefix}1B0")
        ),
    }
    payload = {
        "schema_version": 1,
        "phase": phase,
        "through_block": through_block,
        "counts": counts,
        "flags": flags,
        "early_stop_eligible": through_block in {10, 15}
        and any(
            flags[name]
            for name in (
                "main_first_factor",
                "main_mount_factor",
                "interaction",
                "ubiquitous",
            )
        ),
    }
    _atomic_json(root / f"summary-{phase}-b{through_block:02d}.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, required=True)
    prepare_parser.add_argument("--controller-source", type=Path, required=True)
    prepare_parser.add_argument("--plugin-source", type=Path, required=True)
    prepare_parser.add_argument("--verifier-source", type=Path, required=True)
    run_parser = subparsers.add_parser("run-phase")
    run_parser.add_argument("--repo", type=Path, required=True)
    run_parser.add_argument("--root", type=Path, required=True)
    run_parser.add_argument("--phase", choices=tuple(PHASES), required=True)
    run_parser.add_argument("--through-block", type=int, required=True)
    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("--root", type=Path, required=True)
    summary_parser.add_argument("--phase", choices=tuple(PHASES), required=True)
    summary_parser.add_argument("--through-block", type=int, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(
            args.root.resolve(),
            args.controller_source.resolve(),
            args.plugin_source.resolve(),
            args.verifier_source.resolve(),
        )
    elif args.command == "run-phase":
        run_phase(args.repo.resolve(), args.root.resolve(), args.phase, args.through_block)
    else:
        summary(args.root.resolve(), args.phase, args.through_block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Appendix A: Exact Import-Only Plugin

Create `arkscope_edgar_import_probe.py` with exactly:

```python
from __future__ import annotations

import importlib
import json
import os
import threading
from pathlib import Path


def _threads() -> list[dict[str, object]]:
    return sorted(
        (
            {
                "name": thread.name,
                "ident": thread.ident,
                "daemon": thread.daemon,
            }
            for thread in threading.enumerate()
        ),
        key=lambda row: (str(row["name"]), int(row["ident"] or -1)),
    )


_enabled = os.environ.get("ARKSCOPE_DIAG_IMPORT_EDGAR")
if _enabled not in {"0", "1"}:
    raise RuntimeError("ARKSCOPE_DIAG_IMPORT_EDGAR must be exactly 0 or 1")

_before = _threads()
if _enabled == "1":
    importlib.import_module("edgar")
_after = _threads()


def pytest_sessionstart(session) -> None:
    output = Path(os.environ["ARKSCOPE_DIAG_THREAD_SNAPSHOT"])
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "import_edgar": _enabled == "1",
        "before": _before,
        "after": _after,
    }
    temporary = output.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
```

## Appendix C: Exact Independent Verifier

Create `independent_verifier.py` with exactly:

```python
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TARGET = "tests/test_api.py::TestHealth::test_status"
LEAKER_NAME = "PyrateLimiter's Leaker"
OUTCOMES = (
    "pass",
    "terminated_nonstall_failure",
    "stall_matching_portal_signature",
    "timeout_without_expected_dump",
    "invalid_trial",
)
PREFIX = {"phase1": "A", "phase2": "E"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def signature(stdout: str, stderr: str) -> dict[str, bool]:
    combined = f"{stdout}\n{stderr}"
    return {
        "dump": "Timeout (0:01:00)!" in combined,
        "target": TARGET in combined,
        "future_result": "concurrent/futures/_base.py" in combined and " in result" in combined,
        "spawn": "_spawn_task_from_thread" in combined,
        "portal": "start_task_soon" in combined,
        "testclient": "starlette/testclient.py" in combined and " in __enter__" in combined,
    }


def snapshot_valid(record: dict[str, Any]) -> bool:
    if record["phase"] != "phase2":
        return True
    snapshot = record.get("snapshot")
    if not isinstance(snapshot, dict):
        return False
    before = [row.get("name") for row in snapshot.get("before", [])]
    after = [row.get("name") for row in snapshot.get("after", [])]
    enabled = str(record["cell"]).startswith("E1")
    return (
        snapshot.get("import_edgar") is enabled
        and LEAKER_NAME not in before
        and after.count(LEAKER_NAME) == (1 if enabled else 0)
    )


def reconstructed_outcome(record: dict[str, Any], sig: dict[str, bool]) -> str:
    if (
        record.get("operator_interrupted")
        or record.get("boundary_violation")
        or not snapshot_valid(record)
    ):
        return "invalid_trial"
    if record.get("timed_out") and all(sig.values()):
        return "stall_matching_portal_signature"
    if record.get("timed_out"):
        return "timeout_without_expected_dump"
    if record.get("returncode") == 0:
        return "pass"
    return "terminated_nonstall_failure"


def flags_for(counts: dict[str, Counter[str]], phase: str) -> dict[str, bool]:
    prefix = PREFIX[phase]
    stalls = {
        cell: counts[cell]["stall_matching_portal_signature"]
        for cell in sorted(counts)
    }
    return {
        "main_first_factor": (
            stalls[f"{prefix}0B0"] == 0
            and stalls[f"{prefix}0B1"] == 0
            and stalls[f"{prefix}1B0"] >= 3
            and stalls[f"{prefix}1B1"] >= 3
            and stalls[f"{prefix}1B0"] + stalls[f"{prefix}1B1"] >= 8
        ),
        "main_mount_factor": (
            stalls[f"{prefix}0B0"] == 0
            and stalls[f"{prefix}1B0"] == 0
            and stalls[f"{prefix}0B1"] >= 3
            and stalls[f"{prefix}1B1"] >= 3
            and stalls[f"{prefix}0B1"] + stalls[f"{prefix}1B1"] >= 8
        ),
        "interaction": (
            stalls[f"{prefix}1B1"] >= 6
            and all(
                stalls[cell] == 0
                for cell in (f"{prefix}0B0", f"{prefix}0B1", f"{prefix}1B0")
            )
        ),
        "ubiquitous": all(value >= 2 for value in stalls.values()),
        "first_factor_not_necessary": any(
            stalls[cell] > 0 for cell in (f"{prefix}0B0", f"{prefix}0B1")
        ),
        "mount_not_necessary": any(
            stalls[cell] > 0 for cell in (f"{prefix}0B0", f"{prefix}1B0")
        ),
    }


def verify(root: Path, phase: str, through_block: int) -> dict[str, Any]:
    schedule_path = root / f"schedule-{phase}.json"
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    blocks = schedule["blocks"][:through_block]
    expected_slots = {
        (int(block["block"]), position, cell)
        for block in blocks
        for position, cell in enumerate(block["cells"], start=1)
    }
    records_by_slot: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    errors: list[str] = []
    for record_path in sorted((root / "trials").glob(f"{phase}-*/record.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if int(record["block"]) > through_block:
            continue
        slot = (int(record["block"]), int(record["position"]), str(record["cell"]))
        records_by_slot[slot].append(record)
        trial_dir = record_path.parent
        stdout_path = trial_dir / "stdout.txt"
        stderr_path = trial_dir / "stderr.txt"
        if sha256(stdout_path) != record["stdout_sha256"]:
            errors.append(f"stdout hash mismatch: {record['trial_id']}")
        if sha256(stderr_path) != record["stderr_sha256"]:
            errors.append(f"stderr hash mismatch: {record['trial_id']}")
        sig = signature(
            stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"),
        )
        if sig != record["signature"]:
            errors.append(f"signature mismatch: {record['trial_id']}")
        outcome = reconstructed_outcome(record, sig)
        if outcome != record["outcome"]:
            errors.append(f"outcome mismatch: {record['trial_id']}")
        if record.get("worktree_data_files_before") or record.get("worktree_data_files_after"):
            errors.append(f"worktree data boundary: {record['trial_id']}")
    actual_slots = set(records_by_slot)
    if actual_slots != expected_slots:
        errors.append("scheduled slot set mismatch")
    counts: dict[str, Counter[str]] = {
        f"{PREFIX[phase]}{first}B{second}": Counter()
        for first in ("0", "1")
        for second in ("0", "1")
    }
    invalid_attempts = 0
    for slot in sorted(expected_slots):
        records = sorted(records_by_slot.get(slot, []), key=lambda row: int(row["attempt"]))
        attempts = [int(row["attempt"]) for row in records]
        if attempts not in ([0], [0, 1]):
            errors.append(f"attempt sequence mismatch: {slot}")
        valid = [row for row in records if row["outcome"] != "invalid_trial"]
        if len(valid) != 1:
            errors.append(f"valid outcome count mismatch: {slot}")
        for row in records:
            counts[str(row["cell"])][str(row["outcome"])] += 1
            invalid_attempts += row["outcome"] == "invalid_trial"
    position_counts = Counter()
    for block in schedule["blocks"]:
        for position, cell in enumerate(block["cells"], start=1):
            position_counts[(cell, position)] += 1
    expected_cells = sorted(counts)
    if len(schedule["blocks"]) != 20:
        errors.append("schedule does not have 20 blocks")
    for cell in expected_cells:
        for position in range(1, 5):
            if position_counts[(cell, position)] != 5:
                errors.append(f"schedule position imbalance: {cell}/{position}")
    flags = flags_for(counts, phase)
    early_stop_eligible = through_block in {10, 15} and any(
        flags[name]
        for name in (
            "main_first_factor",
            "main_mount_factor",
            "interaction",
            "ubiquitous",
        )
    )
    payload = {
        "schema_version": 1,
        "phase": phase,
        "through_block": through_block,
        "schedule_sha256": sha256(schedule_path),
        "counts": {
            cell: {outcome: counts[cell][outcome] for outcome in OUTCOMES}
            for cell in expected_cells
        },
        "invalid_attempts": invalid_attempts,
        "flags": flags,
        "early_stop_eligible": early_stop_eligible,
        "errors": errors,
        "ok": not errors,
    }
    output = root / f"reconstruction-{phase}-b{through_block:02d}.json"
    atomic_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=tuple(PREFIX), required=True)
    parser.add_argument("--through-block", type=int, choices=(10, 15, 20), required=True)
    args = parser.parse_args()
    payload = verify(args.root.resolve(), args.phase, args.through_block)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```
