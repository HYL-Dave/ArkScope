# Investor Profile Calibration Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Track A.5: an opt-in Investor Profile calibration chat that stores raw calibration dialogue as a long-lived journal, produces inert structured proposals, and updates the active profile only after explicit user approval.

**Architecture:** Use a dedicated calibration loop, not `research_threads` / `research_runs`, for v1. The dedicated path gives up server-owned research streaming/cancel/replay reuse for now, but it preserves the load-bearing isolation: calibration data is profile state, not research history; calibration has no market/news/tools; raw calibration text never enters research/card prompts.

**Tech Stack:** FastAPI handler-direct routes, SQLite `profile_state.db`, Pydantic DTOs, React/Vite Settings UI, Vitest + pytest. Live LLM responder is isolated behind a small injectable seam and implemented after the store/routes/UI are proven with fakes.

---

## Design Decisions Locked By This Plan

1. **Execution path:** v1 uses a dedicated non-streaming calibration loop. Do not reuse `research_run_manager` in this slice. Rationale: research run manager is intentionally coupled to `research_threads`, event replay, tool traces, and research hydration; calibration must be impossible to leak into those surfaces.
2. **Session lifecycle:** at most one active calibration session. Starting a new session while one is active returns `409 calibration_session_active` unless the client explicitly passes `supersede_active=true`, in which case the old active session becomes `superseded` and a new active session is created.
3. **Proposal authority:** proposals may include `default_stance`; proposals may not include `risk_mismatch`. The server derives `risk_mismatch` from proposed `risk_appetite` and `risk_capacity` by reusing Track A normalization.
4. **Approval path:** approving a proposal is the only calibration action that mutates `investor_profile`; it must call `require_profile_state_write` and then use the existing `InvestorProfileStore.save()` path.
5. **Read-side boundary:** research/card prompt builders keep reading only `build_personalization_context(profile)`. Raw calibration messages and proposal rationales are never prompt inputs.
6. **Tool boundary:** calibration responder gets no tool registry, no DAL, no market/news/web/code/write capability. Live responder may call an LLM, but only with prompt text and prior calibration messages.

## Files

- Create `src/investor_profile_calibration.py`
  - Owns calibration schema, dataclasses, proposal normalization, and persistence.
- Create `src/investor_profile_calibration_agent.py`
  - Owns calibration prompt, model-output parser, `CalibrationResponder` protocol, and live responder seam.
- Create `src/api/routes/investor_profile_calibration.py`
  - Owns `/profile/investor/calibration/*` routes.
- Modify `src/api/dependencies.py`
  - Add `get_investor_calibration_store()`.
- Modify `src/api/app.py`
  - Include the calibration router.
- Modify `apps/arkscope-web/src/api.ts`
  - Add calibration DTOs and API helpers.
- Modify `apps/arkscope-web/src/InvestorProfilePanel.tsx`
  - Add the calibration chat panel and proposal review affordance.
- Modify `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
  - Cover calibration chat and proposal prefill.
- Create `tests/test_investor_profile_calibration.py`
  - Store + parser tests.
- Create `tests/test_investor_profile_calibration_routes.py`
  - Handler-direct route tests.
- Modify `docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md`
  - Mark Track A.5 implemented after live verification.
- Modify `docs/design/PROJECT_PRIORITY_MAP.md`
  - Add closeout entry after merge.

## Stop-Loss Triggers

Stop and report before continuing if any of these happen:

- Any implementation needs to write calibration data into `research_threads`, `research_messages`, `research_runs`, or `research_run_events`.
- Any calibration code imports `src.tools.registry`, `src.tools.data_access`, market/news routes, or DAL helpers outside tests.
- Any route tries to approve a proposal without the existing `InvestorProfileStore.save()` normalization path.
- Any route injects raw calibration message text into `build_personalization_context`, `run_query_stream`, card synthesis, or research run execution.
- Live responder support for a provider requires enabling tools or MCP to make the provider call work.
- Frontend implementation requires changing Research or AICard prompt behavior to display calibration.

---

## Task 1: Calibration Store And Proposal Contract

**Files:**
- Create: `src/investor_profile_calibration.py`
- Test: `tests/test_investor_profile_calibration.py`

- [ ] **Step 1: Write failing store tests**

Create `tests/test_investor_profile_calibration.py`:

```python
"""Track A.5: Investor Profile calibration journal + proposal store."""

import pytest

from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import (
    CalibrationStore,
    normalize_proposal_payload,
)


def test_start_session_enforces_single_active_and_explicit_supersede(tmp_path):
    store = CalibrationStore(tmp_path / "profile_state.db")
    first = store.start_session()
    assert first.status == "active"
    assert store.get_active_session().id == first.id

    with pytest.raises(ValueError, match="calibration_session_active"):
        store.start_session()

    second = store.start_session(supersede_active=True)
    assert second.status == "active"
    assert store.get_session(first.id).status == "superseded"
    assert store.get_active_session().id == second.id
    assert [s.id for s in store.list_sessions()] == [second.id, first.id]


def test_messages_are_append_only_and_role_checked(tmp_path):
    store = CalibrationStore(tmp_path / "profile_state.db")
    sess = store.start_session()
    m1 = store.append_message(sess.id, role="user", content="I chase AI stocks.")
    m2 = store.append_message(sess.id, role="assistant", content="What drawdown would make you sell?")

    assert [m.content for m in store.list_messages(sess.id)] == [m1.content, m2.content]
    with pytest.raises(ValueError, match="invalid calibration role"):
        store.append_message(sess.id, role="system", content="hidden")
    with pytest.raises(ValueError, match="content is required"):
        store.append_message(sess.id, role="user", content="   ")


def test_create_proposal_is_inert_and_server_derives_mismatch(tmp_path):
    db = tmp_path / "profile_state.db"
    cstore = CalibrationStore(db)
    pstore = InvestorProfileStore(db)
    sess = cstore.start_session()

    proposal = cstore.create_proposal(
        session_id=sess.id,
        profile_patch={"enabled": True, "risk_appetite": 9, "risk_capacity": 4, "default_stance": "complementary"},
        rationales={"risk_capacity": "User said a 10% drawdown would likely trigger selling."},
    )

    assert proposal.status == "draft"
    assert proposal.profile_patch["risk_mismatch"] == "appetite_above_capacity"
    assert "risk_mismatch" not in proposal.raw_profile_patch
    assert pstore.get().enabled is False


def test_reject_and_approve_proposal_status_are_terminal(tmp_path):
    store = CalibrationStore(tmp_path / "profile_state.db")
    sess = store.start_session()
    proposal = store.create_proposal(
        session_id=sess.id,
        profile_patch={"enabled": True, "risk_appetite": 8, "risk_capacity": 4},
        rationales={},
    )

    rejected = store.reject_proposal(proposal.id)
    assert rejected.status == "rejected"
    with pytest.raises(ValueError, match="proposal_not_draft"):
        store.mark_proposal_approved(proposal.id, changed_fields=["risk_appetite"])


def test_normalize_proposal_rejects_agent_supplied_mismatch():
    with pytest.raises(ValueError, match="risk_mismatch"):
        normalize_proposal_payload({"risk_mismatch": "none"}, rationales={})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_investor_profile_calibration.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.investor_profile_calibration'`.

- [ ] **Step 3: Implement the store**

Create `src/investor_profile_calibration.py` with:

```python
"""Investor Profile calibration journal and proposal store (Track A.5).

Raw calibration dialogue is profile-state journal data. It must never be used as
research/card prompt input; only approved structured investor_profile rows may
shape research synthesis.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.investor_profile import normalize_profile_payload

SESSION_STATUSES = ("active", "closed", "superseded")
MESSAGE_ROLES = ("user", "assistant")
PROPOSAL_STATUSES = ("draft", "approved", "rejected")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(raw: str | None, fallback):
    if not raw:
        return fallback
    data = json.loads(raw)
    return data if data is not None else fallback


@dataclass
class CalibrationSession:
    id: str
    status: str
    created_at: str
    updated_at: str
    closed_at: Optional[str]


@dataclass
class CalibrationMessage:
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


@dataclass
class CalibrationProposal:
    id: str
    session_id: str
    status: str
    profile_patch: dict
    raw_profile_patch: dict
    rationales: dict
    changed_fields: list[str]
    created_at: str
    approved_at: Optional[str]
    rejected_at: Optional[str]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS investor_profile_calibration_sessions (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_calibration_one_active
ON investor_profile_calibration_sessions(status)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS investor_profile_calibration_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calibration_messages_session
ON investor_profile_calibration_messages(session_id, created_at ASC);

CREATE TABLE IF NOT EXISTS investor_profile_calibration_proposals (
    id                     TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    status                  TEXT NOT NULL,
    profile_patch_json      TEXT NOT NULL,
    raw_profile_patch_json  TEXT NOT NULL,
    rationales_json         TEXT NOT NULL,
    changed_fields_json     TEXT NOT NULL DEFAULT '[]',
    created_at              TEXT NOT NULL,
    approved_at             TEXT,
    rejected_at             TEXT
);
CREATE INDEX IF NOT EXISTS idx_calibration_proposals_session
ON investor_profile_calibration_proposals(session_id, created_at DESC);
"""


def normalize_proposal_payload(profile_patch: dict, rationales: dict | None) -> tuple[dict, dict, dict]:
    if "risk_mismatch" in profile_patch:
        raise ValueError("risk_mismatch is server-derived and cannot be proposed")
    normalized = normalize_profile_payload(profile_patch)
    raw = dict(profile_patch)
    patch = {
        "enabled": normalized.enabled,
        "primary_preset": normalized.primary_preset,
        "risk_appetite": normalized.risk_appetite,
        "risk_capacity": normalized.risk_capacity,
        "risk_mismatch": normalized.risk_mismatch,
        "holding_horizon": normalized.holding_horizon,
        "drawdown_tolerance_pct": normalized.drawdown_tolerance_pct,
        "concentration_limit_pct": normalized.concentration_limit_pct,
        "preferred_edge": normalized.preferred_edge,
        "avoidances": normalized.avoidances,
        "behavioral_flags": normalized.behavioral_flags,
        "freeform_notes": normalized.freeform_notes,
        "default_stance": normalized.default_stance,
        "skill_mode": normalized.skill_mode,
    }
    return patch, raw, dict(rationales or {})


class CalibrationStore:
    """SQLite store for Investor Profile calibration sessions/messages/proposals."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(_SCHEMA)
            conn.commit()

    @staticmethod
    def _session(row: sqlite3.Row) -> CalibrationSession:
        return CalibrationSession(row["id"], row["status"], row["created_at"], row["updated_at"], row["closed_at"])

    @staticmethod
    def _message(row: sqlite3.Row) -> CalibrationMessage:
        return CalibrationMessage(row["id"], row["session_id"], row["role"], row["content"], row["created_at"])

    @staticmethod
    def _proposal(row: sqlite3.Row) -> CalibrationProposal:
        return CalibrationProposal(
            id=row["id"],
            session_id=row["session_id"],
            status=row["status"],
            profile_patch=_loads(row["profile_patch_json"], {}),
            raw_profile_patch=_loads(row["raw_profile_patch_json"], {}),
            rationales=_loads(row["rationales_json"], {}),
            changed_fields=_loads(row["changed_fields_json"], []),
            created_at=row["created_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
        )

    def get_active_session(self) -> Optional[CalibrationSession]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions WHERE status = 'active'"
            ).fetchone()
        return self._session(row) if row else None

    def get_session(self, session_id: str) -> Optional[CalibrationSession]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session(row) if row else None

    def list_sessions(self, *, limit: int = 20) -> list[CalibrationSession]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions "
                "ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._session(r) for r in rows]

    def start_session(self, *, supersede_active: bool = False) -> CalibrationSession:
        ts = _now()
        with self._write_lock, self._connect() as conn:
            active = conn.execute(
                "SELECT id FROM investor_profile_calibration_sessions WHERE status = 'active'"
            ).fetchone()
            if active and not supersede_active:
                raise ValueError("calibration_session_active")
            if active:
                conn.execute(
                    "UPDATE investor_profile_calibration_sessions SET status='superseded', "
                    "updated_at=?, closed_at=? WHERE id=?",
                    (ts, ts, active["id"]),
                )
            sid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO investor_profile_calibration_sessions "
                "(id, status, created_at, updated_at) VALUES (?, 'active', ?, ?)",
                (sid, ts, ts),
            )
            conn.commit()
        got = self.get_session(sid)
        assert got is not None
        return got

    def close_session(self, session_id: str) -> CalibrationSession:
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE investor_profile_calibration_sessions SET status='closed', "
                "updated_at=?, closed_at=? WHERE id=? AND status='active'",
                (ts, ts, session_id),
            )
            conn.commit()
        got = self.get_session(session_id)
        if got is None:
            raise ValueError("calibration_session_not_found")
        return got

    def append_message(self, session_id: str, *, role: str, content: str) -> CalibrationMessage:
        if role not in MESSAGE_ROLES:
            raise ValueError(f"invalid calibration role: {role}")
        text = (content or "").strip()
        if not text:
            raise ValueError("content is required")
        sess = self.get_session(session_id)
        if sess is None:
            raise ValueError("calibration_session_not_found")
        if sess.status != "active":
            raise ValueError("calibration_session_not_active")
        ts, mid = _now(), str(uuid.uuid4())
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO investor_profile_calibration_messages "
                "(id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (mid, session_id, role, text, ts),
            )
            conn.execute(
                "UPDATE investor_profile_calibration_sessions SET updated_at=? WHERE id=?",
                (ts, session_id),
            )
            conn.commit()
        return self.list_messages(session_id)[-1]

    def list_messages(self, session_id: str) -> list[CalibrationMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_messages WHERE session_id=? "
                "ORDER BY created_at ASC, id ASC",
                (session_id,),
            ).fetchall()
        return [self._message(r) for r in rows]

    def create_proposal(self, *, session_id: str, profile_patch: dict, rationales: dict | None) -> CalibrationProposal:
        patch, raw, rats = normalize_proposal_payload(profile_patch, rationales)
        ts, pid = _now(), str(uuid.uuid4())
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO investor_profile_calibration_proposals "
                "(id, session_id, status, profile_patch_json, raw_profile_patch_json, "
                "rationales_json, created_at) VALUES (?, ?, 'draft', ?, ?, ?, ?)",
                (pid, session_id, json.dumps(patch, ensure_ascii=False),
                 json.dumps(raw, ensure_ascii=False), json.dumps(rats, ensure_ascii=False), ts),
            )
            conn.commit()
        got = self.get_proposal(pid)
        assert got is not None
        return got

    def get_proposal(self, proposal_id: str) -> Optional[CalibrationProposal]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
        return self._proposal(row) if row else None

    def latest_proposal(self, session_id: str) -> Optional[CalibrationProposal]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_proposals WHERE session_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._proposal(row) if row else None

    def mark_proposal_approved(self, proposal_id: str, *, changed_fields: list[str]) -> CalibrationProposal:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            raise ValueError("proposal_not_found")
        if proposal.status != "draft":
            raise ValueError("proposal_not_draft")
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE investor_profile_calibration_proposals SET status='approved', "
                "approved_at=?, changed_fields_json=? WHERE id=? AND status='draft'",
                (ts, json.dumps(sorted(changed_fields)), proposal_id),
            )
            conn.commit()
        got = self.get_proposal(proposal_id)
        assert got is not None
        return got

    def reject_proposal(self, proposal_id: str) -> CalibrationProposal:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            raise ValueError("proposal_not_found")
        if proposal.status != "draft":
            raise ValueError("proposal_not_draft")
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE investor_profile_calibration_proposals SET status='rejected', "
                "rejected_at=? WHERE id=? AND status='draft'",
                (ts, proposal_id),
            )
            conn.commit()
        got = self.get_proposal(proposal_id)
        assert got is not None
        return got
```

- [ ] **Step 4: Run store tests**

Run:

```bash
pytest tests/test_investor_profile_calibration.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/investor_profile_calibration.py tests/test_investor_profile_calibration.py
git commit -m "feat: add investor profile calibration store"
```

---

## Task 2: Calibration Agent Parser And Fakeable Responder Seam

**Files:**
- Create: `src/investor_profile_calibration_agent.py`
- Modify: `tests/test_investor_profile_calibration.py`

- [ ] **Step 1: Add failing parser/responder tests**

Append to `tests/test_investor_profile_calibration.py`:

```python
from src.investor_profile_calibration_agent import (
    CalibrationAgentResult,
    CALIBRATION_SYSTEM_PROMPT,
    parse_calibration_model_json,
)


def test_calibration_prompt_forbids_research_advice_and_tools():
    p = CALIBRATION_SYSTEM_PROMPT.lower()
    assert "do not give investment advice" in p
    assert "do not recommend securities" in p
    assert "no market data" in p
    assert "profile proposal" in p


def test_parse_calibration_json_followup_without_proposal():
    result = parse_calibration_model_json(
        '{"assistant_message":"What drawdown would make you sell?","proposal":null}'
    )
    assert result == CalibrationAgentResult(
        assistant_message="What drawdown would make you sell?",
        profile_patch=None,
        rationales={},
    )


def test_parse_calibration_json_with_proposal_rejects_direct_mismatch():
    with pytest.raises(ValueError, match="risk_mismatch"):
        parse_calibration_model_json(
            '{"assistant_message":"Draft ready","proposal":{"profile_patch":{"risk_mismatch":"none"},"rationales":{}}}'
        )


def test_parse_calibration_json_with_default_stance_proposal():
    result = parse_calibration_model_json(
        '{"assistant_message":"Draft ready","proposal":{"profile_patch":'
        '{"enabled":true,"risk_appetite":8,"risk_capacity":4,"default_stance":"complementary"},'
        '"rationales":{"default_stance":"User asked to be challenged."}}}'
    )
    assert result.profile_patch["default_stance"] == "complementary"
    assert result.rationales["default_stance"] == "User asked to be challenged."
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_investor_profile_calibration.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.investor_profile_calibration_agent'`.

- [ ] **Step 3: Implement parser and seam**

Create `src/investor_profile_calibration_agent.py`:

```python
"""Calibration assistant prompt, parser, and responder seam (Track A.5).

This module has no DAL/tool imports by design. It only turns calibration dialogue
into assistant text plus an optional structured profile proposal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Protocol

from src.investor_profile_calibration import normalize_proposal_payload

CALIBRATION_SYSTEM_PROMPT = """You are ArkScope's Investor Profile calibration assistant.

Purpose:
- Ask targeted questions to understand investment style, risk appetite, real risk capacity,
  drawdown behavior, concentration limits, holding horizon, behavioral patterns, and desired
  assistant behavior.
- Produce a profile proposal only when enough information exists.

Hard boundaries:
- Do not give investment advice.
- Do not recommend securities.
- No market data, news lookup, web browsing, code execution, database write, or tool use.
- Raw calibration dialogue is not research evidence.
- The only durable output is a user-reviewed profile proposal.

Return JSON only:
{
  "assistant_message": "short user-facing reply or follow-up question",
  "proposal": null | {
    "profile_patch": {
      "enabled": true,
      "primary_preset": "growth",
      "risk_appetite": 8,
      "risk_capacity": 4,
      "holding_horizon": "months",
      "drawdown_tolerance_pct": 20,
      "concentration_limit_pct": 15,
      "preferred_edge": ["growth", "catalyst"],
      "avoidances": ["leverage"],
      "behavioral_flags": ["FOMO"],
      "freeform_notes": "concise user-confirmed working model",
      "default_stance": "complementary"
    },
    "rationales": {
      "risk_capacity": "User said a 10% drawdown would likely trigger selling."
    }
  }
}

Never output risk_mismatch; the server derives it.
"""


@dataclass(frozen=True)
class CalibrationAgentResult:
    assistant_message: str
    profile_patch: Optional[dict]
    rationales: dict


class CalibrationResponder(Protocol):
    async def __call__(self, *, messages: list[dict], provider: str | None, model: str | None) -> CalibrationAgentResult: ...


def parse_calibration_model_json(raw: str) -> CalibrationAgentResult:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("calibration model output must be a JSON object")
    msg = str(data.get("assistant_message") or "").strip()
    if not msg:
        raise ValueError("assistant_message is required")
    proposal = data.get("proposal")
    if proposal is None:
        return CalibrationAgentResult(msg, None, {})
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be null or an object")
    patch = proposal.get("profile_patch") or {}
    rationales = proposal.get("rationales") or {}
    if not isinstance(patch, dict) or not isinstance(rationales, dict):
        raise ValueError("proposal.profile_patch and proposal.rationales must be objects")
    normalized, _raw, rats = normalize_proposal_payload(patch, rationales)
    return CalibrationAgentResult(msg, normalized, rats)


async def unavailable_responder(*, messages: list[dict], provider: str | None, model: str | None) -> CalibrationAgentResult:
    del messages, provider, model
    raise RuntimeError("calibration live responder is not wired yet")
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
pytest tests/test_investor_profile_calibration.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/investor_profile_calibration_agent.py tests/test_investor_profile_calibration.py
git commit -m "feat: add investor calibration agent contract"
```

---

## Task 3: Calibration API Routes With Injectable Responder

**Files:**
- Create: `src/api/routes/investor_profile_calibration.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/app.py`
- Test: `tests/test_investor_profile_calibration_routes.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/test_investor_profile_calibration_routes.py`:

```python
"""Track A.5: calibration routes — handler-direct, no TestClient."""

import pytest
import asyncio
from fastapi import HTTPException

from src.api.routes import investor_profile_calibration as routes
from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import CalibrationStore
from src.investor_profile_calibration_agent import CalibrationAgentResult


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    return CalibrationStore(db), InvestorProfileStore(db)


def test_start_session_requires_profile_state_gate(stores, monkeypatch):
    cstore, _pstore = stores
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail=None: calls.append((action, detail)))

    data = routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert calls[0][0] == "investor_profile_calibration_start"
    assert data["active_session"]["status"] == "active"


def test_start_session_conflict_without_explicit_supersede(stores, monkeypatch):
    cstore, _pstore = stores
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    with pytest.raises(HTTPException) as exc:
        routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "calibration_session_active"


def test_send_message_appends_user_assistant_and_inert_proposal(stores, monkeypatch):
    cstore, pstore = stores
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    sess = routes.start_calibration_session(routes.StartCalibrationBody(), store=cstore)["active_session"]

    async def fake_responder(*, messages, provider, model):
        assert provider is None and model is None
        assert messages[-1]["role"] == "user"
        return CalibrationAgentResult(
            assistant_message="You sound growth-oriented but drawdown-sensitive.",
            profile_patch={"enabled": True, "risk_appetite": 8, "risk_capacity": 4, "default_stance": "complementary"},
            rationales={"risk_capacity": "User described likely selling after a 10% drawdown."},
        )

    monkeypatch.setattr(routes, "_default_responder", fake_responder)
    data = asyncio.run(routes.send_calibration_message(
        routes.CalibrationMessageBody(session_id=sess["id"], content="I chase AI stocks but panic at drawdowns."),
        store=cstore,
    ))

    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    assert data["latest_proposal"]["status"] == "draft"
    assert data["latest_proposal"]["profile_patch"]["risk_mismatch"] == "appetite_above_capacity"
    assert pstore.get().enabled is False


def test_approve_proposal_uses_existing_profile_save_and_records_provenance(stores, monkeypatch):
    cstore, pstore = stores
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail=None: calls.append((action, detail)))
    sess = cstore.start_session()
    proposal = cstore.create_proposal(
        session_id=sess.id,
        profile_patch={"enabled": True, "risk_appetite": 8, "risk_capacity": 4, "default_stance": "complementary"},
        rationales={},
    )

    data = routes.approve_calibration_proposal(
        proposal.id,
        routes.ApproveProposalBody(profile_patch={"enabled": True, "risk_appetite": 7, "risk_capacity": 4}),
        store=cstore,
        profile_store=pstore,
    )

    assert calls[0][0] == "investor_profile_calibration_approve"
    assert data["proposal"]["status"] == "approved"
    assert data["proposal"]["approved_at"] is not None
    assert data["proposal"]["changed_fields"] == ["enabled", "risk_appetite", "risk_capacity", "risk_mismatch"]
    assert data["profile"]["risk_mismatch"] == "appetite_above_capacity"
    assert pstore.get().risk_appetite == 7


def test_reject_proposal_keeps_profile_unchanged(stores, monkeypatch):
    cstore, pstore = stores
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    sess = cstore.start_session()
    proposal = cstore.create_proposal(session_id=sess.id, profile_patch={"enabled": True}, rationales={})

    data = routes.reject_calibration_proposal(proposal.id, store=cstore)

    assert data["proposal"]["status"] == "rejected"
    assert pstore.get().enabled is False


def test_calibration_router_mounts_on_real_app():
    from src.api.app import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/profile/investor/calibration" in paths
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_investor_profile_calibration_routes.py -q
```

Expected: FAIL with import error for `src.api.routes.investor_profile_calibration`.

- [ ] **Step 3: Add dependency**

Modify `src/api/dependencies.py`:

```python
@lru_cache(maxsize=1)
def get_investor_calibration_store():
    from src.investor_profile_calibration import CalibrationStore

    return CalibrationStore(_local_state_db_path())
```

- [ ] **Step 4: Implement route module**

Create `src/api/routes/investor_profile_calibration.py`:

```python
"""Investor Profile calibration chat routes (Track A.5).

Mutations are profile-state writes. Raw calibration text never enters research
prompt assembly; these routes only store journal messages and inert proposals.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_investor_calibration_store, get_investor_profile_store
from src.api.permissions import require_profile_state_write
from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import CalibrationStore
from src.investor_profile_calibration_agent import unavailable_responder

router = APIRouter(prefix="/profile/investor/calibration", tags=["investor_profile"])
_default_responder = unavailable_responder
_PROFILE_PROVENANCE_FIELDS = (
    "enabled",
    "primary_preset",
    "risk_appetite",
    "risk_capacity",
    "risk_mismatch",
    "holding_horizon",
    "drawdown_tolerance_pct",
    "concentration_limit_pct",
    "preferred_edge",
    "avoidances",
    "behavioral_flags",
    "freeform_notes",
    "default_stance",
    "skill_mode",
)


class StartCalibrationBody(BaseModel):
    supersede_active: bool = False


class CalibrationMessageBody(BaseModel):
    session_id: Optional[str] = None
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None


class ApproveProposalBody(BaseModel):
    profile_patch: Optional[dict] = None


def _session(s):
    return asdict(s) if s else None


def _message(m):
    return asdict(m)


def _proposal(p):
    return asdict(p) if p else None


def _bad(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _state(store: CalibrationStore, session_id: str | None = None) -> dict:
    active = store.get_active_session()
    sid = session_id or (active.id if active else None)
    messages = store.list_messages(sid) if sid else []
    proposal = store.latest_proposal(sid) if sid else None
    return {
        "active_session": _session(active),
        "sessions": [_session(s) for s in store.list_sessions()],
        "messages": [_message(m) for m in messages],
        "latest_proposal": _proposal(proposal),
    }


@router.get("")
def get_calibration_state(
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    return _state(store)


@router.post("/sessions")
def start_calibration_session(
    body: StartCalibrationBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write("investor_profile_calibration_start", {"supersede_active": body.supersede_active})
    try:
        sess = store.start_session(supersede_active=body.supersede_active)
    except ValueError as exc:
        if str(exc) == "calibration_session_active":
            raise _bad(409, "calibration_session_active", "an active calibration session already exists") from exc
        raise _bad(400, "invalid_calibration_session", str(exc)) from exc
    return _state(store, sess.id)


@router.post("/sessions/{session_id}/close")
def close_calibration_session(
    session_id: str,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write("investor_profile_calibration_close", {"session_id": session_id})
    try:
        sess = store.close_session(session_id)
    except ValueError as exc:
        raise _bad(404, "calibration_session_not_found", str(exc)) from exc
    return _state(store, sess.id)


@router.post("/messages")
async def send_calibration_message(
    body: CalibrationMessageBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    active = store.get_active_session()
    sid = body.session_id or (active.id if active else None)
    if not sid:
        raise _bad(409, "calibration_session_required", "start a calibration session first")
    require_profile_state_write("investor_profile_calibration_message", {"session_id": sid})
    try:
        store.append_message(sid, role="user", content=body.content)
        messages = [{"role": m.role, "content": m.content} for m in store.list_messages(sid)]
        result = await _default_responder(messages=messages, provider=body.provider, model=body.model)
        store.append_message(sid, role="assistant", content=result.assistant_message)
        if result.profile_patch is not None:
            store.create_proposal(session_id=sid, profile_patch=result.profile_patch, rationales=result.rationales)
    except ValueError as exc:
        raise _bad(400, "invalid_calibration_message", str(exc)) from exc
    return _state(store, sid)


@router.post("/proposals/{proposal_id}/approve")
def approve_calibration_proposal(
    proposal_id: str,
    body: ApproveProposalBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
    profile_store: InvestorProfileStore = Depends(get_investor_profile_store),
):
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise _bad(404, "proposal_not_found", "proposal not found")
    payload = body.profile_patch if body.profile_patch is not None else proposal.profile_patch
    # Validate before the write gate, matching Track A PUT behavior.
    try:
        profile_store.draft(payload)
    except ValueError as exc:
        raise _bad(400, "invalid_investor_profile", str(exc)) from exc
    require_profile_state_write("investor_profile_calibration_approve", {"proposal_id": proposal_id})
    before = asdict(profile_store.get())
    profile = profile_store.save(payload)
    after = asdict(profile)
    changed = sorted(k for k in _PROFILE_PROVENANCE_FIELDS if before.get(k) != after.get(k))
    approved = store.mark_proposal_approved(proposal_id, changed_fields=changed)
    return {"profile": after, "proposal": _proposal(approved)}


@router.post("/proposals/{proposal_id}/reject")
def reject_calibration_proposal(
    proposal_id: str,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write("investor_profile_calibration_reject", {"proposal_id": proposal_id})
    try:
        proposal = store.reject_proposal(proposal_id)
    except ValueError as exc:
        raise _bad(400, "invalid_calibration_proposal", str(exc)) from exc
    return {"proposal": _proposal(proposal)}
```

- [ ] **Step 5: Register route**

Modify `src/api/app.py`:

```python
from .routes.investor_profile_calibration import router as investor_profile_calibration_router
...
app.include_router(investor_profile_calibration_router)
```

Place it next to the existing `investor_profile_router`.

- [ ] **Step 6: Run route tests**

Run:

```bash
pytest tests/test_investor_profile_calibration_routes.py tests/test_investor_profile_routes.py -q
```

Expected: both route suites pass.

- [ ] **Step 7: Add route isolation grep gate**

Run:

```bash
rg -n "research_threads|research_runs|ResearchRunStore|ResearchThreadStore|ToolRegistry|DataAccessLayer|get_dal|market|news" \
  src/investor_profile_calibration.py src/investor_profile_calibration_agent.py src/api/routes/investor_profile_calibration.py
```

Expected: no hits except comments that explicitly describe the prohibited boundary. If code imports any of those symbols, stop.

- [ ] **Step 8: Commit**

```bash
git add src/api/dependencies.py src/api/app.py src/api/routes/investor_profile_calibration.py tests/test_investor_profile_calibration_routes.py
git commit -m "feat: add investor calibration routes"
```

---

## Task 4: Frontend Calibration Panel

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.tsx`
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`

- [ ] **Step 1: Add failing frontend tests**

First widen the existing test response helper in `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`; the current helper is typed to return only `InvestorProfileResponse`, but calibration calls return a different shape:

```tsx
import type { InvestorProfileResponse, CalibrationState, CalibrationProposal } from "./api";

type PanelApiResponse =
  | InvestorProfileResponse
  | CalibrationState
  | { profile: InvestorProfileResponse["profile"]; proposal: Partial<CalibrationProposal> };

function stubFetch(handler: (url: string, init?: RequestInit) => PanelApiResponse) {
  // existing body unchanged
}
```

Then append tests using the existing `mount()`, `stubFetch()`, `disabledResponse()`, `host`, and `act()` helpers:

```tsx
it("starts calibration, sends a message, and shows proposal rationale", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  stubFetch((url, init) => {
    calls.push({ url, init });
    if (url.endsWith("/profile/investor")) return disabledResponse();
    if (url.endsWith("/profile/investor/calibration/sessions")) {
      return {
        active_session: { id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null },
        sessions: [{ id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null }],
        messages: [],
        latest_proposal: null,
      };
    }
    if (url.endsWith("/profile/investor/calibration/messages")) {
      return {
        active_session: { id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null },
        sessions: [{ id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null }],
        messages: [
          { id: "m1", session_id: "s1", role: "user", content: "I chase AI stocks.", created_at: "t" },
          { id: "m2", session_id: "s1", role: "assistant", content: "Draft ready.", created_at: "t" },
        ],
        latest_proposal: {
          id: "p1",
          session_id: "s1",
          status: "draft",
          profile_patch: { enabled: true, risk_appetite: 8, risk_capacity: 4, risk_mismatch: "appetite_above_capacity", default_stance: "complementary" },
          raw_profile_patch: { enabled: true, risk_appetite: 8, risk_capacity: 4, default_stance: "complementary" },
          rationales: { risk_capacity: "User said 10% drawdown would likely trigger selling." },
          changed_fields: [],
          created_at: "t",
          approved_at: null,
          rejected_at: null,
        },
      };
    }
    return disabledResponse();
  });
  await mount();

  const startBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
    b.textContent?.includes("開始校準對話"),
  )!;
  await act(async () => startBtn.click());
  const textarea = host!.querySelector<HTMLTextAreaElement>('textarea[aria-label="校準訊息"]')!;
  textarea.value = "I chase AI stocks.";
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  const sendBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
    b.textContent?.includes("送出校準訊息"),
  )!;
  await act(async () => sendBtn.click());

  expect(host!.textContent).toContain("Draft ready.");
  expect(host!.textContent).toContain("User said 10% drawdown");
  expect(host!.textContent).toContain("風險承受能力");
});

it("approves calibration proposal through the dedicated endpoint", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  stubFetch((url, init) => {
    calls.push({ url, init });
    if (url.endsWith("/profile/investor")) return disabledResponse();
    if (url.includes("/profile/investor/calibration/proposals/p1/approve")) {
      const resp = disabledResponse();
      resp.profile.enabled = true;
      resp.profile.risk_appetite = 8;
      return { profile: resp.profile, proposal: { id: "p1", status: "approved", approved_at: "t" } };
    }
    return {
      active_session: { id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null },
      sessions: [{ id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null }],
      messages: [],
      latest_proposal: {
        id: "p1", session_id: "s1", status: "draft",
        profile_patch: { enabled: true, risk_appetite: 8, risk_capacity: 4, default_stance: "complementary" },
        raw_profile_patch: {}, rationales: {}, changed_fields: [],
        created_at: "t", approved_at: null, rejected_at: null,
      },
    };
  });
  await mount();
  const approveBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
    b.textContent?.includes("套用校準提案"),
  )!;
  await act(async () => approveBtn.click());

  const approve = calls.find((c) => c.url.includes("/proposals/p1/approve"));
  expect(approve).toBeTruthy();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix apps/arkscope-web test -- InvestorProfilePanel.test.tsx
```

Expected: FAIL because calibration API helpers/UI are missing.

- [ ] **Step 3: Add API DTOs and helpers**

Modify `apps/arkscope-web/src/api.ts`:

```ts
export interface CalibrationSession {
  id: string;
  status: "active" | "closed" | "superseded";
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface CalibrationMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface CalibrationProposal {
  id: string;
  session_id: string;
  status: "draft" | "approved" | "rejected";
  profile_patch: Partial<InvestorProfile>;
  raw_profile_patch: Partial<InvestorProfile>;
  rationales: Record<string, string>;
  changed_fields: string[];
  created_at: string;
  approved_at: string | null;
  rejected_at: string | null;
}

export interface CalibrationState {
  active_session: CalibrationSession | null;
  sessions: CalibrationSession[];
  messages: CalibrationMessage[];
  latest_proposal: CalibrationProposal | null;
}

export function getCalibrationState(): Promise<CalibrationState> {
  return getJSON<CalibrationState>("/profile/investor/calibration", 8_000);
}

export function startCalibrationSession(supersede_active = false): Promise<CalibrationState> {
  return sendJSON<CalibrationState>("/profile/investor/calibration/sessions", "POST", { supersede_active }, 8_000);
}

export function sendCalibrationMessage(body: { session_id?: string; content: string; provider?: string; model?: string }): Promise<CalibrationState> {
  return sendJSON<CalibrationState>("/profile/investor/calibration/messages", "POST", body, 60_000);
}

export function approveCalibrationProposal(proposalId: string, profilePatch: Partial<InvestorProfile>): Promise<{ profile: InvestorProfile; proposal: CalibrationProposal }> {
  return sendJSON(`/profile/investor/calibration/proposals/${encodeURIComponent(proposalId)}/approve`, "POST", { profile_patch: profilePatch }, 20_000);
}

export function rejectCalibrationProposal(proposalId: string): Promise<{ proposal: CalibrationProposal }> {
  return sendJSON(`/profile/investor/calibration/proposals/${encodeURIComponent(proposalId)}/reject`, "POST", undefined, 8_000);
}
```

- [ ] **Step 4: Add calibration panel UI**

Modify `apps/arkscope-web/src/InvestorProfilePanel.tsx`:

- Import the new helpers/types.
- Load `getCalibrationState()` alongside `getInvestorProfile()`.
- Add a section below the existing freeform textarea titled `校準對話`.
- Show messages in order with role labels.
- Add textarea `aria-label="校準訊息"`.
- Add buttons:
  - `開始校準對話`
  - `送出校準訊息`
  - `套用校準提案`
  - `拒絕提案`
- When a draft proposal arrives, merge `latest_proposal.profile_patch` into the local `form` state and show `latest_proposal.rationales` next to the corresponding fields.
- On approval, call `approveCalibrationProposal(proposal.id, payload())`, then call `getInvestorProfile()` and `getCalibrationState()` to refresh truth from the server.

The UI copy must say:

```tsx
<p className="muted">
  校準對話只用來整理投資人輪廓,不是投資建議或個股推薦。只有你核准的結構化設定會影響研究;原始對話不會進入研究 prompt。
</p>
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
npm --prefix apps/arkscope-web test -- InvestorProfilePanel.test.tsx
```

Expected: tests pass.

- [ ] **Step 6: Run TypeScript check**

Run:

```bash
npm --prefix apps/arkscope-web run typecheck
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/InvestorProfilePanel.tsx apps/arkscope-web/src/InvestorProfilePanel.test.tsx
git commit -m "feat: add investor calibration panel"
```

---

## Task 5: Live Calibration Responder

**Files:**
- Modify: `src/investor_profile_calibration_agent.py`
- Modify: `src/api/routes/investor_profile_calibration.py`
- Test: `tests/test_investor_profile_calibration.py`
- Test: `tests/test_investor_profile_calibration_routes.py`

**Important:** This task is intentionally last. If provider-driver constraints make a no-tool calibration call unsafe, stop here and mark live responder as blocked; do not weaken the storage/UI boundaries.

- [ ] **Step 1: Write failing live-responder contract tests**

Append to `tests/test_investor_profile_calibration.py`:

```python
def test_responder_request_contains_no_tool_or_market_language(monkeypatch):
    import asyncio
    import src.investor_profile_calibration_agent as mod

    captured = {}

    async def fake_call(*, provider, model, instructions, input_messages):
        captured.update({
            "provider": provider,
            "model": model,
            "instructions": instructions,
            "input_messages": input_messages,
        })
        return '{"assistant_message":"What is your maximum tolerable drawdown?","proposal":null}'

    monkeypatch.setattr(mod, "_call_calibration_llm", fake_call)
    result = asyncio.run(mod.live_calibration_responder(
        messages=[{"role": "user", "content": "I want growth."}],
        provider="openai",
        model="gpt-5.4-mini",
    ))
    assert result.assistant_message.startswith("What")
    blob = captured["instructions"].lower()
    assert "no market data" in blob
    assert "tool" not in captured
```

Add route test:

```python
def test_route_default_responder_is_live_seam_not_unavailable():
    assert routes._default_responder is routes.default_calibration_responder
    assert routes._default_responder is not routes.unavailable_responder
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_investor_profile_calibration.py tests/test_investor_profile_calibration_routes.py -q
```

Expected: FAIL because `live_calibration_responder` / `default_calibration_responder` are missing.

- [ ] **Step 3: Implement live responder with no-tool call seam**

Modify `src/investor_profile_calibration_agent.py`:

```python
from src.auth_drivers.live_resolver import resolve_live_auth


def _default_model(provider: str, model: str | None) -> str:
    if model:
        return model
    return "gpt-5.4-mini" if provider == "openai" else "claude-sonnet-4-6"


async def _call_calibration_llm(*, provider: str, model: str, instructions: str, input_messages: list[dict]) -> str:
    """Provider call seam. No registry, no DAL, no tools.

    Implementation rule:
    - OpenAI API-key/env: use the direct OpenAI client.
    - ChatGPT OAuth: use OpenAIChatGPTOAuthDriver with registry=None and dal=None, so it sends no tools.
    - Anthropic API-key/env: use direct Anthropic messages.
    - Claude subscription: only support if a no-tool SDK path can be implemented without MCP/tools.
      If not, raise a clear unsupported error and stop this task for review.
    """
    raise NotImplementedError("wire provider-specific no-tool calibration call here")


async def live_calibration_responder(*, messages: list[dict], provider: str | None, model: str | None) -> CalibrationAgentResult:
    chosen_provider = (provider or "openai").lower().strip()
    if chosen_provider not in ("openai", "anthropic"):
        raise ValueError(f"unsupported calibration provider: {chosen_provider}")
    chosen_model = _default_model(chosen_provider, model)
    raw = await _call_calibration_llm(
        provider=chosen_provider,
        model=chosen_model,
        instructions=CALIBRATION_SYSTEM_PROMPT,
        input_messages=messages,
    )
    return parse_calibration_model_json(raw)
```

Then implement `_call_calibration_llm` minimally with existing auth resolution. Required behavior:

- It must never instantiate `ToolRegistry`.
- It must never accept or pass a DAL.
- For ChatGPT OAuth, build `OpenAIChatGPTOAuthDriver(..., registry=None, dal=None)` and call `call_llm(LLMRequest(...))`; `registry=None` means `_build_tools()` returns `[]`.
- For OpenAI API key/env fallback, use direct SDK client with `tools` omitted and JSON-only instructions.
- For Anthropic API key/env fallback, use direct Anthropic client with `tools` omitted and JSON-only instructions.
- For Claude subscription, either implement a no-tool Agent SDK path with `tools=[]`, `allowed_tools=[]`, no MCP server, and isolated config, or raise `RuntimeError("claude_code_oauth calibration no-tool path is not wired")` and stop for review. Do not reuse `AnthropicClaudeCodeSdkDriver` as-is because it hard-wires the research MCP allowlist.

- [ ] **Step 4: Wire route default responder**

Modify `src/api/routes/investor_profile_calibration.py`:

```python
from src.investor_profile_calibration_agent import (
    live_calibration_responder as default_calibration_responder,
)
...
_default_responder = default_calibration_responder
```

Keep tests able to inject a fake responder by monkeypatching the module-level `_default_responder`.

- [ ] **Step 5: Add grep gates for no tools/no research leakage**

Run:

```bash
rg -n "ToolRegistry|register_all|get_dal|DataAccessLayer|research_threads|ResearchRunStore|ResearchThreadStore|market|news" \
  src/investor_profile_calibration_agent.py src/api/routes/investor_profile_calibration.py
```

Expected:

- No code imports `ToolRegistry`, `get_dal`, `DataAccessLayer`, `ResearchRunStore`, or `ResearchThreadStore`.
- The only allowed `market`/`news` occurrences are boundary copy strings such as `No market data`.

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_investor_profile_calibration.py tests/test_investor_profile_calibration_routes.py -q
```

Expected: pass. If live provider support cannot safely satisfy the no-tool boundary, stop and report with the exact failing provider path.

- [ ] **Step 7: Commit**

```bash
git add src/investor_profile_calibration_agent.py src/api/routes/investor_profile_calibration.py tests/test_investor_profile_calibration.py tests/test_investor_profile_calibration_routes.py
git commit -m "feat: wire investor calibration responder"
```

---

## Task 6: Focused Gates, Smoke, And Docs Closeout

**Files:**
- Modify: `docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Run backend focused suite**

Run:

```bash
pytest tests/test_investor_profile.py tests/test_investor_profile_routes.py tests/test_investor_profile_calibration.py tests/test_investor_profile_calibration_routes.py tests/test_research_runs.py tests/test_research_routes.py tests/test_analysis_cards_api.py -q
```

Expected: pass. Any failure in research/card personalization tests is a finding; calibration must not change research prompt behavior except through approved structured profile.

- [ ] **Step 2: Run frontend focused suite**

Run:

```bash
npm --prefix apps/arkscope-web test -- InvestorProfilePanel.test.tsx ResearchPersonalization.test.tsx AICardPersonalization.test.tsx
npm --prefix apps/arkscope-web run typecheck
```

If exact personalization test filenames differ, use:

```bash
rg -n "personalization|assistant_stance|InvestorProfilePanel" apps/arkscope-web/src -g '*.test.tsx' -g '*.test.ts'
```

and run every matching test file.

Expected: pass.

- [ ] **Step 3: Run standing PG-unreachable smoke**

Run:

```bash
python -m src.smoke.pg_unreachable_e2e
```

Expected: `ok:true`, `pg_attempts:[]`.

- [ ] **Step 4: Run boundary grep**

Run:

```bash
rg -n "calibration" src/research_threads.py src/research_runs.py src/research_run_manager.py src/card_synthesis.py src/api/personalization.py src/agents/shared/prompts.py src/api/routes/research.py
```

Expected: no hits. Calibration must not enter research/card prompt or hydration code.

Run:

```bash
rg -n "research_threads|research_runs|ResearchRunStore|ResearchThreadStore|ToolRegistry|DataAccessLayer|get_dal" \
  src/investor_profile_calibration.py src/investor_profile_calibration_agent.py src/api/routes/investor_profile_calibration.py
```

Expected: no code imports those symbols. Comments may mention prohibited boundaries only when phrased as negative assertions.

- [ ] **Step 5: Full A/B**

Run the established virgin-archive full A/B against the merge base and head.

Expected:

- failure set identical;
- pytest passed count increases by exactly the number of new backend tests added;
- zero head-only deterministic failures.

If the local Codex environment cannot complete full A/B, leave it for reviewer and do not claim merge-ready.

- [ ] **Step 6: Docs closeout**

After live/focused verification:

- Update `docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md` Track A.5 header to implemented/merged only after merge/live verification. Before that, use `IMPLEMENTED FOR REVIEW`.
- Add a newest-first §10 entry in `docs/design/PROJECT_PRIORITY_MAP.md` with:
  - dedicated loop decision;
  - one-active-session rule;
  - no-tool/no-research-thread boundary evidence;
  - tests and smoke evidence;
  - any live responder provider limitation, if applicable.

- [ ] **Step 7: Commit closeout**

```bash
git add docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: close investor calibration chat"
```

---

## Review Checklist

Reviewer should verify:

- `src/investor_profile_calibration*` has no live imports of `ToolRegistry`, DAL, market/news sources, or research stores.
- All calibration writes call `require_profile_state_write`.
- Draft proposal does not mutate `investor_profile`.
- Approval uses `InvestorProfileStore.save()` and therefore derives `risk_mismatch`.
- Raw calibration messages are stored only in calibration tables.
- Research/card prompt paths do not mention calibration.
- UI copy says calibration is not investment advice and raw dialogue does not enter research prompts.
- Full A/B is identical except for expected new tests.
