"""Read one bounded contract-state snapshot from an injected IBKR client."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, ContextManager, Protocol

from ib_insync import Contract, RequestError, Stock

from src.security_lifecycle_fact_kernel import AutomationFact
from src.security_lifecycle_sec_evidence import IdentityContext


_ENTITLEMENT_ERROR_CODES = frozenset({354, 10089, 10090, 10091, 10167, 10168})
_MAX_EXCERPT_BYTES = 4096
_MAX_VALID_EXCHANGES = 32
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")


class IBKRContractGateway(Protocol):
    def isConnected(self) -> bool: ...

    def reqContractDetails(self, contract: Contract) -> Iterable[Any]: ...

    def reqMktData(
        self,
        contract: Contract,
        genericTickList: str,
        snapshot: bool,
        regulatorySnapshot: bool,
    ) -> object: ...

    def sleep(self, seconds: float) -> None: ...


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
    contract_status: str
    blocker_context: Mapping[str, object] | None = None


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


def _instant(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        parseable = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
        try:
            parsed = datetime.fromisoformat(parseable)
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _second_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _last_decimal(value: object) -> str | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    rendered = format(parsed, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _market_data_snapshot(
    ticker: object,
    *,
    retrieved_at: datetime,
) -> dict[str, object]:
    statuses = {
        1: "live",
        2: "frozen",
        3: "delayed",
        4: "delayed_frozen",
    }
    status = statuses.get(getattr(ticker, "marketDataType", None), "unavailable")
    last = _last_decimal(getattr(ticker, "last", None))
    provider_time = _instant(getattr(ticker, "time", None))
    age = None if provider_time is None else retrieved_at - provider_time
    fresh = bool(
        status == "live"
        and last is not None
        and age is not None
        and -timedelta(minutes=5) <= age <= timedelta(minutes=15)
    )
    return {
        "status": status,
        "last": last,
        "provider_time": (
            None if provider_time is None else _second_timestamp(provider_time)
        ),
        "retrieved_at": _second_timestamp(retrieved_at),
        "fresh": fresh,
    }


def _unavailable_market_data(*, retrieved_at: datetime) -> dict[str, object]:
    return {
        "status": "unavailable",
        "last": None,
        "provider_time": None,
        "retrieved_at": _second_timestamp(retrieved_at),
        "fresh": False,
    }


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


def _queries(
    context: IdentityContext,
    *,
    candidate_tickers: Iterable[str],
) -> tuple[Contract, ...] | None:
    if len(context.ibkr_conids) > 1:
        return None

    aliases: list[str] = []
    for raw in (
        context.current_ticker,
        *candidate_tickers,
        *context.ticker_aliases,
    ):
        ticker = str(raw or "").strip().upper()
        if not _TICKER.fullmatch(ticker):
            raise ValueError("ibkr_candidate_ticker")
        if ticker not in aliases:
            aliases.append(ticker)
    queries: tuple[Contract, ...] = tuple(
        Contract(conId=con_id, exchange="SMART") for con_id in context.ibkr_conids
    ) + tuple(Stock(alias, "SMART", "USD") for alias in aliases)
    return queries


def _blocked(
    code: str,
    *,
    requests_made: int,
    context: Mapping[str, object] | None = None,
) -> IbkrContractEvidenceResult:
    statuses = {
        "ibkr_gateway_unavailable": "unavailable",
        "ibkr_contract_ambiguous": "ambiguous",
        "ibkr_entitlement_denied": "entitlement_denied",
        "market_confirmation_missing": "unqueried",
    }
    return IbkrContractEvidenceResult(
        (),
        (code,),
        (),
        0,
        requests_made,
        statuses[code],
        context,
    )


def _contract_missing(
    context: IdentityContext,
    *,
    retrieved_at: str,
    requests_made: int,
) -> IbkrContractEvidenceResult:
    payload = {
        "contract_status": "missing",
        "queried_ticker": context.current_ticker,
    }
    excerpt = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    content_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    receipt_digest = hashlib.sha256(
        f"{content_digest}\0{retrieved_at}".encode("utf-8")
    ).hexdigest()
    evidence = IbkrContractEvidence(
        evidence_id="sle_" + receipt_digest[:32],
        source_family="market_infrastructure",
        adapter="ibkr_contract",
        kind="market_infrastructure_snapshot",
        source_url=None,
        title=f"IBKR contract lookup: {context.current_ticker}",
        publisher="Interactive Brokers",
        domain=None,
        source_published_at=None,
        retrieved_at=retrieved_at,
        excerpt=excerpt,
        content_sha256=content_digest,
        source_document_sha256=None,
        source_locator=payload,
        evidence_dedupe_key=f"ibkr_contract_missing:{receipt_digest}",
    )
    return IbkrContractEvidenceResult(
        evidence=(evidence,),
        blockers=("ibkr_contract_missing",),
        source_families=("market_infrastructure",),
        corroboration_family_count=1,
        requests_made=requests_made,
        contract_status="missing",
    )


def _json_value_span(excerpt: str, key: str) -> tuple[int, int]:
    marker = json.dumps(key, ensure_ascii=True) + ":"
    marker_start = excerpt.find(marker)
    if marker_start < 0:
        raise ValueError("ibkr_contract_snapshot_shape")
    value_start = marker_start + len(marker)
    try:
        _, consumed = json.JSONDecoder().raw_decode(excerpt[value_start:])
    except json.JSONDecodeError as exc:
        raise ValueError("ibkr_contract_snapshot_shape") from exc
    start = len(excerpt[:value_start].encode("utf-8"))
    end = len(excerpt[: value_start + consumed].encode("utf-8"))
    return start, end


def contract_snapshot_facts(
    evidence: object,
    *,
    regulator_successors: Iterable[str],
) -> tuple[AutomationFact, ...]:
    """Extract exact cited identity facts from one canonical found snapshot."""
    if (
        getattr(evidence, "adapter", None) != "ibkr_contract"
        or getattr(evidence, "source_family", None) != "market_infrastructure"
        or getattr(evidence, "kind", None) != "market_infrastructure_snapshot"
    ):
        return ()
    locator = getattr(evidence, "source_locator", None)
    if not isinstance(locator, Mapping):
        raise ValueError("ibkr_contract_source_locator")
    snapshot = locator.get("snapshot")
    if snapshot is None:
        return ()
    if not isinstance(snapshot, Mapping):
        raise ValueError("ibkr_contract_snapshot_shape")
    excerpt = str(getattr(evidence, "excerpt", ""))
    try:
        decoded = json.loads(excerpt)
    except json.JSONDecodeError as exc:
        raise ValueError("ibkr_contract_snapshot_shape") from exc
    if decoded != dict(locator) or decoded.get("snapshot") != dict(snapshot):
        raise ValueError("ibkr_contract_snapshot_shape")
    content_digest = str(getattr(evidence, "content_sha256", ""))
    if hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != content_digest:
        raise ValueError("ibkr_contract_snapshot_digest")

    allowed_successors = {
        str(value or "").strip().upper()
        for value in regulator_successors
        if str(value or "").strip()
    }
    symbol = _text(
        snapshot.get("symbol"),
        field="symbol",
        limit=32,
        required=True,
    ).upper()
    if symbol not in allowed_successors:
        return ()
    venue = _text(
        snapshot.get("primaryExchange"),
        field="primary_exchange",
        limit=80,
        required=True,
    ).upper()
    security_types = {"STK": "common_stock"}
    sec_type = _text(
        snapshot.get("secType"),
        field="security_type",
        limit=20,
        required=True,
    ).upper()
    security_class = security_types.get(sec_type)
    if security_class is None:
        return ()

    rows = (
        ("destination_venue", "primaryExchange", venue),
        ("security_class", "secType", security_class),
        ("successor_ticker", "symbol", symbol),
    )
    encoded = excerpt.encode("utf-8")
    return tuple(
        AutomationFact(
            evidence_id=str(getattr(evidence, "evidence_id")),
            fact_type=fact_type,
            normalized_value=value,
            source_span_start=(span := _json_value_span(excerpt, key))[0],
            source_span_end=span[1],
            cited_text_sha256=hashlib.sha256(encoded[span[0] : span[1]]).hexdigest(),
            extractor_rule_id=f"ibkr.contract_snapshot.{fact_type}",
            extractor_rule_version="2",
        )
        for fact_type, key, value in rows
    )


def _entitlement_failure(exc: RequestError) -> bool:
    code = getattr(exc, "code", None)
    return type(code) is int and code in _ENTITLEMENT_ERROR_CODES


def read_ibkr_contract_evidence(
    *,
    gateway: IBKRContractGateway,
    gateway_lock: GatewayLock,
    context: IdentityContext,
    candidate_tickers: Iterable[str] = (),
    retrieved_at: str,
    lock_timeout_s: float = 30.0,
    max_queries: int = 8,
    quote_wait_s: float = 2.0,
) -> IbkrContractEvidenceResult:
    """Query an already-connected client while holding the caller's shared lock."""
    if not callable(getattr(gateway, "isConnected", None)):
        raise TypeError("gateway.isConnected")
    if not callable(getattr(gateway, "reqContractDetails", None)):
        raise TypeError("gateway.reqContractDetails")
    if not callable(getattr(gateway, "reqMktData", None)):
        raise TypeError("gateway.reqMktData")
    if not callable(getattr(gateway, "sleep", None)):
        raise TypeError("gateway.sleep")
    if not callable(gateway_lock):
        raise TypeError("gateway_lock")
    if isinstance(lock_timeout_s, bool) or not isinstance(lock_timeout_s, (int, float)):
        raise ValueError("lock_timeout_s")
    if not 0 < float(lock_timeout_s) <= 1800:
        raise ValueError("lock_timeout_s")
    if type(max_queries) is not int or not 1 <= max_queries <= 16:
        raise ValueError("max_queries")
    if isinstance(quote_wait_s, bool) or not isinstance(quote_wait_s, (int, float)):
        raise ValueError("quote_wait_s")
    if not 0 < float(quote_wait_s) <= 5:
        raise ValueError("quote_wait_s")

    at = _timestamp(retrieved_at)
    retrieved_instant = _instant(at)
    if retrieved_instant is None:
        raise ValueError("retrieved_at")
    queries = _queries(
        context,
        candidate_tickers=candidate_tickers,
    )
    if queries is None:
        return _blocked("ibkr_contract_ambiguous", requests_made=0)
    if len(queries) > max_queries:
        return _blocked(
            "market_confirmation_missing",
            requests_made=0,
            context={
                "code": "candidate_budget_exceeded",
                "candidate_count": len(queries),
                "query_limit": max_queries,
            },
        )
    requests_made = 0
    detail_rows: list[object] = []
    snapshot: dict[str, Any] | None = None
    market_data: dict[str, object] | None = None

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
                return _contract_missing(
                    context,
                    retrieved_at=at,
                    requests_made=requests_made,
                )
            if len(snapshots) != 1:
                return _blocked(
                    "ibkr_contract_ambiguous",
                    requests_made=requests_made,
                )

            snapshot = json.loads(snapshots.pop())
            requests_made += 1
            try:
                ticker = gateway.reqMktData(
                    Contract(conId=int(snapshot["conId"]), exchange="SMART"),
                    "",
                    True,
                    False,
                )
                gateway.sleep(float(quote_wait_s))
                market_data = _market_data_snapshot(
                    ticker,
                    retrieved_at=retrieved_instant,
                )
            except (RequestError, ConnectionError, TimeoutError, OSError):
                market_data = _unavailable_market_data(
                    retrieved_at=retrieved_instant
                )
    except RequestError:
        return _blocked("ibkr_gateway_unavailable", requests_made=requests_made)
    except (ConnectionError, TimeoutError, OSError):
        return _blocked("ibkr_gateway_unavailable", requests_made=requests_made)

    if snapshot is None or market_data is None:
        raise RuntimeError("ibkr_contract_snapshot_missing")
    payload = {
        "adapter_version": "2",
        "contract_status": "found",
        "market_data": market_data,
        "snapshot": snapshot,
    }
    excerpt = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(excerpt.encode("utf-8")) > _MAX_EXCERPT_BYTES:
        raise ValueError("ibkr_contract_snapshot_too_large")
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
        source_locator=payload,
        evidence_dedupe_key=f"ibkr_contract:{content_digest}",
    )
    return IbkrContractEvidenceResult(
        evidence=(evidence,),
        blockers=(),
        source_families=("market_infrastructure",),
        corroboration_family_count=1,
        requests_made=requests_made,
        contract_status="found",
    )
