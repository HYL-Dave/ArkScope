import json

import pytest

from src.security_lifecycle_investigation import project_automation_blocker
from src.security_lifecycle_provider_diagnostics import listing_operator_detail


def test_listing_diagnostic_is_closed_idempotent_and_keeps_the_actionable_reason():
    context = {"reasons": ["otc_continuation_check_missing", "successor_check_unavailable"],
               "provider_codes": ["massive_rate_limited", "eodhd_credential_missing"], "manual_review_required": True,
               "credential": "do-not-render", "internal_id": "private", "hash": "a" * 64}
    projected = project_automation_blocker({"blocker_code": "listing_status_unresolved", "retryable": True, "context_json": json.dumps(context)})
    detail = projected["operator_detail"]
    assert detail == {"code": "listing_checks", "missing_checks": ["continuation", "otc"],
                      "provider_issues": [{"provider": "eodhd", "reason": "credential_missing"}, {"provider": "massive", "reason": "rate_limited"}],
                      "manual_review_required": True}
    assert project_automation_blocker(projected) == projected
    assert listing_operator_detail(detail) == detail
    assert "do-not-render" not in json.dumps(projected)


@pytest.mark.parametrize("bad", [None, [], {}, "private"])
def test_malformed_operator_detail_never_crashes_a_case_view(bad):
    assert listing_operator_detail({"code": "listing_checks", "missing_checks": [], "provider_issues": [
        {"provider": bad, "reason": "rate_limited"}], "manual_review_required": False}) is None
    assert listing_operator_detail({"code": "listing_checks", "missing_checks": [], "provider_issues": [
        {"provider": "massive", "reason": bad}], "manual_review_required": False}) is None
