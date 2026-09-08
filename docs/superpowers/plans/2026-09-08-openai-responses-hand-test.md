# Responses Integration and Hand-Test Handoff

The user authorized merging `83adc5b4`; `master` fast-forwarded from `65c673cf`.
Pre-merge source/artifact hashes match and the 419-test focus passed again.
Fresh full backend from the merged main checkout: **7,401 passed / 12 skipped /
three existing edgar warnings**, exit zero, 797.30 seconds. Both runs use the
unchanged loopback-only wrapper with no inherited provider credentials.
The new JUnit reports are retained locally at
`/tmp/arkscope-responses-merge-preflight.xml` and
`/tmp/arkscope-responses-merged-backend.xml`; these local rerun files are not
retroactively inserted into the implementation's sealed packet.
No provider call, production-store inspection/write, migration, App restart,
push or unrelated worktree cleanup accompanies this integration.

## Existing UI Blocker

Do not count an AI-card-page generation as an OpenAI test yet:

- `apps/arkscope-web/src/AICard.tsx` sends `provider: "anthropic"` in `generate()`.
- `apps/arkscope-web/src/api.ts::generateCard` forwards that body unchanged.
- `src/api/routes/analysis_cards.py::generate_card` gives an explicit body
  provider precedence over `task_route("card_synthesis")`.

Therefore selecting OpenAI in Settings does not select OpenAI at this UI entry
point. It can dispatch through the active Anthropic credential instead. These
three files are byte-identical between `65c673cf` and `83adc5b4`; the Responses
migration did not introduce this behavior. Two existing frontend assertions
explicitly expect the Anthropic override, so a green suite is not evidence
that this UI honors the selected task provider.

The earlier suggestion to select Luna and generate a card was incomplete and
is superseded by this warning. A narrow follow-up should omit the UI's fixed
provider and let the existing server task route decide, with both OpenAI and
Anthropic controls. Preserve deliberate API-level caller overrides unless
separately decided. Implementation and merge approval were requested; no such
runtime change is included in this integration.

## Hand-Test Order

1. Fully quit and restart the App from the local `master` tree, including its
   backend process. Reloading only a page is not enough. No reinstall or data
   migration is required by this change.
2. Activate the intended OpenAI **API-key** credential in Settings. Choose Luna
   with an explicit supported effort such as `low` for the two fixed tasks and
   save. Reopen the section to check that the selections persist. Do not use
   ChatGPT OAuth or Spark to certify a direct API-key change.
3. Use the task's actual model test once, not just model-list revalidation.
   This tests model/effort access; the 16-token probe can report acceptance with
   an output-budget warning, which is not completed task-generation evidence.
4. **After the UI blocker is repaired**, generate a new AI card for a ticker
   that already has local evidence. Confirm the normal card fields appear and
   the request does not fail with the former 400/502 errors.
5. Translate that new card to Traditional Chinese. Check numbers, ticker names,
   citations and list lengths against the English original. Switching to an
   already-cached translation does not test the migrated provider path. Before
   the UI fix, an existing English card never translated to this language can
   independently exercise the translation path without generating another card.
6. In Investor Profile settings, start or continue guided calibration and
   actually send one answer. Opening the session alone uses a stored opening
   prompt, not a model call. The current UI omits provider/model, so the server
   defaults to OpenAI Luna and uses the active OpenAI credential. Expect a
   readable next question or draft proposal, not raw JSON or a stuck turn.
   Do not approve a proposal merely for testing; approval changes the profile.
7. Restore the preferred active credential and task routes after testing.

One model is sufficient for this smoke test. Do not repeat every model/auth
combination or enable unrelated schedules. If a request fails, record the step,
time, ticker/card run when available, model, effort, credential alias and visible
error. Do not share keys/tokens or keep retrying without a new diagnosis.

The independently sealed implementation packet remains unchanged at
`docs/superpowers/evidence/2026-09-08-openai-responses-convergence/`.
Its source manifest is bound to the reviewed implementation snapshot, including
the then-current Priority Map; later integration notes are not retroactive
changes to that acceptance evidence.
