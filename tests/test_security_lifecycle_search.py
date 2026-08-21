from __future__ import annotations

import sqlite3

import pytest


_AT = "2026-08-20T00:00:00Z"
_FINGERPRINT = "a" * 64


def _context(tmp_path):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    conn = sqlite3.connect(tmp_path / "profile_state.db")
    store = SecurityLifecycleInvestigationStore(
        conn,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0000712515-26-000042",
        ticker="EA",
        at=_AT,
    )
    observation = {
        "ticker": "EA",
        "cik": "0000712515",
        "issuer_name": "Electronic Arts Inc.",
        "filing_date": "2026-08-04",
        "source": "sec_edgar",
        "source_ref": "0000712515-26-000042",
        "filing_form": "8-K",
        "filing_items": ["2.01", "3.01"],
        "evidence_url": "https://www.sec.gov/Archives/example/ea-8k.htm",
        "description": "Completion of acquisition and listing review.",
        "first_observed_at": _AT,
        "last_observed_at": _AT,
        "kinds": [
            {"event_type": "acquisition_completed", "effective_date": "2026-08-04"},
            {"event_type": "listing_status_review", "effective_date": None},
        ],
    }
    return conn, store, case_id, observation


class _Adapter:
    identity = "tavily"

    def __init__(self, *, results=None, fetched=None, failure=None, usage=None):
        self.results = [] if results is None else results
        self.fetched = {} if fetched is None else fetched
        self.failure = failure
        self.usage = {"search_requests": 0} if usage is None else usage
        self.search_calls = []
        self.fetch_calls = []

    def search(self, *, query, max_results):
        self.search_calls.append((query, max_results))
        if self.failure is not None:
            raise self.failure
        return {
            "answer": "provider answer must be ignored",
            "results": list(self.results),
            "usage": dict(self.usage),
        }

    def fetch(self, *, target, max_bytes, redirect_guard):
        url = target.url
        self.fetch_calls.append((url, max_bytes))
        value = self.fetched.get(url)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, dict) and value.get("redirect_url"):
            redirect_guard(value["redirect_url"])
        return value


def _safe_resolver(host):
    assert host
    return ("93.184.216.34",)


def _result(index=1, **overrides):
    value = {
        "url": f"https://example.com/news/{index}",
        "title": f"Result {index}",
        "content": f"Snippet {index}",
        "publisher": "Example News",
        "published_at": "2026-08-19T00:00:00Z",
        "score": 0.99,
        "raw_body": "must not persist",
    }
    value.update(overrides)
    return value


def test_adapter_failure_is_typed_and_keeps_prior_evidence(tmp_path):
    from src.api.dependencies import _LifecycleTavilyClient
    from src.security_lifecycle_search import (
        LifecycleSearchFailure,
        add_manual_evidence,
        run_tavily_investigation,
    )

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {"results": []}

    for status_code, failure_code in (
        (429, "rate_limited"),
        (432, "usage_limit_reached"),
        (433, "usage_limit_reached"),
    ):
        client = _LifecycleTavilyClient(
            api_key_loader=lambda: "test-key",
            transport=lambda **_kwargs: Response(status_code),
        )
        with pytest.raises(LifecycleSearchFailure, match=failure_code):
            client.search(query="issuer event", max_results=5)

    redirect_request = {}

    def redirect_transport(**kwargs):
        redirect_request.update(kwargs)
        return Response(302)

    redirect_client = _LifecycleTavilyClient(
        api_key_loader=lambda: "test-key",
        transport=redirect_transport,
    )
    with pytest.raises(LifecycleSearchFailure, match="unsupported_content"):
        redirect_client.search(query="issuer event", max_results=5)
    assert redirect_request["allow_redirects"] is False

    conn, store, case_id, observation = _context(tmp_path)
    try:
        add_manual_evidence(
            store=store,
            case_id=case_id,
            text="Known issuer statement.",
            url=None,
            at=_AT,
        )
        before = store.list_evidence(case_id)
        result = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(failure=LifecycleSearchFailure("network_error")),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        assert result["status"] == "failed"
        assert result["failure_code"] == "network_error"
        assert store.list_evidence(case_id) == before

        exhausted = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(
                failure=LifecycleSearchFailure("usage_limit_reached")
            ),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at="2026-08-20T00:30:00Z",
        )
        assert exhausted["status"] == "failed"
        assert exhausted["failure_code"] == "usage_limit_reached"
        assert store.list_evidence(case_id) == before

        fetched = _result()
        after_fetch_attempt = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(
                results=[fetched],
                fetched={
                    fetched["url"]: LifecycleSearchFailure("network_error")
                },
            ),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at="2026-08-20T01:00:00Z",
        )
        assert after_fetch_attempt["status"] == "failed"
        assert after_fetch_attempt["fetch_count"] == 1
    finally:
        conn.close()


def test_adapter_output_cannot_write_an_assessment_or_proposal(tmp_path):
    from src.security_lifecycle_search import run_tavily_investigation

    conn, store, case_id, observation = _context(tmp_path)
    try:
        adapter = _Adapter(
            results=[
                _result(
                    assessment={"relevance": "direct_tracked_security"},
                    proposal={"action_type": "hide_from_active_universe"},
                )
            ],
            fetched={
                "https://example.com/news/1": {
                    "url": "https://example.com/news/1",
                    "content": "Fetched evidence.",
                    "mime_type": "text/html",
                }
            },
        )
        run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=adapter,
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        assert store.list_evidence(case_id)
        assert store.list_assessments(case_id) == []
        assert store.list_proposals(case_id) == []
    finally:
        conn.close()


def test_explicit_tavily_run_uses_three_queries_five_results_and_five_fetches_at_most(
    tmp_path,
):
    from src.security_lifecycle_search import run_tavily_investigation

    conn, store, case_id, observation = _context(tmp_path)
    try:
        results = [_result(index) for index in range(1, 8)]
        fetched = {
            item["url"]: {
                "url": item["url"],
                "content": f"Fetched {item['url']}",
                "mime_type": "text/html",
            }
            for item in results
        }
        adapter = _Adapter(results=results, fetched=fetched)
        run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=adapter,
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        assert len(adapter.search_calls) == 3
        assert all(max_results == 5 for _query, max_results in adapter.search_calls)
        assert len(adapter.fetch_calls) == 5
        run = store.list_investigation_runs(case_id)[0]
        assert run["query_count"] == 3
        assert run["result_count"] == 5
        assert run["fetch_count"] == 5
    finally:
        conn.close()


def test_failed_retry_does_not_clear_prior_successful_evidence(tmp_path):
    from src.security_lifecycle_search import (
        LifecycleSearchFailure,
        run_tavily_investigation,
    )

    conn, store, case_id, observation = _context(tmp_path)
    try:
        result = _result()
        run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(
                results=[result],
                fetched={
                    result["url"]: {
                        "url": result["url"],
                        "content": "Fetched evidence.",
                        "mime_type": "text/html",
                    }
                },
            ),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        prior = store.list_evidence(case_id)
        failed = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(failure=LifecycleSearchFailure("rate_limited")),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at="2026-08-20T01:00:00Z",
        )
        assert failed["failure_code"] == "rate_limited"
        assert store.list_evidence(case_id) == prior
    finally:
        conn.close()


def test_manual_adapter_adds_bounded_text_and_https_urls_with_zero_network(tmp_path):
    from src.security_lifecycle_search import add_manual_evidence

    conn, store, case_id, _observation = _context(tmp_path)
    try:
        text_id = add_manual_evidence(
            store=store,
            case_id=case_id,
            text="  Manual finding  ",
            url=None,
            at=_AT,
        )
        url_id = add_manual_evidence(
            store=store,
            case_id=case_id,
            text=None,
            url="https://example.com/issuer-notice",
            at=_AT,
        )
        evidence = {item["evidence_id"]: item for item in store.list_evidence(case_id)}
        assert evidence[text_id]["kind"] == "manual_text"
        assert evidence[text_id]["excerpt"] == "Manual finding"
        assert evidence[text_id]["source_url"] is None
        assert evidence[url_id]["kind"] == "manual_url"
        assert evidence[url_id]["source_url"] == "https://example.com/issuer-notice"
    finally:
        conn.close()


def test_normalization_drops_provider_answers_scores_scripts_and_raw_bodies(tmp_path):
    from src.security_lifecycle_search import (
        _normalize_source_published_at,
        run_tavily_investigation,
    )

    assert _normalize_source_published_at("2026-08-19") == "2026-08-19"
    assert _normalize_source_published_at(
        "2026-08-19T08:30:45.120+08:00"
    ) == "2026-08-19T00:30:45.120Z"
    assert _normalize_source_published_at(
        "2026-08-19T08:30:45.123456789+08:00"
    ) == "2026-08-19T00:30:45.123456789Z"
    assert _normalize_source_published_at("yesterday") is None

    conn, store, case_id, observation = _context(tmp_path)
    try:
        result = _result(
            content="Visible <script>secret()</script> excerpt",
            score=0.77,
            raw_body="RAW SECRET BODY",
            published_date="2026-08-19",
            published_at="yesterday",
        )
        adapter = _Adapter(
            results=[result],
            fetched={
                result["url"]: {
                    "url": result["url"],
                    "content": "<main>Useful filing text</main><script>drop()</script>",
                    "mime_type": "text/html",
                    "raw_body": "RAW FETCH BODY",
                }
            },
        )
        run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=adapter,
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        serialized = "\n".join(str(item) for item in store.list_evidence(case_id))
        for forbidden in (
            "provider answer",
            "0.77",
            "RAW SECRET BODY",
            "RAW FETCH BODY",
            "secret()",
            "drop()",
        ):
            assert forbidden not in serialized
        assert "Useful filing text" in serialized
        assert {
            item["source_published_at"]
            for item in store.list_evidence(case_id)
        } == {"2026-08-19"}
    finally:
        conn.close()


def test_search_calls_external_and_metered_permissions_before_egress(tmp_path):
    from src.security_lifecycle_search import run_tavily_investigation

    conn, store, case_id, observation = _context(tmp_path)
    calls = []

    class OrderedAdapter(_Adapter):
        def search(self, *, query, max_results):
            calls.append(("transport", query))
            return super().search(query=query, max_results=max_results)

    try:
        run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=OrderedAdapter(results=[]),
            permission=lambda permission, action, detail: calls.append(
                (permission.value, action, detail)
            ),
            resolver=_safe_resolver,
            at=_AT,
        )
        assert [item[0] for item in calls[:3]] == [
            "external_web_access",
            "metered_spend",
            "transport",
        ]
        assert calls[0][2] == {
            "adapter": "tavily",
            "case_id": case_id,
            "query_count": 3,
        }
        assert "query" not in calls[0][2]

        denied = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=OrderedAdapter(results=[]),
            permission=lambda *_args: (_ for _ in ()).throw(PermissionError()),
            resolver=_safe_resolver,
            at="2026-08-20T01:00:00Z",
        )
        assert denied["failure_code"] == "permission_denied"
    finally:
        conn.close()


def test_search_queries_are_deterministic_for_listing_and_acquisition_kinds():
    from src.security_lifecycle_search import build_lifecycle_query_plan

    listing = {
        "ticker": "EA",
        "issuer_name": "Electronic Arts Inc.",
        "cik": "0000712515",
        "filing_form": "25",
        "source_ref": "ref",
        "kinds": [{"event_type": "listing_removal_notice", "effective_date": None}],
    }
    acquisition = {
        **listing,
        "kinds": [
            {"event_type": "listing_removal_notice", "effective_date": None},
            {"event_type": "acquisition_completed", "effective_date": "2026-08-04"},
        ],
    }
    assert build_lifecycle_query_plan(listing) == build_lifecycle_query_plan(dict(listing))
    assert len(build_lifecycle_query_plan(listing)) == 2
    assert len(build_lifecycle_query_plan(acquisition)) == 3
    assert all("EA" in query for query in build_lifecycle_query_plan(acquisition))


def test_successful_zero_result_search_is_succeeded_not_failed(tmp_path):
    from src.security_lifecycle_search import run_tavily_investigation

    conn, store, case_id, observation = _context(tmp_path)
    try:
        result = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(results=[]),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        assert result["status"] == "succeeded"
        assert result["result_count"] == 0
        assert result["failure_code"] is None
        assert store.list_evidence(case_id) == []
    finally:
        conn.close()


def test_unsafe_local_private_and_redirect_urls_are_rejected(tmp_path):
    from src.api.dependencies import _lifecycle_fetch_transport
    from src.security_lifecycle_search import (
        LifecycleSearchFailure,
        TavilyLifecycleSearchAdapter,
        _resolve_https_target,
        add_manual_evidence,
        run_tavily_investigation,
    )

    conn, store, case_id, observation = _context(tmp_path)
    try:
        with pytest.raises(ValueError, match="unsafe_url"):
            add_manual_evidence(
                store=store,
                case_id=case_id,
                text=None,
                url="https://127.0.0.1/private",
                at=_AT,
            )

        private = _result(url="https://10.0.0.5/private")
        adapter = _Adapter(results=[private])
        failed = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=adapter,
            permission=lambda *_args: None,
            resolver=lambda _host: ("10.0.0.5",),
            at=_AT,
        )
        assert failed["failure_code"] == "unsupported_content"
        assert adapter.fetch_calls == []

        safe = _result()
        redirecting = _Adapter(
            results=[safe],
            fetched={safe["url"]: {"redirect_url": "https://169.254.169.254/meta"}},
        )
        redirected = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=redirecting,
            permission=lambda *_args: None,
            resolver=lambda host: (
                "169.254.169.254" if host == "169.254.169.254" else "93.184.216.34",
            ),
            at=_AT,
        )
        assert redirected["failure_code"] == "unsupported_content"

        class Client:
            def search(self, **_kwargs):
                return {"results": [safe]}

        def unsafe_redirect_transport(*, redirect_guard, **_kwargs):
            redirect_guard("https://169.254.169.254/meta")
            raise AssertionError("redirect rejection must stop the transport")

        production_adapter = TavilyLifecycleSearchAdapter(
            client=Client(),
            fetch_transport=unsafe_redirect_transport,
        )
        production_redirect = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=production_adapter,
            permission=lambda *_args: None,
            resolver=lambda host: (
                "169.254.169.254" if host == "169.254.169.254" else "93.184.216.34",
            ),
            at="2026-08-20T01:00:00Z",
        )
        assert production_redirect["failure_code"] == "unsupported_content"
        assert isinstance(LifecycleSearchFailure("unsupported_content"), RuntimeError)

        resolver_calls = []

        def resolver(host):
            resolver_calls.append(host)
            return ("93.184.216.34",)

        admitted = _resolve_https_target(
            "https://example.com/issuer",
            resolver=resolver,
        )
        pool_calls = []

        class Response:
            status = 200
            headers = {"Content-Type": "text/plain"}

            def stream(self, _chunk_size):
                yield b"issuer evidence"

            def release_conn(self):
                pool_calls.append(("released",))

        class Pool:
            def urlopen(self, method, path, **kwargs):
                pool_calls.append((method, path, kwargs))
                return Response()

            def close(self):
                pool_calls.append(("closed",))

        fetched = _lifecycle_fetch_transport(
            target=admitted,
            max_bytes=100,
            redirect_guard=lambda candidate: _resolve_https_target(
                candidate, resolver=resolver
            ),
            pool_factory=lambda target: (
                pool_calls.append(("target", target)),
                Pool(),
            )[1],
        )
        assert fetched["content"] == "issuer evidence"
        assert resolver_calls == ["example.com"]
        assert pool_calls[0][0] == "target"
        assert pool_calls[0][1] == admitted
        request = next(item for item in pool_calls if item[0] == "GET")
        assert request[1] == "/issuer"
        assert request[2]["headers"]["Host"] == "example.com"

        changing_resolver_calls = []

        def changing_resolver(host):
            changing_resolver_calls.append(host)
            if len(changing_resolver_calls) == 1:
                return ("93.184.216.34",)
            return ("127.0.0.1",)

        class RepeatedResultClient:
            def search(self, **_kwargs):
                return {"results": [safe]}

        pinned_pool_calls = []
        pinned_adapter = TavilyLifecycleSearchAdapter(
            client=RepeatedResultClient(),
            fetch_transport=lambda **kwargs: _lifecycle_fetch_transport(
                pool_factory=lambda target: (
                    pinned_pool_calls.append(target),
                    Pool(),
                )[1],
                **kwargs,
            ),
        )
        pinned = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=pinned_adapter,
            permission=lambda *_args: None,
            resolver=changing_resolver,
            at="2026-08-20T02:00:00Z",
        )
        assert pinned["status"] == "succeeded"
        assert changing_resolver_calls == ["example.com"]
        assert pinned_pool_calls[0].addresses == ("93.184.216.34",)
    finally:
        conn.close()


def test_usage_and_diagnostics_are_bounded_and_secret_safe(tmp_path):
    from src.security_lifecycle_search import (
        LifecycleSearchFailure,
        run_tavily_investigation,
    )

    conn, store, case_id, observation = _context(tmp_path)
    secret = "tvly-secret-value"
    try:
        result = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(
                failure=LifecycleSearchFailure(
                    "network_error",
                    detail=f"request failed for {secret} at /home/private",
                ),
                usage={
                    "provider_blob": "x" * 10000,
                    "secret": secret,
                    "credits_used": float("nan"),
                    "response_time_ms": float("inf"),
                },
            ),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at=_AT,
        )
        run = store.get_investigation_run(result["run_id"])
        assert len(run["usage_json"].encode("utf-8")) <= 4096
        database_text = "\n".join(conn.iterdump())
        assert secret not in database_text
        assert "/home/private" not in database_text
        assert "request failed" not in database_text
        assert "NaN" not in database_text
        assert "Infinity" not in database_text
        assert run["failure_code"] == "network_error"

        succeeded = run_tavily_investigation(
            store=store,
            case_id=case_id,
            observation=observation,
            adapter=_Adapter(
                results=[],
                usage={"credits": 1, "provider_blob": "not persisted"},
            ),
            permission=lambda *_args: None,
            resolver=_safe_resolver,
            at="2026-08-20T01:00:00Z",
        )
        usage = store.get_investigation_run(succeeded["run_id"])["usage_json"]
        assert '"credits":3' in usage
        assert "provider_blob" not in usage
    finally:
        conn.close()


def test_web_search_never_uses_browser_automation_or_a_generic_agent_loop():
    from pathlib import Path

    source = Path("src/security_lifecycle_search.py").read_text(encoding="utf-8")
    for forbidden in (
        "ToolRegistry",
        "web_search(",
        "web_fetch(",
        "web_browse(",
        "playwright",
        "selenium",
        "external_browser_automation",
    ):
        assert forbidden not in source
