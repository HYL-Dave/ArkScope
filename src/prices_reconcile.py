from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping


@dataclass(frozen=True, order=True)
class PriceKey:
    ticker: str
    interval: str
    datetime: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.ticker, self.interval, self.datetime)

    def canonical(self, aliases: Mapping[str, str]) -> "PriceKey":
        return PriceKey(aliases.get(self.ticker, self.ticker), self.interval, self.datetime)


@dataclass(frozen=True)
class PriceDiffReport:
    alias_explained_pg_only: tuple[dict[str, object], ...]
    unexplained_pg_only: tuple[tuple[str, str, str], ...]
    local_only: tuple[tuple[str, str, str], ...]
    bulk_copy_allowed: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint_report(report: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(report).encode("utf-8")).hexdigest()


def compare_value_checksums(
    *,
    pg_checksums: Mapping[tuple[str, str, str], str],
    local_checksums: Mapping[tuple[str, str, str], str],
    sample_limit: int = 5,
) -> tuple[dict[str, object], ...]:
    by_bucket: dict[tuple[str, str], dict[str, object]] = {}
    common_keys = sorted(set(pg_checksums) & set(local_checksums))
    for key in common_keys:
        if pg_checksums[key] == local_checksums[key]:
            continue
        bucket = (key[0], key[1])
        entry = by_bucket.setdefault(
            bucket,
            {
                "bucket": bucket,
                "mismatch_count": 0,
                "reason": "ohlcv_checksum_mismatch",
                "samples": [],
            },
        )
        entry["mismatch_count"] = int(entry["mismatch_count"]) + 1
        samples = entry["samples"]
        assert isinstance(samples, list)
        if len(samples) < sample_limit:
            samples.append(
                {
                    "key": key,
                    "pg_checksum": pg_checksums[key],
                    "local_checksum": local_checksums[key],
                }
            )

    return tuple(
        {
            "bucket": entry["bucket"],
            "mismatch_count": entry["mismatch_count"],
            "reason": entry["reason"],
            "samples": tuple(entry["samples"]),
        }
        for _, entry in sorted(by_bucket.items())
    )


def classify_price_differences(
    *,
    pg_rows: Iterable[PriceKey],
    local_rows: Iterable[PriceKey],
    aliases: Mapping[str, str],
) -> PriceDiffReport:
    pg_set = set(pg_rows)
    local_set = set(local_rows)
    local_canon = {row.as_tuple() for row in local_set}
    alias_explained = []
    unexplained = []

    for row in sorted(pg_set - local_set):
        canonical = row.canonical(aliases)
        if canonical.as_tuple() in local_canon and canonical != row:
            alias_explained.append(
                {
                    "pg_key": row.as_tuple(),
                    "canonical_key": canonical.as_tuple(),
                    "reason": "pg_alias_matches_local_canonical",
                }
            )
        else:
            unexplained.append(row.as_tuple())

    return PriceDiffReport(
        alias_explained_pg_only=tuple(alias_explained),
        unexplained_pg_only=tuple(unexplained),
        local_only=tuple(row.as_tuple() for row in sorted(local_set - pg_set)),
        bulk_copy_allowed=False,
    )
