# Four-Task Route Repair Hand Test

Status: `codex/task-route-authority`, code `b669d455`, is ready for separate
merge authorization. The cold-restoration finding passes scoped re-review.
Not merged; restart only after integration, not against the unchanged master.

Current offline verification: 7,593 backend passed / 12 skipped; 1,825 frontend
passed; typecheck/build passed. Six final frontend mutations were killed and
restored, including both new context guards; 176 final-code synthetic browser
screenshots cover desktop/mobile and both locales/providers. Three existing
backend warnings and the existing Vite large-chunk warning remain. The
[evidence record](../evidence/2026-09-09-task-route-authority-repair/README.md)
preserves earlier failed reviews separately from this correction and from
still-pending live acceptance.

## Boundaries

This repair does not make unsupported models eligible. Spark remains available only for Content Translation through an entitled ChatGPT subscription. Retired models and the existing unadmitted Fable OAuth combination remain blocked. Offline tests do not prove every live provider/model combination works.

An execution receipt describes the provider/model/effort/authentication selection sent by ArkScope. It is not a claim that every provider has supplied an independently verified model receipt. Existing transport-specific model checks remain in place.

## After Merge And Manual Restart

1. In Settings, save a supported provider/model/effort for each of the four task routes. Navigate away and back: the saved choices should remain. Use distinct routes where convenient so an accidental cross-task selection is visible.
2. Generate a NEW AI card with OpenAI selected for AI Card Generation. Its source must show the selected OpenAI model and effort. Repeat with a supported Anthropic route only when useful; opening an old card is not a new-model test.
3. Translate that card with the saved Content Translation route. The translation source must match that route. Switch EN/localized language several times: this must use the same cached translation, without a new execution.
4. Change the Content Translation model or effort in Settings. Returning to the old translation must keep its original source. Use the explicit retranslation command to generate a new version. A failed refresh must leave the old translation readable.
5. Open a new or existing AI Research conversation. The next execution's default must come from the AI Research Settings route, not fixed Luna, a historical message's tuple or a preference saved by an earlier conversation. A deliberate choice made in the currently open conversation may override the default. Visit Home or Settings and return to the SAME conversation: that explicit choice must survive. Opening a different/new conversation clears that transient override. Existing messages retain their own source.
6. Open a target with an older Lifecycle Investigation result. Its source remains historical. Before starting a new investigation, the confirmation must show the current provider, model, effort and authentication channel, even when they differ from that older result.

For the Research navigation checks, also leave a model edit awaiting effort:
Home/Settings and back must keep Send disabled and that pending model selected.
Do not display the previous route's auth/quota/reason as the pending choice's
source. Completing effort restores the new choice's own source and eligibility.

For cold restoration, reopen Research with a previously selected conversation.
Editing the model or draft while history loads must not create a new conversation:
Send remains disabled until the intended history is available. The eventual
answer must stay in that conversation and show the selected new tuple; old
messages retain their old sources. New is the explicit way to start separately.
If history is missing or fails to load, the draft remains and Retry/History/New
provide recovery; no silent fallback to an unrelated conversation is allowed.
The delayed-response and deletion races are covered offline, so do not delete
valuable research just to manufacture a manual race.

Cache/cost hints are a separate recorded proposal, not included in this build.
Do not infer cache hits or misses from model choice, latency, or a short interval.

## Negative Controls

- An unsupported model/effort/auth combination must produce an explicit error, not a successful result from a different model or billing source.
- Settings changes during an already-started operation apply to the next operation. They must not change that operation's credential, model or effort partway through.
- Older cards/translations with missing source metadata must show the missing information as unknown, never borrow the current Settings values.

Report the task, saved provider/model/effort, displayed result source and error message if any step differs. No credentials or tokens are needed in a report.
