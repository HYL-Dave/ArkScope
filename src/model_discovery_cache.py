"""Per-credential model discovery cache (P2.7).

Observational entitlement store: which models did a (provider, auth_mode,
credential) scope actually SEE, and when. Registry facts never live here;
discovery results never mutate the registry.

Contracts (pinned by tests/test_model_discovery_cache.py):
- a successful run REPLACES the scope's run metadata + model rows in one
  transaction (zero-model success is a real, representable state);
- failed runs are never recorded (caller contract) so they cannot clobber a
  previous good observation;
- the scope carries a one-way ``secret_fingerprint`` — a replaced secret under
  the same credential id reads back as ``never_discovered`` instead of serving
  the previous account's entitlement;
- ``seed_only`` marks channels with no live listing (e.g. claude_code_oauth) so
  the UI can badge instead of nudging forever;
- no secret material is ever stored (fingerprints are sha256 digests).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_discovery_runs (
    provider           TEXT NOT NULL,
    auth_mode          TEXT NOT NULL,
    credential_id      TEXT NOT NULL,
    secret_fingerprint TEXT NOT NULL,
    status             TEXT NOT NULL,
    discovered_at      TEXT NOT NULL,
    source_url         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (provider, auth_mode, credential_id)
);

CREATE TABLE IF NOT EXISTS model_discovery_models (
    provider      TEXT NOT NULL,
    auth_mode     TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    model_id      TEXT NOT NULL,
    label         TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (provider, auth_mode, credential_id, model_id)
);

CREATE TABLE IF NOT EXISTS model_discovery_epochs (
    provider      TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    epoch         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, credential_id)
);
"""


class StaleDiscoveryWrite(RuntimeError):
    """A discovery result was produced BEFORE a lifecycle op (re-login / delete)
    landed on the credential — committing it would resurrect the old account's
    entitlement. Callers skip the commit and report the run as uncached."""


@dataclass(frozen=True)
class CachedModel:
    model_id: str
    label: str
    source: str


@dataclass(frozen=True)
class DiscoveryScope:
    status: str                    # "ok" | "seed_only" | "never_discovered"
    discovered_at: str | None
    models: list[CachedModel]


class ModelDiscoveryCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def lifecycle_epoch(self, *, provider: str, credential_id: str) -> int:
        """The credential's lifecycle generation. Bumped by every `delete_scope`
        (re-login clear / credential delete). Discovery captures it BEFORE the
        provider call and passes it as `expected_epoch` to `record_run` — a moved
        epoch means the listing predates a lifecycle op and must not be cached."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT epoch FROM model_discovery_epochs WHERE provider=? AND credential_id=?",
                (provider, credential_id),
            ).fetchone()
            return int(row["epoch"]) if row else 0

    def record_run(
        self,
        *,
        provider: str,
        auth_mode: str,
        credential_id: str,
        secret_fingerprint: str,
        status: str,
        models: list[dict],
        source_url: str = "",
        expected_epoch: int | None = None,
    ) -> None:
        """Record a COMPLETED discovery run (callers never record failures).

        With `expected_epoch`, the write is validated INSIDE the write
        transaction (after the first DELETE takes the write lock, so a
        concurrent `delete_scope` — even from another process — serializes
        before or after the whole commit): if the credential's lifecycle epoch
        moved since capture, raise `StaleDiscoveryWrite` and roll back."""
        if status not in ("ok", "seed_only"):
            raise ValueError(f"invalid discovery run status: {status!r}")
        now = _now()
        scope = (provider, auth_mode, credential_id)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM model_discovery_models "
                "WHERE provider=? AND auth_mode=? AND credential_id=?",
                scope,
            )
            if expected_epoch is not None:
                row = conn.execute(
                    "SELECT epoch FROM model_discovery_epochs WHERE provider=? AND credential_id=?",
                    (provider, credential_id),
                ).fetchone()
                current = int(row["epoch"]) if row else 0
                if current != expected_epoch:
                    # context-manager exit rolls the DELETE back on raise
                    raise StaleDiscoveryWrite(
                        f"discovery write for {provider}/{credential_id} is stale "
                        f"(lifecycle epoch {expected_epoch} -> {current})",
                    )
            conn.execute(
                """
                INSERT INTO model_discovery_runs
                (provider, auth_mode, credential_id, secret_fingerprint, status,
                 discovered_at, source_url)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(provider, auth_mode, credential_id) DO UPDATE SET
                    secret_fingerprint=excluded.secret_fingerprint,
                    status=excluded.status,
                    discovered_at=excluded.discovered_at,
                    source_url=excluded.source_url
                """,
                (*scope, secret_fingerprint, status, now, source_url),
            )
            conn.executemany(
                """
                INSERT INTO model_discovery_models
                (provider, auth_mode, credential_id, model_id, label, source)
                VALUES (?,?,?,?,?,?)
                """,
                [
                    (*scope, str(m["id"]), str(m.get("label") or ""), str(m.get("source") or ""))
                    for m in models
                ],
            )

    def delete_scope(
        self,
        *,
        provider: str,
        credential_id: str,
        auth_mode: str | None = None,
    ) -> int:
        """Remove a credential's cached entitlement (S3 lifecycle: re-login clears
        its own scope; credential deletion cascades every mode). One transaction
        over BOTH tables; returns total rows removed; idempotent (0 on repeat).
        `auth_mode=None` wipes all modes for that credential."""
        where = "provider=? AND credential_id=?"
        params: tuple = (provider, credential_id)
        if auth_mode is not None:
            where += " AND auth_mode=?"
            params = (*params, auth_mode)
        with self._connect() as conn:
            models = conn.execute(
                f"DELETE FROM model_discovery_models WHERE {where}", params,
            ).rowcount
            runs = conn.execute(
                f"DELETE FROM model_discovery_runs WHERE {where}", params,
            ).rowcount
            # ALWAYS bump the lifecycle epoch (even a 0-row clear invalidates an
            # in-flight discovery capture) — same transaction as the deletes.
            conn.execute(
                "INSERT INTO model_discovery_epochs (provider, credential_id, epoch) VALUES (?,?,1) "
                "ON CONFLICT(provider, credential_id) DO UPDATE SET epoch = epoch + 1",
                (provider, credential_id),
            )
        return int(models) + int(runs)

    def get(
        self,
        *,
        provider: str,
        auth_mode: str,
        credential_id: str,
        secret_fingerprint: str,
    ) -> DiscoveryScope:
        scope = (provider, auth_mode, credential_id)
        with self._connect() as conn:
            run = conn.execute(
                "SELECT * FROM model_discovery_runs "
                "WHERE provider=? AND auth_mode=? AND credential_id=?",
                scope,
            ).fetchone()
            if run is None or run["secret_fingerprint"] != secret_fingerprint:
                return DiscoveryScope(status="never_discovered",
                                      discovered_at=None, models=[])
            rows = conn.execute(
                "SELECT model_id, label, source FROM model_discovery_models "
                "WHERE provider=? AND auth_mode=? AND credential_id=? "
                "ORDER BY model_id",
                scope,
            ).fetchall()
        return DiscoveryScope(
            status=run["status"],
            discovered_at=run["discovered_at"],
            models=[CachedModel(r["model_id"], r["label"], r["source"]) for r in rows],
        )
