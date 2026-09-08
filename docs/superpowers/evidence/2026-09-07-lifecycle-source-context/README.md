# Source Compatibility, Capacity And Traceable Model Input

## Authority

The September 7 user distinguishes complete retrieval from LLM input, accepts
ordinary-PC storage/RAM costs, permits justified larger reading limits and asks
for implementation. This packet is provider-free. It does not renew either
consumed Claude canary, read credentials/production data, install the journal,
restart the App, commit, merge or push. Prior sealed attempts remain unchanged.

Worktree: `/tmp/arkscope-lifecycle-terminal-membership`, branch
`codex/lifecycle-tracking-first`, base `0b66732ba4a77c4ba823537001828c1a75563c5d`.
The cumulative worktree includes earlier unfinished lifecycle work. This packet's
incremental source/test changes are enumerated against the sealed Sonnet canary,
not claimed to be the entire branch diff. Model provenance, zero fallback,
exact source binding and human action confirmation remain separate gates.

## Implemented Contract

- Preflight changes from 2 MiB to **16 MiB encoded HTTP body / 32 MiB decoded
  document per source**. Identity-encoded responses remain bounded by both.
  Defaults and an optional per-run decoded limit are digest-bound; old option
  records without it retain their original cap. No Settings/environment field
  or DDL change is introduced in this continuation.
- Request count, four-source count, redirect count, reader deadline, model
  deadline and model-output settings are not raised. Body-byte observations
  exclude headers, chunk framing, TCP and TLS overhead, and are not token counts.
- Real stdlib HTTP parsing owns fixed-length, chunked and EOF bodies, identical
  repeated Content-Length and chunked whitespace. Conflicting framing, actual
  short bodies, unsupported encoding and size exhaustion remain distinct errors.
  Streaming gzip verifies bounded expansion, completion/CRC and every member.
  No over-limit prefix becomes successful evidence.
  Completion here describes the received HTTP message/decoded stream, not a
  guarantee that the publisher's notice is factually complete or correct.
- Strict JSON keeps its representations. XML uses a DTD/entity-disabled
  `defusedxml==0.7.1` parser and standard streaming canonical writer, preserving
  namespaces, fields, security-record boundaries and mixed-content whitespace.
  There is no new DOM dependency, CLI or OS-specific runtime requirement. Windows
  and macOS packaging are not live-tested by this Linux-only packet.
- Complete **readable/extracted source text** and source/entity digests remain
  in the immutable journal. This is not a byte-for-byte HTML/compressed archive.
  Existing 16,000-character evidence/translation and cited-passage limits remain
  domain contracts, not model capabilities; they are not blanket-raised.
- Prose selection keeps every recognized identity/lifecycle/date/negation match
  with two neighboring units and document boundaries. No top-K or first-N clip
  is introduced. Unknown relevance, dense relevance, JSON and XML remain full
  inputs. The selector is heuristic, not proof that all semantic contradictions
  were discovered. Large/dense inputs may still exceed native model context.
- Every supplied range is bound to retained UTF-8 source bytes. The journal
  stores the range manifest; a quote must both match original retained text and
  have actually been supplied to analysis. UI/Research receive closed aggregate
  coverage, not internal IDs/digests/ranges. The UI says when analysis used
  selected passages instead of implying the model read everything.
- Metadata JSON alone cannot support a listing-action fact. A newly automated
  SEC primary-document/history/index resolver is not implemented here; it would
  need separate request planning and owners. Existing Submissions use and the
  primary Massive/EODHD authority are unchanged. Form 25's security-class scope
  is not converted into an issuer-wide delisting fact.
  This Web supplement currently admits JSON as locator/identity input only;
  it does not restrict the separate structured Massive/EODHD decision path.
- Every measured request can retain a closed status/framing/encoding/body-byte
  receipt even when the run fails. No arbitrary headers, cookies, token or URL
  appears in that diagnostic DTO. UI uses collapsed details; Research shares the
  same projection. Legacy absent receipts remain unknown; malformed present
  receipts are rejected. Unknown model usage is not fabricated as zero.
- A failed diagnostic receipt is **not** a successful finding. Population
  retention now explicitly admits failed-run receipts while adoption still
  requires a succeeded finding. This changes a result-JSON contract without DDL;
  old binaries are not assumed rollback-compatible with new failed-result rows.

## Capacity Measurement

`measure_capacity.py` uses fake pinned connections, synthetic public text and
automatically removed temporary journals. It never resolves a host, opens a
provider connection or reads production state. The final run includes real
decoding, four-page persistence, source selection, terminal completion,
validated readback and UI/Research projection in each of two concurrent workers.

| Quantity | Final observed value |
| --- | --- |
| Per document encoded / decoded | 36,566 / 33,552,350 bytes |
| Retained text per worker, four sources | 134,158,984 UTF-8 bytes |
| Selected text per worker | 192,796 UTF-8 bytes |
| Serialized source portion of model input | 577,452 bytes |
| Per-worker temporary SQLite file | 402,903,040 bytes, about 384 MiB |
| Whole process peak RSS | 1,530,957,824 bytes, about 1.43 GiB |
| Peak before workers / additional growth | 950,730,752 / 580,227,072 bytes |
| Source-reading time per worker | 4.511 / 6.490 seconds |
| Entire benchmark elapsed time | 49.183 seconds |

The large fixture uses supplementary four-byte Unicode, exercising Python/JSON
serialization expansion. Its baseline peak includes fixture construction and
imports; the RSS is not claimed to be source-reader-only usage or all-App memory.
Selected-text/serialized-byte counts are **not** tokenizer measurements or a
promise that every real filing reduces by this ratio. The 45-second source
deadline is not replaced with the complete benchmark's elapsed time.

Earlier `capacity-2mib.json` and `capacity-32mib.json` cover saving/reading/selecting
but not terminal completion and final projection. `capacity-32mib-terminal.json`
adds those steps (about 1.40 GiB). The final repeated measurement uses the final
source. An initial enhanced benchmark omitted a dispatch identity binding and
stopped before source reads; that harness was corrected, not a product guard.

This supports the bounded default on an ordinary-PC resource scale. It is not
an all-machine certification, a maximum for every adversarial parser shape, or
permission to allocate unlimited memory. No runtime silently drops text to meet
these resource or native provider limits.

## RED And Regression Record

The `red-*` artifacts are actual pre-fix test output, not reconstructed after
implementation. Transport, model-context binding, capacity/projection, failure
receipts, population adoption, UI diagnostics and legacy preflight parsing have
separate rejecting and positive controls. In the first context RED run, four
tamper tests initially hit the immutable database trigger before their intended
read guard. The test now removes/restores that exact trigger only in its private
fault-injection store, and the independent null-context mutant proves the
intended reader guard is owned. Those four initial failures are not misreported
as initial proof of the reader guard.

The initial XML flattening formatter expanded 20,468 input bytes into 2,120,086
bytes by repeating a long parent field name. `red-xml-expansion.xml` records that
failure and the loss of parseable record structure. The standard canonical writer
replaces it; controls retain all attributes, distinct notes/common-stock records
and mixed text `Before not delisted.` without such expansion. The mixed-content
mutation must fail its named owner.

The first complete frontend baseline caught three failures: one visible `HTTP`
label bypassed the locale resource, and two exact inventories had not counted
the added keys. The label and both inventories were fixed; global scanning and
exact bilingual key counts remain enforced. Backend campaign r1 passed its
focus/mutations/integration but was deliberately interrupted during the full
suite for the XML correction. It is retained as incomplete, not mixed with r2.

Final campaigns apply each independent mutation to a private source copy and run
the **whole** 1,998-test affected backend focus or whole 1,552-test frontend suite.
They require the same node set, named owner failure, zero test errors and exact
restored file hashes. The 1,200-second full-suite harness timeout is not a product
timeout. Existing temporary-database fixtures isolate the full backend suite.

| Final gate | Observed result |
| --- | --- |
| Restored affected backend focus | 1,998 passed |
| Integration | 2,817 passed |
| Complete backend | 6,663 passed, 12 skipped, three existing warnings |
| Independent backend mutants | 14/14 killed by named owners |
| Complete restored frontend | 1,552 passed |
| Independent frontend mutants | 3/3 killed by named owners |
| Browser cases / screenshots | 12 / 24 |

The backend warnings remain the existing edgartools deprecations. The frontend
build succeeds with the existing large-chunk warning, not a build failure.

There is one intentional parameter-name replacement: unsupported gzip becomes
supported gzip with malformed bytes still rejected as `source_compression_invalid`.
The exact node ledger distinguishes that replacement from genuinely added tests;
no assertion is dropped to hide a failure. Full results and source hashes are
published by `seal.py` only after all campaigns complete.

The browser matrix is two locales by desktop/390px/320px by selected-input or
failed-read state, with closed/expanded details: 12 cases and 24 screenshots.
Mocked API routes assert zero unexpected requests and zero write/model commands;
source hashes, nonblank pixels and geometry are checked. The first browser fixture
had two completed receipts mixed into its all-source-failure state; it was corrected
to one HTTP rejection plus three short bodies before final screenshot admission.
These screenshots are not a production App restart or a live canary.

## Remaining Boundaries

The original failed live run is not resumed or rewritten. Framing/compression
compatibility is now exercised offline, but unavailable/forbidden pages may
remain unavailable and source-selection/model-output quality still needs a fresh
authorized canary. No extra model or source request was made in this continuation.

Claude top-level versus per-model aggregate token semantics remain uncalibrated;
source receipts do not fix that separate counter. The dedicated SEC resolver,
production journal installation/population cutover, merge/restart and final hand
testing retain their separate work/approval boundaries. This packet does not
claim the whole lifecycle redesign is ready for final hand testing.
