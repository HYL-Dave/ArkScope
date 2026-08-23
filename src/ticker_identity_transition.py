"""Deterministic previews for user-approved ticker identity transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import sqlite3
from typing import Iterable, Mapping

from src.profile_state import EDITABLE_TAG_SOURCES
from src.security_lifecycle_investigation import assessment_fingerprint
from src.ticker_identity_schema import PRIORITY_RESOLUTIONS


_LEGACY_SOURCE_KEY = "legacy_config_seed"
_PROFILE_SOURCE_KEYS = frozenset({"manual_lists", _LEGACY_SOURCE_KEY})
_SYMBOL_OUTCOMES = frozenset({"symbol_changed", "venue_transfer"})


@dataclass(frozen=True)
class TransitionOptions:
    execute_on: str | None
    priority_resolution: str | None = None
    unhide_successor: bool = False

    def __post_init__(self) -> None:
        if (
            self.priority_resolution is not None
            and self.priority_resolution not in PRIORITY_RESOLUTIONS
        ):
            raise ValueError("priority_resolution")
        if not isinstance(self.unhide_successor, bool):
            raise ValueError("unhide_successor")


def _canonical_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    if len(encoded.encode("utf-8")) > 65536:
        raise ValueError("transition_preview_too_large")
    return encoded


def profile_snapshot_sha256(preview: Mapping[str, object]) -> str:
    """Hash the canonical preview payload, excluding its self-referential digest."""

    payload = {key: value for key, value in preview.items() if key != "preview_sha256"}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _ticker(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if len(text) > 20 or "\0" in text:
        raise ValueError("ticker")
    return text


def _sha256(name: str, value: object) -> str:
    text = str(value or "")
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(name)
    return text


def _execution_date(
    options: TransitionOptions,
    assessment: Mapping[str, object],
) -> tuple[str | None, str | None]:
    raw = str(options.execute_on or assessment.get("effective_date") or "").strip()
    if not raw:
        return None, "execution_date_required"
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None, "execution_date_invalid"
    if parsed.isoformat() != raw:
        return None, "execution_date_invalid"
    return raw, None


def _watchlist_effects(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
) -> dict[str, list[dict]]:
    source_rows = conn.execute(
        "SELECT w.id,w.name,m.position FROM watchlist_memberships m "
        "JOIN watchlists w ON w.id=m.list_id "
        "WHERE m.ticker=? AND m.archived_at IS NULL AND w.archived_at IS NULL "
        "ORDER BY w.id",
        (source_ticker,),
    ).fetchall()
    successor_rows: dict[int, tuple[int, str | None]] = {}
    if successor_ticker is not None:
        successor_rows = {
            int(row[0]): (int(row[1]), row[2])
            for row in conn.execute(
                "SELECT m.list_id,m.position,m.archived_at "
                "FROM watchlist_memberships m JOIN watchlists w ON w.id=m.list_id "
                "WHERE m.ticker=? AND w.archived_at IS NULL",
                (successor_ticker,),
            )
        }

    effects: dict[str, list[dict]] = {
        "add": [],
        "archive": [],
        "reactivate": [],
        "unchanged": [],
    }
    for list_id_raw, list_name_raw, source_position_raw in source_rows:
        list_id = int(list_id_raw)
        list_name = str(list_name_raw)
        source_position = int(source_position_raw)
        effects["archive"].append(
            {
                "list_id": list_id,
                "list_name": list_name,
                "position": source_position,
                "ticker": source_ticker,
            }
        )
        if successor_ticker is None:
            continue
        successor = successor_rows.get(list_id)
        if successor is None:
            effects["add"].append(
                {
                    "list_id": list_id,
                    "list_name": list_name,
                    "position": source_position,
                    "ticker": successor_ticker,
                }
            )
            continue
        successor_position, archived_at = successor
        target = "reactivate" if archived_at is not None else "unchanged"
        effects[target].append(
            {
                "list_id": list_id,
                "list_name": list_name,
                "position": successor_position,
                "ticker": successor_ticker,
            }
        )
    return effects


def _legacy_effects(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
) -> dict[str, list[dict]]:
    rows = {
        str(row[0]): row[1]
        for row in conn.execute(
            "SELECT ticker,archived_at FROM universe_source_memberships "
            "WHERE source_key=? AND ticker IN (?,?)",
            (_LEGACY_SOURCE_KEY, source_ticker, successor_ticker or source_ticker),
        )
    }
    effects: dict[str, list[dict]] = {
        "add": [],
        "archive": [],
        "reactivate": [],
        "unchanged": [],
    }
    if source_ticker not in rows or rows[source_ticker] is not None:
        return effects
    effects["archive"].append(
        {"source_key": _LEGACY_SOURCE_KEY, "ticker": source_ticker}
    )
    if successor_ticker is None:
        return effects
    successor_archived_at = rows.get(successor_ticker, ...)
    item = {"source_key": _LEGACY_SOURCE_KEY, "ticker": successor_ticker}
    if successor_archived_at is ...:
        effects["add"].append(item)
    elif successor_archived_at is None:
        effects["unchanged"].append(item)
    else:
        effects["reactivate"].append(item)
    return effects


def _editable_tags_to_copy(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
) -> list[dict]:
    if successor_ticker is None:
        return []
    placeholders = ",".join("?" for _ in EDITABLE_TAG_SOURCES)
    source_rows = conn.execute(
        "SELECT facet,value,source FROM ticker_tags WHERE ticker=? "
        f"AND source IN ({placeholders}) ORDER BY facet,source,value",
        (source_ticker, *EDITABLE_TAG_SOURCES),
    ).fetchall()
    successor_rows = {
        (str(row[0]), str(row[1]), str(row[2]))
        for row in conn.execute(
            "SELECT facet,value,source FROM ticker_tags WHERE ticker=? "
            f"AND source IN ({placeholders})",
            (successor_ticker, *EDITABLE_TAG_SOURCES),
        )
    }
    return [
        {
            "facet": str(facet),
            "source": str(source),
            "ticker": successor_ticker,
            "value": str(value),
        }
        for facet, value, source in source_rows
        if (str(facet), str(value), str(source)) not in successor_rows
    ]


def _meta_state(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
    options: TransitionOptions,
    transition_kind: str | None,
) -> tuple[dict, dict, list[str]]:
    tickers = (source_ticker, successor_ticker or source_ticker)
    rows = {
        str(row[0]): {"priority": row[1], "hidden_at": row[2]}
        for row in conn.execute(
            "SELECT ticker,priority,hidden_at FROM ticker_meta WHERE ticker IN (?,?)",
            tickers,
        )
    }
    source = rows.get(source_ticker, {"priority": None, "hidden_at": None})
    successor = rows.get(
        successor_ticker or "", {"priority": None, "hidden_at": None}
    )
    source_priority = source["priority"]
    successor_priority = successor["priority"]
    blockers: list[str] = []
    result_priority = None
    if transition_kind == "symbol_continuation":
        if (
            source_priority is not None
            and successor_priority is not None
            and source_priority != successor_priority
        ):
            if options.priority_resolution is None:
                blockers.append("priority_resolution_required")
            elif options.priority_resolution == "source":
                result_priority = source_priority
            else:
                result_priority = successor_priority
        else:
            result_priority = (
                source_priority if source_priority is not None else successor_priority
            )
    priority = {
        "resolution": options.priority_resolution,
        "result_value": result_priority,
        "source_value": source_priority,
        "successor_value": successor_priority,
        "write_successor": (
            transition_kind == "symbol_continuation"
            and result_priority is not None
            and result_priority != successor_priority
        ),
    }
    successor_hidden = bool(successor["hidden_at"]) if successor_ticker else False
    if transition_kind == "symbol_continuation" and successor_hidden:
        if not options.unhide_successor:
            blockers.append("successor_hidden")
    suppression = {
        "hide_source": False,
        "source_hidden": bool(source["hidden_at"]),
        "successor_hidden": successor_hidden,
        "unhide_successor": bool(
            transition_kind == "symbol_continuation"
            and successor_hidden
            and options.unhide_successor
        ),
    }
    return priority, suppression, blockers


def _proposal_state(
    *,
    case_id: str,
    assessment_id: str,
    assessment_fingerprint_sha256: str,
    source_ticker: str,
    successor_ticker: str | None,
    transition_kind: str | None,
    proposals: Iterable[Mapping[str, object]],
) -> tuple[list[str], list[str]]:
    current: list[Mapping[str, object]] = []
    stale = False
    for proposal in proposals:
        if (
            str(proposal.get("case_id") or "") != case_id
            or str(proposal.get("assessment_id") or "") != assessment_id
            or _ticker(proposal.get("source_ticker")) != source_ticker
            or str(proposal.get("status") or "") != "proposed"
        ):
            continue
        if (
            proposal.get("projected_block_reason") == "stale_assessment"
            or proposal.get("assessment_fingerprint_sha256")
            != assessment_fingerprint_sha256
        ):
            stale = True
            continue
        current.append(proposal)

    blockers: list[str] = []
    if stale:
        blockers.append("stale_assessment")
    elif transition_kind == "symbol_continuation":
        remap = any(
            proposal.get("action_type") == "remap_symbol"
            and _ticker(proposal.get("replacement_ticker")) == successor_ticker
            and proposal.get("projected_block_reason") is None
            for proposal in current
        )
        if not remap:
            blockers.append("remap_proposal_missing")
    elif transition_kind == "terminal_delisting":
        if not any(
            proposal.get("action_type") == "notify"
            and proposal.get("projected_block_reason") is None
            for proposal in current
        ):
            blockers.append("proposal_missing")
    proposal_ids = sorted(
        {str(proposal.get("proposal_id") or "") for proposal in current}
    )
    if "" in proposal_ids:
        raise ValueError("proposal_id")
    return proposal_ids, blockers


def build_transition_preview(
    conn: sqlite3.Connection,
    *,
    case: Mapping[str, object],
    assessment: Mapping[str, object],
    proposals: Iterable[Mapping[str, object]],
    observation_fingerprint_sha256: str,
    sources: Iterable[str] | None,
    options: TransitionOptions,
) -> dict:
    """Return an immutable, canonical projection of every owned profile effect."""

    observation_fingerprint = _sha256(
        "observation_fingerprint_sha256", observation_fingerprint_sha256
    )
    evidence_fingerprint = _sha256(
        "evidence_set_sha256", assessment.get("evidence_set_sha256")
    )
    case_id = str(case.get("case_id") or "")
    assessment_id = str(assessment.get("assessment_id") or "")
    if not case_id or not assessment_id:
        raise ValueError("transition_authority_identity")
    source_ticker = _ticker(case.get("ticker"))
    if source_ticker is None:
        raise ValueError("source_ticker")
    successor_ticker = _ticker(assessment.get("successor_ticker"))
    outcomes = frozenset(str(value) for value in assessment.get("outcomes") or ())

    blockers: list[str] = []
    transition_kind: str | None = None
    if "symbol_changed" in outcomes and outcomes <= _SYMBOL_OUTCOMES:
        if successor_ticker is None:
            blockers.append("successor_missing")
        elif successor_ticker == source_ticker:
            blockers.append("successor_not_distinct")
        else:
            transition_kind = "symbol_continuation"
    elif outcomes == {"listing_ended"} and successor_ticker is None:
        transition_kind = "terminal_delisting"
    else:
        blockers.append("outcome_not_executable")

    if str(assessment.get("case_id") or "") != case_id:
        blockers.append("assessment_case_mismatch")
    if assessment.get("status") != "accepted":
        blockers.append("assessment_not_accepted")
    if assessment.get("relevance") != "direct_tracked_security":
        blockers.append("assessment_not_direct")
    if (
        assessment.get("stale") is True
        or assessment.get("observation_fingerprint_sha256") != observation_fingerprint
    ):
        blockers.append("stale_assessment")
    citations = assessment.get("citations") or ()
    if not any(
        citation.get("reference_kind") == "observation"
        and citation.get("cited_content_sha256") == observation_fingerprint
        for citation in citations
    ):
        blockers.append("observation_citation_required")

    execute_on, date_blocker = _execution_date(options, assessment)
    if transition_kind is not None and date_blocker is not None:
        blockers.append(date_blocker)

    if sources is None:
        active_sources: list[str] = []
        if transition_kind is not None:
            blockers.append("source_context_unavailable")
    else:
        active_sources = sorted(
            {
                text
                for source in sources
                if (text := str(source or "").strip())
            }
        )
        if transition_kind is not None and not active_sources:
            blockers.append("no_active_tracking_source")

    current_assessment_fingerprint = assessment_fingerprint(assessment)
    proposal_ids, proposal_blockers = _proposal_state(
        case_id=case_id,
        assessment_id=assessment_id,
        assessment_fingerprint_sha256=current_assessment_fingerprint,
        source_ticker=source_ticker,
        successor_ticker=successor_ticker,
        transition_kind=transition_kind,
        proposals=proposals,
    )
    blockers.extend(proposal_blockers)

    if transition_kind is None:
        watchlists = {"add": [], "archive": [], "reactivate": [], "unchanged": []}
        legacy = {"add": [], "archive": [], "reactivate": [], "unchanged": []}
        tags: list[dict] = []
    else:
        watchlists = _watchlist_effects(
            conn,
            source_ticker=source_ticker,
            successor_ticker=(
                successor_ticker if transition_kind == "symbol_continuation" else None
            ),
        )
        legacy = _legacy_effects(
            conn,
            source_ticker=source_ticker,
            successor_ticker=(
                successor_ticker if transition_kind == "symbol_continuation" else None
            ),
        )
        tags = _editable_tags_to_copy(
            conn,
            source_ticker=source_ticker,
            successor_ticker=(
                successor_ticker if transition_kind == "symbol_continuation" else None
            ),
        )

    priority, suppression, meta_blockers = _meta_state(
        conn,
        source_ticker=source_ticker,
        successor_ticker=successor_ticker,
        options=options,
        transition_kind=transition_kind,
    )
    blockers.extend(meta_blockers)
    portfolio_open = "portfolio_open" in active_sources
    if transition_kind == "terminal_delisting" and portfolio_open:
        blockers.append("portfolio_position_open")
    suppression["hide_source"] = bool(
        transition_kind is not None
        and not suppression["source_hidden"]
        and not portfolio_open
    )

    provider_owned_sources = sorted(
        source for source in active_sources if source not in _PROFILE_SOURCE_KEYS
    )
    caveats: list[str] = []
    if provider_owned_sources:
        caveats.append("provider_owned_sources_retained")
    if transition_kind == "symbol_continuation" and portfolio_open:
        caveats.append("portfolio_position_retained")
    if watchlists["unchanged"] or legacy["unchanged"]:
        caveats.append("successor_already_tracked")

    payload = {
        "active_sources": active_sources,
        "assessment_fingerprint_sha256": current_assessment_fingerprint,
        "assessment_id": assessment_id,
        "block_reasons": sorted(set(blockers)),
        "case_id": case_id,
        "caveats": sorted(caveats),
        "effects": {
            "editable_tags_to_copy": tags,
            "legacy_config_seed": legacy,
            "priority": priority,
            "suppression": suppression,
            "watchlists": watchlists,
        },
        "eligible": transition_kind is not None and not blockers,
        "evidence_set_sha256": evidence_fingerprint,
        "execute_on": execute_on,
        "observation_fingerprint_sha256": observation_fingerprint,
        "outcomes": sorted(outcomes),
        "proposal_ids": proposal_ids,
        "provider_owned_sources": provider_owned_sources,
        "source_ticker": source_ticker,
        "successor_ticker": successor_ticker,
        "transition_kind": transition_kind,
    }
    payload["preview_sha256"] = profile_snapshot_sha256(payload)
    return payload


__all__ = [
    "TransitionOptions",
    "build_transition_preview",
    "profile_snapshot_sha256",
]
