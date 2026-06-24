"""P1.2 free calendar + macro data layer.

Schema lives in ``sql/013_add_p1_2_macro_calendar.sql``; design notes in
``docs/design/P1_2_SPEC.md``. This package only ships the schema +
DAL helpers in commit 1; ingestion jobs, freshness telemetry, and
read API/tools land in later commits.
"""

from typing import Any


def get_macro_calendar_store(dal: Any):
    """Return the macro/cal store for the active mode (PG-exit §4c slice 2).

    ``use_local_macro`` on (env ``ARKSCOPE_USE_LOCAL_MACRO`` or the persisted
    profile_settings key) → the SQLite ``MacroCalendarLocalStore`` over its own
    ``macro_calendar.db`` (no PG). Off (default) → the PG ``MacroCalendarStore(dal)``.
    Both expose the same method surface, so read call sites are mode-agnostic. Lazy
    imports keep psycopg2 off the local path. A ``dal`` lacking the toggle (older/test
    doubles) is treated as OFF → PG store, preserving current behavior.
    """
    if getattr(dal, "_local_macro_enabled", None) and dal._local_macro_enabled():
        from src.macro_calendar.local_store import MacroCalendarLocalStore
        return MacroCalendarLocalStore()
    from src.macro_calendar.store import MacroCalendarStore
    return MacroCalendarStore(dal)