# IBKR News Error 10172 Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve IBKR news-body request error 10172 as a sanitized, typed unavailable result instead of silently classifying it as a successful empty body.

**Architecture:** Temporarily enable `ib_insync` request errors only around the synchronous news-body request, translate code 10172 at the data-source boundary, and always restore the client setting. The normalized adapter and read-only probe consume the typed exception without exposing provider text; N7 retains ownership of the eventual terminal-state policy.

**Tech Stack:** Python 3, `ib_insync`, dataclasses, pytest, existing `ibkr_gateway_lock` operation boundary.

---

## File Map

- Modify `data_sources/ibkr_source.py`: define the sanitized typed exception and translate request error 10172 in the strict body method.
- Modify `src/news_normalized/ibkr_adapter.py`: map typed unavailable to sanitized `BodyStatus.FAILED` while preserving successful-empty behavior.
- Modify `scripts/diagnostics/probe_ibkr_news_bodies.py`: emit the sanitized `unavailable` response class.
- Modify `tests/test_news_normalized_ibkr_adapter.py`: pin strict-source, adapter, and probe contracts hermetically.
- Modify `docs/superpowers/specs/2026-06-28-news-article-normalization-design.md`: record the N7 carry-forward so 10172 cannot remain retryable when N8 routes.

### Task 1: Translate Request Error 10172 at the IBKR Source Boundary

**Files:**
- Modify: `data_sources/ibkr_source.py:24-32`
- Modify: `data_sources/ibkr_source.py:616-640`
- Test: `tests/test_news_normalized_ibkr_adapter.py`

- [ ] **Step 1: Write strict-source tests that initially fail**

Add `RequestError` and traceback-formatting imports, a reusable fake client, and tests covering
success, successful empty, 10172, other request errors, transport errors, restoration, and legacy
compatibility:

```python
import traceback

from ib_insync import RequestError
from data_sources.ibkr_source import (
    IBKRDataSource,
    IBKRNewsArticleUnavailable,
)


class BodyClient:
    def __init__(self, result=None, error=None, raise_request_errors=False):
        self.result = result
        self.error = error
        self.RaiseRequestErrors = raise_request_errors
        self.setting_seen = []

    def reqNewsArticle(self, provider_code, article_id):
        self.setting_seen.append(self.RaiseRequestErrors)
        if self.error is not None:
            raise self.error
        return self.result


def body_source(client):
    source = IBKRDataSource.__new__(IBKRDataSource)
    source._ib = client
    source._ensure_connected = lambda: None
    source._rate_limit_wait = lambda: None
    return source


@pytest.mark.parametrize("result, expected", [(None, None), (type("Body", (), {"articleText": "text"})(), "text")])
def test_ibkr_strict_body_scopes_request_errors_and_restores_on_success(result, expected):
    client = BodyClient(result=result, raise_request_errors=False)
    assert body_source(client).fetch_news_article_body_strict("DJ-N", "id") == expected
    assert client.setting_seen == [True]
    assert client.RaiseRequestErrors is False


def test_ibkr_strict_body_translates_10172_without_leaking_provider_message():
    secret = "licensed provider payload"
    client = BodyClient(error=RequestError(4, 10172, secret))
    with pytest.raises(IBKRNewsArticleUnavailable) as caught:
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")
    assert caught.value.error_code == 10172
    assert secret not in str(caught.value)
    assert secret not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__ is True
    assert client.RaiseRequestErrors is False


def test_ibkr_strict_body_reraises_other_request_errors_and_restores():
    error = RequestError(5, 321, "other")
    client = BodyClient(error=error, raise_request_errors=True)
    with pytest.raises(RequestError) as caught:
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")
    assert caught.value is error
    assert client.RaiseRequestErrors is True


def test_ibkr_strict_body_restores_after_transport_error():
    client = BodyClient(error=TimeoutError("timeout"))
    with pytest.raises(TimeoutError):
        body_source(client).fetch_news_article_body_strict("DJ-N", "id")
    assert client.RaiseRequestErrors is False
```

Retain or adapt the existing compatibility assertion proving `fetch_news_article_body` catches a
strict exception and returns `None`.

- [ ] **Step 2: Run the strict-source tests and confirm RED**

Run:

```bash
pytest -q tests/test_news_normalized_ibkr_adapter.py -k "strict_body"
```

Expected: collection or assertion failures because `IBKRNewsArticleUnavailable` and scoped request
error handling do not exist.

- [ ] **Step 3: Implement the minimal typed exception and scoped translation**

Extend the guarded `ib_insync` import:

```python
from ib_insync import (
    IB,
    Option,
    RequestError,
    ScannerSubscription,
    Stock,
    TagValue,
    util,
)
```

Define the ArkScope-owned exception outside `IBKRDataSource`:

```python
class IBKRNewsArticleUnavailable(RuntimeError):
    """IBKR explicitly reported that a requested news article is unavailable."""

    def __init__(self, error_code: int):
        self.error_code = int(error_code)
        super().__init__(f"IBKR news article unavailable ({self.error_code})")
```

Replace the strict request body with:

```python
previous_raise_request_errors = self._ib.RaiseRequestErrors
self._ib.RaiseRequestErrors = True
try:
    body = self._ib.reqNewsArticle(provider_code, article_id)
except RequestError as exc:
    if exc.code == 10172:
        raise IBKRNewsArticleUnavailable(exc.code) from None
    raise
finally:
    self._ib.RaiseRequestErrors = previous_raise_request_errors
return body.articleText if body else None
```

Do not change the compatibility method.

- [ ] **Step 4: Run strict-source tests and confirm GREEN**

Run:

```bash
pytest -q tests/test_news_normalized_ibkr_adapter.py -k "strict_body"
```

Expected: all selected tests pass with no network access.

- [ ] **Step 5: Commit Task 1**

```bash
git add data_sources/ibkr_source.py tests/test_news_normalized_ibkr_adapter.py
git commit -m "fix: preserve IBKR news unavailable errors"
```

### Task 2: Classify Typed Unavailable in the Adapter and Probe

**Files:**
- Modify: `src/news_normalized/ibkr_adapter.py:10-15,86-101`
- Modify: `scripts/diagnostics/probe_ibkr_news_bodies.py:20-23,75-103`
- Test: `tests/test_news_normalized_ibkr_adapter.py`

- [ ] **Step 1: Write adapter and probe tests that initially fail**

Add tests proving typed unavailable is sanitized `FAILED`, successful `None` remains `EMPTY`, and
probe output emits only the numeric code:

```python
def test_ibkr_unavailable_body_is_failed_and_sanitized():
    gateway = FakeGateway()
    key = ("DJ-N", "DJ-N$2")
    gateway.body_errors[key] = IBKRNewsArticleUnavailable(10172)

    body = IBKRNormalizedProvider(gateway).fetch_body(candidate())

    assert body.status is BodyStatus.FAILED
    assert body.error == "IBKR news article unavailable (10172)"
    assert body.raw_body is None


def test_probe_classifies_ibkr_unavailable_without_payload(capsys):
    class Source:
        def fetch_news_article_body_strict(self, provider, article_id):
            raise IBKRNewsArticleUnavailable(10172)

        def disconnect(self):
            pass

    probe_main(
        [],
        source_factory=Source,
        probes=(ProbeSpec("missing", "DJ-N", "secret-id"),),
        lock_factory=nullcontext,
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == [{
        "error_code": 10172,
        "html_tags": 0,
        "label": "missing",
        "length": 0,
        "present": False,
        "provider": "DJ-N",
        "response_class": "unavailable",
    }]
    assert "secret-id" not in json.dumps(payload)
```

Extend the existing probe-secret test so an injected provider message remains absent from stdout
and stderr.

- [ ] **Step 2: Run adapter/probe tests and confirm RED**

Run:

```bash
pytest -q tests/test_news_normalized_ibkr_adapter.py -k "unavailable or probe"
```

Expected: unavailable adapter/probe assertions fail because both paths still use generic exception
handling.

- [ ] **Step 3: Implement explicit typed handling**

Import `IBKRNewsArticleUnavailable` into both consumers. In the adapter, add before the generic
handler:

```python
except IBKRNewsArticleUnavailable as exc:
    return BodyCandidate(
        status=BodyStatus.FAILED,
        error=str(exc),
        retrieval_method="provider_api",
        retrieval_source=self.source,
    )
```

In `_probe_one`, add before the generic handler:

```python
except IBKRNewsArticleUnavailable as exc:
    return {
        **base,
        "present": False,
        "length": 0,
        "html_tags": 0,
        "response_class": "unavailable",
        "error_code": exc.error_code,
    }
```

Do not emit `str(exc)`, `article_id`, or the original `RequestError.message`.

- [ ] **Step 4: Run adapter/probe tests and confirm GREEN**

Run:

```bash
pytest -q tests/test_news_normalized_ibkr_adapter.py
```

Expected: all tests pass; live IBKR tests remain skipped unless explicitly enabled.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/news_normalized/ibkr_adapter.py scripts/diagnostics/probe_ibkr_news_bodies.py tests/test_news_normalized_ibkr_adapter.py
git commit -m "fix: classify IBKR unavailable news bodies"
```

### Task 3: Pin the N7 Carry-forward and Verify the Slice

**Files:**
- Modify: `docs/superpowers/specs/2026-06-28-news-article-normalization-design.md:301-325`
- Test: `tests/test_news_normalized_ibkr_adapter.py`
- Test: `tests/test_news_normalized_writer.py`
- Test: `tests/test_ibkr_news.py`

- [ ] **Step 1: Record the temporary-policy ownership**

Add after the body-state contract:

```markdown
N6.1 preserves IBKR request error 10172 as typed `unavailable` evidence and temporarily maps it to
retryable `failed`. N7 must resolve unavailable cohorts into a bounded retry or terminal policy
using the post-fix five-article probe before N8 routes IBKR ingest. Shipping N8 with unbounded 10172
retries is not permitted.
```

- [ ] **Step 2: Run focused and adjacent regression tests**

Run:

```bash
pytest -q \
  tests/test_news_normalized_ibkr_adapter.py \
  tests/test_news_normalized_writer.py \
  tests/test_ibkr_news.py
```

Expected: all hermetic tests pass; tests requiring a configured live IBKR session are skipped.

- [ ] **Step 3: Compile touched Python modules**

Run:

```bash
python -m py_compile \
  data_sources/ibkr_source.py \
  src/news_normalized/ibkr_adapter.py \
  scripts/diagnostics/probe_ibkr_news_bodies.py
```

Expected: exit code 0 and no output.

- [ ] **Step 4: Inspect the final diff and hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only the plan, source, adapter, probe, tests, and carry-forward doc
are changed by this branch.

- [ ] **Step 5: Commit Task 3**

```bash
git add docs/superpowers/specs/2026-06-28-news-article-normalization-design.md
git commit -m "docs: carry IBKR unavailable policy into N7"
```

### Task 4: Gated Five-case Premise Confirmation

**Files:**
- Read only: `scripts/diagnostics/probe_ibkr_news_bodies.py`
- Read only: live IB Gateway through the existing configured endpoint

- [ ] **Step 1: Confirm the distinction between test contract and live premise**

Hermetic tests prove: given `RequestError(code=10172)`, ArkScope translates and sanitizes it.
They cannot prove that the live Gateway emits that request error for the approved article IDs.
Only this outward probe confirms the premise.

- [ ] **Step 2: Run the approved sanitized probe only after code review**

Run:

```bash
python scripts/diagnostics/probe_ibkr_news_bodies.py
```

Expected: exactly five JSON records containing only label, provider, presence, length, HTML-tag
count, response class, and numeric error code where applicable. No database writes occur.

- [ ] **Step 3: Record evidence for N7 policy**

Report each reviewed cohort as `body`, `empty`, `unavailable`, or `error`. Do not infer `expired`
from age alone. N7 policy must explicitly bound retries for persistent unavailable records before
N8 routes the IBKR writer.

- [ ] **Step 4: Commit no live data**

The probe result is operational evidence, not licensed repository content. Do not write body text,
article IDs, or raw provider messages into tracked files.
