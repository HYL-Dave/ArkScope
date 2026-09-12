# Compaction Follow-Up

Base: d42f29ce8c7b6c3320bc9ae31e3a222732da641a. Synthetic-only defensive
follow-up to the final review's completed probe, not a substitute review.

Source-to-sink: the native agent's Layer 5 invokes AnthropicSummaryCaller;
its exception path previously logged the raw SDK error. The generic layer
also logged raw caller exceptions and installed unchecked returned summaries.
The review probe used a local SDK MockTransport returning a synthetic credential
in an HTTP 400 error. No provider or production secret/data was accessed.

The fix registers the actual summary client's captured key before use, inherits
the active output scope (or creates a local scope for standalone use), sanitizes
both error paths in-scope, and rejects whole credential-bearing summary text
before any cap/context replacement. It does not alter model, prompts, token
budget, request count, retry or circuit-breaker behavior. Public summaries stay
unchanged; failed compaction retains original messages.

Named owners live in tests/test_research_output_compaction.py (17 cases).
RED compaction-red-01: 10 failed / 7 passed, no errors/skips.
GREEN compaction-green-01 with unchanged compressor/server/core/EIR controls:
163 passed, no failures/errors/skips.

Inverse groups (actual product edits, each restored):

- Omit actual selected-client registration: 2 failed, 15 deselected.
- Omit built-in and layer summary admission: 4 failed / 2 passed,
  11 deselected. Owners cover direct output and before-cap context installation.
- Restore raw error diagnostics in both modules: 4 failed / 4 passed,
  9 deselected, including the actual native SDK MockTransport probe.

The original review's 2 passing probes intentionally assert the old leakage
and are retained as historical defect evidence, not passing safety tests.
The final independent reviewer returned no verdict; no independent approval
is claimed for this local follow-up. Complete verification and external review
remain distinct gates.

Restored focused run compaction-restored-01: 1,046 passed, no failure/error/skip.
This includes all 17 new owners, four-channel policies, event/lifetime guards,
runtime binding and unchanged card authority and compressor/server controls.
These overlapping focused counts must not be added to the complete backend.

Final single complete-backend run on ff7c4d75: 10,166 passed / 12 unchanged
manual live skips, zero failures/errors. All 17 compaction owners ran without
skips. The source/runner/runtime before/after identities agree; no independent
final review is inferred from this automatic verification.
