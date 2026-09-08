# Conditional Sonnet Canary Harness

This directory is preparation, not a live result or authorization receipt.
No production profile, token or SEC contact has been read by this revision.
The single proposed TA / Sonnet 5 / Claude Code OAuth envelope is in
`../../plans/2026-09-07-lifecycle-web-usage-calibration.md` and still needs user
confirmation. Do not reuse either earlier canary's approval or its source seal.

The runner derives from the immutable September 7 Sonnet harness. It chains the
product controller's `on_reply` before observing phase counters, requires the
new usage checkpoint hash explicitly and checks source admission before profile
metadata or token access. The code/runtime/selected-credential binding is
rechecked before a new temporary journal is created. Only the exact selected
token is loaded once. There is no credential/model fallback or profile action.

Search and analysis have at most one SDK submission each (6 / 2 CLI turns),
with Sonnet 5 also pinned for helpers, four admitted WebSearch uses, four source
candidates, eight source HTTP attempts including redirects and two redirects
per page. Limits are 32 MiB encoded / 128 MiB decoded per page, 180 seconds for
source retrieval and 180 seconds per model phase. A 660-second local completion
deadline includes local validation/cleanup, not additional model calls. There
is no application text truncation or inferred subscription charge guarantee.

The input explicitly names TravelCenters common stock on NASDAQ, not its senior
notes. Protocol completion and useful delisting evidence are separate results:
acquisition does not itself prove delisting, BP is not an alias, nonessential
read gaps must be disclosed, and contrary active/OTC or missing essential proof
still prevents action. The harness never accepts or applies a finding.

`test_usage_canary.py` uses a synthetic temporary profile, token adapter, SDK
messages and public-source reader. It exercises the real product controller,
phase callbacks and journal readback, including source and analysis failures.
`verify_harness.py` runs the complete nine-case suite, reverses the callback,
source-admission ordering and HTTP-observation field guards in a temporary copy,
then reruns the restored suite. It does not launch an inference session. Version
admission can locally probe the bundled CLI with `--version`.

The original RED run, the first nine-case green run, the subsequently exposed
HTTP-observation field error and final corrected results are retained in the
parent usage checkpoint. The first green run did not exercise a populated HTTP
observation list and is not final admission. Final tests do populate that list.
