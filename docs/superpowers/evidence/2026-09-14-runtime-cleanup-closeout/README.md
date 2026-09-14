# September 14 Cleanup Closeout

## Scope And Status

User direction: finish SQLite deployment and remaining cleanup before asking for
hand testing; defer cross-platform implementation. This batch closes two bounded
cleanup findings and removes two obsolete C15 leaves. **It does not complete the
whole cleanup program or deploy SQLite.**

| Work | Result |
| --- | --- |
| C15 leaf removal | `c4cb7109`: physically removed `massive_config_migration.py` and the V1-only `security_lifecycle_retirement.py`. No forwarding aliases. |
| CENSUS-I18N-001 original queue | `4d121b17`: all original 100 candidates classified; 82 obsolete leaves removed, 18 shared labels retained. |
| CENSUS-SQL-001 original JOIN gap | `eed65fb8`: retained translation table and all eight columns now have the actual `list_evidence` read witness. No production schema changes. |
| SQLite | Still linked to 3.37.2. Earlier 3.53.4 candidate evidence is not a deployment. Runtime choice and the attended operational window remain pending. |
| C12 | Both current news factories still depend on old modules' fetch/parse code. Routine collection has a current entrypoint; custom-date/full-history CLI parity does not. Capability choice requested; nothing deleted here. |
| Remaining C15 | Five mixed conversion/backup/receipt-replay modules still require ownership separation. Current installation, disposal and backup contracts are not removed merely because of their filenames. |
| C20 | No fresh retained-row inventory or `agent_queries` disposition in this batch. Unknown is not zero. |
| Cross-platform | Deferred. Python sandbox and packaged runtime work are not just Windows/macOS testing. |

The branch remains `codex/sec-research-integration`. Before evidence publication,
master was an ancestor with `0 / 155` unique commits. No merge conflict resolution
was needed, and no master merge or push was performed.

## Fresh Acceptance

The source anchor is `eed65fb806234ca779922abdaa6e526727d57e3b`. All 1,157 frozen
source paths, runtime/package identities and runners match before/after:
`d7ec1a4b98051b0d73231977149bc134091938baacd52a0f704513719ae45291`.

| Check | Result |
| --- | --- |
| Single full backend, `pytest -q tests` through the retained offline launcher | **11,066 passed / 12 skipped**, zero failure/error; 1,388.227 seconds including launcher overhead |
| Exact node reconciliation | 11,078 collected = 11,078 executed, no duplicate nodes; all 12 skip identities unchanged |
| Backend delta from prior accepted run | +26 / -10 = net +16: 24 scanner regressions + 2 physical-absence cases; only 6 obsolete converter and 4 obsolete Tavily cases removed |
| Current config/schema/retirement/provider controls | 189 passed; the two current Massive authority/startup-preservation tests remain unchanged |
| Scanner tests | 59 passed |
| Full frontend | **1,835 passed**, 126 files; +2 locale guards from the prior 1,833 |
| Type checking / build / visible-literal scanner | Passed; existing Vite large-chunk warning retained, not suppressed |
| Source/reference scan | Deleted module names occur only in their physical-absence guards on current code/doc surfaces |

The controller scheduled no other pytest, census or agent work during the full
backend session. Only its own output log was read for progress. Tests used disposable stores, a closed
environment and the preceding reviewed offline launcher; no partitioned results
were substituted for the full run. The launcher is not a product Python sandbox.

## RED And Review Evidence

- C15: two expected absence failures before deleting the modules; 189 controls
  pass afterward. Removed tests exclusively owned the deleted APIs, not the
  current config namespace or preservation-on-startup behavior.
- i18n: two expected locale failures before deleting 41 leaves per locale.
  The first focused green attempt exposed a missed second namespace/total count;
  both count assertions were updated to the exact 41-leaf decrease. That failed
  run is retained. Final focused 192 tests and full frontend pass.
- SQL: three initial failures reproduced the synthetic and actual JOIN omission.
  The first implementation still lost the actual schema because it treated all
  later enum rebindings as ambiguity. Assignment-time snapshots corrected this;
  a regression verifies that old DDL never receives a later enum's values.
- Review found pattern/exception captures and same-assignment walrus rebinding.
  Five new cases failed against the reviewed version; all pass after invalidating
  these bindings/rejecting intra-assignment `NamedExpr`. Conditional helper and
  builtin redefinitions also have RED/green controls. The review is preserved.

The SQL resolver interprets no product code. It recognizes one exact pure
quoted-enum helper idiom and immutable values in eager module assignments.
Function/class/lazy scopes, unknown expressions and unsupported Python behavior
remain outside that subset. This is static syntax evidence, not a complete
runtime data-flow proof or database ownership authority.

## Census Attribution

The scanner changed, so a new-scanner run against unchanged baseline source was
captured before comparing the cleaned tree. The source-only baseline runner's
`--current-scanner-on-revision` option is explicit in its receipt.

| Comparison | Attribution |
| --- | --- |
| Old scanner vs new scanner on baseline source | 13 candidates removed, 2 newly visible column candidates, 1 newly typed SQL prepare gap; zero source coverage reductions |
| Same new scanner, baseline vs cleaned source | 84 candidates removed: 82 locale leaves + 2 deleted Python modules. One new candidate: `data_provider_config.updated_at`, whose obsolete converter reader was removed. No new uncertainty, dependency metadata or untracked-name drift. |
| Current complete census | 4,306 candidates, 3,283 uncertainties, 1,173 files read; three coverage reductions exactly match the two product modules and their Tavily test file |

The newly visible `ticker_identity_transition_attempts.trigger` and
`observed_preview_sha256` columns remain in the canonical transition-attempt
schema and writers; dynamic whole-table/retention reads are not inferred absent.
The new `portfolio_activity.py` prepare gap is a resolved CTE fragment, not a new
product query failure. `data_provider_config.updated_at` remains in the current
configuration schema/write contract. None of these observations authorizes DROP
or timestamp removal. **The census continues to return review_required (exit 2).**

`checks/census-attribution.json` enumerates all original 100 i18n dispositions.
The 18 retained labels (nine per locale) have these consumers:

| Keys under `explore.lifecycle` | Consumer |
| --- | --- |
| `current.checkPrompt`, `current.checkIncomplete` | `currentReviewCopy` -> `InvestigationView` |
| `fields.successorTicker`, `fields.effectiveDate` | `lifecycleAutomationNarrative` |
| `listingEvidence.authorities.{eodhd,nasdaqTrader,massive}` | listing-authority/operator-detail presenters |
| `translation.providers.{anthropic,openai}` | `TrackingDecision` model/provider attribution |

Current SEC/Research additions and other unresolved i18n/CSS/SQL candidates are
not included in this original 100-item closure. Broad cleanup remains open.

## Next Decisions And Boundaries

Proposed Linux SQLite deployment: a versioned app-private runtime under
`~/.local/share/arkscope/runtimes/`, unchanged Python/numpy/system SQLite, and one
verified engine used by Desktop, SA native host and normal writer subprocesses.
This proposal has not been installed or selected. The existing
[admission preflight](../2026-09-13-maintenance-closures/checks/sqlite-admission-preflight.md)
still requires compile-profile/relocation acceptance, entry/child identity tests,
then an attended stopped-writer backup/integrity/switch window. The sanitized,
internal analysis child is a separately scoped exception, not silently widened.

C12 needs an explicit choice: retire old custom-date/full-history/resume/estimate
CLI operations while keeping current incremental collection, or implement the
required historical acquisition in the current owner first. Already collected
files and databases are retained either way. The source-only inventory is in
`checks/c12-inventory.md`; it did not run collectors or inspect credentials.

The repository already has a
[sandbox design](../../specs/2026-09-03-packaged-cross-platform-python-sandbox-design.md)
and plan, but its implementation is gated/unimplemented. `code_executor.py` is
an internal subprocess helper, not OS isolation, and is not an agent tool.
Packaged Python, the broker and renderer/worker isolation are implementation
work in addition to platform tests. User deferred that scope; nothing was enabled.

No production database/credential read, WAL/SHM coordination, row/schema/key
mutation, provider/LLM call, package install, runtime activation, App stop/restart,
master merge or push occurred. This batch is not the requested final hand-test
handoff: SQLite and the remaining cleanup must be handled first.

## Artifacts

`checks/manifest.json` seals 67 selected files (2,207,965 bytes), including both
successful and failed attempts. Source/runtime snapshots and JUnit reconciliation
are in `checks/validation.json`. Temporary database fixtures, isolated homes and
build outputs are deliberately excluded. Retained runners are provenance copies;
their working-directory convention is `.superpowers/sdd/<batch>/`, not execution
from the evidence archive. All published bytes were read back and checked.

Git-blob readback caught 20 `output.log.gz` artifacts excluded by the repository's
`*.log.*` ignore rule in the initial evidence commit. Only those manifest-listed,
hash-verified logs were explicitly added; no ignore rule or source file changed.
