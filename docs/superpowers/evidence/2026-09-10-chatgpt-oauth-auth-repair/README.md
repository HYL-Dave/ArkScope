# ChatGPT OAuth Auth And Recovery Repair

Base: local `master` at `381552b4`. Repair branch:
`codex/chatgpt-oauth-auth-repair`. Not merged or pushed; App not restarted.

## Incident And Scope

The user supplied a provider 401 stating that its access token had expired,
then reported successful AMD card generation after signing in again with the
same ChatGPT OAuth / `gpt-5.6-luna` / `max` route. This establishes a recovered
login failure, not a model/effort incompatibility. The contemporaneous plan
upgrade may be related, but the old token was not inspected and causation is
unproven. No live call or production credential/store read was performed for
this repair.

Separate offline reproduction found that OpenAI SDK ambient
`OPENAI_CUSTOM_HEADERS` can replace or duplicate an OAuth client's selected
Authorization header. This is a real defect, **not an established cause of the
user's incident**. The earlier API-key header-pin repair did not cover these
OAuth constructors; prior broad wording must not be read as proof it did.

Changes:

- Reuse the existing API-key auth-header policy for ChatGPT fixed structured
  output (cards/content translation), AI Research and Settings probes.
  Pin the selected bearer and remove alternate X-Api-Key headers, including
  case variants. Keep endpoint, non-auth custom headers, model, effort,
  retry configuration and refresh policy unchanged. Probe destinations remain
  explicit, including the existing public-API negative probe.
- Preserve the existing typed subscription `reauth_required` classification
  through the card HTTP response. Public detail is limited to code/task and
  the captured provider/model/effort/auth_mode, never provider-controlled text
  or token material. No failed card is stored and no replacement request runs.
- Show localized sign-in guidance with navigation to Provider settings.
  Hide the futile immediate Retry for this code; other errors keep their
  existing behavior. The App retains one transient, ticker-bound card draft
  when the user takes this explicit recovery action. Returning to that ticker
  restores question, news window, maximum articles, expanded controls and
  stance; another ticker cannot consume it. Restoration consumes the draft
  after initialization, never during React render, and does not resubmit.
  No credentials/model/effort are stored with it, no browser/DB persistence is
  added, and a renderer restart discards it. A new generation uses the then
  current route; delayed profile defaults cannot overwrite the restored stance.
  Restored-draft submission (including Enter) waits for the profile read. A
  failed read leaves the draft intact and offers the existing profile Retry.

Lifecycle Investigation's separate OpenAI client already removes ambient
custom headers and is covered as an unchanged positive control. Spark's
app-server adapter, Claude SDK transport, model routing, cache/session design
and production schemas are not changed.

## Verification

All backend verification uses a credential-stripped network namespace with
only loopback and an `ENETUNREACH` external probe. MockTransport tests execute
the actual installed SDK serialization, using synthetic credentials only.

| Check | Result |
| --- | --- |
| Pre-change existing backend focus | 271 passed |
| New backend RED | 25 failed, 10 passed; wrong bearer / lost error code |
| New UI RED | 2 failed; missing localized sign-in guidance |
| Post-change backend focus | 381 passed |
| Full backend `tests/` | 7,628 passed / 12 skipped / 3 existing edgar warnings |
| Full frontend | 1,835 passed / 126 files |
| Typecheck and production build | Passed; existing Vite chunk-size warning |
| Actual frontend fetch/error decoding/navigation | 8 synthetic browser cases passed |
| In-memory auth-pin removal | 24 failed, 11 passed |
| In-memory error-classification removal | 1 failed, 34 passed |
| Non-mutated final focus | 35 passed |
| Shell recovery round trip RED / GREEN | 4 missing-draft failures, then all 4 passed |
| Delayed/failed-profile submission RED / GREEN | 2 premature-submit failures, then both passed |
| Card/shell/ticker frontend focus after recovery fix | 62 passed |
| Independent scoped review | Both P2 recovery findings closed; final scoped review has no remaining findings |

The wire matrix covers four consumers (fixed output, research, subscription
probe and public-API negative probe), four ambient-header shapes, and 200/401
responses. Each checks exactly one request, selected bearer, destination and
unchanged model/effort. The HTTP integration checks 401 vs 403/429 with the real
SDK: only 401 becomes sign-in recovery, and all send once with no stored card.
Existing API-key OpenAI/Anthropic owners are included in the broader focus.

Independent review initially found that the new recovery action unmounted
the card and lost its inputs. The original test preserved input only before
navigation; the preview merely recorded the target. That P2 was not ignored:
`AICardRecovery.test.tsx` exercises the actual App -> TickerDetail -> AICard
unmount/return path (unrelated Home/Settings/read services are fixtures), in
normal and StrictMode with and without another-ticker detour. It checks
restored input/options/stance, no browser-storage write or automatic request,
an explicit retry with the same inputs and no later resurrection of a consumed
draft. The first independent review also ran 163 focused backend tests and
found no other issue. Its second review found that early submission could still
omit the restored stance while the profile read was pending. Two deferred-read
owners now cover click/Enter, delayed success, failed read and explicit Retry.
Both initial findings remain distinct from corrected acceptance.
The final reviewer inspected the corrected gate and deferred-read tests and
reported no remaining finding; the 62-test focus and 1,835-test full frontend
results were run by the implementer, not independently rerun by that reviewer.

Browser cases cover zh-Hant/en, desktop 1280x900/mobile 390x844 and diagnostics
off/on. They use the actual AICard component and API decoder, synthetic 502
responses, the real page container/styles, a local isolated Vite and blocked
external networking. One submission, readable guidance, contained action,
no horizontal overflow/page errors and the Provider navigation target are
checked. Reproducible scripts live here; generated results/screenshots are
under the repair worktree's `tmp/chatgpt-oauth-auth-repair/`.

Verification corrections retained: an initial unscoped `pytest -q` collected
historical evidence scripts and failed collection (obsolete imports/duplicate
module names); the product suite is explicitly `pytest -q tests`. Initial full
frontend runs exposed the four expected locale-inventory count updates for
the one added string. The first browser fixture omitted the real `.main`
container; this was corrected and a readable-width assertion added before
counting final browser acceptance. No product CSS or archived script was
changed to hide those harness failures.

## Reproduce

From the repair worktree, with the project virtualenv and existing frontend
dependencies:

```sh
python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests
npm run test --workspace apps/arkscope-web -- --run
npm run build --workspace apps/arkscope-web
python docs/superpowers/evidence/2026-09-10-chatgpt-oauth-auth-repair/browser_check.py
python docs/superpowers/evidence/2026-09-10-chatgpt-oauth-auth-repair/mutation_check.py baseline
python docs/superpowers/evidence/2026-09-10-chatgpt-oauth-auth-repair/mutation_check.py ambient_auth
python docs/superpowers/evidence/2026-09-10-chatgpt-oauth-auth-repair/mutation_check.py lost_reauth_code
```

Mutation scripts change only that test process's memory, not source files;
they return success only for the expected pytest outcome. Linux namespace
tools and Playwright Chromium are test-harness dependencies, not new product
or packaging requirements.

## Hand Test

Continue the [four-task checklist](../../plans/2026-09-09-task-route-authority-hand-test.md).
The initial card-generation step is already user-confirmed for Luna/max.
Translate that new card, check cached reads and explicit retranslation, then
test Research with one short follow-up and navigation. Last, inspect the
Lifecycle Investigation launch tuple and run one investigation as needed;
applying a tracking change remains a separate deliberate action.

Do not infer provider-attested model identity or cache hits from speed or
prose. Receipts describe the selection ArkScope sent; existing transport
validation remains unchanged. Do not require an account upgrade or an
exhaustive paid model matrix to continue these checks.
