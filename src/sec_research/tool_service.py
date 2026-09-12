"""Validated SEC tool orchestration over the durable query/acquisition owners."""

from contextlib import ExitStack
from datetime import datetime

from . import schema
from .captures import CaptureStore
from .document_queries import DocumentQueries, validate_document_query
from .document_service import DocumentService, _catalog
from .document_store import DocumentStore
from .documents import parse_filing_id
from .issuer_store import IssuerStore
from .issuers import parse_issuer
from .queries import StoredQueries, _decode, validate_query
from .service import ResearchService, _TRANSPORT_CODES, _STORAGE_CODES
from .store import _timestamp


_QUERY_CODES = {"sec_issuer_invalid", "sec_research_query_invalid",
                "sec_research_cursor_invalid", "sec_research_cursor_mismatch"}
_FAILURE_CODES = _QUERY_CODES | _TRANSPORT_CODES | _STORAGE_CODES | {
    "issuer_map_busy", "sec_research_refresh_busy", "sec_research_schema_mismatch",
    "sec_research_receipt_binding_invalid", "sec_research_config_invalid", "cancelled",
}
_KINDS = {"list_sec_filings": "filings", "get_sec_financial_facts": "facts"}


def _unavailable(code, *, resolution=None):
    return dict(status="unavailable", data=[], gaps=[{"code": code}] if resolution is None else resolution["gaps"],
                observed_at=None if resolution is None else resolution["observed_at"],
                coverage={} if resolution is None else {"issuer": resolution}, next_cursor=None)


def _installed(store):
    if not store.paths.market_db_path.exists():
        return False
    with store.connect(readonly=True) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE lower(name) GLOB 'sec_research_*'").fetchone():
            return False
        schema.verify(conn)
    return True


def _recent(observed_at, now):
    if observed_at is None:
        return False
    elapsed = datetime.fromisoformat(_timestamp(now).replace("Z", "+00:00")) - datetime.fromisoformat(
        _timestamp(observed_at).replace("Z", "+00:00"))
    # Application freshness policy, not an assertion about SEC publishing cadence.
    return 0 <= elapsed.total_seconds() < 24 * 60 * 60


def _validate(name, arguments, check):
    if not isinstance(arguments, dict) or check is not None and not callable(check):
        raise ValueError("sec_research_query_invalid")
    params = dict(arguments)
    freshness = params.pop("freshness", "auto")
    if freshness not in ("auto", "stored", "refresh"):
        raise ValueError("sec_research_query_invalid")
    if name == "read_sec_filing":
        identifier = params.pop("filing_id", None)
        params = validate_document_query(identifier, **params)
        pinned = params["cursor"] is not None or params["capture_id"] is not None
        kind = "document"
    elif name in _KINDS:
        kind = _KINDS[name]
        identifier = params.pop("issuer", None)
        issuer_kind, value = parse_issuer(identifier)
        token = _decode(params["cursor"]) if params.get("cursor") is not None else None
        # A ticker continuation belongs to the original CIK, never a newer map.
        cik = value if issuer_kind == "cik" else token["cik"] if token else "0000000001"
        validate_query(cik, kind, **params)
        pinned = params.get("cursor") is not None or params.get("fact_ids") is not None
    else:
        raise ValueError("sec_research_query_invalid")
    if pinned and freshness == "refresh":
        raise ValueError("sec_research_query_invalid")
    return kind, identifier, params, freshness, pinned


class ToolService:
    def __init__(self, store, *, acquisition_factory, clock):
        self.store, self.acquisition_factory, self.clock = store, acquisition_factory, clock

    def invoke(self, name: str, arguments: dict, *, check=None) -> dict:
        """Validate first, then read or perform one bounded additive acquisition."""
        try:
            kind, identifier, params, freshness, pinned = _validate(name, arguments, check)
        except (ValueError, TypeError) as exc:
            code = getattr(exc, "code", str(exc))
            return _unavailable(code if code in _QUERY_CODES else "sec_research_query_invalid")
        try:
            installed = _installed(self.store)
            stored_only = freshness == "stored" or pinned
            if not installed and stored_only:
                return _unavailable("sec_research_not_installed")
            with ExitStack() as stack:
                acquisition = None

                def acquire():
                    nonlocal acquisition, installed
                    if acquisition is None:
                        if check is not None:
                            try:
                                check()
                            except Exception:
                                raise ValueError("cancelled") from None
                        from .runtime import require_acquisition
                        require_acquisition(name)
                        acquisition = stack.enter_context(self.acquisition_factory())
                        installed = True
                    return acquisition

                if kind == "document":
                    return self._document(identifier, params, freshness, stored_only, installed, acquire, check)
                issuer_kind, value = parse_issuer(identifier)
                issuers = IssuerStore(self.store)
                if issuer_kind == "cik":
                    cik = value
                elif params.get("cursor") is not None:
                    cik = _decode(params["cursor"])["cik"]
                else:
                    observation = issuers.latest() if installed else None
                    if not stored_only and (freshness == "refresh" or observation is None
                            or observation["status"] != "ok"
                            or not _recent(observation["observed_at"], self.clock())):
                        captures, transport, _ = acquire()
                        issuers.refresh(transport, captures, clock=self.clock, check=check)
                    resolution = issuers.resolve(identifier)
                    if resolution["status"] != "ok":
                        return _unavailable("issuer_unavailable", resolution=resolution)
                    cik = resolution["cik"]
                receipt = self.store.latest_receipt(cik) if installed else None
                recent = receipt is not None and _recent(receipt["observed_at"], self.clock())
                if not stored_only and (freshness == "refresh" or not recent or receipt["pending"]):
                    captures, transport, _ = acquire()
                    ResearchService(self.store, captures, transport, clock=self.clock).refresh(
                        cik, max_sources=4, resume=freshness == "auto" and recent, check=check)
                return getattr(StoredQueries(self.store), kind)(cik, **params)
        except Exception as exc:
            code = getattr(exc, "code", str(exc))
            return _unavailable(code if code in _FAILURE_CODES else "sec_research_store_unavailable")

    def _document(self, filing_id, params, freshness, stored_only, installed, acquire, check):
        captures = CaptureStore(self.store, budget=None)
        queries = DocumentQueries(self.store, captures)
        if stored_only:
            return queries.read(filing_id, **params)
        attempt = DocumentStore(self.store).latest_attempt(filing_id, params["document_id"]) if installed else None
        if freshness == "auto" and attempt is not None and attempt["capture_id"] is not None:
            return queries.read(filing_id, **params)
        cik, _ = parse_filing_id(filing_id)
        receipt = self.store.latest_receipt(cik) if installed else None
        recent = receipt is not None and _recent(receipt["observed_at"], self.clock())
        authority = _catalog(self.store, filing_id)[0] if installed and recent else None
        captures, transport, reader_factory = acquire()
        if not recent or receipt["pending"] or authority is None:
            ResearchService(self.store, captures, transport, clock=self.clock).refresh(
                cik, max_sources=4, resume=recent and bool(receipt["pending"]), check=check)
        observation = DocumentService(self.store, captures, reader_factory=reader_factory, clock=self.clock).refresh(
            filing_id, params["document_id"], check=check)
        # A lease/storage failure may have no durable attempt. Never reopen old success.
        if observation["capture_id"] is None:
            from .document_queries import _unavailable as document_unavailable
            return document_unavailable(gaps=observation["gaps"], observed_at=observation["observed_at"])
        return queries.read(filing_id, **params)
