# EIR-005 Machine-State Observer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:executing-plans` to execute this reviewed plan,
> `superpowers:test-driven-development` for the diagnostic control code,
> `superpowers:requesting-code-review` before campaign admission, and
> `superpowers:verification-before-completion` before any GREEN, verdict, or
> closeout claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: EXACT-SOURCE PLAN REVIEW NEXT**

**Goal:** Run one finite, paired, read-only machine-state campaign that
distinguishes supported shared wakeup state, self-pipe integrity failure,
surface-specific state, observer perturbation, unreduced matching stalls, or
failure to obtain the matching window, without changing ArkScope product/test
behavior or the official price runner/bank.

**Architecture:** A SHA-pinned parent controller launches the existing T1 and
T6 tier selections with the exact frozen v3 progress plugin and reporter. The
control arm records only kernel/process state. The observed arm additionally
loads one read-only pytest plugin whose daemon thread snapshots all selector
loops, their owner threads, ready/scheduled/task state, selector
registrations, self-pipe endpoints, and non-consuming `FIONREAD`. The parent
joins those snapshots to `/proc`, epoll `fdinfo`, and inode-filtered `ss`
rows. A separately pinned verifier ignores controller verdict claims,
reconstructs attempt classifications from raw artifacts, selects the target
loop from thread/stack evidence, recomputes the six-boolean late-state vector,
and applies O4/O2/O1/O3/O5/O6 precedence.

**Tech Stack:** Python 3.10.12, pytest 8.4.1, CPython selector event loops,
Linux `/proc`, `FIONREAD`, `ss`/netlink, process groups, JSONL, SHA-256, the
frozen price runner v3 progress/reporter protocol, and Git worktree isolation.

---

## 1. Authority, Scope, And Review State

1. Design authority:
   `docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md`.
2. Sequence authority: `docs/design/PROJECT_PRIORITY_MAP.md`.
3. Incident owner: `EIR-005` in
   `docs/design/ENGINEERING_ISSUE_REGISTER.md`.
4. Observer branch: `codex/eir-005-machine-state-observer`.
5. Grounding price tip:
   `5ff3608a979519b7aee8b68dc9863ca852ac1ce1`.
6. Reviewed observer-spec tip:
   `e11851cb8bef9fa9787503b99b7885975eaaf3ec`.
7. Mainline base: `e6d4b7fac7e91c59e855a7f543caac4f57094d86`.
8. Official price-v3 artifact root: `/tmp/price-truth-tier-v3`.
9. New observer runtime root:
   `/tmp/eir005-machine-state-observer-v1`.

Independent full-document spec review returned GREEN with zero findings. It
verified the six-boolean load-bearing vector, O1-O6 precedence, the two fixed
surfaces, finite paired budget, read-only boundary, conditional-only strace,
and the explicit return to price banking after closeout.

This plan adds exact source and executable controls. It does **not** authorize
the behavioral campaign until focused plan review independently extracts the
appendices, reproduces every source SHA, replays the probes, and confirms all
eight mutations.

The main worktree's known untracked drafts remain user-owned and protected:

```text
docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md
docs/design/SCRIPTS_RETIREMENT_DECISION.md
```

They are not copied, edited, staged, referenced as authority, or included in
an artifact manifest.

### 1.1 Product boundary

This line changes no `src/**`, `tests/**`, frontend, extension, desktop,
dependency, configuration, production database, provider, Gateway, scheduler,
or official price-v3 artifact. The scratch plugin contributes zero tests. Its
observations are diagnostic and never enter price admission or a banked tier.

The selected T1/T6 path/node manifests are copied byte-for-byte from the
official v3 root. Running only either target node is prohibited because it
would remove predecessor context.

### 1.2 Branch and merge mechanics

The observer branch is a child of the price-truth tip. During plan review and
campaign execution:

- `codex/price-collection-truth` remains frozen at `5ff3608a...`;
- `master` remains at `e6d4b7fa...`;
- observer commits remain linear descendants of the price history;
- no observer commit is rebased, cherry-picked, or merged around that
  ancestry; and
- the official v3 bank remains unchanged.

After a reviewed O1-O6 closeout:

1. focused review first confirms the exact observer closeout tip;
2. `master` fast-forwards from `e6d4b7fa...` to that full docs-only tip;
3. `codex/price-collection-truth` fast-forwards from `5ff3608a...` to the same
   tip;
4. the observer worktree/branch may then be removed; and
5. a new price-only handoff commit updates the price plan's restart base to
   the merged closeout tip without changing any product ledger, predicted
   hash, runner-v3 identity, or banked tier.

If either fast-forward is impossible, stop. Do not improvise a rebase or
cherry-pick that separates the observer result from its reviewed price
lineage.

---

## 2. Exact Identities

### 2.1 New exact source

Appendices A-C are the runtime authority:

| Artifact | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `eir005_observer_controller.py` | 2758 | 97772 | `9726f1b5ffa346992d2f44945d1224e402fdacc052554f452d4d72bc87205a41` |
| `eir005_observer_plugin.py` | 596 | 19409 | `ac5b343613ee6d83957f2507f1f11555f04a72856998e319ffaa1d0db1cea164` |
| `eir005_observer_verifier.py` | 686 | 21784 | `063544cfbf4b64a898b6088e1310a8690b17b4b616aeef7f77ffeef2aa8c7f77` |

The controller imports only the **copied** v3 runner module in the new root.
It never imports a record, summary, or banked result from the official root.

### 2.2 Reused frozen identities

Copy these exact files from `/tmp/price-truth-tier-v3`:

| Destination | Official source | SHA-256 |
|---|---|---|
| `price_truth_tier_runner.py` | same | `bb5d2245071aa48f8f0ad4e28a0966aa26744f213dcec65a69d947a383fd9de9` |
| `arkscope_price_truth_tier_reporter.py` | same | `09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928` |
| `A.paths` | `T1.paths` | `d222b59322f5936607676b21163b06ecf3e6eb74df7e3df538b7b87245a86cc9` |
| `A.nodes` | `base-T1.nodes` | `d74b9a2bf40a3b13a873be7337f4ad5da7e9e14865f795c0053820b083e2ee30` |
| `P.paths` | `T6.paths` | `9f04af18ffdb255646a2ac294b4e8beb825657d86fdafa253a12008d7ebf93ad` |
| `P.nodes` | `base-T6.nodes` | `b6979e10b7d72b2b70b69e14ab8b8e4dd70b2e10484aa72e8c1d5ac92547500c` |

The official summary remains
`a5686da09e1715e1ea81b618826c956b96649bf12075ccf230a387c87782b198`.
The 3,262-entry official manifest remains
`ff189a4433b571c671ef7e4db82e63c94071d869e4ed48410f2a65c25e622f75`.

### 2.3 Schedule and probes

Appendix D is exactly `18` lines / `883` bytes, SHA-256
`92068b60acd7d4ff06a7d84c33be84406dccb5ecd58b1da9761b31658f1f83a9`.
It schedules sixteen attempts:

```text
A B1 C/O   P B1 O/C
A B2 O/C   P B2 C/O
A B3 C/O   P B3 O/C
A B4 O/C   P B4 C/O
```

Each same-surface pair is adjacent. Early stop is checked only after a complete
block. At most one invalid replacement per surface is permitted; the absolute
launch cap is eighteen.

Appendix E fixtures are:

| Artifact | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `probes/probe_pass.py` | 6 | 81 | `0f86ccdb5c7fc21c320cf4423dfde496603a165a0d7752c7b76bbb3e81c0e466` |
| `probes/probe_interruptible.py` | 11 | 223 | `1a5d026c464f0e8f2c199a28d0c48aea4bbc8a0afda35f1cde9f58eda0c60fd1` |
| `probes/probe_ignore_sigint.py` | 20 | 422 | `738de35828baf135c937e7a91146b46b1450515d7d76168b0caded0eae074940` |
| `probes/probe.nodes` | 1 | 38 | `d245d2628d188bb1a1f97f134ae1c4428969545908481de96c2e87e2e864d8c2` |

The pristine probe summary is deterministic and must be SHA-256
`5f95b3d9731d93d9bc979760343d59152b68c10d60812b8f8f66566b539b24bc`.
PID, timestamps, preflight, transcript, and per-attempt record hashes are host
observations and are recorded rather than predicted.

### 2.4 Sampling and classification

Runtime bounds are immutable:

```text
faulthandler dump       120s
no-progress deadline    150s
SIGINT grace             10s
leader/EOF handshake      1s
process-group drain       1s
```

Observed target-relative samples are:

```text
target_start  0s
early         1s
pre_dump    110s
post_dump   121s
late        136s
pre_deadline 148s
pre_sigint  at the 150s breach before signaling
post_sigint bounded during the existing 10s grace
target_finish on natural completion
```

Probe-only bounds are `2/3/1` for dump/deadline/grace. They cannot enter a
runtime campaign record.

Attempt classes are exactly `matching_stall`, `complete_natural`,
`terminated_nonstall_failure`, and `invalid`. A deadline breach is a matching
stall only when the current-window dump exists, cleanup completes, and the
active node is the pinned target.

---

## 3. Source Construction And Preflight

### Task 0: Re-ground and extract exact source

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-31-eir-005-machine-state-observer-design.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Add: this plan
- Read only: `/tmp/price-truth-tier-v3/**`

- [ ] **Step 1: Re-ground branch and protected boundaries.**

```bash
test "$(git branch --show-current)" = \
  "codex/eir-005-machine-state-observer"
test "$(git merge-base HEAD 5ff3608a979519b7aee8b68dc9863ca852ac1ce1)" = \
  "5ff3608a979519b7aee8b68dc9863ca852ac1ce1"
test "$(git rev-parse codex/price-collection-truth)" = \
  "5ff3608a979519b7aee8b68dc9863ca852ac1ce1"
test "$(git -C /mnt/md0/PycharmProjects/ArkScope rev-parse HEAD)" = \
  "e6d4b7fac7e91c59e855a7f543caac4f57094d86"
git diff --quiet 5ff3608a -- src tests apps extensions desktop \
  pyproject.toml requirements.txt requirements-dev.txt package.json \
  package-lock.json
git status --short
```

Expected: the reviewed plan tip is clean; no product/test/dependency change.
The two known main-worktree drafts are absent from this worktree.

- [ ] **Step 2: Require a fresh runtime root.**

```bash
export EIR005_PLAN="$PWD/docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md"
export EIR005_ROOT=/tmp/eir005-machine-state-observer-v1
test ! -e "$EIR005_ROOT"
mkdir -p "$EIR005_ROOT/probes"
```

No prior construction, probe, mutation, or campaign root may be reused.

- [ ] **Step 3: Extract Appendices A-E.**

Use the same closed extraction form for each marker pair:

```bash
awk '
  /^<!-- EIR005_CONTROLLER_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_CONTROLLER_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/eir005_observer_controller.py"

awk '
  /^<!-- EIR005_PLUGIN_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_PLUGIN_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/eir005_observer_plugin.py"

awk '
  /^<!-- EIR005_VERIFIER_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_VERIFIER_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/eir005_observer_verifier.py"

awk '
  /^<!-- EIR005_SCHEDULE_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_SCHEDULE_END -->$/ { emit=0 }
  emit && $0 != "```json" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/observer-schedule.json"

awk '
  /^<!-- EIR005_PROBE_PASS_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_PROBE_PASS_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/probes/probe_pass.py"

awk '
  /^<!-- EIR005_PROBE_INTERRUPTIBLE_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_PROBE_INTERRUPTIBLE_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/probes/probe_interruptible.py"

awk '
  /^<!-- EIR005_PROBE_IGNORE_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_PROBE_IGNORE_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/probes/probe_ignore_sigint.py"

awk '
  /^<!-- EIR005_PROBE_NODES_BEGIN -->$/ { emit=1; next }
  /^<!-- EIR005_PROBE_NODES_END -->$/ { emit=0 }
  emit && $0 != "```text" && $0 != "```" { print }
' "$EIR005_PLAN" > "$EIR005_ROOT/probes/probe.nodes"
```

Do not copy source from another `/tmp` construction root.

- [ ] **Step 4: Copy only the six reviewed v3 inputs.**

```bash
cp /tmp/price-truth-tier-v3/price_truth_tier_runner.py \
  "$EIR005_ROOT/price_truth_tier_runner.py"
cp /tmp/price-truth-tier-v3/arkscope_price_truth_tier_reporter.py \
  "$EIR005_ROOT/arkscope_price_truth_tier_reporter.py"
cp /tmp/price-truth-tier-v3/T1.paths "$EIR005_ROOT/A.paths"
cp /tmp/price-truth-tier-v3/base-T1.nodes "$EIR005_ROOT/A.nodes"
cp /tmp/price-truth-tier-v3/T6.paths "$EIR005_ROOT/P.paths"
cp /tmp/price-truth-tier-v3/base-T6.nodes "$EIR005_ROOT/P.nodes"
```

No record, summary, bank, non-passing list, or prior attempt directory is
copied.

- [ ] **Step 5: Verify all predicted identities and compile.**

```bash
wc -l -c \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  "$EIR005_ROOT/eir005_observer_plugin.py" \
  "$EIR005_ROOT/eir005_observer_verifier.py"
sha256sum \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  "$EIR005_ROOT/eir005_observer_plugin.py" \
  "$EIR005_ROOT/eir005_observer_verifier.py" \
  "$EIR005_ROOT/observer-schedule.json" \
  "$EIR005_ROOT/probes/"*
PYTHONPATH="$EIR005_ROOT" \
  /home/hyl/.virtualenvs/llm_app/bin/python -m py_compile \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  "$EIR005_ROOT/eir005_observer_plugin.py" \
  "$EIR005_ROOT/eir005_observer_verifier.py"
```

Every value must match §2 exactly.

- [ ] **Step 6: Create the isolated empty data boundary.**

```bash
mkdir -p data
test -z "$(find data -mindepth 1 -print -quit)"
```

If an existing ignored fixture is found, move it reversibly to a separately
recorded quarantine path with inode and SHA evidence. Never compare by
basename alone and never use production data.

- [ ] **Step 7: Build the closed preflight.**

```bash
PYTHONPATH="$EIR005_ROOT" \
  /home/hyl/.virtualenvs/llm_app/bin/python \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  prepare-preflight \
  --artifact-root "$EIR005_ROOT" \
  --repo "$PWD"
```

This command:

- rehashes all 3,262 official-v3 manifest entries;
- checks the six copied v3 identities;
- proves the T1/T6 node manifests match official bytes;
- checks protected Git paths against `5ff3608a...`;
- records interpreter, pytest, dependency, Git, PATH, and source identities;
- opens a controlled socketpair and requires inode-matched `ss` receive queue
  evidence; and
- rejects the official/frozen roots as output.

If the managed sandbox denies Unix socket send or netlink `ss`, rerun this
exact SHA-pinned command through the approved unsandboxed execution boundary.
If the user/reviewer executes it, they return the root manifest and preflight,
not a prose-only result.

---

## 4. RED-First Control Verification

### Task 1: Run the pristine probe suite

- [ ] **Step 1: Run all required probes before behavioral attempts.**

```bash
PYTHONPATH="$EIR005_ROOT" \
  /home/hyl/.virtualenvs/llm_app/bin/python \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  probe-suite \
  --preflight "$EIR005_ROOT/observer-preflight.json"
sha256sum "$EIR005_ROOT/probe-summary.json"
```

Expected summary SHA:
`5f95b3d9731d93d9bc979760343d59152b68c10d60812b8f8f66566b539b24bc`.

The nine design probes, one mutation-specific `ss` fail-closed probe, and one
static gate prove:

1. plugin collection identity and a real O-arm natural subprocess;
2. healthy loop shape;
3. queued callback/wake byte without consumption;
4. FIONREAD/epoll/`ss` inode join;
5. two loop owners without first-loop selection;
6. argument/local/exception/path/`repr` sanitization;
7. SIGINT-natural and SIGKILL cleanup paths;
8. paired-verifier rejection of either missing arm and controller claims;
9. frozen-root/preflight refusal; and
10. unavailable `ss` cannot be reclassified as an empty receive queue; and
11. no prohibited target-loop intervention call or assignment.

- [ ] **Step 2: Inspect the transport and signal records.**

Require:

| Probe | Required raw result |
|---|---|
| `probe-observer-transport` | `complete_natural`, observer ready, active `target_start` snapshot, no signal |
| `probe-signal-interruptible` | `matching_stall`, current-window dump, SIGINT, no SIGKILL |
| `probe-signal-ignored` | `matching_stall`, current-window dump, SIGINT then SIGKILL, no live PGID |

Do not pin host timestamps or per-run record hashes.

### Task 2: Prove all eight mutations

Each mutation gets a fresh root
`/tmp/eir005-machine-state-observer-v1-mN`. Seed only the pristine source,
schedule, fixtures, copied v3 runner/reporter, and A/P manifests. Build a new
preflight after applying the mutation.

| ID | Exact mutation | Owning probe | Mutated source SHA-256 | Portable diff SHA-256 | Required RED |
|---|---|---|---|---|---|
| M1 | `_queued_bytes`: replace `return max(0, int(value[0]))` with `return 0` | `queued_wake` | `952aa1da2b0f1ff1f160a55deb95f59224fe9fde989657b9a4175f07ca42990f` | `53e5c6b4d39569ed507da6b07dea4d62f09ddc8fb619febb49d1d30f25262392` | `queued wake was not observed` |
| M2 | clear `registrations` immediately before sorting | `healthy_loop` | `13a9113fdbc4517471e0427d7ccc5192573d84683479871a8a90393e1419d46a` | `78495ceffab4d5bc605401cead99437d98d80b1a4ebdb7948885f6c3e796340f` | healthy loop incomplete |
| M3 | `_loop_candidates`: return `loops[:1]` | `multiple_loops` | `4245f3c01492b5c164d235e8d35cd3ac74404100e1aa39f696608ab8a6e09bee` | `28b5fc0641d389c4ef6024392683d220be467ec58a449fc946161f253de9a2ab` | loops collapsed |
| M4 | `_qualified_name`: return raw `repr(value)` | `sanitization` | `0c0352e7cf39865a557bcd17fe93db24bf9864e4b1d023727b5db750997f814b` | `8e8796ec43bc26cb7aeae74599a2b8f18ea623f17bab38b05458d42ec73112ee` | prohibited content leaked |
| M5 | `_derive_result`: return non-null controller claim | `paired_verifier` | `7d88e2c8ed39d239995d4b9959c01bfbf67803fc4efca9e82c1b84acbae7f503` | `89b274df5b6a83eebba9e35a90adb82c048a8ed2c8912e8d61236990f51a6d1f` | paired verifier fails |
| M6 | permit one record and arm subset in `_paired_block_qualifies` | `paired_verifier` | `8135be7e0a11da29c0fac31da9ba220a932aea7448f9ba38b52629dfeb4acb93` | `fde48136951f5d27748192625b1d96c1116a2e66e66f9bed6d0549d3493da364` | paired verifier fails |
| M7 | `_ss_rows`: nonzero `ss` returns `[]` | `ss_fail_closed` | `09f0f8ffc89725663a784965171229bdf40191a57c83d8f3c54ab64920dde298` | `1916368b29d32c86c0770b9fbfda1384efa349fb12ddd8d2b57dcf31e667ebab` | unavailable became empty |
| M8 | `_assert_artifact_root_safe`: unconditional return | `frozen_root` | `a732646ce37c3435bfab89984d5f1acbbac29b5bcbac848c94f8b36fe13882f7` | `dbcdf279b02674b434e25e88256fb4247a29097c23969842831bf9d449bf152b` | official root accepted |

- [ ] **Step 1: Seed, mutate, preflight, and run each arm from the closed
  mapping.**

```bash
set -euo pipefail
export EIR005_PLAN="$PWD/docs/superpowers/plans/2026-07-31-eir-005-machine-state-observer.md"
export EIR005_ROOT=/tmp/eir005-machine-state-observer-v1

mutation_files=(
  eir005_observer_plugin.py
  eir005_observer_plugin.py
  eir005_observer_plugin.py
  eir005_observer_plugin.py
  eir005_observer_verifier.py
  eir005_observer_verifier.py
  eir005_observer_controller.py
  eir005_observer_controller.py
)
owning_probes=(
  queued_wake healthy_loop multiple_loops sanitization
  paired_verifier paired_verifier ss_fail_closed frozen_root
)
required_red_patterns=(
  "RuntimeError: queued wake was not observed"
  "RuntimeError: healthy-loop snapshot is incomplete"
  "RuntimeError: observer collapsed multiple loops"
  "RuntimeError: observer leaked prohibited diagnostic content"
  "RuntimeError: paired verifier probe failed"
  "RuntimeError: paired verifier probe failed"
  "RuntimeError: unavailable ss was downgraded to an empty queue"
  "RuntimeError: official v3 root was accepted as observer output"
)
mutated_source_shas=(
  952aa1da2b0f1ff1f160a55deb95f59224fe9fde989657b9a4175f07ca42990f
  13a9113fdbc4517471e0427d7ccc5192573d84683479871a8a90393e1419d46a
  4245f3c01492b5c164d235e8d35cd3ac74404100e1aa39f696608ab8a6e09bee
  0c0352e7cf39865a557bcd17fe93db24bf9864e4b1d023727b5db750997f814b
  7d88e2c8ed39d239995d4b9959c01bfbf67803fc4efca9e82c1b84acbae7f503
  8135be7e0a11da29c0fac31da9ba220a932aea7448f9ba38b52629dfeb4acb93
  09f0f8ffc89725663a784965171229bdf40191a57c83d8f3c54ab64920dde298
  a732646ce37c3435bfab89984d5f1acbbac29b5bcbac848c94f8b36fe13882f7
)
portable_diff_shas=(
  53e5c6b4d39569ed507da6b07dea4d62f09ddc8fb619febb49d1d30f25262392
  78495ceffab4d5bc605401cead99437d98d80b1a4ebdb7948885f6c3e796340f
  28b5fc0641d389c4ef6024392683d220be467ec58a449fc946161f253de9a2ab
  8e8796ec43bc26cb7aeae74599a2b8f18ea623f17bab38b05458d42ec73112ee
  89b274df5b6a83eebba9e35a90adb82c048a8ed2c8912e8d61236990f51a6d1f
  fde48136951f5d27748192625b1d96c1116a2e66e66f9bed6d0549d3493da364
  1916368b29d32c86c0770b9fbfda1384efa349fb12ddd8d2b57dcf31e667ebab
  dbcdf279b02674b434e25e88256fb4247a29097c23969842831bf9d449bf152b
)

for mutation_id in $(seq 1 8); do
  index=$((mutation_id - 1))
  mutation_root="/tmp/eir005-machine-state-observer-v1-m${mutation_id}"
  mutation_file="${mutation_files[$index]}"
  owning_probe="${owning_probes[$index]}"
  test ! -e "$mutation_root"
  mkdir -p "$mutation_root/probes"
  cp \
    "$EIR005_ROOT/eir005_observer_controller.py" \
    "$EIR005_ROOT/eir005_observer_plugin.py" \
    "$EIR005_ROOT/eir005_observer_verifier.py" \
    "$EIR005_ROOT/observer-schedule.json" \
    "$EIR005_ROOT/price_truth_tier_runner.py" \
    "$EIR005_ROOT/arkscope_price_truth_tier_reporter.py" \
    "$EIR005_ROOT/A.paths" \
    "$EIR005_ROOT/A.nodes" \
    "$EIR005_ROOT/P.paths" \
    "$EIR005_ROOT/P.nodes" \
    "$mutation_root/"
  cp "$EIR005_ROOT/probes/"* "$mutation_root/probes/"

  awk \
    -v begin="<!-- EIR005_M${mutation_id}_DIFF_BEGIN -->" \
    -v end="<!-- EIR005_M${mutation_id}_DIFF_END -->" '
      $0 == begin { emit=1; next }
      $0 == end { emit=0 }
      emit && $0 == "<!-- EIR005_DIFF_CONTEXT_BLANK -->" {
        print " "
        next
      }
      emit && $0 != "```diff" && $0 != "```" { print }
    ' "$EIR005_PLAN" > "$mutation_root/mutation.diff"
  test "$(sha256sum "$mutation_root/mutation.diff" | cut -d " " -f 1)" = \
    "${portable_diff_shas[$index]}"
  patch --batch --forward -p1 -d "$mutation_root" \
    < "$mutation_root/mutation.diff"
  test "$(sha256sum "$mutation_root/$mutation_file" | cut -d " " -f 1)" = \
    "${mutated_source_shas[$index]}"

  PYTHONPATH="$mutation_root" \
    /home/hyl/.virtualenvs/llm_app/bin/python \
    "$mutation_root/eir005_observer_controller.py" \
    prepare-preflight \
    --artifact-root "$mutation_root" \
    --repo "$PWD" \
    > "$mutation_root/prepare.stdout" \
    2> "$mutation_root/prepare.stderr"

  set +e
  PYTHONPATH="$mutation_root" \
    /home/hyl/.virtualenvs/llm_app/bin/python \
    "$mutation_root/eir005_observer_controller.py" \
    probe-suite \
    --preflight "$mutation_root/observer-preflight.json" \
    --only "$owning_probe" \
    > "$mutation_root/mutation.stdout" \
    2> "$mutation_root/mutation.stderr"
  status=$?
  set -e
  test "$status" -ne 0
  rg -F "${required_red_patterns[$index]}" \
    "$mutation_root/mutation.stderr"

  test "$(sha256sum "$EIR005_ROOT/probe-summary.json" | cut -d " " -f 1)" = \
    5f95b3d9731d93d9bc979760343d59152b68c10d60812b8f8f66566b539b24bc
  test "$(sha256sum "$EIR005_ROOT/eir005_observer_controller.py" | cut -d " " -f 1)" = \
    9726f1b5ffa346992d2f44945d1224e402fdacc052554f452d4d72bc87205a41
  test "$(sha256sum "$EIR005_ROOT/eir005_observer_plugin.py" | cut -d " " -f 1)" = \
    ac5b343613ee6d83957f2507f1f11555f04a72856998e319ffaa1d0db1cea164
  test "$(sha256sum "$EIR005_ROOT/eir005_observer_verifier.py" | cut -d " " -f 1)" = \
    063544cfbf4b64a898b6088e1310a8690b17b4b616aeef7f77ffeef2aa8c7f77
  sha256sum --quiet -c \
    /tmp/price-truth-tier-v3/task0-v3-incomplete-manifest.sha256
done
```

Each nonzero exit must contain the table's owning RED reason. A setup,
preflight, import, SQLite, or capability failure is wrong-RED. The pristine
three-source hashes are rechecked against §2 after the loop. A mutation root
is never used for the campaign.

---

## 5. Finite Behavioral Campaign

### Task 3: Run paired C/O blocks

- [ ] **Step 1: Revalidate preflight and empty data immediately before launch.**

```bash
test -z "$(find data -mindepth 1 -print -quit)"
sha256sum -c /tmp/price-truth-tier-v3/task0-v3-incomplete-manifest.sha256
PYTHONPATH="$EIR005_ROOT" \
  /home/hyl/.virtualenvs/llm_app/bin/python \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  probe-suite \
  --preflight "$EIR005_ROOT/observer-preflight.json" \
  --only frozen_root
```

- [ ] **Step 2: Run the exact finite schedule.**

```bash
PYTHONPATH="$EIR005_ROOT" \
  /home/hyl/.virtualenvs/llm_app/bin/python \
  "$EIR005_ROOT/eir005_observer_controller.py" \
  run-campaign \
  --preflight "$EIR005_ROOT/observer-preflight.json"
```

The controller, not the operator:

- owns launch, PID/PGID/SID, progress and observer pipes;
- issues the fixed sample schedule;
- captures `/proc` and inode-filtered `ss`;
- recognizes the current-window dump after the last progress offset;
- sends SIGINT, waits exactly ten seconds, then sends SIGKILL if needed;
- drains descendants;
- archives only isolated `data/`;
- retries at most one invalid attempt per surface;
- stops a surface after two qualifying complete blocks; and
- refuses launch 19.

No operator may skip, reorder, repeat, or add an attempt.

- [ ] **Step 3: Check campaign closure without interpreting mechanism.**

```bash
jq -e '
  .protocol_id == "eir005-machine-state-observer-v1"
  and .launch_count <= 18
  and (.campaign_invalid_reason == null)
  and .official_price_admission_unchanged == true
' "$EIR005_ROOT/campaign-summary.json"
```

If a second invalid occurs, stop with its raw packet. It is not O5/O6 and does
not authorize more attempts.

### Task 4: Independently reconstruct O1-O6

- [ ] **Step 1: Run the separate verifier.**

```bash
PYTHONPATH="$EIR005_ROOT" \
  /home/hyl/.virtualenvs/llm_app/bin/python \
  "$EIR005_ROOT/eir005_observer_verifier.py" \
  verify \
  --preflight "$EIR005_ROOT/observer-preflight.json" \
  --campaign-summary "$EIR005_ROOT/campaign-summary.json" \
  --output "$EIR005_ROOT/verifier-result.json"
```

The verifier independently:

- reparses progress JSONL and target start/finish balance;
- recomputes dump-window and natural reporter admission;
- ignores controller verdict claims;
- selects A/P target loops from owner-thread and stack evidence;
- joins snapshot sequence to kernel/`ss` evidence;
- requires at least two stable late samples per O stall;
- keeps ready-only and byte-only vectors distinct;
- rejects one-arm blocks; and
- applies `O4`, `O2`, `O1`, `O3`, `O5`, `O6` precedence.

- [ ] **Step 2: Build a complete immutable manifest.**

```bash
find "$EIR005_ROOT" -type f \
  ! -name complete-manifest.sha256 \
  -print0 \
  | LC_ALL=C sort -z \
  | xargs -0 sha256sum \
  > "$EIR005_ROOT/complete-manifest.sha256"
sha256sum -c "$EIR005_ROOT/complete-manifest.sha256"
sha256sum "$EIR005_ROOT/complete-manifest.sha256"
```

- [ ] **Step 3: Write the tracked evidence packet.**

Create:
`docs/superpowers/evidence/2026-07-31-eir-005-machine-state-observer.md`.

It records source/schedule/probe/mutation identities, all attempt classes,
admitted replacements, C/O block outcomes, independently recomputed vectors,
the selected O result, official-v3 before/after identities, complete manifest
SHA, environment boundary, and explicit diagnostic-only wording. It links raw
paths and never substitutes prose for the manifest.

- [ ] **Step 4: Request independent raw reconstruction.**

The reviewer must re-run the verifier and reconstruct block/attempt totals
from raw records. Reading the evidence prose alone is insufficient.

`strace` remains absent. If and only if reviewed core evidence leaves one
syscall-order ambiguity that could change the result, a separate reviewed
amendment may authorize one launch-under-`strace -f` arm per surface. It is
never retroactively added to this campaign.

---

## 6. Closeout And Return To Product Work

### Task 5: Close observer ownership

- [ ] **Step 1: Update authorities after independent GREEN.**

Update the spec, this plan, evidence, priority map, and EIR-005. Record the
selected O1-O6 result without converting a test-runtime observation into a
desktop/product defect.

- [ ] **Step 2: Prove protected boundaries one final time.**

```bash
git diff --quiet 5ff3608a -- src tests apps extensions desktop \
  pyproject.toml requirements.txt requirements-dev.txt package.json \
  package-lock.json
sha256sum -c /tmp/price-truth-tier-v3/task0-v3-incomplete-manifest.sha256
test "$(git rev-parse codex/price-collection-truth)" = \
  "5ff3608a979519b7aee8b68dc9863ca852ac1ce1"
test -z "$(find data -mindepth 1 -print -quit)"
git diff --check
```

- [ ] **Step 3: Commit closeout docs and request focused pre-merge review.**

No product/test/runtime source is committed. The exact scratch source remains
embedded in this plan; `/tmp` artifacts remain untracked evidence.

- [ ] **Step 4: Perform the two fast-forwards from §1.2.**

Only after focused GREEN:

1. fast-forward `master` to the reviewed observer closeout tip;
2. fast-forward `codex/price-collection-truth` to the same tip;
3. verify both pointers and merged docs;
4. amend the price plan restart base in a new price-only commit; and
5. resume the already-reviewed v3 banking/product-RED sequence.

No dissatisfaction with O5/O6 authorizes another observer campaign. A normal
desktop exhibiting the same failure immediately escalates EIR-005 as a
product incident.

---

## 7. Stop Conditions

Stop without improvising if:

1. any Appendix A-E hash, line count, or byte count, or any Appendix F
   portable-diff hash differs;
2. the official v3 manifest or any copied v3 identity differs;
3. protected product/test/dependency paths differ from `5ff3608a...`;
4. C and O collected node identities differ;
5. either surface selection no longer includes its pinned target;
6. the observer needs to patch/wrap/call a target loop, selector, portal,
   event-loop policy, product, or test;
7. any snapshot contains callback arguments, locals, exception prose,
   credentials, raw `repr`, user data, or unsanitized absolute paths;
8. `ss` capability is unavailable after approved execution handoff;
9. an attempt writes to production data, the main worktree, or the official
   price-v3 root;
10. process identity, reporter, progress, transport, data, or cleanup is
    invalid twice on one surface;
11. the launch count would exceed eighteen;
12. a proposed result relies on one surface, one snapshot, controller prose,
    or strace alone;
13. absence of a wake byte is presented as proof no wake was attempted;
14. a reviewer requests a broader matrix or fourth runner without new
    evidence and explicit user approval;
15. either branch cannot follow the exact fast-forward mechanics in §1.2; or
16. the normal ArkScope desktop reproduces the failure.

Campaign budget exhaustion produces O5/O6. It is not permission to continue.

---

## Appendix A: Exact Controller

<!-- EIR005_CONTROLLER_BEGIN -->
```python
from __future__ import annotations

import argparse
import ast
import asyncio
import functools
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import price_truth_tier_runner as v3


PROTOCOL_ID = "eir005-machine-state-observer-v1"
OFFICIAL_V3_ROOT = Path("/tmp/price-truth-tier-v3")
OFFICIAL_MANIFEST = "task0-v3-incomplete-manifest.sha256"
OFFICIAL_HASHES = {
    "arkscope_price_truth_tier_reporter.py": (
        "09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928"
    ),
    "base-summary.json": (
        "a5686da09e1715e1ea81b618826c956b96649bf12075ccf230a387c87782b198"
    ),
    "base-T1.nodes": (
        "d74b9a2bf40a3b13a873be7337f4ad5da7e9e14865f795c0053820b083e2ee30"
    ),
    "base-T6.nodes": (
        "b6979e10b7d72b2b70b69e14ab8b8e4dd70b2e10484aa72e8c1d5ac92547500c"
    ),
    "price_truth_tier_runner.py": (
        "bb5d2245071aa48f8f0ad4e28a0966aa26744f213dcec65a69d947a383fd9de9"
    ),
    "T1.paths": (
        "d222b59322f5936607676b21163b06ecf3e6eb74df7e3df538b7b87245a86cc9"
    ),
    "T6.paths": (
        "9f04af18ffdb255646a2ac294b4e8beb825657d86fdafa253a12008d7ebf93ad"
    ),
    OFFICIAL_MANIFEST: (
        "ff189a4433b571c671ef7e4db82e63c94071d869e4ed48410f2a65c25e622f75"
    ),
}
SURFACES = {
    "A": {
        "nodes": "A.nodes",
        "nodes_sha256": OFFICIAL_HASHES["base-T1.nodes"],
        "paths": "A.paths",
        "paths_sha256": OFFICIAL_HASHES["T1.paths"],
        "target": (
            "tests/test_monitor.py::TestRunAgentQuery::test_successful_query"
        ),
    },
    "P": {
        "nodes": "P.nodes",
        "nodes_sha256": OFFICIAL_HASHES["base-T6.nodes"],
        "paths": "P.paths",
        "paths_sha256": OFFICIAL_HASHES["T6.paths"],
        "target": "tests/test_api.py::TestHealth::test_status",
    },
}
BOUNDS = {
    "deadline_seconds": 150,
    "dump_seconds": 120,
    "eof_leader_handshake_seconds": 1,
    "grace_seconds": 10,
    "process_group_drain_seconds": 1,
}
PROBE_BOUNDS = {
    "deadline_seconds": 3,
    "dump_seconds": 2,
    "eof_leader_handshake_seconds": 1,
    "grace_seconds": 1,
    "process_group_drain_seconds": 1,
}
SAMPLE_OFFSETS = {
    "early": 1.0,
    "pre_dump": 110.0,
    "post_dump": 121.0,
    "late": 136.0,
    "pre_deadline": 148.0,
}
OBSERVER_MODULE = "eir005_observer_plugin"
REPORTER_MODULE = "arkscope_price_truth_tier_reporter"
PROGRESS_MODULE = "price_truth_tier_runner"
PROGRESS_ENV = "PRICE_TRUTH_PROGRESS_FD"
REPORT_ENV = "PRICE_TRUTH_TIER_REPORT"
OBSERVER_OUTPUT_ENV = "EIR005_OBSERVER_OUTPUT_FD"
OBSERVER_COMMAND_ENV = "EIR005_OBSERVER_COMMAND_FD"
OBSERVER_TARGET_ENV = "EIR005_OBSERVER_TARGET"
OBSERVER_SURFACE_ENV = "EIR005_OBSERVER_SURFACE"
OBSERVER_TRIAL_ENV = "EIR005_OBSERVER_TRIAL"
OBSERVER_REPO_ENV = "EIR005_OBSERVER_REPO"
OBSERVER_ROOT_ENV = "EIR005_OBSERVER_ARTIFACT_ROOT"
SS_COMMAND = ["ss", "-x", "-a", "-n", "-m", "-e", "-p", "-H"]
TARGET_RE = re.compile(r"ino[:=](\d+)")
SS_ROW_RE = re.compile(r"^(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s+")
STATUS_KEYS = {
    "FDSize",
    "NSpgid",
    "NSsid",
    "Pid",
    "PPid",
    "ShdPnd",
    "SigBlk",
    "SigIgn",
    "SigPnd",
    "State",
    "Threads",
    "voluntary_ctxt_switches",
    "nonvoluntary_ctxt_switches",
}
PROTECTED_DIFF_PATHS = [
    "src",
    "tests",
    "apps",
    "extensions",
    "desktop",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "package.json",
    "package-lock.json",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"expected JSONL objects: {path}")
        values.append(value)
    return values


def _timeline(event: str, **fields: Any) -> dict[str, Any]:
    return {
        "event": event,
        "monotonic_ns": time.monotonic_ns(),
        "wall_time_epoch": time.time(),
        **fields,
    }


def _read_lines(path: Path) -> list[str]:
    values = path.read_text(encoding="utf-8").splitlines()
    if values != sorted(set(values)) or not values:
        raise RuntimeError(f"manifest must be sorted, unique, and nonempty: {path}")
    return values


def _assert_artifact_root_safe(root: Path) -> None:
    resolved = root.resolve()
    if resolved == OFFICIAL_V3_ROOT or OFFICIAL_V3_ROOT in resolved.parents:
        raise RuntimeError("observer artifacts may not use the official v3 root")
    for frozen in (Path("/tmp/price-truth-tier-v1"), Path("/tmp/price-truth-tier-v2")):
        if resolved == frozen or frozen in resolved.parents:
            raise RuntimeError("observer artifacts may not use a frozen runner root")


def _verify_manifest_contents(manifest: Path) -> int:
    if _sha256(manifest) != OFFICIAL_HASHES[OFFICIAL_MANIFEST]:
        raise RuntimeError("official v3 manifest identity changed")
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, raw_path = line.partition("  ")
        path = Path(raw_path)
        if (
            not separator
            or len(digest) != 64
            or path.parent.resolve() != OFFICIAL_V3_ROOT
            and OFFICIAL_V3_ROOT not in path.resolve().parents
            or not path.is_file()
            or _sha256(path) != digest
        ):
            raise RuntimeError(f"official v3 manifest entry changed: {raw_path}")
        checked += 1
    if checked != 3262:
        raise RuntimeError("official v3 manifest entry count changed")
    return checked


def _verify_official_key_identities() -> None:
    for relative, expected in OFFICIAL_HASHES.items():
        path = OFFICIAL_V3_ROOT / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"official v3 identity changed: {relative}")


def _verify_copied_v3(root: Path) -> None:
    copied = {
        "price_truth_tier_runner.py": OFFICIAL_HASHES[
            "price_truth_tier_runner.py"
        ],
        "arkscope_price_truth_tier_reporter.py": OFFICIAL_HASHES[
            "arkscope_price_truth_tier_reporter.py"
        ],
        "A.paths": SURFACES["A"]["paths_sha256"],
        "A.nodes": SURFACES["A"]["nodes_sha256"],
        "P.paths": SURFACES["P"]["paths_sha256"],
        "P.nodes": SURFACES["P"]["nodes_sha256"],
    }
    for relative, expected in copied.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"copied v3 artifact changed: {relative}")


def _git_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _assert_protected_paths(repo: Path) -> None:
    subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            "5ff3608a979519b7aee8b68dc9863ca852ac1ce1",
            "--",
            *PROTECTED_DIFF_PATHS,
        ],
        cwd=repo,
        check=True,
    )


def _safe_environment_names(arm: str) -> set[str]:
    names = {
        "ARKSCOPE_CONSENSUS_DB",
        "ARKSCOPE_DISABLE_SCHEDULER",
        "ARKSCOPE_LOCK_DIR",
        "ARKSCOPE_MACRO_CALENDAR_DB",
        "ARKSCOPE_MARKET_DB",
        "ARKSCOPE_PROFILE_DB",
        "ARKSCOPE_SA_DB",
        "EDGAR_LOCAL_DATA_DIR",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONHASHSEED",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        REPORT_ENV,
        PROGRESS_ENV,
        "TMPDIR",
        "TZ",
        "XDG_CACHE_HOME",
    }
    if arm == "O":
        names.update(
            {
                OBSERVER_COMMAND_ENV,
                OBSERVER_OUTPUT_ENV,
                OBSERVER_REPO_ENV,
                OBSERVER_ROOT_ENV,
                OBSERVER_SURFACE_ENV,
                OBSERVER_TARGET_ENV,
                OBSERVER_TRIAL_ENV,
            }
        )
    return names


def _child_environment(
    *,
    arm: str,
    observer_command_fd: int | None,
    observer_output_fd: int | None,
    preflight: dict[str, Any],
    progress_fd: int,
    report_path: Path,
    surface: str,
    target_nodeid: str,
    trial: Path,
) -> dict[str, str]:
    root = Path(preflight["artifact_root"])
    home = trial / "home"
    tmp = trial / "tmp"
    locks = trial / "locks"
    edgar = trial / "edgar"
    for directory in (home, tmp, locks, edgar):
        directory.mkdir(parents=True, exist_ok=False)
    env = {
        "PATH": preflight["path"],
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "Asia/Taipei",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "XDG_CACHE_HOME": str(trial / "xdg-cache"),
        "PYTHONHASHSEED": "0",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(root),
        "ARKSCOPE_DISABLE_SCHEDULER": "1",
        "ARKSCOPE_LOCK_DIR": str(locks),
        "ARKSCOPE_PROFILE_DB": str(trial / "profile_state.db"),
        "ARKSCOPE_MARKET_DB": str(trial / "market_data.db"),
        "ARKSCOPE_MACRO_CALENDAR_DB": str(trial / "macro_calendar.db"),
        "ARKSCOPE_SA_DB": str(trial / "sa_capture.db"),
        "ARKSCOPE_CONSENSUS_DB": str(trial / "consensus.db"),
        "EDGAR_LOCAL_DATA_DIR": str(edgar),
        REPORT_ENV: str(report_path),
        PROGRESS_ENV: str(progress_fd),
    }
    if arm == "O":
        if observer_command_fd is None or observer_output_fd is None:
            raise RuntimeError("observed arm descriptors are missing")
        env.update(
            {
                OBSERVER_COMMAND_ENV: str(observer_command_fd),
                OBSERVER_OUTPUT_ENV: str(observer_output_fd),
                OBSERVER_REPO_ENV: preflight["repo"],
                OBSERVER_ROOT_ENV: preflight["artifact_root"],
                OBSERVER_SURFACE_ENV: surface,
                OBSERVER_TARGET_ENV: target_nodeid,
                OBSERVER_TRIAL_ENV: trial.name,
            }
        )
    if set(env) != _safe_environment_names(arm):
        raise RuntimeError("child environment names changed")
    return env


def _parse_status(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for line in lines:
        key, separator, value = line.partition(":")
        if separator and key in STATUS_KEYS:
            result[key] = value.strip()
    return result


def _fd_inventory(pid: int) -> tuple[list[dict[str, Any]], set[int]]:
    records: list[dict[str, Any]] = []
    socket_inodes: set[int] = set()
    root = Path(f"/proc/{pid}/fd")
    try:
        entries = sorted(root.iterdir(), key=lambda item: int(item.name))
    except OSError:
        return records, socket_inodes
    for entry in entries:
        try:
            target = os.readlink(entry)
            fd = int(entry.name)
        except (OSError, ValueError):
            continue
        socket_match = re.fullmatch(r"socket:\[(\d+)\]", target)
        if socket_match:
            inode = int(socket_match.group(1))
            socket_inodes.add(inode)
            records.append({"fd": fd, "inode": inode, "kind": "socket"})
        elif target == "anon_inode:[eventpoll]":
            records.append({"fd": fd, "inode": None, "kind": "eventpoll"})
    return records, socket_inodes


def _fdinfo(pid: int, fds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in fds:
        path = Path(f"/proc/{pid}/fdinfo/{item['fd']}")
        values: dict[str, Any] = {}
        registrations: list[dict[str, int]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            key, separator, raw = line.partition(":")
            if not separator:
                continue
            value = raw.strip()
            if key in {"flags", "ino", "mnt_id", "pos", "scm_fds"}:
                values[key] = value
            elif key == "tfd":
                match = re.match(
                    r"^\s*(\d+)\s+events:\s*([0-9a-fA-F]+)",
                    value,
                )
                try:
                    if match is None:
                        raise ValueError
                    registrations.append(
                        {
                            "events": int(match.group(2), 16),
                            "fd": int(match.group(1)),
                        }
                    )
                except ValueError:
                    continue
        records.append(
            {
                "fd": item["fd"],
                "kind": item["kind"],
                "registrations": sorted(
                    registrations,
                    key=lambda value: (value["fd"], value["events"]),
                ),
                "values": values,
            }
        )
    return records


def _ss_rows(socket_inodes: set[int]) -> list[dict[str, Any]]:
    result = subprocess.run(
        SS_COMMAND,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("ss_queue_capability_unavailable")
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        inode_match = TARGET_RE.search(line)
        row_match = SS_ROW_RE.match(line)
        fields = line.split()
        local_inode: int | None = None
        if inode_match is not None:
            local_inode = int(inode_match.group(1))
        elif len(fields) >= 6 and fields[5].isdecimal():
            local_inode = int(fields[5])
        if local_inode is None or row_match is None:
            continue
        if local_inode not in socket_inodes:
            continue
        rows.append(
            {
                "inode": local_inode,
                "netid": row_match.group(1),
                "receive_queue": int(row_match.group(3)),
                "send_queue": int(row_match.group(4)),
                "state": row_match.group(2),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            item["inode"],
            item["receive_queue"],
            item["send_queue"],
        ),
    )


def _unix_rows(pid: int, socket_inodes: set[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = Path(f"/proc/{pid}/net/unix").read_text(
            encoding="utf-8"
        ).splitlines()[1:]
    except OSError:
        return rows
    for line in lines:
        fields = line.split()
        if len(fields) < 7:
            continue
        try:
            inode = int(fields[6])
        except ValueError:
            continue
        if inode in socket_inodes:
            rows.append(
                {
                    "flags": fields[3],
                    "inode": inode,
                    "state": fields[5],
                    "type": fields[4],
                }
            )
    return sorted(rows, key=lambda item: item["inode"])


def _read_text_value(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _task_records(pid: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        tasks = sorted(
            Path(f"/proc/{pid}/task").iterdir(),
            key=lambda item: int(item.name),
        )
    except OSError:
        return records
    for task in tasks:
        try:
            tid = int(task.name)
        except ValueError:
            continue
        syscall = _read_text_value(task / "syscall")
        stat_value = _read_text_value(task / "stat")
        stat_record: dict[str, Any] = {}
        if stat_value is not None and ")" in stat_value:
            fields = stat_value.rsplit(")", 1)[1].strip().split()
            if len(fields) >= 20:
                stat_record = {
                    "ppid": fields[1],
                    "starttime_ticks": fields[19],
                    "state": fields[0],
                    "stime_ticks": fields[12],
                    "utime_ticks": fields[11],
                }
        records.append(
            {
                "stat": stat_record,
                "status": _parse_status(task / "status"),
                "syscall_number": (
                    syscall.split()[0] if syscall and syscall.split() else None
                ),
                "tid": tid,
                "wchan": _read_text_value(task / "wchan"),
            }
        )
    return records


def _process_limits(pid: int) -> dict[str, dict[str, str]]:
    value = _read_text_value(Path(f"/proc/{pid}/limits"))
    if value is None:
        return {}
    result: dict[str, dict[str, str]] = {}
    for line in value.splitlines()[1:]:
        match = re.match(
            r"^(Max open files|Max processes)\s+(\S+)\s+(\S+)\s+(\S+)$",
            line.strip(),
        )
        if match is not None:
            result[match.group(1)] = {
                "hard": match.group(3),
                "soft": match.group(2),
                "units": match.group(4),
            }
    return result


def _pressure(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    value = _read_text_value(path)
    if value is None:
        return result
    for line in value.splitlines():
        fields = line.split()
        if not fields:
            continue
        result[fields[0]] = dict(
            item.split("=", 1)
            for item in fields[1:]
            if "=" in item
        )
    return result


def _capture_kernel(
    *,
    pid: int,
    sample_sequence: int,
    surface: str,
    trigger: str,
    trial: str,
) -> dict[str, Any]:
    fds, socket_inodes = _fd_inventory(pid)
    return {
        "event": "kernel_snapshot",
        "fd_count": len(list(Path(f"/proc/{pid}/fd").iterdir())),
        "fdinfo": _fdinfo(pid, fds),
        "file_nr": _read_text_value(Path("/proc/sys/fs/file-nr")),
        "loadavg": _read_text_value(Path("/proc/loadavg")),
        "monotonic_ns": time.monotonic_ns(),
        "pressure": {
            name: _pressure(Path(f"/proc/pressure/{name}"))
            for name in ("cpu", "io", "memory")
        },
        "process_limits": _process_limits(pid),
        "process_status": _parse_status(Path(f"/proc/{pid}/status")),
        "sample_sequence": sample_sequence,
        "schema_version": 1,
        "socket_fds": fds,
        "ss_rows": _ss_rows(socket_inodes),
        "surface": surface,
        "tasks": _task_records(pid),
        "trial": trial,
        "trigger": trigger,
        "unix_rows": _unix_rows(pid, socket_inodes),
        "wall_time_epoch": time.time(),
    }


def _append_json_line(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
        )
        handle.flush()


def _probe_ss_capability() -> dict[str, Any]:
    left, right = socket.socketpair()
    try:
        right.sendall(b"abc")
        inode = os.fstat(left.fileno()).st_ino
        rows = _ss_rows({inode})
        matching = [row for row in rows if row["inode"] == inode]
        if not matching or max(row["receive_queue"] for row in matching) < 3:
            raise RuntimeError("ss did not expose the controlled receive queue")
        return {"inode_joined": True, "queued_bytes": 3}
    finally:
        left.close()
        right.close()


def _pip_freeze_sha256() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = sorted(result.stdout.decode("utf-8").splitlines())
    return _sha256_bytes(("".join(f"{line}\n" for line in lines)).encode())


def _artifact_record(path: Path, role: str) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"observer artifact is missing: {path}")
    return {
        "path": str(path.resolve()),
        "role": role,
        "sha256": _sha256(path),
    }


def _schedule_rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 16:
        raise RuntimeError("observer schedule must contain sixteen rows")
    required = {"arm", "block", "slot", "surface"}
    seen: set[tuple[str, int, str]] = set()
    for index, row in enumerate(value, start=1):
        if (
            not isinstance(row, dict)
            or set(row) != required
            or row["surface"] not in {"A", "P"}
            or row["arm"] not in {"C", "O"}
            or row["block"] not in {1, 2, 3, 4}
            or row["slot"] not in {1, 2}
        ):
            raise RuntimeError("observer schedule row is invalid")
        identity = (row["surface"], row["block"], row["arm"])
        if identity in seen:
            raise RuntimeError("observer schedule contains a duplicate arm")
        seen.add(identity)
        expected_slot = (
            1
            if (
                (row["surface"] == "A" and row["block"] % 2 == 1)
                or (row["surface"] == "P" and row["block"] % 2 == 0)
            )
            == (row["arm"] == "C")
            else 2
        )
        if row["slot"] != expected_slot:
            raise RuntimeError(f"observer schedule order differs at row {index}")
    for surface in ("A", "P"):
        for block in range(1, 5):
            block_rows = [
                row
                for row in value
                if row["surface"] == surface and row["block"] == block
            ]
            if (
                len(block_rows) != 2
                or {row["arm"] for row in block_rows} != {"C", "O"}
            ):
                raise RuntimeError("observer schedule block is incomplete")
    return value


def prepare_preflight(*, artifact_root: Path, repo: Path) -> Path:
    root = artifact_root.resolve()
    repo = repo.resolve()
    _assert_artifact_root_safe(root)
    if Path(__file__).resolve() != root / "eir005_observer_controller.py":
        raise RuntimeError("prepare must run the copied observer controller")
    if Path(v3.__file__).resolve() != root / "price_truth_tier_runner.py":
        raise RuntimeError("controller must import the copied v3 runner")
    if not (repo / ".git").exists():
        raise RuntimeError("observer repo must be an isolated Git worktree")
    output = root / "observer-preflight.json"
    if output.exists() or output.with_suffix(".json.tmp").exists():
        raise RuntimeError("observer preflight output already exists")
    _assert_protected_paths(repo)
    _verify_official_key_identities()
    official_manifest_entries = _verify_manifest_contents(
        OFFICIAL_V3_ROOT / OFFICIAL_MANIFEST
    )
    _verify_copied_v3(root)
    schedule = _schedule_rows(root / "observer-schedule.json")
    if _read_lines(root / "A.nodes") != _read_lines(
        OFFICIAL_V3_ROOT / "base-T1.nodes"
    ):
        raise RuntimeError("A node manifest differs from official v3")
    if _read_lines(root / "P.nodes") != _read_lines(
        OFFICIAL_V3_ROOT / "base-T6.nodes"
    ):
        raise RuntimeError("P node manifest differs from official v3")
    ss_probe = _probe_ss_capability()
    roles = [
        ("controller", "eir005_observer_controller.py"),
        ("plugin", "eir005_observer_plugin.py"),
        ("verifier", "eir005_observer_verifier.py"),
        ("v3_runner", "price_truth_tier_runner.py"),
        ("v3_reporter", "arkscope_price_truth_tier_reporter.py"),
        ("schedule", "observer-schedule.json"),
        ("A_paths", "A.paths"),
        ("A_nodes", "A.nodes"),
        ("P_paths", "P.paths"),
        ("P_nodes", "P.nodes"),
        ("probe_pass", "probes/probe_pass.py"),
        ("probe_interruptible", "probes/probe_interruptible.py"),
        ("probe_ignore_sigint", "probes/probe_ignore_sigint.py"),
        ("probe_nodes", "probes/probe.nodes"),
    ]
    artifacts = [
        _artifact_record(root / relative, role)
        for role, relative in roles
    ]
    import pytest

    payload = {
        "artifact_root": str(root),
        "artifacts": artifacts,
        "bounds": BOUNDS,
        "git_identity": _git_head(repo),
        "official_manifest_entries": official_manifest_entries,
        "official_v3_hashes": OFFICIAL_HASHES,
        "path": os.environ.get("PATH", ""),
        "pip_freeze_sha256": _pip_freeze_sha256(),
        "protocol_id": PROTOCOL_ID,
        "python": sys.executable,
        "python_version": sys.version,
        "pytest_version": pytest.__version__,
        "repo": str(repo),
        "schedule": schedule,
        "schema_version": 1,
        "ss_probe": ss_probe,
        "surfaces": SURFACES,
    }
    _atomic_json(output, payload)
    return output


def _artifact(preflight: dict[str, Any], role: str) -> Path:
    matches = [
        Path(item["path"])
        for item in preflight["artifacts"]
        if item["role"] == role
    ]
    if len(matches) != 1:
        raise RuntimeError(f"observer artifact role must be unique: {role}")
    return matches[0]


def _verify_preflight(path: Path, *, full_official: bool = False) -> dict[str, Any]:
    preflight = _load_json(path)
    required = {
        "artifact_root",
        "artifacts",
        "bounds",
        "git_identity",
        "official_manifest_entries",
        "official_v3_hashes",
        "path",
        "pip_freeze_sha256",
        "protocol_id",
        "python",
        "python_version",
        "pytest_version",
        "repo",
        "schedule",
        "schema_version",
        "ss_probe",
        "surfaces",
    }
    if set(preflight) != required:
        raise RuntimeError("observer preflight keys do not match closed schema")
    if (
        preflight["schema_version"] != 1
        or preflight["protocol_id"] != PROTOCOL_ID
        or preflight["bounds"] != BOUNDS
        or preflight["surfaces"] != SURFACES
        or preflight["official_v3_hashes"] != OFFICIAL_HASHES
    ):
        raise RuntimeError("observer preflight constants changed")
    root = Path(preflight["artifact_root"]).resolve()
    _assert_artifact_root_safe(root)
    if path.resolve() != root / "observer-preflight.json":
        raise RuntimeError("observer preflight moved")
    if Path(__file__).resolve() != _artifact(preflight, "controller").resolve():
        raise RuntimeError("run the controller recorded in preflight")
    if Path(v3.__file__).resolve() != _artifact(preflight, "v3_runner").resolve():
        raise RuntimeError("controller imported a different v3 runner")
    seen_roles: set[str] = set()
    for item in preflight["artifacts"]:
        if set(item) != {"path", "role", "sha256"}:
            raise RuntimeError("observer artifact entry schema changed")
        role = item["role"]
        artifact = Path(item["path"])
        if (
            not isinstance(role, str)
            or not role
            or role in seen_roles
            or not artifact.is_file()
            or _sha256(artifact) != item["sha256"]
        ):
            raise RuntimeError(f"observer artifact changed: {artifact}")
        seen_roles.add(role)
    if (
        preflight["python"] != sys.executable
        or preflight["python_version"] != sys.version
        or preflight["path"] != os.environ.get("PATH", "")
        or preflight["pip_freeze_sha256"] != _pip_freeze_sha256()
    ):
        raise RuntimeError("observer interpreter or environment changed")
    import pytest

    if preflight["pytest_version"] != pytest.__version__:
        raise RuntimeError("observer pytest version changed")
    repo = Path(preflight["repo"])
    if _git_head(repo) != preflight["git_identity"]:
        raise RuntimeError("observer Git identity changed")
    _assert_protected_paths(repo)
    _verify_official_key_identities()
    if full_official:
        checked = _verify_manifest_contents(
            OFFICIAL_V3_ROOT / OFFICIAL_MANIFEST
        )
        if checked != preflight["official_manifest_entries"]:
            raise RuntimeError("official manifest entry count changed")
    _verify_copied_v3(root)
    if _schedule_rows(_artifact(preflight, "schedule")) != preflight["schedule"]:
        raise RuntimeError("observer schedule changed")
    for surface in ("A", "P"):
        if (
            _sha256(_artifact(preflight, f"{surface}_paths"))
            != SURFACES[surface]["paths_sha256"]
            or _sha256(_artifact(preflight, f"{surface}_nodes"))
            != SURFACES[surface]["nodes_sha256"]
        ):
            raise RuntimeError(f"observer surface identity changed: {surface}")
    return preflight


def _send_observer_command(
    *,
    command_fd: int | None,
    command_path: Path,
    sequence: int,
    trigger: str,
) -> bool:
    if command_fd is None:
        return False
    payload = {
        "schema_version": 1,
        "sequence": sequence,
        "trigger": trigger,
    }
    encoded = (
        json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        if os.write(command_fd, encoded) != len(encoded):
            raise RuntimeError("short observer command write")
    except BrokenPipeError:
        return False
    _append_json_line(
        command_path,
        {
            **payload,
            "controller_monotonic_ns": time.monotonic_ns(),
            "controller_wall_time_epoch": time.time(),
        },
    )
    return True


def _observer_payload_safe(payload: Any) -> bool:
    forbidden_keys = {
        "arguments",
        "exception",
        "locals",
        "raw_repr",
        "repr",
    }
    if isinstance(payload, dict):
        return not (set(payload) & forbidden_keys) and all(
            _observer_payload_safe(value)
            for value in payload.values()
        )
    if isinstance(payload, list):
        return all(_observer_payload_safe(value) for value in payload)
    if isinstance(payload, str):
        return not payload.startswith(("/home/", "/mnt/", "/tmp/"))
    return True


def _parse_observer_event(
    raw: bytes,
    *,
    received_monotonic_ns: int,
) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("malformed observer event") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("event")
        not in {"observer_ready", "snapshot", "snapshot_error"}
        or not _observer_payload_safe(payload)
    ):
        raise RuntimeError("observer event violates its closed safe schema")
    return {
        "controller_received_monotonic_ns": received_monotonic_ns,
        "controller_received_wall_time_epoch": time.time(),
        "payload": payload,
    }


def _sample(
    *,
    arm: str,
    command_fd: int | None,
    command_path: Path,
    kernel_path: Path,
    pid: int,
    sample_sequence: int,
    surface: str,
    trigger: str,
    trial: str,
) -> bool:
    command_sent = False
    if arm == "O":
        command_sent = _send_observer_command(
            command_fd=command_fd,
            command_path=command_path,
            sequence=sample_sequence,
            trigger=trigger,
        )
    kernel = _capture_kernel(
        pid=pid,
        sample_sequence=sample_sequence,
        surface=surface,
        trigger=trigger,
        trial=trial,
    )
    kernel["observer_command_sent"] = command_sent
    _append_json_line(kernel_path, kernel)
    return command_sent


def _terminate_with_snapshots(
    *,
    arm: str,
    command_fd: int | None,
    command_path: Path,
    identity: dict[str, int],
    kernel_path: Path,
    process: subprocess.Popen[bytes],
    sample_sequence: int,
    surface: str,
    timeline: list[dict[str, Any]],
    trial: str,
    bounds: dict[str, int],
) -> tuple[int | None, bool, bool, bool, int]:
    if not v3._identity_is_owned(identity):
        raise RuntimeError("refusing to signal an unowned process group")
    sample_sequence += 1
    _sample(
        arm=arm,
        command_fd=command_fd,
        command_path=command_path,
        kernel_path=kernel_path,
        pid=identity["pid"],
        sample_sequence=sample_sequence,
        surface=surface,
        trigger="pre_sigint",
        trial=trial,
    )
    os.killpg(identity["pgid"], signal.SIGINT)
    timeline.append(_timeline("sigint_sent", pgid=identity["pgid"]))
    interrupted = True
    killed = False
    post_offsets = [0.0, 0.25, 1.0, 5.0]
    sampled: set[float] = set()
    started = time.monotonic()
    deadline = started + bounds["grace_seconds"]
    while time.monotonic() < deadline:
        elapsed = time.monotonic() - started
        for offset in post_offsets:
            if offset <= elapsed and offset not in sampled and process.poll() is None:
                sample_sequence += 1
                try:
                    _sample(
                        arm=arm,
                        command_fd=command_fd,
                        command_path=command_path,
                        kernel_path=kernel_path,
                        pid=identity["pid"],
                        sample_sequence=sample_sequence,
                        surface=surface,
                        trigger="post_sigint",
                        trial=trial,
                    )
                except (FileNotFoundError, ProcessLookupError):
                    pass
                sampled.add(offset)
        if process.poll() is not None and not v3._process_group_exists(
            identity["pgid"]
        ):
            timeline.append(_timeline("sigint_exit_observed"))
            return process.returncode, interrupted, killed, True, sample_sequence
        time.sleep(0.05)
    if v3._process_group_exists(identity["pgid"]):
        os.killpg(identity["pgid"], signal.SIGKILL)
        killed = True
        timeline.append(_timeline("sigkill_sent", pgid=identity["pgid"]))
    try:
        returncode = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        returncode = process.poll()
    group_gone, elapsed = v3._wait_for_natural_group_drain(
        identity["pgid"],
        bounds["process_group_drain_seconds"],
    )
    timeline.append(
        _timeline(
            "post_signal_group_drain",
            elapsed_seconds=elapsed,
            group_gone=group_gone,
        )
    )
    return returncode, interrupted, killed, group_gone, sample_sequence


def _attempt_command(
    *,
    arm: str,
    bounds: dict[str, int],
    preflight: dict[str, Any],
    selectors_: list[str],
    trial: Path,
) -> list[str]:
    args = [
        preflight["python"],
        "-m",
        "pytest",
        "-vv",
        "--tb=short",
        "-o",
        f"faulthandler_timeout={bounds['dump_seconds']}",
        "-o",
        f"cache_dir={trial / 'pytest-cache'}",
        "--basetemp",
        str(trial / "pytest-tmp"),
        "-p",
        REPORTER_MODULE,
        "-p",
        PROGRESS_MODULE,
    ]
    if arm == "O":
        args.extend(["-p", OBSERVER_MODULE])
    return [*args, *selectors_]


def _read_observer_chunks(
    *,
    buffer: bytes,
    fd: int,
    output_path: Path,
) -> tuple[bytes, bool, int]:
    eof = False
    count = 0
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            break
        if not chunk:
            eof = True
            break
        buffer += chunk
        while b"\n" in buffer:
            raw, buffer = buffer.split(b"\n", 1)
            envelope = _parse_observer_event(
                raw,
                received_monotonic_ns=time.monotonic_ns(),
            )
            _append_json_line(output_path, envelope)
            count += 1
    return buffer, eof, count


def _run_attempt(
    *,
    arm: str,
    attempt: int,
    bounds: dict[str, int],
    expected_nodes_path: Path,
    label: str,
    preflight_path: Path,
    selectors_: list[str],
    surface: str,
    target_nodeid: str,
    working_directory: Path | None = None,
) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path)
    root = Path(preflight["artifact_root"])
    repo = Path(preflight["repo"])
    cwd = working_directory or repo
    trial = root / label
    if trial.exists():
        raise RuntimeError(f"attempt already exists: {trial}")
    data_before = v3._worktree_data_entries(repo)
    if data_before:
        raise RuntimeError(f"worktree data is not empty: {data_before}")
    trial.mkdir(parents=True)
    transcript_path = trial / "transcript.txt"
    progress_path = trial / "progress.jsonl"
    report_path = trial / "report.json"
    observer_path = trial / "observer.jsonl"
    command_path = trial / "observer-commands.jsonl"
    kernel_path = trial / "kernel.jsonl"
    progress_read, progress_write = os.pipe()
    os.set_blocking(progress_read, False)
    observer_read: int | None = None
    observer_write: int | None = None
    command_read: int | None = None
    command_write: int | None = None
    if arm == "O":
        observer_read, observer_write = os.pipe()
        command_read, command_write = os.pipe()
        os.set_blocking(observer_read, False)
    env = _child_environment(
        arm=arm,
        observer_command_fd=command_read,
        observer_output_fd=observer_write,
        preflight=preflight,
        progress_fd=progress_write,
        report_path=report_path,
        surface=surface,
        target_nodeid=target_nodeid,
        trial=trial,
    )
    args = _attempt_command(
        arm=arm,
        bounds=bounds,
        preflight=preflight,
        selectors_=selectors_,
        trial=trial,
    )
    pass_fds = [progress_write]
    if arm == "O":
        assert command_read is not None and observer_write is not None
        pass_fds.extend([command_read, observer_write])
    started_wall = time.time()
    started_ns = time.monotonic_ns()
    deadline_ns = started_ns + bounds["deadline_seconds"] * 1_000_000_000
    transport_deadline_ns: int | None = None
    expected_progress = 2 * len(_read_lines(expected_nodes_path))
    expected_sequence = 1
    active_nodeid: str | None = None
    progress_count = 0
    progress_buffer = b""
    observer_buffer = b""
    observer_count = 0
    observer_eof = False
    observer_ready = False
    progress_eof = False
    pipe_offset = 0
    last_progress: dict[str, Any] | None = None
    phase = "pre_first_node"
    target_reached = False
    target_finished = False
    target_started_ns: int | None = None
    pending_samples: dict[str, int] = {}
    sample_sequence = 0
    requested_samples: list[dict[str, Any]] = []
    timeline = [_timeline("launch_requested", label=label)]
    process: subprocess.Popen[bytes] | None = None
    identity: dict[str, int] | None = None
    returncode: int | None = None
    interrupted = False
    killed = False
    cleanup_complete = False
    dump_present = False
    invalid_reason: str | None = None
    classification = "invalid"
    natural_outcome: str | None = None
    nonpassing: list[str] = []
    selector = selectors.DefaultSelector()

    def request_sample(trigger: str) -> None:
        nonlocal sample_sequence
        if process is None or process.poll() is not None:
            requested_samples.append(
                {
                    "command_sent": False,
                    "reason": "process_not_running",
                    "trigger": trigger,
                }
            )
            return
        sample_sequence += 1
        sent = _sample(
            arm=arm,
            command_fd=command_write,
            command_path=command_path,
            kernel_path=kernel_path,
            pid=process.pid,
            sample_sequence=sample_sequence,
            surface=surface,
            trigger=trigger,
            trial=label,
        )
        requested_samples.append(
            {
                "command_sent": sent,
                "sample_sequence": sample_sequence,
                "trigger": trigger,
            }
        )
        timeline.append(
            _timeline(
                "sample_requested",
                command_sent=sent,
                sample_sequence=sample_sequence,
                trigger=trigger,
            )
        )

    try:
        with transcript_path.open("wb") as transcript_handle, progress_path.open(
            "w", encoding="utf-8"
        ) as progress_handle:
            process = subprocess.Popen(
                args,
                cwd=cwd,
                env=env,
                stdout=transcript_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=tuple(pass_fds),
            )
            os.close(progress_write)
            progress_write = -1
            if arm == "O":
                assert observer_write is not None and command_read is not None
                os.close(observer_write)
                observer_write = None
                os.close(command_read)
                command_read = None
            identity = v3._process_identity(process)
            timeline.append(_timeline("launched", identity=identity))
            if not v3._identity_is_owned(identity):
                invalid_reason = "process_group_identity_mismatch"
                returncode = process.poll()
            else:
                selector.register(progress_read, selectors.EVENT_READ, "progress")
                if arm == "O":
                    assert observer_read is not None
                    selector.register(
                        observer_read,
                        selectors.EVENT_READ,
                        "observer",
                    )
                while invalid_reason is None and returncode is None:
                    now_ns = time.monotonic_ns()
                    if target_started_ns is not None and not target_finished:
                        for trigger, due_ns in list(pending_samples.items()):
                            if now_ns >= due_ns:
                                request_sample(trigger)
                                del pending_samples[trigger]
                    active_deadline = (
                        transport_deadline_ns
                        if transport_deadline_ns is not None
                        else deadline_ns
                    )
                    sample_deadline = min(
                        pending_samples.values(),
                        default=active_deadline,
                    )
                    wait_ns = max(0, min(active_deadline, sample_deadline) - now_ns)
                    events = selector.select(
                        timeout=min(wait_ns / 1_000_000_000, 0.1)
                    )
                    no_progress_due = (
                        transport_deadline_ns is None
                        and time.monotonic_ns() >= deadline_ns
                    )
                    for key, _ in events:
                        if key.data == "observer":
                            (
                                observer_buffer,
                                observer_pipe_eof,
                                added,
                            ) = _read_observer_chunks(
                                buffer=observer_buffer,
                                fd=key.fd,
                                output_path=observer_path,
                            )
                            observer_count += added
                            if observer_path.is_file():
                                for line in observer_path.read_text(
                                    encoding="utf-8"
                                ).splitlines()[-added:]:
                                    envelope = json.loads(line)
                                    if (
                                        envelope["payload"]["event"]
                                        == "observer_ready"
                                    ):
                                        observer_ready = True
                            if observer_pipe_eof:
                                observer_eof = True
                                selector.unregister(key.fd)
                            continue
                        while True:
                            try:
                                chunk = os.read(key.fd, 65536)
                            except BlockingIOError:
                                break
                            if not chunk:
                                progress_eof = True
                                selector.unregister(key.fd)
                                timeline.append(
                                    _timeline(
                                        "progress_pipe_eof",
                                        active_nodeid=active_nodeid,
                                        progress_count=progress_count,
                                    )
                                )
                                break
                            progress_buffer += chunk
                            while b"\n" in progress_buffer:
                                raw, progress_buffer = progress_buffer.split(
                                    b"\n", 1
                                )
                                received_ns = time.monotonic_ns()
                                if (
                                    transport_deadline_ns is None
                                    and received_ns >= deadline_ns
                                ):
                                    no_progress_due = True
                                    break
                                payload, active_nodeid = v3._parse_progress_event(
                                    raw,
                                    expected_sequence,
                                    active_nodeid,
                                )
                                transcript_handle.flush()
                                pipe_offset = os.fstat(
                                    transcript_handle.fileno()
                                ).st_size
                                enriched = {
                                    **payload,
                                    "controller_received_monotonic_ns": received_ns,
                                    "controller_received_wall_time_epoch": time.time(),
                                    "transcript_offset": pipe_offset,
                                }
                                progress_handle.write(
                                    json.dumps(
                                        enriched,
                                        separators=(",", ":"),
                                        sort_keys=True,
                                    )
                                    + "\n"
                                )
                                progress_handle.flush()
                                progress_count += 1
                                expected_sequence += 1
                                last_progress = enriched
                                phase = (
                                    "active_node"
                                    if payload["event"] == "logstart"
                                    else "post_last_progress"
                                )
                                deadline_ns = (
                                    received_ns
                                    + bounds["deadline_seconds"]
                                    * 1_000_000_000
                                )
                                if (
                                    payload["event"] == "logstart"
                                    and payload["nodeid"] == target_nodeid
                                ):
                                    target_reached = True
                                    target_started_ns = received_ns
                                    request_sample("target_start")
                                    pending_samples = {
                                        trigger: (
                                            received_ns + int(offset * 1e9)
                                        )
                                        for trigger, offset in SAMPLE_OFFSETS.items()
                                    }
                                elif (
                                    payload["event"] == "logfinish"
                                    and payload["nodeid"] == target_nodeid
                                ):
                                    request_sample("target_finish")
                                    target_finished = True
                                    pending_samples.clear()
                            if (
                                progress_eof
                                or invalid_reason is not None
                                or no_progress_due
                            ):
                                break
                    if invalid_reason is not None:
                        (
                            returncode,
                            interrupted,
                            killed,
                            cleanup_complete,
                            sample_sequence,
                        ) = _terminate_with_snapshots(
                            arm=arm,
                            bounds=bounds,
                            command_fd=command_write,
                            command_path=command_path,
                            identity=identity,
                            kernel_path=kernel_path,
                            process=process,
                            sample_sequence=sample_sequence,
                            surface=surface,
                            timeline=timeline,
                            trial=label,
                        )
                        break
                    polled = process.poll()
                    if progress_eof:
                        if progress_buffer:
                            invalid_reason = "partial_progress_event_at_eof"
                        elif active_nodeid is not None:
                            invalid_reason = "unbalanced_progress_at_eof"
                        elif progress_count != expected_progress:
                            invalid_reason = "incomplete_progress_at_eof"
                        if invalid_reason is not None:
                            (
                                returncode,
                                interrupted,
                                killed,
                                cleanup_complete,
                                sample_sequence,
                            ) = _terminate_with_snapshots(
                                arm=arm,
                                bounds=bounds,
                                command_fd=command_write,
                                command_path=command_path,
                                identity=identity,
                                kernel_path=kernel_path,
                                process=process,
                                sample_sequence=sample_sequence,
                                surface=surface,
                                timeline=timeline,
                                trial=label,
                            )
                            break
                        if polled is None:
                            (
                                polled,
                                leader_gone,
                                elapsed,
                            ) = v3._wait_for_natural_leader_exit(
                                process,
                                bounds["eof_leader_handshake_seconds"],
                            )
                            timeline.append(
                                _timeline(
                                    "leader_exit_after_progress_eof",
                                    elapsed_seconds=elapsed,
                                    leader_gone=leader_gone,
                                )
                            )
                            if not leader_gone:
                                invalid_reason = (
                                    "progress_eof_while_child_running"
                                )
                                (
                                    returncode,
                                    interrupted,
                                    killed,
                                    cleanup_complete,
                                    sample_sequence,
                                ) = _terminate_with_snapshots(
                                    arm=arm,
                                    bounds=bounds,
                                    command_fd=command_write,
                                    command_path=command_path,
                                    identity=identity,
                                    kernel_path=kernel_path,
                                    process=process,
                                    sample_sequence=sample_sequence,
                                    surface=surface,
                                    timeline=timeline,
                                    trial=label,
                                )
                                break
                        group_gone, elapsed = v3._wait_for_natural_group_drain(
                            identity["pgid"],
                            bounds["process_group_drain_seconds"],
                        )
                        timeline.append(
                            _timeline(
                                "natural_group_drain",
                                elapsed_seconds=elapsed,
                                group_gone=group_gone,
                            )
                        )
                        if not group_gone:
                            invalid_reason = "natural_process_group_not_drained"
                            (
                                returncode,
                                interrupted,
                                killed,
                                cleanup_complete,
                                sample_sequence,
                            ) = _terminate_with_snapshots(
                                arm=arm,
                                bounds=bounds,
                                command_fd=command_write,
                                command_path=command_path,
                                identity=identity,
                                kernel_path=kernel_path,
                                process=process,
                                sample_sequence=sample_sequence,
                                surface=surface,
                                timeline=timeline,
                                trial=label,
                            )
                        else:
                            returncode = polled
                            cleanup_complete = True
                        break
                    if polled is not None:
                        if transport_deadline_ns is None:
                            transport_deadline_ns = (
                                time.monotonic_ns()
                                + bounds["eof_leader_handshake_seconds"]
                                * 1_000_000_000
                            )
                            timeline.append(
                                _timeline(
                                    "leader_exit_before_progress_eof",
                                    returncode=polled,
                                )
                            )
                        elif time.monotonic_ns() >= transport_deadline_ns:
                            invalid_reason = (
                                "leader_exit_without_timely_progress_eof"
                            )
                            returncode = polled
                            cleanup_complete = not v3._process_group_exists(
                                identity["pgid"]
                            )
                            break
                        continue
                    no_progress_due = (
                        no_progress_due
                        or (
                            transport_deadline_ns is None
                            and time.monotonic_ns() >= deadline_ns
                        )
                    )
                    if no_progress_due:
                        transcript_handle.flush()
                        transcript_bytes = transcript_path.read_bytes()
                        current_window = transcript_bytes[pipe_offset:]
                        dump_present = (
                            v3._dump_marker(bounds["dump_seconds"])
                            in current_window
                        )
                        timeline.append(
                            _timeline(
                                "deadline_breach",
                                active_nodeid=active_nodeid,
                                dump_present=dump_present,
                                phase=phase,
                                transcript_offset=pipe_offset,
                                transcript_sha256=_sha256_bytes(
                                    transcript_bytes
                                ),
                            )
                        )
                        (
                            returncode,
                            interrupted,
                            killed,
                            cleanup_complete,
                            sample_sequence,
                        ) = _terminate_with_snapshots(
                            arm=arm,
                            bounds=bounds,
                            command_fd=command_write,
                            command_path=command_path,
                            identity=identity,
                            kernel_path=kernel_path,
                            process=process,
                            sample_sequence=sample_sequence,
                            surface=surface,
                            timeline=timeline,
                            trial=label,
                        )
                        if not dump_present:
                            invalid_reason = "deadline_breach_without_dump"
                        elif not cleanup_complete:
                            invalid_reason = "deadline_cleanup_incomplete"
                        elif active_nodeid == target_nodeid and target_reached:
                            classification = "matching_stall"
                        else:
                            classification = "terminated_nonstall_failure"
                        break
            if (
                invalid_reason is None
                and classification == "invalid"
                and returncode is not None
            ):
                natural_outcome, nonpassing, natural = v3._validate_natural_result(
                    returncode,
                    transcript_path,
                    report_path,
                    expected_nodes_path,
                )
                timeline.append(
                    _timeline(
                        "natural_validation",
                        details=natural,
                        outcome=natural_outcome,
                    )
                )
                if natural_outcome not in {
                    "complete_pass",
                    "complete_nonpassing",
                }:
                    invalid_reason = "natural_result_validation_failed"
                elif not target_reached or not target_finished:
                    classification = "terminated_nonstall_failure"
                else:
                    classification = "complete_natural"
    except KeyboardInterrupt:
        invalid_reason = "operator_interrupted_controller"
    except BaseException as exc:
        invalid_reason = f"controller_exception:{type(exc).__name__}"
    finally:
        if process is not None and (
            process.poll() is None
            or (
                identity is not None
                and v3._process_group_exists(identity["pgid"])
            )
        ):
            if (
                process.poll() is None
                and identity is not None
                and v3._identity_is_owned(identity)
            ):
                try:
                    (
                        returncode,
                        interrupted,
                        killed,
                        cleanup_complete,
                        sample_sequence,
                    ) = _terminate_with_snapshots(
                        arm=arm,
                        bounds=bounds,
                        command_fd=command_write,
                        command_path=command_path,
                        identity=identity,
                        kernel_path=kernel_path,
                        process=process,
                        sample_sequence=sample_sequence,
                        surface=surface,
                        timeline=timeline,
                        trial=label,
                    )
                except BaseException:
                    cleanup_complete = False
            elif identity is not None and v3._identity_is_owned(identity):
                try:
                    os.killpg(identity["pgid"], signal.SIGINT)
                    timeline.append(
                        _timeline(
                            "finalizer_sigint_sent",
                            pgid=identity["pgid"],
                        )
                    )
                    group_gone, _ = v3._wait_for_natural_group_drain(
                        identity["pgid"],
                        bounds["grace_seconds"],
                    )
                    if not group_gone:
                        os.killpg(identity["pgid"], signal.SIGKILL)
                        timeline.append(
                            _timeline(
                                "finalizer_sigkill_sent",
                                pgid=identity["pgid"],
                            )
                        )
                        group_gone, _ = v3._wait_for_natural_group_drain(
                            identity["pgid"],
                            bounds["process_group_drain_seconds"],
                        )
                    cleanup_complete = group_gone
                except (ProcessLookupError, PermissionError):
                    cleanup_complete = not v3._process_group_exists(
                        identity["pgid"]
                    )
            else:
                process.terminate()
        if arm == "O" and observer_read is not None:
            try:
                (
                    observer_buffer,
                    observer_pipe_eof,
                    added,
                ) = _read_observer_chunks(
                    buffer=observer_buffer,
                    fd=observer_read,
                    output_path=observer_path,
                )
                observer_count += added
                observer_eof = observer_eof or observer_pipe_eof
                if added and observer_path.is_file():
                    for line in observer_path.read_text(
                        encoding="utf-8"
                    ).splitlines()[-added:]:
                        envelope = json.loads(line)
                        if envelope["payload"]["event"] == "observer_ready":
                            observer_ready = True
            except BaseException as exc:
                invalid_reason = (
                    invalid_reason
                    or f"observer_final_drain_failed:{type(exc).__name__}"
                )
        if command_write is not None:
            try:
                os.close(command_write)
            except OSError:
                pass
        for fd in (
            progress_read,
            progress_write,
            observer_read,
            observer_write,
            command_read,
        ):
            if fd is not None and fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        selector.close()
    if invalid_reason is not None:
        classification = "invalid"
    if arm == "O" and not observer_ready:
        invalid_reason = invalid_reason or "observer_never_ready"
        classification = "invalid"
    if observer_buffer:
        invalid_reason = invalid_reason or "partial_observer_event_at_end"
        classification = "invalid"
    try:
        data_after = v3._archive_worktree_data(repo, trial)
    except BaseException as exc:
        data_after = []
        invalid_reason = f"data_archive_failed:{type(exc).__name__}"
        classification = "invalid"
    try:
        verified_after = _verify_preflight(preflight_path)
        if verified_after != preflight:
            raise RuntimeError("preflight changed during attempt")
    except BaseException as exc:
        invalid_reason = f"post_attempt_preflight_failed:{type(exc).__name__}"
        classification = "invalid"
    ended_ns = time.monotonic_ns()
    record = {
        "arm": arm,
        "attempt": attempt,
        "bounds": bounds,
        "classification": classification,
        "cleanup_complete": cleanup_complete,
        "command": args,
        "data_entries_after": data_after,
        "data_entries_before": data_before,
        "dump_present": dump_present,
        "duration_seconds": (ended_ns - started_ns) / 1_000_000_000,
        "ended_at_epoch": time.time(),
        "ended_monotonic_ns": ended_ns,
        "environment_names": sorted(env),
        "identity": identity,
        "interrupted": interrupted,
        "invalid_reason": invalid_reason,
        "killed": killed,
        "label": label,
        "last_progress": last_progress,
        "natural_outcome": natural_outcome,
        "nonpassing_node_ids": nonpassing,
        "observer_count": observer_count,
        "observer_eof": observer_eof,
        "observer_ready": observer_ready,
        "observer_sha256": (
            _sha256(observer_path) if observer_path.is_file() else None
        ),
        "process_returncode": returncode,
        "progress_count": progress_count,
        "progress_eof": progress_eof,
        "progress_sha256": (
            _sha256(progress_path) if progress_path.is_file() else None
        ),
        "protocol_id": PROTOCOL_ID,
        "report_sha256": (
            _sha256(report_path) if report_path.is_file() else None
        ),
        "requested_samples": requested_samples,
        "schema_version": 1,
        "started_at_epoch": started_wall,
        "started_monotonic_ns": started_ns,
        "surface": surface,
        "target_finished": target_finished,
        "target_nodeid": target_nodeid,
        "target_reached": target_reached,
        "timeline": timeline,
        "transcript_sha256": (
            _sha256(transcript_path) if transcript_path.is_file() else None
        ),
    }
    _atomic_json(trial / "record.json", record)
    return record


def _block_qualifies(records: list[dict[str, Any]]) -> bool:
    if len(records) != 2 or {record["arm"] for record in records} != {"C", "O"}:
        return False
    return all(
        record["classification"] == "matching_stall"
        and record["dump_present"]
        and record["cleanup_complete"]
        and record["target_reached"]
        and record["last_progress"]["nodeid"] == record["target_nodeid"]
        for record in records
    )


def run_campaign(preflight_path: Path) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path, full_official=True)
    root = Path(preflight["artifact_root"])
    summary_path = root / "campaign-summary.json"
    if summary_path.exists() or summary_path.with_suffix(".json.tmp").exists():
        raise RuntimeError("observer campaign summary already exists")
    if list(root.glob("campaign-*-*/record.json")):
        raise RuntimeError("observer campaign attempt directories already exist")
    launch_count = 0
    invalid_replacements = {"A": 0, "P": 0}
    qualifying_blocks = {"A": 0, "P": 0}
    stopped_surfaces: set[str] = set()
    records_by_block: dict[tuple[str, int], list[dict[str, Any]]] = {}
    attempt_records: list[dict[str, Any]] = []
    campaign_invalid_reason: str | None = None
    for row in preflight["schedule"]:
        surface = row["surface"]
        block = row["block"]
        arm = row["arm"]
        slot = row["slot"]
        if surface in stopped_surfaces:
            continue
        launch_count += 1
        if launch_count > 18:
            raise RuntimeError("observer launch cap exceeded")
        base_label = f"campaign-{surface}-b{block}-{arm.lower()}"
        record = _run_attempt(
            arm=arm,
            attempt=launch_count,
            bounds=BOUNDS,
            expected_nodes_path=_artifact(preflight, f"{surface}_nodes"),
            label=base_label,
            preflight_path=preflight_path,
            selectors_=_read_lines(_artifact(preflight, f"{surface}_paths")),
            surface=surface,
            target_nodeid=str(SURFACES[surface]["target"]),
        )
        record.update({"block": block, "replacement": False, "slot": slot})
        _atomic_json(root / base_label / "record.json", record)
        attempt_records.append(record)
        admitted = record
        if record["classification"] == "invalid":
            if invalid_replacements[surface] >= 1:
                campaign_invalid_reason = (
                    f"second_controller_invalid_on_surface_{surface}"
                )
                break
            invalid_replacements[surface] += 1
            launch_count += 1
            if launch_count > 18:
                campaign_invalid_reason = "observer_launch_cap_exceeded"
                break
            replacement_label = f"{base_label}-replacement"
            replacement = _run_attempt(
                arm=arm,
                attempt=launch_count,
                bounds=BOUNDS,
                expected_nodes_path=_artifact(
                    preflight,
                    f"{surface}_nodes",
                ),
                label=replacement_label,
                preflight_path=preflight_path,
                selectors_=_read_lines(
                    _artifact(preflight, f"{surface}_paths")
                ),
                surface=surface,
                target_nodeid=str(SURFACES[surface]["target"]),
            )
            replacement.update(
                {"block": block, "replacement": True, "slot": slot}
            )
            _atomic_json(root / replacement_label / "record.json", replacement)
            attempt_records.append(replacement)
            if replacement["classification"] == "invalid":
                campaign_invalid_reason = (
                    f"replacement_controller_invalid_on_surface_{surface}"
                )
                break
            admitted = replacement
        records_by_block.setdefault((surface, block), []).append(admitted)
        block_records = records_by_block[(surface, block)]
        if len(block_records) == 2:
            if _block_qualifies(block_records):
                qualifying_blocks[surface] += 1
            if qualifying_blocks[surface] >= 2:
                stopped_surfaces.add(surface)
        if stopped_surfaces == {"A", "P"}:
            break
    block_summary = []
    for (surface, block), records in sorted(records_by_block.items()):
        block_summary.append(
            {
                "arms": [record["arm"] for record in records],
                "block": block,
                "qualifies": _block_qualifies(records),
                "record_labels": [record["label"] for record in records],
                "surface": surface,
            }
        )
    _verify_preflight(preflight_path, full_official=True)
    summary = {
        "attempt_labels": [record["label"] for record in attempt_records],
        "blocks": block_summary,
        "campaign_invalid_reason": campaign_invalid_reason,
        "complete": campaign_invalid_reason is None,
        "diagnostic_only": True,
        "invalid_replacements": invalid_replacements,
        "launch_count": launch_count,
        "official_price_admission_unchanged": True,
        "protocol_id": PROTOCOL_ID,
        "qualifying_blocks": qualifying_blocks,
        "schema_version": 1,
        "stopped_surfaces": sorted(stopped_surfaces),
    }
    _atomic_json(summary_path, summary)
    return summary


def _loop_by_ssock_inode(
    snapshot: dict[str, Any],
    inode: int,
) -> dict[str, Any]:
    matches = [
        loop
        for loop in snapshot["loops"]
        if loop["ssock"]["inode"] == inode
    ]
    if len(matches) != 1:
        raise RuntimeError("controlled loop was not uniquely observed")
    return matches[0]


def _probe_snapshot(
    *,
    root: Path,
    repo: Path,
    surface: str = "A",
    target_thread_ident: int | None = None,
) -> dict[str, Any]:
    import eir005_observer_plugin as observer

    return observer.capture_snapshot(
        artifact_root=root,
        repo=repo,
        surface=surface,
        target_active=True,
        target_nodeid="probe::target",
        target_thread_ident=target_thread_ident,
        target_thread_native_id=None,
        trial="probe",
        trigger="early",
        sequence=1,
        loop_labels={},
    )


def _loop_worker(
    *,
    ready: threading.Event,
    state: dict[str, Any],
    stop: threading.Event,
) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def wait_for_stop() -> None:
        ready.set()
        while not stop.is_set():
            await asyncio.sleep(0.01)

    state["loop"] = loop
    try:
        loop.run_until_complete(wait_for_stop())
    finally:
        loop.close()


def _probe_healthy_loop(root: Path, repo: Path) -> dict[str, Any]:
    ready = threading.Event()
    stop = threading.Event()
    state: dict[str, Any] = {}
    thread = threading.Thread(
        target=_loop_worker,
        kwargs={"ready": ready, "state": state, "stop": stop},
        name="eir005-probe-healthy-loop",
    )
    thread.start()
    try:
        if not ready.wait(timeout=2):
            raise RuntimeError("healthy-loop probe did not start")
        loop = state["loop"]
        inode = os.fstat(loop._ssock.fileno()).st_ino
        snapshot = _probe_snapshot(root=root, repo=repo)
        record = _loop_by_ssock_inode(snapshot, inode)
        registered = {
            item["fd"]
            for item in record["selector"]["registrations"]
        }
        if (
            not record["running"]
            or not record["ssock"]["open"]
            or not record["csock"]["open"]
            or record["ssock"]["fd"] not in registered
            or record["ssock"]["queued_bytes"] != 0
            or record["tasks_count"] < 1
        ):
            raise RuntimeError("healthy-loop snapshot is incomplete")
        return {
            "registered": True,
            "running": True,
            "tasks_present": True,
            "wake_queue_empty": True,
        }
    finally:
        stop.set()
        thread.join(timeout=2)
        if thread.is_alive():
            raise RuntimeError("healthy-loop probe did not stop")


def _probe_queued_wake(root: Path, repo: Path) -> dict[str, Any]:
    import eir005_observer_plugin as observer

    loop = asyncio.new_event_loop()
    completed: list[str] = []
    try:
        inode = os.fstat(loop._ssock.fileno()).st_ino
        loop.call_soon_threadsafe(completed.append, "done")
        snapshot = observer.capture_snapshot(
            artifact_root=root,
            repo=repo,
            surface="A",
            target_active=True,
            target_nodeid="probe::queued",
            target_thread_ident=threading.get_ident(),
            target_thread_native_id=threading.get_native_id(),
            trial="probe-queued",
            trigger="early",
            sequence=1,
            loop_labels={},
        )
        record = _loop_by_ssock_inode(snapshot, inode)
        registered = {
            item["fd"]
            for item in record["selector"]["registrations"]
        }
        if (
            record["ready_count"] < 1
            or record["ssock"]["queued_bytes"] is None
            or record["ssock"]["queued_bytes"] < 1
            or record["ssock"]["fd"] not in registered
        ):
            raise RuntimeError("queued wake was not observed")
        loop.run_until_complete(asyncio.sleep(0))
        if completed != ["done"]:
            raise RuntimeError("observer consumed or corrupted queued callback")
        return {
            "callback_completed_after_snapshot": True,
            "ready_pending": True,
            "registered": True,
            "wake_byte_pending": True,
        }
    finally:
        loop.close()


def _probe_multiple_loops(root: Path, repo: Path) -> dict[str, Any]:
    workers: list[
        tuple[threading.Thread, threading.Event, threading.Event, dict[str, Any]]
    ] = []
    for name in ("second-created", "first-created"):
        ready = threading.Event()
        stop = threading.Event()
        state: dict[str, Any] = {}
        thread = threading.Thread(
            target=_loop_worker,
            kwargs={"ready": ready, "state": state, "stop": stop},
            name=f"eir005-{name}",
        )
        workers.append((thread, ready, stop, state))
        thread.start()
    try:
        if not all(ready.wait(timeout=2) for _, ready, _, _ in workers):
            raise RuntimeError("multiple-loop probe did not start")
        inodes = {
            os.fstat(state["loop"]._ssock.fileno()).st_ino
            for _, _, _, state in workers
        }
        snapshot = _probe_snapshot(root=root, repo=repo)
        records = [
            loop
            for loop in snapshot["loops"]
            if loop["ssock"]["inode"] in inodes
        ]
        if (
            len(records) != 2
            or len({record["owner_thread_ident"] for record in records}) != 2
            or len({record["owner_thread_native_id"] for record in records})
            != 2
            or {record["owner_thread_name"] for record in records}
            != {"eir005-probe"}
        ):
            raise RuntimeError("observer collapsed multiple loops")
        return {
            "creation_order_not_selector": True,
            "loops": 2,
            "owner_threads": 2,
        }
    finally:
        for _, _, stop, _ in workers:
            stop.set()
        for thread, _, _, _ in workers:
            thread.join(timeout=2)
            if thread.is_alive():
                raise RuntimeError("multiple-loop worker did not stop")


def _probe_sanitization(root: Path, repo: Path) -> dict[str, Any]:
    import eir005_observer_plugin as observer

    secret = "credential-SHOULD-NOT-APPEAR"
    home = "/home/private-user/secret-file"
    exception = ValueError("exception-prose-SHOULD-NOT-APPEAR")
    loop = asyncio.new_event_loop()
    task: asyncio.Task[Any] | None = None

    def callback(value: str, failure: BaseException) -> None:
        del value, failure

    async def pending_coroutine() -> None:
        local_secret = home
        if local_secret:
            await asyncio.sleep(3600)

    try:
        inode = os.fstat(loop._ssock.fileno()).st_ino
        loop.call_soon_threadsafe(
            functools.partial(callback, secret, exception)
        )
        task = loop.create_task(pending_coroutine())
        snapshot = observer.capture_snapshot(
            artifact_root=root,
            repo=repo,
            surface="A",
            target_active=True,
            target_nodeid="probe::sanitization",
            target_thread_ident=threading.get_ident(),
            target_thread_native_id=threading.get_native_id(),
            trial="probe-sanitization",
            trigger="early",
            sequence=1,
            loop_labels={},
        )
        _loop_by_ssock_inode(snapshot, inode)
        encoded = json.dumps(snapshot, sort_keys=True)
        forbidden = [
            secret,
            home,
            str(exception),
            "/home/",
            '"locals"',
            '"repr"',
        ]
        if any(value in encoded for value in forbidden):
            raise RuntimeError("observer leaked prohibited diagnostic content")
        return {
            "absolute_home_absent": True,
            "arguments_absent": True,
            "exception_prose_absent": True,
            "locals_absent": True,
            "repr_absent": True,
        }
    finally:
        if task is not None:
            task.cancel()
            loop.run_until_complete(
                asyncio.gather(task, return_exceptions=True)
            )
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


def _probe_kernel_join(root: Path, repo: Path) -> dict[str, Any]:
    loop = asyncio.new_event_loop()
    completed: list[bool] = []
    try:
        ssock_fd = loop._ssock.fileno()
        ssock_inode = os.fstat(ssock_fd).st_ino
        loop.call_soon_threadsafe(completed.append, True)
        snapshot = _probe_snapshot(
            root=root,
            repo=repo,
            target_thread_ident=threading.get_ident(),
        )
        record = _loop_by_ssock_inode(snapshot, ssock_inode)
        kernel = _capture_kernel(
            pid=os.getpid(),
            sample_sequence=1,
            surface="A",
            trigger="early",
            trial="probe-kernel-join",
        )
        ss_rows = [
            row
            for row in kernel["ss_rows"]
            if row["inode"] == ssock_inode
        ]
        epoll_matches = [
            item
            for item in kernel["fdinfo"]
            if item["kind"] == "eventpoll"
            and any(
                registration["fd"] == ssock_fd
                for registration in item["registrations"]
            )
        ]
        if (
            record["ssock"]["queued_bytes"] is None
            or record["ssock"]["queued_bytes"] < 1
            or not ss_rows
            or max(row["receive_queue"] for row in ss_rows) < 1
            or not epoll_matches
        ):
            raise RuntimeError("kernel join did not preserve wakeup evidence")
        return {
            "epoll_registration_joined": True,
            "fionread_positive": True,
            "inode_joined": True,
            "ss_receive_queue_positive": True,
        }
    finally:
        loop.run_until_complete(asyncio.sleep(0))
        if completed != [True]:
            raise RuntimeError("kernel-join observer consumed the callback")
        loop.close()


def _collect_identity_arm(
    *,
    arm: str,
    preflight: dict[str, Any],
    root: Path,
) -> list[str]:
    trial = root / f"probe-collect-{arm.lower()}"
    trial.mkdir()
    report = trial / "report.json"
    stdout = trial / "stdout.txt"
    output_read: int | None = None
    output_write: int | None = None
    command_read: int | None = None
    command_write: int | None = None
    env = {
        "PATH": preflight["path"],
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "Asia/Taipei",
        "HOME": str(trial / "home"),
        "TMPDIR": str(trial / "tmp"),
        "PYTHONHASHSEED": "0",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(root),
        REPORT_ENV: str(report),
    }
    (trial / "home").mkdir()
    (trial / "tmp").mkdir()
    args = [
        preflight["python"],
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        REPORTER_MODULE,
    ]
    pass_fds: list[int] = []
    if arm == "O":
        output_read, output_write = os.pipe()
        command_read, command_write = os.pipe()
        env.update(
            {
                OBSERVER_COMMAND_ENV: str(command_read),
                OBSERVER_OUTPUT_ENV: str(output_write),
                OBSERVER_REPO_ENV: preflight["repo"],
                OBSERVER_ROOT_ENV: preflight["artifact_root"],
                OBSERVER_SURFACE_ENV: "A",
                OBSERVER_TARGET_ENV: "probes/probe_pass.py::test_probe_pass",
                OBSERVER_TRIAL_ENV: "probe-collect-o",
            }
        )
        pass_fds = [command_read, output_write]
        args.extend(["-p", OBSERVER_MODULE])
    args.append("probes/probe_pass.py")
    try:
        with stdout.open("wb") as handle:
            result = subprocess.run(
                args,
                cwd=root,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                pass_fds=tuple(pass_fds),
                timeout=15,
            )
        if result.returncode != 0 or not report.is_file():
            raise RuntimeError(f"collection identity arm failed: {arm}")
        payload = _load_json(report)
        return payload["collected_node_ids"]
    finally:
        for fd in (output_read, output_write, command_read, command_write):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _probe_plugin_identity(
    preflight: dict[str, Any],
    preflight_path: Path,
    root: Path,
) -> dict[str, Any]:
    control = _collect_identity_arm(arm="C", preflight=preflight, root=root)
    observed = _collect_identity_arm(arm="O", preflight=preflight, root=root)
    expected = ["probes/probe_pass.py::test_probe_pass"]
    if control != expected or observed != expected:
        raise RuntimeError("observer plugin changed collection identity")
    source = _artifact(preflight, "plugin").read_text(encoding="utf-8")
    tree = ast.parse(source)
    test_helpers = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    if test_helpers:
        raise RuntimeError("observer plugin exposes test-named helpers")
    transport_record = _run_attempt(
        arm="O",
        attempt=1,
        bounds=PROBE_BOUNDS,
        expected_nodes_path=_artifact(preflight, "probe_nodes"),
        label="probe-observer-transport",
        preflight_path=preflight_path,
        selectors_=["probes/probe_pass.py"],
        surface="A",
        target_nodeid=expected[0],
        working_directory=root,
    )
    observer_events = _read_jsonl(
        root / "probe-observer-transport" / "observer.jsonl"
    )
    active_start = any(
        event["payload"].get("event") == "snapshot"
        and event["payload"].get("trigger") == "target_start"
        and event["payload"].get("target_active") is True
        for event in observer_events
    )
    if (
        transport_record["classification"] != "complete_natural"
        or not transport_record["observer_ready"]
        or transport_record["observer_count"] < 2
        or not active_start
        or transport_record["interrupted"]
        or transport_record["killed"]
    ):
        raise RuntimeError("observer plugin transport integration failed")
    return {
        "control_nodes": 1,
        "observed_nodes": 1,
        "transport_natural": True,
        "test_named_helpers": 0,
    }


def _probe_static_nonintervention(
    preflight: dict[str, Any],
) -> dict[str, Any]:
    source = _artifact(preflight, "plugin").read_text(encoding="utf-8")
    tree = ast.parse(source)
    prohibited = {
        "_read_from_self",
        "_run_once",
        "_write_to_self",
        "call_soon_threadsafe",
        "recv",
        "send",
        "stop",
        "wake",
    }
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else function.id
                if isinstance(function, ast.Name)
                else None
            )
            if name in prohibited:
                findings.append(f"call:{name}:{node.lineno}")
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in prohibited:
                    findings.append(f"assign:{target.attr}:{node.lineno}")
    if findings:
        raise RuntimeError(
            "observer source contains prohibited intervention: "
            + ",".join(findings)
        )
    return {"findings": 0}


def _probe_signal_timeline(
    *,
    preflight_path: Path,
    root: Path,
) -> dict[str, Any]:
    cases = [
        (
            "interruptible",
            "probes/probe_interruptible.py",
            "probes/probe_interruptible.py::test_probe_interruptible",
            False,
        ),
        (
            "ignored",
            "probes/probe_ignore_sigint.py",
            "probes/probe_ignore_sigint.py::test_probe_ignore_sigint",
            True,
        ),
    ]
    results: dict[str, Any] = {}
    for name, selector_, nodeid, expect_kill in cases:
        nodes = root / f"probe-{name}.nodes"
        nodes.write_text(f"{nodeid}\n", encoding="utf-8")
        record = _run_attempt(
            arm="C",
            attempt=1,
            bounds=PROBE_BOUNDS,
            expected_nodes_path=nodes,
            label=f"probe-signal-{name}",
            preflight_path=preflight_path,
            selectors_=[selector_],
            surface="A",
            target_nodeid=nodeid,
            working_directory=root,
        )
        if (
            record["classification"] != "matching_stall"
            or not record["interrupted"]
            or bool(record["killed"]) != expect_kill
        ):
            raise RuntimeError(f"signal timeline probe failed: {name}")
        results[name] = {
            "interrupted": True,
            "killed": expect_kill,
            "matching_stall": True,
        }
    return results


def _probe_paired_verifier(preflight: dict[str, Any]) -> dict[str, Any]:
    result = subprocess.run(
        [
            preflight["python"],
            str(_artifact(preflight, "verifier")),
            "probe-paired",
        ],
        cwd=preflight["artifact_root"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("paired verifier probe failed")
    payload = json.loads(result.stdout)
    if payload != {
        "controller_claim_ignored": True,
        "full_block_qualifies": True,
        "one_arm_blocks_rejected": True,
    }:
        raise RuntimeError("paired verifier probe result changed")
    return payload


def _probe_ss_fail_closed() -> dict[str, Any]:
    original = list(SS_COMMAND)
    try:
        SS_COMMAND[:] = ["/bin/false"]
        try:
            _ss_rows(set())
        except (FileNotFoundError, RuntimeError):
            return {"unavailable_is_not_empty_queue": True}
        raise RuntimeError("unavailable ss was downgraded to an empty queue")
    finally:
        SS_COMMAND[:] = original


def _probe_frozen_root(root: Path) -> dict[str, Any]:
    before = _sha256(OFFICIAL_V3_ROOT / OFFICIAL_MANIFEST)
    try:
        _assert_artifact_root_safe(OFFICIAL_V3_ROOT)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("official v3 root was accepted as observer output")
    with tempfile.TemporaryDirectory(prefix="eir005-v3-copy-") as raw:
        copied = Path(raw)
        sources = {
            "price_truth_tier_runner.py": "price_truth_tier_runner.py",
            "arkscope_price_truth_tier_reporter.py": (
                "arkscope_price_truth_tier_reporter.py"
            ),
            "A.paths": "T1.paths",
            "A.nodes": "base-T1.nodes",
            "P.paths": "T6.paths",
            "P.nodes": "base-T6.nodes",
        }
        for destination, source in sources.items():
            shutil.copy2(
                OFFICIAL_V3_ROOT / source,
                copied / destination,
            )
        with (copied / "price_truth_tier_runner.py").open("ab") as handle:
            handle.write(b"\n# mutation\n")
        try:
            _verify_copied_v3(copied)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("mutated copied v3 identity was accepted")
    after = _sha256(OFFICIAL_V3_ROOT / OFFICIAL_MANIFEST)
    if before != after or after != OFFICIAL_HASHES[OFFICIAL_MANIFEST]:
        raise RuntimeError("official v3 manifest changed during frozen-root probe")
    return {
        "mutated_copy_refused": True,
        "official_manifest_unchanged": True,
        "official_root_refused": True,
    }


def run_probe_suite(
    preflight_path: Path,
    *,
    only: str | None = None,
) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path, full_official=True)
    root = Path(preflight["artifact_root"])
    repo = Path(preflight["repo"])
    probes = {
        "frozen_root": lambda: _probe_frozen_root(root),
        "healthy_loop": lambda: _probe_healthy_loop(root, repo),
        "kernel_join": lambda: _probe_kernel_join(root, repo),
        "multiple_loops": lambda: _probe_multiple_loops(root, repo),
        "paired_verifier": lambda: _probe_paired_verifier(preflight),
        "plugin_identity": lambda: _probe_plugin_identity(
            preflight,
            preflight_path,
            root,
        ),
        "queued_wake": lambda: _probe_queued_wake(root, repo),
        "sanitization": lambda: _probe_sanitization(root, repo),
        "signal_timeline": lambda: _probe_signal_timeline(
            preflight_path=preflight_path,
            root=root,
        ),
        "ss_fail_closed": _probe_ss_fail_closed,
        "static_nonintervention": lambda: _probe_static_nonintervention(
            preflight
        ),
    }
    if only is not None and only not in probes:
        raise RuntimeError(f"unknown observer probe: {only}")
    selected = [only] if only is not None else list(probes)
    checks: dict[str, Any] = {}
    for name in selected:
        checks[name] = probes[name]()
    _verify_preflight(preflight_path, full_official=True)
    summary = {
        "checks": checks,
        "protocol_id": PROTOCOL_ID,
        "schema_version": 1,
    }
    destination = (
        root / "probe-summary.json"
        if only is None
        else root / f"probe-summary-{only}.json"
    )
    _atomic_json(destination, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-preflight")
    prepare.add_argument("--artifact-root", type=Path, required=True)
    prepare.add_argument("--repo", type=Path, required=True)
    probes = subparsers.add_parser("probe-suite")
    probes.add_argument("--preflight", type=Path, required=True)
    probes.add_argument(
        "--only",
        choices=(
            "frozen_root",
            "healthy_loop",
            "kernel_join",
            "multiple_loops",
            "paired_verifier",
            "plugin_identity",
            "queued_wake",
            "sanitization",
            "signal_timeline",
            "ss_fail_closed",
            "static_nonintervention",
        ),
    )
    campaign = subparsers.add_parser("run-campaign")
    campaign.add_argument("--preflight", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare-preflight":
        result = {
            "preflight": str(
                prepare_preflight(
                    artifact_root=args.artifact_root,
                    repo=args.repo,
                )
            )
        }
    elif args.command == "probe-suite":
        result = run_probe_suite(args.preflight, only=args.only)
    else:
        result = run_campaign(args.preflight)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
<!-- EIR005_CONTROLLER_END -->

## Appendix B: Exact Observer Plugin

<!-- EIR005_PLUGIN_BEGIN -->
```python
from __future__ import annotations

import array
import asyncio
import fcntl
import gc
import json
import os
import stat
import socket
import sys
import termios
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import pytest


SCHEMA_VERSION = 1
OUTPUT_FD_ENV = "EIR005_OBSERVER_OUTPUT_FD"
COMMAND_FD_ENV = "EIR005_OBSERVER_COMMAND_FD"
TARGET_ENV = "EIR005_OBSERVER_TARGET"
SURFACE_ENV = "EIR005_OBSERVER_SURFACE"
TRIAL_ENV = "EIR005_OBSERVER_TRIAL"
REPO_ENV = "EIR005_OBSERVER_REPO"
ARTIFACT_ROOT_ENV = "EIR005_OBSERVER_ARTIFACT_ROOT"
TRIGGERS = {
    "target_start",
    "early",
    "pre_dump",
    "post_dump",
    "late",
    "pre_deadline",
    "pre_sigint",
    "post_sigint",
    "target_finish",
}

_observer: "_Observer | None" = None


def _safe_fd(name: str, *, readable: bool) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.isdecimal():
        raise RuntimeError(f"{name} must be a decimal file descriptor")
    fd = int(raw)
    if fd <= 2:
        raise RuntimeError(f"{name} must not target a standard stream")
    try:
        metadata = os.fstat(fd)
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    except OSError as exc:
        raise RuntimeError(f"{name} is not open") from exc
    if not stat.S_ISFIFO(metadata.st_mode):
        raise RuntimeError(f"{name} must reference a pipe")
    mode = flags & os.O_ACCMODE
    if readable and mode == os.O_WRONLY:
        raise RuntimeError(f"{name} must be readable")
    if not readable and mode == os.O_RDONLY:
        raise RuntimeError(f"{name} must be writable")
    os.set_inheritable(fd, False)
    return fd


def _qualified_name(value: Any) -> str:
    if value is None:
        return "builtins.NoneType"
    candidate = value
    wrapped = getattr(candidate, "func", None)
    if wrapped is not None:
        candidate = wrapped
    if isinstance(candidate, tuple) and candidate:
        candidate = candidate[0]
    module = getattr(candidate, "__module__", None)
    qualname = getattr(candidate, "__qualname__", None)
    if isinstance(module, str) and isinstance(qualname, str):
        return f"{module}.{qualname}"
    value_type = type(candidate)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _coroutine_name(coroutine: Any) -> str:
    code = (
        getattr(coroutine, "cr_code", None)
        or getattr(coroutine, "gi_code", None)
        or getattr(coroutine, "ag_code", None)
    )
    if code is not None:
        module = getattr(type(coroutine), "__module__", "builtins")
        return f"{module}.{code.co_name}"
    return _qualified_name(coroutine)


def _safe_filename(
    filename: str,
    *,
    repo: Path,
    artifact_root: Path,
) -> str:
    path = Path(filename)
    for label, root in (
        ("repo", repo),
        ("artifact", artifact_root),
        ("python", Path(sys.prefix)),
    ):
        try:
            relative = path.resolve().relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        return f"{label}/{relative.as_posix()}"
    return path.name


def _safe_thread_name(value: str) -> str:
    if value == "MainThread":
        return value
    if value.startswith("asyncio-portal-"):
        return "asyncio-portal"
    if value == "EIR-005 Machine-State Observer":
        return value
    if value == "PyrateLimiter's Leaker":
        return value
    if value.startswith("eir005-probe-") or value.startswith("eir005-"):
        return "eir005-probe"
    return "thread"


def _thread_stacks(
    *,
    repo: Path,
    artifact_root: Path,
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    frames = sys._current_frames()
    thread_by_ident = {
        thread.ident: thread
        for thread in threading.enumerate()
        if thread.ident is not None
    }
    records: list[dict[str, Any]] = []
    stacks: dict[int, list[dict[str, Any]]] = {}
    for ident in sorted(frames):
        frame_records = [
            {
                "file": _safe_filename(
                    item.filename,
                    repo=repo,
                    artifact_root=artifact_root,
                ),
                "function": item.name,
                "line": int(item.lineno),
            }
            for item in traceback.extract_stack(frames[ident])
        ]
        stacks[ident] = frame_records
        thread = thread_by_ident.get(ident)
        records.append(
            {
                "ident": ident,
                "name": (
                    _safe_thread_name(thread.name)
                    if thread is not None
                    else "unknown"
                ),
                "native_id": (
                    thread.native_id if thread is not None else None
                ),
                "stack": frame_records,
            }
        )
    return records, stacks


def _queued_bytes(fd: int) -> int | None:
    if fd < 0:
        return None
    value = array.array("i", [0])
    try:
        fcntl.ioctl(fd, termios.FIONREAD, value, True)
    except OSError:
        return None
    return max(0, int(value[0]))


def _socket_record(sock: Any) -> dict[str, Any]:
    try:
        fd = int(sock.fileno())
    except (AttributeError, OSError, TypeError, ValueError):
        fd = -1
    record: dict[str, Any] = {
        "blocking": None,
        "family": None,
        "fd": fd,
        "inode": None,
        "open": False,
        "queued_bytes": None,
        "receive_buffer": None,
        "send_buffer": None,
        "type": None,
    }
    if fd < 0:
        return record
    try:
        metadata = os.fstat(fd)
    except OSError:
        record["open"] = False
        return record
    record.update(
        {
            "blocking": bool(sock.getblocking()),
            "family": int(sock.family),
            "inode": int(metadata.st_ino),
            "open": True,
            "queued_bytes": _queued_bytes(fd),
            "type": int(sock.type),
        }
    )
    for key, option in (
        ("receive_buffer", socket.SO_RCVBUF),
        ("send_buffer", socket.SO_SNDBUF),
    ):
        try:
            record[key] = int(
                sock.getsockopt(socket.SOL_SOCKET, option)
            )
        except (AttributeError, OSError, TypeError, ValueError):
            record[key] = None
    return record


def _selector_record(selector: Any) -> dict[str, Any]:
    registrations: list[dict[str, Any]] = []
    error_code: str | None = None
    try:
        values = list(selector.get_map().values())
        for key in values:
            registrations.append(
                {
                    "callback": _qualified_name(key.data),
                    "events": int(key.events),
                    "fd": int(key.fd),
                }
            )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        error_code = "selector_snapshot_race"
    registrations.sort(
        key=lambda item: (
            item["fd"],
            item["events"],
            item["callback"],
        )
    )
    return {
        "class": _qualified_name(type(selector)),
        "error_code": error_code,
        "registrations": registrations,
    }


def _task_records(loop: Any) -> tuple[list[dict[str, Any]], str | None]:
    records: list[dict[str, Any]] = []
    try:
        tasks = list(asyncio.all_tasks(loop))
        for task in tasks:
            records.append(
                {
                    "cancelled": bool(task.cancelled()),
                    "coroutine": _coroutine_name(task.get_coro()),
                    "done": bool(task.done()),
                    "state": str(getattr(task, "_state", "UNKNOWN")),
                }
            )
    except (AttributeError, RuntimeError, TypeError):
        return [], "task_snapshot_race"
    records.sort(
        key=lambda item: (
            item["coroutine"],
            item["state"],
            item["done"],
            item["cancelled"],
        )
    )
    return records, None


def _callback_names(values: Any) -> tuple[list[str], str | None]:
    try:
        names = [
            _qualified_name(getattr(value, "_callback", value))
            for value in list(values)
        ]
    except (AttributeError, RuntimeError, TypeError):
        return [], "callback_snapshot_race"
    return sorted(names), None


def _loop_candidates() -> list[Any]:
    loops: list[Any] = []
    for value in gc.get_objects():
        try:
            if (
                isinstance(value, asyncio.AbstractEventLoop)
                and hasattr(value, "_selector")
                and hasattr(value, "_ssock")
                and hasattr(value, "_csock")
            ):
                loops.append(value)
        except (ReferenceError, RuntimeError, TypeError):
            continue
    return loops


def capture_snapshot(
    *,
    artifact_root: Path,
    repo: Path,
    surface: str,
    target_active: bool,
    target_nodeid: str,
    target_thread_ident: int | None,
    target_thread_native_id: int | None,
    trial: str,
    trigger: str,
    sequence: int,
    loop_labels: dict[int, str],
) -> dict[str, Any]:
    threads, stacks = _thread_stacks(repo=repo, artifact_root=artifact_root)
    candidates: list[tuple[tuple[Any, ...], Any]] = []
    for loop in _loop_candidates():
        owner_ident = getattr(loop, "_thread_id", None)
        ssock = _socket_record(getattr(loop, "_ssock", None))
        candidates.append(
            (
                (
                    owner_ident is None,
                    owner_ident if isinstance(owner_ident, int) else -1,
                    ssock["fd"] if isinstance(ssock["fd"], int) else -1,
                    _qualified_name(type(loop)),
                    id(loop),
                ),
                loop,
            )
        )
    loops: list[dict[str, Any]] = []
    thread_by_ident = {
        item["ident"]: item
        for item in threads
    }
    for _, loop in sorted(candidates, key=lambda item: item[0]):
        identity = id(loop)
        if identity not in loop_labels:
            loop_labels[identity] = f"loop-{len(loop_labels) + 1}"
        owner_ident = getattr(loop, "_thread_id", None)
        owner = thread_by_ident.get(owner_ident)
        ready, ready_error = _callback_names(getattr(loop, "_ready", ()))
        scheduled, scheduled_error = _callback_names(
            getattr(loop, "_scheduled", ())
        )
        scheduled_values = list(getattr(loop, "_scheduled", ()))
        deadlines = [
            float(getattr(value, "_when"))
            for value in scheduled_values
            if isinstance(getattr(value, "_when", None), (int, float))
        ]
        tasks, task_error = _task_records(loop)
        stack = stacks.get(owner_ident, [])
        match_reasons: list[str] = []
        if surface == "A" and owner_ident == target_thread_ident:
            match_reasons.append("pytest_target_thread")
        if surface == "P" and owner is not None:
            has_anyio_stack = any(
                "anyio" in frame["file"]
                or frame["function"] == "start_blocking_portal"
                for frame in stack
            )
            if owner["name"] == "asyncio-portal" and has_anyio_stack:
                match_reasons.append("anyio_portal_thread")
        loops.append(
            {
                "class": _qualified_name(type(loop)),
                "closed": bool(loop.is_closed()),
                "csock": _socket_record(getattr(loop, "_csock", None)),
                "label": loop_labels[identity],
                "owner_thread_ident": owner_ident,
                "owner_thread_name": (
                    owner["name"] if owner is not None else None
                ),
                "owner_thread_native_id": (
                    owner["native_id"] if owner is not None else None
                ),
                "ready_callbacks": ready,
                "ready_count": len(ready),
                "ready_error_code": ready_error,
                "running": bool(loop.is_running()),
                "scheduled_callbacks": scheduled,
                "scheduled_count": len(scheduled),
                "scheduled_error_code": scheduled_error,
                "scheduled_next_seconds": (
                    max(0.0, min(deadlines) - float(loop.time()))
                    if deadlines
                    else None
                ),
                "selector": _selector_record(
                    getattr(loop, "_selector", None)
                ),
                "ssock": _socket_record(getattr(loop, "_ssock", None)),
                "target_match_reasons": match_reasons,
                "tasks": tasks,
                "tasks_count": len(tasks),
                "tasks_error_code": task_error,
                "thread_stack": stack,
            }
        )
    return {
        "artifact_root_label": artifact_root.name,
        "event": "snapshot",
        "loops": loops,
        "observer_monotonic_ns": time.monotonic_ns(),
        "observer_wall_time_epoch": time.time(),
        "schema_version": SCHEMA_VERSION,
        "sequence": sequence,
        "surface": surface,
        "target_active": target_active,
        "target_nodeid": target_nodeid,
        "target_thread_ident": target_thread_ident,
        "target_thread_native_id": target_thread_native_id,
        "threads": threads,
        "trial": trial,
        "trigger": trigger,
    }


def _write_json_line(fd: int, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")
    offset = 0
    while offset < len(encoded):
        written = os.write(fd, encoded[offset:])
        if written <= 0:
            raise RuntimeError("observer output pipe accepted a short write")
        offset += written


class _Observer:
    def __init__(
        self,
        *,
        artifact_root: Path,
        command_fd: int,
        output_fd: int,
        repo: Path,
        surface: str,
        target_nodeid: str,
        trial: str,
    ) -> None:
        self.artifact_root = artifact_root
        self.command_fd = command_fd
        self.output_fd = output_fd
        self.repo = repo
        self.surface = surface
        self.target_nodeid = target_nodeid
        self.trial = trial
        self.loop_labels: dict[int, str] = {}
        self.state_lock = threading.Lock()
        self.target_active = False
        self.target_thread_ident: int | None = None
        self.target_thread_native_id: int | None = None
        self.thread = threading.Thread(
            target=self._run,
            name="EIR-005 Machine-State Observer",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()

    def target_started(self) -> None:
        with self.state_lock:
            self.target_active = True
            self.target_thread_ident = threading.get_ident()
            self.target_thread_native_id = threading.get_native_id()

    def target_finished(self) -> None:
        with self.state_lock:
            self.target_active = False

    def _snapshot(self, trigger: str, sequence: int) -> dict[str, Any]:
        with self.state_lock:
            target_active = self.target_active
            target_thread_ident = self.target_thread_ident
            target_thread_native_id = self.target_thread_native_id
        return capture_snapshot(
            artifact_root=self.artifact_root,
            repo=self.repo,
            surface=self.surface,
            target_active=target_active,
            target_nodeid=self.target_nodeid,
            target_thread_ident=target_thread_ident,
            target_thread_native_id=target_thread_native_id,
            trial=self.trial,
            trigger=trigger,
            sequence=sequence,
            loop_labels=self.loop_labels,
        )

    def _run(self) -> None:
        _write_json_line(
            self.output_fd,
            {
                "event": "observer_ready",
                "observer_monotonic_ns": time.monotonic_ns(),
                "observer_wall_time_epoch": time.time(),
                "schema_version": SCHEMA_VERSION,
                "surface": self.surface,
                "target_nodeid": self.target_nodeid,
                "trial": self.trial,
            },
        )
        buffer = b""
        expected_sequence = 1
        while True:
            chunk = os.read(self.command_fd, 4096)
            if not chunk:
                return
            buffer += chunk
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                try:
                    command = json.loads(raw.decode("utf-8"))
                    if (
                        not isinstance(command, dict)
                        or set(command)
                        != {"schema_version", "sequence", "trigger"}
                        or command["schema_version"] != SCHEMA_VERSION
                        or command["sequence"] != expected_sequence
                        or command["trigger"] not in TRIGGERS
                    ):
                        raise RuntimeError("observer command schema mismatch")
                    payload = self._snapshot(
                        str(command["trigger"]),
                        expected_sequence,
                    )
                except BaseException as exc:
                    payload = {
                        "error_type": type(exc).__name__,
                        "event": "snapshot_error",
                        "observer_monotonic_ns": time.monotonic_ns(),
                        "observer_wall_time_epoch": time.time(),
                        "schema_version": SCHEMA_VERSION,
                        "sequence": expected_sequence,
                        "surface": self.surface,
                        "target_nodeid": self.target_nodeid,
                        "trial": self.trial,
                    }
                _write_json_line(self.output_fd, payload)
                expected_sequence += 1


def pytest_configure(config) -> None:
    global _observer
    if _observer is not None:
        raise RuntimeError("EIR-005 observer configured twice")
    surface = os.environ.get(SURFACE_ENV)
    target = os.environ.get(TARGET_ENV)
    trial = os.environ.get(TRIAL_ENV)
    repo = os.environ.get(REPO_ENV)
    artifact_root = os.environ.get(ARTIFACT_ROOT_ENV)
    if surface not in {"A", "P"}:
        raise RuntimeError(f"{SURFACE_ENV} must be A or P")
    if not target or not trial or not repo or not artifact_root:
        raise RuntimeError("EIR-005 observer identity environment is incomplete")
    _observer = _Observer(
        artifact_root=Path(artifact_root),
        command_fd=_safe_fd(COMMAND_FD_ENV, readable=True),
        output_fd=_safe_fd(OUTPUT_FD_ENV, readable=False),
        repo=Path(repo),
        surface=surface,
        target_nodeid=target,
        trial=trial,
    )
    _observer.start()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logstart(nodeid, location) -> None:
    if _observer is not None and str(nodeid) == _observer.target_nodeid:
        _observer.target_started()


@pytest.hookimpl(trylast=True)
def pytest_runtest_logfinish(nodeid, location) -> None:
    if _observer is not None and str(nodeid) == _observer.target_nodeid:
        _observer.target_finished()
```
<!-- EIR005_PLUGIN_END -->

## Appendix C: Exact Independent Verifier

<!-- EIR005_VERIFIER_BEGIN -->
```python
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROTOCOL_ID = "eir005-machine-state-observer-v1"
OFFICIAL_ROOT = Path("/tmp/price-truth-tier-v3")
OFFICIAL_MANIFEST_SHA256 = (
    "ff189a4433b571c671ef7e4db82e63c94071d869e4ed48410f2a65c25e622f75"
)
DUMP_MARKER = b"Timeout (0:02:00)!"
TERMINAL_SUMMARY_RE = re.compile(
    rb"(?m)^=+ .+ in [0-9.]+s =+\r?$"
)
LATE_TRIGGERS = {"post_dump", "late", "pre_deadline"}
VECTOR_KEYS = (
    "selector_waiting",
    "self_pipe_open",
    "self_pipe_registered",
    "ready_callbacks_pending",
    "receive_bytes_pending",
    "send_queue_nonempty",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"JSONL row is not an object: {path}:{number}")
        values.append(value)
    return values


def _read_nodes(path: Path) -> list[str]:
    values = path.read_text(encoding="utf-8").splitlines()
    if values != sorted(set(values)) or not values:
        raise RuntimeError(f"node manifest is invalid: {path}")
    return values


def _artifact(preflight: dict[str, Any], role: str) -> Path:
    matches = [
        Path(item["path"])
        for item in preflight["artifacts"]
        if item["role"] == role
    ]
    if len(matches) != 1:
        raise RuntimeError(f"artifact role is not unique: {role}")
    return matches[0]


def _verify_preflight(path: Path) -> dict[str, Any]:
    preflight = _load_json(path)
    if (
        preflight.get("protocol_id") != PROTOCOL_ID
        or preflight.get("schema_version") != 1
    ):
        raise RuntimeError("observer preflight protocol changed")
    roles: set[str] = set()
    for item in preflight["artifacts"]:
        if set(item) != {"path", "role", "sha256"}:
            raise RuntimeError("observer artifact schema changed")
        artifact = Path(item["path"])
        role = item["role"]
        if (
            role in roles
            or not artifact.is_file()
            or _sha256(artifact) != item["sha256"]
        ):
            raise RuntimeError(f"observer artifact changed: {artifact}")
        roles.add(role)
    official_manifest = OFFICIAL_ROOT / "task0-v3-incomplete-manifest.sha256"
    if _sha256(official_manifest) != OFFICIAL_MANIFEST_SHA256:
        raise RuntimeError("official v3 manifest identity changed")
    return preflight


def _recompute_progress(
    path: Path,
) -> tuple[list[dict[str, Any]], str | None, bool]:
    events = _read_jsonl(path)
    expected_sequence = 1
    active: str | None = None
    balanced = True
    for event in events:
        required = {
            "child_monotonic_ns",
            "controller_received_monotonic_ns",
            "controller_received_wall_time_epoch",
            "event",
            "nodeid",
            "schema_version",
            "sequence",
            "transcript_offset",
        }
        if (
            set(event) != required
            or event["schema_version"] != 1
            or event["sequence"] != expected_sequence
            or event["event"] not in {"logstart", "logfinish"}
            or not isinstance(event["nodeid"], str)
        ):
            raise RuntimeError(f"progress schema changed: {path}")
        if event["event"] == "logstart":
            if active is not None:
                balanced = False
            active = event["nodeid"]
        else:
            if active != event["nodeid"]:
                balanced = False
            active = None
        expected_sequence += 1
    return events, active, balanced


def _validate_natural(
    *,
    expected_nodes: list[str],
    report_path: Path,
    returncode: int | None,
    transcript: bytes,
) -> tuple[bool, list[str]]:
    if (
        returncode not in {0, 1}
        or not TERMINAL_SUMMARY_RE.search(transcript)
        or not report_path.is_file()
    ):
        return False, []
    report = _load_json(report_path)
    required = {
        "collected_node_ids",
        "exitstatus",
        "nonpassing_node_ids",
        "schema_version",
        "seen_node_ids",
    }
    nonpassing = report.get("nonpassing_node_ids")
    valid = (
        set(report) == required
        and report["schema_version"] == 1
        and report["exitstatus"] == returncode
        and report["collected_node_ids"] == expected_nodes
        and report["seen_node_ids"] == expected_nodes
        and isinstance(nonpassing, list)
        and nonpassing == sorted(set(nonpassing))
        and all(node in expected_nodes for node in nonpassing)
        and (
            (returncode == 0 and not nonpassing)
            or (returncode == 1 and bool(nonpassing))
        )
    )
    return bool(valid), nonpassing if valid else []


def _recompute_attempt(
    *,
    expected_nodes: list[str],
    record_path: Path,
) -> dict[str, Any]:
    record = _load_json(record_path)
    trial = record_path.parent
    transcript_path = trial / "transcript.txt"
    progress_path = trial / "progress.jsonl"
    report_path = trial / "report.json"
    transcript = (
        transcript_path.read_bytes()
        if transcript_path.is_file()
        else b""
    )
    events, active, balanced = _recompute_progress(progress_path)
    target = record["target_nodeid"]
    target_starts = [
        event
        for event in events
        if event["event"] == "logstart" and event["nodeid"] == target
    ]
    target_finishes = [
        event
        for event in events
        if event["event"] == "logfinish" and event["nodeid"] == target
    ]
    deadline_events = [
        event
        for event in record["timeline"]
        if event["event"] == "deadline_breach"
    ]
    invalid_reason = record["invalid_reason"]
    classification = "invalid"
    dump_present = False
    if invalid_reason is None and len(deadline_events) == 1:
        offset = int(deadline_events[0]["transcript_offset"])
        dump_present = DUMP_MARKER in transcript[offset:]
        active_at_deadline = deadline_events[0]["active_nodeid"]
        if dump_present and record["cleanup_complete"]:
            classification = (
                "matching_stall"
                if active_at_deadline == target and target_starts
                else "terminated_nonstall_failure"
            )
    elif invalid_reason is None and not deadline_events:
        valid_natural, nonpassing = _validate_natural(
            expected_nodes=expected_nodes,
            report_path=report_path,
            returncode=record["process_returncode"],
            transcript=transcript,
        )
        if (
            valid_natural
            and balanced
            and active is None
            and len(events) == 2 * len(expected_nodes)
        ):
            classification = (
                "complete_natural"
                if len(target_starts) == 1 and len(target_finishes) == 1
                else "terminated_nonstall_failure"
            )
        else:
            nonpassing = []
    else:
        nonpassing = []
    if classification != record["classification"]:
        raise RuntimeError(
            f"controller classification differs: {record_path}"
        )
    return {
        "arm": record["arm"],
        "block": record["block"],
        "classification": classification,
        "cleanup_complete": bool(record["cleanup_complete"]),
        "dump_present": dump_present,
        "label": record["label"],
        "record_path": str(record_path),
        "replacement": bool(record["replacement"]),
        "slot": record["slot"],
        "surface": record["surface"],
        "target_nodeid": target,
    }


def _observer_events(path: Path) -> list[dict[str, Any]]:
    events = _read_jsonl(path)
    for event in events:
        if set(event) != {
            "controller_received_monotonic_ns",
            "controller_received_wall_time_epoch",
            "payload",
        }:
            raise RuntimeError(f"observer envelope changed: {path}")
        payload = event["payload"]
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("event")
            not in {"observer_ready", "snapshot", "snapshot_error"}
        ):
            raise RuntimeError(f"observer payload changed: {path}")
    return events


def _target_loop(
    snapshot: dict[str, Any],
    surface: str,
) -> dict[str, Any] | None:
    loops = snapshot["loops"]
    if surface == "A":
        matches = [
            loop
            for loop in loops
            if loop["owner_thread_ident"] == snapshot["target_thread_ident"]
        ]
    else:
        matches = []
        for loop in loops:
            stack = loop["thread_stack"]
            has_anyio = any(
                "anyio" in frame["file"]
                or frame["function"] == "start_blocking_portal"
                for frame in stack
            )
            if (
                loop["owner_thread_name"] == "asyncio-portal"
                and has_anyio
            ):
                matches.append(loop)
    return matches[0] if len(matches) == 1 else None


def _kernel_by_sequence(path: Path) -> dict[int, dict[str, Any]]:
    values = _read_jsonl(path)
    result: dict[int, dict[str, Any]] = {}
    for value in values:
        sequence = value["sample_sequence"]
        if sequence in result:
            raise RuntimeError(f"duplicate kernel sample sequence: {path}")
        result[sequence] = value
    return result


def _selector_waiting(loop: dict[str, Any]) -> bool:
    return any(
        frame["function"] == "select"
        and frame["file"].endswith("selectors.py")
        for frame in loop["thread_stack"]
    )


def _vector(
    *,
    kernel: dict[str, Any] | None,
    loop: dict[str, Any],
) -> dict[str, bool]:
    ssock = loop["ssock"]
    csock = loop["csock"]
    registered = any(
        registration["fd"] == ssock["fd"]
        and registration["events"] & 1
        for registration in loop["selector"]["registrations"]
    )
    receive_from_ss = False
    send_from_ss = False
    if kernel is not None:
        receive_from_ss = any(
            row["inode"] == ssock["inode"] and row["receive_queue"] > 0
            for row in kernel["ss_rows"]
        )
        send_from_ss = any(
            row["inode"] == csock["inode"] and row["send_queue"] > 0
            for row in kernel["ss_rows"]
        )
    return {
        "selector_waiting": _selector_waiting(loop),
        "self_pipe_open": bool(ssock["open"] and csock["open"]),
        "self_pipe_registered": registered,
        "ready_callbacks_pending": loop["ready_count"] > 0,
        "receive_bytes_pending": (
            isinstance(ssock["queued_bytes"], int)
            and ssock["queued_bytes"] > 0
        )
        or receive_from_ss,
        "send_queue_nonempty": send_from_ss,
    }


def _late_vectors(
    attempt: dict[str, Any],
) -> list[dict[str, bool]]:
    trial = Path(attempt["record_path"]).parent
    observer = _observer_events(trial / "observer.jsonl")
    kernels = _kernel_by_sequence(trial / "kernel.jsonl")
    vectors: list[dict[str, bool]] = []
    for envelope in observer:
        payload = envelope["payload"]
        if (
            payload["event"] != "snapshot"
            or payload["trigger"] not in LATE_TRIGGERS
        ):
            continue
        loop = _target_loop(payload, attempt["surface"])
        if loop is None:
            continue
        vectors.append(
            _vector(
                kernel=kernels.get(payload["sequence"]),
                loop=loop,
            )
        )
    return vectors


def _stable_late_vector(
    attempt: dict[str, Any],
) -> dict[str, bool] | None:
    vectors = _late_vectors(attempt)
    if len(vectors) < 2:
        return None
    normalized = [
        tuple(vector[key] for key in VECTOR_KEYS)
        for vector in vectors
    ]
    if len(set(normalized)) != 1:
        return None
    return vectors[0]


def _paired_block_qualifies(
    records: list[dict[str, Any]],
    *,
    controller_claim: bool | None = None,
) -> bool:
    del controller_claim
    return (
        len(records) == 2
        and {record["arm"] for record in records} == {"C", "O"}
        and all(
            record["classification"] == "matching_stall"
            for record in records
        )
    )


def _probe_paired() -> dict[str, bool]:
    control = {"arm": "C", "classification": "matching_stall"}
    observed = {"arm": "O", "classification": "matching_stall"}
    full = _paired_block_qualifies(
        [control, observed],
        controller_claim=False,
    )
    control_only = _paired_block_qualifies([control])
    observed_only = _paired_block_qualifies([observed])
    result_id, _ = _derive_result(
        blocks=[],
        controller_claim="O1",
    )
    if not full or control_only or observed_only or result_id != "O6":
        raise RuntimeError("paired-block verifier contract failed")
    return {
        "controller_claim_ignored": True,
        "full_block_qualifies": True,
        "one_arm_blocks_rejected": True,
    }


def _observer_perturbation(
    blocks: list[dict[str, Any]],
) -> bool:
    by_surface = {
        surface: sorted(
            [block for block in blocks if block["surface"] == surface],
            key=lambda block: block["block"],
        )
        for surface in ("A", "P")
    }
    for surface_blocks in by_surface.values():
        pattern_blocks: list[int] = []
        reverse = False
        for block in surface_blocks:
            records = block["records"]
            by_arm = {record["arm"]: record for record in records}
            if set(by_arm) != {"C", "O"}:
                continue
            if (
                by_arm["C"]["classification"] == "matching_stall"
                and by_arm["O"]["classification"] == "complete_natural"
            ):
                pattern_blocks.append(block["block"])
            if (
                by_arm["O"]["classification"] == "matching_stall"
                and by_arm["C"]["classification"] == "complete_natural"
            ):
                reverse = True
        adjacent = any(
            second == first + 1
            for first, second in zip(pattern_blocks, pattern_blocks[1:])
        )
        if adjacent and not reverse:
            return True
    return False


def _same_vector(vectors: list[dict[str, bool]]) -> dict[str, bool] | None:
    if len(vectors) < 2:
        return None
    tuples = [
        tuple(vector[key] for key in VECTOR_KEYS)
        for vector in vectors
    ]
    return vectors[0] if len(set(tuples)) == 1 else None


def _derive_result(
    *,
    blocks: list[dict[str, Any]],
    controller_claim: str | None,
) -> tuple[str, dict[str, Any]]:
    del controller_claim
    if _observer_perturbation(blocks):
        return "O4", {"reason": "observer_perturbation_supported"}
    qualifying = [
        block
        for block in blocks
        if _paired_block_qualifies(block["records"])
    ]
    stable_by_surface: dict[str, list[dict[str, bool]]] = {"A": [], "P": []}
    observed_stalls = 0
    for block in blocks:
        for attempt in block["records"]:
            if (
                attempt["arm"] == "O"
                and attempt["classification"] == "matching_stall"
            ):
                observed_stalls += 1
    for block in qualifying:
        observed = next(
            record
            for record in block["records"]
            if record["arm"] == "O"
        )
        stable = _stable_late_vector(observed)
        if stable is not None:
            stable_by_surface[block["surface"]].append(stable)
    shared = {
        surface: _same_vector(vectors)
        for surface, vectors in stable_by_surface.items()
    }
    if all(shared.values()):
        a_vector = shared["A"]
        p_vector = shared["P"]
        assert a_vector is not None and p_vector is not None
        same = all(a_vector[key] == p_vector[key] for key in VECTOR_KEYS)
        integrity_failure = (
            not a_vector["self_pipe_open"]
            or not a_vector["self_pipe_registered"]
        )
        pending = (
            a_vector["ready_callbacks_pending"]
            or a_vector["receive_bytes_pending"]
        )
        if same and a_vector["selector_waiting"] and integrity_failure:
            return "O2", {
                "reason": "shared_self_pipe_integrity_failure_supported",
                "vector": a_vector,
            }
        if (
            same
            and a_vector["selector_waiting"]
            and a_vector["self_pipe_open"]
            and a_vector["self_pipe_registered"]
            and pending
        ):
            return "O1", {
                "reason": "shared_pending_wakeup_state_supported",
                "vector": a_vector,
            }
        if not same:
            return "O3", {
                "A_vector": a_vector,
                "P_vector": p_vector,
                "reason": "surface_specific_state_supported",
            }
    if observed_stalls:
        return "O5", {
            "observed_stalls": observed_stalls,
            "reason": "matching_stalls_observed_but_mechanism_not_reduced",
        }
    return "O6", {"reason": "matching_window_not_obtained"}


def verify_campaign(
    *,
    campaign_summary_path: Path,
    output: Path,
    preflight_path: Path,
) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path)
    summary = _load_json(campaign_summary_path)
    if (
        summary.get("protocol_id") != PROTOCOL_ID
        or summary.get("schema_version") != 1
    ):
        raise RuntimeError("campaign summary protocol changed")
    root = Path(preflight["artifact_root"])
    recomputed: dict[str, dict[str, Any]] = {}
    for label in summary["attempt_labels"]:
        path = root / label / "record.json"
        record = _load_json(path)
        surface = record["surface"]
        recomputed[label] = _recompute_attempt(
            expected_nodes=_read_nodes(
                _artifact(preflight, f"{surface}_nodes")
            ),
            record_path=path,
        )
    admitted_blocks: list[dict[str, Any]] = []
    for row in preflight["schedule"]:
        surface = row["surface"]
        block_number = row["block"]
        if any(
            block["surface"] == surface
            and block["block"] == block_number
            for block in admitted_blocks
        ):
            continue
        records: list[dict[str, Any]] = []
        for arm in ("C", "O"):
            base = f"campaign-{surface}-b{block_number}-{arm.lower()}"
            if base not in recomputed:
                continue
            admitted = recomputed[base]
            replacement = f"{base}-replacement"
            if admitted["classification"] == "invalid":
                if replacement not in recomputed:
                    continue
                admitted = recomputed[replacement]
            records.append(admitted)
        if records:
            admitted_blocks.append(
                {
                    "block": block_number,
                    "records": records,
                    "surface": surface,
                }
            )
    result_id, result_detail = _derive_result(
        blocks=admitted_blocks,
        controller_claim=summary.get("result"),
    )
    payload = {
        "attempt_classifications": {
            label: record["classification"]
            for label, record in sorted(recomputed.items())
        },
        "blocks": [
            {
                "arms": [record["arm"] for record in block["records"]],
                "block": block["block"],
                "qualifies": _paired_block_qualifies(block["records"]),
                "surface": block["surface"],
            }
            for block in admitted_blocks
        ],
        "controller_claim_ignored": True,
        "protocol_id": PROTOCOL_ID,
        "result_detail": result_detail,
        "result_id": result_id,
        "schema_version": 1,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe-paired")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--campaign-summary", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--preflight", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "probe-paired":
        result = _probe_paired()
    else:
        result = verify_campaign(
            campaign_summary_path=args.campaign_summary,
            output=args.output,
            preflight_path=args.preflight,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
<!-- EIR005_VERIFIER_END -->

## Appendix D: Exact Schedule

<!-- EIR005_SCHEDULE_BEGIN -->
```json
[
  {"arm": "C", "block": 1, "slot": 1, "surface": "A"},
  {"arm": "O", "block": 1, "slot": 2, "surface": "A"},
  {"arm": "O", "block": 1, "slot": 1, "surface": "P"},
  {"arm": "C", "block": 1, "slot": 2, "surface": "P"},
  {"arm": "O", "block": 2, "slot": 1, "surface": "A"},
  {"arm": "C", "block": 2, "slot": 2, "surface": "A"},
  {"arm": "C", "block": 2, "slot": 1, "surface": "P"},
  {"arm": "O", "block": 2, "slot": 2, "surface": "P"},
  {"arm": "C", "block": 3, "slot": 1, "surface": "A"},
  {"arm": "O", "block": 3, "slot": 2, "surface": "A"},
  {"arm": "O", "block": 3, "slot": 1, "surface": "P"},
  {"arm": "C", "block": 3, "slot": 2, "surface": "P"},
  {"arm": "O", "block": 4, "slot": 1, "surface": "A"},
  {"arm": "C", "block": 4, "slot": 2, "surface": "A"},
  {"arm": "C", "block": 4, "slot": 1, "surface": "P"},
  {"arm": "O", "block": 4, "slot": 2, "surface": "P"}
]
```
<!-- EIR005_SCHEDULE_END -->

## Appendix E: Exact Probe Fixtures

### `probes/probe_pass.py`

<!-- EIR005_PROBE_PASS_BEGIN -->
```python
import time


def test_probe_pass() -> None:
    time.sleep(0.2)
    assert True
```
<!-- EIR005_PROBE_PASS_END -->

### `probes/probe_interruptible.py`

<!-- EIR005_PROBE_INTERRUPTIBLE_BEGIN -->
```python
import signal
import time


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def test_probe_interruptible() -> None:
    signal.signal(signal.SIGINT, _raise_keyboard_interrupt)
    time.sleep(30)
```
<!-- EIR005_PROBE_INTERRUPTIBLE_END -->

### `probes/probe_ignore_sigint.py`

<!-- EIR005_PROBE_IGNORE_BEGIN -->
```python
import signal
import subprocess
import sys
import time


def test_probe_ignore_sigint() -> None:
    subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import signal,time;"
                "signal.signal(signal.SIGINT,signal.SIG_IGN);"
                "time.sleep(30)"
            ),
        ]
    )
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    time.sleep(30)
```
<!-- EIR005_PROBE_IGNORE_END -->

### `probes/probe.nodes`

<!-- EIR005_PROBE_NODES_BEGIN -->
```text
probes/probe_pass.py::test_probe_pass
```
<!-- EIR005_PROBE_NODES_END -->

## Appendix F: Exact Mutation Diffs

The eight portable unified diffs are the exact one-hunk changes listed in
Task 2. Review and execution regenerate them with the fixed
`pristine/eir005_observer_*.py` and `mutated/eir005_observer_*.py` labels and
compare the SHA values in the mutation table before running each owning
probe. `<!-- EIR005_DIFF_CONTEXT_BLANK -->` encodes one unified-diff context
line containing a single space; the extraction command restores that byte so
the tracked Markdown has no trailing whitespace.

### M1

<!-- EIR005_M1_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_plugin.py
+++ mutated/eir005_observer_plugin.py
@@ -181,7 +181,7 @@
         fcntl.ioctl(fd, termios.FIONREAD, value, True)
     except OSError:
         return None
-    return max(0, int(value[0]))
+    return 0
<!-- EIR005_DIFF_CONTEXT_BLANK -->
<!-- EIR005_DIFF_CONTEXT_BLANK -->
 def _socket_record(sock: Any) -> dict[str, Any]:
```
<!-- EIR005_M1_DIFF_END -->

### M2

<!-- EIR005_M2_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_plugin.py
+++ mutated/eir005_observer_plugin.py
@@ -245,6 +245,7 @@
             )
     except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
         error_code = "selector_snapshot_race"
+    registrations = []
     registrations.sort(
         key=lambda item: (
             item["fd"],
```
<!-- EIR005_M2_DIFF_END -->

### M3

<!-- EIR005_M3_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_plugin.py
+++ mutated/eir005_observer_plugin.py
@@ -309,7 +309,7 @@
                 loops.append(value)
         except (ReferenceError, RuntimeError, TypeError):
             continue
-    return loops
+    return loops[:1]
<!-- EIR005_DIFF_CONTEXT_BLANK -->
<!-- EIR005_DIFF_CONTEXT_BLANK -->
 def capture_snapshot(
```
<!-- EIR005_M3_DIFF_END -->

### M4

<!-- EIR005_M4_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_plugin.py
+++ mutated/eir005_observer_plugin.py
@@ -66,6 +66,7 @@
<!-- EIR005_DIFF_CONTEXT_BLANK -->
<!-- EIR005_DIFF_CONTEXT_BLANK -->
 def _qualified_name(value: Any) -> str:
+    return repr(value)
     if value is None:
         return "builtins.NoneType"
     candidate = value
```
<!-- EIR005_M4_DIFF_END -->

### M5

<!-- EIR005_M5_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_verifier.py
+++ mutated/eir005_observer_verifier.py
@@ -500,7 +500,8 @@
     blocks: list[dict[str, Any]],
     controller_claim: str | None,
 ) -> tuple[str, dict[str, Any]]:
-    del controller_claim
+    if controller_claim is not None:
+        return controller_claim, {"reason": "trusted_controller_claim"}
     if _observer_perturbation(blocks):
         return "O4", {"reason": "observer_perturbation_supported"}
     qualifying = [
```
<!-- EIR005_M5_DIFF_END -->

### M6

<!-- EIR005_M6_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_verifier.py
+++ mutated/eir005_observer_verifier.py
@@ -417,8 +417,8 @@
 ) -> bool:
     del controller_claim
     return (
-        len(records) == 2
-        and {record["arm"] for record in records} == {"C", "O"}
+        len(records) >= 1
+        and {record["arm"] for record in records} <= {"C", "O"}
         and all(
             record["classification"] == "matching_stall"
             for record in records
```
<!-- EIR005_M6_DIFF_END -->

### M7

<!-- EIR005_M7_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_controller.py
+++ mutated/eir005_observer_controller.py
@@ -463,7 +463,7 @@
         text=True,
     )
     if result.returncode != 0:
-        raise RuntimeError("ss_queue_capability_unavailable")
+        return []
     rows: list[dict[str, Any]] = []
     for line in result.stdout.splitlines():
         inode_match = TARGET_RE.search(line)
```
<!-- EIR005_M7_DIFF_END -->

### M8

<!-- EIR005_M8_DIFF_BEGIN -->
```diff
--- pristine/eir005_observer_controller.py
+++ mutated/eir005_observer_controller.py
@@ -190,6 +190,7 @@
<!-- EIR005_DIFF_CONTEXT_BLANK -->
<!-- EIR005_DIFF_CONTEXT_BLANK -->
 def _assert_artifact_root_safe(root: Path) -> None:
+    return
     resolved = root.resolve()
     if resolved == OFFICIAL_V3_ROOT or OFFICIAL_V3_ROOT in resolved.parents:
         raise RuntimeError("observer artifacts may not use the official v3 root")
```
<!-- EIR005_M8_DIFF_END -->
