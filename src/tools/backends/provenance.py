"""Per-call market-read provenance (local vs PG-fallback).

The DAL backend is a process-wide singleton shared across concurrent requests, so a
per-instance attribute would race. We instead record the origin of a market-domain
read in a ``contextvars.ContextVar`` — per-request isolated (each sync route runs in
its own context; thread-reuse is handled by ``reset()`` at route start) — and let the
route read it back after the call.

Recorded ONLY by :class:`LocalMarketDatabaseBackend` (i.e. when local-first routing is
enabled): ``local`` (served from the local market DB) / ``pg_fallback`` (local missed,
served from PG) / ``none`` (no data anywhere). When routing is OFF there is no local
layer and nothing is recorded — the route maps that to ``pg`` (PG is the only source)
or ``none`` from the result itself. This is TRUE per-call provenance, not inference.
"""

from __future__ import annotations

import contextvars

# domain ('iv' | 'fundamentals' | ...) → 'local' | 'pg_fallback' | 'none'
_PROVENANCE: contextvars.ContextVar = contextvars.ContextVar("market_read_provenance", default=None)


def reset() -> None:
    """Start a fresh provenance scope for this request (defensive vs thread reuse)."""
    _PROVENANCE.set({})


def record(domain: str, source: str) -> None:
    """Record the origin of a market-domain read for the current request."""
    d = _PROVENANCE.get()
    if d is None:
        d = {}
        _PROVENANCE.set(d)
    d[domain] = source


def read(domain: str):
    """The recorded origin for ``domain`` this request, or None if not recorded
    (routing off / domain not read)."""
    d = _PROVENANCE.get()
    return d.get(domain) if d else None


def fallback(backend_type: str, result_empty: bool) -> str:
    """Source for an UN-recorded read (no local-first layer). ``none`` if the result
    is empty; otherwise the non-local origin by backend type: ``file`` for the
    file-backed dev config, ``pg`` for a PostgreSQL backend (the canonical
    deployment, where PG is the primary source)."""
    if result_empty:
        return "none"
    return "file" if backend_type == "FileBackend" else "pg"
