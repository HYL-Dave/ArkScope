from __future__ import annotations

import socket
import sqlite3

import pytest


_AT = "2026-08-20T00:00:00Z"


def test_manual_adapter_adds_bounded_text_and_https_urls_with_zero_network(
    tmp_path, monkeypatch
):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )
    from src.security_lifecycle_manual_evidence import add_manual_evidence

    network_calls: list[str] = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: network_calls.append("dns"),
    )
    connection = sqlite3.connect(tmp_path / "profile_state.db")
    store = SecurityLifecycleInvestigationStore(
        connection,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0000712515-26-000042",
        ticker="EA",
        at=_AT,
    )
    try:
        text_id = add_manual_evidence(
            store=store,
            case_id=case_id,
            text=f"<script>discard me</script>  {'x' * 17_000}",
            url=None,
            at=_AT,
        )
        url_id = add_manual_evidence(
            store=store,
            case_id=case_id,
            text=None,
            url="https://EXAMPLE.com:443/issuer-notice#fragment",
            at=_AT,
        )
        evidence = {
            item["evidence_id"]: item for item in store.list_evidence(case_id)
        }
        assert evidence[text_id]["kind"] == "manual_text"
        assert evidence[text_id]["excerpt"] == "x" * 16_000
        assert evidence[text_id]["source_url"] is None
        assert evidence[url_id]["kind"] == "manual_url"
        assert evidence[url_id]["source_url"] == (
            "https://example.com/issuer-notice"
        )
        assert network_calls == []

        with pytest.raises(ValueError, match="unsafe_url"):
            add_manual_evidence(
                store=store,
                case_id=case_id,
                text=None,
                url="https://127.0.0.1/private",
                at=_AT,
            )
    finally:
        connection.close()
