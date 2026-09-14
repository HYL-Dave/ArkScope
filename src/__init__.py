"""ArkScope source modules, with early admission of an explicitly selected engine."""

from .sqlite_runtime.contract import require_selected_runtime as _require_selected_runtime

_require_selected_runtime()
del _require_selected_runtime
