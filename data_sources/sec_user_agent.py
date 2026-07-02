"""Shared SEC EDGAR User-Agent resolver.

Every SEC client must use this helper so the app-managed
ARKSCOPE_SEC_USER_AGENT FieldDef actually reaches all SEC request paths.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_SEC_USER_AGENT = "ArkScope research@example.com"


def get_sec_user_agent() -> str:
    canonical = os.environ.get("ARKSCOPE_SEC_USER_AGENT", "").strip()
    if canonical:
        return canonical
    contact = os.environ.get("SEC_CONTACT_EMAIL", "").strip()
    if contact:
        return contact if contact.startswith("ArkScope ") else f"ArkScope {contact}"
    legacy = os.environ.get("SEC_USER_AGENT", "").strip()
    if legacy:
        return legacy
    logger.warning(
        "No SEC User-Agent set - using placeholder (SEC may rate-limit/reject). "
        "Set ARKSCOPE_SEC_USER_AGENT (e.g. 'ArkScope you@example.com') in Settings."
    )
    return DEFAULT_SEC_USER_AGENT
