# Sonnet Web Canary Results

## Current Conclusion

The Claude OAuth lifecycle analysis transport is repaired and has two successful
live analysis checks on different previously captured public source sets. This
is **not** a completed fresh end-to-end live investigation or an action-ready
delisting finding. No production adoption, migration, restart, commit, merge or
push occurred. Do not begin user hand testing on the strength of these results.

The current backend passes **6,901 tests / 12 skips**, with three existing
edgartools warnings. The entire affected focus passes 2,236 before/after all
15 independently killed named mutations; integration passes 3,055. Relative to
the original usage checkpoint, 41 backend nodes were added and none removed.
The frontend, database schemas, other auth adapters, Research and Spark are
unchanged by these follow-up corrections. The earlier frontend/browser gates
remain historical results, not newly executed checks.

## What Failed And Changed

1. The first full canary and its diagnostic failed when native StructuredOutput
   emitted literal function-template property names instead of finding fields.
2. An explicit schema prompt produced one valid native result, but our host
   incorrectly compared total turns with the SDK's tool-round-trip budget.
   Correcting that comparison did not increase the configured native budget.
   [Agent loop documentation](https://code.claude.com/docs/en/agent-sdk/agent-loop)
   documents this distinction.
3. A renewed full run reproduced the template problem despite the improved
   prompt. That mitigation alone was therefore insufficient. The similar
   [upstream report](https://github.com/anthropics/claude-code/issues/87234) is
   supporting context, not vendor confirmation of the cause.
4. Only the tool-free Claude OAuth **analysis** phase now requests final-message
   JSON, with native output_format disabled. This is declared before dispatch,
   not a fallback after failure. The existing shared strict parser and finding
   validator remain authoritative. Search retains native structured output and
   its existing WebSearch bounds. No tool, credential, model or billing fallback
   was added. Repeated JSON keys, wrappers, prose, malformed or mixed results,
   foreign sessions, failed terminals and analysis tool activity remain rejected.

The native output guarantee was deliberately replaced by strict host validation
for that one phase. The host does not repair or extract malformed output, and
does not claim constrained decoding. [SDK result documentation](https://code.claude.com/docs/en/agent-sdk/python#resultmessage)
identifies result text as the final assistant response. Other tool-free OAuth
consumers have not been changed or independently live-tested by this amendment.

## Measured Attempts

| Attempt | SDK submissions | Source HTTP attempts | Actual outcome |
| --- | ---: | ---: | --- |
| R1 full search/read/analysis | 2 | 4 | Search accepted; native analysis exhausted tool rounds |
| D1 captured-source diagnostic | 1 | 0 | Literal template fields confirmed in both output attempts |
| R2 schema-prompt analysis | 1 | 0 | Native success; host rejected final-turn count |
| R3 renewed full run | 2 | 4 | Template failure recurred; three pages captured |
| Final JSON analysis of R3 sources | 1 | 0 | Accepted JSON; finding has essential evidence gaps |
| Final JSON analysis of R1 sources | 1 | 0 | Accepted JSON; citation/date checks prevent adoption |
| **This authorization campaign** | **8** | **8** | **0 profile actions** |

Both final analyses report literal apiKeySource `none`, exact Sonnet 5,
no advertised tools/MCP servers, one total native turn, completed owned
terminals and reaped children. Neither selects another credential/model or an
API key. No rate-limit rejection was observed; this does not assert that the
account has only a five-hour limit. SDK submissions are not hidden provider HTTP
counts or a monetary/subscription-quota measurement.

The final analysis token observations are 10,450 input / 1,204 output (R3) and
8,340 / 1,102 (R1), from model_usage, with cache counters retained separately.
Failed full runs preserve the accepted search subtotal and explicitly unknown
full totals. Rejected analyses do not become zero consumption.

## Evidence Quality

- R3's readable sources confirm acquisition completion, but their explicit
  delisting announcements concern senior notes TANNI/TANNL/TANNZ, not TA common
  stock. The model discloses missing common-stock evidence; action remains null.
- R1 contains a conditional common-stock cancellation notice and later
  acquisition language. The model also abbreviates three purported quotations
  and uses whole phrases in date fields. Only two exact passages are admitted;
  citation, date, identity and unresolved-fact blockers remain. Do not convert
  a confident summary into a verified delisting decision.
- R3's fourth candidate was not requested because the source budget was spent
  after one SEC redirect and three page bodies. This is not a BP outage report.
  A complete transfer is not proof that the page concerns the right security.
- Both recorded outputs were replayed **offline** through the real controller,
  pipeline, temporary journal and projection. Reopening retains all blockers,
  null actions and usage sums. This proves readback, not another live run.
  No human assessment/adoption or production state was created by the replay.

Source quotations are represented by hashes and byte lengths in the published
live-analysis projections; the original raw responses and journals remain in
private temporary directories. The projections are not mislabeled raw outputs.

## Remaining Work

1. Use these real failures to tighten citation/date output guidance and evaluate
   source selection. Do not loosen quote matching or promote debt/conditional
   notices to common-stock delisting just to obtain a positive canary.
2. A new complete live run still needs separately renewed public-source HTTP
   authority. The original eight-attempt budget is exhausted. A proposed bound
   remains four candidate URLs / at most eight total HTTP attempts including
   redirects, not a retry loop; two Sonnet SDK submissions remain within the
   user's additional-model-use authorization. Denied or incomplete evidence is
   a valid negative result, not permission for more calls.
3. Remaining auth-channel live gates and separately authorized production
   installation/population cutover, merge, restart and user hand testing remain
   open. No decision about those gates was inferred from this user grant.

## Immutable Receipts

- Original usage checkpoint: `../2026-09-07-lifecycle-web-usage/`.
- R1/D1 failure: `failed-live-r1/`, seal `a7df8829579c6069ae4b5b2136f825864aead543b6a5caf1ee20b170c9d50093`.
- Prompt admission: `prompt-admission/`, seal `2cd4bcf60f5a9fcd4f60d91402a29bcca90e2a15c9d2bd76c1a67a61c4cb1752`.
- R2 host rejection: `host-rejected-replay-r2/`, seal `3baa4ea61a1ca1ff918689a5b4e75166f42615a0438ff62eee6509ebd8cf23ac`.
- Turn accounting: `turns-admission/`, seal `3bd019ea5014e06a0249173e208ac5f7900ee9c063081c9e017b77afc1e438d4`.
- R3 failure: `failed-renewed-r3/`, seal `79711c3a3a147242f748b58cc765ab7cf5d3a0dca2335296f4100b02648c2422`.
- Final code admission: `json-analysis-admission/`, seal `9c4f48ddc0f4bad452a93b610a610942336390f1ea761fca14bcf12e62e4ba60`.
- Two final live analyses/readback: `live-json-analysis/`, seal `c44fa6670430620747f3a5d85bcffc5220555b49afd0a068052e635a3dd5510b`.

The interrupted filesystem-backed prompt campaign and its successful RAM-backed
rerun are separately preserved. The new wire-fixture adjustment has its initial
failure retained. No failed measurement has been rewritten as green.
