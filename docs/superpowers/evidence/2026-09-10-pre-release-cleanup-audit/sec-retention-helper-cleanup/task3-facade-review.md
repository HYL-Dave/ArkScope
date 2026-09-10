# Task 3 Facade Review

**Finding: CONFIRMED [P2]**
**Spec Verdict: CHANGES REQUESTED**
**Quality Verdict: CHANGES REQUESTED**

Scope: only `TickerIdentityService.get_review_confirmation` after the five-route removal at frozen `0c5896a561fb8397daa79e60d4f1c80cb299463b`, compared with `58e1929b61905b905fc0e12bdc5daf1ad116b84b`. This assessment uses the previously collected source evidence; no new source inspection or tests were performed for this follow-up.

**Evidence**
The [four-line facade](/tmp/arkscope-listing-sec-macro-convergence/src/ticker_identity_service.py:206) only imports `_result` and returns `_result(self, transition_id)`. Its sole runtime caller at base was the removed GET confirmation handler. At frozen head, the bounded exact-reference check found its definition and six test call sites, with no remaining production caller or registration. Four calls already existed in `tests/test_security_lifecycle_review.py`; the patch adds the readbacks at [review_routes:45](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_review_routes.py:45) and [review_routes:228](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_review_routes.py:228). Test dependencies do not make this facade a retained actual consumer.

The live owner is [_result](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_review.py:264), called directly by current confirmation execution at [line 305](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_review.py:305) and [line 322](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_review.py:322). Its `confirmation_for` validation also remains live in [current review](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_current.py:167), [history](/tmp/arkscope-listing-sec-macro-convergence/src/ticker_identity_history.py:223), and [transition application](/tmp/arkscope-listing-sec-macro-convergence/src/ticker_identity_transition.py:1944). Those owners and their integrity/privacy coverage must remain.

**Counterevidence And Scope**
No counterevidence or scope objection was found. Retaining a meaningful public service could be justified by an actual supported consumer, but the collected evidence supplies none for this forwarding facade. Removing it follows the same last-runtime-caller cleanup rule as the translation teardown; it is not authorization for miscellaneous helper cleanup. Severity concerns incomplete cleanup and test ownership, not an observed runtime/privacy failure.

The parent's proposed correction is appropriately bounded: remove only the facade, move its existing test readbacks directly to `_result(service, transition_id)`, preserve all action/state, receipt, corruption-rejection and no-write assertions, and add an absence guard for the facade itself. The guard must not prohibit `_result` or `confirmation_for`. Existing migrated test IDs can remain; account separately for the added guard.

**Execution Boundary**
Leave the current full-backend run on frozen `0c5896a5` undisturbed. That run cannot establish the result of a later cleanup commit; subsequent evidence must identify its own head. No code/index/HEAD edits, tests, App/provider execution, or further source work were performed here. Only this separate note was created; `task3-review.md` was read and left unchanged during this follow-up.
