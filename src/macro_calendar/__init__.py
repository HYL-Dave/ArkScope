"""Calendar and macroeconomic data access."""

from typing import Any

# Persisted setting and optional environment override exposed by the status API.
USE_LOCAL_MACRO_KEY = "use_local_macro"
ENV_USE_LOCAL_MACRO = "ARKSCOPE_USE_LOCAL_MACRO"


def get_macro_calendar_store(dal: Any):
    """Return the current local macro/calendar store."""
    from src.macro_calendar.local_store import MacroCalendarLocalStore
    return MacroCalendarLocalStore()
