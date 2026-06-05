"""
Permission classes for ArkScope side effects.

ProductSpec §4.3 defines six gated permission classes. The interactive
enforcement model (default ASK, per-class auto-approve toggle, once / session /
always grain) is NOT implemented in code yet — it lands with the desktop
permission engine. Until then this module is the single structural
choke-point: every gated side effect calls :func:`require_permission` (or a
class helper) BEFORE acting, and the intent is audit-logged. Wiring real
enforcement later means changing ONLY this module, not every call site.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class PermissionClass(str, Enum):
    """The six gated classes from ProductSpec §4.3.

    Gating is by cost / side effect, not read-vs-write: local reads and
    already-enabled-provider reads are never gated.
    """

    metered_spend = "metered_spend"
    code_execution = "code_execution"
    db_write = "db_write"
    profile_state_write = "profile_state_write"
    external_web_access = "external_web_access"
    external_browser_automation = "external_browser_automation"


def require_permission(
    permission: PermissionClass,
    action: str,
    detail: dict | None = None,
) -> None:
    """Choke-point for a gated side effect.

    Enforcement is a no-op today (the spec's ASK / auto-approve / grain engine
    does not exist in code yet); this audit-logs the intent so the future
    engine has exactly one place to gate. Call this BEFORE performing the
    side effect.
    """
    logger.info("permission[%s] %s %s", permission.value, action, detail or {})


def require_profile_state_write(action: str, detail: dict | None = None) -> None:
    """``profile_state_write``: mutations to the user's research universe /
    profile state — followed, archived, tags, notes, follow rules.

    Storage-independent and distinct from additive ``db_write`` (memory /
    report / analysis records).
    """
    require_permission(PermissionClass.profile_state_write, action, detail)
