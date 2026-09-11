# Task 2 R1 Focused Independent Re-Review

## Verdicts

- **Spec Compliance: PASS for Task 2's reviewed scope.** R1 resolves the previously failed generic FK-retention requirement; the other Task 2 files remain hash-identical to the original reviewed snapshot.
- **Task Quality: PASS for this focused revision.** No remaining blocker or new finding was identified in the canonical-target change and its named cross-call paths.
- **Original P1: FIXED.** The differently cased FK-target defect was pre-existing at `2842c497`, not introduced by Task 2. This report updates its resolution status without rewriting that attribution or the original review.

This is not the parent whole-branch/full-suite verdict or authorization for actual-store disposal.

## Frozen Identity

Repository: `/tmp/arkscope-listing-sec-macro-convergence`.
Base and observed HEAD: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
Subject: frozen uncommitted snapshot supplied in `task2r1-review-package.md`.

| Artifact | SHA-256 |
| --- | --- |
| `task2r1-review-package.md` | `bf3a3805fd8ff7f11d530f628bad4479203fe41afc03ded4b5e191af144a5484` |
| Exact packaged/scoped diff payload | `0c9a3d3c94679073ddc398194ba3bbf07d0dc9636eeef81e8294dc1e438143e6` |
| `task2-r1-report.md` | `3dae8ffa554af58fa63711f81e28df80558858eb363fc74bfcc6fd9e5cc65333` |
| `src/lifecycle_investigation/disposal.py` | `d55cd056293761452c47762d1511c70cd535c9911d149ef54d8e1fd9b80a8865` |
| `tests/test_lifecycle_investigation_retirement.py` | `6a6d281e5ba1e741143a09f4c05d295c6676ee33a7af651486468300c2167418` |
| `task2-r1-final.xml` | `a5c19ad704c95c008b90d00770d567d25ff5082c94eeee0218f861d2a168cbd4` |
| Original `task2-review.md`, preserved | `73097502de2d46e342a86d9317fccc6febd0bb5b2401dfb99f4c8564c07116bb` |

Verified every one of the 12 package entries: nine present-file hashes and three absences. Verified both source hashes and all six XML hashes declared in the implementer report. The packaged diff exactly matches `git diff --no-ext-diff --unified=20 2842c497 -- <the 12 package paths>`. Only disposal and its retirement tests differ from the original Task 2 package; the other ten entries are unchanged.

## P1 Resolution Evidence

The original source is the declared parent spelling returned by `PRAGMA foreign_key_list`. The sensitive sink is the owned parent DELETE that could previously cascade into an unrecognized external child while leaving FK integrity clean.

[disposal.py:73](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:73) now resolves each parent through `sqlite_master` with parameterized `name=? COLLATE NOCASE` and emits the actual catalog name. Resolution occurs in `foreign_keys`, so [closure at line 81](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:81), [market_dependency at line 147](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:147), and [_delete_order at line 194](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:194) receive the same canonical identity. No caller-specific workaround or old-web ownership is restored.

Both `profile_scope` and `market_scope` consume these resolved edges. [apply_disposal_stage at line 234](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:234) checks the scope before backup and again after `BEGIN IMMEDIATE`, before receipt creation or deletion. The revised mapping therefore closes both the preview omission and its repeated preflight/locked-revalidation omission. Missing-target fallback, owned sets, approval/backup/receipt guards, current schema definitions and stage sequencing are otherwise unchanged.

The lookup uses SQLite's identifier-compatible ASCII case comparison rather than Python Unicode casefold. The U+017F external-table control remains a different parent, preventing an overbroad mapping from retaining an unrelated disposable owned root.

### Named Test Owners Inspected

| Owner in `tests/test_lifecycle_investigation_retirement.py` | Protection actually asserted |
| --- | --- |
| [test_cased_cascade_fk_is_retained_by_preview_and_empty_apply:39](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:39) | Four profile/market x upper/mixed cases with real CASCADE FKs. Preview retains the case and market ID; both empty stages execute, then actual parent/child rows remain and FK checks are clean. |
| [test_cased_cascade_fk_added_after_preview_blocks_apply:61](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:61) | Eight cases add the child after preview or after the real backup. The former rejects before backup; the latter rejects during locked revalidation with backup retained. Parent/child rows survive and no target-stage completion receipt is published. Market cases first complete the required profile stage. |
| [test_disposal_does_not_casefold_distinct_non_ascii_fk_targets:98](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:98) | Two legitimate distinct U+017F parents retain their own children without blocking the unrelated approved owned roots. Both stages execute. |
| [test_disposal_preserves_approved_current_investigation_and_idempotent_confirmation:120](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:120) | A real current investigation is prepared and confirmed before separate fixture disposal; its journal read is unchanged afterward and repeated confirmation is `already_applied`. |

The existing eleven retirement nodes remain, including lowercase external-FK controls, human acceptance, action history, backup/receipt safety and rollback. These assertions address the actual retention consequence, not just normalized strings or missing modules.

## Actual Checks

No pytest or full-suite run was started by this re-review. Existing JUnit records were independently parsed, rather than accepting report totals:

| Evidence | Actual records |
| --- | --- |
| Initial R1 RED | 14 failed / 12 passed; includes two fixture schema-prefix failures, not treated as clean behavioral RED |
| Confirmed R1 RED | 12 failed / 14 passed; four incorrect preview selections and eight missing `ValueError` rejections |
| R1 GREEN | 26 passed |
| Declared-target mutation | 12 failed at the same preview/apply owners |
| Unicode-casefold mutation | 2 failed because the distinct-target controls incorrectly retained the owned roots |
| R1 final | 164 passed, zero failure/error/skip records |

All six artifacts have zero error/skip records and no duplicate nodes. Final accounting against original `task2-final.xml`: fifteen added nodes, none removed; the added set exactly matches the report. Final counts are backup 12, population 70, current 44, policy rollover 9, retirement 26, current migration 3. The GREEN retirement node set is contained in final.

Fresh static checks: both revised Python files parse; scoped `git diff --check` is clean; package/source/evidence hashes match. Reviewed the common edge reader and its profile/market/deletion-order consumers, not unrelated branch changes.

### Fresh Original-Reproducer Check

Ran 16 source-extracted, memory-only scenarios: exact base and frozen r1 x profile/market x lowercase/uppercase/mixed-case/distinct-Unicode target. Used the actual `foreign_keys`, `closure`, `market_dependency` and quoting functions, extracted via AST without product imports, with minimal owned-root/external-child fixtures and FK enforcement ON. A conditional parent DELETE demonstrated the cascade consequence only when the guard admitted disposal.

| Variant on both stores | Base | R1 |
| --- | --- | --- |
| Lowercase owned target | Blocks; child remains | Blocks; child remains |
| Upper/mixed-case owned target | Misses; CASCADE removes child | Blocks; child remains |
| Distinct U+017F target | Owned root remains disposable; distinct child survives | Same legitimate behavior; catalog target remains distinct |

All 16 expected observations were asserted successfully, and every FK check was clean. Thus the probe freshly reproduces the original base defect and confirms its resolution in r1 without conflating a valid cascade with an FK violation.

Execution used `env -i`, `/usr/bin/python3 -I -B`, `PYTHONDONTWRITEBYTECODE=1`, and unique workspace identity `task2-r1-review-fk-probe-e7bb8071`. The audit hook allowed only `:memory:` SQLite opens and denied socket/subprocess activity during subject evaluation. No scratch directory or database file was created. This is a focused helper reproducer, not a fresh full-stage integration run; the complete preview/apply/race coverage above is inspected source plus supplied JUnit evidence.

## Residual Limits

- No remaining concrete question blocks resolution of this P1. The original defect remains recorded as pre-existing in the untouched [task2-review.md](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-review.md).
- The 164-pass result is verified artifact evidence, not a suite execution by this reviewer. JUnit alone does not independently authenticate the entire execution environment or neighboring task state.
- Parent full-suite/whole-branch review and complete Task 1/3 integration remain separate. The additional current-investigation preservation owner is relevant protection, not certification of all confirmation/history/cancellation behavior.
- No actual database, configuration/.env, credentials, provider/network, install, App/server start, disposal operation, index or HEAD mutation was performed. Only this new review was written, via `apply_patch`; the original report was not overwritten.

```json
{
  "results": [
    {
      "id": "task2-P1-cased-fk-target-retention",
      "status": "fixed",
      "evidence": "Pre-existing at 2842c497. Frozen r1 disposal.py:73 resolves declared FK targets to catalog names before closure, market_dependency and deletion ordering. Fresh 16-scenario memory comparison reproduces upper/mixed-case CASCADE loss at base and blocks it in r1 while preserving distinct U+017F targets. Inspected pre/post-preview and post-backup owners, 164-pass final XML, and declared-target/Unicode-casefold mutation failures. No remaining focused blocker; full-branch acceptance and real-store operations are outside this verdict."
    }
  ]
}
```
