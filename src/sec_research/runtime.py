"""Lazy application composition; domain queries never import API routers."""

from contextlib import contextmanager
from datetime import datetime, timezone

from .paths import SecResearchPaths
from .store import Store


def require_acquisition(name: str) -> None:
    """Use the existing additive-write permission choke point."""
    from src.api.permissions import require_db_write
    require_db_write("sec_research_tool_acquire", {"tool": name})


@contextmanager
def _acquisition(store):
    from data_sources.sec_transport import SecTransport, validate_sec_identity
    from src.api.dependencies import get_data_provider_store, get_profile_store
    from src.data_provider_config import PROVIDER_FIELDS, normalize_provider_config_value
    from src.lifecycle_public_sources import PublicSourceReader
    from src.lifecycle_web_sec_sources import SecSourcePolicy
    from .captures import CaptureStore
    from .config import get_capture_budget_bytes

    profile = get_profile_store()
    budget = lambda: get_capture_budget_bytes(profile)
    budget()
    identity = get_data_provider_store().get_all().get("sec_edgar", {}).get("user_agent", "")
    validate_sec_identity(identity)
    identity = normalize_provider_config_value(PROVIDER_FIELDS["sec_edgar"][0], identity)
    validate_sec_identity(identity)
    transport = SecTransport(user_agent=identity, max_rate_limit_retries=0)
    try:
        store.install()
        captures = CaptureStore(store, budget=budget)
        policy = SecSourcePolicy(user_agent=identity)

        def reader_factory(limits, *, document_observer, text_extractor):
            return PublicSourceReader(limits, sec_policy=policy,
                document_observer=document_observer, text_extractor=text_extractor)

        yield captures, transport, reader_factory
    finally:
        transport.close()


def build_tool_service():
    """Resolve paths only; defer config, transport and installation to acquisition."""
    from .tool_service import ToolService
    store = Store(SecResearchPaths.resolve())
    return ToolService(store, acquisition_factory=lambda: _acquisition(store),
                       clock=lambda: datetime.now(timezone.utc).isoformat())
