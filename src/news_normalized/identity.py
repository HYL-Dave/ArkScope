import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import ArticleKey, KeyKind


IDENTITY_VERSION = "news-id-v1"


def normalize_identity_text(value: str) -> str:
    text = html.unescape(value or "")
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def normalize_timestamp(value: str) -> str:
    text = (value or "").strip()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    if text.endswith("+0000"):
        return f"{text[:-5]}Z"
    return text


def normalize_stable_url(value: str) -> str:
    if not value or not value.strip():
        return ""
    parts = urlsplit(value.strip())
    query_items = (
        (key, query_value)
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
    )
    query = urlencode(sorted(query_items))
    userinfo = ""
    if parts.username is not None:
        userinfo = parts.username
        if parts.password is not None:
            userinfo = f"{userinfo}:{parts.password}"
        userinfo = f"{userinfo}@"
    host = (parts.hostname or "").casefold()
    if ":" in host:
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port is not None else ""
    return urlunsplit(
        (
            parts.scheme.casefold(),
            f"{userinfo}{host}{port}",
            parts.path.rstrip("/"),
            query,
            "",
        )
    )


def fallback_identity_hash(
    *, source: str, publisher: str, title: str, published_at: str
) -> str:
    payload = "\0".join(
        (
            IDENTITY_VERSION,
            source.casefold(),
            normalize_identity_text(publisher),
            normalize_identity_text(title),
            normalize_timestamp(published_at),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    normalized_provider_id = (provider_article_id or "").strip()
    if normalized_provider_id:
        keys.append(
            ArticleKey(source, KeyKind.PROVIDER_ID, normalized_provider_id, True)
        )

    stable_url = normalize_stable_url(url)
    if stable_url:
        keys.append(ArticleKey(source, KeyKind.URL, stable_url, True))

    keys.append(
        ArticleKey(
            source,
            KeyKind.FALLBACK,
            fallback_identity_hash(
                source=source,
                publisher=publisher,
                title=title,
                published_at=published_at,
            ),
            False,
        )
    )
    return tuple(keys)
