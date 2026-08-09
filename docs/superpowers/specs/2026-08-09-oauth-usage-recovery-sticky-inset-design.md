# OAuth Usage Recovery and Settings Sticky Inset Design

> **Status:** DRAFT; USER-APPROVED DIRECTION; INDEPENDENT DESIGN RE-REVIEW
> PENDING; IMPLEMENTATION NOT AUTHORIZED
>
> **Date:** 2026-08-09
>
> **Grounding base:** `814ef2edd1b6aa66499145e1a9109d05f5fb0d89`
>
> **Scope:** repair the ChatGPT account-usage launcher seam, separate local
> cache-read failures from provider synchronization outcomes, add an explicit
> cost-labeled Anthropic quota probe, and remove the Settings sticky-tab top
> inset. This document does not authorize product or test edits.

## 1. Purpose

The OAuth lifecycle and Settings navigation slices are live, but the first
host-level use exposed four bounded defects:

1. ChatGPT account sync rejects the reviewed Codex CLI even though its version
   is correct, because executable resolution loses the NVM directory that owns
   `node`.
2. The provider row renders cached-read transport failures and backend sync
   failures as the same `cached_read_failed` condition. A transient first read
   can remain stuck for the renderer session, and the copy claims an older
   observation is displayed even when none exists.
3. Anthropic quota is captured passively during a normal Claude request, but
   the row has no explicit manual way to obtain a fresh observation. The user
   accepts the small subscription cost of a clearly labeled, button-triggered
   probe; hidden page-load or preflight probes remain forbidden.
4. The Settings workflow row is sticky relative to `.main`, but `.main` owns a
   20-pixel top padding. At deep scroll, content remains visible in the gap
   above the row, so the row is not visually attached to the scrollport top.

This is a repair slice. It does not redesign credential lifecycle, account
quota semantics, Settings caching, model routing, or the future Signals
product.

## 2. Grounded facts

### 2.1 Live observations are not re-login evidence

The user restarted the desktop application and still observed both the
ChatGPT Plus and Claude subscription rows reporting:

`cached_read_failed; still displaying the last confirmed observation`

The active Claude and ChatGPT credentials remain locally `ready` and
`available=true`. Direct local cached account-usage GETs for the two rows have
also returned HTTP 200 with a valid typed body and no snapshot. These facts do
not prove that every renderer request succeeds, but they rule out treating
re-login as the default repair.

The UI symptom therefore remains a local read/synchronization truth problem.
No implementation in this slice may delete credentials, refresh tokens, or
force a browser login as a side effect of account-usage recovery.

### 2.2 Codex launcher identity is destroyed before execution

The installed command is:

```text
/home/hyl/.nvm/versions/node/v22.14.0/bin/codex
  -> ../lib/node_modules/@openai/codex/bin/codex.js
```

`codex --version` returns the adapter's exact allowlisted output,
`codex-cli 0.147.0`.

`CodexAccountUsageAdapter._resolve_executable()` currently calls
`Path.resolve()`. The returned path is the JavaScript target under
`lib/node_modules`, not the launcher under the NVM `bin` directory. The
adapter's isolated `PATH` is then built from the resolved target parent plus
`/usr/bin:/bin`. The target begins with `#!/usr/bin/env node`, but that `PATH`
does not contain NVM's `node`; the command exits 127 with an interpreter-not-
found diagnostic.

`_verify_version()` maps every non-zero version command to
`version_incompatible`. It therefore reports a false version mismatch for a
correctly allowlisted CLI. The app-server spawn inherits the same broken
invocation boundary.

### 2.3 The frontend collapses independent failure channels

`ProviderSection.tsx::AccountUsageView` currently computes one `syncError`:

- backend `sync_status="failed"` yields its `sync_error_code`; otherwise
- a failed cached GET becomes the synthetic `cached_read_failed` code.

The local state has only `loading | loaded | failed`. A cached GET exception
and a sync POST HTTP exception both write that same failed state. The rendered
copy then says the last observation is still shown even when `snapshot` is
null. Claude rows have no account-usage action, so one failed initial read has
no local recovery affordance.

The backend already distinguishes a successful HTTP response containing a
typed failed synchronization from a transport-level inability to reach the
sidecar. The frontend discards that distinction.

### 2.4 Anthropic exposes two different observation paths

The live Claude execution driver already receives typed `RateLimitEvent`
objects and stores an allowlisted, credential-bound snapshot with
`source="claude_rate_limit_event"`. That passive path must remain the normal,
zero-extra-request path.

A user-authorized live probe on 2026-08-09 proved that the local
`claude_code_oauth` token type can obtain the same unified rate-limit headers
from one bounded Messages request:

```python
client = Anthropic(
    auth_token=token,
    api_key=None,
    timeout=20.0,
    max_retries=0,
)
raw = client.messages.with_raw_response.create(
    model="claude-sonnet-5",
    max_tokens=8,
    messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    extra_headers={"anthropic-beta": "oauth-2025-04-20"},
    system=[{
        "type": "text",
        "text": "You are Claude Code, Anthropic's official CLI for Claude.",
    }],
)
```

The exact one-shot probe script was 147 lines / 4,735 bytes with SHA-256
`18bc30a82dbf719a9332def3a5e1b649d5e98ff96ca54d06ef5477c61abc65bd`.
Its redacted JSON artifact at
`/tmp/arkscope-anthropic-oauth-wire-probe-20260809.json` has SHA-256
`36fa0d9c588b2a831caa651f05b8a37b75f4012fe44f003f10ea12d5798901d8`.
At `2026-08-09T12:58:03Z` it recorded exactly one request, HTTP 200, no
exception, and `wire_shape_accepted=true`. The allowlisted response fields
reported five-hour utilization `0.05` with reset `2026-08-09T17:00:00Z`,
seven-day utilization `0.14` with reset `2026-08-14T06:00:00Z`, overall status
`allowed`, and overage `rejected` with reason `org_level_disabled`. The
redacted artifact contains no response body, generated text, token, account
identity, or unfiltered headers; the fixed request shape is documented above.
This is dated wire-shape evidence, not an implementation artifact or
permission for automatic probes.

The relevant response headers include direct five-hour and seven-day
utilization/reset fields plus overage status/reason. A quota-rejected 429 can
also carry those headers and is then an account observation, not merely a
generic failure.

This does not contradict the earlier proof that a setup token cannot be passed
as an Anthropic `x-api-key`. `auth_token` plus the reviewed OAuth beta and
Claude Code identity is a different authentication shape. Existing authority
text that says Claude subscription traffic must *never* use a raw Messages
request is therefore overbroad for this narrow, user-triggered telemetry use.
It must be corrected during implementation without changing the Agent SDK
research transport.

### 2.5 The sticky gap is padding ownership, not z-index

The current scroll owner is:

```css
.main {
  padding: 20px;
  overflow: auto;
}
```

The Settings workflow row is `position: sticky; top: 0`. It sticks to the
content edge inside that top padding, leaving the padding visible above it.
Increasing z-index, adding a shadow, or masking the gap cannot make the row
occupy the scrollport top.

At the existing `max-width: 760px` breakpoint, `.main` top padding becomes 12
pixels. The same ownership defect therefore exists at both supported viewport
classes; the responsive transfer must preserve 20 pixels on desktop and 12
pixels on mobile before scrolling, while leaving zero inset above the sticky
row after scrolling.

The user-supplied 1201 x 803 screenshot is:

| Screenshot | SHA-256 |
|---|---|
| `Screenshot from 2026-08-09 19-40-23.png` | `038e7a235102171c576a2ccb2eec3997ba4c98ad873ec24ac656acf851d857e2` |

It shows content exposed between the viewport top and the sticky workflow row
after scrolling.

### 2.6 Current identity boundary

These are grounding identities, not future implementation targets. The
implementation plan must re-read them from its exact base and pre-register all
node additions, removals, and protected paths.

| Path | Lines | SHA-256 |
|---|---:|---|
| `src/auth_drivers/codex_account_usage.py` | 614 | `4ec1d1989b132b198d4e1367575df360adc9a97a1e51899215e242cfb3302d09` |
| `src/auth_drivers/oauth_status.py` | 600 | `6b8bd7c9b726b4e53a90ff50bb91a5a80807d0cf1c74230ce1ece1d0a278ef1c` |
| `src/auth_drivers/claude_code_sdk_driver.py` | 849 | `cb04433a8db12402b56120aa3432ea7ed0a1615262e29e1c2ca53f7652052ead` |
| `src/auth_drivers/claude_oauth_probe.py` | 80 | `45b0725b649d3ec01b2372f320ac55095eab1ff62408e419408d75ac6e3dcd12` |
| `src/api/dependencies.py` | 423 | `bb88908670fba3c108c4aed7cb86ef6465d0cd19695deb2ee7bee281133e12d0` |
| `src/api/routes/config_routes.py` | 1,262 | `e00571e8831e5508a411dc4cd6b824aab6ec78be7e1e67064ce9b861193ef573` |
| `apps/arkscope-web/src/settings/ProviderSection.tsx` | 1,727 | `ef4de519ca714c4a48239a40d146451c5998a9d482c35e99d8d19414fdd3aaf8` |
| `apps/arkscope-web/src/settings/settingsReadCache.ts` | 522 | `93a08aa4c16dabf105df76ea58d07485c6acbdde0544ed75e2bd6bc366ff8d4e` |
| `apps/arkscope-web/src/settings/settings.css` | 218 | `486162ee69ea7b471ae6c481869a1baa2378cedb7890473dffbc3551a37a9dbe` |
| `apps/arkscope-web/src/Settings.tsx` | 1,133 | `7e776b062de6b7f8ae6ece53347671440a5e2154af799981c800a982d7fe2d98` |
| `tests/test_subscription_account_usage.py` | 666 | `a6113cacdd15629bca5a5bf859d90de93acd2a7b44cf0fa08b75870f71c93c68` |
| `tests/test_claude_code_sdk_driver.py` | 1,025 | `5f1cdbf4902890b4d1fe61573377bf0334c7f51691a2a9c4ceb0259f06f77c2d` |
| `tests/test_claude_oauth_probe.py` | 100 | `a2d4d2a3848da622b27f20b722f36912dec40230cd1576cb87eb34ff358355c6` |
| `apps/arkscope-web/src/ProviderSection.test.ts` | 878 | `ba2c63b433c53b3a342bf309f806b897b78d433e28087e3b0decbb3dc8fdbe80` |
| `apps/arkscope-web/src/SettingsCss.test.ts` | 117 | `8d195d8f73c05ddce723d067a01c86abd7bda142bfa26a361fdf440278761fef` |
| `docs/design/LLM_AUTH_DRIVER_PLAN.md` | 735 | `db798f6816c5047e266ee9c77fcce045bdec9aa53d4f3224594129af0e4d88c3` |

The inherited reviewed identities are:

- backend collection: `4,527` nodes,
  `4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d`;
- backend runtime: `4,488 passed / 39 skipped / 0 failed`;
- frontend collection: `98 files / 1,123 tests`,
  `9262d7b15a926d7eeb60952e4c351c6c9b944772904fdb82438c62a2a51f6c1c`
  decoded node stream;
- frontend focused Settings collection: `221` tests,
  `a2c20d3607e5fd48982b4e1620089a7b59ee7346c23fc2d2709ec2935bdfe16f`
  decoded node stream.

The plan must reproduce the complete frontend hashes from the pinned decoded
normalizer. None of these design-time identities may be carried forward when
the implementation base differs; they must be re-derived from exact bytes.

## 3. Locked decisions

### LD 1 - Re-login is not a recovery shortcut

Account-usage read or sync failures do not mutate OAuth lifecycle state. They
must not delete a token, mark a ready credential `reauth_required`, start a
login, or hide a credential.

Only the existing lifecycle authority may decide that reauthentication is
required. A manual account probe can report a typed provider authentication
rejection, but that is evidence for the user and lifecycle owner to interpret;
it does not rewrite lifecycle state inside this slice.

### LD 2 - Preserve launcher and target identities

The Codex adapter owns two distinct paths:

1. **launcher path:** the absolute path selected by `shutil.which()` or the
   explicit executable argument, without symlink resolution; and
2. **target path:** a bounded canonical path used for inspection only.

Both must be validated. The launcher remains the path passed to `Popen`.
The isolated `PATH` contains, in order, the launcher directory, the resolved
target directory when different, and the reviewed system directories. It does
not inherit arbitrary user `PATH` entries.

For an `env` shebang, the adapter inspects a bounded first line, accepts only a
closed interpreter-name syntax, and proves the interpreter is available in the
isolated `PATH` before running `--version` or app-server. A missing interpreter
returns `interpreter_unavailable`.

`version_incompatible` is reserved for a version command that executed
successfully and returned a well-formed version different from the exact
allowlist. Spawn failure, timeout, interpreter absence, non-zero launcher exit,
oversized output, and malformed output retain their own typed unavailable or
protocol classes; they may not be relabeled as version skew.

### LD 3 - Cached read and active sync are separate state machines

The frontend tracks at least these independent facts per local credential:

- cached GET state: `idle | loading | loaded | failed`;
- cached GET error code, when failed;
- last decoded `OAuthAccountSyncView`, if any;
- active sync transport state: `idle | sending | transport_failed`;
- active sync transport error code, when failed; and
- backend `sync_status` plus backend `sync_error_code` from a decoded response.

One state may not overwrite another. A failed revalidation preserves a prior
validated snapshot and its original `observed_at`. A failed first read has no
snapshot and must say so. A decoded HTTP 200 with `sync_status="failed"` is not
a transport failure; a POST that never yields a decoded response is not a
backend adapter failure.

The UI must never display `cached_read_failed` for an active sync POST failure.

### LD 4 - Local cached-read recovery is bounded and provider-free

When a visible credential's first cached GET fails, the frontend performs
exactly one automatic retry after 1,000 ms. Credential change, unmount, or a
successful newer generation cancels or supersedes it. There is no repeating
timer.

Every OAuth account row exposes a local **Retry local read** action after a
cached-read failure. It calls only the cached GET. It never contacts OpenAI or
Anthropic and never consumes model quota.

Regaining focus may revalidate under the existing five-minute cache policy,
but it may not create a retry loop. All retry completions remain generation-
checked so an older credential cannot repopulate a switched row.

### LD 5 - ChatGPT synchronization policy remains control-plane only

The existing ChatGPT visibility/focus/login synchronization policy remains in
force. `account/rateLimits/read` and `account/usage/read` do not start a thread
or turn. The adapter fix changes only launcher correctness and typed error
classification.

The ChatGPT row retains a manual sync button with the existing ten-second
cooldown and credential single-flight behavior. A successful sync replaces the
exact credential cache key. A failure preserves the last good observation.

### LD 6 - Anthropic manual sync is one explicit model request

The Claude row gains a manual action labeled to disclose cost, for example:

> Sync usage (uses a small amount of subscription usage)

No Anthropic probe occurs during page load, idle warmup, cached GET, focus,
preflight, credential listing, or timer polling. Passive `RateLimitEvent`
capture remains enabled and preferred.

A present or future preflight surface may read and display the stored snapshot
with its source and `observed_at`; it may not turn that read into a hidden
probe. Wiring quota into a separate preflight UI is not part of this repair.

One accepted click performs exactly one bounded Messages request:

- token read from the existing `claude_code_oauth` token-store record;
- `Anthropic(auth_token=token, api_key=None)`;
- reviewed OAuth beta `oauth-2025-04-20`;
- the exact Claude Code identity system block as the first system block;
- one fixed minimal user message;
- no tools, streaming, retry, model fallback, or agent loop;
- `max_tokens=8`;
- ten-second per-credential cooldown and single-flight; and
- hard timeout with resource cleanup.

The implementation plan pins one reviewed probe model from the capability
registry. At this grounding base that model is `claude-sonnet-5`. If it is no
longer valid at implementation time, the plan stops for a model-identity
amendment; runtime must not try multiple models.

### LD 7 - Unified headers are the observation authority

The manual adapter reads only the allowlisted unified rate-limit headers:

- overall, five-hour, and seven-day status;
- five-hour and seven-day utilization;
- five-hour and seven-day absolute reset timestamps;
- representative claim when it matches the reviewed limit-id syntax; and
- overage status and bounded overage-disabled reason.

Utilization is validated as a finite number in `[0, 1]` and converted to the
existing direct **used percent** representation. Reset values are validated
absolute Unix seconds. Missing fields remain unknown; they are not inferred as
zero or unlimited.

A 2xx response with valid headers records an observation. A quota-rejected 429
with valid unified headers also records an observation whose rate-limit status
is rejected. A 429 without those headers is
`quota_headers_unavailable`, not an empty quota snapshot. Authentication,
entitlement, model, SDK, timeout, and transport failures remain distinct typed
errors and preserve the last good snapshot.

The manual source is the new exact value `anthropic_oauth_probe`. It may not be
mislabeled `claude_rate_limit_event`. Both sources write through the same
validated, credential-bound observation store and use the passive driver's
existing `sha256(provider + NUL + auth_mode + NUL + credential_id)` fingerprint
shape.
V1 stores each observation atomically; it does not merge missing fields across
manual and passive sources. A missing field remains unknown rather than being
borrowed from an older observation with different provenance.

No response body, generated text, prompt, raw header map, access/setup token,
account email, raw account id, or unredacted exception enters SQLite, logs,
frontend state, or evidence. The response body is discarded after bounded
cleanup.

### LD 8 - Provider adapters stay narrow

The account sync service dispatches by the existing explicit provider/auth
mode pair:

- `openai/chatgpt_oauth` -> Codex control-plane adapter;
- `anthropic/claude_code_oauth` -> explicit manual Messages-header adapter;
- other modes -> typed `unsupported_auth_mode`.

The Anthropic adapter is account telemetry only. It does not replace
`AnthropicClaudeCodeSdkDriver`, alter research execution, discover models, or
become a generic Messages client.

The cached GET remains provider-free. Credential inventory remains network-
free. Only the explicit POST can use the Anthropic manual adapter, while the
existing ChatGPT automatic policy may use its non-model control-plane adapter.

Account-usage control belongs only to subscription authentication modes.
`api_key`, `api_key_pool`, and environment-derived API-key credentials never
render this usage panel and never trigger either account-usage adapter. Their
metered billing and transient request-rate headers are different facts and are
not estimated, persisted, or presented as subscription quota by this slice.

The manual adapter exposes a closed minimum error vocabulary:

| Error code | Evidence |
|---|---|
| `missing_token` | the selected token-store record has no usable token |
| `sdk_incompatible` | the installed SDK cannot express or decode the pinned call shape |
| `provider_auth_rejected` | provider returned 401 |
| `provider_access_rejected` | provider returned 403 |
| `quota_headers_unavailable` | provider returned quota rejection without valid unified headers |
| `provider_request_rejected` | another typed provider 4xx response |
| `transport_error` | no HTTP response was obtained |
| `timeout` | the bounded request timed out |
| `credential_changed_during_sync` | token generation changed before snapshot commit |
| `sync_busy` | the credential single-flight/lock could not be acquired in bounds |

Unknown exceptions become `adapter_unavailable`; raw exception text never
crosses the service boundary. Implementations may add a more specific code only
through a reviewed amendment and a dedicated RED owner.

### LD 9 - Error copy describes evidence, not guesses

The visible states are closed and source-specific:

| Condition | Required meaning |
|---|---|
| cached GET failed, no snapshot | local cached observation could not be read; no confirmed observation is available |
| cached GET failed, snapshot retained | local revalidation failed; show the retained observation and its exact `observed_at` |
| sync POST transport failed | the local service did not return a decoded result; provider outcome is unknown |
| decoded backend sync failed | show the stable backend error code and retain any older observation |
| Anthropic has no passive/manual event yet | usage unknown; normal Claude requests update passively |
| Anthropic manual action available | disclose that one minimal request may consume a small amount of subscription usage |

No message says an old observation is displayed unless a snapshot is actually
present. `unknown` is not rendered as zero, unlimited, healthy, or exhausted.

### LD 10 - Remove the sticky inset structurally

Settings becomes a zero-top-padding variant of the shared `.main` scroll
owner. The responsive initial breathing room moves to the Settings
`PageHeader` area: 20 pixels on desktop and the existing 12 pixels at
`max-width: 760px`. The unscrolled page therefore keeps its current visual
spacing while the sticky workflow row reaches the actual scrollport top at
both viewport classes.

The implementation uses a Settings-scoped class or wrapper. It does not change
global `.main` padding for other pages. Negative margins, translated sticky
rows, pseudo-element masks, box-shadow camouflage, and duplicate overlay bars
are forbidden.

The existing shared sticky offset still owns workflow-row height, directory
rail top, and section `scroll-margin-top`. Active-only panel mounting and the
bounded Settings cache remain unchanged.

### LD 11 - Role and sequencing are explicit

This spec is authored by Codex. After independent design review returns GREEN,
the user/Fable implementation side owns the RED-first plan and product edits;
Codex performs an independent code/evidence review and does not patch the
implementation under review unless the user explicitly changes roles.

Tranche B proceeds before this repair. Its reviewed relative ledger
(`-138/+18`) remains frozen, and rebase amendment `5be77be2` already derived
its absolute identities against master `814ef2ed`; Task 0 then began and
produced canonical native evidence before its no-tail owner stop. Invalidating
that work would require a second Tranche B rebase and Task 0 replay. Therefore
this repair remains docs-only until Tranche B is merged and closed, then this
spec and its future implementation plan re-ground once against the resulting
master. This sequencing ruling supersedes the pre-`5be77be2` statement that
Tranche B would wait for this repair.

## 4. Required RED contracts

Implementation begins with independent failing nodes for at least:

1. an NVM-style `codex -> ../lib/.../codex.js` symlink with
   `#!/usr/bin/env node` succeeds when the launcher directory owns `node`;
2. removing the launcher directory from isolated `PATH` turns that node RED;
3. missing shebang interpreter returns `interpreter_unavailable`, while a
   successful mismatched `--version` returns `version_incompatible`;
4. app-server is launched through the preserved launcher, not the resolved JS
   target;
5. cached GET failure without a snapshot does not claim retained evidence;
6. cached GET failure with a snapshot preserves and timestamps it;
7. sync transport failure differs from decoded backend sync failure;
8. one initial cached GET failure schedules exactly one local retry, and
   unmount or credential change cancels it;
9. manual local retry performs one GET and zero sync POST/provider requests;
10. Claude page load, focus, idle warmup, and cached read perform zero Messages
    requests;
11. one Claude manual click performs exactly one request with the pinned model,
    `max_tokens=8`, OAuth beta, identity block, no tools, and no fallback;
12. 2xx unified headers produce five-hour/seven-day observations;
13. 429 with unified headers produces a rejected observation, while 429
    without them produces `quota_headers_unavailable` and no fabricated
    snapshot;
14. passive and manual Claude observations retain distinct source values;
15. malformed numbers, reset values, status, and overage reason are rejected or
    nulled according to the existing typed validator, never coerced to zero;
16. raw token, account id, email, response body, output text, and raw headers
    are absent from persisted rows, API payloads, logs, and artifacts;
17. at deep scroll, the workflow row's top equals the `.main` scrollport top at
    desktop and mobile viewports;
18. at initial scroll, PageHeader spacing remains visually equivalent to the
    pre-fix page;
19. directory rail, focused anchors, and mobile navigation appear below the
    sticky row with no overlap or horizontal overflow; and
20. inactive Settings panels remain unmounted and no cache/polling semantics
    change.

Every mutation changes a live semantic owner. Required mutations include:

- resolving the launcher before constructing `PATH`;
- mapping interpreter absence back to `version_incompatible`;
- collapsing cached-read and sync-transport state;
- enabling Anthropic probe from idle warmup;
- retrying a second Anthropic model after rejection; and
- restoring Settings top padding without transferring the initial inset.

An owning RED node that remains green makes the mutation inadmissible.

## 5. Live acceptance

### 5.1 ChatGPT host acceptance

On the actual NVM installation:

1. prove launcher, target, interpreter, and exact Codex version without logging
   home-directory token content;
2. invoke the account sync from ArkScope's real adapter boundary;
3. obtain a decoded account observation or a truthful account-level quota
   result without starting any thread or turn;
4. prove no `thread/*` or `turn/*` method appeared; and
5. prove the child process group and temporary `CODEX_HOME` are gone.

This live check is host-context evidence and should be run by the implementation
side outside the known restrictive sandbox when needed.

### 5.2 Anthropic manual acceptance

With the user's explicit test authorization:

1. open the Claude credential row and confirm that page load emitted zero
   Anthropic probe requests;
2. click the cost-labeled sync action once;
3. prove exactly one Messages request was sent;
4. show direct five-hour/seven-day usage and reset values, or a truthful typed
   exhausted/unavailable outcome from the response;
5. prove a second click inside cooldown emitted no request;
6. prove passive `RateLimitEvent` remains functional on a later normal request;
   and
7. inspect artifacts for zero secret, raw header, prompt, or generated-text
   retention.

Live testing may consume a small amount of subscription usage. It may not be
performed before the explicit button path and cost copy exist.

### 5.3 Browser acceptance

Use hermetic Playwright at minimum at `1322x777` and `390x844`:

- inspect original-resolution screenshots at page top and after deep scroll;
- assert workflow-row top equals the Settings scrollport top within one CSS
  pixel after deep scroll;
- assert no content pixels or DOM element occupy a strip above the row inside
  the scrollport;
- verify the initial PageHeader inset is unchanged;
- verify all nine directory entries, exact-anchor focus, group-top navigation,
  one mounted tabpanel, and no overlap/clipping; and
- verify Claude automatic request count is zero until the explicit button is
  clicked.

DOM geometry is the admission authority. Screenshots are required supporting
evidence, not a substitute for geometry assertions.

## 6. Out of scope

- changing OAuth login, refresh grants, token-store schema, or credential DB
  schema;
- changing the Claude Agent SDK research driver or OpenAI research execution;
- automatic Anthropic quota probing, periodic provider polling, or preflight
  model calls;
- account billing prediction, scraping private dashboards, or claiming the
  headers are a monetary balance;
- model catalog refresh, default-model changes, or trying multiple models;
- redesigning Settings groups, sections, directory order, cache resource
  policy, or active-only mounting;
- Tranche B implementation, Signals research, Financial Datasets policy,
  fundamentals scheduling, or branch cleanup; and
- rewriting historical evidence. Only current authority wording that would
  prohibit the reviewed manual OAuth wire shape is corrected.

## 7. Stop conditions

Stop and amend before continuing if any of these occurs:

1. the actual Codex launcher/version differs from the grounded host identity;
2. the launcher repair requires inheriting arbitrary user `PATH` or executing
   an unvalidated target;
3. a test uses only a fake Python executable and never exercises the real
   symlink/shebang seam;
4. any account-usage failure mutates lifecycle or starts re-login;
5. cached GET, focus, page load, or warmup emits an Anthropic Messages request;
6. one manual click can emit more than one model request or try a fallback
   model;
7. the installed Anthropic SDK cannot express the exact `auth_token`/raw-
   response contract without weakening isolation;
8. a 429 without valid unified headers is admitted as quota truth;
9. the response body, generated text, raw headers, token, email, or raw account
   id reaches storage, API, logs, or artifacts;
10. the fix changes Agent SDK execution, model routing, discovery, or defaults;
11. the sticky fix changes global page padding or relies on visual masking;
12. browser geometry differs between the DOM assertion and screenshots;
13. any Settings frozen fixture is silently updated rather than reviewed as an
    explicit contract change;
14. backend or frontend collection changes outside the pre-registered ledger;
15. a sandbox-limited host check is represented as native live evidence; or
16. direct local GET succeeds but the browser still fails after its bounded
    retry, without the actual frontend transport cause being captured and
    reviewed; or
17. Tranche B relative accounting, product code, or data is changed in this
    repair; or
18. an API-key credential renders a subscription-usage panel or triggers an
    account-usage probe.

## 8. Review and implementation order

1. Focused independent re-review of this docs-only design amendment and the
   dated one-request Anthropic wire-shape evidence.
2. Complete, independently review, fast-forward merge, and close Tranche B
   from its already reviewed `5be77be2` identity base; this repair performs no
   product edit while that line is active.
3. Rebase this docs-only repair onto exact post-Tranche-B master, re-ground all
   identities, and submit that bounded identity amendment for review.
4. User/Fable writes a RED-first implementation plan with exact backend and
   frontend node ledgers, current full identities, protected paths, mutation
   recipes, and live-test boundary.
5. Independent Codex plan review.
6. Implement Codex launcher/error typing and split frontend recovery states.
7. Implement the explicit Anthropic adapter, source type, service dispatch,
   UI copy/action, and authority wording correction.
8. Implement the Settings top-inset transfer.
9. Run mutations, complete native/frontend/browser admission, and submit one
   implementation packet for independent Codex review.
10. After GREEN, fast-forward merge and exact-master verification.
