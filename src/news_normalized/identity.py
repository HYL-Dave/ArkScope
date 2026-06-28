import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import ArticleKey, KeyKind


IDENTITY_VERSION = "news-id-v1"
_TRACKING_QUERY_KEYS = frozenset(
    {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}
)
_FRACTION_RE = re.compile(r"[.,](\d+)(?=(?:Z|[+-]\d{2}:?\d{2})$)")


def normalize_identity_text(value: str) -> str:
    text = html.unescape(value or "")
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def normalize_timestamp(value: str) -> str:
    """Convert aware ISO timestamps to UTC; preserve trimmed unparseable values."""
    text = (value or "").strip()
    parseable = text
    fraction = _FRACTION_RE.search(text)
    if fraction:
        parser_fraction = f"{fraction.group(1):0<6}"[:6]
        parseable = (
            f"{parseable[:fraction.start(1)]}{parser_fraction}"
            f"{parseable[fraction.end(1):]}"
        )
    if parseable.endswith("Z"):
        parseable = f"{parseable[:-1]}+00:00"
    elif re.search(r"[+-]\d{4}$", parseable):
        parseable = f"{parseable[:-2]}:{parseable[-2:]}"

    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        return text

    normalized = parsed.astimezone(timezone.utc)
    result = normalized.strftime("%Y-%m-%dT%H:%M:%S")
    if fraction:
        result = f"{result}.{fraction.group(1)}"
    return f"{result}Z"


def normalize_stable_url(value: str) -> str:
    if not value or not value.strip():
        return ""
    try:
        parts = urlsplit(value.strip())
        scheme = parts.scheme.casefold()
        host = parts.hostname
        parsed_port = parts.port
    except (UnicodeError, ValueError):
        return ""
    if scheme not in {"http", "https"} or not host or any(
        character.isspace() for character in host
    ):
        return ""
    raw_host_port = parts.netloc.rsplit("@", 1)[-1]
    if parsed_port is None and raw_host_port.endswith(":"):
        return ""

    query_items = [
        (key, query_value)
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    query = urlencode(query_items)
    userinfo = ""
    if parts.username is not None:
        userinfo = parts.username
        if parts.password is not None:
            userinfo = f"{userinfo}:{parts.password}"
        userinfo = f"{userinfo}@"
    host = host.casefold()
    if ":" in host:
        host = f"[{host}]"
    port = ""
    if parsed_port is not None:
        port = f":{raw_host_port.rsplit(':', 1)[-1]}"
    return urlunsplit(
        (
            scheme,
            f"{userinfo}{host}{port}",
            parts.path,
            query,
            "",
        )
    )


def _canonical_source(source: str) -> str:
    return (source or "").strip().casefold()


def _fallback_hash(
    *, canonical_source: str, publisher: str, title: str, published_at: str
) -> str:
    payload = "\0".join(
        (
            IDENTITY_VERSION,
            canonical_source,
            normalize_identity_text(publisher),
            normalize_identity_text(title),
            normalize_timestamp(published_at),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fallback_identity_hash(
    *, source: str, publisher: str, title: str, published_at: str
) -> str:
    return _fallback_hash(
        canonical_source=_canonical_source(source),
        publisher=publisher,
        title=title,
        published_at=published_at,
    )


def build_identity_keys(
    *,
    source: str,
    provider_article_id: str | None,
    url: str,
    publisher: str,
    title: str,
    published_at: str,
) -> tuple[ArticleKey, ...]:
    keys = []
    canonical_source = _canonical_source(source)
    normalized_provider_id = (provider_article_id or "").strip()
    if normalized_provider_id:
        keys.append(
            ArticleKey(
                canonical_source, KeyKind.PROVIDER_ID, normalized_provider_id, True
            )
        )

    stable_url = normalize_stable_url(url)
    if stable_url:
        keys.append(ArticleKey(canonical_source, KeyKind.URL, stable_url, True))

    keys.append(
        ArticleKey(
            canonical_source,
            KeyKind.FALLBACK,
            _fallback_hash(
                canonical_source=canonical_source,
                publisher=publisher,
                title=title,
                published_at=published_at,
            ),
            False,
        )
    )
    return tuple(keys)
