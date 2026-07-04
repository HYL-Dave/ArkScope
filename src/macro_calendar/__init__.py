"""P1.2 free calendar + macro data layer.

Schema lives in ``sql/013_add_p1_2_macro_calendar.sql``; design notes in
``docs/design/P1_2_SPEC.md``. This package only ships the schema +
DAL helpers in commit 1; ingestion jobs, freshness telemetry, and
read API/tools land in later commits.
"""

from typing import Any

# Legacy profile_settings key + env override retained for provenance. After N9
# batch-2, macro/calendar runtime routing is local by default.
USE_LOCAL_MACRO_KEY = "use_local_macro"
ENV_USE_LOCAL_MACRO = "ARKSCOPE_USE_LOCAL_MACRO"


def get_macro_calendar_store(dal: Any):
    """Return the post-N9 local macro/calendar store.

    The old PG ``MacroCalendarStore`` remains importable for legacy/drop tooling,
    but normal runtime routing is always the SQLite ``MacroCalendarLocalStore``.
    """
    from src.macro_calendar.local_store import MacroCalendarLocalStore
    return MacroCalendarLocalStore()
