# Manual Live Smokes

These files are standalone, manually run checks. They are never collected by
the default pytest suite, and no automated admission command runs them.

Depending on the script, execution can require real credentials, network
access, provider entitlement, and live Gateway state, and can incur provider
spend. Review the script's preconditions before running it. This directory
must not contain files named `test_*.py`.

| Script | What it proves | Requires |
|---|---|---|
| `sdk_driver_smoke.py` | The admitted SDK/CLI pair passes two bounded sessions: one positive in-process MCP control and one locked tool/config surface check. Output is a closed, non-secret evidence object. | Explicit provider-call authorization, profile DB path, stored Anthropic `claude_code_oauth` token, network, and provider entitlement. |
| `sdk_route_smoke.py` | The `/query/stream` Anthropic subscription helper drives the real driver through the route's exact path. | Same Anthropic requirements; one real subscription call. |
| `smoke_fred.py` | FRED metadata, release dates, vintage reads, catalog loading, and an in-memory ingestion dry run work against the live API. | FRED API key, network, and provider availability. |

The scripts load credentials at runtime and must not embed or print them.

Run only by explicit manual choice from the repository root:

```text
python tests/live/sdk_driver_smoke.py --profile-db /path/to/profile_state.db
python tests/live/sdk_route_smoke.py
python tests/live/smoke_fred.py
```

Exit code `0` means the selected smoke passed. The Claude smoke background is
`docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md` section 9.
