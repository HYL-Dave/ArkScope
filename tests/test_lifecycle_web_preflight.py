from dataclasses import replace
from types import SimpleNamespace
import sqlite3

import pytest

from src.security_lifecycle_web_contract import PublicInvestigationInput
from tests.test_lifecycle_web_review import context
from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page


@pytest.mark.parametrize("missing", ["security_class", "venue"])
def test_unknown_identity_detail_must_be_sourced_not_guessed_or_reentered_by_user(missing):
    from src.security_lifecycle_web_finding import validate_finding
    request = PublicInvestigationInput.model_validate({**public_input().model_dump(), missing: None})
    result = validate_finding(request, finding_payload(), {"source-1": source_page(NOTICE)})
    assert result.action == "terminal_delisting"
    payload = finding_payload(**{missing: "invented class or venue"})
    result = validate_finding(request, payload, {"source-1": source_page(NOTICE)})
    assert result.action is None and "security_identity_not_supported" in result.block_reasons


def setup(c, *, provider="openai", auth="api_key"):
    from src.lifecycle_web_preflight import LifecycleWebPreflight
    model = "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5"
    row = SimpleNamespace(id=7, provider=provider, auth_type=auth, active=True, alias="Selected account",
                          secret="do-not-export-this-secret" if auth == "api_key" else None, updated_at="2026-09-06T01:00:00Z")
    rows = [row]
    credentials = SimpleNamespace(list=lambda requested: [row for row in rows if row.provider == requested])
    route = SimpleNamespace(provider=provider, model=model, effort="high")
    service = LifecycleWebPreflight(c["service"], credential_store=credentials, route_loader=lambda: route,
                                   sa_db_path=c["sa"], output_limit_loader=lambda: 16384)
    return service, rows, route


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
def test_preflight_uses_public_sec_identity_and_exact_profile_auth_without_provider(tmp_path, monkeypatch, provider, auth):
    c = context(tmp_path)
    service, rows, route = setup(c, provider=provider, auth=auth)
    original = c["service"]._read_service._cases
    def cases():
        result = original()
        return [*result, {"ticker": "OLD", "source": "sec_edgar", "observation": {"issuer_name": "Issuer Old Inc", "cik": "0000012345"}}]
    monkeypatch.setattr(c["service"]._read_service, "_cases", cases)
    packet = service.prepare(c["case_id"], question="listing_status")
    assert packet["available"] and packet["reason"] is None
    assert packet["execution"] == {"provider": provider, "auth_mode": auth, "model": route.model}
    assert packet["credential_label"] == "Selected account"
    assert packet["public_identity"]["issuer_name"] == "Issuer Old Inc"
    assert packet["limits"]["model_submissions"] == 2
    assert packet["limits"]["search_enforcement"] == ("observed" if auth == "chatgpt_oauth" else "enforced")
    assert packet["limits"]["output_token_limit"] == (16384 if auth == "api_key" else None)
    assert "do-not-export" not in str(packet) and "local:7" not in str(packet)


def test_source_capacity_is_separate_from_model_tokens_and_bound_to_confirmation(tmp_path, monkeypatch):
    c = context(tmp_path)
    service, _, _ = setup(c)
    monkeypatch.setattr(service, "_public_input", lambda *args, **kwargs: public_input())
    packet = service.prepare(c["case_id"], question="listing_status")
    values = service.validate_start(c["case_id"], question="listing_status", preflight_sha256=packet["preflight_sha256"])
    assert values["options"].max_source_bytes == packet["limits"]["max_source_bytes"] == 32 * 1024 * 1024
    assert values["options"].max_decoded_source_bytes == packet["limits"]["max_decoded_source_bytes"] == 128 * 1024 * 1024
    assert values["options"].source_timeout_seconds == packet["limits"]["source_timeout_seconds"] == 180
    assert values["options"].model_timeout_seconds == 180
    assert values["options"].output_token_limit == 16384
    assert values["options"].max_sources == 4 and values["options"].max_source_requests == 8
    original = service._material

    for field in ("max_decoded_source_bytes", "source_timeout_seconds"):
        def changed(*args, field=field, **kwargs):
            binding, request, selected, options, label = original(*args, **kwargs)
            binding["options"][field] += 1
            return binding, request, selected, options, label

        monkeypatch.setattr(service, "_material", changed)
        with pytest.raises(ValueError, match="web_preflight_changed"):
            service.validate_start(c["case_id"], question="listing_status", preflight_sha256=packet["preflight_sha256"])


def test_listing_case_uses_only_its_exact_sa_public_company_name(tmp_path):
    c = context(tmp_path)
    service, _, _ = setup(c)
    with sqlite3.connect(c["sa"]) as conn:
        # Only the public company name for this symbol is an eligible fallback.
        conn.execute("INSERT INTO sa_pick_lineages (symbol_key,picked_date,created_at) VALUES ('OLD','2023-01-01','2026-09-06')")
        lineage = conn.execute("SELECT lineage_id FROM sa_pick_lineages WHERE symbol_key='OLD'").fetchone()[0]
        conn.execute("INSERT INTO sa_alpha_picks (symbol,company,picked_date,lineage_id,fetched_at) VALUES (?,?,?,?,?)",
                     ("OLD", "Issuer Old Inc", "2023-01-01", lineage, "2026-09-06"))
    packet = service.prepare(c["case_id"], question="listing_status")
    assert packet["available"] and packet["public_identity"]["issuer_name"] == "Issuer Old Inc"


def test_missing_issuer_is_not_replaced_by_short_ticker_or_private_notes(tmp_path):
    c = context(tmp_path)
    service, _, _ = setup(c)
    packet = service.prepare(c["case_id"], question="listing_status")
    assert packet["available"] is False and packet["reason"] == "web_public_identity_missing"


def test_preflight_change_requires_new_confirmation_instead_of_switching_credentials(tmp_path, monkeypatch):
    c = context(tmp_path)
    service, rows, _ = setup(c)
    monkeypatch.setattr(service, "_public_input", lambda *args, **kwargs: public_input())
    packet = service.prepare(c["case_id"], question="listing_status")
    assert packet["available"]
    rows[0].id = 8
    with pytest.raises(ValueError, match="web_preflight_changed"):
        service.validate_start(c["case_id"], question="listing_status", preflight_sha256=packet["preflight_sha256"])


def test_preflight_does_not_fall_back_from_missing_active_db_credential(tmp_path, monkeypatch):
    c = context(tmp_path)
    service, rows, _ = setup(c)
    monkeypatch.setattr(service, "_public_input", lambda *args, **kwargs: public_input())
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-use-ambient")
    rows[0].active = False
    packet = service.prepare(c["case_id"], question="listing_status")
    assert packet["available"] is False and packet["reason"] == "selected_credential_unavailable"
