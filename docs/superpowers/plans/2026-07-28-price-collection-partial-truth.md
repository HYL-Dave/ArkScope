# Price Collection Partial-Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: DETERMINISTIC TIER RUNNER PLAN REVIEW NEXT**

**Goal:** Make direct-local price collection report per-ticker unresolved
completed-day targets as structural partial truth from collector through
Settings, without changing Coverage v2, provider adapters, schemas, request
policy, or production data.

**Architecture:** The existing collector keeps each ticker's original
zero-bar target dates, inserts fetched rows under the existing short write
boundary, and then performs one parameterized day-presence query against those
same identities. One derived issue set owns collector status, provider
telemetry, the sanitized child payload, scheduler durable state, and the
bounded frontend explanation. Three-value audit tables project semantic
partial to `failed`; structured counts and ticker IDs preserve successful
sibling facts.

**Tech Stack:** Python 3.10, SQLite, pytest, subprocess JSON boundaries,
FastAPI scheduler state, React 18, TypeScript 5.9, i18next, Vitest 4/jsdom, and
the existing TypeScript-AST visible-literal scanner.

---

## 1. Authority And Review State

1. Product authority:
   `docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md`.
2. Sequence and follow-up authority:
   `docs/design/PROJECT_PRIORITY_MAP.md`.
3. Small-issue authority:
   `docs/design/ENGINEERING_ISSUE_REGISTER.md`; this contract violation remains
   an active priority-map slice rather than an EIR item.
4. Restart product base:
   `e6d4b7fac7e91c59e855a7f543caac4f57094d86`.
5. Reviewed spec tip:
   `1a695141` on isolated branch `codex/price-collection-truth`.
6. Reviewed deterministic-runner design tip:
   `1d08a9f30a87066ea0a2e3b3274a22210cdfa57d`.

Independent full-document re-review returned GREEN with zero findings. It
verified the local day-presence rule, the three separately named
anti-false-partial shapes, the fixed-26-slot mutation, the local fail-closed
audit projection, and the explicit non-convergence of normalized-news audit
behavior.

Independent plan review cleared reviewed plan tip `9d1e648a` after the exact
frontend node identity was aligned with its enclosing Vitest `describe` and
the load-bearing 26-slot mutation gained a reviewable-diff evidence pin. Task
0 then stopped under Stop Condition 11 because the required full-suite
baseline hung reproducibly at
`tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint`.

The independently reviewed query-route harness slice merged on `master` at
`2edf12e1`. A later bounded causal diagnosis merged at `e6d4b7fa` after its
independent raw reconstruction returned GREEN and selected
`V6 ambient_or_machine_state_dominates`. The tested SEC collection,
route-mount predecessor, and direct `edgar` import factors were not necessary
for the observed stall; no causal product, dependency, import, or additional
TestClient seam was selected. `EIR-005` owns the unresolved machine-state
behavior.

This branch is rebased onto `e6d4b7fa` while preserving every reviewed price,
harness, and diagnosis decision-log entry. The old blocked runs remain
diagnostic evidence, not baselines. The product design, node/resource ledgers,
and predicted final hashes are unchanged. The tiered admission mechanism is
retained, but deterministic runner design `1d08a9f3` replaces its invalid
manual orchestration. Stop Condition 11 remains binding at tier granularity.
Product RED remains unauthorized until focused review clears the exact runner
source, probes, mutation packet, commands, and this amended plan, and Task 0
closes with a complete tiered baseline.

Focused review of `7844429a..5fecce65` returned GREEN with zero findings and
authorized the historical Task 0 restart. That attempt reproduced every
canonical and focused baseline exactly, then stopped at
`tests/test_api.py::TestHealth::test_status`. Its post-dump partial transcript
remains inadmissible. The causal diagnosis later demonstrated that betting on
a clean monolithic window is not a verification strategy. This amendment
therefore resets Task 0 rather than reusing either historical partial run.

The main worktree's untracked files remain user-owned and out of scope:

```text
docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md
docs/design/SCRIPTS_RETIREMENT_DECISION.md
```

They must not be copied, edited, staged, or used as implementation authority.

## 2. Grounded Baseline

All collection values below were independently reproduced on clean
`1a695141`. The merged harness changes only `tests/test_agents.py` and leaves
all four canonical collection streams byte-identical; merged verification on
restart base `e6d4b7fa` reproduced backend full `4722/fcdb1b7d...`. The
earlier harness merge separately reproduced agents `31/78d7cdbe...` and owned
routes `2/5e1e62ac...`. Normalized node IDs, not
an absolute environment-dependent pass/fail total, are the accounting
authority.

| Gate | Baseline |
|---|---|
| Backend full collection | `4722` nodes; SHA-256 `fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0` |
| Backend focused collection | `151` nodes; SHA-256 `3c07d208ced889497521a779ae46dd88403277c34055c00ba9fd74ada08da428` |
| Backend focused composition | direct `63`, worker `4`, scheduler `84` |
| Backend focused run | `151 passed` |
| Frontend full collection | `96` files / `1074` nodes; SHA-256 `e322e7a51e83eedb8b3c7b1fd99e6033f496031968c1a2cb3f59974bfd994f47` |
| Frontend focused collection | `3` files / `86` nodes; SHA-256 `739385b104c147744e7421f030e3fc628b2d99a981406c9c13aeb25c2a70a479` |
| Frontend focused composition | mounted Settings `36`, resources `14`, display `36` |
| Per-locale resources | Settings `704`, Explore `380`, total `1783` |
| Visible-literal scanner, twice | `36 / 20 / 0 / 20`, scope `src/**` |
| Tool surfaces | central `53`, OpenAI `54`, Anthropic `54` |
| no-PG runtime smoke | `23/23`, `ok=true`, `pg_attempts=[]` |

The root `node_modules` symlink and empty ignored `data/` directory are
worktree-only test prerequisites. They are not product input and must never be
replaced with the production `data/` tree. The known backend non-green family
is EIR-002; Task 0 must derive its complete tiered-protocol node-ID set before
product edits. No historical failure count is an allowlist.

### 2.1 Canonical collection recipes

Backend full:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-be-full.nodes \
  | sha256sum
wc -l /tmp/price-truth-be-full.nodes
```

Backend focused:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_market_data_direct.py \
  tests/test_prices_runtime.py \
  tests/test_data_scheduler.py \
  | sed -n '/^tests\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-be-focused.nodes \
  | sha256sum
wc -l /tmp/price-truth-be-focused.nodes
cut -d: -f1 /tmp/price-truth-be-focused.nodes | sort | uniq -c
```

Frontend full, from `apps/arkscope-web`:

```bash
npx vitest list --json \
  | jq -r '.[] | [.file,.name] | @tsv' \
  | sed "s#$(pwd)/##" \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-fe-full.nodes \
  | sha256sum
wc -l /tmp/price-truth-fe-full.nodes
cut -f1 /tmp/price-truth-fe-full.nodes | sort -u | wc -l
```

Frontend focused is derived from the full normalized stream:

```bash
awk -F '\t' \
  '$1=="src/SettingsProviderConfig.test.ts" || \
   $1=="src/i18n/resources.test.ts" || \
   $1=="src/marketDataDisplay.test.ts"' \
  /tmp/price-truth-fe-full.nodes \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-fe-focused.nodes \
  | sha256sum
wc -l /tmp/price-truth-fe-focused.nodes
cut -f1 /tmp/price-truth-fe-focused.nodes | sort | uniq -c
```

Vitest 4 treats the token after `--json` as an optional output filename. Do
not append test paths after `--json`; generate the full JSON stream first and
filter the normalized TSV.

### 2.2 Deterministic tiered backend protocol

Protocol ID: `price-truth-tier-v2`.

Use one fresh artifact root and preserve it through the complete base/tip
comparison:

```bash
test -d /tmp/price-truth-tier-v1
export PRICE_TRUTH_TIER_ROOT=/tmp/price-truth-tier-v2
test ! -e "$PRICE_TRUTH_TIER_ROOT"
mkdir -p "$PRICE_TRUTH_TIER_ROOT"
cp /tmp/price-truth-be-full.nodes "$PRICE_TRUTH_TIER_ROOT/base.nodes"
```

The v1 root is frozen invalid evidence. The `test -d` command proves the root
still exists without reading its contents; no v2 runner, probe, mutation, or
runtime command may read its contents, write to it, move it, or delete it.

Create `$PRICE_TRUTH_TIER_ROOT/build_tiers.py` from this exact scratch source.
It is an evidence artifact, not tracked product or test code:

```python
from collections import Counter
import os
from pathlib import Path


ROOT = Path(os.environ["PRICE_TRUTH_TIER_ROOT"])
TIER_COUNT = 8

nodes = ROOT.joinpath("base.nodes").read_text(encoding="utf-8").splitlines()
if nodes != sorted(set(nodes)):
    raise SystemExit("base.nodes must be sorted and unique")

counts = Counter(node.split("::", 1)[0] for node in nodes)
tiers: list[list[tuple[str, int]]] = [[] for _ in range(TIER_COUNT)]
loads = [0] * TIER_COUNT

for path, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
    tier = min(range(TIER_COUNT), key=lambda index: (loads[index], index))
    tiers[tier].append((path, count))
    loads[tier] += count

map_lines: list[str] = []
for tier, members in enumerate(tiers):
    ordered = sorted(members)
    ROOT.joinpath(f"T{tier}.paths").write_text(
        "".join(f"{path}\n" for path, _ in ordered),
        encoding="utf-8",
    )
    map_lines.extend(f"T{tier}\t{count}\t{path}" for path, count in ordered)

ROOT.joinpath("tier-map.tsv").write_text(
    "".join(f"{line}\n" for line in map_lines),
    encoding="utf-8",
)

for tier, members in enumerate(tiers):
    print(f"T{tier}\tfiles={len(members)}\tnodes={loads[tier]}")
```

Run and pin it:

```bash
sha256sum "$PRICE_TRUTH_TIER_ROOT/build_tiers.py"
/home/hyl/.virtualenvs/llm_app/bin/python \
  "$PRICE_TRUTH_TIER_ROOT/build_tiers.py"
sha256sum "$PRICE_TRUTH_TIER_ROOT/tier-map.tsv"
wc -l "$PRICE_TRUTH_TIER_ROOT/base.nodes" \
  "$PRICE_TRUTH_TIER_ROOT/tier-map.tsv" \
  "$PRICE_TRUTH_TIER_ROOT"/T?.paths
```

Expected scratch-source SHA-256:
`0f0421f86f46265427914bce7bbede694beaa8d04b5d3b2ea9562d27cd7c8d9c`.
Expected base map SHA-256:
`3d7adb7e1db7b92b25b3ae83fe56ec182c6b070802cd45d95e091c673115994a`.
Expected base distribution:

| Tier | Files | Nodes |
|---|---:|---:|
| T0 | 32 | 591 |
| T1 | 32 | 591 |
| T2 | 31 | 590 |
| T3 | 31 | 590 |
| T4 | 32 | 590 |
| T5 | 31 | 590 |
| T6 | 32 | 590 |
| T7 | 32 | 590 |

Under the locked `+17/-0` ledger, the same map predicts tip loads
`591/591/600/590/590/590/590/597`: scheduler `+6` and worker `+4` remain in
T2, while direct collector `+7` remains in T7. Do not rebalance the tip.

For a side named `SIDE` (`base` or `tip`), collect every tier using the same
immutable path files:

```bash
set -o pipefail
: "${SIDE:?set SIDE to base or tip}"
case "$SIDE" in
  base|tip) ;;
  *) printf 'invalid SIDE: %s\n' "$SIDE" >&2; exit 2 ;;
esac
for tier in 0 1 2 3 4 5 6 7; do
  mapfile -t paths < "$PRICE_TRUTH_TIER_ROOT/T${tier}.paths"
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    "${paths[@]}" \
    | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
    | LC_ALL=C sort \
    > "$PRICE_TRUTH_TIER_ROOT/${SIDE}-T${tier}.nodes"
done

cat "$PRICE_TRUTH_TIER_ROOT"/"$SIDE"-T?.nodes \
  | LC_ALL=C sort \
  > "$PRICE_TRUTH_TIER_ROOT/${SIDE}-tier-union.nodes"
cat "$PRICE_TRUTH_TIER_ROOT"/"$SIDE"-T?.nodes | wc -l
cat "$PRICE_TRUTH_TIER_ROOT"/"$SIDE"-T?.nodes | LC_ALL=C sort -u | wc -l
cmp "$PRICE_TRUTH_TIER_ROOT/${SIDE}.nodes" \
  "$PRICE_TRUTH_TIER_ROOT/${SIDE}-tier-union.nodes"
```

Base must report `4722`, `4722`, and byte equality with
`fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0`.
Tip must report `4739`, `4739`, and byte equality with the canonical tip
collection. Before tip collection, prove that its unique file paths equal the
253 mapped paths; a new or missing test file is not assigned ad hoc:

```bash
cat "$PRICE_TRUTH_TIER_ROOT"/T?.paths \
  | LC_ALL=C sort -u \
  > "$PRICE_TRUTH_TIER_ROOT/mapped.paths"
cut -d: -f1 "$PRICE_TRUTH_TIER_ROOT/tip.nodes" \
  | LC_ALL=C sort -u \
  > "$PRICE_TRUTH_TIER_ROOT/tip.paths"
cmp "$PRICE_TRUTH_TIER_ROOT/mapped.paths" \
  "$PRICE_TRUTH_TIER_ROOT/tip.paths"
```

Canonical collection contains node IDs with embedded spaces, so transcript
token parsing is forbidden. Create
`$PRICE_TRUTH_TIER_ROOT/arkscope_price_truth_tier_reporter.py` from this exact
stdlib-only scratch plugin:

```python
import json
import os
from pathlib import Path


_REPORT_VALUE = os.environ.get("PRICE_TRUTH_TIER_REPORT")
if not _REPORT_VALUE:
    raise RuntimeError("PRICE_TRUTH_TIER_REPORT is required")

_REPORT_PATH = Path(_REPORT_VALUE)
_collected_node_ids: list[str] = []
_seen_node_ids: set[str] = set()
_nonpassing_node_ids: set[str] = set()


def pytest_collection_finish(session) -> None:
    global _collected_node_ids
    _collected_node_ids = sorted(item.nodeid for item in session.items)


def pytest_runtest_logreport(report) -> None:
    _seen_node_ids.add(report.nodeid)
    if report.failed:
        _nonpassing_node_ids.add(report.nodeid)


def pytest_sessionfinish(session, exitstatus) -> None:
    payload = {
        "schema_version": 1,
        "exitstatus": int(exitstatus),
        "collected_node_ids": _collected_node_ids,
        "seen_node_ids": sorted(_seen_node_ids),
        "nonpassing_node_ids": sorted(_nonpassing_node_ids),
    }
    temporary = _REPORT_PATH.with_suffix(_REPORT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(_REPORT_PATH)
```

Expected reporter SHA-256:
`09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928`.
The frozen v1 reporter probe already proves that this exact blob preserves a
failing parametrized node ID containing spaces. Record that prior artifact's
identity rather than rerunning or changing the reporter. The v2 collection
probe below independently proves that adding the progress plugin changes no
collected node.

Runtime control is owned by one dual-role, standard-library Python module.
Extract Appendix A from this plan into the fresh artifact root; do not copy the
already invalid v1 runner or recreate the source from prose:

```bash
export PRICE_TRUTH_PLAN="$PWD/docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md"
awk '
  /^<!-- PRICE_TRUTH_RUNNER_V2_BEGIN -->$/ { emit=1; next }
  /^<!-- PRICE_TRUTH_RUNNER_V2_END -->$/ { emit=0 }
  emit && $0 != "```python" && $0 != "```" { print }
' "$PRICE_TRUTH_PLAN" \
  > "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py"

sha256sum "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py"
/home/hyl/.virtualenvs/llm_app/bin/python -m py_compile \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py"
```

Expected runner SHA-256:
`35cda547ac8b1afaba1231d56cb04d703a284cdd81de978397ce7887ac51339e`.
Appendix extraction, not a nearby working copy, is the runtime authority.
`PRICE_TRUTH_PROGRESS_FD` is checked only by `pytest_configure()` when pytest
loads this file as a plugin. Module execution for `prepare-preflight`,
`probe-suite`, `run-side`, and `run-diagnostic` must not require that
descriptor.

Create these exact scratch probe fixtures under
`$PRICE_TRUTH_TIER_ROOT`. They are evidence artifacts, not repository tests:

`probe_pass.py`:

```python
def test_probe_pass():
    assert True
```

`probe_interruptible.py`:

```python
import signal
import time


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def test_probe_interruptible():
    signal.signal(signal.SIGINT, _raise_keyboard_interrupt)
    time.sleep(30)
```

`probe_ignore_sigint.py`:

```python
import signal
import subprocess
import sys
import time


def test_probe_ignore_sigint():
    subprocess.Popen([
        sys.executable,
        "-c",
        (
            "import signal,time;"
            "signal.signal(signal.SIGINT,signal.SIG_IGN);"
            "time.sleep(30)"
        ),
    ])
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    time.sleep(30)
```

`probe.nodes`:

```text
probe_pass.py::test_probe_pass
```

`probe-tier-map.tsv`:

```text
T0	1	probe_pass.py
```

Require these exact source identities:

| Artifact | SHA-256 |
|---|---|
| `probe_pass.py` | `f284d6dd93c54cd5050f1964d62fb75498e9e1be777e20709d1a175423c1f06e` |
| `probe_interruptible.py` | `47ce71581932a8023ae57ac7b975d67a2040cae18f7e5b44f5a72ca804a5d402` |
| `probe_ignore_sigint.py` | `cd029264a3224bc4a2e6928185b6ff6f1e34e56d9406974310eb5715cbcd7942` |
| `probe.nodes` | `85e427423e6a22513ced4f286045ab33023ba6f0d3e0f3344f8490c4faf92537` |
| `probe-tier-map.tsv` | `fe3ecde0a8261879529289f72f433e1cf0c747e59f0dbfec1f0b5e78d1d525f4` |

The same module creates a closed preflight from current immutable artifacts.
Its preflight creation is not self-authenticating: first compare the runner,
reporter, builder, fixture, canonical-manifest, and map hashes with this plan.
The subsequent preflight rejects accidental drift, relocation, interpreter,
dependency, PATH, or Git-identity changes before child launch.

Before any base runtime, execute the mandatory probes:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  prepare-preflight \
  --artifact-root "$PRICE_TRUTH_TIER_ROOT" \
  --repo "$PWD" \
  --side probe

sha256sum "$PRICE_TRUTH_TIER_ROOT/probe-preflight.json"

/home/hyl/.virtualenvs/llm_app/bin/python \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  probe-suite \
  --preflight "$PRICE_TRUTH_TIER_ROOT/probe-preflight.json"

jq -e '
  .protocol_id == "price-truth-tier-v2"
  and .checks == {
    "collection_identity": true,
    "fd_fail_closed": true,
    "pass": true,
    "sigint": true,
    "sigkill": true
  }
' "$PRICE_TRUTH_TIER_ROOT/probe-summary.json"
sha256sum "$PRICE_TRUTH_TIER_ROOT/probe-summary.json"
```

Expected summary SHA-256:
`47564c644c95e54007d67e4b08ddaeb35ed8370f858b3f004f00f54ef9e1ad48`.
PID, timestamp, transcript, progress, record, and preflight hashes are
environment observations and must be recorded rather than predicted. Require
the following record facts:

| Probe | Required record |
|---|---|
| `probe-fast-pass` | `complete_pass`, two progress events, pipe EOF, no signal |
| `probe-sigint` | `unresolved_stall`, current-window dump, SIGINT, no SIGKILL |
| `probe-sigkill` | `unresolved_stall`, current-window dump, SIGINT then SIGKILL |
| collect control/plugin | identical one-node `collected_node_ids`, plugin emits zero runtime events |
| missing/garbled FD | nonzero pytest exit and transcript names `PRICE_TRUTH_PROGRESS_FD` |

Probe mode alone uses dump/deadline/grace `2/3/1` seconds. Runtime mode has
immutable `120/150/10` values and accepts no CLI override.

#### Runner mutation packet

Run every mutation in its own fresh root. First construct M1-M5 from the
reviewed pristine bytes:

```bash
for number in 1 2 3 4 5; do
  MUTATION_ROOT="/tmp/price-truth-tier-v2-m${number}"
  test ! -e "$MUTATION_ROOT"
  mkdir "$MUTATION_ROOT"
  cp \
    "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
    "$PRICE_TRUTH_TIER_ROOT/arkscope_price_truth_tier_reporter.py" \
    "$PRICE_TRUTH_TIER_ROOT/build_tiers.py" \
    "$PRICE_TRUTH_TIER_ROOT/probe.nodes" \
    "$PRICE_TRUTH_TIER_ROOT/probe-tier-map.tsv" \
    "$PRICE_TRUTH_TIER_ROOT/probe_pass.py" \
    "$PRICE_TRUTH_TIER_ROOT/probe_interruptible.py" \
    "$PRICE_TRUTH_TIER_ROOT/probe_ignore_sigint.py" \
    "$MUTATION_ROOT/"
done
```

Apply each exact patch below with `apply_patch` to these fixed paths:

| Mutation | Patched artifact |
|---|---|
| M1 | `/tmp/price-truth-tier-v2-m1/price_truth_tier_runner.py` |
| M2 | `/tmp/price-truth-tier-v2-m2/price_truth_tier_runner.py` |
| M3 | `/tmp/price-truth-tier-v2-m3/probe_interruptible.py` |
| M4 | `/tmp/price-truth-tier-v2-m4/price_truth_tier_runner.py` |

Then capture each diff against the pristine artifact; a source diff must exit
exactly `1`:

```bash
diff -u \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  /tmp/price-truth-tier-v2-m1/price_truth_tier_runner.py \
  > /tmp/price-truth-tier-v2-m1/mutation.diff \
  || test "$?" -eq 1
diff -u \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  /tmp/price-truth-tier-v2-m2/price_truth_tier_runner.py \
  > /tmp/price-truth-tier-v2-m2/mutation.diff \
  || test "$?" -eq 1
diff -u \
  "$PRICE_TRUTH_TIER_ROOT/probe_interruptible.py" \
  /tmp/price-truth-tier-v2-m3/probe_interruptible.py \
  > /tmp/price-truth-tier-v2-m3/mutation.diff \
  || test "$?" -eq 1
diff -u \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  /tmp/price-truth-tier-v2-m4/price_truth_tier_runner.py \
  > /tmp/price-truth-tier-v2-m4/mutation.diff \
  || test "$?" -eq 1
sha256sum /tmp/price-truth-tier-v2-m{1,2,3,4}/mutation.diff
```

Prepare each probe preflight only after its own mutation is present:

```bash
for number in 1 2 3 4 5; do
  MUTATION_ROOT="/tmp/price-truth-tier-v2-m${number}"
  /home/hyl/.virtualenvs/llm_app/bin/python \
    "$MUTATION_ROOT/price_truth_tier_runner.py" \
    prepare-preflight \
    --artifact-root "$MUTATION_ROOT" \
    --repo "$PWD" \
    --side probe
done
```

For M1-M4, preserve expected nonzero exits mechanically:

```bash
sha256sum /tmp/price-truth-tier-v2-m4/price_truth_tier_runner.py \
  > /tmp/price-truth-tier-v2-m4/runner-before.sha256

for number in 1 2 3 4; do
  MUTATION_ROOT="/tmp/price-truth-tier-v2-m${number}"
  set +e
  /home/hyl/.virtualenvs/llm_app/bin/python \
    "$MUTATION_ROOT/price_truth_tier_runner.py" \
    probe-suite \
    --preflight "$MUTATION_ROOT/probe-preflight.json" \
    > "$MUTATION_ROOT/mutation.stdout" \
    2> "$MUTATION_ROOT/mutation.stderr"
  rc="$?"
  set -e
  printf '%s\n' "$rc" > "$MUTATION_ROOT/exit-code.txt"
  test "$rc" -ne 0
done

sha256sum /tmp/price-truth-tier-v2-m4/price_truth_tier_runner.py \
  > /tmp/price-truth-tier-v2-m4/runner-after.sha256
diff -u \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  /tmp/price-truth-tier-v2-m4/price_truth_tier_runner.py \
  > /tmp/price-truth-tier-v2-m4/runtime-drift.diff \
  || test "$?" -eq 1
```

The exact mutations and owning assertions are:

1. **M1 - delayed progress cannot revive an expired window.**

   ```diff
                        events = selector.select(timeout=min(remaining, 0.1))
   +                    if mode == "probe" and events:
   +                        time.sleep(PROBE_BOUNDS["deadline_seconds"] + 1)
                        deadline_due = time.monotonic_ns() >= deadline_ns
   ```

   `probe-fast-pass/record.json` must be `invalid` with
   `invalid_reason=deadline_breach_without_dump`, `progress_count=0`,
   `active_nodeid_at_end=null`, and `deadline_phase=pre_first_node`. This is
   the load-bearing proof that a pipe event already waiting when the parent
   resumes after the old deadline cannot start a new full window.

   ```bash
   jq -e '
     .outcome == "invalid"
     and .invalid_reason == "deadline_breach_without_dump"
     and .progress_count == 0
     and .active_nodeid_at_end == null
     and .dump_present == false
     and .deadline_phase == "pre_first_node"
   ' /tmp/price-truth-tier-v2-m1/probe-fast-pass/record.json
   ```

2. **M2 - no current-window dump.**

   ```diff
    PROBE_BOUNDS = {
   -    "dump_seconds": 2,
   +    "dump_seconds": 20,
        "deadline_seconds": 3,
   ```

   Run `probe-suite`. Both sleeping records must be `invalid` with
   `invalid_reason=deadline_breach_without_dump` and `dump_present=false`.
   Neither may be admitted as `unresolved_stall`.

   ```bash
   jq -e '
     .outcome == "invalid"
     and .invalid_reason == "deadline_breach_without_dump"
     and .dump_present == false
   ' \
     /tmp/price-truth-tier-v2-m2/probe-sigint/record.json \
     /tmp/price-truth-tier-v2-m2/probe-sigkill/record.json
   ```

3. **M3 - interruptible child ignores SIGINT.**

   ```diff
    def test_probe_interruptible():
   -    signal.signal(signal.SIGINT, _raise_keyboard_interrupt)
   +    signal.signal(signal.SIGINT, signal.SIG_IGN)
        time.sleep(30)
   ```

   Run `probe-suite`. `probe-sigint/record.json` must remain
   `unresolved_stall` but change to `killed=true` with an ordered SIGKILL event,
   causing the suite's `sigint` check to fail.

   ```bash
   jq -e '
     [.timeline[].event] as $events
     | .outcome == "unresolved_stall"
       and .interrupted == true
       and .killed == true
       and ($events | index("sigint"))
           < ($events | index("sigkill"))
       and ($events | index("sigkill"))
           < ($events | index("group_exit_after_sigkill"))
   ' /tmp/price-truth-tier-v2-m3/probe-sigint/record.json
   ```

4. **M4 - between-launch runner drift.**

   ```diff
        pass_record = _probe_record(
            preflight_path,
            preflight,
            "probe_pass",
            "probe-fast-pass",
        )
   +    runner_path = Path(__file__)
   +    runner_path.write_text(
   +        runner_path.read_text(encoding="utf-8") + "\n# MUTATION M4\n",
   +        encoding="utf-8",
   +    )
        interrupt_record = _probe_record(
   ```

   Record the runner SHA immediately before `probe-suite` and again after it.
   `probe-fast-pass/record.json` must exist, the hashes must differ,
   `probe-sigint` must not exist, and stderr must contain
   `preflight artifact changed`. This proves preflight is revalidated between
   child launches, not only once at controller entry.

   ```bash
   test -f /tmp/price-truth-tier-v2-m4/probe-fast-pass/record.json
   test ! -e /tmp/price-truth-tier-v2-m4/probe-sigint
   ! cmp \
     /tmp/price-truth-tier-v2-m4/runner-before.sha256 \
     /tmp/price-truth-tier-v2-m4/runner-after.sha256
   rg -F 'preflight artifact changed' \
     /tmp/price-truth-tier-v2-m4/mutation.stderr
   ```

5. **M5 - invalid progress descriptor.** Use a dedicated fresh M5 root with
   pristine source and fixture bytes, prepare its probe preflight, and run
   `probe-suite`. Its two dedicated input-mutation arms omit
   `PRICE_TRUTH_PROGRESS_FD` and set `not-a-file-descriptor`, respectively.
   Preserve both commands, transcripts, and records. Both child pytest
   commands must fail in `pytest_configure`, while the module-mode preflight
   and parent runner complete without the variable.

   Run its pristine suite normally, require exit `0`, and assert:

   ```bash
   MUTATION_ROOT=/tmp/price-truth-tier-v2-m5
   /home/hyl/.virtualenvs/llm_app/bin/python \
     "$MUTATION_ROOT/price_truth_tier_runner.py" \
     probe-suite \
     --preflight "$MUTATION_ROOT/probe-preflight.json"
   jq -e '
     .returncode != 0
     and .pytest_configure_failure == true
     and .invalid_reason == null
   ' \
     "$MUTATION_ROOT/probe-progress-fd-missing/record.json" \
     "$MUTATION_ROOT/probe-progress-fd-garbled/record.json"
   ```

6. **M6 - prior invalid closes the side.** After base collection artifacts
   exist, create `/tmp/price-truth-tier-v2-m6` and copy the pristine runner,
   reporter, builder, all five probe artifacts, `base.nodes`,
   `tier-map.tsv`, all eight `T?.paths`, and all eight `base-T?.nodes` files
   into it. Create a base preflight there, then create `seed_invalid.py` from
   this exact source:

   ```bash
   MUTATION_ROOT=/tmp/price-truth-tier-v2-m6
   test ! -e "$MUTATION_ROOT"
   mkdir "$MUTATION_ROOT"
   cp \
     "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
     "$PRICE_TRUTH_TIER_ROOT/arkscope_price_truth_tier_reporter.py" \
     "$PRICE_TRUTH_TIER_ROOT/build_tiers.py" \
     "$PRICE_TRUTH_TIER_ROOT/probe.nodes" \
     "$PRICE_TRUTH_TIER_ROOT/probe-tier-map.tsv" \
     "$PRICE_TRUTH_TIER_ROOT/probe_pass.py" \
     "$PRICE_TRUTH_TIER_ROOT/probe_interruptible.py" \
     "$PRICE_TRUTH_TIER_ROOT/probe_ignore_sigint.py" \
     "$PRICE_TRUTH_TIER_ROOT/base.nodes" \
     "$PRICE_TRUTH_TIER_ROOT/tier-map.tsv" \
     "$PRICE_TRUTH_TIER_ROOT"/T?.paths \
     "$PRICE_TRUTH_TIER_ROOT"/base-T?.nodes \
     "$MUTATION_ROOT/"

   /home/hyl/.virtualenvs/llm_app/bin/python \
     "$MUTATION_ROOT/price_truth_tier_runner.py" \
     prepare-preflight \
     --artifact-root "$MUTATION_ROOT" \
     --repo "$PWD" \
     --side base
   ```

   ```python
   import json
   from pathlib import Path

   import price_truth_tier_runner as runner


   root = Path(__file__).resolve().parent
   preflight_path = root / "base-preflight.json"
   preflight = runner._verify_preflight(preflight_path)
   trial = root / "base-T0-a1"
   trial.mkdir()
   record = {
       "bank_identity": runner._bank_identity(
           preflight_path,
           preflight,
           "runtime",
       ),
       "label": "base-T0-a1",
       "outcome": "invalid",
   }
   (trial / "record.json").write_text(
       json.dumps(record, indent=2, sort_keys=True) + "\n",
       encoding="utf-8",
   )
   ```

   Run and admit the negative control exactly:

   ```bash
   PYTHONPATH="$MUTATION_ROOT" \
     /home/hyl/.virtualenvs/llm_app/bin/python \
     "$MUTATION_ROOT/seed_invalid.py"
   find "$MUTATION_ROOT" -maxdepth 1 -type d -printf '%f\n' \
     | LC_ALL=C sort \
     > "$MUTATION_ROOT/directories-before-run-side.txt"

   set +e
   /home/hyl/.virtualenvs/llm_app/bin/python \
     "$MUTATION_ROOT/price_truth_tier_runner.py" \
     run-side \
     --preflight "$MUTATION_ROOT/base-preflight.json" \
     > "$MUTATION_ROOT/mutation.stdout" \
     2> "$MUTATION_ROOT/mutation.stderr"
   rc="$?"
   set -e
   printf '%s\n' "$rc" > "$MUTATION_ROOT/exit-code.txt"
   test "$rc" -ne 0

   jq -e '
     .complete == false
     and .invalid_attempt == "base-T0-a1"
     and .selected_attempts == {}
     and .unresolved_tiers == []
   ' "$MUTATION_ROOT/base-summary.json"
   test ! -e "$MUTATION_ROOT/base-T1-a1"
   ```

   The runner must refuse on the seeded record, atomically write the
   incomplete summary above, and create no T1 or later attempt directory.

For M1, require the fields above with `jq`. For M2, require both sleep records
to have `invalid_reason=deadline_breach_without_dump` and
`dump_present=false`. For M3, require `probe-sigint` to remain
`unresolved_stall` but contain ordered `sigint`, `sigkill`, and
`group_exit_after_sigkill` timeline events with `killed=true`. For M4, save
`runner-before.sha256`, `runner-after.sha256`, and
`runtime-drift.diff` in addition to `mutation.diff`.

M1-M4 diffs, M5 input records, M6 seeded record, commands, exit codes, and
owning record fields go into evidence. Restore is by abandoning each mutation
root; then re-hash the canonical runner and fixtures. Mutation roots are never
inputs to Task 0. Expected `invalid` records in M1/M2 and the seeded M6 record
are negative control results, not Stop Condition 11 runtime attempts.

#### Runtime side command

For each side, the collection-only recipe above must already have produced:

```text
<side>.nodes
<side>-T0.nodes ... <side>-T7.nodes
T0.paths ... T7.paths
tier-map.tsv
```

Re-prove exact union, uniqueness, canonical equality, builder/map hashes, and
the base or tip file-set rule before preflight creation. Then use exactly:

```bash
: "${SIDE:?set SIDE to base or tip}"
case "$SIDE" in
  base|tip) ;;
  *) printf 'invalid SIDE: %s\n' "$SIDE" >&2; exit 2 ;;
esac

/home/hyl/.virtualenvs/llm_app/bin/python \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  prepare-preflight \
  --artifact-root "$PRICE_TRUTH_TIER_ROOT" \
  --repo "$PWD" \
  --side "$SIDE"

sha256sum "$PRICE_TRUTH_TIER_ROOT/${SIDE}-preflight.json"

/home/hyl/.virtualenvs/llm_app/bin/python \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  run-side \
  --preflight "$PRICE_TRUTH_TIER_ROOT/${SIDE}-preflight.json"
```

No `timeout`, shell backgrounding, external process inspection, signal,
wrapper, or alternate retry is permitted. The runner launches pytest directly
with `start_new_session=True`, validates PID=PGID=SID, drains the structured
pipe, owns the three no-progress phases, classifies the current-window dump,
sends SIGINT and conditional SIGKILL, archives generated worktree data, and
atomically records every attempt.

The runner starts all eight initial tiers sequentially. It banks only natural
`complete_pass` or `complete_nonpassing` attempts under the closed identity,
defers each `unresolved_stall` for one ascending retry after all initial
tiers, and refuses every later launch after the first `invalid`. Progress
events control deadlines only. The unchanged reporter and exact tier
manifest remain the sole collection, seen, and non-passing authorities.

Require the completed side summary. `invalid_attempt` is absent from a
completed summary, so use a null-coalescing assertion:

```bash
jq -e --arg side "$SIDE" '
  .protocol_id == "price-truth-tier-v2"
  and .side == $side
  and .complete == true
  and (.invalid_attempt // null) == null
  and .unresolved_tiers == []
  and (.selected_attempts | keys | sort)
      == ["0","1","2","3","4","5","6","7"]
' "$PRICE_TRUTH_TIER_ROOT/${SIDE}-summary.json"

sha256sum \
  "$PRICE_TRUTH_TIER_ROOT/${SIDE}-summary.json" \
  "$PRICE_TRUTH_TIER_ROOT/${SIDE}-nonpassing.nodes"
```

Every selected attempt must have a matching complete record and non-passing
artifact. EIR-002 permits a naturally completed non-green tier; it does not
permit an unresolved or invalid side.

Only after a complete side, run the separately bounded diagnostic command:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python \
  "$PRICE_TRUTH_TIER_ROOT/price_truth_tier_runner.py" \
  run-diagnostic \
  --preflight "$PRICE_TRUTH_TIER_ROOT/${SIDE}-preflight.json"
```

Its record is diagnostic only. It cannot replace, override, or enter the
tiered A/B result. A prior invalid or incomplete side prevents its launch.
If the diagnostic itself is invalid, no later runner launch is permitted
under that preflight, but the already completed tiered admission remains
separately identified.

Every base/tip summary must state that fresh-process tiers reset
process-global, module, fixture, and teardown state between file groups and
therefore are not directly comparable with historical monolithic runs.
Transcript text supplies only terminal-summary and current-window dump
presence; it never supplies node IDs or pass/fail accounting.

## 3. Exact Accounting

### 3.1 Backend node ledger

No existing backend node ID is removed or renamed. Add exactly 17 nodes:

| File | Base | Add | Remove | Final |
|---|---:|---:|---:|---:|
| `tests/test_market_data_direct.py` | 63 | 7 | 0 | 70 |
| `tests/test_prices_runtime.py` | 4 | 4 | 0 | 8 |
| `tests/test_data_scheduler.py` | 84 | 6 | 0 | 90 |
| Focused total | 151 | 17 | 0 | 168 |
| Full repository | 4722 | 17 | 0 | 4739 |

Add these exact direct-collector nodes:

```text
tests/test_market_data_direct.py::test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target
tests/test_market_data_direct.py::test_backfill_failed_when_every_ticker_has_issue
tests/test_market_data_direct.py::test_backfill_resolved_zero_bar_target_stays_succeeded_and_clears_error
tests/test_market_data_direct.py::test_backfill_one_row_low_volume_day_stays_succeeded
tests/test_market_data_direct.py::test_backfill_non_target_rows_do_not_resolve_original_zero_bar_target
tests/test_market_data_direct.py::test_backfill_rechecks_original_target_set_only_once
tests/test_market_data_direct.py::test_backfill_exception_and_unresolved_tickers_share_one_issue_rollup
```

Add these exact worker nodes:

```text
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_partial_json_and_exits_zero
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_failed_result_json_and_exits_nonzero
tests/test_prices_runtime.py::test_prices_worker_rejects_unknown_status_and_malformed_counts
tests/test_prices_runtime.py::test_prices_worker_bounds_sorts_and_sanitizes_ticker_lists
```

Add these exact scheduler nodes:

```text
tests/test_data_scheduler.py::test_prices_worker_stdout_parser_preserves_partial_truth_and_bounded_tickers
tests/test_data_scheduler.py::test_prices_worker_stdout_parser_rejects_malformed_partial_payloads
tests/test_data_scheduler.py::test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation
tests/test_data_scheduler.py::test_prices_failed_payload_persists_failed_without_partial
tests/test_data_scheduler.py::test_prices_success_clears_prior_partial_and_preserves_audit_history
tests/test_data_scheduler.py::test_price_partial_projection_does_not_change_normalized_news_audit_status
```

The following existing nodes evolve in place and retain their exact IDs:

```text
tests/test_market_data_direct.py::test_backfill_per_ticker_exception_isolated
tests/test_market_data_direct.py::test_backfill_meta_write_failure_in_error_path_does_not_abort_batch
tests/test_market_data_direct.py::test_backfill_topup_idempotent_on_complete_day
tests/test_market_data_direct.py::test_backfill_ibkr_empty_from_swallowed_request_error_falls_to_polygon
tests/test_market_data_direct.py::test_backfill_fetches_provider_rows_outside_market_write_lock
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_success_json
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_error_json
tests/test_data_scheduler.py::test_p0c1_ibkr_prices_runs_prices_worker_subprocess
tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync
tests/test_data_scheduler.py::test_price_scope_required
tests/test_data_scheduler.py::test_prices_worker_retryable_lock_busy_is_skip_not_failure
tests/test_data_scheduler.py::test_prices_worker_stdout_parse_preserves_retryable_and_counts
```

The direct-test fixtures above must use one completed market date where the
test claims a wholly successful result. A fixture that returns one day inside a
multi-day zero-bar window is partial by design and must not be relabeled for
test convenience.

### 3.2 Frontend node and resource ledger

Add exactly two frontend nodes; remove or rename none:

```text
src/marketDataDisplay.test.ts > schedulerStateLabel > renders price unresolved count and bounded ticker list without continuation
src/SettingsProviderConfig.test.ts > Settings provider config authority > renders price partial facts without a Continue control in both locales
```

| File | Base | Add | Remove | Final |
|---|---:|---:|---:|---:|
| `src/marketDataDisplay.test.ts` | 36 | 1 | 0 | 37 |
| `src/SettingsProviderConfig.test.ts` | 36 | 1 | 0 | 37 |
| `src/i18n/resources.test.ts` | 14 | 0 | 0 | 14 |
| Focused total | 86 | 2 | 0 | 88 |
| Full frontend | 1074 | 2 | 0 | 1076 |
| Frontend files | 96 | 0 | 0 | 96 |

Add exactly two leaves per locale under
`settings.dataSources.schedule.history`:

```text
priceUnresolved_one
priceUnresolved_other
```

The per-locale resource ledger is:

| Subtree | Base | Add | Remove | Final |
|---|---:|---:|---:|---:|
| Settings | 704 | 2 | 0 | 706 |
| Explore | 380 | 0 | 0 | 380 |
| Total | 1783 | 2 | 0 | 1785 |

The existing count node in `src/i18n/resources.test.ts` evolves in place; its
ID does not change.

## 4. File Map

### 4.1 Create

- `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
  records RED, GREEN, mutation, accounting, protected-boundary, and release
  evidence.

### 4.2 Modify

- `src/market_data_direct.py`: post-write target reconciliation, derived batch
  status, and provider telemetry projection.
- `src/prices_runtime.py`: closed sanitized result validator and status-derived
  exit code.
- `src/service/data_scheduler.py`: strict prices payload parser and local
  partial/failed audit projection.
- `tests/test_market_data_direct.py`: seven new nodes and the exact in-place
  evolutions in Section 3.1.
- `tests/test_prices_runtime.py`: four new nodes and two in-place evolutions.
- `tests/test_data_scheduler.py`: six new nodes and five in-place evolutions.
- `apps/arkscope-web/src/api.ts`: scheduler result DTO fields only.
- `apps/arkscope-web/src/marketDataDisplay.ts`: price-specific durable partial
  presentation only.
- `apps/arkscope-web/src/marketDataDisplay.test.ts`: one pure presentation node.
- `apps/arkscope-web/src/SettingsProviderConfig.test.ts`: one bilingual mounted
  node and a bounded fixture mode.
- `apps/arkscope-web/src/i18n/resources/en/settings.ts`: two English plural
  leaves.
- `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`: two Traditional
  Chinese plural leaves.
- `apps/arkscope-web/src/i18n/resources.test.ts`: count values only, same node
  ID.
- the design spec, this plan, evidence packet, and priority map for lifecycle
  state only.

`apps/arkscope-web/src/settings/DataSourcesSection.tsx` consumes
`schedulerStateLabel` unchanged. It is not an implementation owner unless the
mounted RED proves the existing `needsContinue=false` contract cannot render
correctly; that outcome is a stop condition, not permission to expand scope.

### 4.3 Delete

None.

## 5. Locked Implementation Shape

### 5.1 Collector constants and target query

Add the stable codes next to `_VALID_RUN_STATUSES` and add one private helper
next to `_insert_rows`:

```python
_PRICE_DAY_UNRESOLVED_AFTER_FETCH = "price_day_unresolved_after_fetch"
_PRICE_COLLECTION_PARTIAL = "price_collection_partial"
_PRICE_COLLECTION_FAILED = "price_collection_failed"


def _unresolved_price_target_dates(
    conn,
    *,
    ticker: str,
    interval: str,
    targets: List[date],
) -> List[date]:
    unique_targets = sorted(set(targets))
    if not unique_targets:
        return []
    placeholders = ", ".join("?" for _ in unique_targets)
    target_ids = [target.isoformat() for target in unique_targets]
    rows = conn.execute(
        "SELECT DISTINCT substr(datetime, 1, 10) FROM prices "
        "WHERE ticker = ? AND interval = ? "
        f"AND substr(datetime, 1, 10) IN ({placeholders})",
        (ticker, _INTERVAL_DB.get(interval, interval), *target_ids),
    ).fetchall()
    present = {str(row[0]) for row in rows}
    return [target for target in unique_targets if target.isoformat() not in present]


def _derive_price_collection_status(tickers_scanned: int, issue_count: int) -> str:
    if tickers_scanned <= 0 or issue_count < 0 or issue_count > tickers_scanned:
        raise ValueError("invalid price collection outcome counts")
    if issue_count == 0:
        return "succeeded"
    if issue_count == tickers_scanned:
        return "failed"
    return "partial"
```

The helper receives only `item["gaps"]`, which is the original
`detect_price_gaps()` result captured before provider work. It must not receive
`fetch_days`, call `detect_price_gaps()` itself, count bars, or import Coverage
v2.

### 5.2 Collector write-phase derivation

Initialize the result with the complete semantic envelope:

```python
rollup = {
    "status": "succeeded",
    "provider": provider,
    "tickers_scanned": 0,
    "succeeded_ticker_count": 0,
    "gaps_found": 0,
    "rows_added": 0,
    "errors": {},
    "unresolved_after_fetch_count": 0,
    "unresolved_after_fetch_tickers": [],
}
```

Inside the existing second `market_write_lock`, replace the success path with
this ordered operation. Existing exception recovery remains best-effort and
contributes one issue for that ticker:

```python
rows = item.get("rows")
rows = rows if isinstance(rows, list) else []
targets = item.get("gaps")
targets = targets if isinstance(targets, list) else []
added = _insert_rows(conn, rows)
rollup["rows_added"] += added
last_bar = rows[-1][1] if rows else None
unresolved = _unresolved_price_target_dates(
    conn,
    ticker=canon,
    interval=interval,
    targets=targets,
)
if unresolved:
    rollup["errors"][canon] = _PRICE_DAY_UNRESOLVED_AFTER_FETCH
    rollup["unresolved_after_fetch_tickers"].append(canon)
    _upsert_provider_meta(
        conn,
        provider=provider,
        ticker=canon,
        interval=interval,
        last_bar_datetime=last_bar,
        rows_added=added,
        error=_PRICE_DAY_UNRESOLVED_AFTER_FETCH,
    )
else:
    rollup["succeeded_ticker_count"] += 1
    _upsert_provider_meta(
        conn,
        provider=provider,
        ticker=canon,
        interval=interval,
        last_bar_datetime=last_bar,
        rows_added=added,
        error=None,
    )
```

After all tickers, derive and persist once:

```python
unresolved_tickers = sorted(set(rollup["unresolved_after_fetch_tickers"]))
rollup["unresolved_after_fetch_tickers"] = unresolved_tickers
rollup["unresolved_after_fetch_count"] = len(unresolved_tickers)
issue_count = len(rollup["errors"])
rollup["succeeded_ticker_count"] = rollup["tickers_scanned"] - issue_count
rollup["status"] = _derive_price_collection_status(
    rollup["tickers_scanned"],
    issue_count,
)
run_error = {
    "succeeded": None,
    "partial": _PRICE_COLLECTION_PARTIAL,
    "failed": _PRICE_COLLECTION_FAILED,
}[rollup["status"]]
_finish_provider_run(
    conn,
    run_id,
    status="succeeded" if rollup["status"] == "succeeded" else "failed",
    tickers_scanned=rollup["tickers_scanned"],
    gaps_found=rollup["gaps_found"],
    rows_added=rollup["rows_added"],
    error=run_error,
)
```

Do not add `partial` to `_VALID_RUN_STATUSES` or either SQLite CHECK. Do not
move `_fetch_rows_for_gaps()` under `market_write_lock`.

### 5.3 Worker closed payload

In `src/prices_runtime.py`, add strict helpers. Booleans are invalid integers;
ticker IDs are uppercase ASCII identifiers, sorted/deduplicated, and capped at
the existing 25-item boundary:

```python
import re

_PRICE_RESULT_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PRICE_COUNT_FIELDS = (
    "tickers_scanned",
    "succeeded_ticker_count",
    "gaps_found",
    "rows_added",
    "unresolved_after_fetch_count",
)
_SAFE_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9 ._-]{0,11}$")


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {field}")
    return value


def _ticker_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"invalid {field}")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid {field}")
    result = sorted({item.strip().upper() for item in value})
    if any(not _SAFE_TICKER.fullmatch(item) for item in result):
        raise ValueError(f"invalid {field}")
    return result
```

Replace `sanitize_result()` with validation that cannot manufacture success:

```python
def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    if status not in _PRICE_RESULT_STATUSES:
        raise ValueError("invalid price collection status")
    provider = result.get("provider")
    if provider not in {"ibkr", "polygon"}:
        raise ValueError("invalid provider")
    counts = {
        field: _nonnegative_int(result.get(field), field)
        for field in _PRICE_COUNT_FIELDS
    }
    errors = result.get("errors")
    if not isinstance(errors, dict):
        raise ValueError("invalid errors")
    error_tickers = _ticker_ids(list(errors), "error_tickers")
    unresolved = _ticker_ids(
        result.get("unresolved_after_fetch_tickers"),
        "unresolved_after_fetch_tickers",
    )
    error_count = len(error_tickers)
    if counts["unresolved_after_fetch_count"] != len(unresolved):
        raise ValueError("invalid unresolved_after_fetch_count")
    if not set(unresolved).issubset(error_tickers):
        raise ValueError("unresolved tickers must be issue tickers")
    scanned = counts["tickers_scanned"]
    if counts["succeeded_ticker_count"] != scanned - error_count:
        raise ValueError("invalid succeeded_ticker_count")
    expected = (
        "succeeded" if error_count == 0
        else "failed" if scanned > 0 and error_count == scanned
        else "partial"
    )
    if scanned <= 0 or status != expected:
        raise ValueError("status does not match price collection facts")
    return {
        "status": status,
        "provider": provider,
        **counts,
        "error_count": error_count,
        "error_tickers": error_tickers[:25],
        "unresolved_after_fetch_tickers": unresolved[:25],
    }
```

Keep the recognized lock-busy exception diagnostic required by retryable-skip
classification. For every other exception, expose only its class and a blank
message:

```python
def sanitize_error(exc: BaseException) -> dict[str, Any]:
    raw = str(exc)
    retryable = _is_retryable_error(raw)
    return {
        "status": "failed",
        "error_class": exc.__class__.__name__,
        "error": raw[:MAX_ERROR_LEN] if retryable else "",
        "retryable": retryable,
    }
```

Derive the process exit from the validated status:

```python
payload = sanitize_result(result)
code = 1 if payload["status"] == "failed" else 0
```

### 5.4 Scheduler strict parser and local projection

Expand `_PRICES_WORKER_COUNT_KEYS` and parse structured result and exception
failure shapes separately:

```python
_PRICES_WORKER_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PRICES_WORKER_COUNT_KEYS = (
    "tickers_scanned",
    "succeeded_ticker_count",
    "gaps_found",
    "rows_added",
    "error_count",
    "unresolved_after_fetch_count",
)


def _parse_price_ticker_ids(value: Any) -> Optional[List[str]]:
    if (
        not isinstance(value, list)
        or len(value) > 25
        or any(not isinstance(item, str) for item in value)
    ):
        return None
    normalized = sorted({item.strip().upper() for item in value})
    if any(
        not item
        or len(item) > 12
        or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-" for ch in item)
        for item in normalized
    ):
        return None
    return normalized
```

`_parse_sanitized_prices_worker_stdout()` must follow this order:

1. reject non-object JSON and unknown status;
2. accept the existing exception envelope only for `status='failed'` when no
   structured count key is present, preserving `error_class`, bounded `error`,
   and `retryable`;
3. otherwise require `provider` to be exactly `ibkr` or `polygon`;
4. require every count as a nonnegative integer, rejecting booleans;
5. require both ticker arrays, reject more than 25 exposed IDs, normalize them,
   and require each normalized length to equal `min(full_count, 25)`;
6. require `succeeded_ticker_count == tickers_scanned - error_count`,
   `unresolved_after_fetch_count <= error_count`, and the status implied by
   `tickers_scanned/error_count`; and
7. return only allowlisted fields.

The structured return shape is:

```python
return {
    "status": status,
    "provider": provider,
    **counts,
    "error_tickers": error_tickers,
    "unresolved_after_fetch_tickers": unresolved_tickers,
    "error_class": "",
    "error": "",
    "retryable": False,
}
```

In `run_source()`, introduce only a price-local semantic flag:

```python
price_partial = False
price_audit_error: Optional[str] = None
```

After the prices child returns, classify payload before return code can imply
success:

```python
price_status = step["payload"]["status"]
if price_status == "partial" and step["returncode"] == 0:
    price_partial = True
    price_audit_error = "price_collection_partial"
elif price_status == "failed":
    reason = _prices_worker_retryable_skip_reason(step["payload"])
    if reason is not None:
        result.update({
            "status": "skipped",
            "reason": reason,
            "skip_kind": "skipped_lock_busy",
        })
    else:
        raise RuntimeError("price_collection_failed")
elif price_status != "succeeded" or step["returncode"] != 0:
    raise RuntimeError(_sanitized_prices_worker_failure_message(step["payload"]))
```

Derive durable status with price partial beside, not inside, normalized-news
continuation logic:

```python
elif ok and (writer_partial or price_partial):
    result["status"] = "partial"
    continuation = writer_continuation if writer_partial else None
    if continuation is not None:
        result["continuation"] = continuation
```

Keep `record_outcome(..., error=error)` unchanged so a completed price partial
has durable status `partial`, `continuation=None`, and structured result without
a fabricated retry control. Project only price partial to failed audit:

```python
audit_failed = (not ok) or price_partial
audit_error = price_audit_error if price_partial else error
store.finish_run(
    run_id,
    status="failed" if audit_failed else "succeeded",
    message=audit_error if audit_failed else None,
    error=audit_error if audit_failed else None,
    result=result,
)
```

This code must leave normalized-news `writer_partial` audit behavior exactly
as it is today.

### 5.5 Frontend DTO, copy, and presentation

Extend only `ScheduleRunResult.collect` in `apps/arkscope-web/src/api.ts`:

```typescript
status?: "succeeded" | "partial" | "failed";
succeeded_ticker_count?: number;
gaps_found?: number;
rows_added?: number;
error_count?: number;
error_tickers?: string[];
unresolved_after_fetch_count?: number;
unresolved_after_fetch_tickers?: string[];
```

Add these exact resources:

```typescript
// en/settings.ts
priceUnresolved_one: "Partially completed ({{count}} ticker remains unresolved after collection: {{tickers}})",
priceUnresolved_other: "Partially completed ({{count}} tickers remain unresolved after collection: {{tickers}})",

// zh-Hant/settings.ts
priceUnresolved_one: "部分完成（抓取後仍有 {{count}} 個標的無法確認：{{tickers}}）",
priceUnresolved_other: "部分完成（抓取後仍有 {{count}} 個標的無法確認：{{tickers}}）",
```

In the `partial` branch of `schedulerStateLabel()`, keep actionable
continuation first, then add this price-specific branch before news
continuation/body facts:

```typescript
const collect = durable?.last_result?.collect;
const unresolved = positiveCount(collect?.unresolved_after_fetch_count);
const unresolvedTickers = Array.isArray(collect?.unresolved_after_fetch_tickers)
  ? collect.unresolved_after_fetch_tickers
    .filter((ticker): ticker is string => typeof ticker === "string" && ticker.length > 0)
    .slice(0, 25)
  : [];
if (
  durable?.last_result?.source === "ibkr_prices"
  && collect?.status === "partial"
  && unresolved > 0
  && unresolvedTickers.length > 0
) {
  const label = unresolved === 1
    ? t(($) => $.dataSources.schedule.history.priceUnresolved_one, {
      count: unresolved,
      tickers: unresolvedTickers.join(", "),
    })
    : t(($) => $.dataSources.schedule.history.priceUnresolved_other, {
      count: unresolved,
      tickers: unresolvedTickers.join(", "),
    });
  return { label, tone: "warn", needsContinue: false };
}
```

Then continue through the existing generic news/count/cursor branches. Do not
change `jobOutcome()`, the generic glyph, `DataSourcesSection.tsx`, provider
health, or any Coverage display.

## 6. Stop Conditions

Stop and amend the reviewed authority before implementation continues if any
of these occurs:

1. a canonical collection hash or composition differs before product edits;
2. the exact final node ledger differs from `+17/-0` backend or `+2/-0`
   frontend;
3. resources cannot close at Settings `706`, Explore `380`, total `1785`;
4. reconciliation requires calling `detect_price_gaps()` after fetch, checking
   all fetch days, requiring 26 slots, or importing `src.market_coverage`;
5. provider fetch would move inside `market_write_lock`;
6. an adapter return type, retry policy, fallback order, request count, client
   ID, Gateway lock, scheduler cadence, or source catalog must change;
7. a SQLite schema, migration, status CHECK, existing price row, or production
   DB must change;
8. implementation requires changing normalized-news audit projection, generic
   job glyphs, provider health, Coverage API/DTO/presentation, or repair logic;
9. raw per-ticker/provider diagnostics or target dates would cross worker
   stdout or frontend DTO;
10. a live provider, Gateway, browser, scheduler, or production write is needed
    for RED/GREEN or review;
11. outside the pre-registered negative-control mutation roots, the pristine
    runner classifies any probe or base/tip/diagnostic attempt `invalid`; any
    base or tip tier cannot produce a complete natural-exit outcome after its
    one deferred retry; or either side's tier union does not exactly equal its
    canonical collection;
    preserve the runner/preflight identity, tier, last structured progress
    event, dump, signals, progress stream, record, and transcript as EIR-005
    diagnostic evidence, keep all partial output out of the baseline, and
    stop at that tier boundary; or
12. either main-worktree untracked document changes.

**Stop-11 resolution for the restart:** reviewed diagnosis `e6d4b7fa`
established that no tested code/import factor was necessary and that the
condition changes over time without a reboot. The approved response is not an
exclusion or a pass waiver. Section 2.2 replaces one monolithic admission run
with eight complete-collection tiers, one deferred retry per unresolved tier,
completed-tier banking under an immutable identity, and one SHA-pinned runner
that owns every deadline and signal. Stop Condition 11 is preserved at tier
granularity. A bounded monolithic attempt remains diagnostic-only and cannot
become an A/B side.

## 7. Task 0 - Reground After Plan Clearance

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

> **Historical restart attempt 2026-07-29:** Steps 1-4 completed at clearance
> `5fecce6536f5d9f4a13903a6c1059e235ba15324`. Step 5 emitted its 120-second
> dump and then remained stalled at `test_api.py::TestHealth::test_status`.
> The operator interrupted it under Stop Condition 11. Steps 6-8 and all
> product work remain unstarted.
>
> **Tiered restart 2026-07-30:** diagnosis closeout is merged at
> `e6d4b7fa`; manual tier execution was later invalidated at `fa42d44a`
> because it missed the reviewed no-progress deadline and added an unreviewed
> PID sampling check. Deterministic runner design `1d08a9f3` replaces that
> control plane. Every Task 0 checkbox remains reset. Historical focused and
> invalid tier results may inform review but cannot satisfy v2.

- [ ] **Step 1: Record the clearance identities.**

  Run:

  ```bash
  git status --short --branch
  git rev-parse HEAD
  git merge-base --is-ancestor e6d4b7fa HEAD
  git diff --name-only e6d4b7fa...HEAD
  ```

  Expected before product edits: branch `codex/price-collection-truth`;
  restart base is an ancestor; only the reviewed price-truth spec, plan,
  evidence packet, and priority-map docs differ from `e6d4b7fa`. Export the
  exact runtime identity and record its output in the evidence packet:

  ```bash
  export PLAN_REVIEW_CLEARANCE_COMMIT="$(git rev-parse HEAD)"
  printf '%s\n' "$PLAN_REVIEW_CLEARANCE_COMMIT"
  ```

- [ ] **Step 2: Prove the worktree is isolated and contains no production data.**

  Run:

  ```bash
  test "$(git rev-parse --show-toplevel)" = "/tmp/arkscope-price-collection-truth"
  test -L node_modules
  test "$(readlink node_modules)" = "/mnt/md0/PycharmProjects/ArkScope/node_modules"
  test -d data
  test -z "$(find data -mindepth 1 -maxdepth 1 -print -quit)"
  git check-ignore -q node_modules
  git check-ignore -q data
  git status --short
  ```

  Expected: the ignored dependency symlink and empty data directory do not
  appear in Git status. Do not copy `data/`, `config/.env`, browser profiles,
  or either main-worktree untracked document into this worktree.

- [ ] **Step 3: Reproduce all four canonical collections.**

  Run Section 2.1 exactly. Expected: backend `4722/151` with composition
  `63/4/84`; frontend `96 files / 1074 nodes` and focused `86` with composition
  `36/14/36`; all four SHA-256 values match Section 2.

- [ ] **Step 4: Reproduce focused and non-node behavior.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py

  cd apps/arkscope-web
  npx vitest run \
    src/SettingsProviderConfig.test.ts \
    src/i18n/resources.test.ts \
    src/marketDataDisplay.test.ts
  npm run check:i18n-literals
  npm run check:i18n-literals
  cd ../..

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_tools.py::TestRegistry::test_register_all \
    tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
    tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count \
    tests/test_pg_unreachable_e2e.py

  /home/hyl/.virtualenvs/llm_app/bin/python src/smoke/pg_unreachable_e2e.py
  ```

  Expected: backend `151 passed`; frontend focused `86 passed`; scanner twice
  `36/20/0/20`; tools `53/54/54`; no-PG `23/23`, `ok=true`, and no PG attempt.

- [ ] **Step 5: Build and complete the base tiered non-passing set.**

  Execute all of Section 2.2 with `SIDE=base`: exact runner extraction,
  mandatory probes, six-mutation packet, collection proof, preflight, and the
  single `run-side` command. Prove the builder/map hashes, the
  `591/591/590/590/590/590/590/590` distribution, exact `4722` tier union,
  zero duplicate/missing nodes, and all eight complete selected outcomes.

  Accept only each selected attempt's reporter-derived non-passing artifact.
  The runner, not an operator pipeline, creates the sorted union at
  `$PRICE_TRUTH_TIER_ROOT/base-nonpassing.nodes`. Never parse node IDs from
  `FAILED`, `ERROR`, progress, or other transcript lines. A passing selected
  attempt contributes an empty structured non-passing file.

  Record the runner/preflight/probe identities and each selected attempt's
  outcome, attempt number, duration, exit, transcript/progress/report SHA,
  node count, non-passing count, data boundary, and signal timeline. EIR-002
  permits a naturally completed failing tier; it does not permit an invalid
  or unresolved side. If a deferred retry remains unresolved, preserve the
  atomic incomplete summary and all artifacts, then stop under Stop Condition
  11 without starting Step 6 or product RED.

  Once the tiered base is complete, invoke the Section 2.2
  `run-diagnostic` command. Record its closed outcome without using it in the
  baseline.

- [ ] **Step 6: Capture protected-boundary baselines.**

  ```bash
  git rev-parse HEAD:data_sources/ibkr_source.py
  git rev-parse HEAD:data_sources/polygon_source.py
  git rev-parse HEAD:src/service/provider_health.py
  git rev-parse HEAD:src/ibkr_gateway_lock.py
  git rev-parse HEAD:src/api/routes/market_data.py
  git rev-parse HEAD:src/data_provider_config.py
  git rev-parse HEAD:src/provider_config_runtime.py
  git ls-tree -r HEAD src/market_coverage sql scripts \
    | LC_ALL=C sort \
    | sha256sum

  /home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
  import json
  from src.service.data_scheduler import SOURCES

  print(json.dumps({
      key: {
          "default_interval_min": value.default_interval_min,
          "ibkr": value.ibkr,
          "prices_worker": value.prices_worker,
          "provider_fetch": value.provider_fetch,
      }
      for key, value in sorted(SOURCES.items())
  }, sort_keys=True, indent=2))
  PY
  ```

  Store exact output in the evidence packet. The catalog must contain the same
  four active source IDs and intervals before and after.

- [ ] **Step 7: Update the evidence packet with explicit grounded state.**

  Preserve the historical sections and update this exact section structure:

  ```markdown
  # Price Collection Partial-Truth Evidence

  > **Status: TASK 0 GROUNDED - RED-FIRST IMPLEMENTATION ACTIVE**
  >
  > **Product base:** `e6d4b7fa...`
  > **Plan-review clearance:** recorded from Task 0 Step 1

  ## 1. Scope And Authorities
  ## 2. Canonical Baseline
  ## 3. RED Evidence
  ## 4. GREEN Evidence
  ## 5. Node And Resource Accounting
  ## 6. Mutation Evidence
  ## 7. Protected Boundaries
  ## 8. Tiered Backend A/B And Monolithic Diagnostic
  ## 9. Review Resolution
  ## 10. Integration And Read-Only Release Observation
  ```

  Replace the descriptive clearance line with the real full SHA captured in
  Step 1 before saving the file.

- [ ] **Step 8: Record Task 0 and commit docs only.**

  Add a newest-first priority-map entry with exact reproduced hashes and the
  phrase `RED-FIRST IMPLEMENTATION ACTIVE`. Then run:

  ```bash
  git add \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git diff --cached --check
  git commit -m "docs: ground price collection truth task 0"
  ```

## 8. Task 1 - Direct Collector RED And GREEN

**Files:**
- Modify: `tests/test_market_data_direct.py`
- Modify: `src/market_data_direct.py`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add one-day test helpers without adding nodes.**

  Add beside `_backfill_db`:

  ```python
  _ONE_COMPLETE_DAY_NOW = datetime(2026, 6, 23, 18, 0, tzinfo=timezone.utc)


  def _run_one_complete_day(
      tmp_path, monkeypatch, *, tickers, ibkr, polygon=None, db=None,
  ):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = db or _backfill_db(tmp_path)
      result = mdd.backfill_prices_direct(
          tickers_arg=tickers,
          lookback_days=1,
          provider="ibkr",
          db_path=str(db),
          ibkr_src=ibkr,
          polygon_src=polygon or _FakePolygon(),
          now_et=_ONE_COMPLETE_DAY_NOW,
      )
      return db, result
  ```

  At this instant, 2026-06-22 is the sole completed target date and 2026-06-23
  is still in progress.

- [ ] **Step 2: Add the seven exact RED nodes.**

  Use the existing `_FakeIBKR`, `_FakePolygon`, `_bar`, and SQLite helpers. The
  load-bearing assertions are:

  ```python
  def test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target(
      tmp_path, monkeypatch,
  ):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = _backfill_db(tmp_path)
      conn = sqlite3.connect(db)
      mdd._ensure_provider_sync_tables(conn)
      mdd._upsert_provider_meta(
          conn, provider="ibkr", ticker="LCID", interval="15min",
          last_bar_datetime="2026-06-19T13:30:00+0000", rows_added=0,
          error=None,
      )
      conn.execute(
          "UPDATE provider_sync_meta SET last_success='2000-01-01T00:00:00+00:00' "
          "WHERE provider='ibkr' AND ticker='LCID' AND interval='15min'"
      )
      conn.commit()
      conn.close()
      ibkr = _FakeIBKR({
          "AAPL": [_bar(datetime(2026, 6, 22, 9, 30))],
          "LCID": [],
      })
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="AAPL,LCID", ibkr=ibkr, db=db,
      )
      assert result["status"] == "partial"
      assert result["tickers_scanned"] == 2
      assert result["succeeded_ticker_count"] == 1
      assert result["rows_added"] == 1
      assert result["errors"] == {"LCID": "price_day_unresolved_after_fetch"}
      assert result["unresolved_after_fetch_count"] == 1
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
      conn = sqlite3.connect(db)
      assert conn.execute(
          "SELECT status, error FROM provider_sync_runs"
      ).fetchone() == ("failed", "price_collection_partial")
      assert conn.execute(
          "SELECT last_success, last_error FROM provider_sync_meta WHERE ticker='LCID'"
      ).fetchone() == (
          "2000-01-01T00:00:00+00:00", "price_day_unresolved_after_fetch",
      )
      assert conn.execute(
          "SELECT COUNT(*) FROM prices WHERE ticker='AAPL'"
      ).fetchone()[0] == 1
      conn.close()


  def test_backfill_failed_when_every_ticker_has_issue(tmp_path, monkeypatch):
      ibkr = _FakeIBKR({"LCID": []}, raises_for=["BAD"])
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="BAD,LCID", ibkr=ibkr,
      )
      assert result["status"] == "failed"
      assert result["succeeded_ticker_count"] == 0
      assert set(result["errors"]) == {"BAD", "LCID"}
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
      conn = sqlite3.connect(db)
      assert conn.execute(
          "SELECT status, error FROM provider_sync_runs"
      ).fetchone() == ("failed", "price_collection_failed")
      conn.close()


  def test_backfill_resolved_zero_bar_target_stays_succeeded_and_clears_error(
      tmp_path, monkeypatch,
  ):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = _backfill_db(tmp_path)
      conn = sqlite3.connect(db)
      mdd._ensure_provider_sync_tables(conn)
      mdd._upsert_provider_meta(
          conn, provider="ibkr", ticker="AAPL", interval="15min",
          last_bar_datetime=None, rows_added=0, error="old_error",
      )
      conn.execute(
          "UPDATE provider_sync_meta SET last_success='2000-01-01T00:00:00+00:00' "
          "WHERE provider='ibkr' AND ticker='AAPL' AND interval='15min'"
      )
      conn.commit()
      conn.close()
      result = mdd.backfill_prices_direct(
          tickers_arg="AAPL", lookback_days=1, provider="ibkr",
          db_path=str(db),
          ibkr_src=_FakeIBKR({"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))]}),
          polygon_src=_FakePolygon(), now_et=_ONE_COMPLETE_DAY_NOW,
      )
      assert result["status"] == "succeeded"
      assert result["succeeded_ticker_count"] == 1
      assert result["unresolved_after_fetch_count"] == 0
      conn = sqlite3.connect(db)
      last_success, last_error = conn.execute(
          "SELECT last_success, last_error FROM provider_sync_meta "
          "WHERE provider='ibkr' AND ticker='AAPL' AND interval='15min'"
      ).fetchone()
      assert last_success != "2000-01-01T00:00:00+00:00"
      assert last_error is None
      conn.close()


  def test_backfill_one_row_low_volume_day_stays_succeeded(tmp_path, monkeypatch):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = _backfill_db(tmp_path)
      conn = sqlite3.connect(db)
      conn.execute(
          "INSERT INTO prices "
          "(ticker,datetime,interval,open,high,low,close,volume) "
          "VALUES ('LCID','2026-06-22T13:30:00+0000','15min',1,1,1,1,1)"
      )
      conn.commit()
      conn.close()
      result = mdd.backfill_prices_direct(
          tickers_arg="LCID", lookback_days=1, provider="ibkr",
          db_path=str(db), ibkr_src=_FakeIBKR(), polygon_src=_FakePolygon(),
          now_et=_ONE_COMPLETE_DAY_NOW,
      )
      assert result["rows_added"] == 0
      assert result["gaps_found"] == 0
      assert result["status"] == "succeeded"
      assert result["unresolved_after_fetch_count"] == 0


  def test_backfill_non_target_rows_do_not_resolve_original_zero_bar_target(
      tmp_path, monkeypatch,
  ):
      monkeypatch.setattr(
          mdd,
          "_fetch_rows_for_gaps",
          lambda *args, **kwargs: [(
              "LCID", "2026-06-20T13:30:00+0000", "15min",
              1.0, 1.0, 1.0, 1.0, 1,
          )],
      )
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="LCID", ibkr=_FakeIBKR(),
      )
      assert result["rows_added"] == 1
      assert result["status"] == "failed"
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
      conn = sqlite3.connect(db)
      assert conn.execute(
          "SELECT last_bar_datetime, last_success, last_error "
          "FROM provider_sync_meta WHERE ticker='LCID'"
      ).fetchone() == (
          "2026-06-20T13:30:00+0000", None,
          "price_day_unresolved_after_fetch",
      )
      conn.close()


  def test_backfill_rechecks_original_target_set_only_once(tmp_path, monkeypatch):
      calls = []

      def original_targets(*args, **kwargs):
          calls.append(1)
          if len(calls) != 1:
              raise AssertionError("target set was rederived after fetch")
          return {"LCID": [date(2026, 6, 22)]}

      monkeypatch.setattr(mdd, "detect_price_gaps", original_targets)
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="LCID", ibkr=_FakeIBKR(),
      )
      assert db.exists()
      assert calls == [1]
      assert result["status"] == "failed"
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]


  def test_backfill_exception_and_unresolved_tickers_share_one_issue_rollup(
      tmp_path, monkeypatch,
  ):
      ibkr = _FakeIBKR(
          {"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))], "LCID": []},
          raises_for=["BAD"],
      )
      _, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="AAPL,BAD,LCID", ibkr=ibkr,
      )
      assert result["status"] == "partial"
      assert result["tickers_scanned"] == 3
      assert result["succeeded_ticker_count"] == 1
      assert set(result["errors"]) == {"BAD", "LCID"}
      assert result["unresolved_after_fetch_count"] == 1
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
  ```

- [ ] **Step 3: Evolve the five existing nodes without renaming them.**

  Make these assertion changes:

  ```python
  # test_backfill_per_ticker_exception_isolated
  ibkr = _FakeIBKR(
      {"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))]},
      raises_for=["BAD"],
  )
  db, res = _run_one_complete_day(
      tmp_path, monkeypatch, tickers="AAPL,BAD", ibkr=ibkr, db=db,
  )
  assert res["status"] == "partial"
  assert res["succeeded_ticker_count"] == 1
  assert conn.execute(
      "SELECT status, error FROM provider_sync_runs"
  ).fetchone() == ("failed", "price_collection_partial")

  # test_backfill_meta_write_failure_in_error_path_does_not_abort_batch
  ibkr = _FakeIBKR(
      {"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))]},
      raises_for=["BAD"],
  )
  db, res = _run_one_complete_day(
      tmp_path, monkeypatch, tickers="BAD,AAPL", ibkr=ibkr, db=db,
  )
  assert res["status"] == "partial"
  assert res["succeeded_ticker_count"] == 1
  assert conn.execute(
      "SELECT status, error FROM provider_sync_runs"
  ).fetchone() == ("failed", "price_collection_partial")

  # test_backfill_topup_idempotent_on_complete_day
  # use lookback_days=1 and _ONE_COMPLETE_DAY_NOW for both calls
  assert a["status"] == b["status"] == "succeeded"
  assert a["rows_added"] == 1 and b["rows_added"] == 0

  # test_backfill_ibkr_empty_from_swallowed_request_error_falls_to_polygon
  # use lookback_days=1 and _ONE_COMPLETE_DAY_NOW
  assert res["status"] == "succeeded"
  assert res["unresolved_after_fetch_count"] == 0

  # test_backfill_fetches_provider_rows_outside_market_write_lock
  # return a date object from the detect_price_gaps fake and wrap the real
  # _unresolved_price_target_dates helper.
  reconciliation_observed_lock = []
  real_reconcile = mdd._unresolved_price_target_dates
  def checked_reconcile(*args, **kwargs):
      reconciliation_observed_lock.append(in_lock["value"])
      return real_reconcile(*args, **kwargs)
  monkeypatch.setattr(mdd, "_unresolved_price_target_dates", checked_reconcile)
  monkeypatch.setattr(
      mdd, "detect_price_gaps", lambda *a, **k: {"AAPL": [date(2026, 7, 3)]},
  )
  assert fetch_observed_lock == [False]
  assert reconciliation_observed_lock == [True]
  ```

  Also update comments that currently claim per-ticker failures leave the run
  succeeded. Preserve their isolation assertions.

- [ ] **Step 4: Run the direct suite and capture the right RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py
  ```

  Expected before implementation: the seven new contract nodes and evolved
  status assertions fail because no post-write reconciliation/status envelope
  exists. A provider/network call, calendar error, invalid date fixture, or SQL
  setup error is the wrong RED and must be corrected before product edits.

- [ ] **Step 5: Implement Sections 5.1 and 5.2 exactly.**

  Keep fetch in the first unlocked phase. Reconcile only `item["gaps"]` after
  `_insert_rows()` in the second write phase. Keep the existing outer fatal
  failure finalizer and best-effort per-ticker meta recovery.

- [ ] **Step 6: Run direct GREEN and exact collection.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_market_data_direct.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-direct-tip.nodes \
    | sha256sum
  wc -l /tmp/price-truth-direct-tip.nodes
  ```

  Expected: `70 passed`, exactly `+7/-0`; all existing direct node IDs survive.

- [ ] **Step 7: Commit collector truth.**

  ```bash
  git add src/market_data_direct.py tests/test_market_data_direct.py \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "fix: derive price collection partial truth"
  ```

## 9. Task 2 - Worker RED And GREEN

**Files:**
- Modify: `tests/test_prices_runtime.py`
- Modify: `src/prices_runtime.py`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add a valid result factory and four exact RED nodes.**

  Add this non-test helper:

  ```python
  def _collector_result(*, status="succeeded", scanned=2, errors=None, unresolved=None):
      errors = errors or {}
      unresolved = unresolved or []
      return {
          "status": status,
          "provider": "ibkr",
          "tickers_scanned": scanned,
          "succeeded_ticker_count": scanned - len(errors),
          "gaps_found": len(unresolved),
          "rows_added": 26 if status == "succeeded" else 1,
          "errors": errors,
          "unresolved_after_fetch_count": len(unresolved),
          "unresolved_after_fetch_tickers": unresolved,
      }
  ```

  Add these tests:

  ```python
  def test_prices_worker_prints_sanitized_partial_json_and_exits_zero(monkeypatch, capsys):
      from src import prices_runtime as worker
      monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
      monkeypatch.setattr(
          worker, "_run_worker",
          lambda **kwargs: _collector_result(
              status="partial", errors={"LCID": "PRIVATE_PROVIDER_TEXT"},
              unresolved=["LCID"],
          ),
      )
      assert worker.main(["--tickers", "AAPL,LCID"]) == 0
      payload = json.loads(capsys.readouterr().out)
      assert payload == {
          "status": "partial", "provider": "ibkr", "tickers_scanned": 2,
          "succeeded_ticker_count": 1, "gaps_found": 1, "rows_added": 1,
          "error_count": 1, "error_tickers": ["LCID"],
          "unresolved_after_fetch_count": 1,
          "unresolved_after_fetch_tickers": ["LCID"],
      }
      assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(payload)


  def test_prices_worker_prints_sanitized_failed_result_json_and_exits_nonzero(
      monkeypatch, capsys,
  ):
      from src import prices_runtime as worker
      monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
      monkeypatch.setattr(
          worker, "_run_worker",
          lambda **kwargs: _collector_result(
              status="failed", scanned=2,
              errors={"BAD": "PRIVATE_A", "LCID": "PRIVATE_B"},
              unresolved=["LCID"],
          ),
      )
      assert worker.main(["--tickers", "BAD,LCID"]) == 1
      payload = json.loads(capsys.readouterr().out)
      assert payload["status"] == "failed"
      assert payload["error_count"] == 2
      assert payload["succeeded_ticker_count"] == 0
      assert payload["error_tickers"] == ["BAD", "LCID"]
      assert "PRIVATE_" not in json.dumps(payload)


  def test_prices_worker_rejects_unknown_status_and_malformed_counts(monkeypatch, capsys):
      from src import prices_runtime as worker
      invalid = _collector_result()
      invalid["status"] = "complete"
      with pytest.raises(ValueError, match="status"):
          worker.sanitize_result(invalid)
      for value in (-1, 1.5, True, "2"):
          invalid = _collector_result()
          invalid["rows_added"] = value
          with pytest.raises(ValueError, match="rows_added"):
              worker.sanitize_result(invalid)
      monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
      monkeypatch.setattr(
          worker, "_run_worker",
          lambda **kwargs: {**_collector_result(), "status": "PRIVATE_STATUS"},
      )
      assert worker.main(["--tickers", "AAPL,NVDA"]) == 1
      payload = json.loads(capsys.readouterr().out)
      assert payload["status"] == "failed"
      assert payload["error_class"] == "ValueError"
      assert "PRIVATE_STATUS" not in json.dumps(payload)


  def test_prices_worker_bounds_sorts_and_sanitizes_ticker_lists():
      from src import prices_runtime as worker
      tickers = [f"T{i:02d}" for i in range(30)]
      result = _collector_result(
          status="failed", scanned=30,
          errors={ticker: "PRIVATE" for ticker in reversed(tickers)},
          unresolved=list(reversed(tickers)),
      )
      payload = worker.sanitize_result(result)
      assert payload["error_count"] == 30
      assert payload["unresolved_after_fetch_count"] == 30
      assert payload["error_tickers"] == tickers[:25]
      assert payload["unresolved_after_fetch_tickers"] == tickers[:25]
      for malformed_ids in (["AAPL\nPRIVATE"], [123]):
          malformed = {
              **result,
              "unresolved_after_fetch_tickers": malformed_ids,
              "unresolved_after_fetch_count": len(malformed_ids),
          }
          with pytest.raises(ValueError, match="unresolved_after_fetch_tickers"):
              worker.sanitize_result(malformed)
  ```

- [ ] **Step 2: Evolve the two existing worker nodes in place.**

  `test_prices_worker_prints_sanitized_success_json` must return
  `_collector_result(status="succeeded", errors={}, unresolved=[])`, require
  every new count field, and require no raw error. Keep its node ID.

  `test_prices_worker_prints_sanitized_error_json` keeps the exact retryable
  lock-busy message and exit `1`, then adds one non-retryable exception case
  whose planted message is absent and whose class remains present. Keep both
  cases inside the same existing node.

- [ ] **Step 3: Run worker RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_prices_runtime.py
  ```

  Expected before implementation: partial is hard-coded to succeeded, failed
  result exits zero, malformed counts are coerced, and new fields are absent.
  All failures must be contract assertions, not argparse or fixture failures.

- [ ] **Step 4: Implement Section 5.3 exactly.**

  Keep `_run_worker()` and provider arguments unchanged. Validate all facts
  before serializing; strip per-ticker error values; preserve only the stable
  lock-busy diagnostic needed by scheduler skip classification.

- [ ] **Step 5: Run worker and direct GREEN.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_prices_runtime.py \
    tests/test_market_data_direct.py
  ```

  Expected: `78 passed` (`8 + 70`).

- [ ] **Step 6: Commit the worker boundary.**

  ```bash
  git add src/prices_runtime.py tests/test_prices_runtime.py \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "fix: preserve price worker outcome truth"
  ```

## 10. Task 3 - Scheduler RED And GREEN

**Files:**
- Modify: `tests/test_data_scheduler.py`
- Modify: `src/service/data_scheduler.py`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add scheduler price-payload and audit helpers.**

  Add near the existing prices-worker tests:

  ```python
  def _scheduled_price_payload(
      *, status="succeeded", scanned=2, errors=0, unresolved=0,
  ):
      unresolved_tickers = ["LCID"][:unresolved]
      error_order = ["LCID", "BAD"] if unresolved else ["BAD", "LCID"]
      error_tickers = sorted(error_order[:errors])
      return {
          "status": status,
          "provider": "ibkr",
          "tickers_scanned": scanned,
          "succeeded_ticker_count": scanned - errors,
          "gaps_found": unresolved,
          "rows_added": 26 if status == "succeeded" else 1,
          "error_count": errors,
          "error_tickers": error_tickers,
          "unresolved_after_fetch_count": unresolved,
          "unresolved_after_fetch_tickers": unresolved_tickers,
          "error_class": "",
          "error": "",
          "retryable": False,
      }


  class _RecordingJobStore:
      def __init__(self):
          self.created = []
          self.finished = []

      def create_run(self, name, **kwargs):
          self.created.append((name, kwargs))
          return len(self.created)

      def finish_run(self, run_id, **kwargs):
          self.finished.append((run_id, kwargs))
          return True


  def _install_recording_job_store(monkeypatch):
      store = _RecordingJobStore()
      monkeypatch.setattr(
          "src.service.job_runs_store.JobRunsLocalStore",
          lambda profile_db: store,
      )
      return store
  ```

- [ ] **Step 2: Add the two strict parser RED nodes.**

  ```python
  def test_prices_worker_stdout_parser_preserves_partial_truth_and_bounded_tickers():
      raw = _scheduled_price_payload(
          status="partial", scanned=30, errors=1, unresolved=1,
      )
      raw["succeeded_ticker_count"] = 29
      raw["error_tickers"] = ["LCID"]
      raw["unresolved_after_fetch_tickers"] = ["LCID"]
      parsed = ds._parse_sanitized_prices_worker_stdout(json.dumps(raw))
      assert parsed == raw


  def test_prices_worker_stdout_parser_rejects_malformed_partial_payloads():
      valid = _scheduled_price_payload(status="partial", errors=1, unresolved=1)
      invalid = [
          {**valid, "status": "complete"},
          {**valid, "provider": "PRIVATE_PROVIDER"},
          {**valid, "rows_added": -1},
          {**valid, "error_count": True},
          {**valid, "succeeded_ticker_count": 2},
          {**valid, "unresolved_after_fetch_count": 2},
          {**valid, "error_tickers": "LCID"},
          {**valid, "error_tickers": ["LCID"] * 26},
          {**valid, "error_tickers": [123]},
          {**valid, "unresolved_after_fetch_tickers": ["LCID\nPRIVATE"]},
      ]
      for payload in invalid:
          assert ds._parse_sanitized_prices_worker_stdout(json.dumps(payload)) is None
  ```

  The first node uses one exposed ticker and full count one. The separate
  30-item cap is already owned by the worker node; scheduler owns validation
  and preservation of a bounded payload, not a second independent truncation
  policy.

- [ ] **Step 3: Add the four scheduler outcome RED nodes.**

  ```python
  def test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation(
      monkeypatch,
  ):
      store = _install_recording_job_store(monkeypatch)
      monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "LCID"])
      monkeypatch.setattr(
          ds, "_run_sanitized_prices_worker_subprocess",
          lambda argv: {
              "returncode": 0,
              "payload": _scheduled_price_payload(
                  status="partial", errors=1, unresolved=1,
              ),
          },
      )
      result = ds.run_source("ibkr_prices", trigger_source="api")
      assert result["status"] == "partial"
      assert result["collect"]["succeeded_ticker_count"] == 1
      assert result["collect"]["unresolved_after_fetch_tickers"] == ["LCID"]
      durable = ds._state_store().get("ibkr_prices")
      assert durable["last_status"] == "partial"
      assert durable["last_error"] is None
      assert durable["continuation"] is None
      _, finished = store.finished[-1]
      assert finished["status"] == "failed"
      assert finished["error"] == "price_collection_partial"
      assert finished["message"] == "price_collection_partial"
      assert finished["result"]["status"] == "partial"


  def test_prices_failed_payload_persists_failed_without_partial(monkeypatch):
      store = _install_recording_job_store(monkeypatch)
      monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["BAD", "LCID"])
      monkeypatch.setattr(
          ds, "_run_sanitized_prices_worker_subprocess",
          lambda argv: {
              "returncode": 1,
              "payload": _scheduled_price_payload(
                  status="failed", errors=2, unresolved=1,
              ),
          },
      )
      result = ds.run_source("ibkr_prices", trigger_source="api")
      assert result["status"] == "failed"
      assert result["collect"]["status"] == "failed"
      durable = ds._state_store().get("ibkr_prices")
      assert durable["last_status"] == "failed"
      assert durable["continuation"] is None
      _, finished = store.finished[-1]
      assert finished["status"] == "failed"
      assert finished["error"] == "price_collection_failed"


  def test_prices_success_clears_prior_partial_and_preserves_audit_history(monkeypatch):
      store = _install_recording_job_store(monkeypatch)
      monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "LCID"])
      steps = iter([
          {
              "returncode": 0,
              "payload": _scheduled_price_payload(
                  status="partial", errors=1, unresolved=1,
              ),
          },
          {
              "returncode": 0,
              "payload": _scheduled_price_payload(status="succeeded"),
          },
      ])
      monkeypatch.setattr(
          ds, "_run_sanitized_prices_worker_subprocess", lambda argv: next(steps),
      )
      assert ds.run_source("ibkr_prices")["status"] == "partial"
      assert ds.run_source("ibkr_prices")["status"] == "succeeded"
      durable = ds._state_store().get("ibkr_prices")
      assert durable["last_status"] == "succeeded"
      assert durable["last_error"] is None
      assert durable["continuation"] is None
      assert [kwargs["status"] for _, kwargs in store.finished] == [
          "failed", "succeeded",
      ]
      assert store.finished[0][1]["error"] == "price_collection_partial"
      assert store.finished[1][1]["error"] is None


  def test_price_partial_projection_does_not_change_normalized_news_audit_status(
      monkeypatch,
  ):
      import src.news_normalized.routing as routing
      store = _install_recording_job_store(monkeypatch)
      _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED)
      monkeypatch.setattr(
          ds, "_run_normalized_news_writer",
          lambda *args, **kwargs: {"status": "partial", "continuation": None},
      )
      result = ds.run_source("polygon_news", trigger_source="api")
      assert result["status"] == "partial"
      assert ds._state_store().get("polygon_news")["continuation"] is None
      _, finished = store.finished[-1]
      assert finished["status"] == "succeeded"
      assert finished["error"] is None
  ```

- [ ] **Step 4: Evolve the five existing scheduler nodes in place.**

  Use a fully valid `_scheduled_price_payload()` in both subprocess-launch
  nodes and in `test_price_scope_required`. Extend
  `test_prices_worker_stdout_parse_preserves_retryable_and_counts` to require
  all new fields and closed status while retaining the exception lock-busy
  case. Keep
  `test_prices_worker_retryable_lock_busy_is_skip_not_failure` unchanged except
  for any parser-required exception-envelope field. No node may be renamed.

- [ ] **Step 5: Run scheduler RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_data_scheduler.py
  ```

  Expected before implementation: strict parser cases fail; return-code-zero
  partial becomes succeeded; the audit projection is succeeded; a later
  success/history sequence lacks the required first failed audit. Normalized
  news must remain green.

- [ ] **Step 6: Implement Section 5.4 exactly.**

  Preserve the exception envelope and lock-busy skip. Treat payload status as
  semantic truth. Keep `price_partial` local to the prices branch and use a
  separate audit error so durable partial has no fabricated continuation or
  raw diagnostic.

- [ ] **Step 7: Run all backend focused tests and collect exact nodes.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-be-focused-tip.nodes \
    | sha256sum
  wc -l /tmp/price-truth-be-focused-tip.nodes
  comm -13 /tmp/price-truth-be-focused.nodes /tmp/price-truth-be-focused-tip.nodes
  comm -23 /tmp/price-truth-be-focused.nodes /tmp/price-truth-be-focused-tip.nodes
  ```

  Expected: `168 passed`; hash
  `9faa90281df39dddccf7bedf3ad2ad7304341560c00dea8ff8b9dd887f5e55a3`;
  exact `+17/-0` with only Section 3.1 additions.

- [ ] **Step 8: Commit scheduler projection.**

  ```bash
  git add src/service/data_scheduler.py tests/test_data_scheduler.py \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "fix: project price partial through scheduler"
  ```

## 11. Task 4 - Frontend RED And GREEN

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add the pure display RED node.**

  Add inside `describe("schedulerStateLabel", ...)`:

  ```typescript
  it("renders price unresolved count and bounded ticker list without continuation", () => {
    const durable = {
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_prices",
        status: "partial",
        collect: {
          status: "partial" as const,
          tickers_scanned: 150,
          succeeded_ticker_count: 149,
          unresolved_after_fetch_count: 1,
          unresolved_after_fetch_tickers: ["LCID"],
        },
      },
    };
    expect(localizedSchedulerStateLabel(durable, zhT)).toEqual({
      label: "部分完成（抓取後仍有 1 個標的無法確認：LCID）",
      tone: "warn",
      needsContinue: false,
    });
    expect(localizedSchedulerStateLabel(durable, settingsT("en"))).toEqual({
      label: "Partially completed (1 ticker remains unresolved after collection: LCID)",
      tone: "warn",
      needsContinue: false,
    });
    const nonPrice = {
      ...durable,
      last_result: { ...durable.last_result, source: "polygon_news" },
    };
    expect(localizedSchedulerStateLabel(nonPrice, zhT).label).toBe("部分完成");
  });
  ```

- [ ] **Step 2: Add the mounted bilingual RED node and bounded fixture mode.**

  Place the fixture changes and new node inside the existing
  `describe("Settings provider config authority", ...)` block; the exact node
  ID in Section 3.2 includes that prefix.

  Add to `mocked`:

  ```typescript
  priceScheduleMode: "blank" as "blank" | "partial",
  ```

  In the `ibkr_prices` schedule fixture, derive `last_result` and
  `durable_state` from that mode:

  ```typescript
  last_result: mocked.priceScheduleMode === "partial" ? {
    source: "ibkr_prices",
    status: "partial",
    collect: {
      status: "partial",
      tickers_scanned: 150,
      succeeded_ticker_count: 149,
      gaps_found: 150,
      rows_added: 3874,
      error_count: 1,
      error_tickers: ["LCID"],
      unresolved_after_fetch_count: 1,
      unresolved_after_fetch_tickers: ["LCID"],
    },
  } : null,
  durable_state: mocked.priceScheduleMode === "partial" ? {
    last_status: "partial",
    last_error: null,
    continuation: null,
    last_result: {
      source: "ibkr_prices",
      status: "partial",
      collect: {
        status: "partial",
        tickers_scanned: 150,
        succeeded_ticker_count: 149,
        gaps_found: 150,
        rows_added: 3874,
        error_count: 1,
        error_tickers: ["LCID"],
        unresolved_after_fetch_count: 1,
        unresolved_after_fetch_tickers: ["LCID"],
      },
    },
    last_attempt: "2026-07-28T00:19:00Z",
    updated_at: "2026-07-28T00:22:00Z",
  } : null,
  ```

  Reset `mocked.priceScheduleMode = "blank"` in `afterEach`. Add the exact node:

  ```typescript
  it("renders price partial facts without a Continue control in both locales", async () => {
    mocked.priceScheduleMode = "partial";
    const jobs = health.jobs as Record<string, {
      status: string; finished_at: string; error: string;
    }>;
    jobs["collect.ibkr_prices"] = {
      status: "failed",
      finished_at: "2026-07-28T00:22:00Z",
      error: "price_collection_partial",
    };
    try {
      await renderDataSources();
      const row = () => Array.from(host!.querySelectorAll("tr")).find((node) =>
        node.textContent?.includes(
          i18n.language === "en" ? "IBKR Prices" : "IBKR 股價",
        ));
      expect(row()?.textContent).toContain("✗");
      expect(row()?.textContent)
        .toContain("部分完成（抓取後仍有 1 個標的無法確認：LCID）");
      expect(Array.from(row()!.querySelectorAll("button")).some((button) =>
        button.textContent?.trim() === "補抓")).toBe(false);

      await act(async () => { await i18n.changeLanguage("en"); });
      expect(row()?.textContent).toContain("✗");
      expect(row()?.textContent).toContain(
        "Partially completed (1 ticker remains unresolved after collection: LCID)",
      );
      expect(Array.from(row()!.querySelectorAll("button")).some((button) =>
        button.textContent?.trim() === "Continue")).toBe(false);
    } finally {
      delete jobs["collect.ibkr_prices"];
    }
  });
  ```

- [ ] **Step 3: Evolve the resource count node without renaming it.**

  Change only these expected values:

  ```typescript
  settings: 706,
  // ...
  expect(total, `${locale}.total`).toBe(1785);
  ```

  Explore stays `380`; every other subtree count stays exact.

- [ ] **Step 4: Run frontend RED.**

  ```bash
  cd apps/arkscope-web
  npx vitest run \
    src/marketDataDisplay.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/i18n/resources.test.ts
  ```

  Expected before implementation: the two new nodes fail on the generic
  partial label and missing DTO/resources; the evolved resource count fails by
  exactly two leaves per locale.

- [ ] **Step 5: Implement Section 5.5 exactly.**

  Keep `DataSourcesSection.tsx` byte-identical. The dedicated branch must be
  source-exact (`ibkr_prices`), status-exact (`partial`), require a positive
  count plus at least one bounded ticker, and return `needsContinue=false`.

- [ ] **Step 6: Run focused frontend GREEN and inventory.**

  ```bash
  cd apps/arkscope-web
  npx vitest run \
    src/marketDataDisplay.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/i18n/resources.test.ts
  npx vitest list --json \
    | jq -r '.[] | [.file,.name] | @tsv' \
    | sed "s#$(pwd)/##" \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-fe-full-tip.nodes \
    | sha256sum
  awk -F '\t' \
    '$1=="src/SettingsProviderConfig.test.ts" || \
     $1=="src/i18n/resources.test.ts" || \
     $1=="src/marketDataDisplay.test.ts"' \
    /tmp/price-truth-fe-full-tip.nodes \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-fe-focused-tip.nodes \
    | sha256sum
  wc -l /tmp/price-truth-fe-focused-tip.nodes
  cd ../..
  ```

  Expected: `88 passed`; full `1076` hash
  `de48671aa1d3f70cb87166e3f5b026804e206ac31f8e29fe7e74b38cde9448d5`;
  focused hash
  `b6f01cae4038c5c94f51da05ad920e52b723c387c6f48938f7dce6a13b028e4f`;
  exact `+2/-0`; Settings `706`, Explore `380`, total `1785`.

- [ ] **Step 7: Run frontend static gates.**

  ```bash
  cd apps/arkscope-web
  npm run check:i18n-literals
  npm run check:i18n-literals
  npm run typecheck
  npm run build
  cd ../..
  ```

  Expected: scanner twice `36/20/0/20`; typecheck and build exit zero.

- [ ] **Step 8: Commit frontend truth.**

  ```bash
  git add \
    apps/arkscope-web/src/api.ts \
    apps/arkscope-web/src/marketDataDisplay.ts \
    apps/arkscope-web/src/marketDataDisplay.test.ts \
    apps/arkscope-web/src/SettingsProviderConfig.test.ts \
    apps/arkscope-web/src/i18n/resources/en/settings.ts \
    apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts \
    apps/arkscope-web/src/i18n/resources.test.ts \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "feat: show unresolved price collection facts"
  ```

## 12. Task 5 - Mutation, Boundary, And Full Verification

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
- Modify: `docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md`
- Modify: `docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Run the eight independent mutation probes.**

  Apply one mutation at a time with `apply_patch`, run only its owning node,
  reverse that exact patch with `apply_patch`, and verify the product-file blob
  returns to its pre-mutation SHA. Record command, RED node, and restored blob.

  | Mutation | Required RED owner |
  |---|---|
  | Return `[]` without executing `_unresolved_price_target_dates` | `test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target` |
| Force a zero-row ticker to bypass target reconciliation and imply success | `test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target` |
  | Change day presence to require 26 stored rows | `test_backfill_one_row_low_volume_day_stays_succeeded` |
  | Pass `error=None` for an unresolved ticker | `test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target` |
  | Hard-code worker status to `succeeded` | `test_prices_worker_prints_sanitized_partial_json_and_exits_zero` |
  | Ignore payload partial when return code is zero | `test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation` |
  | Persist price partial audit as succeeded | `test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation` |
  | Remove the frontend price-unresolved branch | both new frontend nodes |

  The 26-row mutation must affect the target/day-presence predicate, not merely
  add a dead condition after an empty target set. The one-row node must turn
  RED for the semantic reason. Preserve the exact temporary diff for this
  mutation in the evidence packet so review can prove that target
  classification, rather than only `_unresolved_price_target_dates()` on an
  already-empty target set, was changed.

- [ ] **Step 2: Reproduce exact final collections and comms.**

  Run Section 2.1, writing `*-tip.nodes`, copy the backend stream to
  `$PRICE_TRUTH_TIER_ROOT/tip.nodes`, then:

  ```bash
  comm -13 /tmp/price-truth-be-full.nodes /tmp/price-truth-be-full-tip.nodes
  comm -23 /tmp/price-truth-be-full.nodes /tmp/price-truth-be-full-tip.nodes
  comm -13 /tmp/price-truth-fe-full.nodes /tmp/price-truth-fe-full-tip.nodes
  comm -23 /tmp/price-truth-fe-full.nodes /tmp/price-truth-fe-full-tip.nodes
  ```

  Expected backend: `4739`, hash
  `a72bbd36dfad3d36aee2e6630e6024ec9fb4e910bebaf1363d44df8a1aa204dd`,
  exact `+17/-0`. Expected frontend: `96/1076`, hash
  `de48671aa1d3f70cb87166e3f5b026804e206ac31f8e29fe7e74b38cde9448d5`,
  exact `+2/-0`.

- [ ] **Step 3: Run focused and tiered backend gates.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py
  ```

  Expected focused: `168 passed`.

  Run only Section 2.2's side-collection and **Runtime side command**
  subsections with `SIDE=tip`, reusing the exact pinned runner, reporter,
  `build_tiers.py`, all five probe artifacts, `tier-map.tsv`, and `T?.paths`.
  Do not repeat fresh-root initialization, mandatory probes, or mutations.
  First write the canonical 4,739-node stream to
  `$PRICE_TRUTH_TIER_ROOT/tip.nodes`; prove its unique file set is exactly the
  mapped 253 paths and its tier union is exact with no duplicates. Create the
  tip preflight only after those artifacts exist, then invoke the single
  `run-side` command. Runtime constants, classifier, environment, sequencing,
  banking, and deferred retry must be byte-identical to base.

  Compare only the aggregate files emitted from complete selected attempts:

  ```bash
  sha256sum "$PRICE_TRUTH_TIER_ROOT/tip-nonpassing.nodes"
  comm -13 \
    "$PRICE_TRUTH_TIER_ROOT/base-nonpassing.nodes" \
    "$PRICE_TRUTH_TIER_ROOT/tip-nonpassing.nodes"
  comm -23 \
    "$PRICE_TRUTH_TIER_ROOT/base-nonpassing.nodes" \
    "$PRICE_TRUTH_TIER_ROOT/tip-nonpassing.nodes"
  ```

  Expected new tiered non-passing IDs from `comm -13`: none. Every disappeared
  ID from `comm -23` is recorded as an environment observation, not claimed as
  this slice's fix unless the changed files causally own it. A stalled or
  invalid tip tier leaves the tip incomplete under Stop Condition 11; its
  partial transcript cannot enter the A/B comparison.

  After the complete tip-side result, invoke `run-diagnostic` with the same
  tip preflight. State explicitly that its process context is different from
  the tiered protocol and every historical monolithic run. Whatever its
  closed outcome, it is not an A/B input.

- [ ] **Step 4: Run frontend full and non-node gates.**

  ```bash
  cd apps/arkscope-web
  npm test -- --run
  npm run typecheck
  npm run build
  npm run check:i18n-literals
  npm run check:i18n-literals
  cd ../..

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_tools.py::TestRegistry::test_register_all \
    tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
    tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count \
    tests/test_pg_unreachable_e2e.py

  /home/hyl/.virtualenvs/llm_app/bin/python src/smoke/pg_unreachable_e2e.py
  ```

  Expected: frontend `96/1076` all green; scanner twice `36/20/0/20`;
  typecheck/build zero; tools `53/54/54`; no-PG `23/23`, `ok=true`,
  `pg_attempts=[]`.

- [ ] **Step 5: Prove byte-identical protected files and trees.**

  ```bash
  git diff --exit-code "$PLAN_REVIEW_CLEARANCE_COMMIT" -- \
    data_sources/ibkr_source.py \
    data_sources/polygon_source.py \
    src/market_coverage \
    src/service/provider_health.py \
    src/ibkr_gateway_lock.py \
    src/api/routes/market_data.py \
    src/data_provider_config.py \
    src/provider_config_runtime.py \
    sql \
    scripts \
    apps/arkscope-web/src/settings/DataSourcesSection.tsx
  ```

  Set `PLAN_REVIEW_CLEARANCE_COMMIT` to the full recorded SHA from Task 0 before
  running the command. Re-run the catalog script from Task 0 and compare exact
  JSON. Run the existing schema,
  coverage, provider-health, Gateway-lock, source-catalog, and interval tests:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py::test_provider_sync_runs_status_check_enforced_at_schema \
    tests/test_market_data_direct.py::test_provider_run_status_constrained_to_valid_set \
    tests/test_market_coverage_boundaries.py \
    tests/test_market_coverage_observations.py \
    tests/test_provider_health.py \
    tests/test_ibkr_gateway_lock.py \
    tests/test_data_scheduler.py::test_defaults_everything_disabled \
    tests/test_data_scheduler.py::test_scheduler_source_defs_have_no_legacy_collector_plumbing \
    tests/test_data_scheduler.py::test_is_due_matrix
  ```

- [ ] **Step 6: Prove shared frontend files changed only in allowed sections.**

  Review:

  ```bash
  git diff -U3 "$PLAN_REVIEW_CLEARANCE_COMMIT" -- \
    apps/arkscope-web/src/api.ts \
    apps/arkscope-web/src/marketDataDisplay.ts
  ```

  Require:

  ```text
  api.ts: only ScheduleRunResult.collect fields change
  marketDataDisplay.ts: only scheduler partial presentation changes
  coverage enums/functions/copy: byte-identical
  provider-health functions/copy: byte-identical
  ```

  In addition, run all existing Coverage V2 frontend nodes in
  `src/marketDataDisplay.test.ts`; they must remain green in the full focused
  file run.

- [ ] **Step 7: Complete the evidence packet and mark review-ready.**

  Record:

  1. every baseline and final node hash;
  2. exact backend `+17/-0` and frontend `+2/-0` comms;
  3. all 17 backend and two frontend additions by ID;
  4. all in-place evolved IDs;
  5. Settings `706`, Explore `380`, total `1785` with `+2/-0` keys;
  6. eight mutation commands and RED owners;
  7. full A/B non-passing node sets;
  8. scanner/tool/no-PG/typecheck/build results;
  9. protected blob/tree/catalog checks;
  10. explicit confirmation of zero provider, Gateway, scheduler, browser, and
      production-data interaction; and
  11. product tip full SHA.

  Update lifecycle headers to `IMPLEMENTATION REVIEW-READY - INDEPENDENT REVIEW
  NEXT` and add a newest-first priority-map entry with the exact final numbers.

- [ ] **Step 8: Commit review evidence.**

  ```bash
  git add \
    docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md \
    docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git diff --cached --check
  git commit -m "docs: record price collection truth evidence"
  git status --short
  ```

## 13. Task 6 - Independent Review And Integration Gate

**Files:**
- Modify only when resolving verified findings in files already owned by this plan.

- [ ] **Step 1: Request independent implementation review.**

  Provide the spec, plan, evidence packet, product base, clearance commit,
  product tip, exact node lists, and mutation records. Ask the reviewer to
  verify:

  ```text
  original target identity is not rederived
  provider fetch remains outside market_write_lock
  one-row low-volume does not become unresolved
  direct status is derived from distinct issue tickers
  unresolved meta preserves prior success and stable error
  worker/parser reject malformed status and counts
  scheduler reads payload status and keeps price continuation null
  price partial audit is failed while normalized-news audit is unchanged
  frontend count/list is source-exact, bilingual, and has no Continue
  exact node/resource/boundary ledgers close
  base and tip tier unions each equal their complete canonical collection
  the immutable builder/map and all eight tier commands are side-exact
  stalled tier output is never normalized or called passing
  tiered results are not compared with historical monolithic results
  ```

- [ ] **Step 2: Resolve findings RED-first.**

  For each verified finding, add or evolve a named test that fails for that
  finding, record its node-ledger effect, implement the minimum correction,
  rerun all gates, and request focused re-review. Do not absorb unrelated
  provider scheduling, extended-hours, pacing, structured adapter-outcome,
  EIR-002, or scripts-retirement work.

- [ ] **Step 3: Integrate only after GREEN and explicit user approval.**

  Use `superpowers:finishing-a-development-branch`. Verify master has not moved
  incompatibly, fast-forward merge the exact reviewed tip, and rerun canonical
  focused collections/tests plus frontend typecheck/build/scanner. Do not push
  unless separately requested.

## 14. Task 7 - Post-Merge Read-Only Observation

**Files:**
- Modify: lifecycle docs only after observed evidence is complete.

- [ ] **Step 1: Restart merged ArkScope without triggering collection.**

  Restart only after merge. Confirm the desktop/sidecar loads merged code. Do
  not press Run, change cadence, or start a provider probe.

- [ ] **Step 2: Capture read-only pre-run facts.**

  With both SQLite databases in `mode=ro`, record latest
  `collect.ibkr_prices`, LCID `provider_sync_meta`, LCID latest stored bar,
  2026-07-27 Coverage row, file size/mtime, `PRAGMA integrity_check`, and
  `PRAGMA foreign_key_check`. This is observation, not repair.

- [ ] **Step 3: Obtain explicit approval before any manual provider action.**

  The ordinary enabled scheduler cycle may occur naturally. A manual Run,
  provider/Gateway probe, cadence change, retry experiment, or LCID repair
  requires a fresh user approval immediately before execution.

- [ ] **Step 4: Accept either truthful terminal outcome.**

  ```text
  Resolved:
    LCID gains at least one 2026-07-27 row; current provider error clears;
    collection succeeds; Coverage may be complete or partial by slot truth.

  Still unresolved:
    LCID remains zero-row; last_success does not advance; current error is
    price_day_unresolved_after_fetch; collector/scheduler are partial with
    unresolved count 1; audit rows are failed; Coverage remains indeterminate.
  ```

  Neither outcome may claim which provider, pacing rule, halt, entitlement, or
  no-trade condition caused it.

- [ ] **Step 5: Close lifecycle docs only after bounded observation.**

  Record merged SHA, read-only before/after facts, the actual natural-run
  outcome, and unchanged non-target DB integrity. Mark the slice LIVE only when
  merged verification and this observation are complete. The next sequence
  remains EIR-002 and then root scripts retirement according to the priority
  map's current explicit decision. Calendar-aware price scheduling and
  extended-hours capture remain separate candidate slices until explicitly
  reprioritized.

## 15. Plan Self-Review Checklist

- [x] Every spec requirement in Sections 3, 5, 6, 7, 8, 9, and 10 maps to a
  task and a named test or boundary gate.
- [x] The backend ledger is exactly `+17/-0`; the frontend ledger is exactly
  `+2/-0`; resource leaves are exactly `+2/-0` per locale.
- [x] Items 3, 4, and 6 of spec Section 9.1 are separately named and cannot
  hide one another.
- [x] The fixed-26 mutation turns the one-row low-volume node RED.
- [x] Normalized-news audit behavior is explicitly tested unchanged.
- [x] No adapter, Coverage, schema, provider-health, scheduler-cadence, source
  catalog, Gateway lock, scripts, production DB, or repair work entered scope.
- [x] Eight immutable whole-file tiers cover the backend collection exactly;
  base and tip use one map and one closed outcome/retry protocol.
- [x] A stalled tier remains incomplete under Stop Condition 11, while
  completed tiers can be banked only under an unchanged identity.
- [x] The plan states that fresh-process tiered context and historical
  monolithic context are not directly comparable.
- [x] No plan step contains an unresolved implementation choice or an
  ungrounded external-market acceptance constant.
- [x] The exact v2 runner source is appendix-pinned, dual-role mode gating
  is explicit, all four mandatory probes pass, and all six control-plane
  mutations have one reproducible owning observation.

## Appendix A - Exact Deterministic Tier Runner

This appendix is executable source, not pseudocode. Section 2.2 owns its
extraction command and SHA-256.

<!-- PRICE_TRUTH_RUNNER_V2_BEGIN -->
```python
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROTOCOL_ID = "price-truth-tier-v2"
PLUGIN_MODULE = "price_truth_tier_runner"
REPORTER_MODULE = "arkscope_price_truth_tier_reporter"
PROGRESS_ENV = "PRICE_TRUTH_PROGRESS_FD"
FROZEN_V1_ROOT = Path("/tmp/price-truth-tier-v1")
RUNTIME_BOUNDS = {
    "dump_seconds": 120,
    "deadline_seconds": 150,
    "grace_seconds": 10,
}
PROBE_BOUNDS = {
    "dump_seconds": 2,
    "deadline_seconds": 3,
    "grace_seconds": 1,
}
EOF_EXIT_GRACE_SECONDS = 1
TERMINAL_SUMMARY_RE = re.compile(
    rb"(?m)^=+ .+ in [0-9.]+s =+\r?$"
)

_progress_fd: int | None = None
_progress_sequence = 0
_progress_active_nodeid: str | None = None


def _plugin_fd() -> int:
    if _progress_fd is None:
        raise RuntimeError("price-truth progress plugin is not configured")
    return _progress_fd


def _emit_progress(event: str, nodeid: str) -> None:
    global _progress_sequence
    fd = _plugin_fd()
    _progress_sequence += 1
    payload = {
        "child_monotonic_ns": time.monotonic_ns(),
        "event": event,
        "nodeid": nodeid,
        "schema_version": 1,
        "sequence": _progress_sequence,
    }
    encoded = (
        json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")
    pipe_buf = int(os.fpathconf(fd, "PC_PIPE_BUF"))
    if len(encoded) > pipe_buf:
        raise RuntimeError("price-truth progress event exceeds PIPE_BUF")
    if os.write(fd, encoded) != len(encoded):
        raise RuntimeError("short write to price-truth progress pipe")


def pytest_configure(config) -> None:
    global _progress_active_nodeid, _progress_fd, _progress_sequence
    raw = os.environ.get(PROGRESS_ENV)
    if raw is None or not raw.isdecimal():
        raise RuntimeError(f"{PROGRESS_ENV} must be a decimal file descriptor")
    fd = int(raw)
    if fd <= 2:
        raise RuntimeError(f"{PROGRESS_ENV} must not target a standard stream")
    try:
        metadata = os.fstat(fd)
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    except OSError as exc:
        raise RuntimeError(f"{PROGRESS_ENV} is not open") from exc
    if not stat.S_ISFIFO(metadata.st_mode):
        raise RuntimeError(f"{PROGRESS_ENV} must reference a pipe")
    if (flags & os.O_ACCMODE) == os.O_RDONLY:
        raise RuntimeError(f"{PROGRESS_ENV} must be writable")
    os.set_inheritable(fd, False)
    _progress_fd = fd
    _progress_sequence = 0
    _progress_active_nodeid = None


def pytest_runtest_logstart(nodeid, location) -> None:
    global _progress_active_nodeid
    if _progress_active_nodeid is not None:
        raise RuntimeError("price-truth progress start while an item is active")
    _emit_progress("logstart", str(nodeid))
    _progress_active_nodeid = str(nodeid)


def pytest_runtest_logfinish(nodeid, location) -> None:
    global _progress_active_nodeid
    value = str(nodeid)
    if _progress_active_nodeid != value:
        raise RuntimeError("price-truth progress finish does not match start")
    _emit_progress("logfinish", value)
    _progress_active_nodeid = None


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


def _artifact(preflight: dict[str, Any], role: str) -> Path:
    matches = [
        Path(item["path"])
        for item in preflight["artifacts"]
        if item["role"] == role
    ]
    if len(matches) != 1:
        raise RuntimeError(f"preflight role must be unique: {role}")
    return matches[0]


def _pip_freeze_sha256() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = sorted(result.stdout.decode("utf-8").splitlines())
    return _sha256_bytes(("".join(f"{line}\n" for line in lines)).encode())


def _verify_preflight(path: Path) -> dict[str, Any]:
    preflight = _load_json(path)
    required = {
        "artifact_root",
        "artifacts",
        "git_identity",
        "path",
        "pip_freeze_sha256",
        "protocol_id",
        "python",
        "python_version",
        "pytest_version",
        "repo",
        "schema_version",
        "side",
        "tiers",
    }
    if set(preflight) != required:
        raise RuntimeError("preflight keys do not match the closed schema")
    if preflight["schema_version"] != 1:
        raise RuntimeError("unsupported preflight schema")
    if preflight["protocol_id"] != PROTOCOL_ID:
        raise RuntimeError("preflight protocol mismatch")
    root = Path(preflight["artifact_root"]).resolve()
    if root == FROZEN_V1_ROOT:
        raise RuntimeError("the frozen v1 artifact root cannot be reused")
    if path.resolve().parent != root:
        raise RuntimeError("preflight must live in its artifact root")
    runner = _artifact(preflight, "runner").resolve()
    if Path(__file__).resolve() != runner:
        raise RuntimeError("run the copied runner recorded in preflight")
    roles: set[str] = set()
    for item in preflight["artifacts"]:
        if set(item) != {"path", "role", "sha256"}:
            raise RuntimeError("artifact entry does not match closed schema")
        role = item["role"]
        artifact_path = Path(item["path"])
        if not isinstance(role, str) or not role or role in roles:
            raise RuntimeError("artifact roles must be unique strings")
        roles.add(role)
        if not artifact_path.is_file():
            raise RuntimeError(f"preflight artifact is missing: {artifact_path}")
        if _sha256(artifact_path) != item["sha256"]:
            raise RuntimeError(f"preflight artifact changed: {artifact_path}")
    if preflight["python"] != sys.executable:
        raise RuntimeError("interpreter path changed")
    if preflight["python_version"] != sys.version:
        raise RuntimeError("interpreter version changed")
    import pytest

    if preflight["pytest_version"] != pytest.__version__:
        raise RuntimeError("pytest version changed")
    if preflight["pip_freeze_sha256"] != _pip_freeze_sha256():
        raise RuntimeError("dependency fingerprint changed")
    if preflight["path"] != os.environ.get("PATH", ""):
        raise RuntimeError("PATH changed")
    repo = Path(preflight["repo"]).resolve()
    git_identity = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    if git_identity != preflight["git_identity"]:
        raise RuntimeError("Git identity changed")
    if preflight["side"] not in {"base", "tip", "probe"}:
        raise RuntimeError("invalid preflight side")
    tiers = preflight["tiers"]
    if not isinstance(tiers, list):
        raise RuntimeError("preflight tiers must be a list")
    expected_tiers = [] if preflight["side"] == "probe" else list(range(8))
    observed_tiers = [item.get("tier") for item in tiers]
    if observed_tiers != expected_tiers:
        raise RuntimeError("preflight tier sequence is invalid")
    for item in tiers:
        if set(item) != {"nodes_role", "paths_role", "tier"}:
            raise RuntimeError("tier entry does not match closed schema")
        _artifact(preflight, item["nodes_role"])
        _artifact(preflight, item["paths_role"])
    if preflight["side"] != "probe":
        _verify_collection_partition(preflight)
    return preflight


def _worktree_data_entries(repo: Path) -> list[str]:
    data = repo / "data"
    if not data.is_dir():
        raise RuntimeError("isolated worktree data directory is missing")
    return sorted(
        str(path.relative_to(repo))
        for path in data.rglob("*")
    )


def _archive_worktree_data(repo: Path, trial: Path) -> list[str]:
    entries = _worktree_data_entries(repo)
    if not entries:
        return []
    data = repo / "data"
    destination = trial / "data-after"
    if destination.exists():
        raise RuntimeError("attempt data archive already exists")
    data.rename(destination)
    data.mkdir()
    if _worktree_data_entries(repo):
        raise RuntimeError("failed to restore empty worktree data directory")
    return entries


def _bounds(mode: str) -> dict[str, int]:
    if mode == "runtime":
        return dict(RUNTIME_BOUNDS)
    if mode == "probe":
        return dict(PROBE_BOUNDS)
    raise RuntimeError(f"unknown runner mode: {mode}")


def _dump_marker(dump_seconds: int) -> bytes:
    minutes, seconds = divmod(dump_seconds, 60)
    return f"Timeout (0:{minutes:02d}:{seconds:02d})!".encode("ascii")


def _child_env(
    preflight: dict[str, Any],
    trial: Path,
    report_path: Path,
    progress_write_fd: int,
) -> dict[str, str]:
    root = Path(preflight["artifact_root"])
    home = trial / "home"
    tmp = trial / "tmp"
    locks = trial / "locks"
    edgar = trial / "edgar"
    for directory in (home, tmp, locks, edgar):
        directory.mkdir(parents=True, exist_ok=False)
    return {
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
        "PRICE_TRUTH_TIER_REPORT": str(report_path),
        PROGRESS_ENV: str(progress_write_fd),
    }


def _process_identity(process: subprocess.Popen[bytes]) -> dict[str, int]:
    return {
        "pid": process.pid,
        "pgid": os.getpgid(process.pid),
        "sid": os.getsid(process.pid),
    }


def _identity_is_owned(identity: dict[str, int]) -> bool:
    return identity["pid"] == identity["pgid"] == identity["sid"]


def _timeline_event(event: str, **fields: Any) -> dict[str, Any]:
    return {
        "event": event,
        "monotonic_ns": time.monotonic_ns(),
        "wall_time_epoch": time.time(),
        **fields,
    }


def _terminate_direct_child(
    process: subprocess.Popen[bytes],
    timeline: list[dict[str, Any]],
) -> bool:
    if process.poll() is not None:
        return True
    process.terminate()
    timeline.append(_timeline_event("direct_child_sigterm"))
    try:
        process.wait(timeout=1)
        return True
    except subprocess.TimeoutExpired:
        process.kill()
        timeline.append(_timeline_event("direct_child_sigkill"))
        try:
            process.wait(timeout=1)
            return True
        except subprocess.TimeoutExpired:
            return False


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_group_exit(
    process: subprocess.Popen[bytes],
    pgid: int,
    timeout_seconds: int,
) -> tuple[int | None, bool]:
    deadline = time.monotonic_ns() + timeout_seconds * 1_000_000_000
    while True:
        returncode = process.poll()
        if not _process_group_exists(pgid):
            if returncode is None:
                try:
                    returncode = process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    return returncode, False
            return returncode, True
        if time.monotonic_ns() >= deadline:
            return returncode, False
        time.sleep(0.01)


def _terminate_owned_group(
    process: subprocess.Popen[bytes],
    expected_identity: dict[str, int] | None,
    grace_seconds: int,
    timeline: list[dict[str, Any]],
) -> tuple[int | None, bool, bool, bool]:
    if expected_identity is None or not _identity_is_owned(expected_identity):
        _terminate_direct_child(process, timeline)
        return process.poll(), False, False, False
    try:
        if process.poll() is None:
            current_identity = _process_identity(process)
            if current_identity != expected_identity:
                _terminate_direct_child(process, timeline)
                return process.poll(), False, False, False
    except ProcessLookupError:
        if _process_group_exists(expected_identity["pgid"]):
            return process.poll(), False, False, False
        return process.poll(), False, False, True
    pgid = expected_identity["pgid"]
    if not _process_group_exists(pgid):
        return process.poll(), False, False, True
    interrupted = True
    killed = False
    try:
        os.killpg(pgid, signal.SIGINT)
    except ProcessLookupError:
        return process.poll(), False, False, True
    timeline.append(_timeline_event("sigint", identity=expected_identity))
    returncode, group_gone = _wait_for_group_exit(
        process,
        pgid,
        grace_seconds,
    )
    if group_gone:
        timeline.append(
            _timeline_event("group_exit_after_sigint", returncode=returncode)
        )
        return returncode, interrupted, killed, True
    killed = True
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return process.poll(), interrupted, False, True
    timeline.append(_timeline_event("sigkill", identity=expected_identity))
    returncode, group_gone = _wait_for_group_exit(
        process,
        pgid,
        grace_seconds,
    )
    if group_gone:
        timeline.append(
            _timeline_event("group_exit_after_sigkill", returncode=returncode)
        )
        return returncode, interrupted, killed, True
    timeline.append(_timeline_event("cleanup_timeout"))
    return returncode, interrupted, killed, False


def _parse_progress_event(
    raw: bytes,
    expected_sequence: int,
    active_nodeid: str | None,
) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("malformed progress event") from exc
    required = {
        "child_monotonic_ns",
        "event",
        "nodeid",
        "schema_version",
        "sequence",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RuntimeError("progress event does not match closed schema")
    if payload["schema_version"] != 1:
        raise RuntimeError("progress schema mismatch")
    if payload["sequence"] != expected_sequence:
        raise RuntimeError("progress sequence mismatch")
    if not isinstance(payload["child_monotonic_ns"], int):
        raise RuntimeError("progress monotonic timestamp is not an integer")
    if not isinstance(payload["nodeid"], str) or not payload["nodeid"]:
        raise RuntimeError("progress nodeid is invalid")
    event = payload["event"]
    nodeid = payload["nodeid"]
    if event == "logstart":
        if active_nodeid is not None:
            raise RuntimeError("progress start arrived while an item is active")
        active_nodeid = nodeid
    elif event == "logfinish":
        if active_nodeid != nodeid:
            raise RuntimeError("progress finish does not match active item")
        active_nodeid = None
    else:
        raise RuntimeError("unknown progress event")
    return payload, active_nodeid


def _read_node_file(path: Path) -> list[str]:
    nodes = path.read_text(encoding="utf-8").splitlines()
    if nodes != sorted(set(nodes)):
        raise RuntimeError(f"node manifest is not sorted and unique: {path}")
    return nodes


def _verify_collection_partition(preflight: dict[str, Any]) -> None:
    canonical = _read_node_file(_artifact(preflight, "canonical_nodes"))
    map_entries: dict[str, tuple[int, int]] = {}
    for line in _artifact(preflight, "tier_map").read_text(
        encoding="utf-8"
    ).splitlines():
        fields = line.split("\t")
        if len(fields) != 3 or not fields[0].startswith("T"):
            raise RuntimeError("tier map row is malformed")
        try:
            tier = int(fields[0][1:])
            count = int(fields[1])
        except ValueError as exc:
            raise RuntimeError("tier map row is malformed") from exc
        path = fields[2]
        if tier not in range(8) or count <= 0 or not path:
            raise RuntimeError("tier map row is invalid")
        if path in map_entries:
            raise RuntimeError("tier map contains a duplicate path")
        map_entries[path] = (tier, count)
    all_nodes: list[str] = []
    all_paths: list[str] = []
    for tier in range(8):
        entry = _tier_entry(preflight, tier)
        paths = _artifact(preflight, entry["paths_role"]).read_text(
            encoding="utf-8"
        ).splitlines()
        if paths != sorted(set(paths)) or not paths:
            raise RuntimeError(f"tier paths are invalid: {tier}")
        nodes = _read_node_file(_artifact(preflight, entry["nodes_role"]))
        node_paths = [node.split("::", 1)[0] for node in nodes]
        if set(node_paths) != set(paths):
            raise RuntimeError(f"tier node/path membership differs: {tier}")
        for path in paths:
            mapped = map_entries.get(path)
            if mapped is None or mapped[0] != tier:
                raise RuntimeError(f"tier map assignment differs: {path}")
            if (
                preflight["side"] == "base"
                and node_paths.count(path) != mapped[1]
            ):
                raise RuntimeError(f"base tier map count differs: {path}")
        all_nodes.extend(nodes)
        all_paths.extend(paths)
    if all_paths != list(dict.fromkeys(all_paths)):
        raise RuntimeError("tier paths are not globally unique")
    if set(all_paths) != set(map_entries):
        raise RuntimeError("tier path union differs from tier map")
    if len(all_nodes) != len(set(all_nodes)):
        raise RuntimeError("tier node union contains duplicates")
    if sorted(all_nodes) != canonical:
        raise RuntimeError("tier node union differs from canonical collection")


def _validate_natural_result(
    returncode: int,
    transcript: Path,
    report_path: Path,
    expected_nodes_path: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    transcript_bytes = transcript.read_bytes()
    terminal_summary = bool(TERMINAL_SUMMARY_RE.search(transcript_bytes))
    details: dict[str, Any] = {
        "terminal_summary": terminal_summary,
        "transcript_sha256": _sha256(transcript),
    }
    if returncode not in {0, 1} or not terminal_summary:
        return "invalid", [], details
    if not report_path.is_file():
        return "invalid", [], details
    report = _load_json(report_path)
    details["report_sha256"] = _sha256(report_path)
    required = {
        "collected_node_ids",
        "exitstatus",
        "nonpassing_node_ids",
        "schema_version",
        "seen_node_ids",
    }
    if set(report) != required or report["schema_version"] != 1:
        return "invalid", [], details
    expected = _read_node_file(expected_nodes_path)
    collected = report["collected_node_ids"]
    seen = report["seen_node_ids"]
    nonpassing = report["nonpassing_node_ids"]
    if (
        report["exitstatus"] != returncode
        or collected != expected
        or seen != expected
        or not isinstance(nonpassing, list)
        or nonpassing != sorted(set(nonpassing))
        or any(node not in expected for node in nonpassing)
    ):
        return "invalid", [], details
    if returncode == 0 and not nonpassing:
        return "complete_pass", [], details
    if returncode == 1 and nonpassing:
        return "complete_nonpassing", nonpassing, details
    return "invalid", [], details


def _bank_identity(
    preflight_path: Path,
    preflight: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    return {
        "canonical_nodes_sha256": _sha256(
            _artifact(preflight, "canonical_nodes")
        ),
        "environment_names": sorted(
            _child_env_names()
        ),
        "git_identity": preflight["git_identity"],
        "mode": mode,
        "pip_freeze_sha256": preflight["pip_freeze_sha256"],
        "preflight_sha256": _sha256(preflight_path),
        "protocol_id": PROTOCOL_ID,
        "python": preflight["python"],
        "reporter_sha256": _sha256(_artifact(preflight, "reporter")),
        "runner_sha256": _sha256(_artifact(preflight, "runner")),
        "side": preflight["side"],
        "tier_map_sha256": _sha256(_artifact(preflight, "tier_map")),
    }


def _child_env_names() -> set[str]:
    return {
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
        "PRICE_TRUTH_TIER_REPORT",
        PROGRESS_ENV,
        "PYTHONHASHSEED",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "TMPDIR",
        "TZ",
        "XDG_CACHE_HOME",
    }


def _run_attempt(
    *,
    preflight_path: Path,
    preflight: dict[str, Any],
    trial: Path,
    cwd: Path,
    selectors_: list[str],
    expected_nodes_path: Path,
    mode: str,
    label: str,
    tier: int | None,
    attempt: int,
) -> dict[str, Any]:
    verified_preflight = _verify_preflight(preflight_path)
    if verified_preflight != preflight:
        raise RuntimeError("preflight changed before attempt launch")
    bank_identity = _bank_identity(preflight_path, preflight, mode)
    bounds = _bounds(mode)
    repo = Path(preflight["repo"])
    data_before = _worktree_data_entries(repo)
    if data_before:
        raise RuntimeError(f"worktree data is not empty: {data_before}")
    trial.mkdir(parents=True, exist_ok=False)
    transcript = trial / "transcript.txt"
    report_path = trial / "report.json"
    progress_path = trial / "progress.jsonl"
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    env = _child_env(preflight, trial, report_path, write_fd)
    if set(env) != _child_env_names():
        raise RuntimeError("child environment names changed")
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
        PLUGIN_MODULE,
        *selectors_,
    ]
    started_wall = time.time()
    started_mono = time.monotonic_ns()
    deadline_ns = started_mono + bounds["deadline_seconds"] * 1_000_000_000
    phase = "pre_first_node"
    active_nodeid: str | None = None
    expected_sequence = 1
    progress_count = 0
    last_progress: dict[str, Any] | None = None
    window_offset = 0
    pipe_buffer = b""
    pipe_eof = False
    child_exit_observed_ns: int | None = None
    timeline = [_timeline_event("launch_requested", label=label)]
    outcome = "invalid"
    returncode: int | None = None
    interrupted = False
    killed = False
    cleanup_complete = False
    dump_present = False
    invalid_reason: str | None = None
    nonpassing_path: Path | None = None
    nonpassing_count: int | None = None
    process: subprocess.Popen[bytes] | None = None
    identity: dict[str, int] | None = None
    selector = selectors.DefaultSelector()
    try:
        with transcript.open("wb") as transcript_handle, progress_path.open(
            "w", encoding="utf-8"
        ) as progress_handle:
            process = subprocess.Popen(
                args,
                cwd=cwd,
                env=env,
                stdout=transcript_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=(write_fd,),
            )
            os.close(write_fd)
            write_fd = -1
            identity = _process_identity(process)
            timeline.append(_timeline_event("launched", identity=identity))
            if not _identity_is_owned(identity):
                invalid_reason = "process_group_identity_mismatch"
                cleanup_complete = _terminate_direct_child(process, timeline)
            else:
                selector.register(read_fd, selectors.EVENT_READ)
                while invalid_reason is None and returncode is None:
                    now_ns = time.monotonic_ns()
                    remaining = max(0, deadline_ns - now_ns) / 1_000_000_000
                    events = selector.select(timeout=min(remaining, 0.1))
                    deadline_due = time.monotonic_ns() >= deadline_ns
                    for key, _ in (() if deadline_due else events):
                        while True:
                            try:
                                chunk = os.read(key.fd, 65536)
                            except BlockingIOError:
                                break
                            if not chunk:
                                pipe_eof = True
                                selector.unregister(key.fd)
                                break
                            pipe_buffer += chunk
                            while b"\n" in pipe_buffer:
                                raw, pipe_buffer = pipe_buffer.split(b"\n", 1)
                                received_mono = time.monotonic_ns()
                                if received_mono >= deadline_ns:
                                    deadline_due = True
                                    break
                                try:
                                    payload, active_nodeid = _parse_progress_event(
                                        raw,
                                        expected_sequence,
                                        active_nodeid,
                                    )
                                except RuntimeError as exc:
                                    invalid_reason = str(exc)
                                    break
                                transcript_handle.flush()
                                window_offset = os.fstat(
                                    transcript_handle.fileno()
                                ).st_size
                                enriched = {
                                    **payload,
                                    "runner_received_at_epoch": time.time(),
                                    "runner_received_monotonic_ns": received_mono,
                                    "transcript_offset": window_offset,
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
                                last_progress = enriched
                                expected_sequence += 1
                                phase = (
                                    "active_node"
                                    if payload["event"] == "logstart"
                                    else "post_last_progress"
                                )
                                deadline_ns = (
                                    received_mono
                                    + bounds["deadline_seconds"]
                                    * 1_000_000_000
                                )
                            if (
                                invalid_reason is not None
                                or pipe_eof
                                or deadline_due
                            ):
                                break
                    if invalid_reason is not None:
                        (
                            returncode,
                            interrupted,
                            killed,
                            cleanup_complete,
                        ) = _terminate_owned_group(
                            process,
                            identity,
                            bounds["grace_seconds"],
                            timeline,
                        )
                        break
                    deadline_due = (
                        deadline_due or time.monotonic_ns() >= deadline_ns
                    )
                    if deadline_due:
                        transcript_handle.flush()
                        transcript_snapshot = transcript.read_bytes()
                        current_window = transcript_snapshot[window_offset:]
                        dump_present = (
                            _dump_marker(bounds["dump_seconds"])
                            in current_window
                        )
                        timeline.append(
                            _timeline_event(
                                "deadline_breach",
                                dump_present=dump_present,
                                last_progress=last_progress,
                                phase=phase,
                                transcript_sha256=_sha256_bytes(
                                    transcript_snapshot
                                ),
                                transcript_size=len(transcript_snapshot),
                                transcript_offset=window_offset,
                            )
                        )
                        (
                            returncode,
                            interrupted,
                            killed,
                            cleanup_complete,
                        ) = _terminate_owned_group(
                            process,
                            identity,
                            bounds["grace_seconds"],
                            timeline,
                        )
                        outcome = (
                            "unresolved_stall"
                            if dump_present and cleanup_complete
                            else "invalid"
                        )
                        if not dump_present:
                            invalid_reason = "deadline_breach_without_dump"
                        elif not cleanup_complete:
                            invalid_reason = "deadline_cleanup_incomplete"
                        break
                    polled = process.poll()
                    if pipe_eof:
                        if pipe_buffer:
                            invalid_reason = "partial_progress_event_at_eof"
                            (
                                returncode,
                                interrupted,
                                killed,
                                cleanup_complete,
                            ) = _terminate_owned_group(
                                process,
                                identity,
                                bounds["grace_seconds"],
                                timeline,
                            )
                        elif polled is None:
                            invalid_reason = "pipe_eof_while_child_running"
                            (
                                returncode,
                                interrupted,
                                killed,
                                cleanup_complete,
                            ) = _terminate_owned_group(
                                process,
                                identity,
                                bounds["grace_seconds"],
                                timeline,
                            )
                        elif _process_group_exists(identity["pgid"]):
                            invalid_reason = "pipe_eof_with_live_process_group"
                            (
                                returncode,
                                interrupted,
                                killed,
                                cleanup_complete,
                            ) = _terminate_owned_group(
                                process,
                                identity,
                                bounds["grace_seconds"],
                                timeline,
                            )
                        else:
                            returncode = polled
                            cleanup_complete = True
                        break
                    if polled is not None:
                        if child_exit_observed_ns is None:
                            child_exit_observed_ns = time.monotonic_ns()
                            timeline.append(
                                _timeline_event(
                                    "child_exit_observed_before_pipe_eof",
                                    returncode=polled,
                                )
                            )
                        elif (
                            time.monotonic_ns() - child_exit_observed_ns
                            >= EOF_EXIT_GRACE_SECONDS * 1_000_000_000
                        ):
                            invalid_reason = "child_exit_without_timely_pipe_eof"
                            (
                                returncode,
                                interrupted,
                                killed,
                                cleanup_complete,
                            ) = _terminate_owned_group(
                                process,
                                identity,
                                bounds["grace_seconds"],
                                timeline,
                            )
                            break
                        continue
                if (
                    invalid_reason is None
                    and outcome == "invalid"
                    and returncode is not None
                ):
                    if active_nodeid is not None:
                        invalid_reason = "unbalanced_progress_at_natural_exit"
                    elif progress_count != (
                        2 * len(_read_node_file(expected_nodes_path))
                    ):
                        invalid_reason = "natural_exit_progress_count_mismatch"
                    else:
                        outcome, nonpassing, natural = _validate_natural_result(
                            returncode,
                            transcript,
                            report_path,
                            expected_nodes_path,
                        )
                        if outcome == "invalid":
                            invalid_reason = "natural_result_validation_failed"
                        else:
                            nonpassing_path = (
                                Path(preflight["artifact_root"])
                                / f"{label}-nonpassing.nodes"
                            )
                            nonpassing_path.write_text(
                                "".join(f"{node}\n" for node in nonpassing),
                                encoding="utf-8",
                            )
                            nonpassing_count = len(nonpassing)
                        timeline.append(
                            _timeline_event(
                                "natural_validation",
                                details=natural,
                                outcome=outcome,
                            )
                        )
    except KeyboardInterrupt:
        invalid_reason = "operator_interrupted_runner"
        if process is not None:
            (
                returncode,
                interrupted,
                killed,
                cleanup_complete,
            ) = _terminate_owned_group(
                process,
                identity,
                bounds["grace_seconds"],
                timeline,
            )
    except BaseException as exc:
        invalid_reason = f"runner_exception:{type(exc).__name__}:{exc}"
        if process is not None and process.poll() is None:
            (
                returncode,
                interrupted,
                killed,
                cleanup_complete,
            ) = _terminate_owned_group(
                process,
                identity,
                bounds["grace_seconds"],
                timeline,
            )
    finally:
        selector.close()
        if write_fd >= 0:
            os.close(write_fd)
        try:
            os.close(read_fd)
        except OSError:
            pass
    if invalid_reason is not None:
        outcome = "invalid"
    try:
        data_after = _archive_worktree_data(repo, trial)
    except BaseException as exc:
        data_after = []
        invalid_reason = f"data_archive_failed:{type(exc).__name__}:{exc}"
        outcome = "invalid"
    try:
        verified_after = _verify_preflight(preflight_path)
        if verified_after != preflight:
            raise RuntimeError("preflight changed during attempt")
    except BaseException as exc:
        invalid_reason = (
            f"post_attempt_preflight_failed:{type(exc).__name__}:{exc}"
        )
        outcome = "invalid"
    ended_mono = time.monotonic_ns()
    record = {
        "active_nodeid_at_end": active_nodeid,
        "attempt": attempt,
        "bank_identity": bank_identity,
        "bounds": bounds,
        "cleanup_complete": cleanup_complete,
        "command": args,
        "data_entries_after": data_after,
        "data_entries_before": data_before,
        "deadline_phase": phase,
        "dump_present": dump_present,
        "duration_seconds": (ended_mono - started_mono) / 1_000_000_000,
        "ended_at_epoch": time.time(),
        "ended_monotonic_ns": ended_mono,
        "environment_names": sorted(env),
        "identity": identity,
        "interrupted": interrupted,
        "invalid_reason": invalid_reason,
        "killed": killed,
        "label": label,
        "last_progress": last_progress,
        "mode": mode,
        "nonpassing_count": nonpassing_count,
        "nonpassing_path": (
            str(nonpassing_path) if nonpassing_path is not None else None
        ),
        "nonpassing_sha256": (
            _sha256(nonpassing_path)
            if nonpassing_path is not None
            else None
        ),
        "outcome": outcome,
        "pipe_eof": pipe_eof,
        "progress_count": progress_count,
        "progress_path": str(progress_path),
        "progress_sha256": (
            _sha256(progress_path) if progress_path.is_file() else None
        ),
        "protocol_id": PROTOCOL_ID,
        "report_sha256": _sha256(report_path) if report_path.is_file() else None,
        "report_path": str(report_path),
        "returncode": returncode,
        "schema_version": 1,
        "side": preflight["side"],
        "started_at_epoch": started_wall,
        "started_monotonic_ns": started_mono,
        "timeline": timeline,
        "tier": tier,
        "transcript_sha256": (
            _sha256(transcript) if transcript.is_file() else None
        ),
        "transcript_path": str(transcript),
    }
    _atomic_json(trial / "record.json", record)
    return record


def _record_for(root: Path, label: str) -> dict[str, Any] | None:
    trial = root / label
    if not trial.exists():
        return None
    record = trial / "record.json"
    temporary = trial / "record.json.tmp"
    if temporary.exists() or not record.is_file():
        raise RuntimeError(f"incomplete attempt directory is invalid: {trial}")
    return _load_json(record)


def _audit_side_attempt_directories(root: Path, side: str) -> None:
    if (root / f"{side}-summary.json.tmp").exists():
        raise RuntimeError("incomplete side summary is invalid")
    for trial in sorted(root.glob(f"{side}-*")):
        if not trial.is_dir():
            continue
        record = trial / "record.json"
        if (trial / "record.json.tmp").exists() or not record.is_file():
            raise RuntimeError(
                f"incomplete attempt directory is invalid: {trial}"
            )


def _validate_banked(
    record: dict[str, Any],
    bank_identity: dict[str, Any],
    root: Path,
) -> None:
    if record.get("bank_identity") != bank_identity:
        raise RuntimeError("banked attempt identity changed")
    side = bank_identity["side"]
    label = record.get("label")
    if (
        record.get("protocol_id") != PROTOCOL_ID
        or record.get("schema_version") != 1
        or record.get("side") != side
        or record.get("mode") != "runtime"
        or record.get("bounds") != RUNTIME_BOUNDS
        or not isinstance(label, str)
    ):
        raise RuntimeError("banked attempt record identity is invalid")
    match = re.fullmatch(rf"{re.escape(side)}-T([0-7])-a([12])", label)
    if match is not None:
        tier = int(match.group(1))
        attempt = int(match.group(2))
        expected_nodes_path = root / f"{side}-T{tier}.nodes"
    elif label == f"{side}-diagnostic-monolithic":
        tier = None
        attempt = 1
        expected_nodes_path = root / f"{side}.nodes"
    else:
        raise RuntimeError("banked attempt label is invalid")
    if record.get("tier") != tier or record.get("attempt") != attempt:
        raise RuntimeError("banked attempt coordinates changed")
    trial = root / label
    for path_field, hash_field, filename in (
        ("progress_path", "progress_sha256", "progress.jsonl"),
        ("transcript_path", "transcript_sha256", "transcript.txt"),
    ):
        path = trial / filename
        if (
            record.get(path_field) != str(path)
            or not path.is_file()
            or record.get(hash_field) != _sha256(path)
        ):
            raise RuntimeError(f"banked {filename} artifact changed")
    outcome = record.get("outcome")
    if outcome == "invalid":
        raise RuntimeError("an invalid attempt closes the side")
    if outcome not in {
        "complete_pass",
        "complete_nonpassing",
        "unresolved_stall",
    }:
        raise RuntimeError("banked attempt outcome is invalid")
    if outcome == "unresolved_stall":
        if any(
            record.get(field) is not None
            for field in (
                "nonpassing_count",
                "nonpassing_path",
                "nonpassing_sha256",
            )
        ):
            raise RuntimeError("stalled attempt has non-passing artifacts")
        return
    report_path = trial / "report.json"
    if (
        record.get("report_path") != str(report_path)
        or not report_path.is_file()
        or record.get("report_sha256") != _sha256(report_path)
    ):
        raise RuntimeError("banked reporter artifact changed")
    path = root / f"{label}-nonpassing.nodes"
    if record.get("nonpassing_path") != str(path) or not path.is_file():
        raise RuntimeError("banked non-passing path changed")
    nodes = _read_node_file(path)
    if (
        record.get("nonpassing_count") != len(nodes)
        or record.get("nonpassing_sha256") != _sha256(path)
    ):
        raise RuntimeError("banked non-passing artifact changed")
    if (outcome == "complete_pass" and nodes) or (
        outcome == "complete_nonpassing" and not nodes
    ):
        raise RuntimeError("banked non-passing outcome is inconsistent")
    expected_nodes = set(_read_node_file(expected_nodes_path))
    if any(node not in expected_nodes for node in nodes):
        raise RuntimeError("banked non-passing node is outside its manifest")


def _write_incomplete_side_summary(
    preflight: dict[str, Any],
    bank_identity: dict[str, Any],
    *,
    invalid_attempt: str | None,
    selected: dict[int, dict[str, Any]],
    unresolved: list[int],
) -> dict[str, Any]:
    summary = {
        "bank_identity": bank_identity,
        "complete": False,
        "invalid_attempt": invalid_attempt,
        "protocol_id": PROTOCOL_ID,
        "schema_version": 1,
        "selected_attempts": {
            str(key): value["label"]
            for key, value in sorted(selected.items())
        },
        "side": preflight["side"],
        "unresolved_tiers": sorted(unresolved),
    }
    _atomic_json(
        Path(preflight["artifact_root"])
        / f"{preflight['side']}-summary.json",
        summary,
    )
    return summary


def _tier_entry(preflight: dict[str, Any], tier: int) -> dict[str, Any]:
    matches = [item for item in preflight["tiers"] if item["tier"] == tier]
    if len(matches) != 1:
        raise RuntimeError(f"missing tier entry: {tier}")
    return matches[0]


def _run_tier(
    preflight_path: Path,
    preflight: dict[str, Any],
    tier: int,
    attempt: int,
) -> dict[str, Any]:
    root = Path(preflight["artifact_root"])
    side = preflight["side"]
    label = f"{side}-T{tier}-a{attempt}"
    existing = _record_for(root, label)
    bank_identity = _bank_identity(preflight_path, preflight, "runtime")
    if existing is not None:
        _validate_banked(existing, bank_identity, root)
        return existing
    entry = _tier_entry(preflight, tier)
    paths = _artifact(preflight, entry["paths_role"]).read_text(
        encoding="utf-8"
    ).splitlines()
    if paths != sorted(set(paths)) or not paths:
        raise RuntimeError(f"tier paths are invalid: {tier}")
    record = _run_attempt(
        preflight_path=preflight_path,
        preflight=preflight,
        trial=root / label,
        cwd=Path(preflight["repo"]),
        selectors_=paths,
        expected_nodes_path=_artifact(preflight, entry["nodes_role"]),
        mode="runtime",
        label=label,
        tier=tier,
        attempt=attempt,
    )
    if record.get("outcome") != "invalid":
        _validate_banked(record, bank_identity, root)
    return record


def _combine_nonpassing(
    preflight: dict[str, Any],
    selected: dict[int, dict[str, Any]],
) -> Path:
    root = Path(preflight["artifact_root"])
    side = preflight["side"]
    nodes: set[str] = set()
    for tier, record in sorted(selected.items()):
        path = root / f"{record['label']}-nonpassing.nodes"
        if not path.is_file():
            raise RuntimeError(f"missing banked nonpassing file: T{tier}")
        nodes.update(path.read_text(encoding="utf-8").splitlines())
    destination = root / f"{side}-nonpassing.nodes"
    destination.write_text(
        "".join(f"{node}\n" for node in sorted(nodes)),
        encoding="utf-8",
    )
    return destination


def run_side(preflight_path: Path) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path)
    if preflight["side"] not in {"base", "tip"}:
        raise RuntimeError("run-side requires base or tip preflight")
    root = Path(preflight["artifact_root"])
    bank_identity = _bank_identity(preflight_path, preflight, "runtime")
    if (root / f"{preflight['side']}-summary.json.tmp").exists():
        raise RuntimeError("incomplete side summary is invalid")
    try:
        _audit_side_attempt_directories(root, preflight["side"])
    except RuntimeError:
        _write_incomplete_side_summary(
            preflight,
            bank_identity,
            invalid_attempt="incomplete_attempt_artifact",
            selected={},
            unresolved=[],
        )
        raise
    for record_path in sorted(root.glob(f"{preflight['side']}-*/record.json")):
        record = _load_json(record_path)
        try:
            _validate_banked(record, bank_identity, root)
        except RuntimeError:
            _write_incomplete_side_summary(
                preflight,
                bank_identity,
                invalid_attempt=str(record.get("label")),
                selected={},
                unresolved=[],
            )
            raise
    selected: dict[int, dict[str, Any]] = {}
    unresolved: list[int] = []
    for tier in range(8):
        try:
            record = _run_tier(preflight_path, preflight, tier, 1)
        except RuntimeError:
            _write_incomplete_side_summary(
                preflight,
                bank_identity,
                invalid_attempt=f"{preflight['side']}-T{tier}-a1:runner_error",
                selected=selected,
                unresolved=unresolved,
            )
            raise
        outcome = record["outcome"]
        if outcome == "invalid":
            _write_incomplete_side_summary(
                preflight,
                bank_identity,
                invalid_attempt=record["label"],
                selected=selected,
                unresolved=unresolved,
            )
            raise RuntimeError(f"invalid tier closes side: T{tier}/a1")
        if outcome == "unresolved_stall":
            unresolved.append(tier)
        else:
            selected[tier] = record
    still_unresolved: list[int] = []
    for tier in unresolved:
        try:
            record = _run_tier(preflight_path, preflight, tier, 2)
        except RuntimeError:
            _write_incomplete_side_summary(
                preflight,
                bank_identity,
                invalid_attempt=f"{preflight['side']}-T{tier}-a2:runner_error",
                selected=selected,
                unresolved=unresolved,
            )
            raise
        outcome = record["outcome"]
        if outcome == "invalid":
            _write_incomplete_side_summary(
                preflight,
                bank_identity,
                invalid_attempt=record["label"],
                selected=selected,
                unresolved=unresolved,
            )
            raise RuntimeError(f"invalid tier closes side: T{tier}/a2")
        if outcome == "unresolved_stall":
            still_unresolved.append(tier)
        else:
            selected[tier] = record
    if still_unresolved:
        return _write_incomplete_side_summary(
            preflight,
            bank_identity,
            invalid_attempt=None,
            selected=selected,
            unresolved=still_unresolved,
        )
    if set(selected) != set(range(8)):
        raise RuntimeError("side selection is incomplete")
    try:
        verified_after = _verify_preflight(preflight_path)
        if verified_after != preflight:
            raise RuntimeError("preflight changed before side completion")
        for record in selected.values():
            _validate_banked(record, bank_identity, root)
    except RuntimeError:
        _write_incomplete_side_summary(
            preflight,
            bank_identity,
            invalid_attempt="side_completion_identity",
            selected=selected,
            unresolved=[],
        )
        raise
    nonpassing = _combine_nonpassing(preflight, selected)
    summary = {
        "bank_identity": bank_identity,
        "complete": True,
        "nonpassing_count": len(
            nonpassing.read_text(encoding="utf-8").splitlines()
        ),
        "nonpassing_sha256": _sha256(nonpassing),
        "protocol_id": PROTOCOL_ID,
        "schema_version": 1,
        "selected_attempts": {
            str(key): value["label"]
            for key, value in sorted(selected.items())
        },
        "side": preflight["side"],
        "unresolved_tiers": [],
    }
    _atomic_json(root / f"{preflight['side']}-summary.json", summary)
    return summary


def run_diagnostic(preflight_path: Path) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path)
    if preflight["side"] not in {"base", "tip"}:
        raise RuntimeError("run-diagnostic requires base or tip preflight")
    root = Path(preflight["artifact_root"])
    _audit_side_attempt_directories(root, preflight["side"])
    summary_path = root / f"{preflight['side']}-summary.json"
    if not summary_path.is_file():
        raise RuntimeError("diagnostic requires a side summary")
    summary = _load_json(summary_path)
    if (
        summary.get("protocol_id") != PROTOCOL_ID
        or summary.get("side") != preflight["side"]
        or summary.get("complete") is not True
    ):
        raise RuntimeError("diagnostic requires a complete tiered side")
    bank_identity = _bank_identity(preflight_path, preflight, "runtime")
    for record_path in sorted(
        root.glob(f"{preflight['side']}-*/record.json")
    ):
        _validate_banked(_load_json(record_path), bank_identity, root)
    label = f"{preflight['side']}-diagnostic-monolithic"
    existing = _record_for(root, label)
    if existing is not None:
        _validate_banked(existing, bank_identity, root)
        return existing
    return _run_attempt(
        preflight_path=preflight_path,
        preflight=preflight,
        trial=root / label,
        cwd=Path(preflight["repo"]),
        selectors_=[],
        expected_nodes_path=_artifact(preflight, "canonical_nodes"),
        mode="runtime",
        label=label,
        tier=None,
        attempt=1,
    )


def _probe_record(
    preflight_path: Path,
    preflight: dict[str, Any],
    role: str,
    label: str,
) -> dict[str, Any]:
    fixture = _artifact(preflight, role)
    nodes = _artifact(preflight, "probe_nodes")
    return _run_attempt(
        preflight_path=preflight_path,
        preflight=preflight,
        trial=Path(preflight["artifact_root"]) / label,
        cwd=Path(preflight["artifact_root"]),
        selectors_=[fixture.name],
        expected_nodes_path=nodes,
        mode="probe",
        label=label,
        tier=None,
        attempt=1,
    )


def _collect_identity_arm(
    preflight_path: Path,
    preflight: dict[str, Any],
    *,
    plugin_enabled: bool,
) -> tuple[list[str], dict[str, Any]]:
    if _verify_preflight(preflight_path) != preflight:
        raise RuntimeError("preflight changed before collection probe")
    root = Path(preflight["artifact_root"])
    label = (
        "probe-collect-plugin"
        if plugin_enabled
        else "probe-collect-control"
    )
    trial = root / label
    trial.mkdir(parents=True, exist_ok=False)
    transcript = trial / "transcript.txt"
    report_path = trial / "report.json"
    manifest_path = trial / "collected.nodes"
    read_fd = -1
    write_fd = -1
    if plugin_enabled:
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
    env = _child_env(preflight, trial, report_path, write_fd)
    if not plugin_enabled:
        env.pop(PROGRESS_ENV)
    args = [
        preflight["python"],
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-o",
        f"cache_dir={trial / 'pytest-cache'}",
        "--basetemp",
        str(trial / "pytest-tmp"),
        "-p",
        REPORTER_MODULE,
    ]
    if plugin_enabled:
        args.extend(["-p", PLUGIN_MODULE])
    args.append(_artifact(preflight, "probe_pass").name)
    timeline = [_timeline_event("collect_probe_launch")]
    process: subprocess.Popen[bytes] | None = None
    identity: dict[str, int] | None = None
    cleanup_complete = False
    returncode: int | None = None
    progress_bytes = b""
    invalid_reason: str | None = None
    try:
        with transcript.open("wb") as transcript_handle:
            process = subprocess.Popen(
                args,
                cwd=root,
                env=env,
                stdout=transcript_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=((write_fd,) if plugin_enabled else ()),
            )
            if plugin_enabled:
                os.close(write_fd)
                write_fd = -1
            identity = _process_identity(process)
            timeline.append(_timeline_event("collect_probe_started", identity=identity))
            if not _identity_is_owned(identity):
                invalid_reason = "process_group_identity_mismatch"
                cleanup_complete = _terminate_direct_child(process, timeline)
                returncode = process.poll()
            else:
                try:
                    returncode = process.wait(
                        timeout=PROBE_BOUNDS["deadline_seconds"]
                    )
                    if _process_group_exists(identity["pgid"]):
                        invalid_reason = "collect_probe_live_group_after_exit"
                        (
                            returncode,
                            _,
                            _,
                            cleanup_complete,
                        ) = _terminate_owned_group(
                            process,
                            identity,
                            PROBE_BOUNDS["grace_seconds"],
                            timeline,
                        )
                    else:
                        cleanup_complete = True
                except subprocess.TimeoutExpired:
                    invalid_reason = "collect_probe_timeout"
                    (
                        returncode,
                        _,
                        _,
                        cleanup_complete,
                    ) = _terminate_owned_group(
                        process,
                        identity,
                        PROBE_BOUNDS["grace_seconds"],
                        timeline,
                    )
        if plugin_enabled:
            pipe_eof = False
            while True:
                try:
                    chunk = os.read(read_fd, 65536)
                except BlockingIOError:
                    break
                if not chunk:
                    pipe_eof = True
                    break
                progress_bytes += chunk
            if not pipe_eof:
                invalid_reason = invalid_reason or "collect_probe_pipe_not_closed"
            if progress_bytes:
                invalid_reason = "collect_only_emitted_runtime_progress"
        if returncode != 0 or not cleanup_complete:
            invalid_reason = invalid_reason or "collect_probe_nonzero"
        if not report_path.is_file():
            invalid_reason = invalid_reason or "collect_probe_report_missing"
            collected: list[str] = []
        else:
            report = _load_json(report_path)
            expected = _read_node_file(_artifact(preflight, "probe_nodes"))
            collected = report.get("collected_node_ids", [])
            if (
                report.get("schema_version") != 1
                or report.get("exitstatus") != 0
                or collected != expected
                or report.get("seen_node_ids") != []
                or report.get("nonpassing_node_ids") != []
            ):
                invalid_reason = invalid_reason or "collect_probe_report_invalid"
            else:
                manifest_path.write_text(
                    "".join(f"{node}\n" for node in collected),
                    encoding="utf-8",
                )
    except BaseException as exc:
        invalid_reason = (
            f"collect_probe_exception:{type(exc).__name__}:{exc}"
        )
        collected = []
        if (
            process is not None
            and identity is not None
            and (
                process.poll() is None
                or _process_group_exists(identity["pgid"])
            )
        ):
            (
                returncode,
                _,
                _,
                cleanup_complete,
            ) = _terminate_owned_group(
                process,
                identity,
                PROBE_BOUNDS["grace_seconds"],
                timeline,
            )
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        if read_fd >= 0:
            os.close(read_fd)
    try:
        data_after = _archive_worktree_data(
            Path(preflight["repo"]),
            trial,
        )
    except BaseException as exc:
        data_after = []
        invalid_reason = (
            f"collect_probe_data_archive_failed:{type(exc).__name__}:{exc}"
        )
    try:
        if _verify_preflight(preflight_path) != preflight:
            raise RuntimeError("preflight changed during collection probe")
    except BaseException as exc:
        invalid_reason = (
            f"collect_probe_postflight_failed:{type(exc).__name__}:{exc}"
        )
    record = {
        "cleanup_complete": cleanup_complete,
        "collected_node_ids": collected,
        "collected_nodes_path": (
            str(manifest_path) if manifest_path.is_file() else None
        ),
        "collected_nodes_sha256": (
            _sha256(manifest_path) if manifest_path.is_file() else None
        ),
        "command": args,
        "data_entries_after": data_after,
        "identity": identity,
        "invalid_reason": invalid_reason,
        "label": label,
        "mode": "probe",
        "bounds": dict(PROBE_BOUNDS),
        "plugin_enabled": plugin_enabled,
        "progress_bytes": len(progress_bytes),
        "protocol_id": PROTOCOL_ID,
        "returncode": returncode,
        "schema_version": 1,
        "timeline": timeline,
        "transcript_sha256": _sha256(transcript),
    }
    _atomic_json(trial / "record.json", record)
    if invalid_reason is not None:
        raise RuntimeError(f"{label} failed: {invalid_reason}")
    return collected, record


def _plugin_fd_fail_closed_arm(
    preflight_path: Path,
    preflight: dict[str, Any],
    *,
    value: str | None,
) -> dict[str, Any]:
    if _verify_preflight(preflight_path) != preflight:
        raise RuntimeError("preflight changed before FD probe")
    root = Path(preflight["artifact_root"])
    suffix = "missing" if value is None else "garbled"
    label = f"probe-progress-fd-{suffix}"
    trial = root / label
    trial.mkdir(parents=True, exist_ok=False)
    transcript = trial / "transcript.txt"
    env = _child_env(preflight, trial, trial / "unused-report.json", -1)
    if value is None:
        env.pop(PROGRESS_ENV)
    else:
        env[PROGRESS_ENV] = value
    args = [
        preflight["python"],
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-o",
        f"cache_dir={trial / 'pytest-cache'}",
        "--basetemp",
        str(trial / "pytest-tmp"),
        "-p",
        PLUGIN_MODULE,
        _artifact(preflight, "probe_pass").name,
    ]
    timeline = [_timeline_event("fd_fail_closed_probe_launch")]
    with transcript.open("wb") as transcript_handle:
        process = subprocess.Popen(
            args,
            cwd=root,
            env=env,
            stdout=transcript_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        identity = _process_identity(process)
        if not _identity_is_owned(identity):
            cleanup_complete = _terminate_direct_child(process, timeline)
            returncode = process.poll()
            invalid_reason = "process_group_identity_mismatch"
        else:
            try:
                returncode = process.wait(
                    timeout=PROBE_BOUNDS["deadline_seconds"]
                )
                if _process_group_exists(identity["pgid"]):
                    (
                        returncode,
                        _,
                        _,
                        cleanup_complete,
                    ) = _terminate_owned_group(
                        process,
                        identity,
                        PROBE_BOUNDS["grace_seconds"],
                        timeline,
                    )
                    invalid_reason = "fd_probe_live_group_after_exit"
                else:
                    cleanup_complete = True
                    invalid_reason = None
            except subprocess.TimeoutExpired:
                (
                    returncode,
                    _,
                    _,
                    cleanup_complete,
                ) = _terminate_owned_group(
                    process,
                    identity,
                    PROBE_BOUNDS["grace_seconds"],
                    timeline,
                )
                invalid_reason = "fd_fail_closed_probe_timeout"
    transcript_text = transcript.read_text(encoding="utf-8", errors="replace")
    pytest_configure_failure = (
        "pytest_configure" in transcript_text
        and PROGRESS_ENV in transcript_text
    )
    if (
        invalid_reason is None
        and (
            returncode == 0
            or not pytest_configure_failure
            or not cleanup_complete
        )
    ):
        invalid_reason = "progress_fd_did_not_fail_closed"
    try:
        data_after = _archive_worktree_data(
            Path(preflight["repo"]),
            trial,
        )
    except BaseException as exc:
        data_after = []
        invalid_reason = (
            f"fd_probe_data_archive_failed:{type(exc).__name__}:{exc}"
        )
    try:
        if _verify_preflight(preflight_path) != preflight:
            raise RuntimeError("preflight changed during FD probe")
    except BaseException as exc:
        invalid_reason = f"fd_probe_postflight_failed:{type(exc).__name__}:{exc}"
    record = {
        "cleanup_complete": cleanup_complete,
        "bounds": dict(PROBE_BOUNDS),
        "command": args,
        "data_entries_after": data_after,
        "identity": identity,
        "invalid_reason": invalid_reason,
        "label": label,
        "mode": "probe",
        "protocol_id": PROTOCOL_ID,
        "pytest_configure_failure": pytest_configure_failure,
        "returncode": returncode,
        "schema_version": 1,
        "transcript_sha256": _sha256(transcript),
        "value_kind": suffix,
    }
    _atomic_json(trial / "record.json", record)
    if invalid_reason is not None:
        raise RuntimeError(f"{label} failed: {invalid_reason}")
    return record


def run_probe_suite(preflight_path: Path) -> dict[str, Any]:
    preflight = _verify_preflight(preflight_path)
    if preflight["side"] != "probe":
        raise RuntimeError("probe-suite requires probe preflight")
    root = Path(preflight["artifact_root"])
    pass_record = _probe_record(
        preflight_path,
        preflight,
        "probe_pass",
        "probe-fast-pass",
    )
    interrupt_record = _probe_record(
        preflight_path,
        preflight,
        "probe_interruptible",
        "probe-sigint",
    )
    kill_record = _probe_record(
        preflight_path,
        preflight,
        "probe_ignore_sigint",
        "probe-sigkill",
    )
    control_nodes, control_record = _collect_identity_arm(
        preflight_path,
        preflight,
        plugin_enabled=False,
    )
    plugin_nodes, plugin_record = _collect_identity_arm(
        preflight_path,
        preflight,
        plugin_enabled=True,
    )
    missing_fd_record = _plugin_fd_fail_closed_arm(
        preflight_path,
        preflight,
        value=None,
    )
    garbled_fd_record = _plugin_fd_fail_closed_arm(
        preflight_path,
        preflight,
        value="not-a-file-descriptor",
    )
    interrupt_events = [
        item["event"] for item in interrupt_record["timeline"]
    ]
    kill_events = [item["event"] for item in kill_record["timeline"]]
    try:
        interrupt_sigint_index = interrupt_events.index("sigint")
        interrupt_exit_index = interrupt_events.index(
            "group_exit_after_sigint"
        )
        kill_sigint_index = kill_events.index("sigint")
        kill_sigkill_index = kill_events.index("sigkill")
        kill_exit_index = kill_events.index("group_exit_after_sigkill")
        kill_sigint_ns = kill_record["timeline"][kill_sigint_index][
            "monotonic_ns"
        ]
        kill_sigkill_ns = kill_record["timeline"][kill_sigkill_index][
            "monotonic_ns"
        ]
    except (KeyError, ValueError):
        interrupt_sigint_index = -1
        interrupt_exit_index = -1
        kill_sigint_index = -1
        kill_sigkill_index = -1
        kill_exit_index = -1
        kill_sigint_ns = 0
        kill_sigkill_ns = 0
    expected = {
        "pass": (
            pass_record["outcome"] == "complete_pass"
            and pass_record["cleanup_complete"]
            and pass_record["pipe_eof"]
            and pass_record["progress_count"] == 2
            and not pass_record["interrupted"]
            and not pass_record["killed"]
        ),
        "sigint": (
            interrupt_record["outcome"] == "unresolved_stall"
            and interrupt_record["dump_present"]
            and interrupt_record["cleanup_complete"]
            and interrupt_record["interrupted"]
            and not interrupt_record["killed"]
            and 0 <= interrupt_sigint_index < interrupt_exit_index
            and "sigkill" not in interrupt_events
        ),
        "sigkill": (
            kill_record["outcome"] == "unresolved_stall"
            and kill_record["dump_present"]
            and kill_record["cleanup_complete"]
            and kill_record["interrupted"]
            and kill_record["killed"]
            and 0 <= kill_sigint_index < kill_sigkill_index < kill_exit_index
            and kill_sigkill_ns - kill_sigint_ns
            >= PROBE_BOUNDS["grace_seconds"] * 1_000_000_000
        ),
        "collection_identity": (
            control_nodes == plugin_nodes
            and control_nodes
            == _read_node_file(_artifact(preflight, "probe_nodes"))
            and control_record["collected_nodes_sha256"]
            == plugin_record["collected_nodes_sha256"]
            == _sha256(_artifact(preflight, "probe_nodes"))
        ),
        "fd_fail_closed": (
            missing_fd_record["returncode"] not in {None, 0}
            and garbled_fd_record["returncode"] not in {None, 0}
            and missing_fd_record["pytest_configure_failure"]
            and garbled_fd_record["pytest_configure_failure"]
        ),
    }
    if not all(expected.values()):
        raise RuntimeError(f"probe outcome mismatch: {expected}")
    summary = {
        "checks": expected,
        "protocol_id": PROTOCOL_ID,
        "records": {
            "pass": pass_record["label"],
            "sigint": interrupt_record["label"],
            "sigkill": kill_record["label"],
            "collect_control": control_record["label"],
            "collect_plugin": plugin_record["label"],
            "fd_missing": missing_fd_record["label"],
            "fd_garbled": garbled_fd_record["label"],
        },
        "schema_version": 1,
    }
    _atomic_json(root / "probe-summary.json", summary)
    return summary


def _preflight_artifact(
    path: Path,
    role: str,
) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"preflight source artifact is missing: {path}")
    return {
        "path": str(path.resolve()),
        "role": role,
        "sha256": _sha256(path),
    }


def prepare_preflight(
    *,
    artifact_root: Path,
    repo: Path,
    side: str,
) -> Path:
    root = artifact_root.resolve()
    repo = repo.resolve()
    if side not in {"base", "tip", "probe"}:
        raise RuntimeError("prepare side must be base, tip, or probe")
    if root == FROZEN_V1_ROOT:
        raise RuntimeError("the frozen v1 artifact root cannot be reused")
    if Path(__file__).resolve() != (root / "price_truth_tier_runner.py"):
        raise RuntimeError("prepare must run the standard copied runner name")
    if not repo.is_dir() or not (repo / ".git").exists():
        raise RuntimeError("prepare repo is not an isolated Git worktree")
    output = root / f"{side}-preflight.json"
    if output.exists() or output.with_suffix(".json.tmp").exists():
        raise RuntimeError("preflight output already exists")
    common = [
        _preflight_artifact(
            root / "price_truth_tier_runner.py",
            "runner",
        ),
        _preflight_artifact(
            root / "arkscope_price_truth_tier_reporter.py",
            "reporter",
        ),
        _preflight_artifact(root / "build_tiers.py", "builder"),
        _preflight_artifact(root / "probe.nodes", "probe_nodes"),
        _preflight_artifact(
            root / "probe-tier-map.tsv",
            "reviewed_probe_tier_map",
        ),
        _preflight_artifact(root / "probe_pass.py", "probe_pass"),
        _preflight_artifact(
            root / "probe_interruptible.py",
            "probe_interruptible",
        ),
        _preflight_artifact(
            root / "probe_ignore_sigint.py",
            "probe_ignore_sigint",
        ),
    ]
    tiers: list[dict[str, Any]] = []
    if side == "probe":
        artifacts = [
            *common,
            _preflight_artifact(root / "probe.nodes", "canonical_nodes"),
            _preflight_artifact(
                root / "probe-tier-map.tsv",
                "tier_map",
            ),
        ]
    else:
        artifacts = [
            *common,
            _preflight_artifact(
                root / f"{side}.nodes",
                "canonical_nodes",
            ),
            _preflight_artifact(root / "tier-map.tsv", "tier_map"),
        ]
        for tier in range(8):
            paths_role = f"tier_{tier}_paths"
            nodes_role = f"tier_{tier}_nodes"
            artifacts.extend(
                [
                    _preflight_artifact(
                        root / f"T{tier}.paths",
                        paths_role,
                    ),
                    _preflight_artifact(
                        root / f"{side}-T{tier}.nodes",
                        nodes_role,
                    ),
                ]
            )
            tiers.append(
                {
                    "nodes_role": nodes_role,
                    "paths_role": paths_role,
                    "tier": tier,
                }
            )
    git_identity = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    import pytest

    payload = {
        "artifact_root": str(root),
        "artifacts": artifacts,
        "git_identity": git_identity,
        "path": os.environ.get("PATH", ""),
        "pip_freeze_sha256": _pip_freeze_sha256(),
        "protocol_id": PROTOCOL_ID,
        "python": sys.executable,
        "python_version": sys.version,
        "pytest_version": pytest.__version__,
        "repo": str(repo),
        "schema_version": 1,
        "side": side,
        "tiers": tiers,
    }
    _atomic_json(output, payload)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("probe-suite", "run-side", "run-diagnostic"):
        child = subparsers.add_parser(name)
        child.add_argument("--preflight", type=Path, required=True)
    prepare = subparsers.add_parser("prepare-preflight")
    prepare.add_argument("--artifact-root", type=Path, required=True)
    prepare.add_argument("--repo", type=Path, required=True)
    prepare.add_argument(
        "--side",
        choices=("base", "tip", "probe"),
        required=True,
    )
    args = parser.parse_args()
    if args.command == "prepare-preflight":
        result = {
            "preflight": str(
                prepare_preflight(
                    artifact_root=args.artifact_root,
                    repo=args.repo,
                    side=args.side,
                )
            )
        }
    elif args.command == "probe-suite":
        result = run_probe_suite(args.preflight)
    elif args.command == "run-side":
        result = run_side(args.preflight)
    else:
        result = run_diagnostic(args.preflight)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
<!-- PRICE_TRUTH_RUNNER_V2_END -->
