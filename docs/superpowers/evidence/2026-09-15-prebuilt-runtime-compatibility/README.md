# Prebuilt Runtime Compatibility Evaluation

Date: 2026-09-15 Asia/Taipei. Product/test source: `f42e79099e47c0cebb45f340599ec212c62d73d5`.
This is an evaluation receipt, not runtime admission or production activation.
No product code, installed selector, original Python/numpy/SDK package, production
database or App process was changed. No SQLite source archive or local compiler
was used. SEC and completed cleanup were not rolled back.

## Outcome

| Check | Observed result |
|---|---|
| Disposable project environment | 89 wheels, versions matching the original environment; candidate/control versions identical |
| Archived UPSERT matrix, unchanged | 5 pass, exit 0 |
| Reused database behavior probes | 8 pass, exit 0 |
| Single complete backend run | **11,147 pass / 26 setup errors / 43 skips**, 11,216 total, exit 1 |
| Additional large-ID cases, candidate | **5 failures**, exit 1 |
| Same additional cases, system-engine control | **5 pass**, exit 0 |

The candidate is **not accepted**. The full suite is not green. Its 26 errors
all occur in `tests/test_sqlite_runtime_contract.py` setup because the old
fixture reads `_sqlite3.__file__`. This prebuilt CPython has a built-in `_sqlite3`
module, as directly confirmed in [module identity](reports/module-identity.json),
so that attribute legitimately does not exist. This is not evidence
that the 26 behavioral properties passed: their replacement owners must run.
Of 43 skips, 31 are old launch-artifact cases requiring an offline SQLite source
archive; 12 are the existing manual IBKR/SEC checks. No skip/xfail or product
expectation was added. Do not compile SQLite merely to run the obsolete fixture.

The additional five cases are **not part of the 11,216 collected identities**.
They expose real parameter-capacity failures absent from the existing suite.
The 915-case repaired preflight is recorded separately and never added to the
full-suite count. Raw JUnit, logs and runtime identity are in [reports](reports/)
and [receipt.json](receipt.json).

## Artifact And Environment

- Publisher: [python-build-standalone release 20260901](https://github.com/astral-sh/python-build-standalone/releases/tag/20260901).
- Artifact: `cpython-3.10.21+20260901-x86_64-unknown-linux-gnu-install_only.tar.gz`.
- Downloaded SHA-256, matching the published release asset:
  `73cc92db5e6fb07ba611dca3709956d57cc2ed74ebcc01515b550ea89dfe9cba`.
- Python 3.10.21; actual SQLite 3.53.1; `MAX_VARIABLE_NUMBER=32766`.
- Control: disposable system-Python 3.10.12 environment, SQLite 3.37.2 with
  `MAX_VARIABLE_NUMBER=250000`, using the same 89 dependency versions.
- `uv 0.8.4` created disposable environments and installed wheels with
  `--only-binary :all:` and a scratch cache. The control reused that cache offline.
  Existing installed versions constrained the probe; no global tool was upgraded.
- [wheels.txt](checks/wheels.txt) records the resulting 89 versions. This is not
  a complete clone of the original 318-distribution environment or a signed
  wheel-hash lock. The three SDK hook files listed in the receipt were also
  compared byte-for-byte; that is not a claim about every dependency file.
- The isolated source's exact npm lockfile supplied 320 packages using
  `npm ci --ignore-scripts --no-audit --no-fund` and a scratch cache. No install
  script, browser/Electron installation or project manifest edit was performed.

This extends the earlier [memory-only spike](../2026-09-15-prebuilt-runtime-spike/probe.json).
It does not change that historical receipt's narrower scope. SQLite 3.53.1 is
still behind the reviewed [3.53.4 release](https://www.sqlite.org/releaselog/3_53_4.html).
The intervening fixes need a separate applicability decision before admission;
passing the archived bug reproducer does not prove every later fix irrelevant.

## Isolation And Source Identity

The scratch root was `/tmp/arkscope-prebuilt-compat.oCmRRHrQ`. A complete product
and test snapshot came from `git archive` at the revision above. Three encrypted,
non-runtime evaluation documents were excluded because git-crypt smudging was
unavailable: `data_sources/DATA_SOURCES_EVALUATION.md`,
`data_sources/IBKR_INVESTOR_DATA_VALUE.md` and
`data_sources/PAID_SUBSCRIPTION_EVALUATION.md`. No key was loaded or document
decrypted. `source-complete.tar`, not the aborted initial `source.tar`, supplied
the tested snapshot; its digest is in the receipt.

The [launcher](checks/run_tests.sh) uses `bwrap --unshare-all --clearenv` with
only disposable scratch writable, system `/usr` and the selected Node tree
read-only, and no production repository, user home, selectors or data stores
mounted. Network is unshared. There is no `LD_LIBRARY_PATH` or `LD_PRELOAD`.
The [pytest entry](checks/offline_pytest.py) directs store/lock/cache paths into
scratch, prevents `.env` loading, and adds outbound-network/provider-CLI guards.
Fixture launchers and version probes remain permitted. No credential-bearing
provider request was run. These are test containment controls, not a new product
Python sandbox or acceptance of arbitrary analysis execution.

The valid full run used **one `pytest.main(..., 'tests/')` invocation**, no
partition runner and no concurrent test/audit/agent/source-edit work. Its
main-entry receipt has exactly one record. The snapshot's tracked files remained
unchanged (`git diff --exit-code` returned 0). Runtime identity was measured in
the executing process before collection, not inferred from its filename.

## Invalid Initial Run And Repair

The first full attempt is **invalid and excluded in its entirety**. The temporary
runner omitted a `__main__` guard. Multiprocessing spawn imported it as
`__mp_main__`, recursively started pytest and shared fixture state across runners.
Missing temporary databases and cascading failures from that attempt must not
be classified as product defects, and none of its passes may be counted.

After checking the process group belonged exclusively to the disposable bwrap
run, it was terminated (exit 143); the parent and observed spawn workers were
confirmed gone. Its source snapshot was retired locally. The faulty entry is
retained only as [non-executable historical text](checks/invalid-runner.txt);
[the invalid log](reports/INVALID-full.log.gz) is not an acceptance report.

The corrected runner executes pytest only from `main()` under the standard
guard. Loading it as `__mp_main__` was checked to leave pytest unimported, cwd
unchanged and the probe directory empty. A fresh source snapshot and the locked
npm dependencies were prepared. The affected-module preflight passed 915 cases
with one main entry. Only then was the new complete run executed; it finished in
23m14s with the counts above. No product/test expectations were modified to fix
the runner. Raw reports distinguish all runs rather than merging their results.

## Parameter-Capacity Findings

Each archived [large-input case](checks/large_input_cases.py) invokes the existing
product method with synthetic data and approximately 33,000 IDs. Candidate
failures reach SQLite's `too many SQL variables`; the SA recovery methods wrap
that cause as `sa_market_news_recovery_unavailable`. No live workload size was
measured and these probes are not claims about current production damage.

| Product owner at the tested revision | Why the input is not bounded by the output limit |
|---|---|
| `src/tools/backends/sa_capture_backend.py:906,944` | Frozen-target projection/final body-presence queries bind one parameter per normalized news ID. |
| `src/sa_article_reconciliation_store.py:44` | The lineage filter expands every supplied positive normalized ID. |
| `src/sa_article_reconciliation_store.py:179` | The article filter binds all input IDs plus three parameters before applying the global 20-row limit. |
| `src/security_lifecycle_fact_kernel.py:2249` | Retained/preserved/cited evidence IDs are expanded into both family-refresh deletion exclusions. |

The lifecycle case duplicates fixture evidence/citation rows to exercise the
large retention set. It checks SQL retention and foreign-key/integrity behavior,
not the semantic validity of 33,000 independently generated assessment digests.
The static unbounded exclusion query is a separate observation. Do not treat
naive `NOT IN` chunking as a repair: it can delete another chunk's retained rows.
Per-chunk ordering/limits would also break global article selection.

Proposed, **not implemented and awaiting confirmation**: pass each normalized
ID set as one JSON parameter and select its values through `json_each(?)`.
Keep existing empty/None distinctions, normalization, deduplication, output order,
global limits, transaction boundaries and citation preservation. Preserve signed
64-bit binding rejection for oversized lineage integers rather than silently
rounding them through JSON numeric decoding. Add RED-first product tests covering
those semantics, quotes/unusual IDs and cross-engine large sets. The three
modules above own that bounded fix; do not force a private SQLite compilation
just to inherit the original distribution's parameter ceiling.

The absence of optional UPDATE/DELETE ORDER BY LIMIT grammar was found in the
earlier probe. The consumer review found explicit use in the superseded verifier
and its tests, not a current product query. This is not exhaustive proof about
every dynamically generated or future SQL statement.

## Reproduction And Remaining Gates

`checks/` preserves the exact scratch runners and inputs, not installed App
commands. Their frozen paths are part of this receipt. Reproduction in another
fresh scratch must retarget those paths; never point their writable source/store
paths at an installed checkout or database. Prepare the verified Python archive,
the exact source revision, wheel versions and locked npm dependencies first.
The large-ID file ran as `test_large_inputs.py`; its archive is named
`large_input_cases.py` to avoid automatic pytest discovery, with bytes unchanged.

The full invocation was:

```sh
/bin/sh /tmp/arkscope-prebuilt-compat.oCmRRHrQ/run_tests.sh full-valid \
  -q tests/ \
  --junitxml=/tmp/arkscope-prebuilt-compat.oCmRRHrQ/full-valid/junit.xml
```

Run the additional test file separately, once with the candidate and once with
`PROBE_PYTHON` pointing to the disposable control and `PROBE_EXPECT_SQLITE=3.37.2`.
The archived eight behavioral probe functions are byte-identical to the prior
synthetic probe (SHA-256 `cb7608899f564a1bdc275faf4c18df54e92f91fce994bae2c7274ddbc71c8be9`).
The thin prebuilt entry changes the identity driver, not those functions. Their
WAL workload is bounded stress, **not** a deterministic WAL-reset reproducer.

Still open: the scoped SQL fix; replacement of self-build/custom-loader code
and obsolete fixtures while transferring real safety tests; newer-fix review;
Desktop/SA/current writer entrypoint and descendant acceptance; an admitted
artifact/layout; and the separately authorized production backup/integrity/switch
window. The dormant analysis library, Windows/macOS and future Python sandbox do
not inherit this Linux probe's evidence. No merge or push occurred.
