from __future__ import annotations

import hashlib
import inspect
import json
from contextlib import contextmanager
from types import SimpleNamespace

from ib_insync import RequestError


def _context():
    from src.security_lifecycle_sec_evidence import build_identity_context

    return build_identity_context(
        case_id="case-hapn",
        observation={
            "ticker": "HAPN",
            "cik": "0001409970",
            "issuer_name": "Happify Network, Inc.",
            "filing_date": "2026-06-27",
            "source_ref": "0001409970-26-000131",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "event_kinds": ["listing_status_review"],
        },
        ticker_aliases=("LC", "HAPN"),
        ibkr_conids=(112233,),
    )


def _details(
    *,
    symbol="HAPN",
    local_symbol="HAPN",
    con_id=112233,
    sec_type="STK",
    primary_exchange="NASDAQ",
    valid_exchanges="SMART,NASDAQ,NYSE",
    currency="USD",
):
    return SimpleNamespace(
        contract=SimpleNamespace(
            symbol=symbol,
            localSymbol=local_symbol,
            conId=con_id,
            secType=sec_type,
            primaryExchange=primary_exchange,
            currency=currency,
        ),
        validExchanges=valid_exchanges,
    )


class _Gateway:
    def __init__(self, responses=(), *, connected=True, lock_state=None):
        self.connected = connected
        self.responses = list(responses)
        self.requests = []
        self.lock_state = lock_state

    def isConnected(self):
        return self.connected

    def reqContractDetails(self, contract):
        if self.lock_state is not None:
            assert self.lock_state["held"] is True
        self.requests.append(contract)
        response = self.responses.pop(0) if self.responses else []
        if isinstance(response, BaseException):
            raise response
        return response


def _lock_recorder():
    state = {"held": False, "timeouts": []}

    @contextmanager
    def lock(timeout):
        assert state["held"] is False
        state["held"] = True
        state["timeouts"].append(timeout)
        try:
            yield
        finally:
            state["held"] = False

    return state, lock


def _read(gateway, lock):
    from src.security_lifecycle_ibkr_evidence import read_ibkr_contract_evidence

    return read_ibkr_contract_evidence(
        gateway=gateway,
        gateway_lock=lock,
        context=_context(),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )


def test_ibkr_adapter_requires_injected_gateway_and_shared_lock():
    import src.security_lifecycle_ibkr_evidence as module
    from src.security_lifecycle_ibkr_evidence import read_ibkr_contract_evidence

    signature = inspect.signature(read_ibkr_contract_evidence)
    assert signature.parameters["gateway"].default is inspect.Parameter.empty
    assert signature.parameters["gateway_lock"].default is inspect.Parameter.empty
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )

    source = inspect.getsource(module)
    assert "IBKRDataSource" not in source
    assert "os.environ" not in source
    assert ".connect(" not in source

    state, lock = _lock_recorder()
    gateway = _Gateway(connected=False, lock_state=state)
    result = _read(gateway, lock)
    assert result.blockers == ("ibkr_gateway_unavailable",)
    assert result.evidence == ()
    assert state == {"held": False, "timeouts": [30.0]}
    assert gateway.requests == []


def test_ibkr_adapter_persists_one_bounded_contract_snapshot():
    state, lock = _lock_recorder()
    detail = _details()
    gateway = _Gateway(
        responses=([detail], [detail], [detail]),
        lock_state=state,
    )

    result = _read(gateway, lock)

    assert result.blockers == ()
    assert result.source_families == ("market_infrastructure",)
    assert result.corroboration_family_count == 1
    assert result.requests_made == 3
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.source_family == "market_infrastructure"
    assert evidence.adapter == "ibkr_contract"
    assert evidence.kind == "market_infrastructure_snapshot"
    assert evidence.source_url is None
    assert evidence.source_published_at is None
    assert evidence.retrieved_at == "2026-08-25T01:02:03.123456Z"
    assert set(evidence.source_locator) == {"snapshot"}
    snapshot = evidence.source_locator["snapshot"]
    assert snapshot == {
        "symbol": "HAPN",
        "localSymbol": "HAPN",
        "conId": 112233,
        "secType": "STK",
        "primaryExchange": "NASDAQ",
        "validExchanges": ["NASDAQ", "NYSE", "SMART"],
        "currency": "USD",
        "retrieved_at": "2026-08-25T01:02:03.123456Z",
    }
    assert evidence.excerpt == json.dumps(
        snapshot, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    assert len(evidence.excerpt.encode("utf-8")) <= 4096
    assert evidence.content_sha256 == hashlib.sha256(
        evidence.excerpt.encode("utf-8")
    ).hexdigest()
    assert evidence.evidence_dedupe_key == f"ibkr_contract:{evidence.content_sha256}"
    assert len(gateway.requests) == 3


def test_ibkr_adapter_reports_gateway_unavailable_and_contract_missing_separately():
    state, lock = _lock_recorder()
    disconnected = _read(_Gateway(connected=False, lock_state=state), lock)
    assert disconnected.blockers == ("ibkr_gateway_unavailable",)

    state, lock = _lock_recorder()
    missing = _read(_Gateway(responses=([], [], []), lock_state=state), lock)
    assert missing.blockers == ("ibkr_contract_missing",)
    assert missing.evidence == ()
    assert missing.requests_made == 3

    state, lock = _lock_recorder()
    unavailable = _read(
        _Gateway(responses=(ConnectionError("gateway stopped"),), lock_state=state),
        lock,
    )
    assert unavailable.blockers == ("ibkr_gateway_unavailable",)
    assert unavailable.evidence == ()


def test_ibkr_adapter_reports_ambiguous_contract_without_guessing():
    state, lock = _lock_recorder()
    old = _details(symbol="LC", local_symbol="LC", con_id=100, primary_exchange="NYSE")
    current = _details(symbol="HAPN", con_id=200)
    gateway = _Gateway(
        responses=([old], [current], [old, current]),
        lock_state=state,
    )

    result = _read(gateway, lock)

    assert result.blockers == ("ibkr_contract_ambiguous",)
    assert result.evidence == ()
    assert result.source_families == ()
    assert result.corroboration_family_count == 0
    assert result.requests_made == 3


def test_ibkr_adapter_reports_entitlement_denied_without_empty_success():
    state, lock = _lock_recorder()
    denied = RequestError(7, 354, "sensitive provider text must not be classified")
    result = _read(_Gateway(responses=(denied,), lock_state=state), lock)

    assert result.blockers == ("ibkr_entitlement_denied",)
    assert result.evidence == ()
    assert result.source_families == ()
    assert result.requests_made == 1
