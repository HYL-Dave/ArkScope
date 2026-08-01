# EIR-002 Green Backend Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** TASK 7 BOUNDED AMENDMENT - INDEPENDENT REVIEW NEXT
>
> **Date:** 2026-07-31
>
> **Design authority:** `20d4e7e2`

**Goal:** Replace the exact 27-node environment-dependent backend debt with a
4,730-node native backend suite that has zero failures, without restoring old
repository data or changing product code.

**Architecture:** Remove nine obsolete positive-data tests, keep all seventeen
live API/tool/agent node identities, and feed those consumers deterministic
current-shape data through existing DAL and FastAPI dependency seams. Fix the
remaining date-rot test through its existing explicit clock input. A pinned
pytest reporter owns collection and non-passing node accounting; ASGI/full
admission runs natively after the EIR-005 wakeup probe.

**Tech Stack:** Python 3.10, pytest, pandas, FastAPI, httpx ASGITransport,
Pydantic, Git.

---

## 0. Authority And Execution Boundary

Canonical design:

```text
docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md
design commit: 20d4e7e2
grounding commit: 3092fb4128dad9a2579f267e915519fa9cdf648c
```

Implementation stays in:

```text
worktree: /tmp/arkscope-eir-002
branch:   codex/eir-002-green-backend-baseline
```

The main worktree's untracked
`docs/design/SCRIPTS_RETIREMENT_DECISION.md` is outside this worktree and must
not be copied, edited, staged, deleted, or cited.

The managed sandbox is valid for collection and non-ASGI focused tests. It is
not an admission boundary for `tests/test_api.py` or the canonical full suite.
Those commands run natively only after this exact probe passes:

```text
/tmp/arkscope_asyncio_wakeup_probe.py
bytes: 942
SHA-256: 10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e
required result:
{"callback_fired": true, "ready_count": 0, "wake_bytes": 0}
```

Any probe mismatch stops the run. It does not authorize a sandbox fallback.

Node.js `v22.14.0` is a pinned test-toolchain dependency, like the pinned
Python interpreter. Adding its exact binary directory to the blank
environment does not add a provider credential or historical product data and
does not weaken the blank-environment contract.

## 1. File Map

### Product and test changes

| File | Responsibility |
|---|---|
| `tests/test_data_access.py` | Remove exactly nine obsolete ambient positive-data nodes |
| `tests/test_api.py` | Add a scoped deterministic DAL override and rewire eight existing HTTP nodes |
| `tests/test_tools.py` | Add a deterministic backend fixture and rewire seven existing tool nodes |
| `tests/test_agents.py` | Add a minimal deterministic backend and rewire two existing dispatch nodes |
| `tests/test_app_records_store.py` | Pin one round-trip query to an explicit date |

### Authority and evidence changes

| File | Responsibility |
|---|---|
| `docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md` | Record the independent GREEN review status without changing the approved contract |
| `docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md` | Exact RED-first implementation authority |
| `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md` | Record exact RED/GREEN, collection, native boundary, and protected-path evidence |
| `docs/design/ENGINEERING_ISSUE_REGISTER.md` | Keep EIR-002 promoted until merged closeout; do not change EIR-006 |
| `docs/design/PROJECT_PRIORITY_MAP.md` | Record implementation-review handoff |

No file under `src/`, `data_sources/`, `apps/`, `config/`, `data/`, or
`scripts/` may change.

## 2. Immutable Accounting

### 2.1 Collection identities

Plan construction reproduced the base hashes from pytest's sorted full node-ID
stream, then removed only the nine Section 4.1 IDs from the approved design.

| Collection | Base | Base SHA-256 | Target | Target SHA-256 |
|---|---:|---|---:|---|
| Canonical backend | 4,739 | `a72bbd36dfad3d36aee2e6630e6024ec9fb4e910bebaf1363d44df8a1aa204dd` | 4,730 | `c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb` |
| Five owned test files | 132 | `76f8f087a24f2ff2934274cbbd1711d203c9dbe7056ba4bf5d6022b2d1a03f9c` | 123 | `37386cd24fca323338fcb0fb2bbe5c42b7c471d2e9fde2e7c5f345b5ce631b8f` |

The delta is exactly `+0/-9`. Helpers must not be named `test_*`. No test is
renamed, parametrized into extra nodes, skipped, or marked xfail.

### 2.2 Runtime ledger

| Stage | Collected | Passed | Failed | Expected non-passing SHA-256 |
|---|---:|---:|---:|---|
| Base | 4,739 | 4,640 | 27 | `7aafce5d2cba923480cc1fb6221bce4f5a33e0bf61c06cf94227cafefe227f15` |
| Nine DAL nodes retired | 4,730 | 4,640 | 18 | `567ea435111078f45dee4c818e282997e1d562e72cf2ddc5a5101a09527cd225` |
| Seven news nodes green | 4,730 | 4,647 | 11 | `e6d59e3ec3e24b3d8ef2d68c341af5dcbb8c3bd0f264e71a130a45713ad8203c` |
| Eight price nodes green | 4,730 | 4,655 | 3 | `c072d5df09468496bb8fa26ade78cf38e1846be9b1dbe665502db60ae1e69664` |
| Two fundamentals nodes green | 4,730 | 4,657 | 1 | `71b6d959c36e1b7d8e9c92b4904a8e68c46c6c4d7992c0bdc939dc1b220798f0` |
| Date node green | 4,730 | 4,658 | 0 | empty file: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Every row includes 72 unchanged skipped nodes. Family checkpoints use the five
owned files, whose corresponding pass/fail progression is:

```text
base:                 105 passed / 27 failed / 132 total
after retirement:    105 passed / 18 failed / 123 total
after news:          112 passed / 11 failed / 123 total
after prices:        120 passed /  3 failed / 123 total
after fundamentals:  122 passed /  1 failed / 123 total
after date:          123 passed /  0 failed / 123 total
```

The final native full run is the only authority for the repository-wide pass
counts. A partial transcript is never a baseline or pass.

## 3. Exact Reporter

Task 0 creates `/tmp/eir002-green-baseline/arkscope_eir002_reporter.py` with
these exact bytes:

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

Required identity:

```text
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
```

The reporter's JSON arrays are the authority. Never parse node IDs from pytest
terminal prose.

### 3.1 Exact native admission wrapper

Task 0 creates `/tmp/eir002-green-baseline/run_native.sh` with these exact
bytes:

```bash
#!/usr/bin/env bash
set -euo pipefail

if (( $# < 1 )); then
  printf 'usage: %s STAGE [PYTEST_ARG ...]\n' "$0" >&2
  exit 64
fi

stage=$1
shift
case "$stage" in
  ''|*[!A-Za-z0-9._-]*)
    printf 'invalid stage: %s\n' "$stage" >&2
    exit 64
    ;;
esac

repo_root=$(git rev-parse --show-toplevel)
test "$(pwd -P)" = "$repo_root"
root="/tmp/eir002-green-baseline/runtime/$stage"
report="/tmp/eir002-green-baseline/reports/$stage.json"
transcript="/tmp/eir002-green-baseline/reports/$stage.txt"
probe=/tmp/arkscope_asyncio_wakeup_probe.py
reporter=/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
node_dir=/home/hyl/.nvm/versions/node/v22.14.0/bin

test ! -e "$root"
test ! -e "$report"
test ! -e "$transcript"
test -x "$node_dir/node"
test "$("$node_dir/node" --version)" = "v22.14.0"
test "$(wc -c < "$probe")" -eq 942
test "$(sha256sum "$probe" | awk '{print $1}')" = \
  10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e
test "$(sha256sum "$reporter" | awk '{print $1}')" = \
  09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928

probe_result=$(
  /home/hyl/.virtualenvs/llm_app/bin/python "$probe"
)
test "$probe_result" = \
  '{"callback_fired": true, "ready_count": 0, "wake_bytes": 0}'

mkdir -p \
  "$root/home" \
  "$root/tmp" \
  "$root/xdg-cache" \
  "$root/locks" \
  "$root/edgar" \
  /tmp/eir002-green-baseline/reports

set +e
env -i \
  PATH="/home/hyl/.virtualenvs/llm_app/bin:$node_dir:/usr/bin:/bin" \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=Asia/Taipei \
  HOME="$root/home" \
  TMPDIR="$root/tmp" \
  XDG_CACHE_HOME="$root/xdg-cache" \
  PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 \
  PYTHONPATH="/tmp/eir002-green-baseline:$repo_root" \
  ARKSCOPE_DISABLE_SCHEDULER=1 \
  ARKSCOPE_LOCK_DIR="$root/locks" \
  ARKSCOPE_PROFILE_DB="$root/profile_state.db" \
  ARKSCOPE_MARKET_DB="$root/market_data.db" \
  ARKSCOPE_MACRO_CALENDAR_DB="$root/macro_calendar.db" \
  ARKSCOPE_SA_DB="$root/sa_capture.db" \
  ARKSCOPE_CONSENSUS_DB="$root/consensus.db" \
  EDGAR_LOCAL_DATA_DIR="$root/edgar" \
  PRICE_TRUTH_TIER_REPORT="$report" \
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    -o faulthandler_timeout=120 \
    -p arkscope_eir002_reporter \
    "$@" 2>&1 | tee "$transcript"
pipeline_status=("${PIPESTATUS[@]}")
set -e
if (( pipeline_status[1] != 0 )); then
  exit 74
fi
exit "${pipeline_status[0]}"
```

Required identity:

```text
79 lines / 2,353 bytes
SHA-256:
e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f
```

This wrapper owns the native/sandbox boundary, fresh runtime roots, exact
wakeup-probe admission, credential-free environment, current Git-root identity,
reporter identity, raw transcript capture, and `faulthandler_timeout=120`.
Reporter JSON remains the node authority; the transcript supplies terminal
counts and diagnostics. Every call starts at that worktree's root. A stage
name is single-use. Never delete a runtime root merely to reuse its name;
choose a new stage name and preserve the first attempt as evidence.

## 4. Deterministic Fixture Shape

The API and tool fixtures independently define the same small current-shape
dataset:

### News rows

```python
[
    {
        "date": "2026-07-30T14:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA earnings beat expectations",
        "source": "polygon",
        "url": "https://example.test/nvda-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 5.0,
        "risk_score": 2.0,
        "description": "NVIDIA reported stronger earnings.",
    },
    {
        "date": "2026-07-30T13:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA product update",
        "source": "ibkr",
        "url": "https://example.test/nvda-product",
        "publisher": "Example Desk",
        "sentiment_score": 3.0,
        "risk_score": 3.0,
        "description": "NVIDIA announced a product update.",
    },
    {
        "date": "2026-07-30T12:00:00+0000",
        "ticker": "AMD",
        "title": "AMD earnings preview",
        "source": "finnhub",
        "url": "https://example.test/amd-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 2.0,
        "risk_score": 4.0,
        "description": "Analysts preview AMD earnings.",
    },
]
```

### Price rows

```python
{
    ("NVDA", "15min"): [
        ("2026-07-30T13:30:00+0000", 100.0, 102.0, 99.0, 101.0, 100),
        ("2026-07-30T13:45:00+0000", 101.0, 106.0, 100.0, 105.0, 120),
    ],
    ("NVDA", "1d"): [
        ("2026-07-29T00:00:00+0000", 100.0, 106.0, 99.0, 105.0, 1000),
        ("2026-07-30T00:00:00+0000", 105.0, 112.0, 104.0, 110.0, 1200),
    ],
    ("AMD", "15min"): [
        ("2026-07-30T13:30:00+0000", 50.0, 52.0, 49.0, 51.0, 200),
        ("2026-07-30T13:45:00+0000", 51.0, 53.0, 50.0, 52.0, 220),
    ],
    ("AMD", "1d"): [
        ("2026-07-29T00:00:00+0000", 50.0, 53.0, 49.0, 52.0, 2000),
        ("2026-07-30T00:00:00+0000", 52.0, 53.0, 50.0, 51.0, 2200),
    ],
}
```

### Fundamentals row

```python
{
    "collected_at": "2026-07-30T00:00:00+0000",
    "snapshot": {
        "market_cap": 1_500_000_000_000.0,
        "pe_ratio": 30.0,
        "price_to_sales": 15.0,
        "price_to_book": 25.0,
    },
}
```

These fixtures prove consumer behavior. Existing real-shape anchors remain:

```text
tests/test_sqlite_backend.py
tests/test_fundamentals_sec_cache.py
tests/test_news_scores.py
tests/test_db_backend.py
```

Their current protected gate is `94 passed / 18 skipped / 112 collected`.

---

### Task 0: Re-ground Base, Reporter, And Target Hashes

**Files:**
- Read: `docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md`
- Create outside Git: `/tmp/eir002-green-baseline/arkscope_eir002_reporter.py`
- Create outside Git: `/tmp/eir002-green-baseline/run_native.sh`
- Create outside Git: `/tmp/eir002-green-baseline/*.json`
- Create outside Git: `/tmp/eir002-green-baseline/*.nodes`

- [ ] **Step 1: Confirm branch, ancestry, and clean worktree**

Run:

```bash
git status --short --branch
git merge-base --is-ancestor 20d4e7e2 HEAD
git diff --name-only 20d4e7e2...HEAD
readlink -f node_modules
```

Expected:

```text
branch: codex/eir-002-green-backend-baseline
merge-base exit: 0
diff since design: plan/authority docs only
node_modules: /mnt/md0/PycharmProjects/ArkScope/node_modules
```

Stop if a product/test file already differs or the worktree is dirty.

- [ ] **Step 2: Create and verify the pinned reporter and native wrapper**

Create the Section 3 and Section 3.1 sources with `apply_patch`, mark only the
wrapper executable, then run:

```bash
python -m py_compile /tmp/eir002-green-baseline/arkscope_eir002_reporter.py
sha256sum /tmp/eir002-green-baseline/arkscope_eir002_reporter.py
chmod 0755 /tmp/eir002-green-baseline/run_native.sh
bash -n /tmp/eir002-green-baseline/run_native.sh
wc -l -c /tmp/eir002-green-baseline/run_native.sh
sha256sum /tmp/eir002-green-baseline/run_native.sh
```

Expected identities:

```text
reporter:
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
wrapper:
79 lines / 2353 bytes
e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f
```

- [ ] **Step 3: Reproduce base canonical and focused collections**

Run collect-only with:

```bash
PYTHONPATH="/tmp/eir002-green-baseline:$(git rev-parse --show-toplevel)" \
PRICE_TRUTH_TIER_REPORT=/tmp/eir002-green-baseline/base-full.json \
pytest --collect-only -q -p arkscope_eir002_reporter
```

Run the same command for the five focused files:

```bash
PYTHONPATH="/tmp/eir002-green-baseline:$(git rev-parse --show-toplevel)" \
PRICE_TRUTH_TIER_REPORT=/tmp/eir002-green-baseline/base-focused.json \
pytest --collect-only -q -p arkscope_eir002_reporter \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

Extract and hash with:

```bash
jq -r '.collected_node_ids[]' \
  /tmp/eir002-green-baseline/base-full.json \
  > /tmp/eir002-green-baseline/base-full.nodes
jq -r '.collected_node_ids[]' \
  /tmp/eir002-green-baseline/base-focused.json \
  > /tmp/eir002-green-baseline/base-focused.nodes
LC_ALL=C sort -c /tmp/eir002-green-baseline/base-full.nodes
LC_ALL=C sort -c /tmp/eir002-green-baseline/base-focused.nodes
wc -l /tmp/eir002-green-baseline/base-full.nodes \
  /tmp/eir002-green-baseline/base-focused.nodes
sha256sum /tmp/eir002-green-baseline/base-full.nodes \
  /tmp/eir002-green-baseline/base-focused.nodes
```

Expected:

```text
base-full.nodes:    4739 / a72bbd36dfad3d36aee2e6630e6024ec9fb4e910bebaf1363d44df8a1aa204dd
base-focused.nodes:  132 / 76f8f087a24f2ff2934274cbbd1711d203c9dbe7056ba4bf5d6022b2d1a03f9c
```

- [ ] **Step 4: Construct target identities before edits**

Create a sorted `/tmp/eir002-green-baseline/retired.nodes` containing exactly:

```text
tests/test_data_access.py::TestFundamentals::test_available_fundamentals_tickers
tests/test_data_access.py::TestFundamentals::test_fundamentals_has_ratios
tests/test_data_access.py::TestFundamentals::test_get_fundamentals
tests/test_data_access.py::TestNews::test_get_news_all
tests/test_data_access.py::TestNews::test_get_news_source_breakdown
tests/test_data_access.py::TestPrices::test_available_price_tickers
tests/test_data_access.py::TestPrices::test_get_prices_15min
tests/test_data_access.py::TestPrices::test_get_prices_daily_resampled
tests/test_data_access.py::TestPrices::test_get_prices_hourly
```

Run:

```bash
LC_ALL=C sort -c /tmp/eir002-green-baseline/retired.nodes
comm -23 \
  /tmp/eir002-green-baseline/base-full.nodes \
  /tmp/eir002-green-baseline/retired.nodes \
  > /tmp/eir002-green-baseline/target-full.nodes
comm -23 \
  /tmp/eir002-green-baseline/base-focused.nodes \
  /tmp/eir002-green-baseline/retired.nodes \
  > /tmp/eir002-green-baseline/target-focused.nodes
wc -l /tmp/eir002-green-baseline/target-full.nodes \
  /tmp/eir002-green-baseline/target-focused.nodes
sha256sum /tmp/eir002-green-baseline/target-full.nodes \
  /tmp/eir002-green-baseline/target-focused.nodes

comm -13 \
  /tmp/eir002-green-baseline/base-full.nodes \
  /tmp/eir002-green-baseline/target-full.nodes \
  > /tmp/eir002-green-baseline/target-full.added.nodes
comm -23 \
  /tmp/eir002-green-baseline/base-full.nodes \
  /tmp/eir002-green-baseline/target-full.nodes \
  > /tmp/eir002-green-baseline/target-full.removed.nodes
test ! -s /tmp/eir002-green-baseline/target-full.added.nodes
cmp \
  /tmp/eir002-green-baseline/retired.nodes \
  /tmp/eir002-green-baseline/target-full.removed.nodes
```

Expected:

```text
target-full.nodes:    4730 / c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb
target-focused.nodes:  123 / 37386cd24fca323338fcb0fb2bbe5c42b7c471d2e9fde2e7c5f345b5ce631b8f
```

Run the focused proof:

```bash
comm -13 \
  /tmp/eir002-green-baseline/base-focused.nodes \
  /tmp/eir002-green-baseline/target-focused.nodes \
  > /tmp/eir002-green-baseline/target-focused.added.nodes
comm -23 \
  /tmp/eir002-green-baseline/base-focused.nodes \
  /tmp/eir002-green-baseline/target-focused.nodes \
  > /tmp/eir002-green-baseline/target-focused.removed.nodes
test ! -s /tmp/eir002-green-baseline/target-focused.added.nodes
cmp \
  /tmp/eir002-green-baseline/retired.nodes \
  /tmp/eir002-green-baseline/target-focused.removed.nodes
```

- [ ] **Step 5: Reproduce the exact native canonical and focused RED baseline**

Run the exact native wrapper from an unrestricted terminal context:

```bash
/tmp/eir002-green-baseline/run_native.sh base-full-v2

/tmp/eir002-green-baseline/run_native.sh base-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

The pre-amendment `base-full` stage is immutable rejected evidence: its
restricted `PATH` omitted the pinned Node.js toolchain and produced 54
additional `FileNotFoundError: 'node'` failures. Preserve that single-use
runtime, report, and transcript. It is not a base result and must not be
imported into any ledger row. `base-full-v2` is the first admissible canonical
attempt under the corrected wrapper.

Expected reporter facts:

```text
base-full-v2:
collected: 4739
seen: 4739
passed: 4640
failed: 27
skipped: 72

base-focused:
collected: 132
seen: 132
passed: 105
failed: 27

both non-passing sets:
non-passing SHA: 7aafce5d2cba923480cc1fb6221bce4f5a33e0bf61c06cf94227cafefe227f15
```

The two reporter `nonpassing_node_ids` arrays must be byte-equal. Any
different set, incomplete `seen_node_ids`, or extra full-suite error is a Stop
Condition. Do not reinterpret it or substitute the historical census.

- [ ] **Step 6: Run protected current-shape anchors**

Run:

```bash
pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_news_scores.py \
  tests/test_db_backend.py
```

Expected:

```text
94 passed, 18 skipped
```

- [ ] **Step 7: Record Task 0 without changing product or tests**

Create the evidence document with this initial structure:

```markdown
# EIR-002 Green Backend Baseline Evidence

> **Status:** IMPLEMENTATION IN PROGRESS
>
> **Date:** 2026-07-31
> **Design:** `20d4e7e2`
> **Plan commit:** record the exact reviewed plan tip from `git rev-parse HEAD`
> before Task 0 starts

## 1. Grounding

- branch/worktree:
- base collection:
- focused collection:
- target identities constructed before edits:
- reporter identity:
- native wrapper identity:
- wakeup probe identity/result:
- native 27-node baseline:
- protected current-shape anchors:

## 2. Stage Ledger

| Stage | Collection | Passed | Failed | Non-passing SHA |
|---|---:|---:|---:|---|

## 3. RED And Mutation Evidence

## 4. Protected Boundaries

## 5. Native Final Admission

## 6. Reviewed Merge And Closeout
```

Replace every grounding bullet with the exact command, artifact path, count,
and SHA observed in Steps 1-6. Replace the plan-commit instruction with the
actual reviewed SHA before commit. Add a newest-first priority-map entry
stating that Task 0
reproduced the base and that product/test edits remain blocked until the
independent plan review clears implementation.

Commit only evidence/authority docs:

```bash
git add docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md \
        docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: ground EIR-002 implementation"
```

---

### Task 1: Remove Nine Obsolete Ambient Data Nodes

**Files:**
- Modify: `tests/test_data_access.py`
- Modify: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`

- [ ] **Step 1: Delete exactly the nine approved test functions**

Remove these complete function bodies and no others:

```text
TestNews.test_get_news_all
TestNews.test_get_news_source_breakdown
TestPrices.test_get_prices_15min
TestPrices.test_get_prices_hourly
TestPrices.test_get_prices_daily_resampled
TestPrices.test_available_price_tickers
TestFundamentals.test_get_fundamentals
TestFundamentals.test_fundamentals_has_ratios
TestFundamentals.test_available_fundamentals_tickers
```

Do not delete the classes, fixtures, protocol/config tests, empty-result tests,
schema tests, or cache tests.

- [ ] **Step 2: Prove collection is exact `-9/+0` immediately**

Re-run both collect commands from Task 0. Expected:

```text
canonical: 4730 / c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb
focused:    123 / 37386cd24fca323338fcb0fb2bbe5c42b7c471d2e9fde2e7c5f345b5ce631b8f
```

Use `comm` to prove the nine removed IDs are the only missing IDs.

- [ ] **Step 3: Run the remaining DAL file**

Run:

```bash
pytest -q tests/test_data_access.py
```

Expected:

```text
19 passed
```

- [ ] **Step 4: Run the native five-file checkpoint**

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh after-retirement-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

Expected:

```text
105 passed / 18 failed / 123 collected
non-passing SHA:
567ea435111078f45dee4c818e282997e1d562e72cf2ddc5a5101a09527cd225
```

- [ ] **Step 5: Commit the retirement**

```bash
git add tests/test_data_access.py \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md
git commit -m "test: retire obsolete ambient data contracts"
```

---

### Task 2: Rewire Seven News Consumers

**Files:**
- Modify: `tests/test_api.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_agents.py`
- Modify: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`

- [ ] **Step 1: Strengthen the seven existing news assertions while they are still RED**

Keep the existing `client`/`dal` parameters for this step and replace only the
assertion bodies with these exact facts.

`tests/test_api.py`:

```python
class TestNewsEndpoints:
    def test_get_news(self, client):
        r = client.get("/news/NVDA?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["count"] == 2
        assert data["source_breakdown"] == {"polygon": 1, "ibkr": 1}

    def test_get_news_sentiment(self, client):
        r = client.get("/news/NVDA/sentiment?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["article_count"] == 2
        assert data["scored_count"] == 2
        assert data["sentiment_mean"] == 4.0
        assert data["bullish_ratio"] == 0.5

    def test_search_news(self, client):
        r = client.get("/news/search/keyword?keyword=earnings&days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert {article["ticker"] for article in data["articles"]} == {"NVDA", "AMD"}
```

`tests/test_tools.py`:

```python
class TestNewsTools:
    def test_get_ticker_news(self, dal):
        from src.tools.news_tools import get_ticker_news
        result = get_ticker_news(dal, ticker="NVDA", days=9999)
        assert isinstance(result, NewsQueryResult)
        assert result.ticker == "NVDA"
        assert result.count == 2
        assert result.source_breakdown == {"polygon": 1, "ibkr": 1}

    def test_get_news_sentiment_summary(self, dal):
        from src.tools.news_tools import get_news_sentiment_summary
        result = get_news_sentiment_summary(dal, ticker="NVDA", days=9999)
        assert result["ticker"] == "NVDA"
        assert result["article_count"] == 2
        assert result["scored_count"] == 2
        assert result["sentiment_mean"] == 4.0
        assert result["bullish_ratio"] == 0.5

    def test_search_news_by_keyword(self, dal):
        from src.tools.news_tools import search_news_by_keyword
        result = search_news_by_keyword(dal, keyword="earnings", days=9999)
        assert isinstance(result, NewsQueryResult)
        assert result.count == 2
        assert {article.ticker for article in result.articles} == {"NVDA", "AMD"}
```

`tests/test_agents.py`:

```python
def test_execute_get_ticker_news(self, dal):
    from src.agents.anthropic_agent.tools import execute_tool

    result = execute_tool(
        "get_ticker_news",
        {"ticker": "NVDA", "days": 9999},
        dal,
    )

    data = json.loads(_unwrap(result))
    assert data["ticker"] == "NVDA"
    assert data["count"] == 2
    assert data["source_breakdown"] == {"polygon": 1, "ibkr": 1}
```

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh news-red \
  tests/test_api.py::TestNewsEndpoints::test_get_news \
  tests/test_api.py::TestNewsEndpoints::test_get_news_sentiment \
  tests/test_api.py::TestNewsEndpoints::test_search_news \
  tests/test_tools.py::TestNewsTools::test_get_ticker_news \
  tests/test_tools.py::TestNewsTools::test_get_news_sentiment_summary \
  tests/test_tools.py::TestNewsTools::test_search_news_by_keyword \
  tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_ticker_news
```

Expected: all seven remain RED because the old ambient fixture cannot satisfy
the exact dataset. A missing fixture/import or SQLite error is wrong-RED and
must be fixed before continuing.

- [ ] **Step 2: Add the deterministic backend to `tests/test_api.py`**

Add imports:

```python
import httpx
import pandas as pd

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
```

Add this helper block after the existing module-level `client` fixture. Helpers
remain private and do not add nodes:

```python
_HERMETIC_NEWS_ROWS = [
    {
        "date": "2026-07-30T14:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA earnings beat expectations",
        "source": "polygon",
        "url": "https://example.test/nvda-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 5.0,
        "risk_score": 2.0,
        "description": "NVIDIA reported stronger earnings.",
    },
    {
        "date": "2026-07-30T13:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA product update",
        "source": "ibkr",
        "url": "https://example.test/nvda-product",
        "publisher": "Example Desk",
        "sentiment_score": 3.0,
        "risk_score": 3.0,
        "description": "NVIDIA announced a product update.",
    },
    {
        "date": "2026-07-30T12:00:00+0000",
        "ticker": "AMD",
        "title": "AMD earnings preview",
        "source": "finnhub",
        "url": "https://example.test/amd-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 2.0,
        "risk_score": 4.0,
        "description": "Analysts preview AMD earnings.",
    },
]

_HERMETIC_PRICE_ROWS = {
    ("NVDA", "15min"): [
        ("2026-07-30T13:30:00+0000", 100.0, 102.0, 99.0, 101.0, 100),
        ("2026-07-30T13:45:00+0000", 101.0, 106.0, 100.0, 105.0, 120),
    ],
    ("NVDA", "1d"): [
        ("2026-07-29T00:00:00+0000", 100.0, 106.0, 99.0, 105.0, 1000),
        ("2026-07-30T00:00:00+0000", 105.0, 112.0, 104.0, 110.0, 1200),
    ],
    ("AMD", "15min"): [
        ("2026-07-30T13:30:00+0000", 50.0, 52.0, 49.0, 51.0, 200),
        ("2026-07-30T13:45:00+0000", 51.0, 53.0, 50.0, 52.0, 220),
    ],
    ("AMD", "1d"): [
        ("2026-07-29T00:00:00+0000", 50.0, 53.0, 49.0, 52.0, 2000),
        ("2026-07-30T00:00:00+0000", 52.0, 53.0, 50.0, 51.0, 2200),
    ],
}

_PRICE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


class _HermeticMarketBackend:
    def query_news(
        self,
        ticker=None,
        days=30,
        source="auto",
        scored_only=True,
        model=None,
    ):
        del days, model
        frame = pd.DataFrame(_HERMETIC_NEWS_ROWS)
        if ticker:
            frame = frame[frame["ticker"] == ticker.upper()]
        if source not in ("", "auto", None):
            frame = frame[frame["source"] == source]
        if scored_only:
            frame = frame[frame["sentiment_score"].notna()]
        return frame.reset_index(drop=True)

    def query_prices(self, ticker, interval="15min", days=30):
        del days
        rows = _HERMETIC_PRICE_ROWS.get((ticker.upper(), interval), [])
        return pd.DataFrame(rows, columns=_PRICE_COLUMNS)

    def query_fundamentals(self, ticker):
        if ticker.upper() != "NVDA":
            return {}
        return {
            "collected_at": "2026-07-30T00:00:00+0000",
            "snapshot": {
                "market_cap": 1_500_000_000_000.0,
                "pe_ratio": 30.0,
                "price_to_sales": 15.0,
                "price_to_book": 25.0,
            },
        }

    def get_available_tickers(self, data_type):
        return {
            "news": ["AMD", "NVDA"],
            "prices": ["AMD", "NVDA"],
            "fundamentals": ["NVDA"],
        }.get(data_type, [])


@pytest.fixture()
def hermetic_market_app():
    app = create_app()
    dal = DataAccessLayer(
        base_path=project_root,
        backend=_HermeticMarketBackend(),
    )
    app.dependency_overrides[get_dal] = lambda: dal
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_dal, None)


def _api_get(app, path):
    async def _request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(_request())


def _install_fundamentals_provider_spies(monkeypatch):
    calls = []

    def _record_sec(*args, **kwargs):
        del args, kwargs
        calls.append("sec_edgar")
        raise RuntimeError("SEC provider fallback reached")

    def _record_fd(*args, **kwargs):
        del args, kwargs
        calls.append("financial_datasets")
        return False

    monkeypatch.setattr(
        "data_sources.sec_edgar_financials.SECEdgarFinancials",
        _record_sec,
    )
    monkeypatch.setattr(
        "src.tools.analysis_tools._is_fd_enabled",
        _record_fd,
    )
    return calls
```

This uses the real app/router/HTTP/serialization path but does not enter app
lifespan. Do not copy the `run_in_threadpool` patch used by the SA route test;
these EIR-002 API nodes are admitted natively.

- [ ] **Step 3: Add the deterministic backend to `tests/test_tools.py`**

Add `import pandas as pd`, then add this block after the existing `dal`
fixture:

```python
_HERMETIC_NEWS_ROWS = [
    {
        "date": "2026-07-30T14:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA earnings beat expectations",
        "source": "polygon",
        "url": "https://example.test/nvda-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 5.0,
        "risk_score": 2.0,
        "description": "NVIDIA reported stronger earnings.",
    },
    {
        "date": "2026-07-30T13:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA product update",
        "source": "ibkr",
        "url": "https://example.test/nvda-product",
        "publisher": "Example Desk",
        "sentiment_score": 3.0,
        "risk_score": 3.0,
        "description": "NVIDIA announced a product update.",
    },
    {
        "date": "2026-07-30T12:00:00+0000",
        "ticker": "AMD",
        "title": "AMD earnings preview",
        "source": "finnhub",
        "url": "https://example.test/amd-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 2.0,
        "risk_score": 4.0,
        "description": "Analysts preview AMD earnings.",
    },
]

_HERMETIC_PRICE_ROWS = {
    ("NVDA", "15min"): [
        ("2026-07-30T13:30:00+0000", 100.0, 102.0, 99.0, 101.0, 100),
        ("2026-07-30T13:45:00+0000", 101.0, 106.0, 100.0, 105.0, 120),
    ],
    ("NVDA", "1d"): [
        ("2026-07-29T00:00:00+0000", 100.0, 106.0, 99.0, 105.0, 1000),
        ("2026-07-30T00:00:00+0000", 105.0, 112.0, 104.0, 110.0, 1200),
    ],
    ("AMD", "15min"): [
        ("2026-07-30T13:30:00+0000", 50.0, 52.0, 49.0, 51.0, 200),
        ("2026-07-30T13:45:00+0000", 51.0, 53.0, 50.0, 52.0, 220),
    ],
    ("AMD", "1d"): [
        ("2026-07-29T00:00:00+0000", 50.0, 53.0, 49.0, 52.0, 2000),
        ("2026-07-30T00:00:00+0000", 52.0, 53.0, 50.0, 51.0, 2200),
    ],
}

_PRICE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


class _HermeticMarketBackend:
    def query_news(
        self,
        ticker=None,
        days=30,
        source="auto",
        scored_only=True,
        model=None,
    ):
        del days, model
        frame = pd.DataFrame(_HERMETIC_NEWS_ROWS)
        if ticker:
            frame = frame[frame["ticker"] == ticker.upper()]
        if source not in ("", "auto", None):
            frame = frame[frame["source"] == source]
        if scored_only:
            frame = frame[frame["sentiment_score"].notna()]
        return frame.reset_index(drop=True)

    def query_prices(self, ticker, interval="15min", days=30):
        del days
        rows = _HERMETIC_PRICE_ROWS.get((ticker.upper(), interval), [])
        return pd.DataFrame(rows, columns=_PRICE_COLUMNS)

    def query_fundamentals(self, ticker):
        if ticker.upper() != "NVDA":
            return {}
        return {
            "collected_at": "2026-07-30T00:00:00+0000",
            "snapshot": {
                "market_cap": 1_500_000_000_000.0,
                "pe_ratio": 30.0,
                "price_to_sales": 15.0,
                "price_to_book": 25.0,
            },
        }

    def get_available_tickers(self, data_type):
        return {
            "news": ["AMD", "NVDA"],
            "prices": ["AMD", "NVDA"],
            "fundamentals": ["NVDA"],
        }.get(data_type, [])


@pytest.fixture()
def hermetic_dal():
    return DataAccessLayer(
        base_path=project_root,
        backend=_HermeticMarketBackend(),
    )


def _install_fundamentals_provider_spies(monkeypatch):
    calls = []

    def _record_sec(*args, **kwargs):
        del args, kwargs
        calls.append("sec_edgar")
        raise RuntimeError("SEC provider fallback reached")

    def _record_fd(*args, **kwargs):
        del args, kwargs
        calls.append("financial_datasets")
        return False

    monkeypatch.setattr(
        "data_sources.sec_edgar_financials.SECEdgarFinancials",
        _record_sec,
    )
    monkeypatch.setattr(
        "src.tools.analysis_tools._is_fd_enabled",
        _record_fd,
    )
    return calls
```

- [ ] **Step 4: Add the minimal deterministic backend to `tests/test_agents.py`**

Add `import pandas as pd`, then add this block before
`TestAnthropicToolExecution`:

```python
class _HermeticAgentBackend:
    def query_news(
        self,
        ticker=None,
        days=30,
        source="auto",
        scored_only=True,
        model=None,
    ):
        del days, model
        rows = [
            {
                "date": "2026-07-30T14:00:00+0000",
                "ticker": "NVDA",
                "title": "NVIDIA earnings beat expectations",
                "source": "polygon",
                "url": "https://example.test/nvda-earnings",
                "publisher": "Example Wire",
                "sentiment_score": 5.0,
                "risk_score": 2.0,
                "description": "NVIDIA reported stronger earnings.",
            },
            {
                "date": "2026-07-30T13:00:00+0000",
                "ticker": "NVDA",
                "title": "NVIDIA product update",
                "source": "ibkr",
                "url": "https://example.test/nvda-product",
                "publisher": "Example Desk",
                "sentiment_score": 3.0,
                "risk_score": 3.0,
                "description": "NVIDIA announced a product update.",
            },
        ]
        frame = pd.DataFrame(rows)
        if ticker:
            frame = frame[frame["ticker"] == ticker.upper()]
        if source not in ("", "auto", None):
            frame = frame[frame["source"] == source]
        if scored_only:
            frame = frame[frame["sentiment_score"].notna()]
        return frame.reset_index(drop=True)

    def query_prices(self, ticker, interval="15min", days=30):
        del days
        if ticker.upper() != "NVDA" or interval not in ("15min", "1d"):
            return pd.DataFrame(
                columns=["datetime", "open", "high", "low", "close", "volume"]
            )
        if interval == "1d":
            rows = [
                ("2026-07-29T00:00:00+0000", 100.0, 106.0, 99.0, 105.0, 1000),
                ("2026-07-30T00:00:00+0000", 105.0, 112.0, 104.0, 110.0, 1200),
            ]
        else:
            rows = [
                ("2026-07-30T13:30:00+0000", 100.0, 102.0, 99.0, 101.0, 100),
                ("2026-07-30T13:45:00+0000", 101.0, 106.0, 100.0, 105.0, 120),
            ]
        return pd.DataFrame(
            rows,
            columns=["datetime", "open", "high", "low", "close", "volume"],
        )


@pytest.fixture()
def hermetic_dal():
    return DataAccessLayer(backend=_HermeticAgentBackend())
```

- [ ] **Step 5: Switch only the seven news nodes to the new seams**

In `tests/test_api.py`, change the three news parameters from `client` to
`hermetic_market_app` and replace `client.get(...)` with
`_api_get(hermetic_market_app, ...)`.

In `tests/test_tools.py`, change only the three news parameters from `dal` to
`hermetic_dal` and pass `hermetic_dal` to the function under test.

In `tests/test_agents.py`, change only
`test_execute_get_ticker_news(self, dal)` to
`test_execute_get_ticker_news(self, hermetic_dal)` and pass `hermetic_dal` to
`execute_tool`.

Do not alter the module-wide `client` or `dal` fixtures. Unrelated nodes must
retain their existing setup.

- [ ] **Step 6: Run the seven news nodes natively**

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh news-green \
  tests/test_api.py::TestNewsEndpoints::test_get_news \
  tests/test_api.py::TestNewsEndpoints::test_get_news_sentiment \
  tests/test_api.py::TestNewsEndpoints::test_search_news \
  tests/test_tools.py::TestNewsTools::test_get_ticker_news \
  tests/test_tools.py::TestNewsTools::test_get_news_sentiment_summary \
  tests/test_tools.py::TestNewsTools::test_search_news_by_keyword \
  tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_ticker_news
```

Expected:

```text
7 passed
```

Then run:

```bash
/tmp/eir002-green-baseline/run_native.sh after-news-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

Expected:

```text
112 passed / 11 failed / 123 collected
non-passing SHA:
e6d59e3ec3e24b3d8ef2d68c341af5dcbb8c3bd0f264e71a130a45713ad8203c
```

- [ ] **Step 7: Prove the transferred source-breakdown assertion is sensitive**

Temporarily change the second NVDA fixture source from `"ibkr"` to
`"polygon"` in `tests/test_tools.py`.

Run:

```bash
pytest -q tests/test_tools.py::TestNewsTools::test_get_ticker_news
```

Expected: RED because the actual breakdown becomes `{"polygon": 2}` rather
than `{"polygon": 1, "ibkr": 1}`.

Restore the exact bytes and rerun GREEN. Record the temporary diff and result
in evidence.

- [ ] **Step 8: Commit the news rewire**

```bash
git add tests/test_api.py tests/test_tools.py tests/test_agents.py \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md
git commit -m "test: make news consumer contracts hermetic"
```

---

### Task 3: Rewire Eight Price Consumers

**Files:**
- Modify: `tests/test_api.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_agents.py`
- Modify: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`

- [ ] **Step 1: Replace the eight price assertions before switching fixtures**

Keep the old `client`/`dal` parameters for the RED run.

`tests/test_api.py`:

```python
class TestHealth:
    def test_status(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["tools_registered"] == 53
        assert data["data_sources"] == {
            "news_tickers": 2,
            "price_tickers": 2,
            "fundamentals_tickers": 1,
        }


class TestPriceEndpoints:
    def test_get_prices(self, client):
        r = client.get("/prices/NVDA?interval=15min&days=7")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["count"] == 2
        assert [bar["close"] for bar in data["bars"]] == [101.0, 105.0]

    def test_price_change(self, client):
        r = client.get("/prices/NVDA/change?days=30")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["bar_count"] == 2
        assert data["change_pct"] == 10.0
        assert data["period_high"] == 112.0
        assert data["period_low"] == 99.0

    def test_sector_performance(self, client):
        r = client.get("/prices/sector/AI_CHIPS?days=30")
        assert r.status_code == 200
        data = r.json()
        assert data["sector"] == "AI_CHIPS"
        assert data["ticker_count"] == 2
        assert data["avg_change_pct"] == 6.0
        assert data["best_ticker"] == "NVDA"
        assert data["worst_ticker"] == "AMD"
```

`tests/test_tools.py`:

```python
class TestPriceTools:
    def test_get_ticker_prices(self, dal):
        from src.tools.price_tools import get_ticker_prices
        result = get_ticker_prices(dal, ticker="NVDA", interval="15min", days=7)
        assert isinstance(result, PriceQueryResult)
        assert result.ticker == "NVDA"
        assert result.count == 2
        assert [bar.close for bar in result.bars] == [101.0, 105.0]

    def test_get_price_change(self, dal):
        from src.tools.price_tools import get_price_change
        result = get_price_change(dal, ticker="NVDA", days=30)
        assert result["ticker"] == "NVDA"
        assert result["bar_count"] == 2
        assert result["change_pct"] == 10.0
        assert result["period_high"] == 112.0
        assert result["period_low"] == 99.0
        assert result["total_volume"] == 2200

    def test_get_sector_performance(self, dal):
        from src.tools.price_tools import get_sector_performance
        result = get_sector_performance(dal, sector="AI_CHIPS", days=30)
        assert result["sector"] == "AI_CHIPS"
        assert result["ticker_count"] == 2
        assert result["avg_change_pct"] == 6.0
        assert result["best_ticker"] == "NVDA"
        assert result["worst_ticker"] == "AMD"
```

`tests/test_agents.py`:

```python
def test_execute_get_price_change(self, dal):
    from src.agents.anthropic_agent.tools import execute_tool

    result = execute_tool(
        "get_price_change",
        {"ticker": "NVDA", "days": 30},
        dal,
    )

    data = json.loads(_unwrap(result))
    assert data["ticker"] == "NVDA"
    assert data["bar_count"] == 2
    assert data["change_pct"] == 10.0
```

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh prices-red \
  tests/test_api.py::TestHealth::test_status \
  tests/test_api.py::TestPriceEndpoints::test_get_prices \
  tests/test_api.py::TestPriceEndpoints::test_price_change \
  tests/test_api.py::TestPriceEndpoints::test_sector_performance \
  tests/test_tools.py::TestPriceTools::test_get_ticker_prices \
  tests/test_tools.py::TestPriceTools::test_get_price_change \
  tests/test_tools.py::TestPriceTools::test_get_sector_performance \
  tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_price_change
```

Expected: all eight remain RED against the ambient fixtures.

- [ ] **Step 2: Switch only the eight price nodes**

In `tests/test_api.py`, change the four price/status parameters to
`hermetic_market_app` and route requests through `_api_get`.

In `tests/test_tools.py`, change the three price parameters to `hermetic_dal`
and pass it to the function under test.

In `tests/test_agents.py`, change only the price-dispatch parameter to
`hermetic_dal` and pass it to `execute_tool`.

- [ ] **Step 3: Run the price nodes and checkpoint**

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh prices-green \
  tests/test_api.py::TestHealth::test_status \
  tests/test_api.py::TestPriceEndpoints::test_get_prices \
  tests/test_api.py::TestPriceEndpoints::test_price_change \
  tests/test_api.py::TestPriceEndpoints::test_sector_performance \
  tests/test_tools.py::TestPriceTools::test_get_ticker_prices \
  tests/test_tools.py::TestPriceTools::test_get_price_change \
  tests/test_tools.py::TestPriceTools::test_get_sector_performance \
  tests/test_agents.py::TestAnthropicToolExecution::test_execute_get_price_change
```

Expected price-focused result:

```text
8 passed
```

Expected five-file checkpoint:

```text
120 passed / 3 failed / 123 collected
non-passing SHA:
c072d5df09468496bb8fa26ade78cf38e1846be9b1dbe665502db60ae1e69664
```

Run the checkpoint with:

```bash
/tmp/eir002-green-baseline/run_native.sh after-prices-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

- [ ] **Step 4: Prove price math sensitivity**

Temporarily change the final NVDA daily close in `tests/test_tools.py` from
`110.0` to `100.0`.

Run:

```bash
pytest -q tests/test_tools.py::TestPriceTools::test_get_price_change
```

Expected: RED on `change_pct == 10.0`. Restore exact bytes and rerun GREEN.
Record the temporary diff and result.

- [ ] **Step 5: Commit the price rewire**

```bash
git add tests/test_api.py tests/test_tools.py tests/test_agents.py \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md
git commit -m "test: make price consumer contracts hermetic"
```

---

### Task 4: Rewire Two Fundamentals Consumers

**Files:**
- Modify: `tests/test_api.py`
- Modify: `tests/test_tools.py`
- Modify: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`

- [ ] **Step 1: Strengthen both fundamentals assertions while still RED**

`tests/test_api.py`:

```python
class TestFundamentalsEndpoints:
    def test_fundamentals(self, client, monkeypatch):
        provider_calls = _install_fundamentals_provider_spies(monkeypatch)
        r = client.get("/fundamentals/NVDA")
        assert r.status_code == 200
        assert provider_calls == []
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["data_source"] == "ibkr"
        assert data["market_cap"] == 1_500_000_000_000.0
        assert data["pe_ratio"] == 30.0
```

`tests/test_tools.py`:

```python
class TestAnalysisTools:
    def test_get_fundamentals_analysis(self, dal, monkeypatch):
        from src.tools.analysis_tools import get_fundamentals_analysis
        provider_calls = _install_fundamentals_provider_spies(monkeypatch)
        result = get_fundamentals_analysis(dal, ticker="NVDA")
        assert provider_calls == []
        assert isinstance(result, FundamentalsResult)
        assert result.ticker == "NVDA"
        assert result.data_source == "ibkr"
        assert result.market_cap == 1_500_000_000_000.0
        assert result.pe_ratio == 30.0
```

Run both IDs natively before switching fixtures:

```bash
/tmp/eir002-green-baseline/run_native.sh fundamentals-red \
  tests/test_api.py::TestFundamentalsEndpoints::test_fundamentals \
  tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis
```

Expected: RED with `provider_calls` containing the attempted fallback, or on
the exact absent-data assertion if the current ambient path returns before a
fallback. A network result, credential-dependent result, or provider call not
captured by the two spies is wrong-RED and stops implementation.

- [ ] **Step 2: Switch both nodes to deterministic seams**

In `tests/test_api.py`, change the signature to:

```python
def test_fundamentals(self, hermetic_market_app, monkeypatch):
```

Use `_api_get(hermetic_market_app, "/fundamentals/NVDA")`.

In `tests/test_tools.py`, change the signature to:

```python
def test_get_fundamentals_analysis(self, hermetic_dal, monkeypatch):
```

Pass `hermetic_dal` to `get_fundamentals_analysis`.

The fixture's non-empty `collected_at` makes
`get_fundamentals_analysis()` return at the DAL snapshot boundary. Keep
`assert provider_calls == []` before the result-field assertions. SEC EDGAR
and Financial Datasets are the only external fallback branches in this
function; do not invent Finnhub or direct-IBKR patches that are not on this
call chain. The fake backend's `query_fundamentals()` is the expected stored
IBKR-snapshot boundary.

- [ ] **Step 3: Run fundamentals and checkpoint**

Expected:

```text
2 passed
```

Exact command:

```bash
/tmp/eir002-green-baseline/run_native.sh fundamentals-green \
  tests/test_api.py::TestFundamentalsEndpoints::test_fundamentals \
  tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis
```

Expected five-file checkpoint:

```text
122 passed / 1 failed / 123 collected
remaining node:
tests/test_app_records_store.py::test_report_insert_query_roundtrip
remaining SHA:
71b6d959c36e1b7d8e9c92b4904a8e68c46c6c4d7992c0bdc939dc1b220798f0
```

Run that checkpoint with:

```bash
/tmp/eir002-green-baseline/run_native.sh after-fundamentals-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

- [ ] **Step 4: Prove the fundamentals fixture cannot silently empty**

Temporarily change the deterministic `market_cap` in
`tests/test_tools.py` to `None`.

Run:

```bash
pytest -q tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis
```

Expected: RED on the exact market-cap assertion. Restore and rerun GREEN.

- [ ] **Step 5: Commit the fundamentals rewire**

```bash
git add tests/test_api.py tests/test_tools.py \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md
git commit -m "test: make fundamentals consumer contracts hermetic"
```

---

### Task 5: Pin The App-Record Round-Trip Clock

**Files:**
- Modify: `tests/test_app_records_store.py`
- Modify: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`

- [ ] **Step 1: Reproduce the one-node RED**

Run:

```bash
pytest -q tests/test_app_records_store.py::test_report_insert_query_roundtrip
```

Expected: RED because the default 30-day window excludes the fixed 2026-06-20
record on 2026-07-31.

- [ ] **Step 2: Use the existing explicit clock seam**

Change:

```python
df = store.query_reports()
```

to:

```python
df = store.query_reports(today="2026-06-21")
```

Do not change `days`, the inserted date, or any round-trip assertion.

- [ ] **Step 3: Run the node and full app-record file**

Run:

```bash
pytest -q tests/test_app_records_store.py::test_report_insert_query_roundtrip
pytest -q tests/test_app_records_store.py
```

Expected:

```text
round-trip node: 1 passed
file: 20 passed
```

- [ ] **Step 4: Run the final five-file native checkpoint**

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh final-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py
```

Expected:

```text
123 passed / 0 failed / 123 collected
non-passing file empty
empty SHA:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

- [ ] **Step 5: Commit the date fix**

```bash
git add tests/test_app_records_store.py \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md
git commit -m "test: pin app-record round-trip clock"
```

---

### Task 6: Final Collection, Protected Gates, And Native Full Admission

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`
- Modify: `docs/design/ENGINEERING_ISSUE_REGISTER.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Reproduce both target collection hashes**

Run:

```bash
PYTHONPATH="/tmp/eir002-green-baseline:$(git rev-parse --show-toplevel)" \
PRICE_TRUTH_TIER_REPORT=/tmp/eir002-green-baseline/final-collect-full.json \
pytest --collect-only -q -p arkscope_eir002_reporter

PYTHONPATH="/tmp/eir002-green-baseline:$(git rev-parse --show-toplevel)" \
PRICE_TRUTH_TIER_REPORT=/tmp/eir002-green-baseline/final-collect-focused.json \
pytest --collect-only -q -p arkscope_eir002_reporter \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py

jq -r '.collected_node_ids[]' \
  /tmp/eir002-green-baseline/final-collect-full.json \
  > /tmp/eir002-green-baseline/final-collect-full.nodes
jq -r '.collected_node_ids[]' \
  /tmp/eir002-green-baseline/final-collect-focused.json \
  > /tmp/eir002-green-baseline/final-collect-focused.nodes
LC_ALL=C sort -c /tmp/eir002-green-baseline/final-collect-full.nodes
LC_ALL=C sort -c /tmp/eir002-green-baseline/final-collect-focused.nodes
wc -l /tmp/eir002-green-baseline/final-collect-full.nodes \
  /tmp/eir002-green-baseline/final-collect-focused.nodes
sha256sum /tmp/eir002-green-baseline/final-collect-full.nodes \
  /tmp/eir002-green-baseline/final-collect-focused.nodes
```

Expected:

```text
canonical: 4730 / c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb
focused:    123 / 37386cd24fca323338fcb0fb2bbe5c42b7c471d2e9fde2e7c5f345b5ce631b8f
```

Prove:

- all seventeen Section 4.2 IDs occur exactly once;
- the app-record ID occurs exactly once;
- all nine retired IDs are absent; and
- the only base-to-tip collection difference is `retired.nodes`.

- [ ] **Step 2: Run protected current-shape anchors**

Run:

```bash
pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_news_scores.py \
  tests/test_db_backend.py
```

Expected:

```text
94 passed, 18 skipped
```

- [ ] **Step 3: Prove no product or protected data path changed**

Run:

```bash
git diff --quiet 20d4e7e2 -- src data_sources apps config scripts
git diff --name-only 20d4e7e2 -- data
git status --short
```

Expected:

- first command exits 0;
- second command has no output;
- status contains only the five owned tests and approved authority/evidence
  files before their final commit.

Also verify the main-worktree scripts decision remains untracked and unchanged
without staging or reading it into this branch.

- [ ] **Step 4: Run the pinned native wakeup probe**

Reverify its 942-byte SHA and required `true/0/0` result. Stop on any mismatch.

- [ ] **Step 5: Run one fresh native canonical full suite**

Run from the unrestricted native context:

```bash
/tmp/eir002-green-baseline/run_native.sh final-full
```

Expected:

```text
4730 collected
4730 seen
4658 passed
72 skipped
0 failed
exitstatus 0
empty non-passing SHA:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Do not run the full suite concurrently with another gate. If the reporter does
not contain all 4,730 seen IDs, the run is incomplete even if terminal prose
looks green.

- [ ] **Step 6: Inspect and quarantine only newly generated ignored artifacts**

Compare the isolated worktree's pre/post status and file inventory. For any new
ignored DB/cache file, record path, inode, size, and SHA, move it to a unique
`/tmp/eir002-green-baseline/final-quarantine/` path, then prove the worktree is
clean. Never match or remove files by basename alone.

- [ ] **Step 7: Complete implementation-review evidence**

The evidence must include:

- base and target collection lists and hashes;
- every stage's reporter JSON and exact non-passing set hash;
- the three temporary mutation diffs and owning RED results;
- source-breakdown transfer evidence;
- native wakeup probe identity/result;
- protected anchor result;
- full native result;
- product/protected-path byte checks; and
- data hygiene/quarantine record.

Update EIR-002's `next_action` to independent implementation review. Keep its
status `promoted` until reviewed merge and merged verification. Do not alter
EIR-006.

- [ ] **Step 8: Commit the review-ready packet**

```bash
git add tests/test_data_access.py \
        tests/test_api.py \
        tests/test_tools.py \
        tests/test_agents.py \
        tests/test_app_records_store.py \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md \
        docs/design/ENGINEERING_ISSUE_REGISTER.md \
        docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: prepare EIR-002 implementation review"
```

Verify the worktree is clean. Stop for independent implementation review; do
not merge.

---

### Task 7: Reviewed Merge And EIR Closure

**Files:**
- Modify after amendment review: `tests/test_db_backend.py`
- Modify for amendment: `docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md`
- Modify for amendment: `docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md`
- Modify after merge: `docs/design/ENGINEERING_ISSUE_REGISTER.md`
- Modify after merge: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify after merge: `docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md`

- [ ] **Step 1: Require explicit implementation-review clearance**

The review must independently reproduce:

- `4730/c34de9a0...`;
- `123/37386cd2...`;
- all seventeen retained IDs and nine removed IDs;
- the three mutation results;
- protected `94 passed / 18 skipped`;
- native `4658 passed / 72 skipped / 0 failed`; and
- zero product/data changes.

No finding may be waived by the implementer.

- [ ] **Step 2: Fast-forward master to the exact reviewed tip**

From the main worktree, verify `master` is an ancestor and use `git merge
--ff-only`. Do not merge or stage
`docs/design/SCRIPTS_RETIREMENT_DECISION.md`.

- [ ] **Step 3: Run merged focused and native full verification**

The first main-worktree attempt is frozen as rejected Task 7 evidence. It
proved exact collection `4730/c34de9a0...` and focused `123/123`, then stopped
when a real extension sync modified the production log and databases. After
sync was paused, `merged-full` saw all 4,730 nodes but returned one failure:

```text
tests/test_db_backend.py::TestFundamentalsDB::test_fundamentals_via_dal
```

The same node fails in the main worktree with ignored `config/.env` present
and skips in the reviewed worktree where that file is absent. Git history and
the current schema prove that `FundamentalsResult.found` never existed; the
current absence discriminator is `data_source="none"`. The production
scheduler also completed `collect.ibkr_news` run `18436` during the main-root
suite, so that root cannot satisfy the frozen-data admission boundary.

Before another full run:

1. preserve the failed `merged-full` reporter and transcript;
2. change only
   `tests/test_db_backend.py::TestFundamentalsDB::test_fundamentals_via_dal`
   from `result.found is False` to `result.data_source == "none"`;
3. prove the owning node RED before and GREEN after in the data-bearing main
   worktree, with its node ID unchanged;
4. create a fresh worktree at the exact amended master commit, require
   `config/.env` absent, create only an empty `data/` directory, and prove no
   production data file is reachable there; explicitly link only the reviewed
   `node_modules` toolchain; and
5. run fresh `merged-v2-focused` and `merged-v2-full` stages from that clean
   worktree with the unchanged wrapper/reporter/probe identities.

The clean merged worktree, not the production main root, owns canonical
`4658/72/0` admission. The main worktree owning-node pass is supplemental.
Collection remains exactly `+0/-9`; no skip marker or test identity changes.
Any second node failure, production-data access, or canonical pass/skip drift
is a Stop Condition.

The commands below record the historical first attempt and must not be rerun
under the consumed `merged-focused` or `merged-full` stage names. The amended
execution must first record the exact test-fix tip and build its own detached
worktree:

```bash
fix_tip="$(git rev-parse HEAD)"
test -z "$(git status --short --untracked-files=all \
  | grep -v '^?? docs/design/SCRIPTS_RETIREMENT_DECISION.md$')"
test ! -e /tmp/arkscope-eir002-merged-v2
test ! -L /tmp/arkscope-eir002-merged-v2
git worktree add --detach /tmp/arkscope-eir002-merged-v2 "$fix_tip"
cd /tmp/arkscope-eir002-merged-v2
test "$(git rev-parse HEAD)" = "$fix_tip"
test ! -e config/.env
mkdir data
test ! -L data
test -z "$(find data -mindepth 1 -print -quit)"
node_modules_target=/mnt/md0/PycharmProjects/ArkScope/node_modules
test -d "$node_modules_target"
test "$(sha256sum package-lock.json | awk '{print $1}')" = \
  5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
ln -s "$node_modules_target" node_modules
test "$(readlink -f node_modules)" = "$node_modules_target"
test "$(sha256sum node_modules/.package-lock.json | awk '{print $1}')" = \
  4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
test "$(/home/hyl/.nvm/versions/node/v22.14.0/bin/node --version)" = \
  "v22.14.0"
test "$(/home/hyl/.nvm/versions/node/v22.14.0/bin/node \
  -p "require('./node_modules/jsdom/package.json').version")" = "29.1.1"
git status --short --untracked-files=all \
  > /tmp/eir002-green-baseline/merged-v2-pre-status.txt
find data src/data -type f -print 2>/dev/null | LC_ALL=C sort \
  > /tmp/eir002-green-baseline/merged-v2-pre-data.paths
```

Before pytest, also inspect the worktree's full ignored inventory and require
that no project database, historical dataset, provider credential, or other
symlink into the production root is present. `data/` is the sole deliberately
added data path; `node_modules` is the sole allowed production-root link and
is admitted only as the pinned test toolchain above. If any other input is
reachable, stop instead of deleting or masking it.

Run the clean canonical stages from that worktree:

```bash
PYTHONPATH="/tmp/eir002-green-baseline:$(git rev-parse --show-toplevel)" \
PRICE_TRUTH_TIER_REPORT=/tmp/eir002-green-baseline/merged-v2-collect-full.json \
pytest --collect-only -q -p arkscope_eir002_reporter

/tmp/eir002-green-baseline/run_native.sh merged-v2-focused \
  tests/test_data_access.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_agents.py \
  tests/test_app_records_store.py

/tmp/eir002-green-baseline/run_native.sh merged-v2-full

pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_news_scores.py \
  tests/test_db_backend.py
```

Extract and hash `merged-v2-collect-full.json` exactly as in Task 6. Require
`4730/c34de9a0...`, focused `123 passed`, full
`4658 passed / 72 skipped`, empty non-passing set, and protected
`94 passed / 18 skipped`.

Compare merged product/data paths against the pre-implementation merge base.
The only test collection difference must remain the exact nine retired IDs.
The frozen main-root attempts, their consumed stage names, and their artifact
transactions remain auditable in Evidence Section 8; they are not rerun.

- [ ] **Step 4: Reconcile and quarantine merged-run artifacts**

Capture the post-run state:

```bash
git status --short --untracked-files=all \
  > /tmp/eir002-green-baseline/merged-v2-post-status.txt
find data src/data -type f -print 2>/dev/null | LC_ALL=C sort \
  > /tmp/eir002-green-baseline/merged-v2-post-data.paths
comm -13 \
  /tmp/eir002-green-baseline/merged-v2-pre-data.paths \
  /tmp/eir002-green-baseline/merged-v2-post-data.paths \
  > /tmp/eir002-green-baseline/merged-v2-new-data.paths
```

`src/data/cache/risk_free_rate.json` is a known possible full-suite artifact,
not an allowed repository change. For every path in
`merged-v2-new-data.paths`, record its exact path, inode, size, modification
time, and SHA-256. Move each new file by its exact path to a unique location
under `/tmp/eir002-green-baseline/merged-v2-quarantine/`; do not glob or match
by basename. Preserve the quarantine manifest in closeout evidence.

If that known path existed before the run, it is pre-existing user state:
record its pre/post metadata and SHA, require byte identity, and do not move
it. Any modification of a pre-existing ignored file is a Stop Condition.

Re-run the status and data inventory after quarantine. They must be
byte-identical to `merged-v2-pre-status.txt` and
`merged-v2-pre-data.paths`. Re-run the `node_modules` target, installed
lockfile SHA, Node version, and `jsdom` version checks; any drift is a Stop
Condition.
Pre-existing user files, including the untracked scripts-retirement decision,
must remain untouched.

- [ ] **Step 5: Close EIR-002 with exact merged evidence**

Set EIR-002 to `closed` only after merged verification. Record:

- reviewed implementation commit;
- merge/closeout commit;
- exact commands;
- `4730/c34de9a0...`;
- `4658 passed / 72 skipped / 0 failed`; and
- empty non-passing SHA.

Add the newest-first priority-map closeout entry. EIR-006 remains promoted and
independent.

- [ ] **Step 6: Commit docs-only closeout and request focused review**

```bash
git add docs/design/ENGINEERING_ISSUE_REGISTER.md \
        docs/design/PROJECT_PRIORITY_MAP.md \
        docs/superpowers/evidence/2026-07-31-eir-002-green-backend-baseline.md
git commit -m "docs: close EIR-002 green backend baseline"
```

The root scripts-retirement line begins only after this closeout is reviewed.

## 5. Stop Conditions

Stop immediately if:

1. the base collection or 27-node SHA does not match;
2. either target collection hash does not match before edits;
3. a helper is collected as a test;
4. any of the seventeen live IDs is renamed or removed;
5. a removed source-breakdown contract is not RED/GREEN-transferred to
   `test_get_ticker_news`;
6. a retained node requires a provider, key, network call, production DB, old
   repository data, or product-code change;
7. a module-wide fixture change affects unrelated nodes;
8. a family checkpoint changes any non-owning failure;
9. a current backend anchor stops passing;
10. collection differs from exact `+0/-9`;
11. API/full admission is attempted in the incompatible managed sandbox;
12. native wakeup probe is not exact `true/0/0`;
13. full reporter `seen_node_ids` is not exactly the collected set;
14. any product, provider, schema, frontend, scripts, or data file changes;
15. EIR-006 is mixed into this implementation; or
16. old CSV/parquet files are deleted, moved, archived, or rewritten; or
17. a branch or merged native run leaves an unaccounted repository-relative
    artifact; or
18. the clean Task 7 worktree contains `config/.env`, a non-empty `data/`,
    any provider credential or project database, historical data, or a
    symlink that reaches the production root other than the exact pinned
    `node_modules` toolchain link.

## 6. Plan Self-Review Map

| Approved design requirement | Owning task |
|---|---|
| Remove exactly nine ambient nodes | Task 1 |
| Preserve seventeen live IDs | Tasks 2-4, Task 6 |
| Transfer source-breakdown coverage | Task 2 Steps 1, 7 |
| Current-shape deterministic seams | Tasks 2-4 |
| No provider/network work | Task 4, Task 6 |
| Fix date through explicit clock | Task 5 |
| Exact `-9/+0` and target hashes | Task 0, Task 1, Task 6 |
| Native ASGI/full admission | Task 0, Task 6 |
| Preserve current backend anchors | Task 0, Task 6 |
| Zero product/data changes | Task 6 |
| Keep EIR-006 separate | Tasks 6-7 |
| Close only after merged verification | Task 7 |
