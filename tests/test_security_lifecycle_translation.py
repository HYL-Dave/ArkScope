from __future__ import annotations

import hashlib
import sqlite3

import pytest


_AT = "2026-08-25T01:00:00Z"


def _store_with_evidence():
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    conn = sqlite3.connect(":memory:")
    store = SecurityLifecycleInvestigationStore(
        conn,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0000712515-26-000042",
        ticker="EA",
        at=_AT,
    )
    evidence_id = store.add_evidence(
        case_id=case_id,
        run_id=None,
        kind="manual_text",
        adapter="manual",
        excerpt="The issuer will trade under the new symbol EA2.",
        source_url=None,
        title="Issuer notice",
        publisher=None,
        domain=None,
        source_published_at=None,
        retrieved_at=None,
        mime_type="text/plain",
        document_status=None,
        at=_AT,
    )
    return conn, store, case_id, evidence_id


def _result(text: str = "發行人將以新代號 EA2 交易。"):
    from src.security_lifecycle_translation import EvidenceTranslationResult

    return EvidenceTranslationResult(
        translated_text=text,
        provider="anthropic",
        model="claude-sonnet-5",
        harness="claude_subscription_structured_output",
    )


def test_listing_snapshot_translation_rejects_before_every_downstream_boundary():
    from src.security_lifecycle_translation import translate_evidence

    calls: list[str] = []

    class BoundaryOwner:
        def get_evidence(self, evidence_id: str):
            calls.append(f"evidence:{evidence_id}")
            return {
                "evidence_id": evidence_id,
                "kind": "listing_directory_snapshot",
                "content_sha256": "a" * 64,
                "excerpt": '{"listing_status":"active","ticker":"EA"}',
            }

        @staticmethod
        def get_evidence_translation(**_kwargs):
            pytest.fail("listing translation reached cache lookup")

        @staticmethod
        def assert_translation_write_available():
            pytest.fail("listing translation reached write authority")

    def translator(_text: str, _locale: str):
        pytest.fail("listing translation reached route or provider invocation")

    with pytest.raises(ValueError, match="^unsupported_content$"):
        translate_evidence(
            BoundaryOwner(),
            evidence_id="sle_listing",
            locale="zh-Hant",
            translator=translator,
            at=_AT,
        )

    assert calls == ["evidence:sle_listing"]


def test_translation_cache_is_bound_to_evidence_hash_and_locale():
    from src.security_lifecycle_translation import translate_evidence

    conn, store, _, evidence_id = _store_with_evidence()
    calls: list[tuple[str, str]] = []

    def translator(text: str, locale: str):
        calls.append((text, locale))
        return _result("Translated " + locale)

    try:
        first = translate_evidence(
            store,
            evidence_id=evidence_id,
            locale="zh-Hant",
            translator=translator,
            at=_AT,
        )
        second = translate_evidence(
            store,
            evidence_id=evidence_id,
            locale="zh-Hant",
            translator=translator,
            at="2026-08-25T01:01:00Z",
        )
        english = translate_evidence(
            store,
            evidence_id=evidence_id,
            locale="en",
            translator=translator,
            at="2026-08-25T01:02:00Z",
        )

        evidence = store.get_evidence(evidence_id)
        assert first["cached"] is False
        assert second == {**first, "cached": True}
        assert english["cached"] is False
        assert calls == [
            (evidence["excerpt"], "zh-Hant"),
            (evidence["excerpt"], "en"),
        ]
        assert {
            tuple(row)
            for row in conn.execute(
                "SELECT evidence_content_sha256,locale "
                "FROM security_lifecycle_evidence_translations"
            )
        } == {
            (evidence["content_sha256"], "en"),
            (evidence["content_sha256"], "zh-Hant"),
        }
    finally:
        conn.close()


def test_translation_runs_without_write_transaction_and_rechecks_evidence():
    from src.security_lifecycle_translation import (
        EvidenceTranslationConflict,
        translate_evidence,
    )

    conn, store, _, evidence_id = _store_with_evidence()
    replacement = "The source changed while translation was running."
    replacement_hash = hashlib.sha256(replacement.encode()).hexdigest()

    def translator(_text: str, _locale: str):
        assert conn.in_transaction is False
        conn.execute(
            "UPDATE security_lifecycle_evidence SET excerpt=?,content_sha256=? "
            "WHERE evidence_id=?",
            (replacement, replacement_hash, evidence_id),
        )
        conn.commit()
        return _result()

    try:
        with pytest.raises(EvidenceTranslationConflict) as captured:
            translate_evidence(
                store,
                evidence_id=evidence_id,
                locale="zh-Hant",
                translator=translator,
                at=_AT,
            )
        assert captured.value.code == "evidence_changed"
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_evidence_translations"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_translation_failure_leaves_authoritative_evidence_and_case_unchanged():
    from src.security_lifecycle_translation import (
        EvidenceTranslationFailure,
        translate_evidence,
    )

    conn, store, case_id, evidence_id = _store_with_evidence()
    before_case = tuple(
        conn.execute(
            "SELECT * FROM security_lifecycle_cases WHERE case_id=?", (case_id,)
        ).fetchone()
    )
    before_evidence = tuple(
        conn.execute(
            "SELECT * FROM security_lifecycle_evidence WHERE evidence_id=?",
            (evidence_id,),
        ).fetchone()
    )

    def translator(_text: str, _locale: str):
        raise RuntimeError("credential-secret-must-not-escape")

    try:
        with pytest.raises(EvidenceTranslationFailure) as captured:
            translate_evidence(
                store,
                evidence_id=evidence_id,
                locale="zh-Hant",
                translator=translator,
                at=_AT,
            )
        assert captured.value.code == "translation_provider_error"
        assert captured.value.retryable is True
        assert "credential-secret" not in str(captured.value)
        assert tuple(
            conn.execute(
                "SELECT * FROM security_lifecycle_cases WHERE case_id=?", (case_id,)
            ).fetchone()
        ) == before_case
        assert tuple(
            conn.execute(
                "SELECT * FROM security_lifecycle_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
        ) == before_evidence
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_evidence_translations"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_translation_failure_detail_is_closed_bounded_and_message_free():
    from src.security_lifecycle_translation import EvidenceTranslationFailure

    failure = EvidenceTranslationFailure(
        "translation_auth_rejected",
        retryable=False,
        provider="anthropic",
        model="claude-sonnet-5",
        harness="claude_subscription_structured_output",
    )

    assert failure.detail() == {
        "code": "translation_auth_rejected",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "harness": "claude_subscription_structured_output",
        "retryable": False,
    }
    assert "secret-value" not in repr(failure)

    with pytest.raises(ValueError, match="translation_failure_code"):
        EvidenceTranslationFailure(
            "translation_failed",
            retryable=True,
            provider="anthropic",
            model="claude-sonnet-5",
            harness="claude_subscription_structured_output",
        )
    with pytest.raises(ValueError, match="translation_failure_provider"):
        EvidenceTranslationFailure(
            "translation_provider_error",
            retryable=True,
            provider="a" * 65,
            model="claude-sonnet-5",
            harness="claude_subscription_structured_output",
        )


def test_translation_preserves_safe_typed_provider_failure():
    from src.security_lifecycle_translation import (
        EvidenceTranslationFailure,
        translate_evidence,
    )

    conn, store, _, evidence_id = _store_with_evidence()
    failure = EvidenceTranslationFailure(
        "translation_quota_exhausted",
        retryable=False,
        provider="openai",
        model="gpt-5.4-mini",
        harness="chatgpt_subscription_structured_output",
    )

    def translator(_text: str, _locale: str):
        raise failure

    try:
        with pytest.raises(EvidenceTranslationFailure) as captured:
            translate_evidence(
                store,
                evidence_id=evidence_id,
                locale="zh-Hant",
                translator=translator,
                at=_AT,
            )
        assert captured.value is failure
    finally:
        conn.close()


def test_translation_rejects_unsupported_locale_and_malformed_output():
    from src.security_lifecycle_translation import (
        EvidenceTranslationFailure,
        translate_evidence,
    )

    conn, store, _, evidence_id = _store_with_evidence()
    calls: list[str] = []

    def malformed(_text: str, locale: str):
        calls.append(locale)
        return _result("   ")

    try:
        with pytest.raises(ValueError, match="translation_locale"):
            translate_evidence(
                store,
                evidence_id=evidence_id,
                locale="fr",
                translator=malformed,
                at=_AT,
            )
        assert calls == []

        with pytest.raises(EvidenceTranslationFailure) as captured:
            translate_evidence(
                store,
                evidence_id=evidence_id,
                locale="zh-Hant",
                translator=malformed,
                at=_AT,
            )
        assert captured.value.code == "translation_output_invalid"
        assert calls == ["zh-Hant"]
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_evidence_translations"
        ).fetchone()[0] == 0
    finally:
        conn.close()
