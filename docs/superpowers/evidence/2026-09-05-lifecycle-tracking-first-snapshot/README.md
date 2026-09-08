# Tracking-First Snapshot Integrity

Date: 2026-09-05. Baseline: `0b66732b`.
Scope: implementation Tasks 0-1, temporary SQLite and synthetic evidence only.
No production read/write, provider call, migration installation, restart, merge
or push. This is not evidence that the new listing policy or whole feature works.

## Contract And Consumers

- `ProviderCheckStore._prepare` classifies a new observation once. Its reader
  calls only the versioned codec, never the evolving policy.
- V1 uses its original payload hash and frozen 0b66732b read-only reconstruction.
  V2 seals the version, payload and observation (excluding the self-referential
  digest field) with a distinct domain. Unknown/malformed explicit versions fail.
- The provider store is the only product reader of `observation_json`.
  Consumers use the unchanged plain-observation API: investigation composition,
  provider scanning, scheduler evidence loading and transition write guards.
- Classification/coarse state is consumed by the store, scan, decision policy
  and transition authority. Those live policy consumers are Task 2.
- Existing DDL requires valid JSON, at most 131072 characters of evidence JSON,
  four coarse states and append-only provider rows; no envelope-shape CHECK.
  Neither schema nor migration code changed.
- `observations()` includes tickers with any historical non-active check, then
  returns their latest observation. Recovered-active history is intentionally
  retained; always-active tickers are not introduced as cases.

## RED And GREEN

- Initial snapshot/store RED: **47 failed, 36 passed**. The 20 legacy policy-change
  cases fail by calling the patched current classifier; other failures expose
  the missing envelope/seal contract. Frozen baseline receipt controls pass.
- An additional RED owner proves V1 must not use V2 observation-shape rules.
- Eleven-file affected focus: **254 passed** before independent mutation runs.
- Seven more storage controls cover both formats at 131072/131073 characters,
  append-only/uniqueness and mixed-store batch rollback.
- Complete affected focus: **1228 passed in 69.92s**. `focused-nodes.json` lists
  those node IDs. It was captured after implementation, not before edits.
- Pre-edit baseline available from the preceding review was the four-file
  provider/store/scan/workflow focus, **44 passed**. No broader pre-edit result
  is claimed here.

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
  tests/test_security_lifecycle*.py tests/test_ticker_identity*.py \
  tests/test_sa_tracking_memberships.py tests/test_active_universe*.py --tb=short
```

## Independent Mutations

Each mutation ran against the entire 254-test focus in a separate code copy,
then was restored. The actual implementation worktree was never mutated.

| Mutation | Result | Named owner |
| --- | --- | --- |
| Reintroduce current classifier in V1 reader | 20 failed / 234 passed | `test_old_snapshot_readback_survives_current_policy_change` (20 cases) |
| Omit observation from V2 hash | 3 failed / 251 passed | `test_new_snapshot_envelope_seals_observation_and_uses_the_existing_schema`; tampering description/effective-date cases |
| Drop latest-active rows from historical query | 2 failed / 252 passed | `test_recovered_provider_check_retains_latest_active_observation`; existing worker recovered-case control |
| Accept numeric-equal non-int version | 1 failed / 253 passed | `test_snapshot_codec_rejects_unknown_or_malformed_explicit_version[2.0]` |
| Apply new-format shape rules to V1 | 1 failed / 253 passed | `test_legacy_codec_does_not_apply_new_observation_shape_rules` |

Restored copy: **254 passed in 19.41s**. The seven final storage controls were
added afterwards; they are in the 1228-test run, not claimed as mutation coverage.

## Fixture And Rollback Boundary

The fixture has 20 actual old-writer receipts using 30 shared synthetic evidence
rows, generated before the codec edit. It includes absent/multiple/candidate
timelines, missing/stale/conflicting required material and source failures. It
contains no production records and must not be regenerated using the new writer.

`tests/fixtures/security_lifecycle_provider_snapshots_v1.json` SHA-256:
`b065d0767c739cd9113d444ea4617d711228f6beb906db909c56fe0ac7b6e7b6`.

No DDL migration does **not** mean binary rollback is free. Once V2 is written,
0b66732b's reader rejects those rows. Before authorized deployment, stop writers
and make a consistent profile backup, retain the matching application revision
and prove readback. An immediate rollback before any writes may revert code;
after writes, retain the compatible reader or use an explicitly approved restore
of the pre-write backup with its potential loss of later profile changes spelled
out. Never silently delete new rows, strip the discriminator or rehash history.
