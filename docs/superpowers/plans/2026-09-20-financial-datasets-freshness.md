# Explicit Financial Datasets Freshness

Status: implemented, offline-verified at `bd316536` and merged into local master.
Full backend: **11,796 passed / 12 unchanged skips**. Frontend, channel checks
and the existing default-worker timing limitation are recorded in the
[acceptance evidence](../evidence/2026-09-20-quote-financial-freshness/README.md).
This follows the user's explicit correction to the previous cache-first policy.
No production cache is deleted and no paid request policy is activated.

## Retrieval Choices

The client exposes `freshness` / `max_age_seconds`. The existing fundamentals
tool exposes these as `fd_freshness` / `fd_max_age_seconds`, across all four
research transports. They apply **only to the FD fallback**. They do not change
the legacy SEC source precedence, its cache or its automatic fetch behavior.
The three dedicated SEC research tools retain their separate `stored` defaults.

| Mode | Saved data | Network |
|---|---|---|
| `refresh` (default) | Not consulted; failure never silently reuses old data | Requires the existing trusted paid policy |
| `stored` | Explicitly read saved, verifiable observations; optional maximum age | Never; also no cache promotion |
| `auto` | Reuse only within an explicitly supplied nonnegative integer maximum age | A miss still requires the separate trusted paid policy |

An absent paid policy now produces a refusal by default, even when saved data
exists. It is not a spending grant and is not implicit consent to reuse a cache.
No maximum age is guessed from a quarterly/annual period or account balance.
Invalid boolean/string ages are refused before data access in every transport;
the API-key SDK may not coerce them into an accepted integer.

Examples of tool arguments (not spending approvals):

```json
{"ticker":"AAPL","period":"quarterly","fd_freshness":"stored"}
```

```json
{"ticker":"AAPL","period":"quarterly","fd_freshness":"auto","fd_max_age_seconds":604800}
```

The second example tolerates a seven-day-old acquisition; it does not assert
that seven days is appropriate for every user or that no new filing exists.
The default quote tolerance is separately measured in seconds, not fiscal periods.

## Evidence And Storage

- Each successful FD statement read adds `source_observations`: provider,
  dataset, retrieval/freshness mode, original `fetched_at`, `evaluated_at`, age,
  selected maximum, `within_max_age` and returned `report_periods`.
  `latest_period_verified=false`: a recently fetched response can still contain
  older periods or omit data outside this account's coverage.
- Existing annual/quarterly cache-day configuration remains storage/legacy-expiry
  metadata, not read freshness. The new metadata reader can reopen expired
  rows without changing the old TTL-aware getter used by other paths.
- New keys include request limit, and saved responses retain that query envelope.
  Old limit-free entries are usable only when they demonstrably contain at least
  the requested number of matching-period/ticker rows. Missing, future, naive or
  invalid acquisition times cannot substantiate an aged read. A cache miss is
  not evidence that financial statements do not exist.
- File-to-DB promotion is allowed only in `auto`, preserving both original
  timestamps exactly as instants. `stored` neither promotes nor renews TTL.
  A failed backend save still retains a file copy of paid data for later explicit
  reuse; source bytes are not discarded just because refresh is the default.
- Stored reads report individual missing datasets while retaining other saved
  statements. Paid failures still stop fan-out; they do not retry, silently
  choose a paid source, or refund an uncertain request reservation.
- Native API-key wrappers now forward `period`, previously exposed only by the
  registry. Quarter-specific four-channel fixtures verify actual statement
  metadata, not just a schema declaration.

## Verification And Limits

Owners: `test_financial_datasets_freshness.py`, `test_freshness_tool_channels.py`,
the prior FD client/governance/cache tests and the full backend suite. Missing-key
errors are typed refusals instead of success-shaped empty data. Existing cache
tests explicitly request their intended retrieval mode; none are deleted.

This does not repair D/E numerators, financial period comparability, earnings
event alignment, native synchronous-tool cancellation, external authorization,
provider selection UI or unattended scheduling. Do not present the legacy
fundamentals report as fully accepted because its retrieval age is now visible.
