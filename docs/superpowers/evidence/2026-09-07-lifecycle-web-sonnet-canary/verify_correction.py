"""Source transport correction, whole affected focus and full backend admission."""

import importlib.util
from pathlib import Path


PACKET = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "source_correction_verifier",
    PACKET.parent / "2026-09-07-lifecycle-web-runtime/scripts/verify.py",
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
verifier.foundation.ADDED |= {"tests/test_lifecycle_public_sources_wire.py"}
mutation = verifier.mutation
SOURCE = "src/lifecycle_public_sources.py"

verifier.MUTATIONS = {
    "backend": (
        mutation(
            "normal_close_aborts_response_body", "test_response_owned_body_survives_connection_close", SOURCE,
            "                stream.close()\n\n\nclass _SourceTextParser",
            "                stream.close()\n\n"
            "    def close(self):\n        self.abort()\n        super().close()\n\n\nclass _SourceTextParser",
        ),
        mutation(
            "response_socket_not_retained_for_abort",
            "test_stop_interrupts_response_after_connection_ownership_transfer", SOURCE,
            "                self._transport_socket = wrapped", "                self._transport_socket = None",
        ),
        mutation(
            "response_handle_not_closed_on_header_rejection",
            "test_response_stream_is_closed_when_headers_reject_source", SOURCE,
            "                if response is not None:\n                    response.close()",
            "                if response is not None:\n                    pass",
        ),
        mutation(
            "incomplete_body_is_admitted", "test_real_truncated_response_remains_rejected", SOURCE,
            "                if length is not None and len(body) != int(length):", "                if False:",
        ),
        mutation(
            "abort_does_not_interrupt_open_response",
            "test_stop_interrupts_response_after_connection_ownership_transfer", SOURCE,
            "                    stream.shutdown(socket.SHUT_RDWR)", "                    pass",
        ),
    ),
    "frontend": (),
}


if __name__ == "__main__":
    verifier.main()
