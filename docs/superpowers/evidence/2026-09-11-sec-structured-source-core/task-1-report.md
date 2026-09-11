# Task 1 Report

Status: Task 1 evidence implementation complete; ready for parent review.
Diagnostic outcome: **defect_reproduced, exit 1**, not an all-pass engine result.
Parent supplied the date-control results below; independent review, staging and
any later commit remain parent-owned.
No subagents were used. No files were staged or committed by this worker.

## Files Written

Only these four authorized paths in the existing isolated worktree were written:

- `docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py`
- `docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite-upsert-result.json`
- `docs/superpowers/evidence/2026-09-11-sec-structured-source-core/review-followups.md`
- `.superpowers/sdd/2026-09-11-sec-structured-source-core/task-1-report.md`

All manual file contents were written with `apply_patch`. The JSON was populated
from captured actual stdout, then compared byte-for-byte to a fresh probe run.
No sealed old evidence was rewritten. The scratch report is ignored by Git;
parent decides how to retain its regression command during review.

## Commands And Results

All Python commands used `env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B`,
with `login=false` and working directory
`/tmp/arkscope-listing-sec-macro-convergence`. This worker ran no App imports or
date tests.

Exact diagnostic command:

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B /tmp/arkscope-listing-sec-macro-convergence/docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py
```

Result: exit 1. All three duplicate-clause cases had table/index counts 2/3,
full integrity error `wrong # of entries in index sqlite_autoindex_v0_1`, and
quick check `ok`. Both single-clause controls had 2/2 and both checks `ok`.
Every journal mode was `memory`; actual table rows were `[[0,11],[11,22]]`.
Python 3.10.12, SQLite 3.37.2, source ID
`2022-01-06 13:25:41 872ba256cbf61d9290b571c0e6d82a20c224ca3ad82971edc46b29818d5dalt1`.

Fresh-output/archive verification command:

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B -c 'import json, pathlib, subprocess; p = pathlib.Path("docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite-upsert-result.json"); archived = p.read_text(); result = subprocess.run(["/usr/bin/python3", "-I", "-S", "-B", str(p.with_name("sqlite_upsert_repro.py").resolve())], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, check=False); assert result.stdout == archived; report = json.loads(archived); assert result.returncode == report["exit_code"] == 1; assert result.stderr == ""; print("PASS: fresh stdout exactly matches archive; process/report exit 1; stderr empty")'
```

Result: exit 0, `PASS: fresh stdout exactly matches archive; process/report exit 1; stderr empty`.

The preserved regression command below first ran RED before implementation:
six tests failed because the diagnostic/classifier/probe did not exist (61
assertion failures including subtests). After implementation, all six passed.
An added connection-audit assertion initially failed because this interpreter's
`sqlite3.connect` audit event supplied `b':memory:'`, not a string. A separate
clean memory probe confirmed the byte-valued event; only the test's target
normalization changed. Final regression result: **6 tests passed, exit 0**,
including five observed memory connection targets, invalid SQL handling,
control-failure precedence, behavioral version independence, and rejected CLI
database arguments. No skip or runtime upgrade was used to obtain this result.

Parent-supplied Task 2/date-control results, not executed or independently
verified by this worker:

- Initial absence RED: 2 failed / 280 passed, including three unchanged
  date/transition/review files.
- Final combined focus: **447 passed in 32.38 seconds**; parent reports XML at
  `scratch/task2-green.xml`.
- Inverse check: 2 failed / 1 passed; parent reports restoration and a rerun in
  progress. No final inverse-rerun result is claimed here.

Read-only preservation/ownership checks:

- `git rev-parse --show-toplevel --git-dir --git-common-dir --show-superproject-working-tree --abbrev-ref HEAD`
  confirmed the existing linked worktree on `codex/listing-sec-macro-convergence`,
  not a submodule. HEAD observed during follow-up was
  `96990ef51d12cabf6ca7661a4d77f3cd220683fe`.
- `git ls-tree -r --name-only 30bb31c7 -- src/audit` returned four files:
  `__init__.py`, `ibkr_news_catchup_audit.py`, `sa_article_reconciliation.py`,
  and `universe_retirement.py`. Isolated `src/audit` lookup found no directory.
  Main presence is parent-verified context; no main deletion was performed.
- `sha256sum docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/current-journal-cleanup/sqlite-research.md`
  matched before and after:
  `170fd68b2dfe84b8fde89dd76fb763c2810c0ee465b218f50e25b058a03f109c`.
- `git diff --exit-code -- docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit`
  exited 0 with empty output.
- `git status --short --untracked-files=all` showed the three new evidence files
  plus concurrent parent-owned source/test changes, which were not touched.

## Concerns And Parent Gates

- Independent review is pending, not claimed complete by this worker. Verify
  exact archived SQL, separate memory targets, 2-before-1 failure precedence,
  version-independent classification and reproduction instructions.
- Date-control verification is recorded above solely as parent-supplied evidence;
  the inverse rerun remains pending in the last parent update. The September 8
  plan, lines 91-97, already states limitation versus unresolved-condition
  handling and explicit attended execution-date policy. No lifecycle changes
  are needed or made here to "close" that policy.
- The observed engine reproduced the defect. This is not proof that the running
  App uses this interpreter or that any user's database is corrupt. No production
  DB/config/token access, filesystem-backed SQLite, App import, network/provider
  call, installation, upgrade, repair, restart, merge or push occurred.
- Audit cleanup, actual-store disposition, all other tasks, and future SQLite
  runtime decisions remain outside this worker's scope. Main's four tracked old
  audit files and the sealed archive must remain preserved.

## Preserved Diagnostic Regression Tests

These tests catch version-based decisions, false success on failed/missing
controls, defect precedence over an inconclusive probe, SQL drift, and CLI
status/report disagreement. Only the real five-case matrix and a deliberate
invalid-SQL probe open SQLite, always through the diagnostic's memory target.
Synthetic classifier inputs do not open any database.

Run from `/tmp/arkscope-listing-sec-macro-convergence` with `login=false`:

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B -c 'from pathlib import Path; p = Path(".superpowers/sdd/2026-09-11-sec-structured-source-core/task-1-report.md"); source = p.read_text().split("```python\n", 1)[1].split("\n```", 1)[0]; exec(compile(source, str(p), "exec"))'
```

```python
import copy
import json
from pathlib import Path
import runpy
import subprocess
import sys
import unittest

SCRIPT = Path("docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py").resolve()
namespace = runpy.run_path(str(SCRIPT)) if SCRIPT.exists() else {}
NAMES = (
    "upstream_replace_duplicate",
    "insert_schema_replace_duplicate",
    "insert_or_replace_duplicate",
    "replace_single_clause",
    "insert_single_clause",
)
CONNECTION_TARGETS = []

def audit_connections(event, args):
    if event == "sqlite3.connect":
        target = args[0].decode("ascii") if isinstance(args[0], bytes) else args[0]
        if target != ":memory:":
            raise AssertionError("non-memory SQLite target rejected")
        CONNECTION_TARGETS.append(target)

sys.addaudithook(audit_connections)

def passing(name):
    return {
        "name": name, "error": None, "sqlite_version": "arbitrary-version",
        "sqlite_source_id": "arbitrary-source", "journal_mode": "memory",
        "table_count": 2, "indexed_count": 2,
        "table_rows": [[0, 11], [11, 22]],
        "integrity_check": ["ok"], "quick_check": ["ok"],
    }

def defect(name):
    result = passing(name)
    result.update(indexed_count=3, integrity_check=[
        "wrong # of entries in index sqlite_autoindex_v0_1"
    ])
    return result

class DiagnosticTests(unittest.TestCase):
    def classifier(self):
        function = namespace.get("classify_results")
        self.assertTrue(callable(function), "classify_results is not implemented")
        return function

    def test_all_pass_does_not_depend_on_version(self):
        results = [passing(name) for name in NAMES]
        self.assertEqual(self.classifier()(results), ("all_pass", 0))
        for result in results:
            result["sqlite_version"] = "3.37.2"
        self.assertEqual(self.classifier()(results), ("all_pass", 0))

    def test_exact_defect_with_valid_controls(self):
        for position in range(3):
            results = [passing(name) for name in NAMES]
            results[position] = defect(NAMES[position])
            results[position]["sqlite_version"] = "99.99.99"
            self.assertEqual(self.classifier()(results), ("defect_reproduced", 1))

    def test_inconclusive_takes_precedence_over_defect(self):
        changes = (
            {"error": {"type": "OperationalError", "message": "probe failed"}},
            {"journal_mode": "wal"},
            {"table_count": 0},
            {"indexed_count": 4},
            {"table_rows": []},
            {"integrity_check": []},
            {"integrity_check": ["unexpected corruption"]},
            {"quick_check": []},
            {"quick_check": ["unexpected corruption"]},
            {"sqlite_version": None},
            {"sqlite_source_id": None},
        )
        for position in range(5):
            for change in changes:
                with self.subTest(position=position, change=change):
                    results = [defect(name) if i < 3 else passing(name)
                               for i, name in enumerate(NAMES)]
                    results[position].update(change)
                    self.assertEqual(self.classifier()(results), ("inconclusive", 2))
        for position in (3, 4):
            results = [defect(name) if i < 3 else passing(name)
                       for i, name in enumerate(NAMES)]
            results[position] = defect(NAMES[position])
            self.assertEqual(self.classifier()(results), ("inconclusive", 2))

    def test_missing_duplicate_and_incomplete_cases_fail_closed(self):
        results = [passing(name) for name in NAMES]
        malformed = [[], results[:-1], results + [results[0]],
                     [results[0]] * 5]
        incomplete = copy.deepcopy(results)
        del incomplete[0]["quick_check"]
        malformed.append(incomplete)
        for cases in malformed:
            self.assertEqual(self.classifier()(cases), ("inconclusive", 2))

    def test_real_matrix_is_memory_only_and_matches_archived_sql(self):
        probe = namespace.get("run_probe")
        self.assertTrue(callable(probe), "run_probe is not implemented")
        cases = namespace["CASES"]
        self.assertEqual(tuple(case[0] for case in cases), NAMES)
        start = len(CONNECTION_TARGETS)
        results = [probe(case) for case in cases]
        self.assertEqual(CONNECTION_TARGETS[start:], [":memory:"] * 5)
        for result in results:
            self.assertIsNone(result["error"])
            self.assertEqual(result["journal_mode"], "memory")
            self.assertEqual(result["table_rows"], [[0, 11], [11, 22]])
        self.assertEqual(results[0]["sql"],
            "CREATE TABLE v0(c1 INTEGER PRIMARY KEY ON CONFLICT REPLACE,c2 UNIQUE);\n"
            "INSERT INTO v0 VALUES(0,33),(11,22);\n"
            "REPLACE INTO v0 VALUES(0,11) ON CONFLICT(c2) DO UPDATE SET c1=c2,c2=c2"
            " ON CONFLICT(c2) DO UPDATE SET c1=c1,c2=c1;")
        for result in results[3:]:
            self.assertEqual(result["integrity_check"], ["ok"])
            self.assertEqual(result["indexed_count"], 2)
        broken = probe(("bad_sql", "INVALID", "", True))
        self.assertIsNotNone(broken["error"])

    def test_cli_report_exit_status_and_rejected_argument(self):
        self.assertTrue(SCRIPT.exists(), "diagnostic is not implemented")
        command = ["/usr/bin/python3", "-I", "-S", "-B", str(SCRIPT)]
        completed = subprocess.run(command, env={"PATH": "/usr/bin:/bin"},
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.stderr, "")
        report = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, report["exit_code"])
        self.assertEqual((report["classification"], report["exit_code"]),
                         self.classifier()(report["cases"]))
        rejected = subprocess.run(command + ["--database=forbidden.db"],
                                  env={"PATH": "/usr/bin:/bin"},
                                  capture_output=True, text=True, check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(json.loads(rejected.stdout)["classification"], "inconclusive")
        self.assertEqual(json.loads(rejected.stdout)["cases"], [])

unittest.main(argv=["sqlite-evidence-tests"], verbosity=2)
```
