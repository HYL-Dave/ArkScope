# IBKR News Error 10172 Capture Design

**Date:** 2026-06-28
**Slice:** N6.1, before N7 migration policy
**Status:** Proposed for review

## 1. Context

The N6 five-article outward probe can retrieve IBKR article bodies again, but it exposed an
error-classification defect. `ib_insync` defaults `IB.RaiseRequestErrors` to false. When
`reqNewsArticle` receives request error 10172, the request future is completed without a result and
the synchronous API returns `None`. ArkScope therefore cannot distinguish:

- a successful request whose article genuinely has no body; and
- an explicit IBKR response that the requested article is unavailable.

The normalized IBKR adapter currently maps `None` to terminal `BodyStatus.EMPTY`. That can make an
unavailable or expired article look like a provider-confirmed empty article and prematurely freeze
the wrong N7 migration policy.

This is a request-error capture defect, not evidence that every 10172 response means `expired`.

## 2. Goals

1. Preserve the distinction between successful empty, explicit 10172 unavailable, and all other
   request or transport failures.
2. Capture 10172 without globally changing error behavior for unrelated IBKR operations.
3. Keep probe output sanitized: no licensed body, provider error message, title, URL, or article ID.
4. Re-run the five approved N6 cases with truthful response classes before N7 body policy is locked.
5. Preserve the legacy compatibility method's `Optional[str]` and catch-and-return-`None` behavior.

## 3. Non-goals

- Do not map 10172 to `BodyStatus.EXPIRED`, `EMPTY`, or any other terminal migration state yet.
- Do not implement N7 conflict resolution, migration apply, or any live database write.
- Do not change global IBKR connection settings or enable `RaiseRequestErrors` for all requests.
- Do not change retry limits, retention windows, body cleaning, or normalized schema.
- Do not run the outward probe as part of tests or module import.

## 4. Error Contract

| Provider outcome | Strict source method | Probe class | Adapter status before N7 policy |
|---|---|---|---|
| Non-empty response | Return body | `body` | `FETCHED` |
| Successful empty response | Return `None` | `empty` | `EMPTY` |
| Request error 10172 | Raise `IBKRNewsArticleUnavailable` | `unavailable`, code `10172` | `FAILED` with sanitized error |
| Other IB request error | Re-raise original `RequestError` | `error` + exception type | `FAILED` |
| Transport/runtime error | Re-raise original exception | `error` + exception type | `FAILED` |

`FAILED` is deliberately temporary for 10172. N8 is not routed yet, so this does not introduce a
live retry loop. The post-fix N6 evidence will determine whether N7 maps particular unavailable
cohorts to `expired`, another terminal policy, or a reviewed retry state.

## 5. Strict Request Behavior

`IBKRDataSource.fetch_news_article_body_strict` will:

1. preserve the current `IB.RaiseRequestErrors` value;
2. set it to true immediately around the synchronous `reqNewsArticle` call;
3. catch `ib_insync.RequestError`;
4. translate only code 10172 to `IBKRNewsArticleUnavailable(error_code=10172)`;
5. re-raise every other request error unchanged; and
6. restore the original setting in `finally`, on success and every failure path.

The typed exception exposes only a numeric `error_code`. Its public message is ArkScope-owned and
does not include IBKR's provider message or licensed content. Translation uses `raise ... from
None` so normal traceback rendering does not expose the original provider message.

`RaiseRequestErrors` is mutable on one `IB` instance, so the setting is request-scoped in time, not
intrinsically request-local inside `ib_insync`. ArkScope's normalized writer and probe already hold
the shared `ibkr_gateway_lock` around the provider operation. Existing scheduler IBKR work uses the
same lock. The fix must not add a second lock or permanently mutate the client setting.

The compatibility method `fetch_news_article_body` remains unchanged in contract: it calls the
strict method, logs a failure, and returns `None` for legacy callers.

## 6. Adapter and Probe Behavior

The normalized adapter catches `IBKRNewsArticleUnavailable` before its generic exception handler
and returns retryable `FAILED` with a fixed message such as `IBKR article unavailable (10172)`.
It must not copy `RequestError.message` into `BodyCandidate.error`.

The probe catches the typed exception before generic exceptions and emits only:

```json
{
  "label": "recent_missing",
  "provider": "DJ-RTA",
  "present": false,
  "length": 0,
  "html_tags": 0,
  "response_class": "unavailable",
  "error_code": 10172
}
```

Generic failures continue to expose only `response_class="error"` and the exception class name.
The probe never emits exception text or the probed article ID.

## 7. Verification

Hermetic tests must pin:

1. strict success returns the body and restores the prior `RaiseRequestErrors` value;
2. strict successful empty remains `None` and restores the setting;
3. 10172 becomes the typed exception with only code 10172 and restores the setting;
4. non-10172 `RequestError` is re-raised unchanged and restores the setting;
5. transport exceptions propagate and restore the setting;
6. compatibility method still catches strict failures and returns `None`;
7. adapter maps typed unavailable to sanitized `FAILED`, while true `None` remains `EMPTY`;
8. probe maps typed unavailable to the sanitized response above;
9. probe output contains none of injected body or exception-message secrets; and
10. existing normalized IBKR writer and probe tests remain green.

No test may connect to IBKR.

## 8. Delivery and Gates

1. Commit this reviewed design independently.
2. Write an implementation plan with production and test file boundaries.
3. Implement test-first as one small N6.1 code slice.
4. Run focused hermetic tests and the broader IBKR/news-normalization regression set.
5. Only after code review, run the five approved outward probe cases under the shared Gateway lock.
6. Record response classes and lengths only; do not persist bodies or mutate the live database.
7. Use those results to lock N7 body-status and conflict-resolution policy.

N7 live apply and N8 cutover remain separate hard-gated slices.
