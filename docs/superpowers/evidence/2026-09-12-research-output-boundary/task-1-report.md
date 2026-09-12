# Task 1 Report

## Delivery

- Final commit: `f2068c7599cb71f2aa86112b6659f7f88eac7f30` (shared-guard concurrency correction).
- Core commit: `2f0cedeb62c6663e1d55ebf82e8623833c631095`.
- Pre-dispatch base: `e0b0ed4aafd1fce1687ff7fa6b7dc6e391c9a469`.
- Workspace: `/tmp/arkscope-research-output-boundary`.
- Both commits contain ONLY `src/agents/shared/output_boundary.py` and `tests/test_output_boundary.py`.
- This report and `task-1-checks.json` are plan-local ignored artifacts, not committed.
- Final verification: **112 passed, 0 failed, 0 errors, 0 skipped**: 74 primitive tests, 27 unchanged probe tests, 11 unchanged security/wrapper tests.
- The coordinator separately reported the unchanged existing baseline as 308 passed. That number is not a fresh run by this task and is not combined with the 112 above.

No registry, driver, plan, spec, diagnostic heuristic, skill script, auth store, provider integration, or stream-wrapper implementation was edited. Coordinator plan/spec edits remain untouched. No subagents, installs, network/provider sessions, production data, credentials, .env access, merges, pushes, or application restarts were used.

## Final Contract

```python
OutputBoundaryError(code: str)  # ValueError subclass; .code and .args hold only a trusted code
OutputGuard(secrets: Iterable[str | None] = ())
guard.add_secret(secret: str | None) -> None
guard.check(value: object) -> None
guard.prose(text: str) -> str
guard.stream() -> SecretStream
stream.feed(text: str) -> str
stream.finish() -> str
stream.abort() -> None
current_output_guard() -> OutputGuard | None
remember_output_secret(secret: str | None) -> None
output_scope(*secrets: str | None, inherit: bool = False)  # context manager yielding OutputGuard
activate_output_guard(guard: OutputGuard)                # context manager yielding the borrowed guard
```

`check` accepts exact built-in JSON types: dict with str keys, list, str, int, finite float, bool, and None. It recursively scans strings AND mapping keys. It returns None on success and never mutates or serializes the input. Unsupported objects/subclasses, bytes, tuples, sets, nonstring keys, nonfinite floats, and cycles are rejected without arbitrary str/repr coercion. Repeated noncyclic references are allowed and counted per occurrence.

Task 2 owns normalization, result policies, explicit credential-field denial, canonical serialization, and the encoded byte budget. In particular, numeric leaves are not rendered by `check`: check the actual canonical emitted string as well as the normalized value to cover numeric coincidences and serializer output. No field-name exemption or heuristic prose regex exists here.

`None` and empty credentials are absent; other secrets must be exact strings. Registration is additive, deduplicated, and atomic on validation/budget failure. Constructor input is a trusted iterable of already captured credentials, not an auth-store query.

`prose` is a display projection, not a source quotation. Raw-offset overlapping AND adjacent matches coalesce to one `[REDACTED]`. Normal `finish` matches complete credentials and flushes unmatched prefixes unchanged. Abort, feed failure, and root-scope cancellation discard pending raw text; finish after closure returns an empty string, and feed after closure raises `stream_closed`.

Default scopes create independent guards. Explicit `inherit=True` shares the already-active guard, or creates a root if none exists. Child/refreshed credentials remain available to later callbacks in the same execution. Owned root exit aborts unfinished streams; inherited exit does not. `activate_output_guard` only borrows/restores context and never aborts streams or clears credentials. Exit either context before publicly yielding; Task 3 must activate the retained guard separately around each upstream anext/aclose and own iterator closure and normal/abnormal stream termination.

An RLock serializes registration, matcher-cache publication, and coherent stream pattern/length/marker snapshots. Matcher objects are not changed after construction. The weak stream registry is also synchronized. Each check and internal stream slice takes a current snapshot; streams do not freeze patterns at creation. Register BEFORE provider use. No retrospective detection is promised for prior snapshots, emitted text, or discarded history. A single SecretStream remains single-consumer; its owner must sequence feed/finish/abort.

## Error Codes

| Code | Meaning |
| --- | --- |
| known_secret | A complete protected representation occurred in a checked string/key. |
| invalid_secret | Credential type or UTF-8 encoding is invalid. |
| secret_limit | Distinct-secret count or raw-secret length limit exceeded. |
| representation_limit | Protected representation count/length/aggregate limit exceeded. |
| invalid_value | Unsupported JSON/prose/feed/activation input, nonfinite float, or cycle. |
| value_limit | JSON depth/nodes, aggregate text, prose length, or feed length exceeded. |
| stream_closed | A feed was attempted after finish/abort/failure. |
| redaction_marker_conflict | Emitting the fixed marker could reproduce a known secret within the marker or across an edge. |
| not_serializable | Guard, matcher, or stream serialization/copy protocol refused. |
| no_output_scope | remember_output_secret was called without an active guard. |
| output_boundary_error | Safe fallback when OutputBoundaryError receives an unrecognized/nonstring code. |

Error codes contain no rejected value or secret-derived details. Guard/stream reprs contain only their type name; pickle, copy/deepcopy, and getstate refuse serialization. Fixed trusted labels/codes can coincidentally equal or contain very short synthetic secrets; this is not a universal substring-absence claim about control metadata.

## Encodings And Bounds

Exactly these single-step, case-sensitive variants are derived from each captured string; duplicates are removed:

1. Raw string.
2. JSON-escaped string contents from Python json.dumps with ensure_ascii=False and True, with only the surrounding quotes removed.
3. UTF-8 URL quote with safe='/' and safe='', and quote_plus with its default safe=''.
4. UTF-8 standard and URL-safe base64, each padded and with trailing '=' removed.

| Resource | Bound |
| --- | --- |
| Distinct secrets | 64 |
| Raw secret | 4,096 code points |
| Variants | At most 10 per secret, 640 total |
| Individual representation | 49,152 code points |
| Sum of unique representation lengths | 262,144 code points |
| JSON depth | 64, root at depth 0 |
| JSON nodes | 1,000,000, including containers, values, and keys |
| Aggregate string/key text per check | 32 * 1024**2 code points |
| Prose argument | 32 * 1024**2 code points |
| Feed argument | 32 * 1024**2 code points |
| Internal stream processing slice | 65,536 code points |
| Retained raw suffix between calls | Longest current representation minus one, at most 49,151 code points |
| Total stream length | No cumulative limit |

The guard text budget is in code points; Task 2 applies its 32 MiB encoded-result byte budget. A native full TextBlock is not rejected merely for exceeding 64 Ki characters. Temporary scan/interval state is bounded by an internal slice plus the retained suffix; input/output allocation remains proportional to the caller's bounded argument. Neither guard nor stream retains complete rendered answers across calls.

No recursive encoding, JSON optional slash escaping, alternate JSON Unicode escape spelling, URL percent-case folding, arbitrary safe sets, base64 line wrapping, Unicode normalization, unknown-secret detection, or arbitrary transform detection is claimed. Exact public-data/credential coincidences favor secrecy. Very short credentials are not ignored. Unsafe marker collisions produce a typed failure only when redaction would be required, not a supposedly safe marker containing the secret.

## RED And Verification Evidence

All product tests used the mandatory offline runner:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task1-UNIQUE backend ...
```

Each named run below has its own command.json, output.log, and results.xml. Counts, failing nodes/messages, exit codes, and JUnit SHA-256 values were parsed from those artifacts into `task-1-checks.json`. The artifact-only XML census used a cleared environment and standard-library parsers; it imported no product code.

| Run | Pass | Fail | Error | Skip | Exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| task1-red-01 | 0 | 62 | 0 | 0 | 1 |
| task1-red-naive-02 | 0 | 1 | 0 | 0 | 1 |
| task1-green-attempt-03 | 62 | 0 | 0 | 0 | 0 |
| task1-review-04 | 67 | 0 | 0 | 0 | 0 |
| task1-red-aligned-bounds-05 | 0 | 3 | 0 | 0 | 1 |
| task1-green-aligned-06 | 69 | 1 | 0 | 0 | 1 |
| task1-green-07 | 70 | 0 | 0 | 0 | 0 |
| task1-red-normal-eof-08 | 0 | 0 | 1 | 0 | 4 |
| task1-red-normal-eof-09 | 1 | 3 | 0 | 0 | 1 |
| task1-green-normal-eof-10 | 72 | 0 | 0 | 0 | 0 |
| task1-inverse-known-match-11 | 0 | 1 | 0 | 0 | 1 |
| task1-restored-known-match-12 | 72 | 0 | 0 | 0 | 0 |
| task1-inverse-emit-suffix-13 | 0 | 1 | 0 | 0 | 1 |
| task1-restored-emit-suffix-14 | 72 | 0 | 0 | 0 | 0 |
| task1-inverse-share-scopes-15 | 0 | 1 | 0 | 0 | 1 |
| task1-restored-share-scopes-16 | 72 | 0 | 0 | 0 | 0 |
| task1-inverse-abort-tail-17 | 0 | 2 | 0 | 0 | 1 |
| task1-restored-abort-tail-18 | 72 | 0 | 0 | 0 | 0 |
| task1-inverse-stale-patterns-19 | 0 | 1 | 0 | 0 | 1 |
| task1-restored-stale-patterns-20 | 72 | 0 | 0 | 0 | 0 |
| task1-final-21 | 110 | 0 | 0 | 0 | 0 |
| task1-red-concurrency-22 | 0 | 2 | 0 | 0 | 1 |
| task1-green-concurrency-23 | 112 | 0 | 0 | 0 | 0 |
| task1-final-concurrency-24 | 112 | 0 | 0 | 0 | 0 |

Decisive RED nodes (all names below are in tests/test_output_boundary.py):

- `test_shared_output_boundary_exists`: named "missing shared output boundary" assertion. The initial 62 tests all failed through that owner, with no collection errors.
- `test_every_split_and_single_character_feeds_protect_encoded_secrets[raw]`: the temporary exact-only implementation leaked at split 1; one failure, no errors.
- `test_shared_json_policy_accepts_one_million_nodes`, `test_shared_text_policy_accepts_32_mib_ascii_without_reduction`, and `test_feed_accepts_full_provider_text_blocks_above_64_kib`: three value_limit failures before aligning the old tighter bounds.
- `test_normal_finish_preserves_every_unmatched_partial_prefix`, `test_normal_prose_preserves_public_word_ending_in_jwt_prefix`, and the raw-mask oracle: three failures after the coordinator corrected normal EOF semantics. The unchanged abort owner passed.
- `test_concurrent_registration_cannot_lose_secrets_or_publish_stale_matcher[registration]` and `[matcher-publication]`: both deterministically admitted a captured second secret on the unlocked core commit. The test uses event rendezvous and a forwarding real-RLock acquisition observer, not sleeps or stress loops.

Run 06's one failure was a test fixture tied to the former feed ceiling: after the ceiling changed to 32 Mi characters, it constructed a prose argument above that limit. Its split point was corrected to the actual 64 Ki internal boundary; oversize rejection tests remain. Run 08 was an editing mistake, an IndentationError while separating normal/abnormal EOF owners. It was corrected and rerun as run 09 before changing production EOF behavior. The collection error is not counted as meaningful RED evidence.

The coordinator explicitly corrected the initial spec's normal-EOF partial-prefix masking and requested aligned shared bounds and borrowed activation. The final implementation follows those corrections, rather than the older brief wording.

## Inverses And Restoration

All five inverses were temporary apply_patch edits to the owned source; each was restored with apply_patch and followed by a full 72-test primitive GREEN before the next inverse.

| Run | Deliberate inverse | Decisive owner/result |
| --- | --- | --- |
| 11 | Bypass matcher.contains in check | known_representations...[raw], 1 failure: DID NOT RAISE |
| 13 | Make feed cut=len(data), releasing its pending suffix | every_split...[raw], 1 failure: raw leak at split 1 |
| 15 | Share current scope even when inherit=False | default_scopes..., 1 failure: unrelated is parent |
| 17 | Keep abort tail and return it from finish after closure | abort_discards... and cancellation_aborts..., 2 failures: partial raw text released |
| 19 | Do not invalidate a cached matcher on add_secret | late_registration..., 1 failure: child credential released |

Mutated source SHA-256 values:

- 11: c2d6c3b6f1b4a15dbfb4a4de23640ed78a9986a1ce191ec0116d594bd6e836ef
- 13: 3517fd72b3e384fc806e73a398c8234cdc12062d387180008c9907d799afc12b
- 15: f945d1fdee8e22dcca6ec986bf100803d511aa4368622731745ac00927982a22
- 17: d679852d80220a218b8ba789f0d9d3269267610409f431c02367f31cf45381fd
- 19: fe8e72da7e4bc064e8b33b952977a3d96dec2d1e2311d443031b055dedc2d1a3

Every restoration (12/14/16/18/20) matched these exact pre-mutation hashes:

- Source: aa8f32cae417f79f26081a00d6114e1c6ab2c1eab40904295f8997354e7e174d
- Tests: 7a7109c66af7a187421cac05f5457f0e135b3cb4ecbc3d4dedfe44f1df23049b

The later required concurrency correction was independently RED against core commit 2f0cedeb, then GREEN in runs 23/24. The five earlier inverses were not rerun against the lock-only correction. Their owners and the full primitive suite remained green in the final run.

Final committed file SHA-256 values:

- Source: 409d4814e92b906039b2f74abd7b9b4314162e418cd48b43bf3e85229131af3b
- Tests: b3c4543d4da40b74df2c9b06d32f83eae5e94e3af1396142c69e628ad655685c

## Self-Review And Residuals

Self-review covered literal trie failure links and interval union, raw-offset carry state across split positions, current-pattern snapshots after registration, scope cleanup/restoration, marker edges, unsupported-object handling, serialization refusal, JSON budgets, and bounded streaming allocation. A fixed-seed independent raw-mask oracle covers 400 mixed overlapping inputs with varied chunking; this is deterministic functional coverage, not a concurrency stress run. Exhaustive per-representation split points, one-character feeds, padding/alphabet fixtures, Unicode, public data, cancellation, and interleaved generator activations are named owners.

No known failing test remains in this task's final focused checks. Independent review is still the coordinator's responsibility; no subagent or independent-review pass is claimed. Whole-backend verification, registry/adapter equivalence, producer-side event/replay/scratchpad persistence, iterator closure, and late-callback integration remain dependent-task work. The parked SEC failures were not executed, hidden, or relabeled here.

Residual limitations: captured strings remain in process memory until references are released; this is not memory encryption or guaranteed zeroization. Python/private-state introspection and arbitrary custom serializers are not a security sandbox. A captured known secret or marker-edge coincidence can reject otherwise public prose. Repeated tiny feeds rescan a bounded tail, so CPU cost grows with tail length and chunk fragmentation. Callers must distinguish true normal EOF from cancellation and must never finish/reset a stream merely to flush an intermediate delta. Guards can be shared across threads; a single stream's lifecycle operations must remain sequenced by its owner. Concurrent checks/slices linearize at their pattern snapshot, and registrations must precede provider use.

