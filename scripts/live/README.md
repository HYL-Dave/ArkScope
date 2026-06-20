# scripts/live/ — manual live smokes (real billing)

These are **standalone, manually-run** diagnostics that make **real** subscription / API
calls. They are deliberately **NOT** part of the pytest suite (they cost money and need
live credentials + network). Run them by hand when validating an auth/driver change
end-to-end; the fake-SDK unit tests cover everything that can be proven offline.

| script | what it proves | requires |
|---|---|---|
| `sdk_driver_smoke.py` | The Claude-subscription SDK driver (`AnthropicClaudeCodeSdkDriver`) built via the factory: subscription auth (no API-key billing), a Tier-1 tool through the in-process bridge, built-ins locked, no token leak. | active anthropic `claude_code_oauth` credential + token |
| `sdk_route_smoke.py`  | The `/query/stream` route helper `_anthropic_subscription_stream` drives the real driver end-to-end (same four checks, through the route's exact path). | same |

**Token discipline:** none of these embed a token — each loads it at runtime from the
token-store and redacts it from all printed output. Do not paste tokens into these files.

Run from the repo root:

```sh
python scripts/live/sdk_driver_smoke.py
python scripts/live/sdk_route_smoke.py
```

Exit code `0` = PASS. Background: `docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md` §9.
