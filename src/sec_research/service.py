"""Explicit, bounded acquisition of durable SEC structured observations."""

from datetime import datetime, timezone
import errno
import re

from data_sources.sec_transport import SecTransportFailure

from .capture_lock import issuer_refresh
from .catalog import parse_submissions
from .common import SourceError, normalize_cik
from .facts import parse_companyfacts


_TRANSPORT_CODES = frozenset({
    "sec_identity_unconfigured", "sec_url_unsupported", "sec_rate_limited",
    "sec_response_too_large", "sec_transport_unavailable", "sec_http_error",
    "sec_governor_unavailable", "sec_request_budget_exhausted",
    "sec_request_cancelled",
})
_STORAGE_CODES = frozenset({
    "capture_budget_exceeded", "storage_space_insufficient", "capture_store_write_failed",
    "capture_store_busy", "capture_path_unsafe", "capture_integrity_failed",
    "capture_platform_unsupported", "capture_body_invalid",
    "sec_research_snapshot_bytes_exceeded", "sec_research_snapshot_rows_exceeded",
    "sec_research_object_hash_mismatch", "sec_research_object_missing",
    "sec_research_object_invalid", "sec_research_schema_mismatch",
})


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_url(cik, source):
    if source == "submissions":
        return f"https://data.sec.gov/submissions/CIK{cik}.json"
    if source == "companyfacts":
        return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    if isinstance(source, str) and re.fullmatch(r"CIK" + cik + r"-submissions-[0-9]+\.json", source):
        return "https://data.sec.gov/submissions/" + source
    raise ValueError("invalid_source_locator")


def _storage_code(exc):
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return "storage_space_insufficient"
    if isinstance(exc, ValueError) and exc.args and isinstance(exc.args[0], str):
        if exc.args[0] in _STORAGE_CODES:
            return exc.args[0]
    return "capture_store_write_failed"


def _status(completed, pending, gaps):
    if not completed:
        return "unavailable"
    return "partial" if pending or gaps else "ok"


class ResearchService:
    """The caller owns explicit schema installation and transport lifetime.

    Completion covers only the current structured-source traversal, never all
    filings/documents for an issuer. Store and capture methods own short writes;
    no transaction or capture lease spans transport or parsing here.
    A separate per-issuer lease serializes receipt ownership across invocations.
    """

    def __init__(self, store, captures, transport, *, clock=_now):
        self.store = store
        self.captures = captures
        self.transport = transport
        self.clock = clock

    def refresh(self, cik, *, max_sources=4, resume=False, check=None):
        cik = normalize_cik(cik)
        if type(max_sources) is not int or not 1 <= max_sources <= 16:
            raise ValueError("invalid_max_sources")
        if type(resume) is not bool:
            raise ValueError("invalid_resume")
        if check is not None and not callable(check):
            raise ValueError("invalid_check")

        with issuer_refresh(self.store.paths.capture_root, cik):
            return self._refresh(cik, max_sources=max_sources, resume=resume, check=check)

    def _refresh(self, cik, *, max_sources, resume, check):
        prior = self.store.latest_receipt(cik) if resume else None
        completed = list(prior["completed"]) if prior else []
        source_snapshots = dict(prior["source_snapshots"]) if prior else {}
        pending = list(prior["pending"]) if prior else ["submissions", "companyfacts"]
        gaps = [dict(gap) for gap in prior["gaps"]] if prior else []
        for source in completed + pending:
            _source_url(cik, source)
        # Explicitly unbound observations must be reacquired, not blessed by a
        # resume checkpoint that happens to find retained older snapshots.
        unbound = [source for source in completed if source not in source_snapshots]
        completed = [source for source in completed if source in source_snapshots]
        pending = list(dict.fromkeys([*unbound, *pending]))
        if prior and not pending:
            return prior

        def checkpoint():
            self.store.record_receipt(
                cik, status=_status(completed, pending, gaps),
                completed=completed, pending=pending, gaps=gaps,
                observed_at=self.clock(),
                source_snapshots=source_snapshots,
            )

        def gap(source, code):
            gaps[:] = [item for item in gaps if item["source"] != source]
            gaps.append({"source": source, "code": code})

        # Publish intent before any provider dispatch, including a fresh run
        # whose old snapshots remain readable but cannot satisfy this receipt.
        checkpoint()
        attempted = set()
        while len(attempted) < max_sources:
            source = next((item for item in pending if item not in attempted), None)
            if source is None:
                break
            if check is not None:
                try:
                    check()
                except Exception:
                    gap(source, "cancelled")
                    checkpoint()
                    break
            try:
                self.captures.preflight()
            except Exception as exc:
                gap(source, _storage_code(exc))
                checkpoint()
                break

            attempted.add(source)
            url = _source_url(cik, source)
            try:
                # Preserve SecTransport's default 16 MiB metadata body bound.
                response = self.transport.get(url, **({"check": check} if check is not None else {}))
                response.raise_for_status()
                body = response.body
            except Exception as exc:
                code = (exc.code if isinstance(exc, SecTransportFailure)
                        and exc.code in _TRANSPORT_CODES else "sec_transport_unavailable")
                gap(source, code)
                checkpoint()
                continue

            observed_at = self.clock()
            try:
                if source == "companyfacts":
                    snapshot = parse_companyfacts(body, cik=cik)
                else:
                    snapshot = parse_submissions(
                        body, cik=cik,
                        historical_name=None if source == "submissions" else source,
                    )
            except SourceError:
                snapshot = None

            try:
                digest = self.captures.put(body)
                if snapshot is not None:
                    snapshot_id = self.store.publish(snapshot, object_sha256=digest,
                                                     observed_at=observed_at, source_url=url)
            except Exception as exc:
                gap(source, _storage_code(exc))
                checkpoint()
                break
            if snapshot is None:
                gap(source, "source_invalid")
                checkpoint()
                continue

            pending.remove(source)
            completed.append(source)
            source_snapshots[source] = {"snapshot_id": snapshot_id, "observed_at": observed_at}
            gaps[:] = [item for item in gaps if item["source"] != source]
            if source == "submissions":
                for historical in snapshot.historical_files:
                    if historical.name not in pending and historical.name not in completed:
                        pending.append(historical.name)
                if not snapshot.historical_files_observed:
                    gap(source, "historical_files_unobserved")
            checkpoint()

        return self.store.latest_receipt(cik)

    def stored(self, cik):
        """Read receipt coverage and retained counts, never unpaged observations.

        Counts include all retained snapshot rows, not unique/current filings or
        facts. Snapshot timestamps do not establish current-run source state.
        """
        cik = normalize_cik(cik)
        receipt = self.store.latest_receipt(cik)
        catalog_snapshots = self.store.snapshots(cik, "catalog")
        fact_snapshots = self.store.snapshots(cik, "facts")
        status = (_status(receipt["completed"], receipt["pending"], receipt["gaps"])
                  if receipt is not None else "unavailable")
        return {
            "cik": cik, "status": status, "receipt": receipt,
            "catalog_count": sum(row["row_count"] for row in catalog_snapshots),
            "fact_count": sum(row["row_count"] for row in fact_snapshots),
            "snapshot_counts": {"catalog": len(catalog_snapshots), "facts": len(fact_snapshots)},
        }
