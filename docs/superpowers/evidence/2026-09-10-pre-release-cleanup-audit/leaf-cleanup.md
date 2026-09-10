# First Abandoned-Leaf Cleanup

Scope: `54dd05a9..263c21a5` on `codex/listing-sec-macro-convergence`.
Status: first cleanup batch complete; independent code review found no issues.
Full-selection results and targeted follow-up are distinguished below.
No merge, push, App restart, provider calls, real credentials, production DB access,
DB DDL or stored-data changes. The wider cleanup and new SEC research service are
not completed by this batch.

## Changes And Test Ledger

| Commit | Removed product surface | Retained live owners | Test delta |
| --- | --- | --- | --- |
| `300b7400` | C02 `data_sources/sec_filings.py`; C18 `data_sources/sec_earnings_releases.py`; C17 `src/security_lifecycle_news_evidence.py`; C19 `src/news_identity_repair.py` (four files, 1,338 lines) | EDGAR source, financials, insider trades and shared transport; `LocalNews` investigation; `news_identity.py` and market-data administration | Delete eight standalone-facade tests and eight obsolete acquisition-adapter tests; add four physical-absence cases: net -12 |
| `263c21a5` | C07 factory placeholder, export, unreachable return, obsolete mode/slice prose | All six concrete auth combinations, two wrong-provider OAuth rejection cases, every constructor keyword and real-driver dependency injection | Retain/strengthen real-driver tests in both auth files; retain and rename the real OAuth two-protocol conformance test; add one internal-error behavior case and one absence case: net +2 |

Overall collected-case delta attributable to cleanup: **-10**, with no unexplained
test disappearance. Removing `tests/test_news_identity_repair.py` accounts for
the fifth deleted file; it is not a fifth product module.
The publisher design-supersession assertion remains. Provider catalog entries
no longer advertise the two unused SEC parsers or edgartools connectivity;
no future SEC tool is advertised as implemented.

Review correction: `test_api_key_drivers.py` imported the removed symbol twice.
Both imports were removed atomically with the class; exact OpenAI API-key,
Anthropic API-key and ChatGPT OAuth class assertions replace negative placeholder
checks. The plan's proposed deletion of a placeholder-conformance test was also
corrected: its body was already testing the real OAuth driver, so it remains.

## Offline Verification

All product tests run with an empty inherited environment, temporary HOME and
profile/market/SA/macro/token/lock paths, disabled `.env` loader and scheduler,
explicit AnyIO plugin, an external-network-denying audit hook, private-config and
production-data access guards. Loopback-only OAuth callback fixtures and bundled
binary `--version` probes are allowed; actual harness sessions are denied.
This is offline behavior evidence, not live provider compatibility evidence.

| Selection | Observed result |
| --- | --- |
| Pre-edit relevant ten-file baseline | 135 passed; three dormant edgartools deprecation warnings |
| Corrected wider auth baseline | 352 passed |
| Task 1 physical absence RED | 4 failed, all expected file-presence assertions |
| Task 1 required focused GREEN | 79 passed |
| Task 1 expanded with active SEC financials/tools and supersession | 112 passed |
| Coordinator's retained Task 1 focus including supersession | 80 passed |
| Each deleted module independently restored | Its named test failed; restored cleanup returned four passed each time |
| Task 2 new-owner RED | 2 failed for the expected placeholder and unhandled-mode behavior |
| Task 2 focused GREEN after mutations restored | 49 passed |
| Cross-provider OAuth admitted by mutation | Both wrong-provider cases failed |
| Inert placeholder class restored by mutation | New class/export absence case failed |
| Python census tests | 35 passed |
| Frontend census parser tests | 24 passed |
| Full backend selection (7,953 cases) | 7,939 passed / 12 skipped / 2 temporary-runner false refusals; 741.98 seconds |
| Entire subscription account-usage file after runner correction | 29 passed; both previously failed node IDs included |
| Final combined cleanup/SEC/news/auth/subscription focus | 186 passed, no skips or warnings |
| Runner boundary checks after correction | 5 passed; no subprocess actually dispatched |

The first broader auth attempt exposed defects in the temporary runner: it denied
loopback callback tests and lacked a multiprocessing main guard. That attempt is
not an acceptance result. Both were corrected; callback/multiprocessing tests
passed 10/10, then the same wider auth selection passed 352/352. No product code
or existing test expectation was changed to bypass those harness failures.

The full selection's two failures were
`test_nvm_symlink_launcher_with_env_shebang_passes_exact_version_check` and
`test_app_server_spawn_uses_launcher_path_with_launcher_and_target_dirs_on_path`
in `test_subscription_account_usage.py`. Both create local Python protocol
fixtures whose launcher is named `codex`. The runner incorrectly classified
them as real harness executables by basename. The test and its two runtime
modules are byte-identical across `54dd05a9..263c21a5`; no product/test fix was made.
The corrected guard permits only absolute executable paths whose resolved target
is inside the runner-owned pytest temporary root. Real PATH/bundled launchers,
symlink escapes and external network calls remain denied. Five non-dispatch
boundary checks confirmed the fixture allowance and real/escaped-path denials.

JUnit XML was parsed to verify that both failed node IDs are included in the
successful 29-case rerun and that the rerun has zero failures/errors. The final
186-case run repeats both cleanup tasks and that entire subscription file together.
The original failure report is retained in `backend-regression.xml.gz`, with
`subscription-regression.xml.gz` and `final-focused.xml.gz` alongside it. No second
complete 7,953-case run is claimed. The 12 skips are existing live financial/IBKR/
option-chain/peer-comparison tests, not new skips introduced to hide failures.

## Mechanical Comparison

`leaf-cleanup-census.json.gz` is a new create-only observation compared against
the original `mechanical-census.json.gz`; the baseline was not replaced.
Its compressed SHA-256 is
`b45d645b75afdafcbd33527931b655dc8fbc575b81aec30d6bc1faea0d20e8a8`.
The census reads tracked source only and enumerates main-worktree untracked names
without reading their contents. It imports no product modules and opens no real DB.

- 1,120 source files read; 4,346 candidate rows; 3,464 uncertainty sites.
- New candidates: 0. New uncertainties: 0. Changed dependency metadata: 0.
- New main-worktree untracked names: 0.
- Five coverage reductions: exactly the four approved product deletions plus
  `tests/test_news_identity_repair.py`. No other reduced source coverage.
- Exit **2**, `review_required=true`, is retained honestly for those explicit
  deletions. This is reviewed scope, not a forced green baseline or proof that
  the remaining repository contains no abandoned functionality.

No frontend product source, API schema, tool registration, i18n or stylesheet
changed in this batch, so frontend product tests/build were not rerun. The 24
frontend parser tests above verify the maintenance scanner, not the UI.

## Review And Completion

Independent Task 1 review found no concrete issue. It parsed the immutable
base/head Python sources, checked imports and literal/dynamic entrypoints,
verified 20 retained source/test files were unchanged and reconciled the removed
test ledger. Its runtime evidence is explicitly attributed to the runs above,
not claimed as an independent live or packaged validation.

Independent Task 2/combined review also found no issues: all six auth modes,
rejection guards, constructor branches, keyword/default semantics, exports and
retained real-driver tests were checked against immutable Git blobs. Reports
are `task-1-review.md` and `task-2-review.md`. Those reports preceded the final
test results; their remaining verification gate is closed by the separately
recorded full-selection and corrected-runner follow-up above.

C02, C07 and C17-C19 are implemented on the feature branch. No merge or push.
Coordinated old SEC intake/settings/web/schema removal remains separate, before
the new SEC financial research service and three tools.
