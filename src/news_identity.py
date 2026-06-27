"""Canonical identity helpers for local and mirrored news rows."""

from __future__ import annotations

import hashlib


def canonical_article_hash(ticker: str, title: str, published_at: str) -> str:
    """Return the canonical news identity for the stored ticker, title, and UTC date."""
    date10 = (published_at or "")[:10]
    raw = f"{ticker}|{title}|{date10}".encode("utf-8")
    # No [:64]: a SHA-256 hex digest is already exactly 64 characters. This is byte-identical
    # to the existing stored hash contract.
    return hashlib.sha256(raw).hexdigest()
