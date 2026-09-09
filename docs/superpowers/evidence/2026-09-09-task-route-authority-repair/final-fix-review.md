# Final Fix Wave Scoped Re-Review

**Final verdict: NOT APPROVED.** P1 is ADDRESSED. P2 is partially addressed,
but NOT ADDRESSED in full: the warm App-navigation defect and caption issue
are fixed, while this fix introduces one P2 cold-restoration regression.
No other new fix-diff breakage was found in this scoped re-review.

## Original Findings, In Order

### 1. P1: Structured Refusal Metadata Bypasses Selected-Key Redaction

**ADDRESSED.** [anthropic_refusal.py:43](/tmp/arkscope-task-route-authority/src/anthropic_refusal.py:43)
projects only string `type`, `category` and `explanation` fields from SDK
objects or dictionaries. Unknown, nested, null and malformed values cannot
escape that closed shape. Each retained field uses the existing captured-key
redaction before its 500-character bound, at
[runtime_binding.py:93](/tmp/arkscope-task-route-authority/src/auth_drivers/runtime_binding.py:93).
Benign useful strings survive; this is not arbitrary recursive event rewriting.

The exception projects its details and sanitizes its text at
[anthropic_refusal.py:25](/tmp/arkscope-task-route-authority/src/anthropic_refusal.py:25).
The native caller supplies its already-selected client's key before the warning
log and error event at
[agent.py:465](/tmp/arkscope-task-route-authority/src/agents/anthropic_agent/agent.py:465).
The active binding is also available to the sanitizer. Neither path reselects
credentials. Refusal still branches on `stop_reason`, emits `model_refusal`,
and returns without success or fallback.

Independent enforcement occurs before legacy SSE at
[query.py:569](/tmp/arkscope-task-route-authority/src/api/routes/query.py:569)
and before managed event persistence at
[research_run_manager.py:65](/tmp/arkscope-task-route-authority/src/research_run_manager.py:65).
Legacy passes its captured binding; the manager validates binding identity
before iteration and passes that same binding to classification and projection
at [research_run_manager.py:164](/tmp/arkscope-task-route-authority/src/research_run_manager.py:164).
Raw-adapter events therefore cannot bypass the native-origin protection.

The 54 cases owned by
[test_task_runtime_binding.py:858](/tmp/arkscope-task-route-authority/tests/test_task_runtime_binding.py:858)
cover nine shapes across six native/adapter boundaries. Assertions observe
native logs/events, legacy SSE, actual SQLite rows, reopened-store public
replay, typed failure and exactly one request or adapter invocation. Replacing
the active fixture credential after capture tests binding authority, not just
generic token-pattern redaction. The final backend focus contains all 54.

The helper retains the old two-positional-argument constructor. Synthesis and
translation still raise/catch that same exception without retry at
[card_synthesis.py:395](/tmp/arkscope-task-route-authority/src/card_synthesis.py:395)
and [card_synthesis.py:924](/tmp/arkscope-task-route-authority/src/card_synthesis.py:924),
under their existing activated execution bindings. I checked the shared import
path and other constructor consumers; no new consumer breakage was found.

### 2. P2: Same-Conversation Overrides Are Lost on Ordinary App Navigation

**PARTIALLY ADDRESSED; NOT ADDRESSED in full.** The original warm-navigation
reproduction is repaired. App owns one transient current-conversation record
at [App.tsx:55](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/App.tsx:55)
and passes it across Research page unmounts at
[App.tsx:164](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/App.tsx:164).
Standalone consumers retain the local-ref fallback. Complete and incomplete
choices initialize from that record; same-ID hydration retains them at
[Research.tsx:348](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:348).
Submission associates the first client-created/server-accepted ID at line 577.
New and delete-current reset the record at lines 631 and 663; opening another
ID resets through hydration, and delete-other leaves it alone. There is no
historical override collection, localStorage tuple preference, or message-tuple
authority.

Actual StrictMode App unmount/remount owners start at
[ResearchWorkspace.test.tsx:599](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/ResearchWorkspace.test.tsx:599).
They cover warm delayed restoration, exact next-run bodies, both Settings
providers, complete/incomplete choices, custom IDs, reset actions and first-ID
continuity. Their delayed case first establishes the App-owned record; it does
not exercise the saved-session-ID-only cold mount described below.

**Caption completion is ADDRESSED.** The guards at
[Research.tsx:273](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:273)
and [Research.tsx:1113](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:1113)
suppress the prior route's auth/quota and both localized/raw blocked-reason
captions while effort is incomplete. Provider buttons retain their independent
provider presentation, and Send remains blocked. Completing effort restores
the new route's real captions and any runtime-unavailable reason. Eight owners
at [ResearchWorkspace.test.tsx:532](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/ResearchWorkspace.test.tsx:532)
cover both directions and ready/blocked prior and destination states. I also
viewed the final Traditional Chinese mobile pending/completed screenshots:
the pending OpenAI choice has no stale Claude composer captions; the completed
choice shows ChatGPT captions without incoherent overlap.

## New Fix-Diff Breakage

### P2: Initial Picker Edits Discard the Saved Conversation Before Hydration

New-fix locations:
[Research.tsx:296](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:296),
[Research.tsx:403](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:403),
and [Research.tsx:782](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:782).
The incomplete initialization guard is at
[Research.tsx:228](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:228).

Reproduction: cold App mount with session storage naming an existing thread T
but no App-owned ref yet. Let the model catalog load before the initial history
list. Select Sol/low without clicking New Research, let history finish loading,
then submit. The saved thread association has been removed, the composer stays
on New conversation, and the request uses a new UUID instead of T.

`transcriptPendingThreadId` initializes only from the App ref, not the saved
session ID. `chooseModel` supplies null when that ref is not initialized; the
new `rememberConversation` stores a known-blank record and calls
`writeActiveThreadId(null)` at line 299. The new early return at line 403 then
treats this edit as an explicitly blank conversation and never reaches the
session/history restoration code. After effort completes, both submission
guards see no pending transcript, and line 573 allocates a new thread ID.

The bounded real-App diagnostic below reproduced this twice. Its no-edit
control waits for the same delayed history and submits to T. Its edit case
waits for history too, yet submits Sol/low to a new ID. This is not merely the
pre-existing ability to press Send before history resolves: the new state
write and early-return guard prevent restoration even after the response.
At the immutable base, picker edits did not clear the saved ID, and the initial
history callback still restored that ID. The existing warm-restoration owners
and nine mutations do not guard this cold path.

Impact: the current-thread bookmark/association is lost and the next question
executes without the intended conversation context. **The old thread and its
messages are not deleted**; they remain in history and can be reopened. This
is a P2 workflow/routing regression, not destructive database data loss.

Required correction: distinguish unresolved cold restoration from an explicit
new conversation. Preserve the saved target through initial picker edits and
block submission until its identity/hydration is resolved; keep the deliberate
New/delete-current blank-state behavior. Add a cold App-mount owner with a
delayed initial history response and exact thread-ID assertion, alongside the
existing warm-remount controls. No implementation was performed in this review.

## Scope And Verification

- Immutable range: `090a72258e76f84367c886da0e41ae79e181d2c0` to
  `20a7737300fb0557cbc0e1712f833163cadb61ce`, all three supplied fix commits.
  Package SHA-256:
  `387884f38d1e4b03391cce22640853ba35b7344f6f4314cd5681227428a5639c`.
  Its diff body matches `git diff --unified=10` byte-for-byte. Review scope was
  the two findings, caption ruling and new breakage in these fixes, not another
  whole-branch review.
- Read the final implementer report including its caption supplement; its
  canonical archive matches byte-for-byte. Parsed actual JUnit artifacts:
  `tmp/final-fix/backend-focus-green.xml`: 1,469 cases, no failures/errors/skips;
  `tmp/final-fix/frontend-caption-green-verified.xml`: 214, likewise clean.
  Controller post-fix baseline XML independently has those same clean counts.
  Intermediate misleadingly named green artifacts were not used as final proof.
- Parsed all nine mutation XMLs and matched their SHA-256 and named owners to
  `post-fix-mutation-results.json`. M7 raw refusal: 24 failing owners; M8 missing
  App ref: 38; M9 stale caption: eight. M4's separate failure/teardown records
  share one classname/name; that overlap is one logical owner, not two guards.
  Restored runtime/frontend/tests/harness files match Head and the index is
  unchanged. No reviewer mutation occurred.
- Latest browser results hash matches
  `91de9c434c35ad95754e95c9467e14a0e1f6d85bfaa80d9e891ecd17d6228013`:
  96 scenes in eight contexts, five synthetic run requests per context, no
  recorded page errors or geometry failures. Inspected the harness assertions
  and the two mobile screenshots noted above; no browser evidence was regenerated.
- Controller's post-restoration complete frontend XML
  `.superpowers/sdd/2026-09-09-task-route-authority-repair/post-fix/frontend-final.xml`
  contains 1,781 tests in 125 files, zero failures/errors/skips. Controller
  reports 11.82 s wall time, typecheck exit 0 and build exit 0 in 4.71 s with
  only the existing chunk warning. These are controller-run results, not
  reviewer full-suite reruns. Full backend session 1049 remains pending at
  unchanged Head; latest controller update was approximately 66% complete.
- New reviewer diagnostic: the exact OFFLINE command below completed with
  **1 doctest passed in 2.30 s, exit 0**, running only two in-memory App cases.
  The wrapper verified loopback-only networking, `ENETUNREACH` externally and
  no inherited credentials. The first attempt had the same observed cases and
  node exit 0 but failed textual comparison on ANSI prefixes; only report-side
  output parsing was corrected. Its pass confirms the observed regression,
  not remediation.
- Immutable-range `git diff --check` is clean. Only this report was authored,
  using `apply_patch`. No code/index/HEAD/branch changes, provider calls,
  production config/credential/store reads, App restart, installs, subagents,
  full-suite duplication, merge or push.

## Out-of-Scope Observations

The recorded pre-existing compaction/eventkit issues and existing build chunk
warning remain separate follow-ups. No fix-diff change to their behavior was
identified; none explains the reproduced cold-restoration path. No additional
broad investigation or live-provider acceptance is claimed.

**Final assessment: NOT APPROVED.** Correct the one P2 cold-restoration
regression. P1 and the original warm-navigation/caption repairs are supported
by source and focused evidence; full passing suites would not negate this
concrete missed path. This report grants no merge or implementation permission.

## Read-Only Cold-Restoration Diagnostic

This report-local doctest adds two diagnostic test cases to the existing
ResearchWorkspace test module in memory only. It does not substitute or edit
any runtime module. The real App, Research, reducer, shell navigation and
existing synthetic fetch fixtures run under the plan's OFFLINE wrapper.
Vite config/env loading, dependency optimization and test caching are disabled.
The existing test file and all runtime files remain unchanged on disk.

Executed from the review worktree:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q --noconftest -p no:cacheprovider --doctest-glob=final-fix-review.md .superpowers/sdd/2026-09-09-task-route-authority-repair/final-fix-review.md --tb=short
```

The assertions below intentionally record observed behavior, not the desired
contract: a passing diagnostic can confirm a regression. The no-edit case is
the legitimate saved-thread restoration control.

```pycon
>>> import json, subprocess
>>> node_program = r'''
... import { startVitest } from "vitest/node";
... const extra = `
...   it.each([false, true])("review cold saved-thread hydration (edit=%s)", async edit => {
...     const rows = [thread("same", "Same conversation")];
...     const delayed = deferred<void>();
...     const fetchMock = stubFetch({ catalog: catalog(), threads: rows });
...     vi.stubGlobal("fetch", (input: string | URL | Request, init?: RequestInit) => {
...       if (new URL(String(input)).pathname === "/research/threads") {
...         return delayed.promise.then(() => json({ threads: rows, total: 1, limit: 50, offset: 0 }));
...       }
...       return fetchMock(input, init);
...     });
...     window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "same");
...     await mountShell();
...     if (edit) {
...       await setSelect(select("Model")!, "gpt-5.6-sol");
...       await setSelect(select("effort")!, "low");
...     }
...     delayed.resolve();
...     await flush();
...     const title = document.querySelector(".research-conversation-title")?.textContent;
...     const saved = window.sessionStorage.getItem("arkscope.aiResearch.activeThreadId");
...     await setTextarea("Question after history has loaded");
...     await click(button("Send")!);
...     const posts = fetchMock.mock.calls.filter(([input, init]) =>
...       new URL(String(input)).pathname === "/research/runs" && init?.method === "POST");
...     expect(posts).toHaveLength(1);
...     const body = JSON.parse(String(posts[0][1]?.body));
...     console.log(JSON.stringify({ diagnostic: "cold-restoration", edit, title, saved,
...       sameThread: body.thread_id === "same", model: body.model, effort: body.effort }));
...     expect(title).toBe(edit ? "New conversation" : "Same conversation");
...     expect(saved).toBe(edit ? null : "same");
...     expect(body.thread_id === "same").toBe(!edit);
...   });
... `;
... const marker = 'describe("Research workspace contracts", () => {';
... const ctx = await startVitest("test", ["src/ResearchWorkspace.test.tsx"], {
...   config: false, watch: false, cache: false,
...   testNamePattern: "review cold saved-thread hydration", reporters: ["default"],
...   setupFiles: ["src/test/setupI18n.ts"], environment: "node",
...   deps: { optimizer: { client: { enabled: false }, ssr: { enabled: false } } },
... }, {
...   configFile: false, envFile: false,
...   plugins: [{ name: "report-only-diagnostic", enforce: "pre", transform(code, id) {
...     if (id.split("?")[0].endsWith("/src/ResearchWorkspace.test.tsx")) {
...       if (!code.includes(marker)) throw new Error("diagnostic insertion marker missing");
...       return code.replace(marker, marker + extra);
...     }
...   } }],
... });
... await ctx.close();
... '''
>>> result = subprocess.run(
...     ["/home/hyl/.nvm/versions/node/v22.14.0/bin/node", "--input-type=module", "-e", node_program],
...     cwd="/tmp/arkscope-task-route-authority/apps/arkscope-web",
...     env={"PATH": "/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"},
...     text=True, capture_output=True, timeout=60,
... )
>>> print(result.returncode)
0
>>> records = [json.loads(line[line.index("{"):]) for line in result.stdout.splitlines() if '"diagnostic":"cold-restoration"' in line]
>>> print("\n".join(json.dumps(record, separators=(",", ":")) for record in records))
{"diagnostic":"cold-restoration","edit":false,"title":"Same conversation","saved":"same","sameThread":true,"model":"gpt-5.6-luna","effort":"xhigh"}
{"diagnostic":"cold-restoration","edit":true,"title":"New conversation","saved":null,"sameThread":false,"model":"gpt-5.6-sol","effort":"low"}

```
