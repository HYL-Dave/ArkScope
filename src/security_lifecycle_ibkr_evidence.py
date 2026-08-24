"""Read one bounded contract-state snapshot from an injected IBKR client."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ContextManager, Protocol

from ib_insync import Contract, RequestError, Stock

from src.security_lifecycle_sec_evidence import IdentityContext


_ENTITLEMENT_ERROR_CODES = frozenset({354, 10089, 10090, 10091, 10167, 10168})
_MAX_EXCERPT_BYTES = 4096
_MAX_VALID_EXCHANGES = 32


class IBKRContractGateway(Protocol):
    def isConnected(self) -> bool: ...

    def reqContractDetails(self, contract: Contract) -> Iterable[Any]: ...


GatewayLock = Callable[[float], ContextManager[None]]


@dataclass(frozen=True)
class IbkrContractEvidence:
    evidence_id: str
    source_family: str
    adapter: str
    kind: str
    source_url: None
    title: str
    publisher: str
    domain: None
    source_published_at: None
    retrieved_at: str
    excerpt: str
    content_sha256: str
    source_document_sha256: None
    source_locator: Mapping[str, Any]
    evidence_dedupe_key: str


@dataclass(frozen=True)
class IbkrContractEvidenceResult:
    evidence: tuple[IbkrContractEvidence, ...]
    blockers: tuple[str, ...]
    source_families: tuple[str, ...]
    corroboration_family_count: int
    requests_made: int


def _timestamp(value: str) -> str:
    normalized = str(value or "").strip()
    parseable = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise ValueError("retrieved_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at")
    return normalized


def _text(value: object, *, field: str, limit: int, required: bool = False) -> str:
    normalized = str(value or "").strip()
    if "\0" in normalized or len(normalized.encode("utf-8")) > limit:
        raise ValueError(f"ibkr_contract_{field}")
    if required and not normalized:
        raise ValueError(f"ibkr_contract_{field}")
    return normalized


def _valid_exchanges(value: object) -> tuple[str, ...]:
    if value is None:
        raw: Iterable[object] = ()
    elif isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, Iterable):
        raw = value
    else:
        raise ValueError("ibkr_contract_valid_exchanges")
    exchanges = tuple(
        sorted(
            {
                _text(item, field="valid_exchange", limit=40, required=True)
                for item in raw
                if str(item or "").strip()
            }
        )
    )
    if len(exchanges) > _MAX_VALID_EXCHANGES:
        raise ValueError("ibkr_contract_valid_exchanges")
    return exchanges


def _snapshot(detail: object, *, retrieved_at: str) -> dict[str, Any]:
    contract = getattr(detail, "contract", detail)
    raw_con_id = getattr(contract, "conId", None)
    if isinstance(raw_con_id, bool):
        raise ValueError("ibkr_contract_con_id")
    try:
        con_id = int(raw_con_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("ibkr_contract_con_id") from exc
    if con_id <= 0:
        raise ValueError("ibkr_contract_con_id")

    return {
        "symbol": _text(
            getattr(contract, "symbol", None),
            field="symbol",
            limit=32,
            required=True,
        ),
        "localSymbol": _text(
            getattr(contract, "localSymbol", None),
            field="local_symbol",
            limit=64,
        ),
        "conId": con_id,
        "secType": _text(
            getattr(contract, "secType", None),
            field="security_type",
            limit=20,
            required=True,
        ),
        "primaryExchange": _text(
            getattr(contract, "primaryExchange", None),
            field="primary_exchange",
            limit=80,
        ),
        "validExchanges": list(
            _valid_exchanges(getattr(detail, "validExchanges", None))
        ),
        "currency": _text(
            getattr(contract, "currency", None),
            field="currency",
            limit=12,
            required=True,
        ),
        "retrieved_at": retrieved_at,
    }


def _queries(context: IdentityContext, *, max_queries: int) -> tuple[Contract, ...]:
    aliases = (context.current_ticker,) + tuple(
        alias for alias in context.ticker_aliases if alias != context.current_ticker
    )
    queries: tuple[Contract, ...] = tuple(
        Contract(conId=con_id, exchange="SMART") for con_id in context.ibkr_conids
    ) + tuple(Stock(alias, "SMART", "USD") for alias in aliases)
    if len(queries) > max_queries:
        raise ValueError("ibkr_identity_candidates_exceed_max_queries")
    return queries


def _blocked(code: str, *, requests_made: int) -> IbkrContractEvidenceResult:
    return IbkrContractEvidenceResult((), (code,), (), 0, requests_made)


def _entitlement_failure(exc: RequestError) -> bool:
    code = getattr(exc, "code", None)
    return type(code) is int and code in _ENTITLEMENT_ERROR_CODES


def read_ibkr_contract_evidence(
    *,
    gateway: IBKRContractGateway,
    gateway_lock: GatewayLock,
    context: IdentityContext,
    retrieved_at: str,
    lock_timeout_s: float = 30.0,
    max_queries: int = 8,
) -> IbkrContractEvidenceResult:
    """Query an already-connected client while holding the caller's shared lock."""
    if not callable(getattr(gateway, "isConnected", None)):
        raise TypeError("gateway.isConnected")
    if not callable(getattr(gateway, "reqContractDetails", None)):
        raise TypeError("gateway.reqContractDetails")
    if not callable(gateway_lock):
        raise TypeError("gateway_lock")
    if isinstance(lock_timeout_s, bool) or not isinstance(lock_timeout_s, (int, float)):
        raise ValueError("lock_timeout_s")
    if not 0 < float(lock_timeout_s) <= 1800:
        raise ValueError("lock_timeout_s")
    if type(max_queries) is not int or not 1 <= max_queries <= 16:
        raise ValueError("max_queries")

    at = _timestamp(retrieved_at)
    queries = _queries(context, max_queries=max_queries)
    requests_made = 0
    detail_rows: list[object] = []

    try:
        with gateway_lock(float(lock_timeout_s)):
            if not gateway.isConnected():
                return _blocked("ibkr_gateway_unavailable", requests_made=0)
            for contract in queries:
                requests_made += 1
                try:
                    details = gateway.reqContractDetails(contract)
                except RequestError as exc:
                    if _entitlement_failure(exc):
                        return _blocked(
                            "ibkr_entitlement_denied",
                            requests_made=requests_made,
                        )
                    raise
                if details is None:
                    continue
                detail_rows.extend(tuple(details))
    except RequestError:
        return _blocked("ibkr_gateway_unavailable", requests_made=requests_made)
    except (ConnectionError, TimeoutError, OSError):
        return _blocked("ibkr_gateway_unavailable", requests_made=requests_made)

    snapshots = {
        json.dumps(
            _snapshot(detail, retrieved_at=at),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        for detail in detail_rows
    }
    if not snapshots:
        return _blocked("ibkr_contract_missing", requests_made=requests_made)
    if len(snapshots) != 1:
        return _blocked("ibkr_contract_ambiguous", requests_made=requests_made)

    excerpt = snapshots.pop()
    if len(excerpt.encode("utf-8")) > _MAX_EXCERPT_BYTES:
        raise ValueError("ibkr_contract_snapshot_too_large")
    snapshot = json.loads(excerpt)
    content_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    evidence = IbkrContractEvidence(
        evidence_id="sle_" + content_digest[:32],
        source_family="market_infrastructure",
        adapter="ibkr_contract",
        kind="market_infrastructure_snapshot",
        source_url=None,
        title=f'IBKR contract snapshot: {snapshot["symbol"]}',
        publisher="Interactive Brokers",
        domain=None,
        source_published_at=None,
        retrieved_at=at,
        excerpt=excerpt,
        content_sha256=content_digest,
        source_document_sha256=None,
        source_locator={"snapshot": snapshot},
        evidence_dedupe_key=f"ibkr_contract:{content_digest}",
    )
    return IbkrContractEvidenceResult(
        evidence=(evidence,),
        blockers=(),
        source_families=("market_infrastructure",),
        corroboration_family_count=1,
        requests_made=requests_made,
    )
