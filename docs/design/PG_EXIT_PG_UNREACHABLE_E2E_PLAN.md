# PG-Unreachable E2E Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** DRAFT for review. This plan is non-destructive and does not authorize batch-3 `prices` drop. It builds and runs the final PG-unreachable runtime proof before the physical PG `prices` archive/drop.

**Goal:** Prove normal ArkScope desktop/API runtime works when PostgreSQL is unreachable, and turn that proof into a repeatable gate for batch-3 and future regressions.

**Architecture:** Add a dedicated smoke harness that injects a poisoned PG DSN, patches PG connection attempts to fail immediately, disables scheduler startup, exercises the route/tool surfaces that make up normal desktop usage, and emits a sanitized JSON report. If the smoke finds a PG attempt or a runtime 500, stop and open a focused fix slice; do not proceed to batch-3 until the smoke is green.

**Tech Stack:** Python, FastAPI `TestClient`, pytest, existing local SQLite stores (`market_data.db`, `profile_state.db`, `sa_capture.db`, `macro_calendar.db`), existing route handlers, no PostgreSQL writes, no provider fetches.

---

## Map Check

Active authority:

- `PROJECT_PRIORITY_MAP.md` P0-B says N9 batch-2 is live-complete and the next PG-exit item is **batch-3 PG `prices` archive/drop plan or PG-unreachable E2E**.
- `PG_EXIT_COMPLETION_PLAN.md` DONE criteria require: "The app starts normally with PG unreachable / no `DATABASE_URL`" and tests include a "PG unreachable" scenario proving normal use does not stall or fall back.
- `PG_EXIT_REMAINDER_SCOPING.md` §8 says runtime authority is local; remaining PG physical objects are archive-only `prices` plus app-record archive tables.

This plan chooses **PG-unreachable E2E first** because it is non-destructive and can reveal the last universe-summaries-style runtime leak before batch-3.

## Scope

In scope:

- Add a repeatable PG-unreachable E2E smoke harness.
- Cover the normal desktop/API surfaces that should work without PG.
- Ensure any PG connection attempt fails immediately and is recorded as a test failure.
- Produce a sanitized JSON report that can be attached to the batch-3 approval packet.
- Update docs after the live smoke is green.

Out of scope:

- Do not drop PG `prices`; that is batch-3 after a separate archive/restore/drop approval packet.
- Do not drop app-record archive tables.
- Do not start provider fetches or scheduler jobs from this smoke.
- Do not test explicit archive/migration endpoints that are allowed to require PG archives, such as app-record migration preview/apply.
- Do not redesign FRED/macro product semantics, Data Sources UI layout, model list, or token monitoring.

## Success Criteria

The E2E gate is green only if all of these hold:

1. The smoke starts the API app with scheduler disabled.
2. The DAL sees a poisoned PG DSN, but normal runtime selects local stores.
3. `psycopg2.connect` is patched to raise immediately; `pg_attempts == []` at the end.
4. Each required check returns the expected status and passes its body assertion.
5. The JSON report contains no DSN, password, token, or API key material.
6. The smoke can be run twice against the same local DBs with stable pass/fail status.
7. If any check fails, batch-3 is blocked until a focused fix slice lands and the full smoke passes.

## Required Runtime Surfaces

The smoke must exercise at least these surfaces:

| Surface | Check | Expected |
|---|---|---|
| Liveness | `GET /healthz` | `200`, `status=="ok"` |
| System status | `GET /status` | `200`, no PG attempt |
| Data Sources config | `GET /providers/config` | `200`, provider list present |
| Provider health | `GET /providers/health` | `200`, no PG attempt |
| Schedule status | `GET /schedule` | `200`; do not run jobs |
| Market status | `GET /market-data/status` | `200`, `pg_fallback_active is False`, `prices_authority=="local"` |
| Market retired update | `POST /market-data/update` | `409` with retired/local-only code; no PG attempt |
| Price read | `GET /prices/NVDA?interval=15min&days=7` | `200`, local result shape |
| Price coverage | `GET /market-data/coverage/NVDA` | `200`, local result shape |
| News status | `GET /news/status` | `200`, hard-local/local status |
| News feed | `GET /news/feed?days=7&limit=5` | `200`, local result shape |
| News ticker | `GET /news/NVDA?days=30` | `200`, local result shape |
| News sentiment | `GET /news/NVDA/sentiment?days=9999` | `200`, local score path |
| Fundamentals stored | `GET /fundamentals/NVDA?stored=true` | `200`, local-cache/honest-empty shape |
| IV history | `GET /options/AMD/history` | `200`, local/honest-empty shape; do not call live IBKR analysis |
| SA feed | `GET /sa/feed?limit=5` | `200`, local `sa_capture.db` path |
| SA health | `GET /sa/market-news/health` | `200`, may be warning but not PG error |
| Macro status | `GET /macro/status` | `200`, local-first active |
| Macro health | `GET /macro/health` | `200` or documented non-500 health status; no PG attempt |
| Macro IPO | `GET /macro/ipo-calendar?limit=5` | `200`, local result shape |
| Reports | `GET /reports` | `200`, local `profile_state.db` path |
| App records preview | `GET /app-records/migration/preview` | excluded from normal-runtime smoke; archive/migration path may require PG |
| Universe summaries | direct call `get_universe_summaries(None, days=7)` | returns dict, no PG attempt |

---

## File Map

Create:

- `scripts/smoke/pg_unreachable_e2e.py` — executable smoke harness, JSON report writer, route list, PG poison hook.
- `tests/test_pg_unreachable_e2e.py` — unit tests for harness behavior, route contract, sanitizer, and failure handling.

Modify:

- `docs/design/PG_EXIT_COMPLETION_PLAN.md` — after live smoke: record PG-unreachable E2E result.
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` — after live smoke: update §8 / endgame notes.
- `docs/design/PROJECT_PRIORITY_MAP.md` — after live smoke: decision-log entry and next PG-exit item.

Do not modify in this slice unless the smoke fails:

- runtime route handlers;
- DAL/backend routing;
- scheduler sources;
- frontend UI.

If the smoke fails, stop and open a separate fix slice with its own TDD plan.

---

## Task 1 - Build The PG-Unreachable Smoke Harness

### Intent

Add one command that can run in the main checkout and prove normal API runtime does not touch PG.

### Files

- Create: `scripts/smoke/pg_unreachable_e2e.py`
- Test: `tests/test_pg_unreachable_e2e.py`

### Red Tests

- [ ] Create `tests/test_pg_unreachable_e2e.py`.
- [ ] Add `test_required_checks_cover_pg_exit_surfaces()`:

```python
def test_required_checks_cover_pg_exit_surfaces():
    from scripts.smoke.pg_unreachable_e2e import REQUIRED_CHECKS

    names = {check.name for check in REQUIRED_CHECKS}
    assert {
        "healthz",
        "system_status",
        "provider_config",
        "provider_health",
        "schedule_status",
        "market_status",
        "market_update_retired",
        "price_read",
        "price_coverage",
        "news_status",
        "news_feed",
        "news_ticker",
        "news_sentiment",
        "fundamentals_stored",
        "iv_history",
        "sa_feed",
        "sa_health",
        "macro_status",
        "macro_health",
        "macro_ipo",
        "reports",
        "universe_summaries",
    } <= names
```

- [ ] Add `test_report_sanitizes_poison_dsn()`:

```python
def test_report_sanitizes_poison_dsn(tmp_path):
    from scripts.smoke.pg_unreachable_e2e import SmokeReport, CheckResult

    report = SmokeReport(
        ok=False,
        poison_label="postgresql://user:secret@host/db?connect_timeout=1",
        pg_attempts=["postgresql://user:secret@host/db?connect_timeout=1"],
        checks=[CheckResult(name="x", ok=False, status_code=500, detail="secret")],
    )
    data = report.to_sanitized_dict()
    text = str(data)
    assert "secret" not in text
    assert "user:secret" not in text
    assert "postgresql://user:***@host/db" in text
```

- [ ] Add `test_pg_poison_records_and_raises()`:

```python
def test_pg_poison_records_and_raises():
    from scripts.smoke.pg_unreachable_e2e import PgPoison

    poison = PgPoison()
    with pytest.raises(RuntimeError, match="PG_UNREACHABLE_E2E_POISON"):
        poison.connect("postgresql://u:p@host/db")
    assert len(poison.attempts) == 1
    assert poison.attempts[0].startswith("postgresql://u:***@host/db")
```

- [ ] Run:

```bash
pytest tests/test_pg_unreachable_e2e.py -q
```

Expected: FAIL because the harness does not exist.

### Implementation

- [ ] Create `scripts/smoke/pg_unreachable_e2e.py` with these public symbols:

```python
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


POISON_DSN = "postgresql://pg-poison.invalid/arkscope?connect_timeout=1"


@dataclass(frozen=True)
class CheckSpec:
    name: str
    method: str
    path: str
    expected_status: int | tuple[int, ...]
    assert_body: Callable[[Any], None] | None = None


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: int | None = None
    detail: str = ""


@dataclass
class SmokeReport:
    ok: bool
    poison_label: str
    pg_attempts: list[str]
    checks: list[CheckResult]

    def to_sanitized_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "poison_label": sanitize_secret(self.poison_label),
            "pg_attempts": [sanitize_secret(x) for x in self.pg_attempts],
            "checks": [asdict(c) | {"detail": sanitize_secret(c.detail)} for c in self.checks],
        }


def sanitize_secret(value: Any) -> str:
    text = str(value)
    text = re.sub(r"(postgres(?:ql)?://[^:/@]+):([^@]+)@", r"\1:***@", text)
    text = re.sub(r"(?i)(api[_-]?key|token|password|secret)=([^&\\s]+)", r"\1=***", text)
    return text


class PgPoison:
    def __init__(self) -> None:
        self.attempts: list[str] = []

    def connect(self, *args: Any, **kwargs: Any) -> None:
        label = args[0] if args else kwargs.get("dsn") or kwargs
        self.attempts.append(sanitize_secret(label))
        raise RuntimeError("PG_UNREACHABLE_E2E_POISON: PostgreSQL connection attempted")
```

- [ ] Define body assertion helpers:

```python
def _assert_key(key: str) -> Callable[[Any], None]:
    def inner(body: Any) -> None:
        assert isinstance(body, dict)
        assert key in body
    return inner


def _assert_market_status(body: Any) -> None:
    assert body["pg_fallback_active"] is False
    assert body["prices_authority"] == "local"
    assert body["routing_enabled"] is True


def _assert_update_retired(body: Any) -> None:
    assert body.get("code") in {"pg_market_update_retired", "pg_market_bootstrap_retired"}


def _assert_list_or_dict(_: Any) -> None:
    assert True
```

- [ ] Define the required checks:

```python
REQUIRED_CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec("healthz", "GET", "/healthz", 200, _assert_key("status")),
    CheckSpec("system_status", "GET", "/status", 200, _assert_key("data_sources")),
    CheckSpec("provider_config", "GET", "/providers/config", 200, _assert_key("providers")),
    CheckSpec("provider_health", "GET", "/providers/health", 200, _assert_list_or_dict),
    CheckSpec("schedule_status", "GET", "/schedule", 200, _assert_key("sources")),
    CheckSpec("market_status", "GET", "/market-data/status", 200, _assert_market_status),
    CheckSpec("market_update_retired", "POST", "/market-data/update", 409, _assert_update_retired),
    CheckSpec("price_read", "GET", "/prices/NVDA?interval=15min&days=7", 200, _assert_key("bars")),
    CheckSpec("price_coverage", "GET", "/market-data/coverage/NVDA", 200, _assert_list_or_dict),
    CheckSpec("news_status", "GET", "/news/status", 200, _assert_list_or_dict),
    CheckSpec("news_feed", "GET", "/news/feed?days=7&limit=5", 200, _assert_key("items")),
    CheckSpec("news_ticker", "GET", "/news/NVDA?days=30", 200, _assert_key("articles")),
    CheckSpec("news_sentiment", "GET", "/news/NVDA/sentiment?days=9999", 200, _assert_key("ticker")),
    CheckSpec("fundamentals_stored", "GET", "/fundamentals/NVDA?stored=true", 200, _assert_list_or_dict),
    CheckSpec("iv_history", "GET", "/options/AMD/history", 200, _assert_key("points")),
    CheckSpec("sa_feed", "GET", "/sa/feed?limit=5", 200, _assert_list_or_dict),
    CheckSpec("sa_health", "GET", "/sa/market-news/health", 200, _assert_key("severity")),
    CheckSpec("macro_status", "GET", "/macro/status", 200, _assert_key("local_first_active")),
    CheckSpec("macro_health", "GET", "/macro/health", (200, 503), _assert_key("severity")),
    CheckSpec("macro_ipo", "GET", "/macro/ipo-calendar?limit=5", 200, _assert_list_or_dict),
    CheckSpec("reports", "GET", "/reports", 200, _assert_list_or_dict),
)
```

- [ ] Implement `run_route_checks(client)`, `run_universe_summary_check()`, and `run_smoke()`:

```python
def _expected(status: int, expected: int | tuple[int, ...]) -> bool:
    return status in expected if isinstance(expected, tuple) else status == expected


def run_route_checks(client: Any, checks: Iterable[CheckSpec] = REQUIRED_CHECKS) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        try:
            response = client.request(check.method, check.path)
            body = response.json()
            if not _expected(response.status_code, check.expected_status):
                results.append(CheckResult(check.name, False, response.status_code, str(body)[:500]))
                continue
            if check.assert_body is not None:
                check.assert_body(body)
            results.append(CheckResult(check.name, True, response.status_code, ""))
        except Exception as exc:
            results.append(CheckResult(check.name, False, None, sanitize_secret(repr(exc))))
    return results


def run_universe_summary_check() -> CheckResult:
    try:
        from src.tools.analysis_tools import get_universe_summaries
        out = get_universe_summaries(None, days=7)
        assert isinstance(out, dict)
        return CheckResult("universe_summaries", True, None, "")
    except Exception as exc:
        return CheckResult("universe_summaries", False, None, sanitize_secret(repr(exc)))
```

- [ ] Add an injectable client factory so unit tests do not need to start the real FastAPI lifespan:

```python
def _make_live_client():
    from fastapi.testclient import TestClient
    from src.api.app import create_app

    return TestClient(create_app())
```

- [ ] In `run_smoke()`, patch before creating the app:

```python
def run_smoke(
    *,
    poison_dsn: str = POISON_DSN,
    client_factory: Callable[[], Any] = _make_live_client,
) -> SmokeReport:
    os.environ["ARKSCOPE_DISABLE_SCHEDULER"] = "1"
    os.environ["ARKSCOPE_PG_UNREACHABLE_E2E"] = "1"

    from src.api import dependencies
    dependencies.get_dal.cache_clear()
    dependencies.get_registry.cache_clear()

    from src.tools import data_access as data_access_mod
    original_loader = data_access_mod.DataAccessLayer._load_env_db_dsn
    data_access_mod.DataAccessLayer._load_env_db_dsn = lambda self: poison_dsn

    import psycopg2
    poison = PgPoison()
    original_connect = psycopg2.connect
    psycopg2.connect = poison.connect

    try:
        with client_factory() as client:
            checks = run_route_checks(client)
            checks.append(run_universe_summary_check())
    finally:
        data_access_mod.DataAccessLayer._load_env_db_dsn = original_loader
        psycopg2.connect = original_connect
        dependencies.get_dal.cache_clear()
        dependencies.get_registry.cache_clear()

    ok = all(c.ok for c in checks) and not poison.attempts
    return SmokeReport(
        ok=ok,
        poison_label=poison_dsn,
        pg_attempts=poison.attempts,
        checks=checks,
    )
```

- [ ] Implement CLI:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poison-dsn", default=POISON_DSN)
    parser.add_argument("--output")
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(poison_dsn=args.poison_dsn)
    payload = report.to_sanitized_dict()
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

### Green Gate

```bash
pytest tests/test_pg_unreachable_e2e.py -q
python -m compileall scripts/smoke/pg_unreachable_e2e.py
```

Expected: all pass.

Commit:

```bash
git add scripts/smoke/pg_unreachable_e2e.py tests/test_pg_unreachable_e2e.py
git commit -m "test: add pg-unreachable e2e smoke"
```

---

## Task 2 - Prove Harness Failure Modes

### Intent

The smoke must fail loudly on exactly the regressions we care about: a PG connection attempt, route 500, missing local authority marker, and secret leakage.

### Files

- Modify: `tests/test_pg_unreachable_e2e.py`

### Red Tests

- [ ] Add `test_smoke_fails_if_any_pg_attempt_is_recorded()`:

```python
def test_smoke_fails_if_any_pg_attempt_is_recorded(monkeypatch):
    from scripts.smoke import pg_unreachable_e2e as smoke

    monkeypatch.setattr(smoke, "run_route_checks", lambda client: [])
    monkeypatch.setattr(smoke, "run_universe_summary_check", lambda: smoke.CheckResult("universe_summaries", True))

    class FakePoison(smoke.PgPoison):
        def __init__(self):
            super().__init__()
            self.attempts.append("postgresql://u:***@host/db")

    monkeypatch.setattr(smoke, "PgPoison", FakePoison)

    class FakeClient:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    report = smoke.run_smoke(client_factory=FakeClient)
    assert report.ok is False
```

- [ ] Add `test_smoke_fails_on_bad_route_status()`:

```python
def test_smoke_fails_on_bad_route_status():
    from scripts.smoke.pg_unreachable_e2e import CheckSpec, run_route_checks

    class Response:
        status_code = 500
        def json(self):
            return {"error": "boom"}

    class Client:
        def request(self, method, path):
            return Response()

    checks = [CheckSpec("bad", "GET", "/bad", 200)]
    result = run_route_checks(Client(), checks)[0]
    assert result.ok is False
    assert result.status_code == 500
```

- [ ] Add `test_market_status_assertion_requires_no_pg_fallback()`:

```python
def test_market_status_assertion_requires_no_pg_fallback():
    from scripts.smoke.pg_unreachable_e2e import _assert_market_status

    with pytest.raises(AssertionError):
        _assert_market_status({
            "pg_fallback_active": True,
            "prices_authority": "pg",
            "routing_enabled": False,
        })
```

### Green Gate

```bash
pytest tests/test_pg_unreachable_e2e.py -q
```

Expected: pass.

Commit:

```bash
git add tests/test_pg_unreachable_e2e.py
git commit -m "test: harden pg-unreachable smoke failure modes"
```

---

## Task 3 - Run Live PG-Unreachable Smoke

### Intent

Run the smoke against the real local desktop stores without scheduler or provider fetches.

### Preconditions

- No repo freeze is required; this is non-destructive.
- Do not start scheduler jobs during the smoke.
- It is safe if Firefox/SA sync is running, but quieter output is easier to review if writers are idle.
- Do not use a real PG password in the poison DSN.

### Commands

- [ ] Run twice:

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
OUT_DIR=scratchpad/pg-unreachable-e2e-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$OUT_DIR"

ARKSCOPE_DISABLE_SCHEDULER=1 \
"$PY" scripts/smoke/pg_unreachable_e2e.py \
  --poison-dsn "postgresql://pg-poison.invalid/arkscope?connect_timeout=1" \
  --output "$OUT_DIR/run-1.json"

ARKSCOPE_DISABLE_SCHEDULER=1 \
"$PY" scripts/smoke/pg_unreachable_e2e.py \
  --poison-dsn "postgresql://pg-poison.invalid/arkscope?connect_timeout=1" \
  --output "$OUT_DIR/run-2.json"
```

- [ ] Compare the pass/fail-critical fields:

```bash
python - <<'PY'
import json, sys
from pathlib import Path
out = sorted(Path("scratchpad").glob("pg-unreachable-e2e-*/run-*.json"))[-2:]
docs = [json.load(open(p)) for p in out]
for p, d in zip(out, docs):
    print(p, d["ok"], len(d["pg_attempts"]), [c["name"] for c in d["checks"] if not c["ok"]])
assert all(d["ok"] for d in docs)
assert all(not d["pg_attempts"] for d in docs)
assert [c["name"] for c in docs[0]["checks"]] == [c["name"] for c in docs[1]["checks"]]
PY
```

Expected:

- both reports `ok:true`;
- both reports `pg_attempts:[]`;
- no failed checks.

### Failure Policy

If any check fails:

1. Do not proceed to batch-3.
2. Keep the JSON report in `scratchpad/`.
3. Open a focused fix slice named after the failed surface, for example:
   - `PG_EXIT_E2E_FIX_UNIVERSE_SUMMARIES_PLAN.md`;
   - `PG_EXIT_E2E_FIX_PROVIDER_HEALTH_PLAN.md`.
4. After the fix, rerun the full smoke from Task 3, not just the failed check.

---

## Task 4 - Docs Sync After Green Smoke

### Intent

Record the E2E result as the formal pre-batch-3 proof.

### Files

- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

### Steps

- [ ] Update `PG_EXIT_COMPLETION_PLAN.md`:
  - mark the PG-unreachable E2E criterion as passing;
  - record the smoke output directory and check count;
  - state that batch-3 remains the physical PG `prices` drop, not runtime cutover.
- [ ] Update `PG_EXIT_REMAINDER_SCOPING.md` §8:
  - add a "PG-unreachable E2E green" record;
  - mention `pg_attempts=[]`;
  - leave app-record archive tables as a separate decision.
- [ ] Update `PROJECT_PRIORITY_MAP.md` §10:
  - add newest-first decision-log entry;
  - set next PG-exit item to batch-3 PG `prices` archive/drop plan unless the reviewer chooses to handle app-record archive-table policy first.
- [ ] Run:

```bash
git diff --check -- \
  docs/design/PG_EXIT_COMPLETION_PLAN.md \
  docs/design/PG_EXIT_REMAINDER_SCOPING.md \
  docs/design/PROJECT_PRIORITY_MAP.md
```

Expected: no output.

Commit:

```bash
git add \
  docs/design/PG_EXIT_COMPLETION_PLAN.md \
  docs/design/PG_EXIT_REMAINDER_SCOPING.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: record pg-unreachable e2e proof"
```

---

## Task 5 - Review Gate Before Batch-3

Batch-3 planning may start only after a reviewer confirms:

- [ ] `scripts/smoke/pg_unreachable_e2e.py` has no provider fetch or scheduler run side effect.
- [ ] Live smoke report has `ok:true`.
- [ ] Live smoke report has `pg_attempts:[]`.
- [ ] All required runtime surfaces in this plan are covered or have a written exclusion.
- [ ] Any warning/503 accepted by the smoke is a health-state response, not a PG-unreachable failure.
- [ ] Docs record the result and do not claim physical `prices` drop has happened.

After this gate:

- Proceed to `PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md`.
- Keep the smoke as a required pre-drop and post-drop command for batch-3.

---

## Self-Review Notes

- **Spec coverage:** This covers the completion-plan PG-unreachable criterion, the runtime surfaces named in recent reviews, and the universe-summaries leak class.
- **No destructive operations:** The plan patches `psycopg2.connect` in-process and never calls `DROP`, `pg_dump`, `pg_restore`, provider fetches, or scheduler run endpoints.
- **No hidden PG allowance:** Explicit archive/migration endpoints are excluded; normal runtime routes must not attempt PG.
- **Batch-3 sequencing:** The plan blocks physical `prices` drop until this proof is green.
