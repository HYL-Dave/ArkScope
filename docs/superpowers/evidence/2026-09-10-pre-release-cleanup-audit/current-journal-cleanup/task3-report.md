# Task 3: SEC Configuration And Paths Foundation

Implemented in `/tmp/arkscope-listing-sec-macro-convergence` on the existing
`codex/listing-sec-macro-convergence` worktree. No commit, staging, merge, push,
restart, installation, provider call, network request, production DB access,
configuration-file edit, token access, or 100 GiB allocation was performed.

Status: foundation implemented and focused offline verification passed.
The five product/test files are FROZEN FOR INDEPENDENT REVIEW; this worker will
make no further source/test changes. Parent owns evidence archiving, broad-suite
verification, independent review, and serialized integration/commit.
This is NOT a user-ready SEC feature or the three SEC tools.

## Files

Only these five product/test files were created or edited by this task:

- `src/sec_research/__init__.py`
- `src/sec_research/config.py`
- `src/sec_research/paths.py`
- `tests/test_sec_research_config.py`
- `tests/test_sec_research_paths.py`

This requested report and runner-generated `task3-*` evidence are in the existing
ignored plan scratch directory. Concurrent Task 1/2 changes were not modified.
The plan, approved spec, existing authorities, and runner were read, not edited.

## Contracts

- `get_capture_budget_bytes(store)` uses the real
  `ProfileStateStore.get_settings_snapshot` API. Only absence defaults to
  `107374182400` bytes, exactly 100 GiB. Present NULL, malformed/noncanonical
  decimal text, blobs, nonpositive values and overflow raise `ValueError` without
  repair or fallback.
- `set_capture_budget_bytes(store, value)` accepts only Python integers in
  `1..9007199254740991`, explicitly excluding booleans and all floats. It writes
  canonical decimal text to `sec_research.capture_budget_bytes` with the existing
  `set_setting` API and returns the exact integer. Increases above the default,
  decreases to one byte, large odd integers, and the maximum round-trip exactly.
  Other settings, their timestamps, and the profile schema remain unchanged.
- Neither budget accessor creates a market/capture directory or file. No
  schedule, registration, acquisition, reservation, schema, or UI code was added.
- Frozen `SecResearchPaths` resolves its `market_db_path` once. `resolve()` calls
  the existing `src.market_data_admin.resolve_market_db_path` authority;
  `from_market_db(path)` binds an explicit path. There is no new environment key.
- For resolved market DB `P`, `capture_root` remains exactly
  `P.parent / (P.name + ".sec-research")`. Database symlinks bind the target store,
  relative inputs remain stable after CWD changes, distinct filenames produce
  distinct roots, and moved DB/capture pairs reopen the same relative object key.
- `object_path(key)` returns a resolved path without creating anything. Keys use
  canonical POSIX-relative syntax. Validation rejects absolute/parent paths,
  empty/dot components, foreign Windows drive/root/UNC/device paths, backslashes,
  alternate streams, control characters, invalid Windows characters, trailing
  dots/spaces, and reserved Windows names in any component. Unicode filenames
  and literal percent characters remain valid; keys are never URL-decoded.
- Resolution checks containment against the DB-derived anchor, not a symlink's
  substituted root. Tests cover directory/file/dangling/chained/root symlinks,
  sibling paths sharing the root's string prefix, loops, and aliases to the root
  itself. A separate owner covers a capture-root symlink already present before
  path binding. Symlinks resolving to objects inside the root remain usable.

## Offline Runs

All commands ran from the supplied worktree using this exact environment and
runner pattern, with the run IDs and selectors recorded below:

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/<run-id> /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q <selectors> --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/<run-id>.xml
```

Every run has a separate workspace and matching JUnit XML in this directory.
The reviewed runner installed its production-data/network guards before imports.
Profile fixtures are real temporary SQLite stores; filesystem fixtures contain
only tiny test data. There are no mocked profile-store implementations.

Selector aliases below expand exactly as follows:

```text
SEC:
tests/test_sec_research_config.py tests/test_sec_research_paths.py

CONTROLS:
tests/test_profile_state.py::test_profile_settings_get_set
tests/test_profile_state.py::test_profile_settings_snapshot_distinguishes_missing_from_present_null
```

| Run ID | Selectors / extra arguments | Result |
| --- | --- | --- |
| `task3-red-owners-01` | SEC + CONTROLS, before behavior cases were added | 3 failed, 2 passed; exit 1 |
| `task3-red-behavior-02` | SEC + `--tb=line`, before product modules existed | 125 failed; exit 1 |
| `task3-green-03` | SEC + CONTROLS | 127 passed; exit 0 |
| `task3-mut-null-04` | Exact mutation owners below | 1 failed; exit 1 |
| `task3-mut-bool-05` | Exact mutation owners below | 2 failed; exit 1 |
| `task3-mut-range-06` | Exact mutation owners below | 2 failed; exit 1 |
| `task3-mut-traversal-07` | Exact mutation owner below | 1 passed; exit 0; redundant guard survived |
| `task3-mut-traversal-all-08` | Exact mutation owner below | 1 failed; exit 1 |
| `task3-mut-symlink-09` | Exact mutation owners below | 7 failed; exit 1 |
| `task3-green-restored-10` | SEC + CONTROLS, all mutations restored | 127 passed; exit 0 |
| `task3-mut-preexisting-root-11` | Additional pre-existing-root owner below | 1 failed; exit 1 |
| `task3-green-frozen-12` | SEC + CONTROLS, including the additional owner, all mutations restored | 128 passed; exit 0 |

Both RED runs were assertion failures, not import/collection errors. The three
initial assertions owned `__init__.py`, `config.py`, and `paths.py` existence.
The second RED run deliberately stopped each case at its missing-module
assertion gate; it is not claimed as evidence of individual runtime branches.
The real branch failures are demonstrated by the inverse mutations below.
All runs reported zero errors and zero skips.

Final exact command (128 passed in 2.23 seconds):

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task3-green-frozen-12 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sec_research_config.py tests/test_sec_research_paths.py tests/test_profile_state.py::test_profile_settings_get_set tests/test_profile_state.py::test_profile_settings_snapshot_distinguishes_missing_from_present_null --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task3-green-frozen-12.xml
```

## Inverse Mutations

Each mutation was applied manually with `apply_patch`, executed only through the
offline runner, and restored. No mutant remains in the delivered files.

1. `task3-mut-null-04`: replaced membership testing with
   `snapshot.get(CAPTURE_BUDGET_KEY) is None`, incorrectly defaulting explicit NULL.
   This exact owner failed with `DID NOT RAISE ValueError`:

   ```text
   tests/test_sec_research_config.py::test_budget_defaults_only_when_the_key_is_absent
   ```

2. `task3-mut-bool-05`: replaced `type(value) is not int` with
   `not isinstance(value, int)`, admitting `True`. Both owners failed with
   `DID NOT RAISE ValueError`:

   ```text
   tests/test_sec_research_config.py::test_budget_setter_rejects_invalid_values_before_writing[bool-true]
   tests/test_sec_research_config.py::test_rejected_budget_does_not_create_an_absent_setting
   ```

3. `task3-mut-range-06`: raised the technical bound from `2**53 - 1` to
   `2**63 - 1`. Both owners failed with `DID NOT RAISE ValueError`:

   ```text
   tests/test_sec_research_config.py::test_budget_setter_rejects_invalid_values_before_writing[overflow]
   tests/test_sec_research_config.py::test_budget_rejects_corrupt_persisted_values_without_repair[overflow]
   ```

4. `task3-mut-traversal-07`: removed only `".." in relative.parts`. This owner
   PASSED because the trailing-dot component check independently still rejected
   `..`. This was a surviving redundant mutation, not a killed mutation:

   ```text
   tests/test_sec_research_paths.py::test_object_path_rejects_unsafe_or_malformed_keys[contained-traversal]
   ```

5. `task3-mut-traversal-all-08`: additionally removed the trailing-dot/space
   component check, leaving the reserved-name check. The same exact owner then
   failed with `DID NOT RAISE ValueError`, proving that normalized-but-contained
   `objects/../body` cannot silently become a valid persisted key.

6. `task3-mut-symlink-09`: removed the final
   `resolved == root or not resolved.is_relative_to(root)` rejection. The command
   selected `test_object_path_rejects_symlink_escape` and
   `test_object_path_does_not_accept_a_symlink_to_the_root_as_an_object`.
   All seven expanded owners failed with `DID NOT RAISE ValueError`:

   ```text
   tests/test_sec_research_paths.py::test_object_path_rejects_symlink_escape[directory]
   tests/test_sec_research_paths.py::test_object_path_rejects_symlink_escape[file]
   tests/test_sec_research_paths.py::test_object_path_rejects_symlink_escape[dangling]
   tests/test_sec_research_paths.py::test_object_path_rejects_symlink_escape[chain]
   tests/test_sec_research_paths.py::test_object_path_rejects_symlink_escape[prefix-sibling]
   tests/test_sec_research_paths.py::test_object_path_rejects_symlink_escape[capture-root]
   tests/test_sec_research_paths.py::test_object_path_does_not_accept_a_symlink_to_the_root_as_an_object
   ```

7. `task3-mut-preexisting-root-11`: reapplied the same containment mutation as
   run 09 after adding a test that creates the escaping capture-root symlink
   before constructing `SecResearchPaths`. This new owner first failed with
   `DID NOT RAISE ValueError`, then passed after restoration in run 12:

   ```text
   tests/test_sec_research_paths.py::test_object_path_rejects_preexisting_capture_root_symlink
   ```

Summary: six failing mutation runs covering five distinct effective mutants;
one redundant single-guard mutation survived. The final restored run passed
every named owner. The existing-root check does not solve future TOCTOU races.

## Exact Test Inventory

No existing test nodes were removed or changed. The final new suite contains 54
config nodes and 72 path nodes, plus the two unchanged controls above in GREEN
runs. The pre-existing-root owner was added after the original 125-case suite.
For each table row, the full node ID is `<file>::<test>[<parameter-id>]`, with no
suffix for `none`. Every parameter ID is listed; JUnit records expanded IDs.

File: `tests/test_sec_research_config.py`

| Test | Parameter IDs |
| --- | --- |
| `test_sec_configuration_owner_exists` | `__init__.py`, `config.py` |
| `test_budget_defaults_only_when_the_key_is_absent` | none |
| `test_budget_reads_exact_canonical_integers_without_writes` | `minimum`, `below-default`, `default`, `above-default`, `large-odd`, `maximum` |
| `test_budget_rejects_corrupt_persisted_values_without_repair` | `empty`, `zero`, `negative`, `plus`, `leading-zero`, `leading-space`, `trailing-space`, `newline`, `nul`, `whole-float`, `fraction`, `exponent`, `nan`, `infinity`, `negative-infinity`, `true-text`, `false-text`, `null-text`, `underscore`, `hex`, `unicode-digit`, `fullwidth-digit`, `overflow`, `huge-overflow`, `blob` |
| `test_budget_setter_rejects_invalid_values_before_writing` | `null`, `bool-true`, `bool-false`, `zero`, `negative`, `whole-float`, `fraction`, `default-float`, `nan`, `infinity`, `negative-infinity`, `numeric-text`, `bytes`, `list`, `dict`, `overflow`, `huge-overflow` |
| `test_rejected_budget_does_not_create_an_absent_setting` | none |
| `test_budget_changes_persist_exact_text_and_leave_other_settings_untouched` | none |
| `test_budget_accessors_do_not_create_market_or_capture_files` | none |

File: `tests/test_sec_research_paths.py`

| Test | Parameter IDs |
| --- | --- |
| `test_sec_paths_owner_exists` | none |
| `test_capture_root_keeps_the_resolved_database_filename_without_creating_files` | none |
| `test_two_market_databases_in_one_directory_have_distinct_capture_roots` | none |
| `test_relative_market_binding_survives_cwd_changes` | `from_market_db`, `constructor` |
| `test_market_binding_cannot_be_reassigned` | none |
| `test_resolve_uses_market_environment_authority` | none |
| `test_resolve_uses_existing_default_authority` | `absent`, `empty` |
| `test_resolve_delegates_to_existing_market_path_resolver` | none |
| `test_market_database_symlink_binds_the_target_store` | none |
| `test_relative_object_key_reopens_the_capture_after_relocation` | none |
| `test_safe_relative_object_keys_are_resolved_without_writes` | `nested-hash`, `canonical-text`, `embedded-dots`, `literal-percent`, `unicode-name` |
| `test_object_path_rejects_unsafe_or_malformed_keys` | `empty`, `dot`, `parent`, `parent-prefix`, `nested-traversal`, `contained-traversal`, `dot-prefix`, `dot-component`, `empty-component`, `trailing-separator`, `posix-absolute`, `forward-unc`, `windows-forward-drive`, `windows-drive`, `windows-drive-relative`, `windows-drive-only`, `windows-rooted`, `windows-unc`, `windows-extended-drive`, `windows-extended-unc`, `windows-device-path`, `windows-traversal`, `windows-separator`, `nested-drive-or-stream`, `alternate-stream`, `nul`, `newline`, `control-character`, `delete-character`, `trailing-dot`, `trailing-space`, `reserved-device`, `reserved-device-extension`, `reserved-directory`, `reserved-port`, `question-mark`, `asterisk`, `left-angle`, `right-angle`, `double-quote`, `pipe`, `null`, `integer`, `bytes`, `path-object` |
| `test_object_path_rejects_symlink_escape` | `directory`, `file`, `dangling`, `chain`, `prefix-sibling`, `capture-root` |
| `test_object_path_rejects_preexisting_capture_root_symlink` | none |
| `test_object_path_allows_symlinks_that_stay_beneath_the_capture_root` | none |
| `test_object_path_does_not_accept_a_symlink_to_the_root_as_an_object` | none |
| `test_object_path_rejects_symlink_loops_as_invalid_keys` | none |

## Final Checks And Limitations

- Scoped `git diff --check` returned exit 0. Each new file was also checked using
  `git diff --no-index --check /dev/null <file>`: empty diagnostic output, exit 1
  for the new-file difference, with no whitespace errors.
- This worker performed focused code/test self-review. An independent reviewer
  was not dispatched from this tool context; parent review is still required.
- The full backend suite, repository inventory/census, integration, and actual
  data disposition are not claimed here. They remain parent/Task 4 work.
- Windows drive/UNC/device syntax is exercised on Linux through the standard
  path parsers. A native Windows filesystem run was not performed.
- `object_path` validates the filesystem at resolution time. It is not an atomic
  file-open/publication primitive and does not prevent a hostile filesystem
  mutation after validation. Future capture I/O needs its own race-safe handling.
- Relocation tests move small fixtures and read a retained object. They are not
  validated SQLite export/restore tests, which are explicitly future work.
- Catalog, facts, document capture, capacity accounting/reservations, export and
  restoration, API/UI, schedule, and atomic three-tool registration remain
  unimplemented by this foundation task. No SEC workflow readiness is implied.

Final file SHA-256 values:

```text
283db4d3a4f27a14b29fb8e6b1c60bac262252a801ceea21c7f6375ef574d07f  src/sec_research/__init__.py
67818a242046a94b97c61a6fc80e24627dc4eed9a4c13da77efc0b918a30646c  src/sec_research/config.py
93fc1abd8addc3d7b924d1b6b67ab0a94a7203d061da4e7c8a4b7a57e3005eaa  src/sec_research/paths.py
8bcbbaf8c54b88f26e0165fcbb52b802c1f5e0645e3115e72ad9d8f5833cfea9  tests/test_sec_research_config.py
0bdad74318b5849d89fe9f2810a295401299fc46bf13a266b8fa460f01afc408  tests/test_sec_research_paths.py
```
