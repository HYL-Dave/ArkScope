# Tool Output Boundary Analysis Context

This is derived design analysis, not a vulnerability scan, approved specification,
implementation, or release verdict. The user questioned the principle of the
SEC-only exception and requested a root-level explanation. No such exception or
replacement policy is authorized by this document.

Source worktree: /tmp/arkscope-listing-sec-macro-convergence
HEAD: 18d46062c30da87b30666b1ba0f290872a28fa7f
Drift: present; the previously paused 48-path Task2 patch remains uncommitted.
The identities in [observations.json](observations.json), not HEAD alone, bind
this analysis. Collection SHA-256: 47fd62991101838a0618cb9545c4a9016fd72d99094912d68252afa0d63db682.
The digest is SHA-256 of the sorted, compact JSON path-to-hash mapping; 23 files
cover inspected sources and the fresh offline regression output.

The user's pasted review is an unsealed contextual lead, not an independently
hashed source document. I inspected the actual callers and used only synthetic
values, disposable test stores and injected transports. No production data,
config, credentials, provider calls, installation, restart, merge or push.

| Evidence | Title | Source | Establishes |
| --- | --- | --- | --- |
| E1 | Probe diagnostic scrubber | `src/auth_drivers/probe_harness.py` | A shape-only, deliberately lossy diagnostic safety net is reused for substantive content. |
| E2 | OAuth result and prose sinks | `src/auth_drivers/chatgpt_oauth_driver.py` | Tool results, streamed deltas and final answers share generic redaction; Claude separates prose. |
| E3 | API-key serializers and error guard | `src/auth_drivers/runtime_binding.py` | Successful tool serialization lacks the OAuth blanket rule; captured-key error protection exists. |
| E4 | SEC exact-value and cursor contracts | `src/sec_research/document_queries.py` | Domain identifiers, Decimal TEXT and receipt/filter-bound cursors cannot be rewritten. |
| E5 | Four-channel offline reproduction | `.superpowers/sdd/2026-09-12-sec-research-release-integration/redaction-architecture-checkpoint-01/results.xml` | Four API-key cases pass; four OAuth cases fail, with no setup errors. |
| E6 | Exact-function synthetic probes | `observations.json` | Public strings are corrupted and per-fragment replacement does not protect a split synthetic secret. |
| E7 | Registry and current paused boundary | `src/tools/registry.py` | The registry defines input schemas, not a shared typed result policy; the SEC patch is unshipped. |

The synthetic probe extracts only named redactor definitions and regex constants
with Python AST, then calls them in a standard-library-only namespace. It does not
import drivers or resolve auth. Fragment results are function-level evidence,
not an end-to-end exploit or a production incident. Four-channel test selection
ran eight actual adapter cases; 70 unrelated cases were deselected. Full-suite
and broader security coverage are not claimed. A separate follow-up run of
35 existing probe/captured-key error controls passes (133 deselected), with its
source logs/XML included in the collection. It is not remediation evidence.

Source inspection and experiments preceded this compact inventory; it is not
represented as a prior scan manifest. Original evidence remains untouched.
