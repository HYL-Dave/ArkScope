"""Per-call current-local market-read provenance.

The DAL backend is a process-wide singleton shared across concurrent requests, so a
per-instance attribute would race. We instead record the origin of a market-domain
read in a ``contextvars.ContextVar`` — per-request isolated (each sync route runs in
its own context; thread-reuse is handled by ``reset()`` at route start) — and let the
route read it back after the call.

The current local market composition records ``local`` when data is served and
``none`` for an honest miss. This is per-call provenance, not inference.
"""

from __future__ import annotations

import contextvars

# domain ('iv' | 'fundamentals' | ...) -> 'local' | 'none'
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
