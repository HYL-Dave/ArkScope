# Security Lifecycle Provider Authority Shadow Census Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a detached, bounded, secret-safe shadow census that measures
whether Massive and EODHD can authorize exact listing status, ticker changes,
economic successor relationships, and terminal retirement before ArkScope
changes lifecycle policy.

**Architecture:** A pure oracle/classifier consumes closed normalized provider
observations. A separate shadow-only HTTP transport gathers Massive, EODHD, and
Nasdaq evidence under an injected request boundary and a budget that cannot be
used by the production scheduler. Live execution writes only a sealed evidence
packet after a separate authorization; it never writes application databases.

**Tech Stack:** Python 3.12, dataclasses, `requests`, pytest, SQLite read-only
connections only at separately authorized inventory stages, SHA-256 evidence
binding.

**Spec:**
`docs/superpowers/specs/2026-09-04-lifecycle-provider-authority-shadow-census-design.md`

## Global Constraints

- The frozen known-case expectations are exact same-security rename
  `LC -> HAPN`; independently confirmed terminal old securities `ARCH`, `LTHM`,
  and `TA` without an acquirer alias; and active controls `AAPL` and canonical
  `SMCI`. An acquisition relation is never terminal evidence by itself.
- The closed result vocabulary is `confirmed | contradicted | coverage_limited
  | not_entitled | credential_unavailable | provider_unavailable | ambiguous`.
- Only `confirmed` is authority evidence.
- No adapter in this plan may be imported by
  `src/service/security_lifecycle_automation_scheduler.py`.
- No provider call, credential read, further production database access,
  migration, authority change, App restart, merge, or push occurs without its
  own gate.
- Provider keys come only from the active profile credential authority. Never
  source or read `config/.env` for this work.
- Live requests have zero retry, redirect, or fallback. Evidence never retains
  a secret, authorization header, key-bearing URL, raw body, account record, or
  unrelated provider row.
- Massive request starts are proactively spaced by at least 12.5 seconds to
  respect the documented Stocks Basic five-calls-per-minute limit. Pacing does
  not repeat a failed request or expand the fixed budget.
- The initial core canary permits at most 14 Massive, 2 EODHD, and 2 Nasdaq
  HTTP requests. Paid EODHD symbol history is a later independent gate.

## Completed Alpha Picks Identity Preflight

The separately authorized SQLite `mode=ro` plus `query_only` census found 118
pick rows and 106 lineages. All 118 source detail URLs were ticker-bound and
none exposed a provider article ID; the only URL/stored-symbol mismatches were
the three legacy terminal cases. A post-ingestion article link covered 89
lineages but was absent from 17, including all legacy cases. Pick dates also
collided. No implementation task may reintroduce normalized URL, article link,
or pick date as a supposedly immutable source identity. The source-membership
invariants are frozen in design section 8; their schema is selected only after
the provider census.

---

### Task 1: Closed Census Domain and Known-Case Oracle

**Files:**
- Create: `src/security_lifecycle_provider_census.py`
- Create: `tests/test_security_lifecycle_provider_census.py`
- Create: `tests/fixtures/lifecycle_provider_census/known_cases.json`

**Interfaces:**
- Consumes: normalized provider observations only; no database or network
  object.
- Produces: `CensusObservation`, `CensusCaseResult`,
  `classify_known_case(case_id, observations)`, and
  `render_census_summary(results)`.

- [ ] **Step 1: Write the frozen fixture before any adapter code**

```json
{
  "version": 1,
  "cases": [
    {"case_id": "LC", "source": "LC", "successor": "HAPN", "terminal": false},
    {"case_id": "ARCH", "source": "ARCH", "successor": null, "terminal": true},
    {"case_id": "LTHM", "source": "LTHM", "successor": null, "terminal": true},
    {"case_id": "TA", "source": "TA", "successor": null, "terminal": true},
    {"case_id": "AAPL", "source": "AAPL", "successor": null, "terminal": false},
    {"case_id": "SMCI", "source": "SMCI", "successor": null, "terminal": false}
  ]
}
```

- [ ] **Step 2: Write RED tests for the closed model and oracle**

```python
def test_lc_requires_exact_same_security_change_to_hapn():
    rows = (
        observation("massive", "listing_state", "LC", active=False),
        observation("massive", "ticker_change", "LC", successor="HAPN"),
        observation("massive", "listing_state", "HAPN", active=True),
    )
    assert classify_known_case("LC", rows).outcome == "confirmed"


def test_independently_confirmed_terminal_acquisition_never_becomes_identity_alias():
    rows = (
        observation("massive", "listing_state", "ARCH", active=False),
        observation("massive", "economic_successor", "ARCH", successor="CNR"),
        observation("massive", "listing_state", "CNR", active=True),
    )
    result = classify_known_case("ARCH", rows)
    assert result.outcome == "confirmed"
    assert result.successor is None


def test_acquisition_relation_without_terminal_state_is_not_terminal_authority():
    rows = (
        observation("massive", "economic_successor", "ARCH", successor="CNR"),
        observation("massive", "listing_state", "CNR", active=True),
    )
    result = classify_known_case("ARCH", rows)
    assert result.outcome == "ambiguous"
    assert result.successor is None


def test_ta_requires_terminal_state_without_a_successor():
    rows = (observation("massive", "listing_state", "TA", active=False),)
    result = classify_known_case("TA", rows)
    assert result.outcome == "confirmed"
    assert result.successor is None


def test_smci_provider_marker_cannot_match_exact_control():
    rows = (observation("massive", "listing_state", "SMCI*", active=True),)
    assert classify_known_case("SMCI", rows).outcome == "ambiguous"
```

- [ ] **Step 3: Run the RED tests**

Run:
`pytest -q tests/test_security_lifecycle_provider_census.py`

Expected: collection or import failure because the census module does not yet
exist.

- [ ] **Step 4: Implement the closed data model**

```python
CENSUS_OUTCOMES = frozenset({
    "confirmed", "contradicted", "coverage_limited", "not_entitled",
    "credential_unavailable", "provider_unavailable", "ambiguous",
})


@dataclass(frozen=True)
class CensusObservation:
    provider: str
    axis: str
    source_ticker: str
    successor_ticker: str | None
    active: bool | None
    stable_id: str | None
    effective_date: str | None
    complete: bool


@dataclass(frozen=True)
class CensusCaseResult:
    case_id: str
    outcome: str
    listing_state: str
    successor: str | None
    reasons: tuple[str, ...]
```

Reject unknown fields, outcomes, axes, lowercase/noncanonical tickers,
duplicate contradictory rows, and a successor without an explicit source to
successor relation. Do not infer a relation from matching issuer names.

- [ ] **Step 5: Add all positive and negative oracle owners**

Cover exact `LC -> HAPN`, terminal `ARCH`, `LTHM`, and `TA` without identity
aliases, active `AAPL`, exact `SMCI`, provider disagreement, incomplete
response, missing stable identity, and every closed outcome value. Prove a
same-security `ticker_change` and a merger conversion remain distinguishable.

- [ ] **Step 6: Run GREEN and mutation controls**

Run:
`pytest -q tests/test_security_lifecycle_provider_census.py`

Then mutate exact ticker equality to case-insensitive or punctuation-stripping
equality and confirm
`test_smci_provider_marker_cannot_match_exact_control` fails. Remove the
explicit relation requirement and confirm
`test_lc_requires_exact_same_security_change_to_hapn` fails.

- [ ] **Step 7: Commit the pure domain slice**

```bash
git add src/security_lifecycle_provider_census.py \
  tests/test_security_lifecycle_provider_census.py \
  tests/fixtures/lifecycle_provider_census/known_cases.json
git commit -m "test(lifecycle): freeze provider authority census oracle"
```

### Task 2: Shadow-Only Massive and Nasdaq Transport

**Files:**
- Create: `data_sources/lifecycle_provider_census_transport.py`
- Create: `tests/test_lifecycle_provider_census_transport.py`

**Interfaces:**
- Consumes: an injected `requests.Session`, a non-empty Massive key supplied by
  the caller, and `CensusRequestBudget`.
- Produces: `fetch_massive_listing()`, `fetch_massive_ticker_events()`,
  `fetch_nasdaq_directory()`, and secret-safe `CensusTransportFailure`.

- [ ] **Step 1: Write RED transport-boundary tests**

```python
def test_massive_events_requires_stable_identifier_and_exact_ticker_change():
    transport = transport_with_json(event_fixture("LC", "HAPN"))
    row = transport.fetch_massive_ticker_events(
        stable_id="BBG_TEST_LC", api_key="secret", budget=budget()
    )
    assert row.events == (("LC", "HAPN", "2026-06-27"),)


def test_massive_event_budget_stops_before_fifteenth_request():
    b = CensusRequestBudget(max_massive_requests=14)
    for index in range(14):
        b.reserve_massive(("listing", str(index)))
    with pytest.raises(CensusTransportFailure, match="massive_request_budget"):
        b.reserve_massive(("events", "overflow"))


def test_secret_never_appears_in_failure_or_source_locator():
    secret = "massive-secret-sentinel"
    with pytest.raises(CensusTransportFailure) as caught:
        failing_transport().fetch_massive_listing(
            "ARCH", expected_active=False, api_key=secret, budget=budget()
        )
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
```

- [ ] **Step 2: Run the RED tests**

Run:
`pytest -q tests/test_lifecycle_provider_census_transport.py`

Expected: collection or import failure because the shadow transport does not
exist.

- [ ] **Step 3: Implement a transport that cannot enter production runtime**

```python
MASSIVE_LISTING_URL = "https://api.massive.com/v3/reference/tickers"
MASSIVE_EVENTS_PREFIX = "https://api.massive.com/vX/reference/tickers/"
MAX_MASSIVE_REQUESTS = 14
MAX_NASDAQ_REQUESTS = 2


@dataclass
class CensusRequestBudget:
    max_massive_requests: int = MAX_MASSIVE_REQUESTS
    max_eodhd_requests: int = 2
    max_nasdaq_requests: int = MAX_NASDAQ_REQUESTS
    massive_requests: int = 0
    eodhd_requests: int = 0
    nasdaq_requests: int = 0
```

Use an explicit endpoint allowlist, `allow_redirects=False`, a 15-second
timeout, JSON content-type checks, exact case-sensitive ticker binding, and
only `type == "ticker_change"`. Preserve the current Nasdaq ceilings of 8 MiB
per file and 12 MiB aggregate. Give Massive an independent 1 MiB per response
and 14 MiB aggregate ceiling. Reject any unknown event type, malformed date,
duplicate stable identity, response `next_url`, or request URL containing a
credential. Do not reuse or modify production `ListingRequestBudget`.

- [ ] **Step 4: Add a structural non-integration owner**

```python
def test_shadow_transport_is_not_imported_by_scheduler():
    source = Path("src/service/security_lifecycle_automation_scheduler.py").read_text()
    assert "lifecycle_provider_census_transport" not in source
```

- [ ] **Step 5: Run GREEN and reverse mutations**

Run:
`pytest -q tests/test_lifecycle_provider_census_transport.py`

Confirm removing `allow_redirects=False`, permitting ticker identifiers for
historical events, accepting unknown event types, or raising the 14-request
budget kills a named test.

- [ ] **Step 6: Commit the Massive/Nasdaq shadow transport**

```bash
git add data_sources/lifecycle_provider_census_transport.py \
  tests/test_lifecycle_provider_census_transport.py
git commit -m "feat(lifecycle): add bounded provider census transport"
```

### Task 3: Profile-Backed EODHD Status Lane

**Files:**
- Modify: `src/data_provider_config.py`
- Modify: `src/api/routes/providers_config.py`
- Create: `src/security_lifecycle_provider_census_credentials.py`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `data_sources/lifecycle_provider_census_transport.py`
- Modify: `tests/test_data_provider_config.py`
- Modify: `tests/test_lifecycle_provider_census_transport.py`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.test.ts`

**Interfaces:**
- Consumes: generic profile provider-settings storage already used by
  `PROVIDER_FIELDS`.
- Produces: profile provider `eodhd.api_key`,
  `resolve_census_credential(store, provider)`, and
  `fetch_eodhd_symbol_sets(symbols, api_key, budget)`.

- [ ] **Step 1: Write RED credential-authority tests**

```python
def test_eodhd_census_uses_profile_value_not_ambient_environment(monkeypatch, store):
    monkeypatch.setenv("EODHD_API_KEY", "ambient-secret")
    store.set_field("eodhd", "api_key", "profile-secret")
    assert resolve_census_credential(store, "eodhd") == "profile-secret"
    assert provider_config_missing_detail("eodhd", "api_key")["provider"] == "eodhd"
    assert importable_env_vars(PROVIDER_FIELDS["eodhd"][0]) == ()
```

Also prove no generic `config/.env` import can become App authority, that the
census credential resolver reads the profile store rather than `os.environ`,
and that Settings copy exists in both languages. Do not change the project's
separate explicit shell-environment override policy in this task.

- [ ] **Step 2: Run the credential RED tests**

Run:
`pytest -q tests/test_data_provider_config.py -k eodhd`

Expected: FAIL because `eodhd` is absent from `PROVIDER_FIELDS`.

- [ ] **Step 3: Add the closed profile field without a schema migration**

```python
"eodhd": [
    FieldDef(
        "api_key",
        "EODHD_API_KEY",
        True,
        "API key",
        env_file_importable=False,
        env_file_runtime_fallback=False,
    ),
],
```

Use the existing generic provider-settings table. Do not add a second durable
store. Leave `eodhd` out of `_TESTABLE` in this slice: a generic connection
test would either use the prohibited legacy client or spend provider quota
outside the separately authorized census. Settings must report that live
validation belongs to the bounded census rather than present a test button.
Implement `resolve_census_credential()` as an exact profile-store lookup that
accepts only `massive` and `eodhd`, rejects missing/multiple fields, and never
consults `os.environ`.

- [ ] **Step 4: Write RED exact-set parser tests**

```python
def test_eodhd_active_and_delisted_sets_require_complete_requested_accounting():
    transport = transport_with_eodhd(active=[{"Code": "AAPL"}], delisted=[])
    result = transport.fetch_eodhd_symbol_sets(
        symbols=("AAPL", "TA"), api_key="secret", budget=budget()
    )
    assert result.active == ("AAPL",)
    assert result.unreported == ("TA",)
    assert result.complete is False
```

Cover active/delisted overlap, duplicate code, unexpected code, malformed row,
non-US exchange, more than two requests, redirect, oversized body, and secret
redaction.

- [ ] **Step 5: Implement only the all-plan status endpoints**

Call `/api/exchange-symbol-list/US` exactly twice with the same sorted exact
symbol manifest, `fmt=json`, and `delisted=0` then `delisted=1`. Compare every
requested symbol to returned codes. Do not implement or invoke Symbol Change
History in this task.

- [ ] **Step 6: Run backend and frontend GREEN**

Run:

```bash
pytest -q tests/test_data_provider_config.py tests/test_lifecycle_provider_census_transport.py
npm --prefix apps/arkscope-web test -- --run src/settings/settingsBackendCopy.test.ts
npm --prefix apps/arkscope-web run typecheck
```

- [ ] **Step 7: Commit the EODHD status lane separately**

```bash
git add src/data_provider_config.py src/api/routes/providers_config.py \
  src/security_lifecycle_provider_census_credentials.py \
  data_sources/lifecycle_provider_census_transport.py \
  tests/test_data_provider_config.py \
  tests/test_lifecycle_provider_census_transport.py \
  apps/arkscope-web/src/settings/settingsBackendCopy.ts \
  apps/arkscope-web/src/settings/settingsBackendCopy.test.ts \
  apps/arkscope-web/src/i18n/resources/en/settings.ts \
  apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
git commit -m "feat(providers): add profile-backed EODHD status credential"
```

### Task 4: Detached Known-Case Runner and Evidence Contract

**Files:**
- Create: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py`
- Create: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/README.md`
- Create: `tests/test_lifecycle_provider_census_runner.py`

**Interfaces:**
- Consumes: the frozen fixture, the pure classifier, injected transport, and
  caller-supplied profile credential resolver.
- Produces: `census-summary.json` and `SHA256SUMS` only when invoked after live
  authorization.

- [ ] **Step 1: Write RED dry-run and evidence tests**

```python
def test_dry_run_lists_exact_budget_without_reading_credentials(fake_resolver):
    result = run_census(mode="dry-run", credential_resolver=fake_resolver)
    assert result["maximum_http_requests"] == 18
    assert fake_resolver.calls == []


def test_packet_omits_raw_bodies_secrets_and_account_data(tmp_path):
    packet = render_packet(synthetic_results(), output_dir=tmp_path)
    text = packet.read_text()
    assert "apiKey" not in text
    assert "authorization" not in text.lower()
    assert "raw_body" not in text
    assert "account_id" not in text.lower()
    assert "user_email" not in text.lower()
```

- [ ] **Step 2: Run the runner RED tests**

Run:
`pytest -q tests/test_lifecycle_provider_census_runner.py`

Expected: FAIL because the detached runner does not exist.

- [ ] **Step 3: Implement explicit modes and hard stops**

```python
MODES = ("dry-run", "fixture-replay", "known-case-live", "universe-manifest")


def run_census(*, mode: str, credential_resolver, transport=None) -> dict[str, object]:
    if mode not in MODES:
        raise ValueError("census_mode")
    if mode in {"dry-run", "fixture-replay"}:
        return run_without_credentials_or_network(mode)
    return run_authorized_read_only(mode, credential_resolver, transport)
```

`known-case-live` must require a command-line acknowledgement containing the
exact spec digest and budget. It must refuse if the output directory exists,
if the working tree product/test files differ from the admitted commit, or if a
production database path is supplied. `universe-manifest` is read-only and
must remain separately gated.

- [ ] **Step 4: Add deterministic fixture replay**

Use digest-bound Massive/EODHD/Nasdaq synthetic payloads to produce all seven
result codes and the complete six-case table. Repeat twice and assert
byte-identical summary JSON after excluding only the explicitly supplied
observation timestamp.

- [ ] **Step 5: Add request accounting and packet sealing**

Count actual HTTP attempts before each call and body bytes after each accepted
response. Emit normalized fields only, then write SHA-256 for every packet file.
The README must state whether each provider lane executed, the exact reason for
every skipped lane, and that a negative oracle result is a successful
experiment outcome rather than a transport failure.

- [ ] **Step 6: Run offline admission**

Run:

```bash
pytest -q tests/test_security_lifecycle_provider_census.py \
  tests/test_lifecycle_provider_census_transport.py \
  tests/test_lifecycle_provider_census_runner.py \
  tests/test_data_provider_config.py
python docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py \
  --mode fixture-replay
```

Expected: all tests pass; fixture replay makes zero socket calls and reads no
credential or application database.

- [ ] **Step 7: Commit the offline runner without live output**

```bash
git add docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py \
  docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/README.md \
  tests/test_lifecycle_provider_census_runner.py
git commit -m "test(lifecycle): add detached provider census runner"
```

### Task 5: Separately Authorized Known-Case Live Census

**Files:**
- Create after execution: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/census-summary.json`
- Create after execution: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/SHA256SUMS`
- Modify after review: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/README.md`

**Interfaces:**
- Consumes: explicit user authorization for the exact admitted commit and
  18-request core budget.
- Produces: a sealed read-only known-case packet. It produces no application
  state.

- [ ] **Step 1: Stop and obtain the live provider authorization**

Report the exact code commit, spec SHA-256, admitted tests, credential providers
that will be accessed, and maximum `14 Massive + 2 EODHD + 2 Nasdaq` HTTP
requests. Do not infer authorization from approval of this plan.

- [ ] **Step 2: Run one dry-run immediately before live execution**

Run:

```bash
python docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py \
  --mode dry-run
```

Confirm zero credential reads and zero requests, then compare its manifest and
budget to the authorization.

- [ ] **Step 3: Execute exactly one live run**

Use the active profile's Massive credential and, only if Task 3 has landed and
the profile contains it, EODHD credential. Make no retry. A missing EODHD key
becomes `credential_unavailable`; do not source an environment value.

Retain the normalized local failure code for a failed request. Do not retain
provider response text. The first authorized attempt established that status
family alone is insufficient to distinguish rate limiting from entitlement or
coverage failure.

- [ ] **Step 4: Verify request and secret boundaries**

Assert observed attempts are at or below every provider budget. Scan the packet
and process diagnostics against non-secret credential fingerprints without
printing or saving the secret values. Confirm no application SQLite file was
opened writable.

- [ ] **Step 5: Evaluate without changing the oracle**

Report each case/axis using only the seven closed results. Specifically state
whether Massive resolved exact `LC -> HAPN` as a same-security ticker change,
whether it merely reported old inactive/current rows for the three
acquisition/terminal controls, and whether any event would incorrectly create
an acquirer alias. A `coverage_limited` result closes that authority axis for
this design round.

- [ ] **Step 6: Seal and review the packet**

Write `SHA256SUMS`, read back every digest, run `git diff --check`, and request
independent review before any Stage 3 census or authority design.

### Task 6: Full-Universe Manifest and Conditional Census

**Files:**
- Modify: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py`
- Create after separately authorized read: private git-ignored
  `data/private_evidence/lifecycle-provider-authority-universe-manifest/`
- Create after separately authorized read: tracked aggregate-only
  `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/universe-manifest/`
- Create after separately authorized calls: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/universe-summary.json`
- Modify: `tests/test_lifecycle_provider_census_runner.py`

**Interfaces:**
- Consumes: a separately authorized read-only active-universe snapshot and only
  the provider axes that passed Task 5.
- Produces: sealed active-pass and missing-subset manifests with exact counts
  and SHA-256 values.

- [x] **Step 1: Write RED manifest stability tests**

```python
def test_universe_manifest_is_sorted_exact_and_digest_bound():
    manifest = build_universe_manifest({"SMCI": ("manual_lists",), "AAPL": ("manual_lists",)})
    assert manifest["tickers"] == ["AAPL", "SMCI"]
    assert manifest["count"] == 2
    assert manifest["sha256"] == digest_tickers(("AAPL", "SMCI"))
```

Also reject `SMCI*`, duplicate normalized tickers, empty sources, and any count
supplied by the caller rather than derived from exact rows.

The private manifest must preserve internal ticker identity separately from
provider request identity. Own the reviewed `BRK B -> BRK.B` Massive mapping,
reject any unreviewed non-provider-shaped ticker, and publish only the mapping
count rather than either value.

- [x] **Step 2: Add read-only manifest mode**

Open the production inputs only with SQLite URI `mode=ro`, make no provider
call, and record the actual count. Treat 186 as the last recorded comparison,
not a hardcoded assertion. The full ticker/source rows and seal are `0600`
inside a new `0700` git-ignored directory. The tracked attestation contains no
ticker or per-symbol source membership and binds the private file by SHA-256.

- [x] **Step 3: Stop for active-pass authorization**

Derive the Massive ceiling as exactly `N`, where `N` is the sealed manifest
count. Add two Nasdaq and, if admitted/configured, two EODHD requests. Do not
authorize inactive or event requests in this step.

The manifest records this budget with status `not_authorized`. Raising the
known-case transport's 14-request Massive ceiling is part of the later active-
pass implementation and must not weaken that existing gate.

The sealed 2026-09-04 manifest contains `N = 186`; the exact stopped envelope
is therefore 186 Massive + 2 EODHD + 2 Nasdaq = 190 HTTP attempts. No request
in that envelope has been authorized or executed.

- [ ] **Step 4: Run and seal only the active pass**

Produce the exact missing/ambiguous subset and digest. Stop without querying
inactive status or events.

- [ ] **Step 5: Stop for missing-subset authorization**

Let `M` be exact inactive candidates and `K` be exact stable-identifier event
candidates after review. Authorize at most `M + K` additional Massive requests;
do not request events for ordinary active symbols.

- [ ] **Step 6: Run the conditional pass and summarize disagreement**

Classify exact agreement, contradiction, coverage limitation, and ambiguity.
Never turn absence from one provider into delisting.

### Task 7: Authority Decision and Legacy-Case Migration Design

**Files:**
- Modify after census review: `docs/superpowers/specs/2026-09-04-lifecycle-provider-authority-shadow-census-design.md`
- Create after census review: `docs/superpowers/specs/2026-09-04-lifecycle-structured-authority-decision.md`
- Modify after census review: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: independently reviewed known-case and, if admitted, universe census
  packets.
- Produces: one of the three architectures in spec section 10 and an explicit
  storage/cutover plan for legacy cases.

- [ ] **Step 1: Inventory legacy state under separate authorization**

Read only counts and IDs for observations, unresolved cases, accepted
assessments, generated proposals, approved/unapplied transitions, applied
activity, and reversible state. Do not read provider credentials or translate
evidence.

- [ ] **Step 2: Select the architecture from measured pass/fail axes**

Use structured status with attended rename when listing passes but exact
`LC -> HAPN` fails. Permit provider-first same-security ticker changes only if
that axis passes with stable-identity agreement. Economic merger/acquisition
successors never become aliases, regardless of provider coverage. An
acquisition observation does not stop tracking the target while it remains
active; only independently confirmed listing termination or explicit user
removal may stop active collection. Keep the current attended system if listing
state itself is not reliable. Do not add an acquisition kind to
`ticker_identity_transitions`: acquisition is an assessment/relationship, not
an identity mutation.

- [ ] **Step 3: Specify the 36-case semantic migration**

Preserve raw history and applied activity, revalidate approved/unapplied work,
project provider-confirmed cases under the new policy, move no-trigger legacy
candidates out of the operational queue with
`legacy_candidate_no_current_trigger`, and send every ambiguous or unavailable
case to attended review. Complete `ARCH`, `LTHM`, and `TA` in this delivery
stage: use current structured evidence when available, otherwise use the
already reviewed primary-source listing/delisting evidence through attended
terminal transitions after the open-position guard. Do not treat acquisition
itself as terminal evidence. Never create an acquirer alias or edit application
tables by hand. Any acquirer or combined-security follow-up is an independent
attended tracking suggestion, not a membership transfer.

- [ ] **Step 4: Decide the storage mechanism explicitly**

Compare a schema migration against a policy-versioned derived projection using
the measured inventory. The selected design must implement both Current and
Former accepted-membership projection, event-correlated Current admission,
durable source-specific suppression with explicit restore, no acquisition
aliases, acquisition-safe tracking continuity, independently confirmed terminal
retirement, attended related-security suggestions, attended capture-gap
candidates, and provenance-bound bootstrap from design section 8. The RED-first
plan must first replace the broad `transition_kind is not None` source-hiding
condition with an explicit closed set containing only `symbol_continuation` and
`terminal_delisting`; no new transition kind may land before that guard. It
must then separately own these behaviors:

- an acquired target that remains listed keeps its membership and price/news
  collection and emits `notify` plus `keep_tracking`, with no archive, hide, or
  remap proposal;
- an acquisition assessment remains non-executable in the identity-transition
  preview and cannot acquire a hidden source effect;
- an independently confirmed terminal target may leave active collection while
  its history and relationship provenance remain intact;
- accepting a related acquirer/new-company suggestion creates a distinct
  membership, while dismissal leaves the target membership unchanged; and
- explicit source removal creates a tombstone that neither refresh nor any
  later identity alias can bypass.

The source-hiding allowlist needs a defensive positive/negative owner: both
existing mutating kinds hide when otherwise eligible, while an acquisition or
unknown relationship value does not. Replacing the allowlist with a generic
non-null check must make that test fail.

If a migration is selected, stop for separate schema, backup, rollback, and
production authorization; do not hide it in policy code.

- [ ] **Step 5: Write a new RED-first implementation plan**

The authority redesign is a new implementation slice. Do not implement it by
continuing this census plan or by importing the shadow adapter into the
scheduler.

## Plan Self-Review

- Spec coverage: provider contracts, frozen oracle, negative-result semantics,
  closed results, request budgets, credential boundary, universe sealing, and
  36-case treatment each have an owning task.
- Placeholder scan: all output paths, modes, result values, and request limits
  are explicit; there are no unresolved implementation markers.
- Type consistency: `CensusObservation`, `CensusCaseResult`,
  `CensusRequestBudget`, and the four runner modes are introduced once and used
  consistently by later tasks.
