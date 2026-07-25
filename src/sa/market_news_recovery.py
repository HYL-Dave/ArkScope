"""Audited, resumable repair service for Seeking Alpha Market News details."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import unquote, urlsplit

from src.sa.extension_run_protocol import ProtocolError, derive_run_result


REPAIR_JOB_NAME = "sa_market_news_repair"
MARKET_NEWS_SYNC_JOB_NAME = "sa_market_news_refresh"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_HASH_ALGORITHM = "sha256"
MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS = 168
MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS = 60
MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS = 600_000
MARKET_NEWS_INCIDENT_STABLE_ROUNDS = 5
MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS = 80

_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "hash_algorithm",
        "kind",
        "interval",
        "targets",
        "source_run_ids",
        "bounds",
    }
)
_TARGET_KEYS = frozenset({"news_id", "pathname", "published_at", "body_present"})
_INTERVAL_KEYS = frozenset({"start_at", "end_at", "anchor_verified"})
_KINDS = frozenset({"recorded_failures", "incident_window"})
_DISCOVERY_KEYS = frozenset(
    {
        "newly_discovered_metadata_count",
        "newly_discovered_detail_saved_count",
        "reached_interval_start",
        "stop_reason",
        "unresolved_interval",
    }
)
_DISCOVERY_STOP_REASONS = frozenset(
    {
        "window_start_reached",
        "stable_no_growth",
        "source_bottom",
        "elapsed_limit",
        "round_limit",
        "interrupted",
    }
)


class MarketNewsRecoveryError(ValueError):
    """A stable repair-domain rejection suitable for the fixed sidecar API."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise MarketNewsRecoveryError(code)


def _utc(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        _fail("manifest_invalid")
    if parsed.tzinfo is None:
        _fail("manifest_invalid")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: Any) -> str:
    return _utc(value).isoformat(timespec="seconds")


def _canonical_pathname(value: Any) -> str:
    text = str(value or "")
    parsed = urlsplit(text)
    decoded = unquote(parsed.path).replace("\\", "/")
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not text.startswith("/news/")
        or "//" in text
        or any(part in {".", ".."} for part in decoded.split("/"))
    ):
        _fail("manifest_invalid")
    return text


def _canonical_target(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _TARGET_KEYS:
        _fail("manifest_invalid")
    news_id = value.get("news_id")
    if not isinstance(news_id, str) or not news_id.strip() or len(news_id) > 240:
        _fail("manifest_invalid")
    body_present = value.get("body_present")
    if not isinstance(body_present, bool):
        _fail("manifest_invalid")
    published = value.get("published_at")
    return {
        "news_id": news_id,
        "pathname": _canonical_pathname(value.get("pathname")),
        "published_at": _timestamp(published) if published is not None else None,
        "body_present": body_present,
    }


def _canonical_interval(value: Any) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != _INTERVAL_KEYS:
        _fail("manifest_invalid")
    start = _utc(value.get("start_at"))
    end = _utc(value.get("end_at"))
    if start > end or not isinstance(value.get("anchor_verified"), bool):
        _fail("manifest_invalid")
    return {
        "start_at": start.isoformat(timespec="seconds"),
        "end_at": end.isoformat(timespec="seconds"),
        "anchor_verified": value["anchor_verified"],
    }


def _bounds(kind: str) -> dict[str, int]:
    values = {"detail_attempts_per_pass": MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS}
    if kind == "incident_window":
        values.update(
            {
                "incident_recovery_max_hours": MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS,
                "max_list_scroll_rounds": MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS,
                "max_list_elapsed_ms": MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS,
                "stable_rounds": MARKET_NEWS_INCIDENT_STABLE_ROUNDS,
            }
        )
    return values


def build_repair_manifest(
    *,
    kind: str,
    targets: Iterable[Mapping[str, Any]],
    source_run_ids: Iterable[int] = (),
    interval: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build the only canonical immutable repair-manifest shape."""

    if kind not in _KINDS:
        _fail("manifest_invalid")
    canonical_targets = [_canonical_target(value) for value in targets]
    canonical_targets.sort(key=lambda value: value["news_id"])
    ids = [value["news_id"] for value in canonical_targets]
    if len(ids) != len(set(ids)):
        _fail("manifest_invalid")
    try:
        run_ids = sorted({int(value) for value in source_run_ids})
    except (TypeError, ValueError):
        _fail("manifest_invalid")
    if any(value <= 0 for value in run_ids):
        _fail("manifest_invalid")
    canonical_interval = _canonical_interval(interval)
    if (kind == "incident_window") != (canonical_interval is not None):
        _fail("manifest_invalid")
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "hash_algorithm": MANIFEST_HASH_ALGORITHM,
        "kind": kind,
        "interval": canonical_interval,
        "targets": canonical_targets,
        "source_run_ids": run_ids,
        "bounds": _bounds(kind),
    }


def _validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _MANIFEST_KEYS:
        _fail("manifest_invalid")
    canonical = build_repair_manifest(
        kind=value.get("kind"),
        targets=value.get("targets") if isinstance(value.get("targets"), list) else (),
        source_run_ids=(
            value.get("source_run_ids")
            if isinstance(value.get("source_run_ids"), list)
            else ()
        ),
        interval=value.get("interval"),
    )
    if canonical != dict(value):
        _fail("manifest_invalid")
    return canonical


def canonical_manifest_json(manifest: Mapping[str, Any]) -> str:
    return json.dumps(_validate_manifest(manifest), sort_keys=True, separators=(",", ":"))


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_manifest_json(manifest).encode("utf-8")).hexdigest()


def _validate_attempt_item(
    *,
    news_id: str,
    state: str,
    reason_code: str,
    attempt_count: int,
    evidence_code: Optional[str],
) -> dict[str, Any]:
    item = {
        "news_id": news_id,
        "state": state,
        "reason_code": reason_code,
        "attempt_count": attempt_count,
        "evidence_code": evidence_code,
    }
    payload = {
        "schema_version": 1,
        "operation": "market_news_retry_recorded",
        "mode": "recorded",
        "phases": {
            "manifest": {"state": "complete", "reason_code": None},
            "detail_fetch": {"state": "complete", "reason_code": None},
            "capture_readback": {"state": "complete", "reason_code": None},
        },
        "item_outcomes": [item],
    }
    try:
        return derive_run_result(payload)["item_outcomes"][0]
    except ProtocolError as exc:
        raise MarketNewsRecoveryError(exc.code) from exc


def _counts(items: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    result = {
        "target_total": 0,
        "repaired": 0,
        "already_present": 0,
        "unavailable_at_source": 0,
        "failed_retryable": 0,
    }
    for item in items:
        result["target_total"] += 1
        result[str(item["state"])] += 1
    return result


def _result_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _canonical_discovery(
    manifest: Mapping[str, Any], value: Optional[Mapping[str, Any]]
) -> dict[str, Any]:
    if manifest["kind"] == "recorded_failures":
        if value:
            _fail("discovery_invalid")
        return {}
    if value is None:
        value = {
            "newly_discovered_metadata_count": 0,
            "newly_discovered_detail_saved_count": 0,
            "reached_interval_start": False,
            "stop_reason": "interrupted",
            "unresolved_interval": {
                "start_at": manifest["interval"]["start_at"],
                "end_at": manifest["interval"]["end_at"],
            },
        }
    if not isinstance(value, Mapping) or set(value) != _DISCOVERY_KEYS:
        _fail("discovery_invalid")
    metadata_count = value.get("newly_discovered_metadata_count")
    saved_count = value.get("newly_discovered_detail_saved_count")
    reached = value.get("reached_interval_start")
    reason = value.get("stop_reason")
    if (
        isinstance(metadata_count, bool)
        or not isinstance(metadata_count, int)
        or metadata_count < 0
        or isinstance(saved_count, bool)
        or not isinstance(saved_count, int)
        or saved_count < 0
        or saved_count > metadata_count
        or not isinstance(reached, bool)
        or reason not in _DISCOVERY_STOP_REASONS
    ):
        _fail("discovery_invalid")
    unresolved = value.get("unresolved_interval")
    if reached:
        if unresolved is not None or reason != "window_start_reached":
            _fail("discovery_invalid")
    else:
        if not isinstance(unresolved, Mapping) or set(unresolved) != {"start_at", "end_at"}:
            _fail("discovery_invalid")
        start = _timestamp(unresolved["start_at"])
        end = _timestamp(unresolved["end_at"])
        if start > end:
            _fail("discovery_invalid")
        unresolved = {"start_at": start, "end_at": end}
    return {
        "initial_known_detail_target_count": len(manifest["targets"]),
        "newly_discovered_metadata_count": metadata_count,
        "newly_discovered_detail_saved_count": saved_count,
        "reached_interval_start": reached,
        "stop_reason": reason,
        "unresolved_interval": unresolved,
    }


class MarketNewsRecoveryService:
    """Domain orchestration over the capture DAL and local job-run owner."""

    def __init__(
        self,
        dal: Any,
        job_store: Any,
        *,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.dal = dal
        self.job_store = job_store
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _rows(self, news_ids: Iterable[str]) -> list[dict[str, Any]]:
        try:
            return self.dal.get_sa_market_news_recovery_rows(list(news_ids))
        except RuntimeError as exc:
            raise MarketNewsRecoveryError("recovery_data_unavailable") from exc

    @staticmethod
    def _retryable_ids(result: Any) -> list[str]:
        if not isinstance(result, Mapping):
            return []
        items = result.get("item_outcomes")
        if not isinstance(items, list):
            return []
        return [
            item["news_id"]
            for item in items
            if isinstance(item, Mapping)
            and item.get("state") == "failed_retryable"
            and isinstance(item.get("news_id"), str)
            and item["news_id"]
        ]

    @staticmethod
    def _legacy_failure_ids(result: Any) -> list[str]:
        if not isinstance(result, Mapping) or not isinstance(result.get("detail_failures"), list):
            return []
        return [
            item["news_id"]
            for item in result["detail_failures"]
            if isinstance(item, Mapping)
            and isinstance(item.get("news_id"), str)
            and item["news_id"]
        ]

    def preview_recorded_failures(
        self, *, source_run_ids: Optional[Iterable[int]] = None
    ) -> dict[str, Any]:
        explicit = source_run_ids is not None
        requested_ids = sorted({int(value) for value in (source_run_ids or [])})
        source_rows: list[dict[str, Any]] = []
        source = "reviewed_historical_runs" if explicit else "latest_structured_retryable"
        if explicit:
            wanted = set(requested_ids)
            source_rows = [
                row
                for row in self.job_store.list_runs(
                    job_name=MARKET_NEWS_SYNC_JOB_NAME, limit=200
                )
                if row.get("id") in wanted
            ]
            if {int(row["id"]) for row in source_rows} != wanted:
                _fail("source_run_not_found")
        else:
            summary = self.job_store.structured_extension_summary_by_name(
                [MARKET_NEWS_SYNC_JOB_NAME]
            ) or {}
            latest = (summary.get(MARKET_NEWS_SYNC_JOB_NAME) or {}).get("latest_attempt")
            if isinstance(latest, dict):
                source_rows = [latest]
                requested_ids = [int(latest["id"])]

        news_ids: list[str] = []
        for row in source_rows:
            result = row.get("result")
            news_ids.extend(self._retryable_ids(result))
            if explicit:
                news_ids.extend(self._legacy_failure_ids(result))
        rows = self._rows(sorted(set(news_ids)))
        manifest = build_repair_manifest(
            kind="recorded_failures",
            targets=rows,
            source_run_ids=requested_ids,
        )
        can_start = bool(rows)
        return {
            "status": "ready" if can_start else "no_work",
            "source": source,
            "target_count": len(rows),
            "missing_metadata_count": len(set(news_ids) - {row["news_id"] for row in rows}),
            "can_start": can_start,
            "manifest": manifest,
            "manifest_hash": manifest_hash(manifest),
        }

    def preview_incident(self) -> dict[str, Any]:
        end = self._now().astimezone(timezone.utc).replace(microsecond=0)
        floor = end - timedelta(hours=MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS)
        summary = self.job_store.structured_extension_summary_by_name(
            [MARKET_NEWS_SYNC_JOB_NAME]
        ) or {}
        anchor = (summary.get(MARKET_NEWS_SYNC_JOB_NAME) or {}).get(
            "latest_derived_complete"
        )
        anchor_verified = isinstance(anchor, dict)
        anchor_time = None
        if anchor_verified:
            anchor_time = _utc(anchor.get("finished_at") or anchor.get("started_at"))
        start = max(floor, anchor_time) if anchor_time is not None else floor
        interval = {
            "start_at": start.isoformat(timespec="seconds"),
            "end_at": end.isoformat(timespec="seconds"),
            "anchor_verified": anchor_verified,
        }
        try:
            rows = self.dal.get_sa_market_news_missing_detail_interval(
                interval["start_at"], interval["end_at"]
            )
        except RuntimeError as exc:
            raise MarketNewsRecoveryError("recovery_data_unavailable") from exc
        source_run_ids = [int(anchor["id"])] if anchor_verified else []
        manifest = build_repair_manifest(
            kind="incident_window",
            targets=rows,
            source_run_ids=source_run_ids,
            interval=interval,
        )
        discovery = {
            "enabled": start < end,
            "missing_metadata_count": None,
            "max_list_scroll_rounds": MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS,
            "max_elapsed_ms": MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS,
            "stable_rounds": MARKET_NEWS_INCIDENT_STABLE_ROUNDS,
        }
        can_start = bool(rows) or discovery["enabled"]
        return {
            "status": (
                "ready" if rows else "discovery_only" if discovery["enabled"] else "no_work"
            ),
            "source_run_id": source_run_ids[0] if source_run_ids else None,
            "target_count": len(rows),
            "discovery": discovery,
            "can_start": can_start,
            "manifest": manifest,
            "manifest_hash": manifest_hash(manifest),
        }

    @staticmethod
    def _response(row: Mapping[str, Any], *, created: Optional[bool] = None) -> dict[str, Any]:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        result = row.get("result") if isinstance(row.get("result"), Mapping) else {}
        response = {
            "run_id": int(row["id"]),
            "status": row["status"],
            "manifest": payload.get("manifest"),
            "manifest_hash": payload.get("manifest_hash"),
            **result,
        }
        if created is not None:
            response["created"] = created
        return response

    def start(self, manifest: Mapping[str, Any], expected_hash: str) -> dict[str, Any]:
        canonical = _validate_manifest(manifest)
        if manifest_hash(canonical) != expected_hash:
            _fail("manifest_invalid")
        interval = canonical.get("interval")
        has_discovery = bool(
            canonical["kind"] == "incident_window"
            and interval
            and interval["start_at"] < interval["end_at"]
        )
        if not canonical["targets"] and not has_discovery:
            _fail("no_recovery_work")
        try:
            value = self.job_store.start_market_news_repair(
                manifest=canonical, manifest_hash=expected_hash
            )
        except ValueError as exc:
            raise MarketNewsRecoveryError(str(exc)) from exc
        return self._response(value["run"], created=bool(value["created"]))

    def state(self, run_id: Optional[int] = None) -> dict[str, Any]:
        row = self.job_store.get_market_news_repair(run_id)
        if row is None:
            _fail("repair_not_found")
        return self._response(row)

    def checkpoint(
        self,
        run_id: int,
        expected_hash: str,
        *,
        news_id: str,
        attempt_id: str,
        state: str,
        reason_code: str,
        evidence_code: Optional[str] = None,
        attempt_count: int = 1,
    ) -> dict[str, Any]:
        if not isinstance(attempt_id, str) or not attempt_id.strip() or len(attempt_id) > 160:
            _fail("checkpoint_invalid")
        item = _validate_attempt_item(
            news_id=news_id,
            state=state,
            reason_code=reason_code,
            attempt_count=attempt_count,
            evidence_code=evidence_code,
        )
        attempt = {"attempt_id": attempt_id, **item}
        try:
            row = self.job_store.checkpoint_market_news_repair(
                run_id=run_id,
                manifest_hash=expected_hash,
                attempt=attempt,
            )
        except ValueError as exc:
            raise MarketNewsRecoveryError(str(exc)) from exc
        return self._response(row)

    @staticmethod
    def _latest_attempts(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        progress = result.get("progress") if isinstance(result.get("progress"), Mapping) else {}
        attempts = progress.get("attempts") if isinstance(progress.get("attempts"), list) else []
        latest: dict[str, dict[str, Any]] = {}
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            news_id = attempt.get("news_id")
            current = latest.get(news_id)
            rank = (int(attempt.get("attempt_count") or 0), str(attempt.get("attempt_id") or ""))
            current_rank = (
                int(current.get("attempt_count") or 0),
                str(current.get("attempt_id") or ""),
            ) if current else (-1, "")
            if isinstance(news_id, str) and rank > current_rank:
                latest[news_id] = attempt
        return latest

    def _terminal_result(
        self,
        row: Mapping[str, Any],
        *,
        cancelled: bool = False,
        discovery: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        payload = row["payload"]
        manifest = _validate_manifest(payload["manifest"])
        expected_hash = payload["manifest_hash"]
        if manifest_hash(manifest) != expected_hash:
            _fail("manifest_invalid")
        target_ids = [item["news_id"] for item in manifest["targets"]]
        try:
            presence = self.dal.get_sa_market_news_body_presence(target_ids)
        except RuntimeError as exc:
            raise MarketNewsRecoveryError("recovery_data_unavailable") from exc
        latest = self._latest_attempts(row.get("result") or {})
        items: list[dict[str, Any]] = []
        for target in manifest["targets"]:
            news_id = target["news_id"]
            attempt = latest.get(news_id)
            attempt_count = max(1, int((attempt or {}).get("attempt_count") or 0))
            if cancelled:
                item = _validate_attempt_item(
                    news_id=news_id,
                    state="failed_retryable",
                    reason_code="interrupted",
                    attempt_count=attempt_count,
                    evidence_code=None,
                )
            elif target["body_present"]:
                item = _validate_attempt_item(
                    news_id=news_id,
                    state="already_present",
                    reason_code="body_present_at_freeze",
                    attempt_count=0,
                    evidence_code=None,
                )
            elif presence.get(news_id) is True:
                item = _validate_attempt_item(
                    news_id=news_id,
                    state="repaired",
                    reason_code="body_present_during_run",
                    attempt_count=attempt_count,
                    evidence_code=None,
                )
            elif attempt and attempt.get("state") == "unavailable_at_source":
                item = _validate_attempt_item(
                    news_id=news_id,
                    state="unavailable_at_source",
                    reason_code=attempt["reason_code"],
                    attempt_count=attempt_count,
                    evidence_code=attempt.get("evidence_code"),
                )
            else:
                reason = (
                    attempt.get("reason_code")
                    if attempt and attempt.get("state") == "failed_retryable"
                    else "detail_save_failed"
                    if attempt
                    else "interrupted"
                )
                item = _validate_attempt_item(
                    news_id=news_id,
                    state="failed_retryable",
                    reason_code=reason,
                    attempt_count=attempt_count,
                    evidence_code=None,
                )
            items.append(item)
        counts = _counts(items)
        derived = "degraded" if counts["failed_retryable"] else "complete"
        result: dict[str, Any] = {
            "schema_version": 1,
            "lifecycle_state": "cancelled" if cancelled else "terminal",
            "reason_code": "operator_cancelled" if cancelled else None,
            "manifest_hash": expected_hash,
            "derived_outcome": derived,
            "db_status": "failed" if cancelled or derived == "degraded" else "succeeded",
            "counts": counts,
            "item_outcomes": items,
            "discovery": _canonical_discovery(manifest, discovery),
            "resumable": False,
        }
        result["result_hash"] = _result_hash(result)
        return result

    def finalize(
        self,
        run_id: int,
        expected_hash: str,
        *,
        discovery: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        row = self.job_store.get_market_news_repair(run_id)
        if row is None:
            _fail("repair_not_found")
        if row["status"] != "running":
            return self._response(row)
        if row["payload"].get("manifest_hash") != expected_hash:
            _fail("manifest_invalid")
        result = self._terminal_result(row, discovery=discovery)
        try:
            stored = self.job_store.finish_market_news_repair(
                run_id=run_id,
                manifest_hash=expected_hash,
                status=result["db_status"],
                result=result,
                error_code=(
                    "repair_retryable" if result["db_status"] == "failed" else None
                ),
            )
        except ValueError as exc:
            raise MarketNewsRecoveryError(str(exc)) from exc
        return self._response(stored)

    def cancel(self, run_id: int, expected_hash: str) -> dict[str, Any]:
        row = self.job_store.get_market_news_repair(run_id)
        if row is None:
            _fail("repair_not_found")
        if row["status"] != "running":
            return self._response(row)
        if row["payload"].get("manifest_hash") != expected_hash:
            _fail("manifest_invalid")
        result = self._terminal_result(row, cancelled=True)
        try:
            stored = self.job_store.finish_market_news_repair(
                run_id=run_id,
                manifest_hash=expected_hash,
                status="failed",
                result=result,
                error_code="operator_cancelled",
            )
        except ValueError as exc:
            raise MarketNewsRecoveryError(str(exc)) from exc
        return self._response(stored)

    def interrupt_stale(self, run_id: int, expected_hash: str) -> dict[str, Any]:
        try:
            row = self.job_store.mark_market_news_repair_interrupted(
                run_id=run_id, manifest_hash=expected_hash
            )
        except ValueError as exc:
            raise MarketNewsRecoveryError(str(exc)) from exc
        return self._response(row)
