import asyncio
import json
import sqlite3

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential
from src.lifecycle_investigation.agent import run_agent
from src.lifecycle_investigation.news import LocalNews
from src.lifecycle_investigation.runtime import InvestigationRuntime
from src.lifecycle_investigation.schema import install_journal
from src.lifecycle_investigation.store import InvestigationStore
from src.lifecycle_investigation.target import Target, TargetPreflight
from src.security_lifecycle_web_contract import ExecutionSelection
from src.ticker_identity_transition import TransitionOptions
from tests.test_lifecycle_investigation_agent import completed, choose
from tests.test_lifecycle_investigation_findings import NOTICE, payload
from tests.test_lifecycle_investigation_news import corpus
from tests.lifecycle_investigation_fixtures import synthetic_credentials
from tests.test_security_lifecycle_terminal_workflow import setup_workflow


def context(tmp_path, *, finding_edit=lambda value: value, provider="openai", auth="api_key", body=NOTICE):
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    c["now"][0] = "2026-09-08T01:00:00Z"
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=(), diagnostics={}, blockers=("massive_unavailable",))
    credentials, _, route = synthetic_credentials(provider=provider, auth=auth)
    with sqlite3.connect(c["profile"]) as conn:
        install_journal(conn, at=c["now"][0])
        conn.execute("DELETE FROM security_lifecycle_cases")
    preflight = TargetPreflight(c["service"], credential_store=credentials, route_loader=lambda: route,
        market_path=c["market"], sa_path=c["sa"])
    binding, _ = preflight._material("OLD")
    store = InvestigationStore(c["profile"], clock=lambda: c["now"][0])
    job = store.start(binding=binding, owner="worker", request_key="explicit-click")
    identity = job["run_id"]
    control = store.control(identity, owner="worker")
    async def model(call, credential, control):
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        return completed(call, control, choose("conclude", finding=finding_edit(payload(material["sources"][0]["passages"]))))
    result = asyncio.run(run_agent(Target.model_validate(binding["target"]), WebCredential(ExecutionSelection(**binding["selection"])), control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(corpus(tmp_path, body=body), None, clock=lambda: c["now"][0]), model=model,
        on_source=lambda key, value: store.source(identity, owner="worker", source_id=key, payload=value),
        on_step=lambda kind, value: store.step(identity, owner="worker", kind=kind, payload=value)))
    assert result["status"] == "succeeded", result
    store.finish(identity, owner="worker", status="succeeded", payload=result)
    c.update(investigation=store, run_id=identity, preflight=preflight)
    return c


def test_target_finding_uses_existing_atomic_receipt_without_fabricating_a_case_at_launch(tmp_path):
    from src.lifecycle_web_review import prepare, confirm
    c = context(tmp_path)
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_cases").fetchone()[0] == 0
    packet = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    assert packet["ready"], packet["block_reasons"]
    assert packet["lane"] == "investigation"
    result = confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
        options=TransitionOptions(execute_on=None), before_write=lambda: None)
    assert result["status"] == "applied", result
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT source,source_ref FROM security_lifecycle_cases").fetchall() == [("lifecycle_investigation", c["run_id"])]
        assert conn.execute("SELECT actor FROM lifecycle_investigation_acceptances").fetchone()[0] == "attended_user"
    again = confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
        options=TransitionOptions(execute_on=None), before_write=lambda: None)
    assert again["status"] == "already_applied"


def test_failed_adoption_does_not_leave_an_anchor_or_partial_profile_change(tmp_path, monkeypatch):
    from src.lifecycle_web_review import prepare, confirm
    from src.ticker_identity_transition import TickerIdentityTransitionStore
    c = context(tmp_path)
    packet = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    monkeypatch.setattr(TickerIdentityTransitionStore, "_approve", lambda *a, **k: (_ for _ in ()).throw(ValueError("blocked")))
    with pytest.raises(ValueError, match="blocked"):
        confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
            options=TransitionOptions(execute_on=None), before_write=lambda: None)
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_cases").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_acceptances").fetchone()[0] == 0
    assert "OLD" in c["sources"]()


def test_unknown_event_date_is_explicit_and_requires_an_attended_execution_date(tmp_path):
    from src.lifecycle_web_review import prepare, confirm
    def unknown_date(value):
        return {**value, "effective_date": None, "effective_date_text": None,
            "limitations": ["The exact trading-end date was not established."]}
    c = context(tmp_path, finding_edit=unknown_date)
    packet = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    assert not packet["ready"]
    assert packet["execute_on"] is None
    assert "exact trading-end date" in packet["finding"]["impact_summary"]
    options = TransitionOptions(execute_on="2026-09-07")
    packet = prepare(c["service"], c["run_id"], options=options)
    assert packet["ready"], packet["block_reasons"]
    result = confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
        options=options, before_write=lambda: None)
    assert result["status"] == "applied"
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT effective_date FROM security_lifecycle_assessments").fetchone()[0] is None
        assert conn.execute("SELECT execute_on FROM ticker_identity_transitions").fetchone()[0] == "2026-09-07"


def test_new_position_invalidates_target_review_even_with_source_gap_acknowledgement(tmp_path):
    from src.lifecycle_web_review import prepare, confirm
    from src.portfolio_state import PortfolioStore
    from src.ticker_identity_service import TickerIdentityConflict
    c = context(tmp_path)
    packet = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    assert packet["ready"]
    portfolio = PortfolioStore(c["profile"])
    account = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(account_id=account.id, symbol="OLD", quantity=1)
    with pytest.raises(TickerIdentityConflict, match="review_changed"):
        confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
            options=TransitionOptions(execute_on=None), before_write=lambda: None, acknowledge_source_gaps=True)
    assert "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_acceptances").fetchone()[0] == 0


def test_fresh_active_provider_evidence_is_not_waived_by_source_gap_acknowledgement(tmp_path):
    from src.lifecycle_web_review import prepare, confirm
    from tests.test_security_lifecycle_population import active
    from src.ticker_identity_service import TickerIdentityConflict
    c = context(tmp_path)
    packet = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    c["checks"].record(ticker="OLD", at="2026-09-08T01:00:01Z", evidence=(active("OLD", at="2026-09-08T01:00:01Z"),), diagnostics={})
    c["now"][0] = "2026-09-08T01:00:02Z"
    fresh = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    assert not fresh["ready"] and "web_active_listing_conflict" in fresh["block_reasons"]
    with pytest.raises(TickerIdentityConflict, match="review_changed"):
        confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
            options=TransitionOptions(execute_on=None), before_write=lambda: None, acknowledge_source_gaps=True)
    assert "OLD" in c["sources"]()


def test_same_security_rename_moves_tracking_but_preserves_the_source_history(tmp_path):
    from src.lifecycle_web_review import prepare, confirm
    body = NOTICE.split("\n")[0] + "\nOn September 1, 2026, the same common stock on NASDAQ changed its ticker from OLD to NEW and continues trading."
    def rename(value):
        value.update(event_kind="symbol_continuation", successor_ticker="NEW", summary="The same common stock now trades as NEW.")
        value["citations"][-1]["supports"] = ["same_security_continuation", "effective_date"]
        return value
    c = context(tmp_path, body=body, finding_edit=rename)
    with sqlite3.connect(c["sa"]) as conn:
        history = tuple(conn.iterdump())
    packet = prepare(c["service"], c["run_id"], options=TransitionOptions(execute_on=None))
    assert packet["ready"] and packet["action"] == "symbol_continuation", packet["block_reasons"]
    result = confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
        options=TransitionOptions(execute_on=None), before_write=lambda: None)
    assert result["status"] == "applied"
    assert "OLD" not in c["sources"]() and {"NEW", "LIVE"} <= set(c["sources"]())
    with sqlite3.connect(c["sa"]) as conn:
        assert tuple(conn.iterdump()) == history
