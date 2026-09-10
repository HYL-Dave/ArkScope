# Authorized SEC Retention Manifest

Observed September 11, 2026 at 02:05:28 Asia/Taipei
(`2026-09-10T18:05:28Z`). This is the renewed, once-authorized statistics-only
read of the exact profile and market stores, not a disposal or backup approval.
The original failed attempt remains separately archived.

## Observation Boundary

The unchanged reviewed query ran for approximately 45 ms; the complete launcher
took approximately 0.26 seconds. Its two per-store read transactions are not an
atomic cross-database snapshot. Only authorized metadata, counts and reference
aggregates were returned. No body, URL, token, credential value, setting value,
symbol list or whole-row hash was queried or exported.

Both main DB files were opened `O_RDONLY` under read-only mounts. Their observed
device, inode, size and mtime were identical before/after this operation:

| File | Size Before / After |
| --- | --- |
| `profile_state.db` | 65,908,736 / 65,908,736 bytes |
| `market_data.db` | 3,828,281,344 / 3,828,281,344 bytes |

These metadata observations are not whole-file byte hashes or a reconstruction
of the earlier third-party probe. No production whole-file copy/hash was made.
The payload-free trace shows both attempted exclusive main-file locks on close
failing with `EBADF`, consistent with their read-only descriptors. No main-file
write or checkpoint was observed. SQLite created/opened the four real sidecars
and initialized the two SHM files: two `ftruncate` calls, sixteen one-byte
`pwrite64` calls and two 32 KiB shared writable SHM mappings. No WAL frame writes
or sidecar unlink/rename occurred in this invocation. Namespace setup writes to
the caller's `/proc` UID/GID maps and pipe/stdout writes are distinct from data
file mutations. Shared memory stores are not individually traceable by strace.

The real parent directory allowed new names; enumerated existing non-sidecar
entries were read-only. This was a fixed reviewed query, not an arbitrary-code
sandbox with an exact-filename kernel allowlist. See the boundary review for
this limitation and the pre-read hardlink/bytecode fixes.

## Measured Data

| Group | Observation | Retention Meaning |
| --- | --- | --- |
| Market original intake | 36 observations, 37 kind rows | The two counts represent different entities; do not treat 37 as observation count |
| SEC observation/case tuple comparison | 36 matched; 0 observation-only; 0 case-only | No unmatched `(source, source_ref, ticker)` in this read; not a claim of one case per ticker |
| Profile cases | 39 total: 36 SEC, 3 listing-authority, 0 target-investigation source | Shared table still carries current provider decisions |
| SEC cases with dependent assessments | 14 cases | Legacy is not equivalent to empty/unreferenced |
| SEC cases with identity transitions | 0 cases | Does not prove all application-level references are absent |
| Assessments | 17 total; 9 accepted; 3 human-authority | Counts overlap; this query does not partition accepted/human rows by source |
| Dependent assessment material | 17 outcomes, 250 evidence links, 10 proposals | Preserve through an explicitly defined retained-reference projection |
| Evidence / automation | 1,025 evidence rows; 76 runs; 503 facts; 91 blockers | Shared/current dependencies must be separated before any table removal |
| Historical evidence translations | 4 rows, all four composite evidence/digest references matched | Existing API JOIN still reads them; no permission to delete translation history follows from removed LLM execution |
| Old `lifecycle_web_*` journal | All seven named tables absent | No stored old-web journal to migrate in this observed installation; not seven empty tables |
| Current investigation | Installation marker 1; jobs/calls/steps/sources/results/acceptances/runtime 0 | Current feature/schema remains supported; empty state is not abandoned capability |
| Provider / identity history | 3 provider checks; 3 transitions; 3 attempts; 3 activity rows; 0 alias links | Preserve current decisions and reversal/history dependencies |
| Former memberships | 105 memberships, 105 bindings, 108 events; 3 removed memberships | Preserve removal intent; synchronization must not revive it |
| Legacy source settings | Both exact schedule keys have count 0 | No setting values read; no keys need deletion in this observation |
| Legacy runtime history | Exact scheduler-state source 1; exact job name 1 | Only these source-specific rows are potential later cleanup targets |
| Receipts | Legacy migration receipt 1; disposal-receipt table absent | Keep actual applied-history evidence; absence is not deletion permission |

Profile: 29 named tables observed, 8 absent. Market: both named tables observed.
All 32 inspected declared-FK groups were measurable and had zero orphan rows;
no inspected group had an external child. This is **not** a whole-database
integrity check or proof that undeclared/application-level dependencies do not
exist. Nullable evidence references remain distinct from orphans.

The raw `old_web_unfinished` and `sec_cases_with_old_web_runs` classifiers report
`unavailable/schema_columns_missing`, not zero. The structural table inventory
explains why: `lifecycle_web_runs` is absent. No unavailable classifier was
rewritten into a successful zero result.

## Next Cleanup Boundary

1. Remove remaining old-only source helpers after moving genuinely current
   confirmation, source-reading and error/validation ownership. The absent
   old-web schema removes a presumed historical-data migration requirement for
   this installation; it does not make shared functions dead.
2. Define one current schema and a precise retained-row/reference projection.
   Preserve current listing decisions, accepted history, provider evidence,
   translations, membership removals, receipts and unrelated prices/news/SA.
   The current aggregate read alone cannot decide the fate of all 36 SEC cases.
3. Test conversion on fresh and populated synthetic stores, including retained
   history, refusal on unexpected dependencies, interruption and unrelated-data
   equality. The new SEC research service remains separate from old intake.
4. Before touching production data, present exact scoped disposition and backup
   requirements for authorization. This read did not authorize broad snapshots,
   body/credential copying, schema mutation, DROP or deletion.

## Reviewer Claim Corrections

The third-party probe's reported file growth is not independently reproduced.
Concurrent activity prevents attributing that change to a read-only connection;
there is also no before/after logical snapshot supporting its assertion that
all rows/settings stayed unchanged. Two synthetic controls and the present
trace show read-only access without a main-file checkpoint. The SQLite
[read-only open contract](https://www.sqlite.org/c3ref/open.html) and
[3.37.2 close implementation](https://raw.githubusercontent.com/sqlite/sqlite/version-3.37.2/src/wal.c)
support distinguishing read-only descriptors from generic checkpoint-on-close
documentation, not diagnosing the earlier process after the fact.

The third party additionally reports a full 7,972-passed/12-skipped backend run.
That is external corroboration, not a new run performed here. Our 7,971 checkpoint
is `0c5896a5`, not `302106d2`; the following facade owner adds one node. The nine
translation SQL census candidates originate in an incomplete synthetic union
schema, not a general inability to understand `SELECT t.*`. Original test and
census artifacts remain unchanged.

## Evidence Identities

- Query: `f851057861c55980d4aeb114a8cf230ca7203ad1f3f2d86ca905004f833627c5`
- Caller: `8e11b37f1dd7d2d46242c3c5ef27ca93e1262eba8c2c1496299394f2fcbf7a90`
- Dispatcher: `7265952d8881106d03daae7f65ba667237ac2a2f7321b67eb25a4ec4d9f5b722`
- Result: `e44cec4f6ba8fa2ab45dfc8d74083886835324c84e83feccb7582e440479baf8`
- Uncompressed trace: `fa54782fd24a136964ea4557cc811df60a5dd4cb02b5924c0bba8447cf140391`

No provider calls, production logical writes, App restart, merge or push.
