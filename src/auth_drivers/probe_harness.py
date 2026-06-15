"""Redacted probe harness — S3-prep skeleton (no live probe logic yet).

The safe runner for the live auth probes P1/P2/P3 (LLM_AUTH_DRIVER_PLAN.md §9):
record shape/status/error, NEVER persist tokens/PII, NEVER raise (except operator
signals), user-triggered only.

SECURITY MODEL (hardened after an adversarial leak review):
- PRIMARY control: a probe body MUST record response SHAPE/status, not raw token
  values, and MUST NOT itself log/re-raise with a live token in the message.
- SAFETY NET (this module): redact() is FAIL-CLOSED — it over-redacts rather than
  risk a leak (scrubs token shapes incl. base64 +/=, dotted/PASETO, percent- and
  newline-fragmented, short mixed-entropy creds, OAuth artifacts) AND email/account
  PII. A non-string observation is reduced to its TYPE NAME (never str()'d, so a
  structured __repr__ can't smuggle a fragmented token). Every ProbeResult str
  field is redacted at construction (defense-in-depth, even for direct callers).
This module has no file/network I/O of its own.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, model_validator

_REDACT = "[REDACTED]"

# Fail-closed redaction rules (specific → generic). Each scrubs a token/PII shape.
_RULES = [
    # email PII
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    # Authorization: Bearer <token>
    re.compile(r"[Bb]earer\s+\S+"),
    # value following a known secret key / prefix (assignment or prefix form)
    re.compile(
        r"\b(?:sk|ghp|gho|ghs|ghu|ghr|pat|acct|org|cus|user|key|tok|code|secret|password|"
        r"access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|api[_-]?key|"
        r"code[_-]?verifier|code[_-]?challenge|setup[_-]?token)"
        r"['\"]?\s*[:=_\-]\s*['\"]?[^\s'\"]{3,}",
        re.I,
    ),
    # JWT (eyJ...)
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)?"),
    # dotted multi-segment token (PASETO/JWE/opaque): >=4 base64ish segments
    re.compile(r"(?:[A-Za-z0-9_\-+/]{2,}\.){3,}[A-Za-z0-9_\-+/]{2,}"),
    # standard base64 blob — + and / are IN the class so they don't fragment the run
    re.compile(r"[A-Za-z0-9+/]{16,}={0,2}"),
    # percent-encoded run (url-encoded token)
    re.compile(r"(?:%[0-9A-Fa-f]{2}|[A-Za-z0-9+/=]){12,}"),
    # short-but-mixed-entropy opaque token: >=10 chars with lower AND upper AND digit
    re.compile(r"\b(?=[A-Za-z0-9_\-]*[a-z])(?=[A-Za-z0-9_\-]*[A-Z])(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{10,}\b"),
    # long generic run (base64url _ -) — require a digit so snake_case words survive
    re.compile(r"\b(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{20,}\b"),
]


def redact(text: Any) -> str:
    """Scrub token/PII-shaped material (fail-closed). Coercion is guarded so a
    pathological __str__ can't crash redaction. Short single-class strings
    (model ids, efforts, statuses) survive."""
    if text is None:
        return ""
    try:
        s = text if isinstance(text, str) else str(text)
    except Exception:  # noqa: BLE001 — a hostile __str__ must not break redaction
        return f"<unstringable {type(text).__name__}>"
    for pat in _RULES:
        s = pat.sub(_REDACT, s)
    return s


class ProbeResult(BaseModel):
    """A single probe outcome. extra=forbid + every str field redacted at
    construction — no field can carry a raw token, even via a direct caller."""

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    expected: str
    observed: str = ""
    error: str | None = None

    @model_validator(mode="after")
    def _redact_all_str_fields(self):  # defense-in-depth
        self.name = redact(self.name)
        self.expected = redact(self.expected)
        self.observed = redact(self.observed)
        self.error = redact(self.error) if self.error is not None else None
        return self


def _safe_str(exc: BaseException) -> str:
    """Stringify an exception without ever raising (a hostile __str__ leaks/raises)."""
    try:
        return str(exc)
    except Exception:  # noqa: BLE001
        try:
            return repr(getattr(exc, "args", "")) or "<unstringable>"
        except Exception:  # noqa: BLE001
            return "<unstringable>"


def _coerce_observation(out: Any) -> tuple[bool, str]:
    """(passed, observed). A NON-(str|tuple) observation is reduced to its TYPE
    NAME — never str()'d — so a structured __repr__ can't smuggle a fragmented
    token (plan §9: record SHAPE, not the raw object)."""
    if isinstance(out, tuple) and len(out) == 2:
        passed_raw, obs = out
        return bool(passed_raw), obs if isinstance(obs, str) else f"<{type(obs).__name__}>"
    if isinstance(out, str):
        return True, out
    return True, f"<{type(out).__name__}>"


def run_probe(name: str, *, expected: str, fn: Callable[[], Any]) -> ProbeResult:
    """Run a probe callable safely. `fn` returns an observation string or a
    ``(passed, observed)`` tuple. Operator signals (KeyboardInterrupt/SystemExit/
    GeneratorExit) propagate; any other exception → a failed (not raised) result.
    All emitted text is redacted at ProbeResult construction.

    CONTRACT: `fn` must record SHAPE/status (not raw token values) and must not
    itself log or re-raise with a live token in the message — the harness only
    redacts what `run_probe` emits.
    """
    try:
        passed, observed = _coerce_observation(fn())
        return ProbeResult(name=name, passed=passed, expected=expected, observed=observed)
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        raise  # operator/runtime signals must NOT be swallowed as a benign failure
    except Exception as exc:  # noqa: BLE001 — a probe failure must never propagate
        return ProbeResult(name=name, passed=False, expected=expected,
                            error=f"{type(exc).__name__}: {_safe_str(exc)}")
