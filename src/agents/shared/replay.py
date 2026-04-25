"""Replay harness — minimal-spike (P0.1).

Captures one agent turn (user query → tool loop → final answer) into a
provider-neutral JSON fixture. The companion CLI ``scripts/replay_run.py``
validates fixtures statically against the current ``ToolRegistry`` and
system prompt — no LLM re-run.

Goal: before refactors that touch agent core (Phase B compression /
Phase C unified runner), capture a few real turns. After the refactor,
diff fixtures against current code to detect regressions in:

  - tool availability
  - tool argument shape / required keys
  - tool call sequence
  - system prompt drift (warning, not failure)

Out of scope for v1: streaming chunk capture, subagent traces,
compaction state, OpenAI path, deterministic LLM rerun.

Activation: set ``ARKSCOPE_REPLAY_CAPTURE=1``. Without the flag the
hook is a no-op (zero overhead).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ENV_FLAG = "ARKSCOPE_REPLAY_CAPTURE"
DEFAULT_OUTPUT_DIR = Path("data/replay")
SHAPE_MAX_DEPTH = 4
DIGEST_LEN = 16


def is_capture_enabled() -> bool:
    """True iff the capture env flag is set to a truthy value."""
    return os.environ.get(ENV_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Hash / digest / shape helpers
# ---------------------------------------------------------------------------


def hash_text(text: str) -> str:
    """SHA256 prefix of a string. Used for system_prompt_hash."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_LEN]


def digest_json(value: Any) -> str:
    """SHA256 prefix of a canonicalized JSON serialization.

    Sorts dict keys, uses tight separators, falls back to ``str()`` for
    non-JSON-native types (e.g. datetime, numpy types). Stable across
    runs given the same logical value.
    """
    try:
        canon = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        canon = repr(value)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:DIGEST_LEN]


def compute_shape(value: Any, depth: int = 0) -> Any:
    """Recursive type/key tree, depth-capped at SHAPE_MAX_DEPTH.

    Returns:
        - dict: ``{key: shape(value)}`` for each key
        - list: ``[shape(first_item)]`` (single-element representative; empty → ``[]``)
        - scalar: type name string ("str", "int", "float", "bool", "NoneType")
        - past max depth: "..."
    """
    if depth >= SHAPE_MAX_DEPTH:
        return "..."
    if isinstance(value, dict):
        return {k: compute_shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        return [compute_shape(value[0], depth + 1)]
    return type(value).__name__


def normalize_args(args: Any) -> Dict[str, Any]:
    """Return a dict view of tool arguments with sorted keys.

    Used so two captures with different insertion orders produce the
    same digest. Non-dict inputs are wrapped in ``{"_raw": ...}`` so the
    fixture stays a stable shape.
    """
    if not isinstance(args, dict):
        return {"_raw": args}
    return {k: args[k] for k in sorted(args.keys())}


def _coerce_result(result: Any) -> Any:
    """Best-effort decode of a tool result for shape/digest computation.

    Most tools return JSON strings (see ``src/tools/*``). Try to parse
    as JSON; fall back to the raw value if not.
    """
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (TypeError, ValueError):
            return result
    return result


# ---------------------------------------------------------------------------
# Trace dataclass
# ---------------------------------------------------------------------------


@dataclass
class CapturedToolCall:
    index: int
    name: str
    arguments: Dict[str, Any]
    arguments_digest: str
    result_digest: str
    result_shape: Any


@dataclass
class ReplayTrace:
    schema_version: int
    captured_at: str
    entrypoint: str  # cli | api | discord | test
    provider: str  # anthropic | openai
    model: str
    session_id: str
    turn_id: int
    system_prompt_hash: str
    user_input: str
    tools_available: List[str]
    tool_calls: List[CapturedToolCall] = field(default_factory=list)
    final_answer: str = ""
    final_answer_hash: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


class ReplayCapture:
    """Accumulates a single turn's data and writes it to disk on save().

    Lifecycle:

        cap = ReplayCapture(provider="anthropic", model="...", entrypoint="cli")
        cap.set_initial(question, system_prompt, [t["name"] for t in tools])
        # ... per tool call:
        cap.record_tool_call(name, arguments, result_str)
        # ... at end:
        cap.record_final(final_answer, usage)
        path = cap.save()
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        entrypoint: str = "cli",
        session_id: Optional[str] = None,
        turn_id: int = 1,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.entrypoint = entrypoint
        self.session_id = session_id or _new_session_id()
        self.turn_id = turn_id
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

        self._user_input: str = ""
        self._system_prompt_hash: str = ""
        self._tools_available: List[str] = []
        self._tool_calls: List[CapturedToolCall] = []
        self._final_answer: str = ""
        self._usage: Dict[str, Any] = {}
        self._notes: str = ""
        self._tool_call_index = 0

    # -- recording -----------------------------------------------------------

    def set_initial(
        self,
        question: str,
        system_prompt: str,
        tools_available: Sequence[str],
    ) -> None:
        self._user_input = question
        self._system_prompt_hash = hash_text(system_prompt)
        self._tools_available = sorted(tools_available)

    def record_tool_call(
        self,
        name: str,
        arguments: Any,
        result: Any,
    ) -> None:
        norm = normalize_args(arguments)
        decoded = _coerce_result(result)
        call = CapturedToolCall(
            index=self._tool_call_index,
            name=name,
            arguments=norm,
            arguments_digest=digest_json(norm),
            result_digest=digest_json(decoded),
            result_shape=compute_shape(decoded),
        )
        self._tool_calls.append(call)
        self._tool_call_index += 1

    def record_final(self, answer: str, usage: Optional[Dict[str, Any]] = None) -> None:
        self._final_answer = answer
        self._usage = dict(usage or {})

    def add_note(self, note: str) -> None:
        self._notes = (self._notes + "\n" + note).strip() if self._notes else note

    # -- assembly + save -----------------------------------------------------

    def to_trace(self) -> ReplayTrace:
        return ReplayTrace(
            schema_version=SCHEMA_VERSION,
            captured_at=datetime.now(timezone.utc).isoformat(),
            entrypoint=self.entrypoint,
            provider=self.provider,
            model=self.model,
            session_id=self.session_id,
            turn_id=self.turn_id,
            system_prompt_hash=self._system_prompt_hash,
            user_input=self._user_input,
            tools_available=self._tools_available,
            tool_calls=list(self._tool_calls),
            final_answer=self._final_answer,
            final_answer_hash=hash_text(self._final_answer) if self._final_answer else "",
            usage=self._usage,
            notes=self._notes,
        )

    def save(self, output_dir: Optional[Path] = None) -> Path:
        target_dir = Path(output_dir) if output_dir else self.output_dir
        session_dir = target_dir / self.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"turn_{self.turn_id:03d}.json"
        trace = self.to_trace()
        with path.open("w", encoding="utf-8") as f:
            json.dump(trace.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Replay capture saved: %s", path)
        return path


def _new_session_id() -> str:
    """Timestamped session id with short random suffix for uniqueness."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}_{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Validation against current registry
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""

    def render(self) -> str:
        lines: List[str] = []
        status = "PASS" if self.passed else "FAIL"
        lines.append(f"[{status}] {self.summary}")
        for w in self.warnings:
            lines.append(f"  WARN: {w}")
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        return "\n".join(lines)


def load_trace(path: Path) -> ReplayTrace:
    """Load and minimally validate a fixture file."""
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Trace must be a JSON object, got {type(data).__name__}")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version {data.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION})"
        )
    required = {
        "captured_at", "entrypoint", "provider", "model",
        "session_id", "turn_id", "system_prompt_hash",
        "user_input", "tools_available", "tool_calls",
    }
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Trace missing required fields: {sorted(missing)}")

    tool_calls = [
        CapturedToolCall(
            index=c["index"],
            name=c["name"],
            arguments=c.get("arguments", {}),
            arguments_digest=c.get("arguments_digest", ""),
            result_digest=c.get("result_digest", ""),
            result_shape=c.get("result_shape"),
        )
        for c in data["tool_calls"]
    ]
    return ReplayTrace(
        schema_version=data["schema_version"],
        captured_at=data["captured_at"],
        entrypoint=data["entrypoint"],
        provider=data["provider"],
        model=data["model"],
        session_id=data["session_id"],
        turn_id=data["turn_id"],
        system_prompt_hash=data["system_prompt_hash"],
        user_input=data["user_input"],
        tools_available=list(data["tools_available"]),
        tool_calls=tool_calls,
        final_answer=data.get("final_answer", ""),
        final_answer_hash=data.get("final_answer_hash", ""),
        usage=data.get("usage", {}),
        notes=data.get("notes", ""),
    )


def validate_trace_against_registry(
    trace: ReplayTrace,
    registry: Any,
    *,
    current_system_prompt: Optional[str] = None,
) -> ValidationResult:
    """Static diff: tool existence + argument shape compatibility + sequence.

    Does NOT call any LLM. Does NOT compare full tool results.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Tool availability set diff
    current_names = set(registry.list_names())
    captured_names = set(trace.tools_available)
    removed_from_registry = captured_names - current_names
    added_to_registry = current_names - captured_names
    if removed_from_registry:
        warnings.append(
            "Tools no longer registered (removed since capture): "
            + ", ".join(sorted(removed_from_registry))
        )
    if added_to_registry:
        warnings.append(
            "Tools newly registered (added since capture): "
            + ", ".join(sorted(added_to_registry))
        )

    # Per-call validation
    for call in trace.tool_calls:
        tool_def = registry.get(call.name)
        if tool_def is None:
            errors.append(
                f"tool_calls[{call.index}]: tool {call.name!r} not found in current registry"
            )
            continue
        param_names = {p.name for p in tool_def.parameters}
        required_names = {p.name for p in tool_def.parameters if p.required}
        captured_keys = set(call.arguments.keys()) - {"_raw"}

        # Captured key not in current schema → backward-incompat refactor
        unknown = captured_keys - param_names
        if unknown:
            errors.append(
                f"tool_calls[{call.index}] {call.name}: captured argument(s) "
                f"{sorted(unknown)} no longer accepted by tool"
            )
        # Required parameter not in captured args → tool got stricter
        missing_required = required_names - captured_keys
        if missing_required:
            errors.append(
                f"tool_calls[{call.index}] {call.name}: tool now requires "
                f"argument(s) {sorted(missing_required)} not present in capture"
            )

    # System prompt drift (warning only)
    if current_system_prompt is not None:
        current_hash = hash_text(current_system_prompt)
        if current_hash != trace.system_prompt_hash:
            warnings.append(
                f"system_prompt_hash drift: captured={trace.system_prompt_hash} "
                f"current={current_hash}"
            )

    passed = not errors
    summary = (
        f"{len(trace.tool_calls)} tool call(s), "
        f"{len(errors)} error(s), {len(warnings)} warning(s)"
    )
    return ValidationResult(passed=passed, errors=errors, warnings=warnings, summary=summary)