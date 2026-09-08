"""Run the same framing owners with real TLS over AF_UNIX, never a provider.

OpenSSL generates an ephemeral test-only certificate/key in pytest's private
temporary directory. No test key or certificate is copied into this packet.
This is a local admission probe, not an additional production dependency.
"""

import ssl
import subprocess

import pytest

from tests.test_lifecycle_public_sources import deny_real_network
from tests.test_lifecycle_public_sources_wire import (
    wire,
    test_real_truncated_response_remains_rejected,
    test_response_owned_body_survives_connection_close,
    test_response_stream_is_closed_when_headers_reject_source,
    test_stop_interrupts_response_after_connection_ownership_transfer,
)


@pytest.fixture(scope="module")
def wire_contexts(tmp_path_factory):
    directory = tmp_path_factory.mktemp("source-wire-tls")
    certificate, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes",
        "-keyout", str(key), "-out", str(certificate), "-days", "1",
        "-subj", "/CN=ir.example.com", "-addext", "subjectAltName=DNS:ir.example.com",
    ], check=True, capture_output=True, timeout=15)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(str(certificate), str(key))
    client = ssl.create_default_context(cafile=str(certificate))
    assert client.check_hostname and client.verify_mode == ssl.CERT_REQUIRED
    yield client, server
    key.unlink()
    certificate.unlink()
