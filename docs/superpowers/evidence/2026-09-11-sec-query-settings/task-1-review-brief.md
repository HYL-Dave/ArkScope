# Independent Task 1 Review

Worktree /tmp/arkscope-listing-sec-macro-convergence.
Use superpowers:requesting-code-review/task reviewer discipline. Read only
task-1-brief.md, task-1-report.md, approved plan globals/Task1 and
task-1-diff.txt here. Base0658ebf0 -> e207b3ad; diff is frozen authoritative input.
Do not edit product/test files, index, git state or spawn any agents. Other work
is in progress in disjoint frontend files; do not include it in this review.

Review spec compliance and implementation quality independently. Read diff once;
outside reads only for a named concrete risk, record why and checked path.
Do not re-run whole suites; a focused disposable probe is allowed for a specific
unanswered doubt, only through this plan's offline harness with unique paths.
Never open actual stores/config/token files or use provider network.

Load-bearing checks: receipt snapshot/locator/issuer/time binding, restart/resume
and failure authority, cursor filter/snapshot/receipt consistency across refresh,
schema immutability, shared sqlite_sequence ownership, filter-before-limit and
aggregate memory admission, no incomplete->empty lies, whole-envelope bound,
conflicting repeated filing metadata, no accidentally removed current caller.
Characterization tests for existing invariants are allowed initially green if the
explicit inverse mutation proves the owner; don't pretend those are new fixes.

Report to task-1-review.md with Spec Compliance, Quality, Critical/Important/Minor
findings with file:line and concrete failure/risk, evidence checked, unanswered
items. Read claimed raw evidence as needed, don't trust report or create a new
full suite. Existing baseline test debug/deprecation noise should be identified
as such, not conflated with newly introduced failures.
