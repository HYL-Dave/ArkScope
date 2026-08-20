"""Attended, provider-neutral evidence collection for lifecycle cases."""

from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import math
import re
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlsplit, urlunsplit

from src.api.permissions import PermissionClass, require_permission
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
from src.security_lifecycle_schema import RUN_FAILURE_CODES


MAX_QUERIES = 3
MAX_RESULTS_PER_QUERY = 5
MAX_FETCHES = 5
MAX_FETCH_BYTES = 100_000

_SPACE_RE = re.compile(r"\s+")


class _UnsafeLifecycleUrl(ValueError):
    def __init__(self):
        super().__init__("unsafe_url")


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.parts.append(data)


class LifecycleSearchFailure(RuntimeError):
    def __init__(self, code: str, *, detail: str | None = None):
        if code not in RUN_FAILURE_CODES:
            raise ValueError("failure_code")
        super().__init__(code)
        self.code = code
        self.detail = detail


class LifecycleSearchAdapter(Protocol):
    identity: str

    def search(self, *, query: str, max_results: int) -> Mapping[str, object]: ...

    def fetch(
        self,
        *,
        url: str,
        max_bytes: int,
        redirect_guard: Callable[[str], str],
    ) -> Mapping[str, object] | None: ...


class TavilyLifecycleSearchAdapter:
    """Decode an injected Tavily client without owning product decisions."""

    identity = "tavily"

    def __init__(self, *, client: object, fetch_transport: Callable[..., object]):
        self._client = client
        self._fetch_transport = fetch_transport

    def search(self, *, query: str, max_results: int) -> Mapping[str, object]:
        try:
            payload = self._client.search(
                query=query,
                topic="finance",
                max_results=max_results,
                include_answer=False,
            )
        except LifecycleSearchFailure:
            raise
        except _UnsafeLifecycleUrl:
            raise LifecycleSearchFailure("unsupported_content") from None
        except Exception:
            raise LifecycleSearchFailure("network_error") from None
        if not isinstance(payload, Mapping):
            raise LifecycleSearchFailure("extract_failed")
        return {
            "results": payload.get("results", []),
            "usage": payload.get("usage", {}),
        }

    def fetch(
        self,
        *,
        url: str,
        max_bytes: int,
        redirect_guard: Callable[[str], str],
    ) -> Mapping[str, object] | None:
        try:
            payload = self._fetch_transport(
                url=url,
                max_bytes=max_bytes,
                redirect_guard=redirect_guard,
            )
        except LifecycleSearchFailure:
            raise
        except _UnsafeLifecycleUrl:
            raise LifecycleSearchFailure("unsupported_content") from None
        except Exception:
            raise LifecycleSearchFailure("network_error") from None
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise LifecycleSearchFailure("extract_failed")
        return payload


def _clean_text(value: object, *, limit: int) -> str:
    parser = _VisibleTextParser()
    parser.feed(str(value or ""))
    parser.close()
    text = _SPACE_RE.sub(" ", " ".join(parser.parts)).strip()
    return text[:limit]


def _literal_host_is_forbidden(host: str) -> bool:
    normalized = host.rstrip(".").casefold()
    if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith(
        ".localhost"
    ):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return not address.is_global


def _canonical_https_url(
    value: object,
    *,
    resolver: Callable[[str], tuple[str, ...]] | None,
) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
        host_value = parsed.hostname
        port = parsed.port
    except ValueError:
        raise _UnsafeLifecycleUrl() from None
    if parsed.scheme.casefold() != "https" or not host_value:
        raise _UnsafeLifecycleUrl()
    if parsed.username is not None or parsed.password is not None:
        raise _UnsafeLifecycleUrl()
    host = host_value.rstrip(".").casefold()
    if _literal_host_is_forbidden(host):
        raise _UnsafeLifecycleUrl()
    if resolver is not None:
        try:
            addresses = tuple(resolver(host))
        except Exception:
            raise _UnsafeLifecycleUrl() from None
        try:
            forbidden_address = any(
                _literal_host_is_forbidden(address) for address in addresses
            )
        except (AttributeError, TypeError, ValueError):
            raise _UnsafeLifecycleUrl() from None
        if not addresses or forbidden_address:
            raise _UnsafeLifecycleUrl()
    netloc = host if port in {None, 443} else f"{host}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def build_lifecycle_query_plan(observation: Mapping[str, object]) -> tuple[str, ...]:
    ticker = _clean_text(observation.get("ticker"), limit=20)
    issuer = _clean_text(observation.get("issuer_name"), limit=240)
    cik = _clean_text(observation.get("cik"), limit=10)
    source_ref = _clean_text(observation.get("source_ref"), limit=160)
    identity = " ".join(part for part in (ticker, issuer, cik, source_ref) if part)
    queries = [
        f"{identity} official filing exchange issuer event",
        f"{ticker} {issuer} symbol venue delisting successor",
    ]
    kinds = {
        str(item.get("event_type") or "")
        for item in observation.get("kinds", [])
        if isinstance(item, Mapping)
    }
    if kinds & {"merger_agreement", "merger_proxy", "acquisition_completed"}:
        queries.append(f"{ticker} {issuer} acquisition merger consideration terms")
    return tuple(queries[:MAX_QUERIES])


def add_manual_evidence(
    *,
    store: SecurityLifecycleInvestigationStore,
    case_id: str,
    text: str | None,
    url: str | None,
    at: str,
) -> str:
    if (text is None) == (url is None):
        raise ValueError("manual_evidence_shape")
    if text is not None:
        excerpt = _clean_text(text, limit=16000)
        if not excerpt:
            raise ValueError("manual_text")
        return store.add_evidence(
            case_id=case_id,
            run_id=None,
            kind="manual_text",
            adapter="manual",
            excerpt=excerpt,
            source_url=None,
            title=None,
            publisher=None,
            domain=None,
            source_published_at=None,
            retrieved_at=None,
            mime_type="text/plain",
            document_status=None,
            at=at,
        )
    source_url = _canonical_https_url(url, resolver=None)
    return store.add_evidence(
        case_id=case_id,
        run_id=None,
        kind="manual_url",
        adapter="manual",
        excerpt=source_url,
        source_url=source_url,
        title=None,
        publisher=None,
        domain=urlsplit(source_url).hostname,
        source_published_at=None,
        retrieved_at=None,
        mime_type=None,
        document_status=None,
        at=at,
    )


def _safe_usage(values: object, *, query_count: int, fetch_count: int) -> dict:
    result: dict[str, int | float | bool] = {
        "query_count": query_count,
        "fetch_count": fetch_count,
    }
    if isinstance(values, Mapping):
        for key in sorted(values):
            if key not in {
                "search_requests",
                "fetch_requests",
                "credits_used",
                "response_time_ms",
            }:
                continue
            value = values[key]
            if isinstance(value, bool) or isinstance(value, int):
                result[str(key)] = value
            elif isinstance(value, float) and math.isfinite(value):
                result[str(key)] = value
    return result


def _result_rows(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw = payload.get("results", [])
    if not isinstance(raw, list):
        raise LifecycleSearchFailure("extract_failed")
    return [item for item in raw if isinstance(item, Mapping)]


def run_tavily_investigation(
    *,
    store: SecurityLifecycleInvestigationStore,
    case_id: str,
    observation: Mapping[str, object],
    adapter: LifecycleSearchAdapter,
    permission: Callable[[PermissionClass, str, dict], None] = require_permission,
    resolver: Callable[[str], tuple[str, ...]],
    at: str,
) -> dict:
    if adapter.identity != "tavily":
        raise ValueError("adapter")
    queries = build_lifecycle_query_plan(observation)
    run_id = store.create_investigation_run(
        case_id=case_id,
        trigger="attended_user",
        adapter="tavily",
        query_plan=queries,
        at=at,
    )
    detail = {"adapter": "tavily", "case_id": case_id, "query_count": len(queries)}
    fetch_count = 0
    usage: dict[str, Any] = {}

    def fail_run(failure_code: str) -> dict:
        run = store.get_investigation_run(run_id)
        if run["status"] == "queued":
            store.start_investigation_run(run_id, at=at)
        return store.fail_investigation_run(
            run_id,
            failure_code=failure_code,
            fetch_count=fetch_count,
            usage=_safe_usage(
                usage,
                query_count=len(queries),
                fetch_count=fetch_count,
            ),
            at=at,
        )

    try:
        permission(
            PermissionClass.external_web_access,
            "security_lifecycle_investigation",
            detail,
        )
        permission(
            PermissionClass.metered_spend,
            "security_lifecycle_investigation",
            detail,
        )
        store.start_investigation_run(run_id, at=at)
        by_url: dict[str, Mapping[str, object]] = {}
        for query in queries:
            payload = adapter.search(query=query, max_results=MAX_RESULTS_PER_QUERY)
            if not isinstance(payload, Mapping):
                raise LifecycleSearchFailure("extract_failed")
            if isinstance(payload.get("usage"), Mapping):
                usage.update(payload["usage"])
            for item in _result_rows(payload)[:MAX_RESULTS_PER_QUERY]:
                try:
                    url = _canonical_https_url(item.get("url"), resolver=resolver)
                except _UnsafeLifecycleUrl:
                    raise LifecycleSearchFailure("unsupported_content") from None
                by_url.setdefault(url, item)
        selected = list(by_url.items())[:MAX_FETCHES]
        for url, item in selected:
            snippet = _clean_text(
                item.get("content") or item.get("snippet"), limit=16000
            )
            if not snippet:
                snippet = _clean_text(item.get("title") or url, limit=16000)
            store.add_evidence(
                case_id=case_id,
                run_id=run_id,
                kind="web_search_result",
                adapter="tavily",
                excerpt=snippet,
                source_url=url,
                title=_clean_text(item.get("title"), limit=500) or None,
                publisher=_clean_text(item.get("publisher"), limit=240) or None,
                domain=urlsplit(url).hostname,
                source_published_at=(
                    _clean_text(item.get("published_at"), limit=40) or None
                ),
                retrieved_at=at,
                mime_type=None,
                document_status=None,
                at=at,
            )

            def redirect_guard(candidate: str) -> str:
                return _canonical_https_url(candidate, resolver=resolver)

            fetch_count += 1
            fetched = adapter.fetch(
                url=url,
                max_bytes=MAX_FETCH_BYTES,
                redirect_guard=redirect_guard,
            )
            if fetched is None:
                continue
            final_url = _canonical_https_url(
                fetched.get("url") or url, resolver=resolver
            )
            excerpt = _clean_text(fetched.get("content"), limit=16000)
            if excerpt:
                store.add_evidence(
                    case_id=case_id,
                    run_id=run_id,
                    kind="web_page_excerpt",
                    adapter="tavily",
                    excerpt=excerpt,
                    source_url=final_url,
                    title=_clean_text(item.get("title"), limit=500) or None,
                    publisher=_clean_text(item.get("publisher"), limit=240) or None,
                    domain=urlsplit(final_url).hostname,
                    source_published_at=(
                        _clean_text(item.get("published_at"), limit=40) or None
                    ),
                    retrieved_at=at,
                    mime_type=_clean_text(fetched.get("mime_type"), limit=127) or None,
                    document_status=None,
                    at=at,
                )
        safe_usage = _safe_usage(
            usage,
            query_count=len(queries),
            fetch_count=fetch_count,
        )
        return store.succeed_investigation_run(
            run_id,
            result_count=len(selected),
            fetch_count=fetch_count,
            usage=safe_usage,
            at=at,
        )
    except LifecycleSearchFailure as exc:
        return fail_run(exc.code)
    except PermissionError:
        return fail_run("permission_denied")
    except _UnsafeLifecycleUrl:
        return fail_run("unsupported_content")


__all__ = [
    "LifecycleSearchAdapter",
    "LifecycleSearchFailure",
    "TavilyLifecycleSearchAdapter",
    "add_manual_evidence",
    "build_lifecycle_query_plan",
    "run_tavily_investigation",
]
