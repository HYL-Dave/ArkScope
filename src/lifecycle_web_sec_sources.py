"""SEC identity/pacing over the common pinned HTTPS reader, without retries."""

from data_sources.sec_transport import SecRequestGovernor, SecTransport, SecTransportFailure
from data_sources.sec_user_agent import get_sec_user_agent
from src.lifecycle_public_sources import SourceReadError


class _ReadStopped(Exception):
    def __init__(self, error):
        self.error = error


class SecSourcePolicy:
    def __init__(self, *, user_agent=None, governor=None):
        self.user_agent = user_agent
        self.governor = governor

    def prepare(self, url, *, check):
        from data_sources.sec_transport import validate_sec_identity

        try:
            SecTransport._validate_url(url)
            identity = get_sec_user_agent() if self.user_agent is None else self.user_agent
            validate_sec_identity(identity)
            def poll():
                try:
                    check()
                except SourceReadError as exc:
                    raise _ReadStopped(exc) from None
            governor = self.governor or SecRequestGovernor()
            governor.reserve_request_start(check=poll)
            check()
            return identity
        except _ReadStopped as exc:
            raise exc.error from None
        except SecTransportFailure as exc:
            raise SourceReadError(exc.code) from None
