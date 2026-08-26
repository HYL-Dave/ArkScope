from __future__ import annotations

import pytest

from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.subscription_structured_output import (
    SubscriptionStructuredOutputError,
)
from src.card_synthesis import ModelExecutionTimeout, TextTranslationOutputInvalid


class _StatusError(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__("secret-value")


class _CodeError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__("secret-value")


class _StatusCodeError(_StatusError):
    def __init__(self, status_code: int, code: str):
        self.code = code
        super().__init__(status_code)


@pytest.mark.parametrize(
    ("exc", "code", "retryable"),
    [
        (
            ModelExecutionTimeout(
                provider="anthropic",
                model="claude-sonnet-5",
                effort="default",
                effective_seconds=10,
            ),
            "translation_timeout",
            True,
        ),
        (TimeoutError("secret-value"), "translation_timeout", True),
        (
            TextTranslationOutputInvalid("secret-value"),
            "translation_output_invalid",
            False,
        ),
        (
            MissingCredentialError("secret-value"),
            "translation_credential_missing",
            False,
        ),
        (
            SubscriptionStructuredOutputError(
                "reauth_required", "secret-value"
            ),
            "translation_auth_rejected",
            False,
        ),
        (
            SubscriptionStructuredOutputError(
                "insufficient_quota", "secret-value"
            ),
            "translation_quota_exhausted",
            False,
        ),
        (_StatusError(401), "translation_auth_rejected", False),
        (_StatusError(403), "translation_auth_rejected", False),
        (_StatusError(404), "translation_model_unavailable", False),
        (_StatusError(429), "translation_rate_limited", True),
        (_CodeError("usage_limit_reached"), "translation_quota_exhausted", False),
        (
            _StatusCodeError(429, "insufficient_quota"),
            "translation_quota_exhausted",
            False,
        ),
        (RuntimeError("secret-value"), "translation_provider_error", True),
    ],
)
def test_translation_failures_are_closed_and_safe(exc, code, retryable):
    from src.content_translation_failures import (
        TRANSLATION_FAILURE_CODES,
        classify_content_translation_failure,
    )

    got = classify_content_translation_failure(exc)

    assert got.code in TRANSLATION_FAILURE_CODES
    assert (got.code, got.retryable) == (code, retryable)
    assert "secret-value" not in repr(got)


def test_translation_failure_codes_are_the_exact_closed_vocabulary():
    from src.content_translation_failures import TRANSLATION_FAILURE_CODES

    assert TRANSLATION_FAILURE_CODES == frozenset(
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
