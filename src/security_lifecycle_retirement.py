"""Read-only retirement guards for legacy lifecycle search storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    verify_v1_profile_connection as verify_profile_connection,
)


@dataclass(frozen=True)
class TavilyRetirementPreflight:
    profile_path: str
    tavily_run_count: int
    tavily_evidence_count: int
    storage_empty: bool


class TavilyRetirementUnavailable(RuntimeError):
    code = "tavily_retirement_preflight_unavailable"


class TavilyRetirementBlocked(RuntimeError):
    code = "stored_tavily_rows_present"

    def __init__(self, *, run_count: int, evidence_count: int):
        self.run_count = int(run_count)
        self.evidence_count = int(evidence_count)
        super().__init__(self.code)


def preflight_tavily_retirement(
    *, profile_path: str | Path
) -> TavilyRetirementPreflight:
    """Prove that an explicit profile database has no stored Tavily rows."""

    candidate = Path(profile_path)
    if not candidate.is_file():
        raise TavilyRetirementUnavailable(
            "tavily_retirement_preflight_unavailable"
        )

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{candidate.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        verify_profile_connection(connection)
        connection.execute("BEGIN")
        run_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM security_lifecycle_investigation_runs "
                "WHERE adapter='tavily'"
            ).fetchone()[0]
        )
        evidence_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM security_lifecycle_evidence "
                "WHERE adapter='tavily'"
            ).fetchone()[0]
        )
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch) as exc:
        raise TavilyRetirementUnavailable(
            "tavily_retirement_preflight_unavailable"
        ) from exc
    finally:
        if connection is not None:
            connection.close()

    report = TavilyRetirementPreflight(
        profile_path=str(candidate.resolve()),
        tavily_run_count=run_count,
        tavily_evidence_count=evidence_count,
        storage_empty=(run_count == 0 and evidence_count == 0),
    )
    if not report.storage_empty:
        raise TavilyRetirementBlocked(
            run_count=run_count,
            evidence_count=evidence_count,
        )
    return report


__all__ = [
    "TavilyRetirementBlocked",
    "TavilyRetirementPreflight",
    "TavilyRetirementUnavailable",
    "preflight_tavily_retirement",
]
