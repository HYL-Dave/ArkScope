# Shared Fourteen-Day News Target

## Delivered

Source commit: `8b468771823f3d47d8298ab5a6ec0f7a403c6642`, based on `4b3f848b`,
on `codex/sec-research-integration`.

The review suggestion was verified against the actual consumers: three separate
seven-day defaults existed. They now consult one
`src/news_collection_policy.py::INITIAL_NEWS_LOOKBACK` at request construction.
The five exercised adapters are direct Massive/Finnhub, normalized
Massive/Finnhub, and strict IBKR. No shared date parser, new provider framework,
credential lookup, schema change or write-policy change was introduced.

Saved cursors remain inclusive and are not clamped to fourteen days. New tickers
and sources initialize independently. Direct/normalized writer deduplication is
retained. Strict IBKR still yields observed headlines and then reports incomplete
or unknown coverage when appropriate; a saturated seven-day page cannot prove
the fourteen-day request complete. Its non-strict fallback remains source-owned.

## Fresh Verification

| Check | Observed result |
| --- | --- |
| Behavioral RED | Five failures, all actual request starts September 7 instead of August 31; no collection/import failure |
| Same five cases after implementation | Five passed |
| Focused adapter/writer/worker/scheduler/CLI controls | 304 passed |
| Single full backend run | **11,114 passed / 12 skipped**, no failures/errors; 1,416.431 seconds including launcher overhead |
| Exact node reconciliation | 11,126 collected = 11,126 executed; +48 new cases / zero removed; all 12 skip identities unchanged |
| Source/runtime/runner freeze | 1,159 source paths, packages, SDK hooks and runners unchanged before/after |
| Independent static review | No findings; no tests or edits by the reviewer |

The source collection SHA-256 is
`d808b2b38b6ffb5d6d676066a8445ca8e44333e097c0c19b90180f6637f4ccc9`.
`checks/news-validation.json` includes exact identities, retained safety-owner
results, before/after references and baseline JUnit hash. The prior baseline is
the September 14 cleanup closeout's 11,066 passed / 12 skipped run.

The reviewer was closed before the full backend run. During that run the
controller only waited and read its output log; no concurrent pytest, census,
source editing or agent work took place. Tests used the retained offline launcher
with a closed environment, fake providers and disposable databases. The launcher
is not the deferred product Python sandbox. No new frontend verification is
claimed: frontend source did not change in this slice.

The shared-authority guard changes the single value to three days after adapter
construction and verifies each actual request moves with it. Other new cases
cover malformed/missing and saved recent/older/date-only cursors, exact normalized
Massive timestamps, independent source/ticker initialization, deduplication,
unknown/incomplete IBKR responses and an empty entitled-provider set.

## Census

The same scanner compared this committed source with the preceding closeout's
`checks/census-current/census.json.gz`: 1,175 files read, 4,306 candidates and
3,283 uncertainties. No new candidates, uncertainties, coverage reductions,
dependency changes or untracked-name drift; comparison `review_required=false`,
exit 0. Existing unresolved findings are not thereby closed. The shared module
has live consumers, not a temporarily unwired foundation.

The retained `run_census.py` was invoked after full backend completion, with
`--root .`, `--untracked-root /mnt/md0/PycharmProjects/ArkScope`,
`--compare docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/checks/census-current/census.json.gz`
and output `.superpowers/sdd/2026-09-14-runtime-cleanup-closeout/news-census.json.gz`.
Its environment was closed; PATH supplied the existing Python, Node 22.14.0 and
system commands, HOME was the disposable news-collection home. The main
worktree's untracked names were enumerated, not their private file contents.

## Remaining Boundaries

This closes the shared request-target implementation, **not the entire recent
collection policy**. Known account-limit discovery/reporting, a shorter effective
REST window and durable initial-interval retry handling remain open. No actual
account entitlement or fourteen-day data completeness was measured.

C12 old collector/CLI removal, remaining C15/C20 cleanup, Linux runtime
installation/activation and SA Open-first targeting are not delivered here.
SQLite is still 3.37.2. No production database/configuration read or write,
provider/LLM call, App stop/restart, runtime install, merge or push occurred.
Before evidence publication, master remained an ancestor, `0 / 159` unique
commits. This is not the final hand-test handoff for the larger cleanup/runtime
workstream.

## Artifacts

`checks/manifest.json` seals 26 selected files, 1,362,154 bytes, including RED
and GREEN records, complete JUnit output, source snapshots and review. Every
published artifact was read back. Fixture databases, disposable homes and build
outputs are excluded. Runners are provenance copies: their executable working
location is `.superpowers/sdd/2026-09-14-runtime-cleanup-closeout/`, not this archive.

Only manifest-listed, hash-verified log files are force-added when the repository
ignore rules exclude them. Git-blob readback is the final publication check.
