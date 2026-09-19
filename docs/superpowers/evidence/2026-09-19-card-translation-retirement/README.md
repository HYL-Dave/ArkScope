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
- Final full-backend verification is recorded separately after the frozen run.

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
