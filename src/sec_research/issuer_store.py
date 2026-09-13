"""Append-only, capture-budgeted issuer-map observations and stored resolution."""

import json

from data_sources.sec_transport import SecTransportFailure

from . import schema
from .capture_lock import _lease, store_operation
from .common import SourceError
from .issuers import TICKER_MAP_URL, parse_issuer, parse_ticker_map
from .service import _TRANSPORT_CODES, _storage_code
from .store import Store, _bounded_json, _timestamp


class IssuerStore:
    def __init__(self, store: Store):
        self.store = store

    def latest(self) -> dict | None:
        """Read the latest attempt, including failed/interrupted observations."""
        if not self.store.paths.market_db_path.exists():
            return None
        with self.store.connect(readonly=True) as conn:
            if not schema._owned(conn):
                return None
            schema.verify(conn)
            row = conn.execute("SELECT * FROM sec_research_issuer_maps ORDER BY observation_id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        result = dict(row)
        result["symbols"] = json.loads(result["symbols"])
        result["gaps"] = json.loads(result["gaps"])
        return result

    @store_operation
    def resolve(self, issuer: str) -> dict:
        """Return a stored resolution observation; explicit CIKs need no map I/O."""
        kind, value = parse_issuer(issuer)
        result = dict(status="ok", cik=value if kind == "cik" else None,
                      candidates=[], observed_at=None, source=None, gaps=[])
        if kind == "cik":
            return result
        observation = self.latest()
        result.update(status="unavailable", source={"url": TICKER_MAP_URL, "sha256": None})
        if observation is None:
            result["gaps"] = [{"code": "issuer_map_unobserved"}]
            return result
        result.update(observed_at=observation["observed_at"], gaps=observation["gaps"],
                      source={"url": observation["source_url"], "sha256": observation["object_sha256"]})
        if observation["status"] != "ok":
            return result
        candidates = observation["symbols"].get(value, [])
        result["candidates"] = candidates
        if len(candidates) == 1:
            result.update(status="ok", cik=candidates[0])
        else:
            result["gaps"] = [{"code": "issuer_ambiguous" if candidates else "issuer_not_found"}]
        return result

    def _record(self, *, status, observed_at, digest=None, symbols=None, code=None):
        with self.store._write() as conn:
            conn.execute("""INSERT INTO sec_research_issuer_maps
                (status, object_sha256, observed_at, source_url, symbols, gaps)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (status, digest, _timestamp(observed_at), TICKER_MAP_URL,
                 _bounded_json(symbols or {}), _bounded_json([{"code": code}] if code else [])))

    def refresh(self, transport, captures, *, clock, check) -> dict:
        """Make at most one governed request under a separate root-scoped lease."""
        if check is not None and not callable(check):
            raise ValueError("sec_research_query_invalid")
        with _lease(self.store.paths.capture_root, ".issuer-map.lock", "issuer_map_busy"):
            self._record(status="unavailable", observed_at=clock(), code="issuer_map_interrupted")
            digest = None
            try:
                if check is not None:
                    try:
                        check()
                    except Exception:
                        raise SourceError("cancelled") from None
                captures.preflight()
                response = transport.get(TICKER_MAP_URL, **({"check": check} if check is not None else {}))
                response.raise_for_status()
                body = response.body
                digest = captures.put(body)
                try:
                    symbols = parse_ticker_map(body)
                except SourceError:
                    raise SourceError("issuer_map_invalid") from None
                self._record(status="ok", observed_at=clock(), digest=digest, symbols=symbols)
            except Exception as exc:
                if isinstance(exc, SourceError) and exc.code in {"cancelled", "issuer_map_invalid"}:
                    code = exc.code
                elif isinstance(exc, SecTransportFailure):
                    code = exc.code if exc.code in _TRANSPORT_CODES else "sec_transport_unavailable"
                elif isinstance(exc, (ValueError, OSError)):
                    code = _storage_code(exc)
                else:
                    code = "sec_transport_unavailable"
                self._record(status="unavailable", observed_at=clock(), digest=digest, code=code)
            return self.latest()
