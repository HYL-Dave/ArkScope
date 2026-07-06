# S-A1 IBKR News Worker Module Implementation Plan

> **Status: COMPLETED — historical implementation record; closeout entry in `PROJECT_PRIORITY_MAP.md` §10.**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the N8a IBKR normalized-news worker runtime boundary from `scripts/collection/collect_ibkr_news_normalized.py` into `src/news_normalized/ibkr_cli.py`, and repoint the scheduler to `python -m src.news_normalized.ibkr_cli` without changing behavior or weakening sanitized-output guarantees.

**Architecture:** Keep IBKR subprocess isolation. Provider clients remain in `data_sources/`; domain runtime/orchestration moves to `src/news_normalized/`. The old `scripts/` file becomes a compatibility wrapper only, while app runtime and tests target the `src` module.

**Tech Stack:** Python 3, argparse, subprocess, pytest, SQLite, existing `src.news_normalized` writer/store modules, existing scheduler.

---

## Scope And Risk

This is a small refactor with a security invariant, not a data migration. It does not touch live DB schemas, profile markers, provider fetch semantics, or scheduler enablement. The load-bearing invariant is that the worker's stdout/stderr captured by the scheduler never exposes provider payloads, titles, URLs, article IDs, raw bodies, or provider error text.

This slice should not block normal PG-exit progress. It can run while scheduler/news freshness work continues because it changes only code wiring and hermetic tests.

## File Map

- Create: `src/news_normalized/ibkr_cli.py`
  - Owns CLI args, worker orchestration, provider config injection, Gateway/process lock discipline, market write lock, sanitized stdout JSON, sanitized error JSON, stderr/log suppression, and `main()`.
- Modify: `scripts/collection/collect_ibkr_news_normalized.py`
  - Becomes a thin compatibility wrapper that imports and calls `src.news_normalized.ibkr_cli.main`.
  - Retained temporarily for manual/backward compatibility; runtime must no longer call it.
- Modify: `src/service/data_scheduler.py`
  - Repoint normalized IBKR news subprocess from `scripts/collection/collect_ibkr_news_normalized.py` to `[sys.executable, "-m", "src.news_normalized.ibkr_cli", "--tickers", ",".join(scope), "--gateway-lock-held"]`.
  - Ensure subprocess package resolution remains repo-root based by relying on existing `cwd=str(_REPO_ROOT)` in `_run_sanitized_json_subprocess`.
- Modify: `tests/test_normalized_ibkr_worker.py`
  - Import `src.news_normalized.ibkr_cli` for worker tests.
  - Add a compatibility-wrapper test proving the old script delegates without duplicating logic.
  - Add a committed `python -m src.news_normalized.ibkr_cli` subprocess test that proves module
    startup emits clean JSON, not import-time noise.
- Modify: `tests/test_data_scheduler.py`
  - Update three scheduler assertions to require `-m src.news_normalized.ibkr_cli`.
  - Assert `scripts/collection/collect_ibkr_news_normalized.py` is no longer in runtime argv.

## Task 1: Move Worker Implementation Into `src`

**Files:**
- Create: `src/news_normalized/ibkr_cli.py`
- Modify: `tests/test_normalized_ibkr_worker.py`

- [ ] **Step 1: Write failing import-path tests**

Change the worker imports in `tests/test_normalized_ibkr_worker.py` from:

```python
from scripts.collection import collect_ibkr_news_normalized as worker
```

to:

```python
from src.news_normalized import ibkr_cli as worker
```

Apply that replacement in these tests:

```python
def test_ibkr_worker_requires_explicit_tickers():
    from src.news_normalized import ibkr_cli as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args([])

    assert caught.value.code == 2


def test_ibkr_worker_prints_sanitized_json_without_provider_payload(
    monkeypatch,
    capsys,
):
    from src.news_normalized import ibkr_cli as worker
    # Keep the existing test body unchanged after the import line.


def test_ibkr_worker_suppresses_provider_stderr_and_logging(monkeypatch, capsys):
    from src.news_normalized import ibkr_cli as worker
    # Keep the existing test body unchanged after the import line.


def test_ibkr_worker_standalone_acquires_gateway_lock_before_market_lock(
    monkeypatch,
):
    from src.news_normalized import ibkr_cli as worker
    # Keep the existing test body unchanged after the import line.
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py::test_ibkr_worker_requires_explicit_tickers -q
```

Expected: FAIL with `ImportError` because `src.news_normalized.ibkr_cli` does not exist.

- [ ] **Step 3: Create `src/news_normalized/ibkr_cli.py` by moving the worker body**

Create `src/news_normalized/ibkr_cli.py` with the full body currently in `scripts/collection/collect_ibkr_news_normalized.py`, except remove the `PROJECT_ROOT` / `sys.path.insert(...)` bootstrap block. The module must keep these public functions and constants:

```python
DEFAULT_MAX_ARTICLES = 50_000
DEFAULT_MAX_BODY_FETCHES = 50_000

def parse_args(argv: list[str] | None = None) -> argparse.Namespace: ...
def sanitize_worker_result(result: Any) -> dict[str, Any]: ...
def sanitize_worker_error(exc: BaseException) -> dict[str, Any]: ...
def main(argv: list[str] | None = None) -> int: ...
```

The `main()` implementation must continue to:

```python
try:
    with _suppress_provider_stderr_logging():
        _apply_provider_config()
        result = _run_worker(
            args.tickers,
            max_articles=args.max_articles,
            max_body_fetches=args.max_body_fetches,
            gateway_lock_held=args.gateway_lock_held,
        )
    payload = sanitize_worker_result(result)
    code = 0
except Exception as exc:
    payload = sanitize_worker_error(exc)
    code = 1
print(json.dumps(payload, sort_keys=True))
return code
```

- [ ] **Step 4: Run worker test file**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py -q
```

Expected: all tests in that file pass. This proves the moved module preserves the parse, sanitization, stderr suppression, lock ordering, and cleanup behavior.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/news_normalized/ibkr_cli.py tests/test_normalized_ibkr_worker.py
git commit -m "refactor: move IBKR news worker into src module"
```

## Task 2: Convert Legacy Script To Compatibility Wrapper

**Files:**
- Modify: `scripts/collection/collect_ibkr_news_normalized.py`
- Modify: `tests/test_normalized_ibkr_worker.py`

- [ ] **Step 1: Add failing wrapper delegation test**

Append this test to `tests/test_normalized_ibkr_worker.py`:

```python
def test_legacy_ibkr_worker_script_delegates_to_src_module(monkeypatch):
    import scripts.collection.collect_ibkr_news_normalized as legacy
    import src.news_normalized.ibkr_cli as worker

    calls = []

    def fake_main(argv=None):
        calls.append(argv)
        return 17

    monkeypatch.setattr(worker, "main", fake_main)

    assert legacy.main(["--tickers", "AAPL"]) == 17
    assert calls == [["--tickers", "AAPL"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py::test_legacy_ibkr_worker_script_delegates_to_src_module -q
```

Expected: FAIL because the current legacy script owns its own `main` implementation and does not delegate.

- [ ] **Step 3: Replace legacy script body with wrapper**

Replace `scripts/collection/collect_ibkr_news_normalized.py` with a call-time delegating wrapper:

```python
#!/usr/bin/env python3
"""Compatibility wrapper for the normalized IBKR news worker.

Runtime scheduler code must invoke ``python -m src.news_normalized.ibkr_cli``.
This file remains only for manual/backward compatibility during scripts retirement.
Retire it in N9, or earlier once grep confirms no manual/docs/tests path still
requires the old ``scripts/`` entrypoint.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.news_normalized import ibkr_cli  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return ibkr_cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run worker tests**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py -q
```

Expected: PASS. This proves the wrapper delegates and existing worker behavior is preserved through the new module.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/collection/collect_ibkr_news_normalized.py tests/test_normalized_ibkr_worker.py
git commit -m "refactor: keep legacy IBKR worker wrapper"
```

## Task 3: Repoint Scheduler To `python -m src...`

**Files:**
- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`

- [ ] **Step 1: Update scheduler tests to expect module invocation**

In `tests/test_data_scheduler.py`, update the first direct argv assertion from:

```python
assert argv[0] == ds.sys.executable
assert argv[1].endswith("collect_ibkr_news_normalized.py")
```

to:

```python
assert argv[:3] == [
    ds.sys.executable,
    "-m",
    "src.news_normalized.ibkr_cli",
]
assert not any(str(part).endswith("collect_ibkr_news_normalized.py") for part in argv)
```

Update the two rendered-call assertions from:

```python
assert "collect_ibkr_news_normalized.py" in rendered_calls
```

to:

```python
assert "src.news_normalized.ibkr_cli" in rendered_calls
assert "collect_ibkr_news_normalized.py" not in rendered_calls
```

- [ ] **Step 2: Run scheduler tests to verify they fail**

Run:

```bash
pytest tests/test_data_scheduler.py::test_ibkr_news_routes_to_normalized_worker_without_pg_sync tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_worker_without_pg_or_mirror tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_when_profile_store_unavailable -q
```

Expected: FAIL because scheduler still passes the script path.

- [ ] **Step 3: Change scheduler argv**

In `src/service/data_scheduler.py`, replace:

```python
argv = [
    sys.executable,
    str(_COLLECT_DIR / "collect_ibkr_news_normalized.py"),
    "--tickers",
    ",".join(scope),
    "--gateway-lock-held",
]
```

with:

```python
argv = [
    sys.executable,
    "-m",
    "src.news_normalized.ibkr_cli",
    "--tickers",
    ",".join(scope),
    "--gateway-lock-held",
]
```

Do not change `_run_sanitized_json_subprocess`; it already uses `cwd=str(_REPO_ROOT)`, which lets `python -m src.news_normalized.ibkr_cli` resolve the package from the repo root.

- [ ] **Step 4: Run scheduler tests**

Run:

```bash
pytest tests/test_data_scheduler.py::test_ibkr_news_routes_to_normalized_worker_without_pg_sync tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_worker_without_pg_or_mirror tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_when_profile_store_unavailable -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "refactor: run IBKR news worker as src module"
```

## Task 4: Add `python -m` Subprocess Purity Test

**Files:**
- Modify: `tests/test_normalized_ibkr_worker.py`

- [ ] **Step 1: Add failing subprocess test for module stdout purity**

Add this test to `tests/test_normalized_ibkr_worker.py`:

```python
def test_ibkr_worker_module_subprocess_stdout_is_single_json_object(tmp_path):
    import os
    import sqlite3
    import subprocess
    import sys
    from pathlib import Path

    market_db = tmp_path / "market_data.db"
    sqlite3.connect(market_db).close()

    env = os.environ.copy()
    env["ARKSCOPE_MARKET_DB"] = str(market_db)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.news_normalized.ibkr_cli",
            "--tickers",
            "FAKE",
            "--max-articles",
            "0",
            "--max-body-fetches",
            "0",
            "--gateway-lock-held",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert proc.stdout.strip() == json.dumps(payload, sort_keys=True)
    assert payload["status"] == "partial"
    assert payload["articles_seen"] == 0
    assert payload["error_count"] == 0
    assert "FAKE" not in proc.stderr
```

This intentionally uses a temp `ARKSCOPE_MARKET_DB`. It must not touch live `data/market_data.db`
and must not require a live IBKR Gateway. `--max-articles 0` exercises module startup and sanitized
JSON output while preventing provider fetches.

- [ ] **Step 2: Run test to verify it fails before Task 3**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py::test_ibkr_worker_module_subprocess_stdout_is_single_json_object -q
```

Expected before Task 3/module creation: FAIL with `No module named src.news_normalized.ibkr_cli`.
Expected after Task 3/module creation: PASS. If it fails because the subprocess touches live IBKR
or live DB, fix the module/test so the zero-budget path remains hermetic.

- [ ] **Step 3: Run module help from repo root**

Run:

```bash
python -m src.news_normalized.ibkr_cli --help
```

Expected: exits 0 and prints argparse help containing `Write IBKR news directly to normalized SQLite tables.`

- [ ] **Step 4: Run module parse failure and confirm argparse-only failure**

Run:

```bash
python -m src.news_normalized.ibkr_cli
```

Expected: exits non-zero with argparse usage. This command occurs before provider work, so no provider payload can be emitted.

- [ ] **Step 5: Run targeted tests**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py::test_ibkr_news_routes_to_normalized_worker_without_pg_sync tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_worker_without_pg_or_mirror tests/test_data_scheduler.py::test_post_exit_ibkr_audit_routes_to_normalized_when_profile_store_unavailable -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add tests/test_normalized_ibkr_worker.py
git commit -m "test: pin IBKR worker module stdout contract"
```

## Task 5: Verify Subprocess Resolution And Sanitized Contract End-To-End

**Files:**
- Test only; no code change expected unless a failure reveals a real issue.

- [ ] **Step 1: Run broader scheduler/news-normalized tests**

Run:

```bash
pytest tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py -q
```

Expected: PASS, except live-IBKR tests may be skipped if they require Gateway. There must be no failures.

- [ ] **Step 2: Run the offline suite subset that commonly imports scheduler/backend code**

Run:

```bash
pytest tests/test_data_scheduler.py tests/test_normalized_ibkr_worker.py tests/test_news_normalized_ibkr_adapter.py tests/test_news_pg_unreachable.py tests/test_provider_health.py tests/test_sqlite_backend.py -q
```

Expected: PASS, except explicit live-IBKR tests may be skipped. There must be no failures.

- [ ] **Step 3: Commit only if verification caused code/test changes**

If Steps 1-2 required a fix, commit only the actual files changed by that fix. For example, if
`src/news_normalized/ibkr_cli.py` needed a package-resolution fix, run:

```bash
git add src/news_normalized/ibkr_cli.py
git commit -m "fix: preserve IBKR worker module contract"
```

If verification required no changes, do not create an empty commit.

## Task 6: Documentation Touch-Up

**Files:**
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`

- [ ] **Step 1: Update S-A1 status line**

In `docs/design/PG_EXIT_REMAINDER_SCOPING.md`, update the S-A1 recommendation to say the demonstrator is implemented once Tasks 1-4 are complete. Keep this factual and short, for example:

```markdown
Status: S-A1 implemented in code; runtime now invokes `python -m src.news_normalized.ibkr_cli`.
```

- [ ] **Step 2: Run placeholder scan**

Run:

```bash
rg -n "TBD|TODO|FIXME|thin shell|one-line|src/providers" docs/design/PG_EXIT_REMAINDER_SCOPING.md
```

Expected: no matches for `TBD|TODO|FIXME|thin shell|one-line`. A match for `src/providers` is acceptable only if it is the sentence warning not to create that layer.

- [ ] **Step 3: Commit docs**

Run:

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md
git commit -m "docs: mark S-A1 scripts demonstrator complete"
```

## Final Verification

- [ ] **Step 1: Check staged/uncommitted scope**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated changes remain, especially `config/tickers_core.json` and `trained_models/*`. There should be no unstaged S-A1 files.

- [ ] **Step 2: Confirm runtime no longer references the script worker path**

Run:

```bash
rg -n "collect_ibkr_news_normalized.py" src tests docs/design/PG_EXIT_REMAINDER_SCOPING.md
```

Expected: no `src/service/data_scheduler.py` runtime invocation. Matches are acceptable only in the legacy wrapper, historical docs/plans, or compatibility tests.

- [ ] **Step 3: Report outcome**

Report:

- commits created,
- tests run and results,
- whether any live DB or provider call was made,
- remaining recommended next slice (`S-B fundamentals refetch/cache`).
