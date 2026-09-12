# C09 Implementation And Inverse Evidence

Initial implementation: 2026-09-12, base `88f0512e`.
Resumed inverses: 2026-09-13, HEAD `5d979910`, branch `codex/sec-research-integration`.
C09 was preserved by the controller as `f30ee8fc`; Task2 repairs are `5d979910`.
Workspace: `/tmp/arkscope-research-output-boundary`.
Authority: this workspace's `c09-brief.md` and the tracked pre-release cleanup audit.

## Handoff Status

**All required C09 inverse checks are complete and fully restored. Writes are
stopped.** Each resumed inverse failed its named assertion, was restored in
`finally`, matched its pre-mutation SHA-256, and passed its owner before the next
mutation. Fresh four-suite verification at `5d979910` is **196 passed**.
The resumed work leaves no tracked or staged diff and no active test session.
Independent acceptance remains with the controller and reviewer Mencius; no
Task2, full-backend, C10, or overall-cleanup completion is claimed here.

No git index writes or commits were made. `GIT_OPTIONAL_LOCKS=0` was used for
git read commands; `git diff --cached --exit-code` returned 0 with no output at
handoff. No provider, production DB, private config/env/token, installation,
restart, merge, push, or subdelegation was performed. Tests used the existing
current-plan offline runner, sanitized environment, isolated HOME/state paths,
disabled dotenv loading and provider-network guard. Other plan workspaces and
the SQLite agent's artifact contents were not read. Task2 files were not edited.

## Initial Tracked Changes

These are the original C09 changes, now preserved in the controller's
`f30ee8fc` commit, not outstanding changes from the resumed inverse work.

| Change | Path |
| --- | --- |
| Delete | `data_sources/alpha_vantage_source.py` |
| Delete | `data_sources/eodhd_source.py` |
| Delete | `data_sources/finnhub_source.py` |
| Delete | `data_sources/source_factory.py` |
| Modify | `data_sources/__init__.py` |
| Modify | `tests/test_abandoned_surface_cleanup.py` |
| Modify | `tests/test_data_provider_config.py` |
| Modify | `docs/design/ARKSCOPE_PROVIDER_CATALOG.md` |
| Modify | `docs/design/DESKTOP_APP_VISION_DRAFT.md` |
| Modify | `docs/data/IBKR_NEWS_API_LIMITATIONS.md` |

All ten paths are allowed by the brief. At the initial handoff, `git diff --stat` was
10 files changed, 118 insertions, 1551 deletions. `git diff --check` returned 0.
This untracked report and `c09-impl-*` / `c09-resume-*` runner output directories are the C09
scratch artifacts; the existing runner files were not modified.

## Product Boundary

- Removed `EODHDDataSource`, `AlphaVantageDataSource`, `FinnhubDataSource`, and
  the whole factory (`_SOURCE_REGISTRY`, `get_data_source`,
  `list_available_sources`, `register_source`, `get_multi_source_news`).
- Removed their package bindings, `__all__` entries and factory examples.
  No alias, disabled wrapper, new adapter, dependency or Settings change.
- Recheck found no CLI main guard in those four modules. The only external
  factory call was the Polygon constructor test. The unrelated
  `src/portfolio_capture_ibkr.py::_source_factory` remains unchanged.
- `PolygonDataSource` still serves `src/market_data_direct.py`; EDGAR/IBKR
  exports and the optional-IBKR import handling remain. Finnhub calendar and
  the distinct news collectors remain. EODHD census transport, provider-scan
  consumer, profile credential resolver and Settings/key paths remain.
- Current docs point to those real owners. Alpha Vantage is no longer labeled
  connected. Dated API comparisons remain explicitly historical, with removed
  source references anchored to `88f0512e`; no provider facts were reverified.
- C10-C20, collector CLI behavior, stored data and SEC integration are untouched.

## Test Ownership

Existing IDs were retained. In
`test_data_provider_config.py::test_polygon_data_source_constructors_prefer_massive_then_legacy`,
only the factory import/construction/assertion/close arm was removed. The real
direct constructor, both competing environment values, Massive-key assertion
and session cleanup remain. No other key/source test was changed.

Exactly seven collected IDs were added in `test_abandoned_surface_cleanup.py`:

```text
test_abandoned_leaf_is_physically_absent[data_sources/eodhd_source.py]
test_abandoned_leaf_is_physically_absent[data_sources/alpha_vantage_source.py]
test_abandoned_leaf_is_physically_absent[data_sources/finnhub_source.py]
test_abandoned_leaf_is_physically_absent[data_sources/source_factory.py]
test_data_source_package_does_not_import_abandoned_modules
test_data_source_package_has_no_abandoned_exports
test_data_source_package_preserves_current_exports
```

The import guard runs a fresh Python process and rejects obsolete module loads
with an assertion, including before cached imports can mask the dependency.
The export guard rejects obsolete `__all__` entries and package bindings.
The positive control checks current package exports against the real source
classes/data types, without making provider calls.

Final scope: cleanup 18, data-provider configuration 78, IBKR import safety 1,
lifecycle provider census transport 99: **196 tests**. Baseline was 189.
The before/after collection diff has exactly +7/-0 IDs; no skips were added.

## Commands And Evidence

All commands ran from the workspace root. `P` below abbreviates
`.superpowers/sdd/2026-09-12-sec-research-release-integration`; it was not a
required shell variable. Every runner invocation was:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B P/run_checks.py RUN_ID MODE ARGS
```

`SCOPE` below is the following literal four-file argument list:

```text
tests/test_abandoned_surface_cleanup.py tests/test_data_provider_config.py tests/test_ibkr_source_import_safety.py tests/test_lifecycle_provider_census_transport.py
```

| RUN_ID | MODE / ARGS | Observed outcome |
| --- | --- | --- |
| `c09-impl-baseline-01` | `backend -q SCOPE` | Exit 0, 189 passed |
| `c09-impl-collect-before-01` | `collect SCOPE` | Exit 0, 189 collected |
| `c09-impl-red-01` | `backend -q SCOPE` | Exit 1, 6 failed / 190 passed |
| `c09-impl-green-01` | `backend -q SCOPE` | Exit 0, 196 passed |
| `c09-impl-m1-leaf-01` | `backend -q 'tests/test_abandoned_surface_cleanup.py::test_abandoned_leaf_is_physically_absent[data_sources/eodhd_source.py]'` | Exit 1, exactly the owning assertion failed |
| `c09-impl-m1-restored-01` | `backend -q SCOPE` | Exit 0, 196 passed, 2.79s pytest time |
| `c09-impl-collect-after-01` | `collect SCOPE` | Exit 0, 196 collected |

Each named directory contains `command.json` with the complete executable,
arguments, environment, timing and exit code, plus `output.log`. Backend runs
also contain `results.xml`. In particular:

- [Initial RED](c09-impl-red-01/output.log): four physical-presence assertions,
  the fresh-import assertion and obsolete-export assertion failed before any
  product deletion. No collection errors; retained controls passed.
- [First GREEN](c09-impl-green-01/output.log).
- [M1 failure](c09-impl-m1-leaf-01/output.log).
- [Restored GREEN](c09-impl-m1-restored-01/output.log).
- [Before IDs](c09-impl-collect-before-01/output.log) and
  [after IDs](c09-impl-collect-after-01/output.log).

M1 temporarily reinstated the EODHD implementation from the base via
`apply_patch`. Its only difference from base was an added final newline
(base had no EOF newline); the failure was on physical presence, not content.
It was then deleted again. The four intended deletions and all six surviving
changed-file hashes exactly match the pre-mutation GREEN state below.

## Restored Written-File SHA-256

```text
7e47fc4f2ad6775fe0eff561875e658259386b47db4056c299e012e9f638a426  data_sources/__init__.py
8a91f1bc0c3fec4b19c669837ae647d5a477cd56400a77d01118f718e1d4c26f  tests/test_abandoned_surface_cleanup.py
45e333f0931b8b8aabc3631f78bb8411fd14def52e452f3e6cfcb3af1a7ed6bb  tests/test_data_provider_config.py
3ad7c0a6ab844a2463aa94f99f403c5e42429043c6b31d95fb028aaa2ac02b55  docs/design/ARKSCOPE_PROVIDER_CATALOG.md
6e86869691941c825f4336b7dac5ffcd6a4982f90f60e5271fdae18f2fc632d4  docs/design/DESKTOP_APP_VISION_DRAFT.md
e1e78c45817864a703cf86feb29e565b12883303928874edbb30381eb5447f42  docs/data/IBKR_NEWS_API_LIMITATIONS.md
```

## Unchanged Retained-Owner SHA-256

These matched both the pre-edit capture and the post-restoration capture:

```text
5207a5a44d3275f6e0d3d5849d3ee5ada055c52fde3e70156cc77db3aa5ea803  data_sources/polygon_source.py
ddf29d8b08f0af19eec1379f4225d0e70b806a54cfe163d9ec3c5f72b61b0574  data_sources/sec_edgar_source.py
1cf2641bd48c8ff9e3a046bdd9df55a712153ff260cc84f00559cb2574b66015  data_sources/ibkr_source.py
22a6c16e472c8991cdc40f3af0225439d5e312d6885896bd20cf753d22740375  data_sources/finnhub_calendar_client.py
320e94c5ebdbf75f932842712fe5f324513e5f2b4318aa3af5fcb475f4aca916  data_sources/lifecycle_provider_census_transport.py
8f4baea55856d229162a89a935a6d59ee3a1a34c9a8907205436dc407f53e5ca  src/data_provider_config.py
69038dcc56ccfeb6cc367919b23f22e5628108a48f038ff40681465bffa86b7a  src/market_data_direct.py
878931807f043d99d3024d68d3dafd981c4e7b6743de1995ef81e68247df868e  src/collectors/finnhub_news.py
ed24fdcd836df0f207c14073a000cc0c3257a57473d3b923a119b766f8190928  src/collectors/polygon_news.py
1f26f33113893d8354ce7af0ab9b3ee968fdedb6335ab0255bef5d20b8a9ee01  tests/test_ibkr_source_import_safety.py
91b7e870e838e689b118a13164ea7ba7a6359a7e47bf38a757c1da658f7f745f  tests/test_lifecycle_provider_census_transport.py
```

## Resumed Inverses: 2026-09-13

The initial controller stop occurred after M1 restoration. The controller later
authorized these remaining three inverses and explicitly extended temporary
mutation permission to `data_sources/polygon_source.py`. No initializer hack,
test change, new adapter, reset, checkout, stash, index write or commit was used.

Each case used serial tool orchestration: read the source hash; apply the mutant
with `apply_patch`; wait for the existing offline runner to exit; restore with
the inverse `apply_patch` in `finally`; compare the restored hash to the original;
run the restored owner to GREEN. No source was changed while a test process ran.
All temporary product writes ended with M4 restoration. Only this report and
runner evidence were subsequently written.

| Case | Temporary product mutation | Named owner and observed failure |
| --- | --- | --- |
| M2 | Added `FinnhubDataSource` to `data_sources/__init__.py::__all__` | `tests/test_abandoned_surface_cleanup.py::test_data_source_package_has_no_abandoned_exports`; assertion rejected `{'FinnhubDataSource'}` |
| M3 | In `data_sources/polygon_source.py::PolygonDataSource.__init__`, replaced the default key read with `os.environ.get("POLYGON_API_KEY") or os.environ.get("MASSIVE_API_KEY")` | `tests/test_data_provider_config.py::test_polygon_data_source_constructors_prefer_massive_then_legacy`; asserted `'polygon-legacy' == 'massive-primary'` and failed |
| M4 | Removed the package binding `from .polygon_source import PolygonDataSource` from `data_sources/__init__.py`, leaving the actual source class available | `tests/test_abandoned_surface_cleanup.py::test_data_source_package_preserves_current_exports`; assertion found `None` instead of the real `PolygonDataSource` class |

Each mutant produced exactly **one failed test, exit 1**, not a collection or
import error. Each byte-restored owner produced **one passed test, exit 0**.

### Resumed Commands And Evidence

Use the executable/runner prefix and literal `SCOPE` defined above. These are
new unique IDs; no previous evidence directory was reused. Full commands,
arguments, sanitized environment and exit codes are in each `command.json`;
each run also has `output.log` and `results.xml`.

| RUN_ID | Selection (`backend -q`) | Observed outcome |
| --- | --- | --- |
| `c09-resume-baseline-01` | All three named owners in the mutation table above | Exit 0, 3 passed |
| `c09-resume-m2-obsolete-export-01` | M2 owner | Exit 1, 1 failed |
| `c09-resume-m2-restored-01` | M2 owner | Exit 0, 1 passed |
| `c09-resume-m3-key-01` | M3 owner | Exit 1, 1 failed |
| `c09-resume-m3-restored-01` | M3 owner | Exit 0, 1 passed |
| `c09-resume-m4-retained-export-01` | M4 owner | Exit 1, 1 failed |
| `c09-resume-m4-restored-01` | M4 owner | Exit 0, 1 passed |
| `c09-resume-final-01` | `SCOPE` | Exit 0, 196 passed, 2.79s pytest time |

- [M2 failure](c09-resume-m2-obsolete-export-01/output.log) and
  [restored owner](c09-resume-m2-restored-01/output.log).
- [M3 real-constructor failure](c09-resume-m3-key-01/output.log) and
  [restored owner](c09-resume-m3-restored-01/output.log).
- [M4 binding failure](c09-resume-m4-retained-export-01/output.log) and
  [restored owner](c09-resume-m4-restored-01/output.log).
- [Fresh final four-suite result](c09-resume-final-01/output.log).

### Mutation Hashes

`sha256sum` was run before mutation, while mutated, and after restoration for
each case. Both before/after pairs also match the original C09 hashes recorded
above. The restored files were checked again after the final 196-test run.

```text
M2 data_sources/__init__.py
before:   7e47fc4f2ad6775fe0eff561875e658259386b47db4056c299e012e9f638a426
mutant:   6d60df0da867c5c9fbd402b5b5e5f2d82cc48eb4275a87855d80d8f8a11dfd0b
restored: 7e47fc4f2ad6775fe0eff561875e658259386b47db4056c299e012e9f638a426

M3 data_sources/polygon_source.py
before:   5207a5a44d3275f6e0d3d5849d3ee5ada055c52fde3e70156cc77db3aa5ea803
mutant:   f9166e1610a37cacfa9fa38c4dc54b32bf8b511f4e44469c7f20dcae15a908ea
restored: 5207a5a44d3275f6e0d3d5849d3ee5ada055c52fde3e70156cc77db3aa5ea803

M4 data_sources/__init__.py
before:   7e47fc4f2ad6775fe0eff561875e658259386b47db4056c299e012e9f638a426
mutant:   022bfc77d656f1a8dc8867643410c7e0678160793a97bc835330864827bd4b21
restored: 7e47fc4f2ad6775fe0eff561875e658259386b47db4056c299e012e9f638a426
```

The four test-file hashes also match their earlier values. No test IDs or
assertions changed in this resumed work. Read-only verification after the final
run returned exit 0 with no output for both:

```text
env GIT_OPTIONAL_LOCKS=0 git diff --exit-code
env GIT_OPTIONAL_LOCKS=0 git diff --cached --exit-code
```

Tracked status was clean on `codex/sec-research-integration`. No mutants remain.

## Remaining Review

All mandatory C09 inverse and scoped runtime checks are now satisfied. The
optional extra import-guard inverse was not added to this bounded resume; its
original assertion RED remains recorded above. Independent review/acceptance
belongs to the controller and Mencius. This worker has stopped writes and has
not begun C10. There are no active test sessions and no new product/test/doc
changes beyond the controller's existing commits.
