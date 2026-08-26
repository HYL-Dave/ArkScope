"""Safe closed failure classification shared by content-translation surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.subscription_structured_output import (
    SubscriptionStructuredOutputError,
)
from src.card_synthesis import ModelExecutionTimeout, TextTranslationOutputInvalid


TRANSLATION_FAILURE_CODES = frozenset(
    {
        "translation_route_unavailable",
        "translation_credential_missing",
        "translation_auth_rejected",
        "translation_rate_limited",
        "translation_quota_exhausted",
        "translation_model_unavailable",
        "translation_timeout",
        "translation_output_invalid",
        "translation_provider_error",
        "evidence_changed",
    }
)


@dataclass(frozen=True)
class ContentTranslationFailure:
    code: str
    retryable: bool

    def __post_init__(self) -> None:
        if self.code not in TRANSLATION_FAILURE_CODES:
            raise ValueError("translation_failure_code")


def classify_content_translation_failure(
    exc: Exception,
) -> ContentTranslationFailure:
    """Classify without retaining or inspecting provider-controlled messages."""

    if isinstance(exc, (ModelExecutionTimeout, TimeoutError)):
        return ContentTranslationFailure("translation_timeout", True)
    if isinstance(exc, TextTranslationOutputInvalid):
        return ContentTranslationFailure("translation_output_invalid", False)
    if isinstance(exc, MissingCredentialError):
        return ContentTranslationFailure("translation_credential_missing", False)
    if isinstance(exc, SubscriptionStructuredOutputError):
        if exc.code == "reauth_required":
            return ContentTranslationFailure("translation_auth_rejected", False)
        if exc.code in {"insufficient_quota", "usage_limit_reached"}:
            return ContentTranslationFailure("translation_quota_exhausted", False)

    status = getattr(exc, "status_code", None)
    if status in {401, 403}:
        return ContentTranslationFailure("translation_auth_rejected", False)
    if status == 404:
        return ContentTranslationFailure("translation_model_unavailable", False)
    if getattr(exc, "code", None) in {
        "insufficient_quota",
        "usage_limit_reached",
    }:
        return ContentTranslationFailure("translation_quota_exhausted", False)
    if status == 429:
        return ContentTranslationFailure("translation_rate_limited", True)
    return ContentTranslationFailure("translation_provider_error", True)


__all__ = [
    "ContentTranslationFailure",
    "TRANSLATION_FAILURE_CODES",
    "classify_content_translation_failure",
]
