# Final Review Cancellation Repair

Whole-change review found one P1 at the native OpenAI queue/consumer boundary.
An end hook could admit and enqueue a complete result, then executor cancellation
could interrupt ready.wait before its consumer persisted that result. Recovery
correctly rebuilt durable events, but could not reconstruct this unpersisted end.

Commit dbc8f7e5 adds a narrow CancelledError handler: disable hook publication,
deliver the already-admitted finite queue, then rethrow. Existing finally still
cancels/awaits the same SDK worker through repeated cancellation. No GeneratorExit
yield, extra retry, raw-result fallback, secret exemption or provider API change.
Events still pass the retained output guard before the executor appends them.

New deterministic integration owner:
test_queued_openai_completions_survive_executor_cancellation[False/True].
The fake SDK runner invokes real tool hooks with two whole generated SEC outputs,
cancels the real executor before it can consume them, and attempts secret-bearing
late publication during cleanup. True additionally repeats cancellation twice.
Assertions read actual reopened run/thread stores and query-only citation roots,
then verify market reference closure. Exact IDs, inputs, both reference arrays,
cancelled message and SDK cleanup must survive. No live provider/store is used.

- final-review-cancel-red: 2 intended assertion failures, missing both durable ends.
- final-review-cancel-green: command setup error, nonexistent test path, exit4,
  no tests run. This is a controller typo, not a product failure or GREEN receipt.
- final-review-cancel-green-02: 709 passed, runner63.047s, relevant seven suites.
- backend-final-collection-02: 10595 nodes, exit0, supersedes earlier10593 collection.

Only agent.py and the trace test changed, 11 and71 added lines. Original reviewer
owns scoped re-review. Full-backend execution/acceptance remain pending at this
report checkpoint; its outcome belongs in the final evidence README.
