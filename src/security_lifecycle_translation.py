"""Hash-bound derived translations for lifecycle evidence excerpts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.card_synthesis import ModelExecutionTimeout, TextTranslationOutputInvalid
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore


SUPPORTED_TRANSLATION_LOCALES = frozenset({"en", "zh-Hant"})


@dataclass(frozen=True)
class EvidenceTranslationResult:
    translated_text: str
    provider: str
    model: str
    harness: str


class EvidenceTranslationFailure(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class EvidenceTranslationConflict(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def prepare_evidence_translation(
    store: SecurityLifecycleInvestigationStore,
    *,
    evidence_id: str,
    locale: str,
) -> tuple[dict, dict | None]:
    if locale not in SUPPORTED_TRANSLATION_LOCALES:
        raise ValueError("translation_locale")
    evidence = store.get_evidence(evidence_id)
    cached = store.get_evidence_translation(
        evidence_id=evidence_id,
        evidence_content_sha256=str(evidence["content_sha256"]),
        locale=locale,
    )
    return evidence, cached


def _validated_result(value: object) -> EvidenceTranslationResult:
    if not isinstance(value, EvidenceTranslationResult):
        raise EvidenceTranslationFailure("translation_output_invalid")
    limits = {
        "translated_text": 16000,
        "provider": 64,
        "model": 160,
        "harness": 160,
    }
    for field, limit in limits.items():
        text = getattr(value, field, None)
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > limit
            or "\0" in text
        ):
            raise EvidenceTranslationFailure("translation_output_invalid")
    return value


def translate_evidence(
    store: SecurityLifecycleInvestigationStore,
    *,
    evidence_id: str,
    locale: str,
    translator: Callable[[str, str], EvidenceTranslationResult],
    at: str,
) -> dict:
    evidence, cached = prepare_evidence_translation(
        store,
        evidence_id=evidence_id,
        locale=locale,
    )
    if cached is not None:
        return {**cached, "cached": True}

    store.assert_translation_write_available()
    if store.conn.in_transaction:
        raise EvidenceTranslationConflict("translation_transaction_open")
    try:
        result = translator(str(evidence["excerpt"]), locale)
    except (ModelExecutionTimeout, TimeoutError):
        raise EvidenceTranslationFailure("translation_timeout") from None
    except TextTranslationOutputInvalid:
        raise EvidenceTranslationFailure("translation_output_invalid") from None
    except Exception:
        raise EvidenceTranslationFailure("translation_failed") from None
    validated = _validated_result(result)

    try:
        current = store.get_evidence(evidence_id)
    except KeyError:
        raise EvidenceTranslationConflict("evidence_changed") from None
    if current["content_sha256"] != evidence["content_sha256"]:
        raise EvidenceTranslationConflict("evidence_changed")
    try:
        saved, inserted = store.save_evidence_translation(
            evidence_id=evidence_id,
            evidence_content_sha256=str(evidence["content_sha256"]),
            locale=locale,
            translated_text=validated.translated_text,
            provider=validated.provider,
            model=validated.model,
            harness=validated.harness,
            at=at,
        )
    except (KeyError, ValueError):
        raise EvidenceTranslationConflict("evidence_changed") from None
    return {**saved, "cached": not inserted}


__all__ = [
    "EvidenceTranslationConflict",
    "EvidenceTranslationFailure",
    "EvidenceTranslationResult",
    "prepare_evidence_translation",
    "translate_evidence",
]
