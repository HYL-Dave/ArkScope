"""Acquisition-age policy and same-query reuse for financial observations."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import time

from src.ibkr_gateway_lock import lock_dir
from src.fundamentals.execution import check_financial_work


FINANCIAL_REUSE_SECONDS = 7 * 86400
EARNINGS_REUSE_SECONDS = 3600
_WAIT_SECONDS = 120


class ReuseFailure(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ReusePolicy:
    mode: str
    max_age_seconds: int | None


def policy(freshness="auto", max_age_seconds=None, *, default_age=FINANCIAL_REUSE_SECONDS):
    if (freshness not in ("auto", "stored", "refresh")
            or (max_age_seconds is not None and (type(max_age_seconds) is not int or max_age_seconds < 0))
            or (freshness == "refresh" and max_age_seconds is not None)):
        raise ReuseFailure("financial_freshness_invalid")
    if freshness == "auto" and max_age_seconds is None:
        if type(default_age) is not int or default_age < 0:
            raise ReuseFailure("financial_reuse_policy_invalid")
        max_age_seconds = default_age
    return ReusePolicy(freshness, max_age_seconds)


def configured_age(profile, *, earnings=False):
    preferences = profile.get("data_preferences", {}) if isinstance(profile, dict) else {}
    sources = preferences.get("fundamentals_sources", {}) if isinstance(preferences, dict) else {}
    if not isinstance(sources, dict):
        raise ReuseFailure("financial_reuse_policy_invalid")
    key = "earnings_refresh_seconds" if earnings else "refresh_days"
    default = EARNINGS_REUSE_SECONDS if earnings else FINANCIAL_REUSE_SECONDS // 86400
    value = sources.get(key, default)
    if type(value) is not int or value < 0:
        raise ReuseFailure("financial_reuse_policy_invalid")
    return value if earnings else value * 86400


def instant(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


@dataclass(frozen=True)
class Observation:
    data: object
    fetched_at: datetime
    evaluated_at: datetime
    retrieval: str = "stored"
    persisted: bool = True

    def describe(self, provider, dataset, reuse_policy, **details):
        age = (self.evaluated_at - self.fetched_at).total_seconds()
        maximum = reuse_policy.max_age_seconds
        return {
            "provider": provider, "dataset": dataset, "retrieval": self.retrieval,
            "freshness_mode": reuse_policy.mode,
            "fetched_at": self.fetched_at.isoformat(), "evaluated_at": self.evaluated_at.isoformat(),
            "age_seconds": age, "max_age_seconds": maximum,
            "within_max_age": None if maximum is None else 0 <= age <= maximum,
            "persisted": self.persisted, **details,
        }


def read_entry(backend, key, provider, ticker, validate, max_age, *, not_before=None):
    if backend is None:
        return None
    try:
        row = backend.get_financial_cache_entry(key)
    except Exception:
        return None
    if not isinstance(row, dict) or row.get("source") != provider or row.get("ticker") != ticker:
        return None
    fetched = instant(row.get("fetched_at"))
    expires = instant(row.get("expires_at"))
    now = datetime.now(timezone.utc)
    if (fetched is None or expires is None or expires < fetched or fetched > now
            or (not_before is not None and fetched < not_before)
            or (max_age is not None and (now - fetched).total_seconds() > max_age)):
        return None
    data = validate(row.get("data"))
    return None if data is None else Observation(data, fetched, now)


def storage_scope(backend):
    for name in ("_market_db", "db_path"):
        value = getattr(backend, name, None)
        if isinstance(value, (str, Path)):
            return str(Path(value).expanduser().resolve())
    return f"process:{os.getpid()}:backend:{id(backend)}"


@contextmanager
def acquisition_lock(scope):
    """A fresh descriptor per caller serializes both threads and processes."""
    try:
        import fcntl
    except ImportError as exc:
        raise ReuseFailure("financial_refresh_lock_unavailable") from exc
    digest = hashlib.sha256(json.dumps(scope, separators=(",", ":")).encode()).hexdigest()
    root = lock_dir() / "financial_acquisitions"
    fd = None
    waited = False
    try:
        try:
            root.mkdir(parents=True, exist_ok=True)
            if not stat.S_ISDIR(root.lstat().st_mode):
                raise OSError("unsafe lock directory")
            fd = os.open(root / (digest + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError("unsafe lock file")
            deadline = time.monotonic() + _WAIT_SECONDS
            while True:
                check_financial_work()
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    waited = True
                    if time.monotonic() >= deadline:
                        raise ReuseFailure("financial_refresh_in_progress")
                    time.sleep(0.02)
        except OSError as exc:
            raise ReuseFailure("financial_refresh_lock_unavailable") from exc
        yield waited
    finally:
        if fd is not None:
            os.close(fd)


def reuse_or_acquire(reuse_policy, scope, read, acquire):
    check_financial_work()
    started = datetime.now(timezone.utc)
    if reuse_policy.mode != "refresh":
        saved = read(reuse_policy.max_age_seconds)
        if saved is not None:
            return saved
        if reuse_policy.mode == "stored":
            raise ReuseFailure("financial_stored_data_unavailable")
    with acquisition_lock(scope) as waited:
        check_financial_work()
        saved = read(reuse_policy.max_age_seconds,
                     not_before=started if reuse_policy.mode == "refresh" else None)
        if saved is not None:
            return replace(saved, retrieval="coalesced" if waited else "stored")
        if waited:
            # A failed/unsaved attempt is not a new caller's authority to retry.
            raise ReuseFailure("financial_refresh_result_unavailable")
        return acquire()


def cached_dataset(backend, key, provider, ticker, reuse_policy, validate, fetch, *, ttl_days=90):
    """Persist only validated successful observations, outside network I/O."""
    def read(max_age, not_before=None):
        return read_entry(backend, key, provider, ticker, validate, max_age, not_before=not_before)

    def acquire():
        data = validate(fetch())
        if data is None:
            raise ReuseFailure("financial_source_data_unavailable")
        now = datetime.now(timezone.utc)
        persisted = False
        if backend is not None:
            try:
                persisted = bool(backend.set_financial_cache(
                    key, ticker, data, source=provider, ttl_days=ttl_days, fetched_at=now.isoformat(),
                ))
            except Exception:
                pass
        return Observation(data, now, now, "refreshed", persisted)

    return reuse_or_acquire(reuse_policy, [storage_scope(backend), provider, key], read, acquire)
