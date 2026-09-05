export const LISTING_CHECK_NAMES = [
  "delisting", "stocks", "otc", "eodhd", "nasdaq", "identity",
  "continuation", "freshness", "source_conflict", "integrity",
] as const;

export const LISTING_PROVIDER_ISSUES = [
  "credential_missing", "rate_limited", "access_denied", "unavailable",
  "mapping_required", "not_found",
] as const;

export const LISTING_PROVIDER_NAMES = ["massive", "eodhd", "nasdaq"] as const;
