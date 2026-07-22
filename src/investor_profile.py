"""Investor Profile + Assistant Stance store and pure helpers (Track A).

Design authority: docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md.
The profile personalizes SYNTHESIS/CHAT emphasis only — the generated context
block carries its own evidence-boundary guard and must never be passed into
gather_evidence() or any deterministic evidence collector (ProductSpec §2).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PRESETS = ("growth", "value", "momentum", "income", "event_driven", "balanced", "custom")
STANCES = (
    "off",
    "neutral",
    "aligned",
    "complementary",
    "strict_risk_control",
    "valuation_rationalist",
    "growth_opportunity",
)
SKILL_MODES = ("off", "suggest_only")  # auto_with_trace is Track C, not Track A.
RISK_MISMATCHES = ("none", "appetite_above_capacity", "capacity_above_appetite", "unclear")
HOLDING_HORIZONS = ("intraday", "days_weeks", "months", "multi_year", "mixed")

# Difference in 1-10 scores at or below this is treated as consistent.
_MISMATCH_TOLERANCE = 1

_STANCE_INSTRUCTIONS = {
    "neutral": "Analyze objectively; do not materially personalize conclusions.",
    "aligned": (
        "Frame the analysis in the user's preferred style and edge; still state material "
        "risks and the counter-thesis plainly."
    ),
    "complementary": (
        "Counterbalance the user's likely blind spots and behavioral flags. Preserve the "
        "upside analysis, but explicitly test valuation, downside, concentration, and "
        "invalidation."
    ),
    "strict_risk_control": (
        "Prioritize downside scenarios, concentration, liquidity, and invalidation "
        "conditions before any upside case."
    ),
    "valuation_rationalist": (
        "Emphasize intrinsic value, peer valuation, margin of safety, and the explicit "
        "assumptions behind any price view."
    ),
    "growth_opportunity": (
        "Emphasize catalysts, growth durability, TAM, execution quality, and optionality; "
        "keep risk sections intact."
    ),
}

_EVIDENCE_GUARD = (
    "Emphasis only; do not exclude, filter, or reweight evidence, and always retain "
    "counter-thesis analysis. The profile is a user-confirmed working model, not an "
    "objective diagnosis."
)


@dataclass
class InvestorProfile:
    enabled: bool
    primary_preset: str
    risk_appetite: Optional[int]
    risk_capacity: Optional[int]
    risk_mismatch: str
    holding_horizon: str
    drawdown_tolerance_pct: Optional[float]
    concentration_limit_pct: Optional[float]
    preferred_edge: list[str]
    avoidances: list[str]
    behavioral_flags: list[str]
    freeform_notes: str
    default_stance: str
    skill_mode: str
    last_reviewed_at: Optional[str]
    updated_at: Optional[str]


def default_profile() -> InvestorProfile:
    """Return the disabled Growth-Investor default profile."""
    return InvestorProfile(
        enabled=False,
        primary_preset="growth",
        risk_appetite=None,
        risk_capacity=None,
        risk_mismatch="unclear",
        holding_horizon="mixed",
        drawdown_tolerance_pct=None,
        concentration_limit_pct=None,
        preferred_edge=[],
        avoidances=[],
        behavioral_flags=[],
        freeform_notes="",
        default_stance="complementary",
        skill_mode="off",
        last_reviewed_at=None,
        updated_at=None,
    )


def derive_risk_mismatch(risk_appetite: Optional[int], risk_capacity: Optional[int]) -> str:
    if risk_appetite is None or risk_capacity is None:
        return "unclear"
    if risk_appetite - risk_capacity > _MISMATCH_TOLERANCE:
        return "appetite_above_capacity"
    if risk_capacity - risk_appetite > _MISMATCH_TOLERANCE:
        return "capacity_above_appetite"
    return "none"


def _validate_choice(value: str, allowed: tuple, field: str) -> str:
    if value not in allowed:
        raise ValueError(f"invalid {field}: {value!r} (allowed: {', '.join(allowed)})")
    return value


def _validate_risk_score(value, field: str) -> Optional[int]:
    if value is None:
        return None
    score = int(value)
    if not 1 <= score <= 10:
        raise ValueError(f"invalid {field}: {value!r} (must be 1-10)")
    return score


def _validate_pct(value, field: str) -> Optional[float]:
    if value in (None, ""):
        return None
    pct = float(value)
    if not 0 < pct <= 100:
        raise ValueError(f"invalid {field}: {value!r} (must be within (0, 100])")
    return pct


def _normalize_str_list(value, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"invalid {field}: expected a list of strings")
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def normalize_profile_payload(
    payload: dict, *, existing: Optional[InvestorProfile] = None
) -> InvestorProfile:
    """Validate, clamp/normalize lists, and derive risk_mismatch."""
    base = existing if existing is not None else default_profile()
    merged = asdict(base)
    for key in payload:
        if key == "risk_mismatch":
            continue  # always derived, never client-supplied
        if key not in merged:
            raise ValueError(f"unknown profile field: {key}")
        merged[key] = payload[key]

    profile = InvestorProfile(
        enabled=bool(merged["enabled"]),
        primary_preset=_validate_choice(str(merged["primary_preset"]), PRESETS, "primary_preset"),
        risk_appetite=_validate_risk_score(merged["risk_appetite"], "risk_appetite"),
        risk_capacity=_validate_risk_score(merged["risk_capacity"], "risk_capacity"),
        risk_mismatch="unclear",  # replaced below
        holding_horizon=_validate_choice(
            str(merged["holding_horizon"]), HOLDING_HORIZONS, "holding_horizon"
        ),
        drawdown_tolerance_pct=_validate_pct(merged["drawdown_tolerance_pct"], "drawdown_tolerance_pct"),
        concentration_limit_pct=_validate_pct(
            merged["concentration_limit_pct"], "concentration_limit_pct"
        ),
        preferred_edge=_normalize_str_list(merged["preferred_edge"], "preferred_edge"),
        avoidances=_normalize_str_list(merged["avoidances"], "avoidances"),
        behavioral_flags=_normalize_str_list(merged["behavioral_flags"], "behavioral_flags"),
        freeform_notes=str(merged["freeform_notes"] or ""),
        default_stance=_validate_choice(str(merged["default_stance"]), STANCES, "default_stance"),
        skill_mode=_validate_choice(str(merged["skill_mode"]), SKILL_MODES, "skill_mode"),
        last_reviewed_at=merged["last_reviewed_at"],
        updated_at=merged["updated_at"],
    )
    return replace(
        profile, risk_mismatch=derive_risk_mismatch(profile.risk_appetite, profile.risk_capacity)
    )


def effective_stance(profile: InvestorProfile, override: Optional[str] = None) -> str:
    """Return 'off' when disabled, else a validated override/default stance."""
    if not profile.enabled:
        return "off"
    stance = profile.default_stance if override is None else override
    return _validate_choice(str(stance), STANCES, "assistant_stance")


def personalization_trace(profile: InvestorProfile, override: Optional[str] = None) -> dict:
    """Return the persisted run-trace dict used by card/research records."""
    stance = effective_stance(profile, override)
    active = profile.enabled and stance != "off"
    return {
        "profile_active": active,
        "assistant_stance": stance,
        "skill_mode": profile.skill_mode if active else "off",
        "suggested_skills": [],
        "applied_skills": [],
    }


def build_personalization_context(profile: InvestorProfile, override: Optional[str] = None) -> str:
    """Return the compact prompt block, or '' when disabled/effective stance off.

    The block goes into synthesis/chat context ONLY — never into
    gather_evidence() (ProductSpec §2 evidence boundary).
    """
    stance = effective_stance(profile, override)
    if not profile.enabled or stance == "off":
        return ""

    lines = ["[Investor Profile]", f"Primary preset: {profile.primary_preset}"]
    if profile.risk_appetite is not None:
        lines.append(f"Risk appetite: {profile.risk_appetite}/10")
    if profile.risk_capacity is not None:
        lines.append(f"Risk capacity: {profile.risk_capacity}/10")
    lines.append(f"Risk mismatch: {profile.risk_mismatch}")
    lines.append(f"Holding horizon: {profile.holding_horizon}")
    if profile.drawdown_tolerance_pct is not None:
        lines.append(f"Drawdown tolerance: {profile.drawdown_tolerance_pct:g}%")
    if profile.concentration_limit_pct is not None:
        lines.append(f"Concentration limit: {profile.concentration_limit_pct:g}%")
    if profile.preferred_edge:
        lines.append("Preferred edge: " + ", ".join(profile.preferred_edge))
    if profile.avoidances:
        lines.append("Avoidances: " + ", ".join(profile.avoidances))
    if profile.behavioral_flags:
        lines.append("Behavioral flags: " + ", ".join(profile.behavioral_flags))

    lines += [
        "",
        "[Assistant Stance]",
        f"Mode: {stance}",
        f"Instruction: {_STANCE_INSTRUCTIONS[stance]}",
        "",
        "[Boundary]",
        _EVIDENCE_GUARD,
        "",
        "[Skill Mode]",
        profile.skill_mode,
    ]
    return "\n".join(lines)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS investor_profile (
    id                       TEXT PRIMARY KEY CHECK (id = 'default'),
    enabled                  INTEGER NOT NULL DEFAULT 0,
    primary_preset            TEXT NOT NULL DEFAULT 'growth',
    risk_appetite             INTEGER,
    risk_capacity             INTEGER,
    risk_mismatch             TEXT NOT NULL DEFAULT 'unclear',
    holding_horizon           TEXT NOT NULL DEFAULT 'mixed',
    drawdown_tolerance_pct    REAL,
    concentration_limit_pct   REAL,
    preferred_edge_json       TEXT NOT NULL DEFAULT '[]',
    avoidances_json           TEXT NOT NULL DEFAULT '[]',
    behavioral_flags_json     TEXT NOT NULL DEFAULT '[]',
    freeform_notes            TEXT NOT NULL DEFAULT '',
    default_stance            TEXT NOT NULL DEFAULT 'complementary',
    skill_mode                TEXT NOT NULL DEFAULT 'off',
    last_reviewed_at          TEXT,
    updated_at                TEXT NOT NULL
);
"""


def _read_profile_on_connection(conn: sqlite3.Connection) -> InvestorProfile:
    """Read the singleton profile without owning connection or transaction state."""
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name = ? COLLATE NOCASE",
        ("investor_profile",),
    ).fetchone()
    if table_exists is None:
        return default_profile()
    row = conn.execute(
        "SELECT enabled, primary_preset, risk_appetite, risk_capacity, "
        "risk_mismatch, holding_horizon, drawdown_tolerance_pct, "
        "concentration_limit_pct, preferred_edge_json, avoidances_json, "
        "behavioral_flags_json, freeform_notes, default_stance, skill_mode, "
        "last_reviewed_at, updated_at FROM investor_profile WHERE id = 'default'"
    ).fetchone()
    if row is None:
        return default_profile()
    return InvestorProfile(
        enabled=bool(row[0]),
        primary_preset=row[1],
        risk_appetite=row[2],
        risk_capacity=row[3],
        risk_mismatch=row[4],
        holding_horizon=row[5],
        drawdown_tolerance_pct=row[6],
        concentration_limit_pct=row[7],
        preferred_edge=json.loads(row[8]),
        avoidances=json.loads(row[9]),
        behavioral_flags=json.loads(row[10]),
        freeform_notes=row[11],
        default_stance=row[12],
        skill_mode=row[13],
        last_reviewed_at=row[14],
        updated_at=row[15],
    )


def _write_profile_on_connection(
    conn: sqlite3.Connection,
    profile: InvestorProfile,
) -> None:
    """Write an already-normalized profile on a caller-owned transaction."""
    conn.execute(
        """
        INSERT OR REPLACE INTO investor_profile (
            id, enabled, primary_preset, risk_appetite, risk_capacity,
            risk_mismatch, holding_horizon, drawdown_tolerance_pct,
            concentration_limit_pct, preferred_edge_json, avoidances_json,
            behavioral_flags_json, freeform_notes, default_stance,
            skill_mode, last_reviewed_at, updated_at
        ) VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(profile.enabled),
            profile.primary_preset,
            profile.risk_appetite,
            profile.risk_capacity,
            profile.risk_mismatch,
            profile.holding_horizon,
            profile.drawdown_tolerance_pct,
            profile.concentration_limit_pct,
            json.dumps(profile.preferred_edge, ensure_ascii=False),
            json.dumps(profile.avoidances, ensure_ascii=False),
            json.dumps(profile.behavioral_flags, ensure_ascii=False),
            profile.freeform_notes,
            profile.default_stance,
            profile.skill_mode,
            profile.last_reviewed_at,
            profile.updated_at,
        ),
    )


class InvestorProfileStore:
    """Singleton investor profile persisted in local profile_state.db."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._write_lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass  # WAL is best-effort; busy_timeout below is the real guard
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def get(self) -> InvestorProfile:
        with self._connect() as conn:
            return _read_profile_on_connection(conn)

    def draft(self, payload: dict) -> InvestorProfile:
        """Normalize payload without writing it."""
        return normalize_profile_payload(payload, existing=self.get())

    def save(self, payload: dict) -> InvestorProfile:
        """Normalize and upsert the singleton profile."""
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                current = _read_profile_on_connection(conn)
                profile = normalize_profile_payload(payload, existing=current)
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                profile = replace(profile, last_reviewed_at=now, updated_at=now)
                _write_profile_on_connection(conn, profile)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
        return profile
