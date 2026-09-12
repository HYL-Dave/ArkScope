# Security Hardening Review: Research Output Boundaries

## Evidence Basis

I inspected the four Research adapters, the diagnostic scrubber, runtime error
handling, SEC value/cursor contracts and existing regression owners. The fresh
offline adapter reproduction has four passes and four failures, all failures in
OAuth. Exact-function probes also corrupt the ordinary word `Consolidated` and
show that independent fragment replacement is not a streaming secret guarantee.
No live credential or production disclosure was observed or tested. Separately,
35 existing probe and API-key error-protection cases pass; they remain required
positive controls, not evidence that the proposed replacement exists.

[Source identities and observations](observations.json) distinguish the dirty
worktree from its HEAD. This is a derived proposal, not an implemented fix.

## Constraints

We must preserve useful research data, exact citations, selected credentials,
four-channel behavior and existing diagnostic protections. No blanket regex
relaxation, credential-store enumeration, extra provider calls, production-data
changes or new service/process is proposed. The unfinished SEC release stays
blocked until its real adapter tests pass. Existing data is not disposable.

## Opportunity Portfolio

| Opportunity | Evidence | Options | Recommendation | Proposal |
| --- | --- | --- | --- | --- |
| Own output policy by data type and destination | OAuth/API serializer differences, SEC cursor failures, prose and fragment probes | 1. SEC-local exception; 2. Shared contextual output boundary | Option 2 | [Technical proposal](proposals/contextual-output-policy.md) |

## Recommendation Summary

I recommend Option 2 under the user's preference for a root-level correction.
We should keep the lossy diagnostic scrubber for diagnostics, and stop using it
as the definition of safe research content. A common boundary should validate
tool results, inspect the execution's known secrets, preserve public data, and
separately produce diagnostic summaries. Answers and streaming events need the
same secret policy, with state across fragment boundaries.

This is more work than the SEC-only repair: we must inventory result producers,
schemas and persistence paths, not add another special case. It also avoids
pretending that a regex can distinguish every unknown secret from a public hash.
The residual limit remains explicit: arbitrary unknown or deliberately encoded
secrets cannot be ruled out from shape alone. Credential isolation is the primary
control, not an assurance supplied by string matching.

## Next Decisions

Approve or revise Option 2's principle: ordinary public research values and prose
will no longer be altered solely because they are long, numeric or token-shaped.
Known execution credentials, credential-bearing fields and diagnostic errors
remain protected; malformed structured results are rejected rather than repaired
with altered identifiers. This changes shared behavior and requires explicit
approval before an implementation plan or source change.

The recommendation is not approval to merge, restart, query real stores or perform
maintenance. Citation persistence, export/restore, recovery and scheduling remain
unfinished SEC work after this boundary is resolved.
