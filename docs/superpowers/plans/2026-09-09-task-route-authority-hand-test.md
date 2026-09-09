# Four-Task Route Repair Hand Test

Status: `codex/task-route-authority` is NOT ready to merge. One cold App-start Research restoration regression remains after scoped re-review. Not merged, not a request to restart yet.

Pre-fix offline verification: 7,537 backend passed / 12 skipped; 1,739 frontend passed;
typecheck/build passed; six regression mutations killed and restored. The
[evidence record](../evidence/2026-09-09-task-route-authority-repair/README.md)
separates these results from still-pending live acceptance.

Post-fix verification: 7,591 backend passed / 12 skipped; 1,781 frontend passed,
typecheck/build passed; nine mutations killed and restored; 96 new synthetic
browser screenshots. These checks do not cover the remaining cold-restoration case: editing
a model before the saved conversation loads can silently start a new conversation
instead. Its old messages are not deleted. A bounded correction has been proposed;
do not treat waiting before editing as a completed fix.

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

The currently failing cold-start gate must pass before this checklist becomes
an operator handoff: restore a saved conversation with delayed history, edit the
model before it loads, then confirm the next request retains that conversation
and the chosen tuple. A deliberate New action must still create a new conversation.

## Negative Controls

- An unsupported model/effort/auth combination must produce an explicit error, not a successful result from a different model or billing source.
- Settings changes during an already-started operation apply to the next operation. They must not change that operation's credential, model or effort partway through.
- Older cards/translations with missing source metadata must show the missing information as unknown, never borrow the current Settings values.

Report the task, saved provider/model/effort, displayed result source and error message if any step differs. No credentials or tokens are needed in a report.
