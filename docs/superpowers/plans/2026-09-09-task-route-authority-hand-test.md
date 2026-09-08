# Four-Task Route Repair Hand Test

Status: implementation in progress on `codex/task-route-authority`; not merged, not a request to restart yet.

## Boundaries

This repair does not make unsupported models eligible. Spark remains available only for Content Translation through an entitled ChatGPT subscription. Retired models and the existing unadmitted Fable OAuth combination remain blocked. Offline tests do not prove every live provider/model combination works.

An execution receipt describes the provider/model/effort/authentication selection sent by ArkScope. It is not a claim that every provider has supplied an independently verified model receipt. Existing transport-specific model checks remain in place.

## After Merge And Manual Restart

1. In Settings, save a supported provider/model/effort for each of the four task routes. Navigate away and back: the saved choices should remain. Use distinct routes where convenient so an accidental cross-task selection is visible.
2. Generate a NEW AI card with OpenAI selected for AI Card Generation. Its source must show the selected OpenAI model and effort. Repeat with a supported Anthropic route only when useful; opening an old card is not a new-model test.
3. Translate that card with the saved Content Translation route. The translation source must match that route. Switch EN/localized language several times: this must use the same cached translation, without a new execution.
4. Change the Content Translation model or effort in Settings. Returning to the old translation must keep its original source. Use the explicit retranslation command to generate a new version. A failed refresh must leave the old translation readable.
5. Open a new or existing AI Research conversation. The next execution's default must come from the AI Research Settings route, not fixed Luna, a historical message's tuple or a preference saved by an earlier conversation. A deliberate choice made in the currently open conversation may override the default. Opening a different/new conversation clears that transient override. Existing messages retain their own source.
6. Open a target with an older Lifecycle Investigation result. Its source remains historical. Before starting a new investigation, the confirmation must show the current provider, model, effort and authentication channel, even when they differ from that older result.

## Negative Controls

- An unsupported model/effort/auth combination must produce an explicit error, not a successful result from a different model or billing source.
- Settings changes during an already-started operation apply to the next operation. They must not change that operation's credential, model or effort partway through.
- Older cards/translations with missing source metadata must show the missing information as unknown, never borrow the current Settings values.

Report the task, saved provider/model/effort, displayed result source and error message if any step differs. No credentials or tokens are needed in a report.
