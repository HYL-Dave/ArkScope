"""S3-prep: redacted probe-harness skeleton.

The safe runner for the live auth probes (P1/P2/P3) that arrive in S3/S4. Plan §9
discipline: record response shape/status/error, NEVER save tokens/PII, never
raise, user-triggered only. This is the skeleton — no real probe logic yet, just
the redaction + result shape + runner that make live probes safe to run.
"""

from __future__ import annotations

import json

import pytest

from src.auth_drivers.probe_harness import ProbeResult, redact, run_probe

# token-shaped strings that MUST never survive into a result/log
_SK = "sk-proj-AbCdEf0123456789AbCdEf0123456789"
_SK_ANT = "sk-ant-api03-ZyXwVu9876543210ZyXwVu9876543210"
_BEARER = "Bearer abcDEF123456ghiJKL789mnoPQR"
_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N"


# --- redact(): scrubs token-shaped material ---------------------------------
@pytest.mark.parametrize("secret", [_SK, _SK_ANT, _BEARER, _JWT])
def test_redact_scrubs_token_shapes(secret):
    out = redact(f"auth failed with {secret} on backend")
    assert secret not in out
    # the non-secret context survives
    assert "auth failed" in out and "backend" in out


def test_redact_keeps_short_nonsecret_tokens():
    # model ids / short identifiers are NOT secrets and must survive
    s = redact("model gpt-5.4 effort medium status ok")
    assert "gpt-5.4" in s and "medium" in s and "ok" in s


def test_redact_handles_non_strings():
    assert redact(None) == ""
    assert "123" in redact(12345)  # coerced, not crashed


# --- ProbeResult: no field can carry a raw token ----------------------------
def test_probe_result_shape_and_no_token_field():
    r = ProbeResult(name="P1", passed=True, expected="standard host", observed="ok")
    d = r.model_dump()
    assert set(d) == {"name", "passed", "expected", "observed", "error"}  # no token/secret field
    assert d["error"] is None


def test_probe_result_rejects_unknown_field():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProbeResult(name="P1", passed=True, expected="x", observed="y", access_token="leak")


# --- run_probe(): never raises, redacts observed AND errors -----------------
def test_run_probe_pass():
    r = run_probe("P1", expected="standard host", fn=lambda: "api.openai.com reached")
    assert r.passed is True and r.error is None and "api.openai.com" in r.observed


def test_run_probe_redacts_token_in_observed():
    r = run_probe("P2", expected="capability floor", fn=lambda: f"sent token {_SK} got 200")
    assert _SK not in r.observed and _SK not in json.dumps(r.model_dump())
    assert r.passed is True


def test_run_probe_catches_and_redacts_exception_token():
    def boom():
        raise RuntimeError(f"401 rejected key {_SK_ANT}")

    r = run_probe("P1", expected="reject", fn=boom)
    assert r.passed is False  # an exception is a failed probe, never propagated
    assert r.error is not None and _SK_ANT not in r.error
    # the WHOLE serialized result is token-free (no leak via any field)
    assert _SK_ANT not in json.dumps(r.model_dump())


def test_run_probe_never_raises_even_on_weird_fn():
    r = run_probe("P3", expected="x", fn=lambda: (_ for _ in ()).throw(ValueError(f"boom {_BEARER}")))
    assert r.passed is False and _BEARER not in (r.error or "")


def test_run_probe_passed_flag_from_bool_fn():
    # an fn returning a (passed, observation) tuple sets passed explicitly
    r = run_probe("P1", expected="reject", fn=lambda: (False, "host accepted the token (unexpected)"))
    assert r.passed is False and "unexpected" in r.observed and r.error is None


# ===========================================================================
# Adversarial-review regression tests (verified leaks → permanent guards)
# ===========================================================================
def _no_trace(secret: str, r) -> bool:
    """No 4+ char substring of the secret survives anywhere in the serialized result."""
    blobs = [json.dumps(r.model_dump()), r.model_dump_json(), repr(r), r.observed, r.error or "", r.name]
    chunks = [secret[i:i + 4] for i in range(0, max(1, len(secret) - 3))]
    return all(all(c not in b for c in chunks) for b in blobs)


def test_leak_name_argument_is_redacted():
    # was a leak: name was never redacted → survived into every sink
    r = run_probe(name=f"probe for {_SK}", expected="x", fn=lambda: "ok")
    assert _SK not in r.name and _SK not in json.dumps(r.model_dump()) and _SK not in repr(r)


def test_leak_base64_token_with_plus_slash_equals():
    secret = "abcDEFghiJKL012345+mnoPQRstuVWX/yz6789AB=="
    r = run_probe("P2", expected="x", fn=lambda: f"sent {secret} got 200")
    assert _no_trace(secret, r)


def test_leak_dotted_paseto_token():
    secret = "v2.local.aBcD1234.eFgH5678.iJkL9012"
    r = run_probe("P2", expected="x", fn=lambda: f"token {secret}")
    assert _no_trace(secret, r)


def test_leak_url_encoded_token():
    secret = "tok%3Dabc%2Bdef%2Fghi%3Djkl%2Bmno"
    r = run_probe("P2", expected="x", fn=lambda: f"redirect {secret}")
    assert _no_trace(secret, r)


def test_leak_newline_wrapped_token():
    r = run_probe("P2", expected="x", fn=lambda: "hdr AbCdEf01234\n56789AbCdEfGh0 end")
    assert "AbCdEf01234" not in r.observed and "56789AbCdEfGh0" not in r.observed


def test_leak_short_mixed_entropy_credentials():
    for secret in ("ghp_16C7e42F292c69", "code=ac_Xy12Zw7Qr"):
        r = run_probe("P1", expected="x", fn=lambda s=secret: f"401 rejected {s}")
        assert _no_trace(secret.split("=")[-1], r)


def test_leak_email_and_account_pii():
    r = run_probe("P1", expected="x", fn=lambda: "authenticated as dave.li@toppansecurity.com acct acct_19Bz7T8x")
    assert "dave.li@toppansecurity.com" not in json.dumps(r.model_dump())
    assert "acct_19Bz7T8x" not in json.dumps(r.model_dump())


def test_leak_structured_repr_fragmentation_is_typegated():
    # a non-str observation is reduced to its TYPE NAME, never str()'d
    class Resp:
        def __init__(self, tok):
            self.tok = tok

        def __repr__(self):
            return "Resp(" + ", ".join(repr(self.tok[i:i + 8]) for i in range(0, len(self.tok), 8)) + ")"

    secret = "proj-AbCdEf0123456789AbCdEf"
    r = run_probe("P2", expected="x", fn=lambda: Resp(secret))
    assert r.observed == "<Resp>" and _no_trace(secret, r)


def test_exception_with_raising_str_returns_not_raises():
    class Evil(Exception):
        def __str__(self):
            raise RuntimeError("boom in __str__")

    r = run_probe("P1", expected="x", fn=lambda: (_ for _ in ()).throw(Evil()))  # must not propagate
    assert r.passed is False and r.error is not None  # synthesized, not raised


@pytest.mark.parametrize("sig", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_operator_signals_propagate_not_swallowed(sig):
    with pytest.raises(sig):
        run_probe("P1", expected="x", fn=lambda: (_ for _ in ()).throw(sig()))


def test_model_dump_json_is_token_free_on_error_path():
    r = run_probe("P1", expected="x", fn=lambda: (_ for _ in ()).throw(RuntimeError(f"key {_SK}")))
    assert _SK not in r.model_dump_json()


def test_direct_construction_also_redacts():
    # the model validator redacts even when ProbeResult is built directly
    r = ProbeResult(name=_SK, passed=True, expected="x", observed=f"got {_JWT}")
    assert _SK not in r.name and _JWT not in r.observed
