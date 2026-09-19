# Card Translation Retirement

Implementation date: 2026-09-19 through 2026-09-20.
Base: `544d8dfd` (Spark-only retirement, based on master `52037620`).

## Superseding Scope

The user's next instruction explicitly removes the entire low-value card
translation feature, including other-model translation, not only Spark. This
supersedes the preservation scope in the earlier Spark retirement packet.
Original AI cards, receipts, saved reports, Research conversations and Chinese
interface localization are retained. Historical lifecycle source translations
are a separate read-only evidence surface and are not relabeled or deleted.

The user permits appropriate commits, merges and deletion of obsolete branches
and backups. Push remains exclusively the user's action. This does not authorize
merging the unaccepted 31-commit fundamentals branch or deleting unrelated data.

## Removed Surface

- `card_translation` task, provider/model/effort settings, environment overrides,
  runtime setting, discovery/task-canary option and frontend model/runtime card.
- `/analysis/cards/{run_id}/translate`, translation dispatch, prose/schema
  transformation, error classifier, cache/version reads and writes.
- Card language/retranslate buttons, translated receipt presentation, timeout
  wrapper, error guidance, dead CSS and bilingual locale leaves/search aliases.
- Fresh database creation of `translations_json`, translation-version table and
  its index. Existing databases are read without these objects; destructive
  disposal is not hidden in a constructor or ordinary App startup.
- The old translation-only live API canary and its five exclusive harness tests.
  Its historical result records remain; it is no longer a runnable acceptance
  script against a removed translation function.

Spark retains only a historical rejection identity, preventing old/custom model
IDs from re-entering execution as an unknown model. No automatic replacement
model, credential, paid call or fallback is introduced.

## Coverage Ownership

| Retired cases | Retained owner |
| --- | --- |
| Translation-specific schema, text transformation, cache and version writes | Removed with the feature. `test_card_translation_retirement.py` proves task/API/writer absence, 404 with no credential/store work, no new translation schema and unchanged original-card reads from legacy stores. |
| Shared provider selection, selected credential, no billing fallback, timeout, receipt atomicity, sensitive-error handling | `test_card_execution_authority.py`, `test_card_synthesis.py`, `test_task_runtime_binding.py`; remaining synthesis cases preserved. |
| Responses request shape, model receipts, refusal/invalid output, no retry | `test_openai_fixed_output_compatibility.py`, `test_gpt6_admission.py`; the generic assertions now exercise synthesis, not a removed translation entry point. |
| Shared model picker, effort, discovery, dirty state and locale changes | Existing frontend owners now use active synthesis/Research/investigation tasks. Exact task and locale inventories are updated, not disabled. |
| Original card display, save and historical receipt | AICard/Home/API tests retain source identity and prove UI locale switching sends no translation request. |
| Route inventory | Exact count 223 to 222 plus explicit absence of the removed route in both route inventory owners. |

## Verification

- Initial retirement fixture: four expected failures before removal, then green.
- Related backend before final freeze: 534 passed, later route/card focus 128
  passed. These are separate focused runs, not a complete-backend claim.
- Complete frontend: 1,830 passed / 124 files.
- TypeScript and production build pass; pre-existing large-bundle warning remains.
- i18n literal scan: zero debt signatures. Electron shell: eight passed.
- Real component browser checks: 1440px and 390px, English and Traditional
  Chinese, original text preserved, no translation controls, save/runtime
  commands still function, no horizontal overflow or external/sidecar request.
  Runner: `browser_check.py`; synthetic screenshots under
  `/tmp/arkscope-card-retirement-browser/`. This is not production App activation.
- Frozen complete regression at `033c451572b4eb97088f6a088a7d13defba500a6`:
  **11,266 backend passed / 12 skipped**, 1,807.15 seconds, one plain
  `pytest tests/` process; **1,830 frontend passed / 124 files**, 13.98 seconds.
  TypeScript/build, i18n (zero debt signatures) and all eight desktop tests were
  freshly rerun at that revision. No second application pytest session ran in
  parallel. Separate disposal rehearsals imported no App code and used only
  in-memory databases outside the product worktree.
- The first full attempt at `751b2051` was stopped after a stale test expectation
  appeared. A first-failure replay reported one failed / 91 passed: the fresh
  route test expected two different models for synthesis after retiring its
  translation case. `033c4515` now checks all three active tasks exactly once;
  its eight-test focused file passed before the complete clean rerun above.
  Neither interrupted run is counted as acceptance.
- All 1,162 tracked files under `src`, `data_sources`, `tests` and `apps` kept
  the same fingerprint before and after complete backend/frontend verification:
  `791e18c52c7b88dbdaaff6e9416c10ec79895872421c079f542bbefaddbb6485`.
  Method: `git ls-files -z src data_sources tests apps | sort -z |
  xargs -0 sha256sum | sha256sum`. Subsequent changes add only this evidence,
  planning updates and the separately tested operator script below.

## Prepared Disposal, Not Executed

`checks/dispose.py` is an explicit one-time operator program, not a startup
migration, API or scheduler task. Its **10 standalone in-memory tests pass**:
unchanged originals/receipts/Research and remaining settings, repeat no-op,
embedded-only legacy state, changed target/settings shape, unexpected index,
views/triggers/FK dependencies, settings-cascade refusal and COMMIT rollback.
The code verifies integrity/FKs before and after one transaction, drops only the
translation table/index and embedded translation column, and removes only the
retired task's two settings rows. It preserves other schema, sequence entries,
protected row counts and the complete remaining route/runtime settings.

The command requires explicit `--apply --writers-stopped` flags and targets only
the approved main profile path, opened with `mode=rw` so it cannot create a
missing database. The stop flag is an operator assertion, not a substitute for
checking the App, native-host/collector writers and open DB handles. No actual
apply has run. No original-card text, translation text or credentials are dumped;
the eventual receipt contains counts and structural outcomes only. This operation
does not delete backups, alter private YAML/environment files or change unrelated
task selections. Private-file retirement keys, if present, still need a scoped
check during activation; this is not an automatic global configuration cleanup.

## Remaining Operations

The desktop App was still running at the last process check. No production
translation data or backups have been deleted. Once it and its writers are
closed, remove only translation cache/version data and the retired task's route
and runtime row, verifying original-card/receipt and Research records survive.
Do not erase historical model provenance on other tasks.

The old root-level June/July backup inventory contains 29 files, including
SQLite sidecars, totaling 13,324,488,704 logical bytes. A deletion decision is
restricted to that identified set; recent `data/backups/`, archives, current
databases and current WAL/SHM files are not included. Filename age alone is not
proof that an arbitrary backup can be deleted.

Earnings monitoring remains a separate scoped follow-up:
`docs/superpowers/plans/2026-09-20-earnings-observation-followup.md`.
The source-workflow branch and pre-existing dirty/unknown worktrees are retained.
Its previously uncommitted source/tool/research audit is now safely recorded at
`5c123120`; its inventory validator passed (56/57 tools, 17/18 OAuth tools each,
28 observed names and 37 valid relative links). That dated audit still describes
its original revisions, not a claim that its parked product code has this fix.
The unattached `codex/research-output-boundary` branch at `41682675` was deleted
only after confirming it is an ancestor of master. Attached worktrees with
ignored data or unknown edits were not removed. Main remains at `52037620`,
with its two pre-existing untracked documentation locations untouched. There
has been no merge, remote push or post-merge production smoke test.
