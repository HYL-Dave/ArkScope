"""Deterministic previews for user-approved ticker identity transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import sqlite3
from typing import Callable, Iterable, Mapping
import uuid

from src.profile_state import EDITABLE_TAG_SOURCES
from src.security_lifecycle_investigation import assessment_fingerprint
from src.ticker_identity_schema import (
    ATTEMPT_TRIGGERS,
    PRIORITY_RESOLUTIONS,
    verify_ticker_identity_connection,
)


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


def _rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    names = [str(item[0]) for item in cursor.description or ()]
    return [
        {name: row[index] for index, name in enumerate(names)}
        for row in cursor.fetchall()
    ]


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_columns(conn: sqlite3.Connection, table: str) -> frozenset[str]:
    return frozenset(
        str(row[1])
        for row in conn.execute(
            f"PRAGMA table_info({_quote_identifier(table)})"
        ).fetchall()
    )


def _portfolio_dependency_snapshot(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
) -> dict:
    required = {
        "portfolio_accounts": frozenset({"id", "archived_at"}),
        "portfolio_positions": frozenset(
            {"id", "account_id", "symbol", "asset_class", "closed_at"}
        ),
    }
    columns = {table: _table_columns(conn, table) for table in required}
    if any(
        not expected.issubset(columns[table])
        for table, expected in required.items()
    ):
        return {"available": False, "rows": []}

    tickers = (source_ticker, successor_ticker or source_ticker)
    rows = _rows_as_dicts(
        conn.execute(
            "SELECT p.id AS position_id,p.account_id,p.symbol,p.asset_class,"
            "p.closed_at,a.archived_at AS account_archived_at "
            "FROM portfolio_positions p JOIN portfolio_accounts a ON a.id=p.account_id "
            "WHERE UPPER(TRIM(p.symbol)) IN (?,?) "
            "ORDER BY p.id,p.account_id",
            tickers,
        )
    )
    return {"available": True, "rows": rows}


def _profile_dependency_snapshot(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
) -> dict:
    tickers = (source_ticker, successor_ticker or source_ticker)
    watchlists = _rows_as_dicts(
        conn.execute(
            "SELECT w.id AS list_id,w.name,w.kind,w.position AS list_position,"
            "w.archived_at AS list_archived_at,m.ticker,m.position,"
            "m.archived_at,m.created_at,m.updated_at "
            "FROM watchlist_memberships m JOIN watchlists w ON w.id=m.list_id "
            "WHERE m.ticker IN (?,?) ORDER BY w.id,m.ticker",
            tickers,
        )
    )
    legacy = _rows_as_dicts(
        conn.execute(
            "SELECT source_key,ticker,created_at,archived_at "
            "FROM universe_source_memberships WHERE source_key=? "
            "AND ticker IN (?,?) ORDER BY source_key,ticker",
            (_LEGACY_SOURCE_KEY, *tickers),
        )
    )
    placeholders = ",".join("?" for _ in EDITABLE_TAG_SOURCES)
    tags = _rows_as_dicts(
        conn.execute(
            "SELECT ticker,facet,value,source,created_at FROM ticker_tags "
            f"WHERE ticker IN (?,?) AND source IN ({placeholders}) "
            "ORDER BY ticker,facet,source,value",
            (*tickers, *EDITABLE_TAG_SOURCES),
        )
    )
    meta = _rows_as_dicts(
        conn.execute(
            "SELECT ticker,priority,hidden_at,updated_at FROM ticker_meta "
            "WHERE ticker IN (?,?) ORDER BY ticker",
            tickers,
        )
    )
    return {
        "editable_tags": tags,
        "legacy_config_seed": legacy,
        "portfolio_open_inputs": _portfolio_dependency_snapshot(
            conn,
            source_ticker=source_ticker,
            successor_ticker=successor_ticker,
        ),
        "ticker_meta": meta,
        "watchlists": watchlists,
    }


def _profile_dependency_sha256(
    conn: sqlite3.Connection,
    *,
    source_ticker: str,
    successor_ticker: str | None,
) -> str:
    snapshot = _profile_dependency_snapshot(
        conn,
        source_ticker=source_ticker,
        successor_ticker=successor_ticker,
    )
    return hashlib.sha256(_canonical_json(snapshot).encode("utf-8")).hexdigest()


def _effect_keys(preview: Mapping[str, object]) -> dict[str, list]:
    effects = preview.get("effects")
    if not isinstance(effects, Mapping):
        raise ValueError("preview_effects")
    watchlists = effects.get("watchlists")
    legacy = effects.get("legacy_config_seed")
    if not isinstance(watchlists, Mapping) or not isinstance(legacy, Mapping):
        raise ValueError("preview_membership_effects")

    watchlist_keys = {
        (int(item["list_id"]), str(item["ticker"]))
        for action in ("add", "archive", "reactivate")
        for item in watchlists.get(action, ())
    }
    legacy_keys = {
        (str(item["source_key"]), str(item["ticker"]))
        for action in ("add", "archive", "reactivate")
        for item in legacy.get(action, ())
    }
    tag_keys = {
        (
            str(item["ticker"]),
            str(item["facet"]),
            str(item["value"]),
            str(item["source"]),
        )
        for item in effects.get("editable_tags_to_copy", ())
    }
    priority = effects.get("priority")
    suppression = effects.get("suppression")
    if not isinstance(priority, Mapping) or not isinstance(suppression, Mapping):
        raise ValueError("preview_meta_effects")
    meta_keys: set[str] = set()
    if priority.get("write_successor") or suppression.get("unhide_successor"):
        successor = _ticker(preview.get("successor_ticker"))
        if successor is None:
            raise ValueError("preview_successor")
        meta_keys.add(successor)
    if suppression.get("hide_source"):
        source = _ticker(preview.get("source_ticker"))
        if source is None:
            raise ValueError("preview_source")
        meta_keys.add(source)
    return {
        "ticker_meta": sorted(meta_keys),
        "ticker_tags": [list(key) for key in sorted(tag_keys)],
        "universe_source_memberships": [list(key) for key in sorted(legacy_keys)],
        "watchlist_memberships": [list(key) for key in sorted(watchlist_keys)],
    }


def _affected_snapshot(
    conn: sqlite3.Connection,
    *,
    preview: Mapping[str, object] | None = None,
    keys: Mapping[str, Iterable] | None = None,
) -> dict:
    selected = _effect_keys(preview) if preview is not None else dict(keys or {})
    watchlist_keys = [tuple(value) for value in selected["watchlist_memberships"]]
    legacy_keys = [tuple(value) for value in selected["universe_source_memberships"]]
    tag_keys = [tuple(value) for value in selected["ticker_tags"]]
    meta_keys = [str(value) for value in selected["ticker_meta"]]

    watchlist_rows = []
    for list_id, ticker in watchlist_keys:
        cursor = conn.execute(
            "SELECT list_id,ticker,position,archived_at,created_at,updated_at "
            "FROM watchlist_memberships WHERE list_id=? AND ticker=?",
            (list_id, ticker),
        )
        watchlist_rows.extend(_rows_as_dicts(cursor))
    legacy_rows = []
    for source_key, ticker in legacy_keys:
        cursor = conn.execute(
            "SELECT source_key,ticker,created_at,archived_at "
            "FROM universe_source_memberships WHERE source_key=? AND ticker=?",
            (source_key, ticker),
        )
        legacy_rows.extend(_rows_as_dicts(cursor))
    tag_rows = []
    for ticker, facet, value, source in tag_keys:
        cursor = conn.execute(
            "SELECT ticker,facet,value,source,created_at FROM ticker_tags "
            "WHERE ticker=? AND facet=? AND value=? AND source=?",
            (ticker, facet, value, source),
        )
        tag_rows.extend(_rows_as_dicts(cursor))
    meta_rows = []
    for ticker in meta_keys:
        cursor = conn.execute(
            "SELECT ticker,priority,hidden_at,updated_at FROM ticker_meta WHERE ticker=?",
            (ticker,),
        )
        meta_rows.extend(_rows_as_dicts(cursor))
    return {
        "keys": {
            "ticker_meta": meta_keys,
            "ticker_tags": [list(value) for value in tag_keys],
            "universe_source_memberships": [list(value) for value in legacy_keys],
            "watchlist_memberships": [list(value) for value in watchlist_keys],
        },
        "rows": {
            "ticker_meta": meta_rows,
            "ticker_tags": tag_rows,
            "universe_source_memberships": legacy_rows,
            "watchlist_memberships": watchlist_rows,
        },
        "version": 1,
    }


def _affected_snapshot_sha256(snapshot: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(snapshot).encode("utf-8")).hexdigest()


def _restore_affected_snapshot(
    conn: sqlite3.Connection,
    snapshot: Mapping[str, object],
) -> None:
    if snapshot.get("version") != 1:
        raise ValueError("snapshot_version")
    keys = snapshot.get("keys")
    rows = snapshot.get("rows")
    if not isinstance(keys, Mapping) or not isinstance(rows, Mapping):
        raise ValueError("snapshot_shape")

    for list_id, ticker in keys["watchlist_memberships"]:
        conn.execute(
            "DELETE FROM watchlist_memberships WHERE list_id=? AND ticker=?",
            (list_id, ticker),
        )
    for source_key, ticker in keys["universe_source_memberships"]:
        conn.execute(
            "DELETE FROM universe_source_memberships WHERE source_key=? AND ticker=?",
            (source_key, ticker),
        )
    for ticker, facet, value, source in keys["ticker_tags"]:
        conn.execute(
            "DELETE FROM ticker_tags WHERE ticker=? AND facet=? AND value=? AND source=?",
            (ticker, facet, value, source),
        )
    for ticker in keys["ticker_meta"]:
        conn.execute("DELETE FROM ticker_meta WHERE ticker=?", (ticker,))

    conn.executemany(
        "INSERT INTO watchlist_memberships "
        "(list_id,ticker,position,archived_at,created_at,updated_at) "
        "VALUES (:list_id,:ticker,:position,:archived_at,:created_at,:updated_at)",
        rows["watchlist_memberships"],
    )
    conn.executemany(
        "INSERT INTO universe_source_memberships "
        "(source_key,ticker,created_at,archived_at) "
        "VALUES (:source_key,:ticker,:created_at,:archived_at)",
        rows["universe_source_memberships"],
    )
    conn.executemany(
        "INSERT INTO ticker_tags (ticker,facet,value,source,created_at) "
        "VALUES (:ticker,:facet,:value,:source,:created_at)",
        rows["ticker_tags"],
    )
    conn.executemany(
        "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
        "VALUES (:ticker,:priority,:hidden_at,:updated_at)",
        rows["ticker_meta"],
    )


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
        "profile_state_sha256": _profile_dependency_sha256(
            conn,
            source_ticker=source_ticker,
            successor_ticker=successor_ticker,
        ),
        "source_ticker": source_ticker,
        "successor_ticker": successor_ticker,
        "transition_kind": transition_kind,
    }
    payload["preview_sha256"] = profile_snapshot_sha256(payload)
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _assessment_authority_matches(
    conn: sqlite3.Connection,
    *,
    assessment_id: str,
    case_id: str,
    observation_fingerprint_sha256: str,
    evidence_set_sha256: str,
    assessment_fingerprint_sha256: str,
) -> bool:
    row = conn.execute(
        "SELECT case_id,status,observation_fingerprint_sha256,"
        "evidence_set_sha256 FROM security_lifecycle_assessments "
        "WHERE assessment_id=?",
        (assessment_id,),
    ).fetchone()
    if row is None:
        return False
    current = {
        "assessment_id": assessment_id,
        "observation_fingerprint_sha256": str(row[2]),
        "evidence_set_sha256": str(row[3]),
    }
    return (
        str(row[0]) == case_id
        and str(row[1]) == "accepted"
        and current["observation_fingerprint_sha256"]
        == observation_fingerprint_sha256
        and current["evidence_set_sha256"] == evidence_set_sha256
        and assessment_fingerprint(current) == assessment_fingerprint_sha256
    )


class TickerIdentityTransitionStore:
    """Durable approval state over a caller-owned profile connection."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        id_factory: Callable[[str], str] | None = None,
        clock: Callable[[], str] | None = None,
        _step_hook: Callable[[str], None] | None = None,
    ):
        verify_ticker_identity_connection(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        self.conn = conn
        self._id_factory = id_factory or _new_id
        self._clock = clock or _utc_now
        self._step_hook = _step_hook

    @staticmethod
    def _row(cursor: sqlite3.Cursor, row) -> dict:
        names = [str(item[0]) for item in cursor.description or ()]
        return {name: row[index] for index, name in enumerate(names)}

    def _get(self, transition_id: str) -> dict | None:
        cursor = self.conn.execute(
            "SELECT * FROM ticker_identity_transitions WHERE transition_id=?",
            (transition_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        item = self._row(cursor, row)
        item["proposal_ids"] = json.loads(str(item["proposal_ids_json"]))
        item["approved_preview"] = json.loads(str(item["approved_preview_json"]))
        return item

    def get(self, transition_id: str) -> dict:
        item = self._get(transition_id)
        if item is None:
            raise KeyError("transition_not_found")
        return item

    def _begin(self) -> None:
        if self.conn.in_transaction:
            raise RuntimeError("caller_transaction_open")
        self.conn.execute("BEGIN IMMEDIATE")

    @staticmethod
    def _dedupe_key(preview: Mapping[str, object]) -> str:
        parts = (
            "ticker-identity-transition-v1",
            str(preview.get("case_id") or ""),
            str(preview.get("assessment_id") or ""),
            str(preview.get("transition_kind") or ""),
        )
        return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_preview(
        preview: Mapping[str, object], approved_preview_sha256: str
    ) -> tuple[str, str]:
        supplied_digest = _sha256("preview_digest", approved_preview_sha256)
        embedded_digest = _sha256(
            "preview_digest", preview.get("preview_sha256")
        )
        if supplied_digest != embedded_digest or profile_snapshot_sha256(preview) != embedded_digest:
            raise ValueError("preview_digest")
        if preview.get("eligible") is not True or preview.get("block_reasons"):
            raise ValueError("preview_ineligible")
        kind = str(preview.get("transition_kind") or "")
        if kind not in {"symbol_continuation", "terminal_delisting"}:
            raise ValueError("preview_kind")
        execute_on = str(preview.get("execute_on") or "")
        try:
            if date.fromisoformat(execute_on).isoformat() != execute_on:
                raise ValueError
        except ValueError as exc:
            raise ValueError("preview_execute_on") from exc
        return kind, execute_on

    def approve(
        self,
        *,
        preview: Mapping[str, object],
        approved_preview_sha256: str,
    ) -> dict:
        kind, execute_on = self._validate_preview(
            preview, approved_preview_sha256
        )
        case_id = str(preview.get("case_id") or "")
        assessment_id = str(preview.get("assessment_id") or "")
        source_ticker = _ticker(preview.get("source_ticker"))
        successor_ticker = _ticker(preview.get("successor_ticker"))
        if not case_id or not assessment_id or source_ticker is None:
            raise ValueError("preview_authority")
        proposal_ids = sorted(
            {str(value) for value in preview.get("proposal_ids") or ()}
        )
        if not proposal_ids or any(not value or "\0" in value for value in proposal_ids):
            raise ValueError("preview_proposals")
        observation_fingerprint = _sha256(
            "observation_fingerprint_sha256",
            preview.get("observation_fingerprint_sha256"),
        )
        current_assessment_fingerprint = _sha256(
            "assessment_fingerprint_sha256",
            preview.get("assessment_fingerprint_sha256"),
        )
        evidence_fingerprint = _sha256(
            "evidence_set_sha256", preview.get("evidence_set_sha256")
        )
        digest = str(preview["preview_sha256"])
        preview_json = _canonical_json(dict(preview))
        proposal_ids_json = _canonical_json(proposal_ids)
        priority_resolution = (
            preview.get("effects", {}).get("priority", {}).get("resolution")
        )
        unhide_successor = bool(
            preview.get("effects", {})
            .get("suppression", {})
            .get("unhide_successor")
        )
        dedupe_key = self._dedupe_key(preview)
        now = self._clock()

        self._begin()
        try:
            if not _assessment_authority_matches(
                self.conn,
                assessment_id=assessment_id,
                case_id=case_id,
                observation_fingerprint_sha256=observation_fingerprint,
                evidence_set_sha256=evidence_fingerprint,
                assessment_fingerprint_sha256=current_assessment_fingerprint,
            ):
                raise ValueError("preview_changed")
            expected_profile_digest = _sha256(
                "profile_state_sha256", preview.get("profile_state_sha256")
            )
            observed_profile_digest = _profile_dependency_sha256(
                self.conn,
                source_ticker=source_ticker,
                successor_ticker=successor_ticker,
            )
            if expected_profile_digest != observed_profile_digest:
                raise ValueError("preview_changed")
            cursor = self.conn.execute(
                "SELECT transition_id,status,approved_preview_sha256 "
                "FROM ticker_identity_transitions WHERE transition_dedupe_key=?",
                (dedupe_key,),
            )
            row = cursor.fetchone()
            if row is not None:
                existing = self._row(cursor, row)
                transition_id = str(existing["transition_id"])
                if existing["approved_preview_sha256"] == digest:
                    self.conn.commit()
                    return self.get(transition_id)
                if existing["status"] not in {"approved", "needs_review"}:
                    raise ValueError("transition_not_reapprovable")
                self.conn.execute(
                    "UPDATE ticker_identity_transitions SET "
                    "proposal_ids_json=?,status='approved',source_ticker=?,"
                    "successor_ticker=?,execute_on=?,priority_resolution=?,"
                    "unhide_successor=?,approved_observation_fingerprint_sha256=?,"
                    "approved_assessment_fingerprint_sha256=?,"
                    "approved_preview_sha256=?,approved_preview_json=?,"
                    "approval_authority='attended_user',automation_policy_version=NULL,"
                    "rule_id=NULL,rule_version=NULL,decision_provenance_sha256=?,"
                    "approved_at=?,updated_at=? WHERE transition_id=?",
                    (
                        proposal_ids_json,
                        source_ticker,
                        successor_ticker,
                        execute_on,
                        priority_resolution,
                        int(unhide_successor),
                        observation_fingerprint,
                        current_assessment_fingerprint,
                        digest,
                        preview_json,
                        current_assessment_fingerprint,
                        now,
                        now,
                        transition_id,
                    ),
                )
            else:
                transition_id = self._id_factory("tit")
                self.conn.execute(
                    "INSERT INTO ticker_identity_transitions "
                    "(transition_id,case_id,assessment_id,proposal_ids_json,"
                    "transition_dedupe_key,kind,status,source_ticker,successor_ticker,"
                    "execute_on,priority_resolution,unhide_successor,"
                    "approved_observation_fingerprint_sha256,"
                    "approved_assessment_fingerprint_sha256,approved_preview_sha256,"
                    "approved_preview_json,before_snapshot_json,after_snapshot_sha256,"
                    "approved_at,updated_at,applied_at,cancelled_at,reversed_at,"
                    "approval_authority,automation_policy_version,rule_id,rule_version,"
                    "decision_provenance_sha256) "
                    "VALUES (?,?,?,?,?,?,'approved',?,?,?,?,?,?,?,?,?,NULL,NULL,?,?,"
                    "NULL,NULL,NULL,'attended_user',NULL,NULL,NULL,?)",
                    (
                        transition_id,
                        case_id,
                        assessment_id,
                        proposal_ids_json,
                        dedupe_key,
                        kind,
                        source_ticker,
                        successor_ticker,
                        execute_on,
                        priority_resolution,
                        int(unhide_successor),
                        observation_fingerprint,
                        current_assessment_fingerprint,
                        digest,
                        preview_json,
                        now,
                        now,
                        current_assessment_fingerprint,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get(transition_id)

    def list_due(self, *, on_date: str, limit: int) -> list[dict]:
        try:
            if date.fromisoformat(on_date).isoformat() != on_date:
                raise ValueError
        except ValueError as exc:
            raise ValueError("on_date") from exc
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit")
        cursor = self.conn.execute(
            "SELECT transition_id FROM ticker_identity_transitions "
            "WHERE status='approved' AND execute_on<=? "
            "ORDER BY execute_on,approved_at,transition_id LIMIT ?",
            (on_date, limit),
        )
        return [self.get(str(row[0])) for row in cursor.fetchall()]

    def cancel(self, transition_id: str) -> dict:
        now = self._clock()
        self._begin()
        try:
            item = self._get(transition_id)
            if item is None:
                raise KeyError("transition_not_found")
            if item["status"] == "cancelled":
                self.conn.commit()
                return item
            if item["status"] not in {"approved", "needs_review"}:
                raise ValueError("transition_not_cancellable")
            self.conn.execute(
                "UPDATE ticker_identity_transitions SET status='cancelled',"
                "cancelled_at=?,updated_at=? WHERE transition_id=?",
                (now, now, transition_id),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get(transition_id)

    def _step(self, name: str) -> None:
        if self._step_hook is not None:
            self._step_hook(name)

    def _insert_attempt(
        self,
        *,
        transition_id: str,
        trigger: str,
        status: str,
        block_reasons: Iterable[str],
        observed_preview_sha256: str | None,
        at: str,
    ) -> str:
        attempt_id = self._id_factory("tia")
        self.conn.execute(
            "INSERT INTO ticker_identity_transition_attempts "
            "(attempt_id,transition_id,trigger,status,block_reasons_json,"
            "observed_preview_sha256,attempted_at) VALUES (?,?,?,?,?,?,?)",
            (
                attempt_id,
                transition_id,
                trigger,
                status,
                _canonical_json(sorted(set(block_reasons))),
                observed_preview_sha256,
                at,
            ),
        )
        return attempt_id

    def _blocked_apply(
        self,
        *,
        transition_id: str,
        trigger: str,
        reasons: list[str],
        observed_preview_sha256: str | None,
        at: str,
        mark_needs_review: bool,
    ) -> dict:
        if mark_needs_review:
            self.conn.execute(
                "UPDATE ticker_identity_transitions SET status='needs_review',"
                "updated_at=? WHERE transition_id=?",
                (at, transition_id),
            )
        attempt_id = self._insert_attempt(
            transition_id=transition_id,
            trigger=trigger,
            status="blocked",
            block_reasons=reasons,
            observed_preview_sha256=observed_preview_sha256,
            at=at,
        )
        return {
            "attempt_id": attempt_id,
            "block_reasons": reasons,
            "status": "blocked",
        }

    def apply(
        self,
        transition_id: str,
        *,
        current_preview: Mapping[str, object] | None,
        expected_preview_sha256: str,
        trigger: str,
    ) -> dict:
        if trigger not in ATTEMPT_TRIGGERS:
            raise ValueError("trigger")
        expected_digest = _sha256(
            "preview_digest", expected_preview_sha256
        )
        now = self._clock()
        self._begin()
        try:
            transition = self._get(transition_id)
            if transition is None:
                raise KeyError("transition_not_found")
            if transition["approved_preview_sha256"] != expected_digest:
                raise ValueError("request_preview_changed")
            if transition["status"] == "applied":
                attempt_id = self._insert_attempt(
                    transition_id=transition_id,
                    trigger=trigger,
                    status="already_applied",
                    block_reasons=(),
                    observed_preview_sha256=str(
                        (current_preview or {}).get("preview_sha256") or ""
                    )
                    or None,
                    at=now,
                )
                self._step("attempt_receipt")
                self.conn.commit()
                return {
                    "attempt_id": attempt_id,
                    "block_reasons": [],
                    "status": "already_applied",
                    "transition": self.get(transition_id),
                }
            if transition["status"] != "approved":
                reason = f"transition_{transition['status']}"
                result = self._blocked_apply(
                    transition_id=transition_id,
                    trigger=trigger,
                    reasons=[reason],
                    observed_preview_sha256=str(
                        (current_preview or {}).get("preview_sha256") or ""
                    )
                    or None,
                    at=now,
                    mark_needs_review=False,
                )
                self.conn.commit()
                result["transition"] = self.get(transition_id)
                return result

            if current_preview is None:
                result = self._blocked_apply(
                    transition_id=transition_id,
                    trigger=trigger,
                    reasons=["preview_changed"],
                    observed_preview_sha256=None,
                    at=now,
                    mark_needs_review=True,
                )
                self.conn.commit()
                result["transition"] = self.get(transition_id)
                return result

            current_digest = _sha256(
                "preview_digest", current_preview.get("preview_sha256")
            )
            current_profile_digest = _sha256(
                "profile_state_sha256", current_preview.get("profile_state_sha256")
            )
            current_preview_valid = (
                profile_snapshot_sha256(current_preview) == current_digest
                and current_preview.get("eligible") is True
                and not current_preview.get("block_reasons")
            )
            source_ticker = _ticker(transition["source_ticker"])
            successor_ticker = _ticker(transition["successor_ticker"])
            if source_ticker is None:
                raise ValueError("transition_source")
            observed_profile_digest = _profile_dependency_sha256(
                self.conn,
                source_ticker=source_ticker,
                successor_ticker=successor_ticker,
            )
            assessment_current = _assessment_authority_matches(
                self.conn,
                assessment_id=str(transition["assessment_id"]),
                case_id=str(transition["case_id"]),
                observation_fingerprint_sha256=str(
                    transition["approved_observation_fingerprint_sha256"]
                ),
                evidence_set_sha256=str(
                    transition["approved_preview"]["evidence_set_sha256"]
                ),
                assessment_fingerprint_sha256=str(
                    transition["approved_assessment_fingerprint_sha256"]
                ),
            )
            if (
                not current_preview_valid
                or current_digest != transition["approved_preview_sha256"]
                or current_profile_digest != observed_profile_digest
                or not assessment_current
            ):
                result = self._blocked_apply(
                    transition_id=transition_id,
                    trigger=trigger,
                    reasons=["preview_changed"],
                    observed_preview_sha256=current_digest,
                    at=now,
                    mark_needs_review=True,
                )
                self.conn.commit()
                result["transition"] = self.get(transition_id)
                return result

            before_snapshot = _affected_snapshot(
                self.conn,
                preview=current_preview,
            )
            effects = current_preview["effects"]
            watchlists = effects["watchlists"]
            legacy = effects["legacy_config_seed"]

            for item in watchlists["add"]:
                self.conn.execute(
                    "INSERT INTO watchlist_memberships "
                    "(list_id,ticker,position,archived_at,created_at,updated_at) "
                    "VALUES (?,?,?,NULL,?,?)",
                    (
                        item["list_id"],
                        item["ticker"],
                        item["position"],
                        now,
                        now,
                    ),
                )
            for item in watchlists["reactivate"]:
                cursor = self.conn.execute(
                    "UPDATE watchlist_memberships SET archived_at=NULL,updated_at=? "
                    "WHERE list_id=? AND ticker=? AND archived_at IS NOT NULL",
                    (now, item["list_id"], item["ticker"]),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("preview_changed_during_apply")
            for item in legacy["add"]:
                self.conn.execute(
                    "INSERT INTO universe_source_memberships "
                    "(source_key,ticker,created_at,archived_at) VALUES (?,?,?,NULL)",
                    (item["source_key"], item["ticker"], now),
                )
            for item in legacy["reactivate"]:
                cursor = self.conn.execute(
                    "UPDATE universe_source_memberships SET archived_at=NULL "
                    "WHERE source_key=? AND ticker=? AND archived_at IS NOT NULL",
                    (item["source_key"], item["ticker"]),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("preview_changed_during_apply")
            self._step("successor_memberships")

            for item in effects["editable_tags_to_copy"]:
                self.conn.execute(
                    "INSERT OR IGNORE INTO ticker_tags "
                    "(ticker,facet,value,source,created_at) VALUES (?,?,?,?,?)",
                    (
                        item["ticker"],
                        item["facet"],
                        item["value"],
                        item["source"],
                        now,
                    ),
                )
            self._step("editable_tags")

            priority = effects["priority"]
            if priority["write_successor"]:
                if successor_ticker is None:
                    raise ValueError("transition_successor")
                self.conn.execute(
                    "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
                    "VALUES (?,?,NULL,?) ON CONFLICT(ticker) DO UPDATE SET "
                    "priority=excluded.priority,updated_at=excluded.updated_at",
                    (successor_ticker, priority["result_value"], now),
                )
            self._step("successor_priority")

            if transition["kind"] == "symbol_continuation":
                if successor_ticker is None:
                    raise ValueError("transition_successor")
                self.conn.execute(
                    "INSERT INTO ticker_identity_links "
                    "(link_id,transition_id,source_ticker,successor_ticker,"
                    "relationship,effective_date,created_at,reversed_at) "
                    "VALUES (?,?,?,?,?,?,?,NULL)",
                    (
                        self._id_factory("til"),
                        transition_id,
                        source_ticker,
                        successor_ticker,
                        "symbol_continuation",
                        transition["execute_on"],
                        now,
                    ),
                )
            self._step("identity_link")

            for item in watchlists["archive"]:
                cursor = self.conn.execute(
                    "UPDATE watchlist_memberships SET archived_at=?,updated_at=? "
                    "WHERE list_id=? AND ticker=? AND archived_at IS NULL",
                    (now, now, item["list_id"], item["ticker"]),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("preview_changed_during_apply")
            for item in legacy["archive"]:
                cursor = self.conn.execute(
                    "UPDATE universe_source_memberships SET archived_at=? "
                    "WHERE source_key=? AND ticker=? AND archived_at IS NULL",
                    (now, item["source_key"], item["ticker"]),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("preview_changed_during_apply")
            self._step("source_membership_archives")

            suppression = effects["suppression"]
            if suppression["unhide_successor"]:
                if successor_ticker is None:
                    raise ValueError("transition_successor")
                self.conn.execute(
                    "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
                    "VALUES (?,NULL,NULL,?) ON CONFLICT(ticker) DO UPDATE SET "
                    "hidden_at=NULL,updated_at=excluded.updated_at",
                    (successor_ticker, now),
                )
            if suppression["hide_source"]:
                self.conn.execute(
                    "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
                    "VALUES (?,NULL,?,?) ON CONFLICT(ticker) DO UPDATE SET "
                    "hidden_at=excluded.hidden_at,updated_at=excluded.updated_at",
                    (source_ticker, now, now),
                )
            self._step("suppression")

            after_snapshot = _affected_snapshot(
                self.conn,
                keys=before_snapshot["keys"],
            )
            after_digest = _affected_snapshot_sha256(after_snapshot)
            self.conn.execute(
                "UPDATE ticker_identity_transitions SET status='applied',"
                "before_snapshot_json=?,after_snapshot_sha256=?,updated_at=?,"
                "applied_at=? WHERE transition_id=?",
                (
                    _canonical_json(before_snapshot),
                    after_digest,
                    now,
                    now,
                    transition_id,
                ),
            )
            self._step("transition_receipt")

            attempt_id = self._insert_attempt(
                transition_id=transition_id,
                trigger=trigger,
                status="applied",
                block_reasons=(),
                observed_preview_sha256=current_digest,
                at=now,
            )
            self._step("attempt_receipt")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {
            "attempt_id": attempt_id,
            "block_reasons": [],
            "status": "applied",
            "transition": self.get(transition_id),
        }

    def reverse(self, transition_id: str, *, trigger: str) -> dict:
        if trigger not in ATTEMPT_TRIGGERS:
            raise ValueError("trigger")
        now = self._clock()
        self._begin()
        try:
            transition = self._get(transition_id)
            if transition is None:
                raise KeyError("transition_not_found")
            if transition["status"] != "applied":
                raise ValueError("transition_not_reversible")
            before_snapshot = json.loads(str(transition["before_snapshot_json"]))
            current_snapshot = _affected_snapshot(
                self.conn,
                keys=before_snapshot["keys"],
            )
            current_digest = _affected_snapshot_sha256(current_snapshot)
            blockers: list[str] = []
            if current_digest != transition["after_snapshot_sha256"]:
                blockers.append("reverse_state_changed")
            successor_ticker = _ticker(transition["successor_ticker"])
            if successor_ticker is not None:
                later = self.conn.execute(
                    "SELECT 1 FROM ticker_identity_links "
                    "WHERE source_ticker=? AND reversed_at IS NULL "
                    "AND transition_id<>? LIMIT 1",
                    (successor_ticker, transition_id),
                ).fetchone()
                if later is not None:
                    blockers.append("successor_has_later_transition")
            if blockers:
                attempt_id = self._insert_attempt(
                    transition_id=transition_id,
                    trigger=trigger,
                    status="blocked",
                    block_reasons=blockers,
                    observed_preview_sha256=transition["approved_preview_sha256"],
                    at=now,
                )
                self.conn.commit()
                return {
                    "attempt_id": attempt_id,
                    "block_reasons": sorted(blockers),
                    "status": "blocked",
                    "transition": self.get(transition_id),
                }

            _restore_affected_snapshot(self.conn, before_snapshot)
            restored = _affected_snapshot(
                self.conn,
                keys=before_snapshot["keys"],
            )
            if restored != before_snapshot:
                raise RuntimeError("reverse_restore_mismatch")
            self.conn.execute(
                "UPDATE ticker_identity_links SET reversed_at=? "
                "WHERE transition_id=? AND reversed_at IS NULL",
                (now, transition_id),
            )
            self.conn.execute(
                "UPDATE ticker_identity_transitions SET status='reversed',"
                "updated_at=?,reversed_at=? WHERE transition_id=?",
                (now, now, transition_id),
            )
            attempt_id = self._insert_attempt(
                transition_id=transition_id,
                trigger=trigger,
                status="reversed",
                block_reasons=(),
                observed_preview_sha256=transition["approved_preview_sha256"],
                at=now,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {
            "attempt_id": attempt_id,
            "block_reasons": [],
            "status": "reversed",
            "transition": self.get(transition_id),
        }

    def lineage_for_ticker(self, ticker: str) -> dict:
        normalized = _ticker(ticker)
        if normalized is None:
            raise ValueError("ticker")
        cursor = self.conn.execute(
            "SELECT l.link_id,l.transition_id,l.source_ticker,l.successor_ticker,"
            "l.relationship,l.effective_date,l.created_at,l.reversed_at,"
            "t.status AS transition_status "
            "FROM ticker_identity_links l "
            "JOIN ticker_identity_transitions t ON t.transition_id=l.transition_id "
            "WHERE l.source_ticker=? OR l.successor_ticker=? "
            "ORDER BY l.effective_date,l.created_at,l.link_id",
            (normalized, normalized),
        )
        items = _rows_as_dicts(cursor)
        return {
            "predecessors": [
                item for item in items if item["successor_ticker"] == normalized
            ],
            "successors": [
                item for item in items if item["source_ticker"] == normalized
            ],
            "ticker": normalized,
        }


__all__ = [
    "TickerIdentityTransitionStore",
    "TransitionOptions",
    "build_transition_preview",
    "profile_snapshot_sha256",
]
