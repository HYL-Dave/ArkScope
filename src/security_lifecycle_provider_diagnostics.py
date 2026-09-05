"""Closed operator diagnostics shared by API and research projections."""

from collections.abc import Mapping

LISTING_CHECK_NAMES = frozenset({"delisting", "stocks", "otc", "eodhd", "nasdaq", "identity", "continuation", "freshness", "source_conflict", "integrity"})
LISTING_PROVIDER_NAMES = frozenset({"massive", "eodhd", "nasdaq"})
LISTING_PROVIDER_ISSUES = frozenset({"credential_missing", "rate_limited", "access_denied", "unavailable", "mapping_required", "not_found"})
_CHECK_BY_REASON = {
    "massive_explicit_inactive_missing": "delisting", "delisting_date_missing": "delisting", "delisting_date_future": "delisting",
    "stocks_continuation_check_missing": "stocks", "otc_continuation_check_missing": "otc",
    "eodhd_delisting_missing": "eodhd", "nasdaq_not_found_incomplete": "nasdaq",
    "stable_identity_missing": "identity", "successor_check_unavailable": "continuation",
    "successor_ambiguous": "continuation", "successor_market_confirmation_missing": "continuation",
    "successor_date_invalid": "continuation", "successor_date_future": "continuation", "successor_check_invalid": "integrity",
    "listing_directory_stale": "freshness", "active_listing_present": "source_conflict",
    "listing_observation_incomplete": "integrity", "listing_observation_invalid": "integrity",
}


def listing_operator_detail(value):
    if not isinstance(value, Mapping):
        return None
    if value.get("code") == "listing_checks":
        missing, issues = value.get("missing_checks"), value.get("provider_issues")
        if (not isinstance(missing, list) or any(not isinstance(key, str) or key not in LISTING_CHECK_NAMES for key in missing)
                or not isinstance(issues, list) or any(not isinstance(row, dict) or not isinstance(row.get("provider"), str)
                                                    or row["provider"] not in LISTING_PROVIDER_NAMES or not isinstance(row.get("reason"), str)
                                                    or row["reason"] not in LISTING_PROVIDER_ISSUES for row in issues)
                or type(value.get("manual_review_required")) is not bool):
            return None
        return {"code": "listing_checks", "missing_checks": sorted(set(missing)), "provider_issues": [
            {"provider": row["provider"], "reason": row["reason"]} for row in issues], "manual_review_required": value["manual_review_required"]}
    reasons, codes = value.get("reasons"), value.get("provider_codes")
    if not isinstance(reasons, list) or not isinstance(codes, list) or any(not isinstance(item, str) for item in reasons + codes):
        return None
    missing = sorted({_CHECK_BY_REASON.get(reason, "integrity") for reason in reasons})
    issues = set()
    for code in codes:
        provider = next((name for name in LISTING_PROVIDER_NAMES if code.startswith(name + "_")), None)
        if provider is None:
            missing = sorted({*missing, "integrity"})
            continue
        reason = next((name for name in LISTING_PROVIDER_ISSUES if code.endswith("_" + name)), "unavailable")
        issues.add((provider, reason))
    return {"code": "listing_checks", "missing_checks": missing, "provider_issues": [
        {"provider": provider, "reason": reason} for provider, reason in sorted(issues)],
        "manual_review_required": value.get("manual_review_required") is True}
