"""Bounded manual evidence ingestion for lifecycle cases."""

from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import re
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore


_SPACE_RE = re.compile(r"\s+")


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


def canonical_manual_https_url(value: object) -> str:
    """Validate and normalize a manual evidence URL without network access."""
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
        host_value = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("unsafe_url") from None
    if parsed.scheme.casefold() != "https" or not host_value:
        raise ValueError("unsafe_url")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("unsafe_url")
    host = host_value.rstrip(".").casefold()
    if _literal_host_is_forbidden(host):
        raise ValueError("unsafe_url")
    rendered_host = f"[{host}]" if ":" in host else host
    netloc = rendered_host if port in {None, 443} else f"{rendered_host}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def add_manual_evidence(
    *,
    store: SecurityLifecycleInvestigationStore,
    case_id: str,
    text: str | None,
    url: str | None,
    at: str,
    case_identity: Mapping[str, object] | None = None,
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
            case_identity=case_identity,
        )
    source_url = canonical_manual_https_url(url)
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
        case_identity=case_identity,
    )


__all__ = ["add_manual_evidence", "canonical_manual_https_url"]
