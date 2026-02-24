"""
Interactive CLI chat for MindfulRL agents.

Run:
    python -m src.agents
    python -m src.agents --provider anthropic
    python -m src.agents --provider openai

Slash commands (during chat):
    /model          Show available models and switch
    /model <name>   Switch to model by name or shorthand
    /reasoning      Pick reasoning effort interactively (OpenAI)
    /reasoning <n>  Set: none|minimal|low|medium|high|xhigh
    /effort         Pick effort level interactively (Anthropic, model-aware)
    /effort <n>     Set: max|high|medium|low
    /thinking       Toggle extended thinking on/off (Anthropic)
    /context        Toggle 1M context beta on/off (Anthropic)
    /skill          Run a predefined skill workflow (e.g. /skill full_analysis NVDA)
    /subagent       View/change subagent models (persisted to local config)
    /code-backend   Show/set code gen backend (api/codex/claude)
    /scratchpad     List recent agent session logs (JSONL)
    /history        Show recent chat history (Q&A pairs)
    /turns          Show/set max tool calls per query
    /save           Save session exchanges as report
    /reports        List saved research reports
    /status         Show current session config
    help            Show all commands
    clear           Clear conversation history
    quit            Exit
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console


def _load_env():
    """Load API keys from config/.env into environment."""
    env_path = Path("config/.env")
    if not env_path.exists():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Only set if not already in environment
            if key and value and key not in os.environ:
                os.environ[key] = value


_load_env()
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich import box

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import ANSI

from .config import get_agent_config, ReasoningEffort
from .shared.attachments import Attachment, AttachmentManager
from .shared.prompts import SYSTEM_PROMPT
from .shared.scratchpad import ChatHistory, Scratchpad, _safe_serialize
from .shared.subagent import _EXTENDED_CONTEXT_BETA, _use_extended_context
from .shared.context_manager import ContextManager
from .shared.token_tracker import TokenTracker

console = Console()
logger = logging.getLogger(__name__)


# ============================================================
# Model Catalog
# ============================================================

@dataclass
class ModelEntry:
    """A model available for selection."""
    id: str
    provider: str  # "anthropic" or "openai"
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""


# Canonical model list — update here when new models are available
MODEL_CATALOG: List[ModelEntry] = [
    ModelEntry(
        id="claude-opus-4-6",
        provider="anthropic",
        name="Opus 4.6",
        aliases=["opus", "opus4.6", "opus-4.6", "o46", "claude-opus"],
        description="Most intelligent — deep analysis & reasoning (128K output, $5/$25)",
    ),
    ModelEntry(
        id="claude-sonnet-4-6",
        provider="anthropic",
        name="Sonnet 4.6",
        aliases=["sonnet", "sonnet4.6", "sonnet-4.6", "s46", "claude-sonnet", "claude"],
        description="Fast + intelligent — financial analysis (64K output, $3/$15)",
    ),
    ModelEntry(
        id="gpt-5.2",
        provider="openai",
        name="GPT-5.2",
        aliases=["gpt5", "gpt-5", "gpt5.2", "5.2"],
        description="SOTA reasoning with configurable effort",
    ),
    # Codex series — optimized for agentic coding
    ModelEntry(
        id="gpt-5.2-codex",
        provider="openai",
        name="GPT-5.2 Codex",
        aliases=["codex", "codex5.2", "5.2-codex"],
        description="Agentic coding — long-horizon, refactors, migrations",
    ),
    # gpt-5.3-codex: API not yet available (Codex CLI only), add when released
]


def find_model(query: str) -> Optional[ModelEntry]:
    """Find a model by ID, name, or alias (case-insensitive)."""
    q = query.lower().strip()
    for m in MODEL_CATALOG:
        if q == m.id.lower() or q == m.name.lower():
            return m
        if q in [a.lower() for a in m.aliases]:
            return m
    # Partial match on id
    for m in MODEL_CATALOG:
        if q in m.id.lower():
            return m
    return None


# ============================================================
# Session State
# ============================================================

@dataclass
class SessionState:
    """Mutable state for the current chat session."""
    provider: str  # "anthropic" or "openai"
    model: Optional[str]  # None = use config default
    reasoning_effort: Optional[str]
    no_history: bool
    verbose: bool
    messages_history: Optional[List[dict]] = field(default=None)
    anthropic_effort: Optional[str] = None
    anthropic_thinking: bool = False
    extended_context: bool = False  # 1M context beta (Anthropic only)
    server_compaction: bool = False  # Server-side compaction L2 (Anthropic + OpenAI)
    code_model: str = ""  # Code generation model (empty = auto)
    code_backend: str = "api"  # api | codex | codex-apikey | claude | claude-apikey
    max_tool_calls: Optional[int] = None  # None = use config default
    attachments: List[Attachment] = field(default_factory=list)
    chat_history: Optional["ChatHistory"] = None  # Per-session chat history

    def effective_model(self) -> str:
        """Return the active model ID."""
        config = get_agent_config()
        if self.model:
            return self.model
        if self.provider == "openai":
            return config.openai_model
        return config.anthropic_model

    def effective_reasoning(self) -> str:
        config = get_agent_config()
        return self.reasoning_effort or config.reasoning_effort

    def status_line(self) -> str:
        """One-line status string."""
        parts = [f"Provider: {self.provider}", f"Model: {self.effective_model()}"]
        if self.provider == "openai":
            parts.append(f"Reasoning: {self.effective_reasoning()}")
        elif self.provider == "anthropic":
            effort = self.anthropic_effort or get_agent_config().anthropic_effort or "default"
            parts.append(f"Effort: {effort}")
            if self.anthropic_thinking:
                parts.append("Thinking: ON")
            if self.extended_context:
                parts.append("Context: 1M")
        if self.server_compaction:
            parts.append("Compaction: L2")
        if self.code_model:
            parts.append(f"CodeModel: {self.code_model}")
        if self.code_backend != "api":
            parts.append(f"CodeBackend: {self.code_backend}")
        if self.max_tool_calls:
            parts.append(f"MaxTurns: {self.max_tool_calls}")
        history = "on" if not self.no_history else "off"
        parts.append(f"History: {history}")
        return " | ".join(parts)


# ============================================================
# Slash Command Autocomplete
# ============================================================

# Command definitions: (name, aliases, description, sub_options_fn or None)
# sub_options_fn receives SessionState and returns list of (value, description) tuples
_SLASH_COMMANDS = [
    ("/model", "/m", "Show models & switch"),
    ("/code-model", "/cm", "Set code generation model"),
    ("/code-backend", "/cb", "Set code generation backend"),
    ("/reasoning", "/r", "Set reasoning effort (OpenAI)"),
    ("/effort", "/e", "Set effort level (Anthropic)"),
    ("/thinking", "/t", "Toggle extended thinking (Anthropic)"),
    ("/context", "/ctx", "Toggle 1M context beta (Anthropic)"),
    ("/compaction", "/cmp", "Toggle server-side compaction L2"),
    ("/skill", "/sk", "Run a predefined skill workflow"),
    ("/subagent", "/sa", "View/change subagent models"),
    ("/scratchpad", "/pad", "List recent scratchpad sessions"),
    ("/history", "/h", "Show recent chat history (Q&A pairs)"),
    ("/turns", "", "Set max tool calls per query"),
    ("/attach", "/at", "Attach file (PDF/image/text) to next query"),
    ("/save", "/sv", "Save chat exchanges as report"),
    ("/reports", "/rp", "List saved research reports"),
    ("/memory", "/mem", "Manage long-term memories"),
    ("/monitor", "/mon", "Scan watchlist for alerts"),
    ("/status", "/s", "Show session config"),
    ("/help", "", "Show all commands"),
]

_REASONING_OPTIONS = [
    ("none", "No reasoning"),
    ("minimal", "Minimal reasoning"),
    ("low", "Low effort"),
    ("medium", "Medium effort"),
    ("high", "High effort"),
    ("xhigh", "Extra high effort"),
]

_THINKING_OPTIONS = [
    ("on", "Enable extended thinking"),
    ("off", "Disable extended thinking"),
]

_CONTEXT_OPTIONS = [
    ("on", "Enable 1M context beta"),
    ("off", "Disable 1M context (standard 200K)"),
]

_COMPACTION_OPTIONS = [
    ("on", "Enable server-side compaction L2 (Anthropic + OpenAI)"),
    ("off", "Disable server-side compaction"),
]

_CODE_BACKEND_OPTIONS = [
    ("api", "Direct API call (default)"),
    ("codex", "Codex CLI (subscription)"),
    ("codex-apikey", "Codex CLI (API key)"),
    ("claude", "Claude Code (subscription)"),
    ("claude-apikey", "Claude Code (API key)"),
]

_SKILL_NAMES = [
    ("full_analysis", "Comprehensive single-ticker entry analysis"),
    ("portfolio_scan", "Watchlist-wide screening"),
    ("earnings_prep", "Pre-earnings risk assessment"),
    ("sector_rotation", "Cross-sector rotation analysis"),
]

_SUBAGENT_NAMES = [
    ("code_analyst", "Quantitative Python analysis"),
    ("deep_researcher", "Multi-source investigation"),
    ("data_summarizer", "Fast bulk summarization"),
    ("reviewer", "Critical analysis review"),
]


def _get_effort_completions(state: SessionState):
    """Return effort options as (value, description) tuples for the current model."""
    options = _get_effort_options_for_model(state.effective_model())
    if options is None:
        return []
    descs = {"max": "Maximum (Opus 4.6 only)", "high": "High", "medium": "Medium", "low": "Low"}
    return [(opt, descs.get(opt, "")) for opt in options]


def _get_model_completions():
    """Return model names/aliases for /model completion."""
    results = []
    for m in MODEL_CATALOG:
        results.append((m.id, f"{m.name} ({m.provider})"))
        for alias in m.aliases[:3]:
            results.append((alias, f"→ {m.name}"))
    return results


class SlashCompleter(Completer):
    """Autocomplete for slash commands with context-aware sub-options."""

    def __init__(self, state: SessionState):
        self.state = state

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # Only complete if starts with /
        if not text.startswith("/"):
            return

        parts = text.split(None, 1)
        cmd_text = parts[0].lower()

        if len(parts) == 1 and not text.endswith(" "):
            # Completing command name: /rea... → /reasoning
            for name, alias, desc in _SLASH_COMMANDS:
                if name.startswith(cmd_text):
                    yield Completion(name, start_position=-len(cmd_text), display_meta=desc)
                elif alias and alias.startswith(cmd_text):
                    yield Completion(alias, start_position=-len(cmd_text), display_meta=f"→ {name}")
        else:
            # Completing sub-options: /reasoning x... → xhigh
            sub_text = parts[1].strip().lower() if len(parts) > 1 else ""
            options = self._get_sub_options(cmd_text)
            for value, desc in options:
                if value.startswith(sub_text):
                    yield Completion(value, start_position=-len(sub_text), display_meta=desc)

    def _get_sub_options(self, cmd: str):
        if cmd in ("/reasoning", "/r"):
            return _REASONING_OPTIONS
        elif cmd in ("/effort", "/e"):
            return _get_effort_completions(self.state)
        elif cmd in ("/thinking", "/t"):
            return _THINKING_OPTIONS
        elif cmd in ("/context", "/ctx"):
            return _CONTEXT_OPTIONS
        elif cmd in ("/compaction", "/cmp"):
            return _COMPACTION_OPTIONS
        elif cmd in ("/skill", "/sk"):
            return _SKILL_NAMES
        elif cmd in ("/subagent", "/sa"):
            return _SUBAGENT_NAMES
        elif cmd in ("/model", "/m"):
            return _get_model_completions()
        elif cmd in ("/code-model", "/cm"):
            return [("auto", "Use default model")] + _get_model_completions()
        elif cmd in ("/code-backend", "/cb"):
            return _CODE_BACKEND_OPTIONS
        return []


# ============================================================
# Display Helpers
# ============================================================

def print_banner():
    """Print startup banner."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]MindfulRL[/bold cyan] [dim]Interactive Agent[/dim]\n"
            "[dim]Type your question, or /help for commands[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def print_help():
    """Print all available commands."""
    console.print(
        Panel(
            "[bold]Slash Commands[/bold]\n"
            "  [cyan]/model[/cyan]              Show models & switch interactively\n"
            "  [cyan]/model <name>[/cyan]       Switch model (e.g. /model opus, /model gpt5)\n"
            "  [cyan]/code-model[/cyan]         Pick code generation model interactively\n"
            "  [cyan]/code-model <n>[/cyan]     Set code model (e.g. /code-model opus, /cm auto)\n"
            "  [cyan]/code-backend[/cyan]       Show/set code gen backend (api/codex/claude)\n"
            "  [cyan]/code-backend <n>[/cyan]   Set: api|codex|codex-apikey|claude|claude-apikey\n"
            "  [cyan]/reasoning[/cyan]          Pick reasoning effort interactively (OpenAI)\n"
            "  [cyan]/reasoning <n>[/cyan]      Set: none|minimal|low|medium|high|xhigh\n"
            "  [cyan]/effort[/cyan]             Pick effort level interactively (Anthropic, model-aware)\n"
            "  [cyan]/effort <n>[/cyan]         Set: max|high|medium|low\n"
            "  [cyan]/thinking[/cyan]           Toggle extended thinking on/off (Anthropic)\n"
            "  [cyan]/context[/cyan]            Toggle 1M context beta on/off (Anthropic)\n"
            "  [cyan]/skill[/cyan]              List available analysis skills\n"
            "  [cyan]/skill <name> [args][/cyan] Run a skill (e.g. /skill full_analysis NVDA)\n"
            "  [cyan]/subagent[/cyan]           View/change subagent models\n"
            "  [cyan]/subagent <name>[/cyan]    Change a subagent's model (e.g. /subagent code_analyst opus)\n"
            "  [cyan]/scratchpad[/cyan]         List recent agent session logs\n"
            "  [cyan]/scratchpad <id>[/cyan]    View details of a session log\n"
            "  [cyan]/history[/cyan]            Show recent chat history (Q&A pairs)\n"
            "  [cyan]/history <N>[/cyan]        Show last N conversations\n"
            "  [cyan]/turns[/cyan]              Show/set max tool calls per query (e.g. /turns 30)\n"
            "  [cyan]/attach <path>[/cyan]       Attach file (PDF/image/text) to next query\n"
            "  [cyan]/attach <path> <pages>[/cyan] Attach PDF pages (e.g. /attach report.pdf 1-5)\n"
            "  [cyan]/attach list[/cyan]        List pending attachments\n"
            "  [cyan]/attach clear[/cyan]       Clear all attachments\n"
            "  [cyan]/save[/cyan]               Save session exchanges as report\n"
            "  [cyan]/save <N>[/cyan]           Save last N exchanges\n"
            "  [cyan]/save <N-M>[/cyan]         Save exchanges #N to #M\n"
            "  [cyan]/save <N> \"title\"[/cyan]   Save with custom title\n"
            "  [cyan]/reports[/cyan]            List saved research reports\n"
            "  [cyan]/reports <id>[/cyan]       View a specific report\n"
            "  [cyan]/reports <TICKER>[/cyan]   Filter reports by ticker\n"
            "  [cyan]/memory[/cyan]             List recent memories\n"
            "  [cyan]/memory save[/cyan]        Save a new memory manually\n"
            "  [cyan]/memory search <q>[/cyan]  Search memories\n"
            "  [cyan]/memory <id>[/cyan]        View a specific memory\n"
            "  [cyan]/memory delete <id>[/cyan] Delete a memory\n"
            "  [cyan]/status[/cyan]             Show current session config\n"
            "\n[bold]General[/bold]\n"
            "  [cyan]clear[/cyan]               Clear conversation history\n"
            "  [cyan]quit[/cyan]                Exit\n"
            "\n[dim]Ask anything about your watchlist tickers, "
            "news, prices, IV, signals, etc.[/dim]",
            title="[bold]Help[/bold]",
            title_align="left",
            border_style="dim",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def print_model_picker(current_model: str) -> Optional[ModelEntry]:
    """
    Display the model catalog and prompt user to pick one.

    Returns the selected ModelEntry, or None if cancelled.
    """
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Model", style="cyan")
    table.add_column("Provider")
    table.add_column("Description", style="dim")
    table.add_column("", width=3)  # active marker

    for i, m in enumerate(MODEL_CATALOG, 1):
        marker = "[bold green]*[/bold green]" if m.id == current_model else ""
        table.add_row(
            str(i),
            f"{m.name} [dim]({m.id})[/dim]",
            m.provider,
            m.description,
            marker,
        )

    console.print()
    console.print(table)
    console.print("[dim]Enter number, name, or 'q' to cancel:[/dim]", end=" ")

    try:
        choice = console.input("").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not choice or choice.lower() in ("q", "cancel"):
        return None

    # Try numeric selection
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(MODEL_CATALOG):
            return MODEL_CATALOG[idx]
    except ValueError:
        pass

    # Try name/alias lookup
    return find_model(choice)


def print_tool_call(tool_name: str, tool_input: dict, index: int):
    """Display a tool call in progress."""
    # Summarize input
    summary_parts = []
    for k, v in tool_input.items():
        if isinstance(v, str) and len(v) < 30:
            summary_parts.append(f"{k}={v}")
        elif isinstance(v, (int, float)):
            summary_parts.append(f"{k}={v}")
        elif isinstance(v, list) and len(v) <= 3:
            summary_parts.append(f"{k}={v}")
    summary = ", ".join(summary_parts) if summary_parts else "..."

    console.print(
        f"  [dim]#{index}[/dim] [yellow]{tool_name}[/yellow]"
        f"[dim]({summary})[/dim]"
    )


def print_tool_result_summary(tool_name: str, result_str: str):
    """Display abbreviated tool result."""
    try:
        data = json.loads(result_str)
        if isinstance(data, dict):
            if "error" in data:
                console.print(f"     [red]error: {data['error']}[/red]")
            elif "count" in data:
                console.print(f"     [dim]{data.get('count', '?')} results[/dim]")
            elif "change_pct" in data:
                pct = data["change_pct"]
                color = "green" if pct >= 0 else "red"
                console.print(f"     [{color}]{pct:+.2f}%[/{color}]")
            elif "current_iv" in data:
                iv = data.get("current_iv")
                console.print(f"     [dim]IV={iv}[/dim]")
            elif "action" in data:
                console.print(f"     [dim]{data['action']}[/dim]")
            elif "ticker_count" in data:
                console.print(f"     [dim]{data['ticker_count']} tickers[/dim]")
        elif isinstance(data, list):
            console.print(f"     [dim]{len(data)} items[/dim]")
    except (json.JSONDecodeError, TypeError):
        pass


def print_answer(answer: str):
    """Display the final answer."""
    console.print()
    console.print(Panel(
        Markdown(answer),
        border_style="green",
        title="[bold green]Answer[/bold green]",
        title_align="left",
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    console.print()


def print_summary(
    tools_used: List[str],
    elapsed: float,
    scratchpad_path: Optional[str] = None,
    token_usage: Optional[Dict[str, Any]] = None,
):
    """Print query summary."""
    parts = []
    if tools_used:
        tool_str = ", ".join(sorted(set(tools_used)))
        parts.append(f"Tools: {tool_str}")
    parts.append(f"{elapsed:.1f}s")
    if token_usage:
        tin = token_usage.get("total_input_tokens", 0)
        tout = token_usage.get("total_output_tokens", 0)
        turns = token_usage.get("turn_count", 0)
        parts.append(f"Tokens: {tin:,}in/{tout:,}out ({turns} turns)")
        # Cache stats
        cc = token_usage.get("cache_creation_tokens", 0)
        cr = token_usage.get("cache_read_tokens", 0)
        if cc or cr:
            parts.append(f"Cache: {cr:,}read/{cc:,}write")
        # Web search stats
        ws = token_usage.get("web_search_requests", 0)
        if ws:
            parts.append(f"WebSearch: {ws}")
    if scratchpad_path:
        parts.append(f"Log: {scratchpad_path}")
    console.print(f"[dim]{' | '.join(parts)}[/dim]")


def _log_agent_query(
    dal: Any,
    question: str,
    result: dict,
    state: "SessionState",
    elapsed: float,
) -> None:
    """Log a completed query to agent_queries table (best-effort, no errors)."""
    try:
        if not hasattr(dal, '_backend') or not hasattr(dal._backend, 'insert_agent_query'):
            return
        usage = result.get("token_usage", {})
        dal._backend.insert_agent_query(
            question=question,
            answer=result.get("answer", "")[:2000],  # Truncate for DB
            provider=state.provider,
            model=state.model,
            tools_used=result.get("tools_used"),
            duration_ms=int(elapsed * 1000),
            tokens_in=usage.get("input_tokens") or usage.get("prompt_tokens"),
            tokens_out=usage.get("output_tokens") or usage.get("completion_tokens"),
        )
    except Exception:
        pass  # Best-effort logging, never fail the query


# ============================================================
# Anthropic Interactive Loop
# ============================================================

def run_anthropic_interactive(
    question: str,
    dal: Any,
    model: Optional[str] = None,
    messages_history: Optional[List[dict]] = None,
    effort: Optional[str] = None,
    thinking: bool = False,
    extended_context: bool = False,
    max_tool_calls: Optional[int] = None,
    attachments: Optional[List[Attachment]] = None,
    chat_history: Optional["ChatHistory"] = None,
) -> Dict[str, Any]:
    """
    Run Anthropic agent with live tool call display.

    Returns dict with answer, tools_used, messages (for conversation continuity).
    """
    from anthropic import Anthropic
    from .anthropic_agent.tools import get_anthropic_tools, execute_tool
    from .anthropic_agent.agent import (
        _supports_effort, _build_thinking_param,
        _prepare_cached_system, _prepare_cached_tools,
    )

    config = get_agent_config()
    model_name = model or config.anthropic_model
    client = Anthropic()
    tools = get_anthropic_tools()

    # Conditionally add Claude web search server tool
    if config.web_claude_search:
        from .anthropic_agent.agent import _CLAUDE_WEB_SEARCH_TOOL
        tools.append({**_CLAUDE_WEB_SEARCH_TOOL, "max_uses": config.web_claude_max_uses})

    tools_used: List[str] = []
    _tool_calls_detail: List[Dict[str, Any]] = []
    _tickers: set = set()
    tool_index = 0
    tracker = TokenTracker()
    _query_start = time.time()
    pad = Scratchpad(query=question, provider="anthropic", model=model_name)
    ctx = ContextManager(
        model=model_name,
        threshold_ratio=config.context_threshold_ratio,
        keep_recent_turns=config.context_keep_recent_turns,
        preview_chars=config.context_preview_chars,
    )

    # Build optional API params (effort + thinking)
    api_kwargs: Dict[str, Any] = {}

    effective_effort = effort or config.anthropic_effort
    if effective_effort and _supports_effort(model_name):
        api_kwargs["output_config"] = {"effort": effective_effort}

    thinking_param, effective_max_tokens = _build_thinking_param(
        model_name, thinking or config.anthropic_thinking, config,
    )
    if thinking_param:
        api_kwargs["thinking"] = thinking_param

    # Apply prompt caching: cache_control on tools (last) + system prompt
    tools = _prepare_cached_tools(tools)
    cached_system = _prepare_cached_system(SYSTEM_PROMPT)

    # Build user message (with optional attachment content blocks)
    if attachments:
        content_blocks = AttachmentManager.to_anthropic_blocks(attachments)
        content_blocks.append({"type": "text", "text": question})
        user_msg = {"role": "user", "content": content_blocks}
    else:
        user_msg = {"role": "user", "content": question}

    if messages_history is not None:
        messages = messages_history + [user_msg]
    else:
        messages = [user_msg]

    # 1M context beta
    use_beta = _use_extended_context(model_name, extended_context)

    status_parts = [f"Model: {model_name}"]
    if effective_effort:
        status_parts.append(f"effort: {effective_effort}")
    if thinking or config.anthropic_thinking:
        status_parts.append("thinking: ON")
    if use_beta:
        status_parts.append("context: 1M")
    console.print(f"[dim]{' | '.join(status_parts)}[/dim]")

    effective_max_turns = max_tool_calls or config.max_tool_calls
    for turn in range(effective_max_turns):
        stream_kwargs = dict(
            model=model_name,
            max_tokens=effective_max_tokens,
            system=cached_system,
            tools=tools,
            messages=messages,
            **api_kwargs,
        )

        with console.status("[cyan]Thinking...", spinner="dots"):
            if use_beta:
                stream_ctx = client.beta.messages.stream(
                    betas=[_EXTENDED_CONTEXT_BETA],
                    **stream_kwargs,
                )
            else:
                stream_ctx = client.messages.stream(**stream_kwargs)

            with stream_ctx as stream:
                response = stream.get_final_message()

        tracker.record_anthropic(response, model=model_name)

        # Display thinking blocks (extended thinking)
        for block in response.content:
            if block.type == "thinking":
                console.print(Panel(
                    Markdown(block.thinking),
                    title="[dim]Thinking[/dim]",
                    border_style="dim",
                    box=box.ROUNDED,
                    padding=(0, 1),
                ))

        # Handle pause_turn (Claude web search mid-turn pause)
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        # Done - no more tool calls
        if response.stop_reason != "tool_use":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            elapsed = time.time() - _query_start
            pad.log_final_answer(final_text, tools_used=list(set(tools_used)))
            pad.close()

            # Record Q&A pair in chat history (per-session)
            if chat_history:
                chat_history.append(
                    user_message=question,
                    agent_response=final_text,
                    provider="anthropic",
                    model=model_name,
                    tools_used=list(set(tools_used)),
                    elapsed_seconds=elapsed,
                    tickers=sorted(_tickers) if _tickers else None,
                    tool_calls_detail=_tool_calls_detail or None,
                    token_usage=tracker.summary() or None,
                )

            # Update messages for conversation continuity
            messages.append({"role": "assistant", "content": response.content})

            return {
                "answer": final_text,
                "tools_used": tools_used,
                "messages": messages,
                "scratchpad_path": str(pad.filepath) if pad.filepath else None,
                "token_usage": tracker.summary(),
            }

        # Process tool calls
        tool_use_blocks = [
            b for b in response.content if b.type == "tool_use"
        ]

        # Show any text before tool calls
        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                console.print(f"[dim italic]{block.text.strip()}[/dim italic]")

        if tool_use_blocks:
            console.print("[bold]Tools:[/bold]")

        tool_results = []
        for tool_use in tool_use_blocks:
            tool_index += 1
            tool_name = tool_use.name
            tool_input = tool_use.input

            tools_used.append(tool_name)
            print_tool_call(tool_name, tool_input, tool_index)

            # Extract tickers from tool params
            if isinstance(tool_input, dict):
                for k in ("ticker", "tickers"):
                    v = tool_input.get(k)
                    if isinstance(v, str) and v:
                        _tickers.add(v.upper())
                    elif isinstance(v, list):
                        _tickers.update(t.upper() for t in v if isinstance(t, str))

            # Execute with spinner
            with console.status("", spinner="dots"):
                result = execute_tool(tool_name, tool_input, dal)

            pad.log_tool_result(tool_name, result_data=result, tool_input=tool_input)
            print_tool_result_summary(tool_name, result)

            # Collect tool call detail for ChatHistory
            _tool_calls_detail.append({
                "name": tool_name,
                "params": _safe_serialize(tool_input) if isinstance(tool_input, dict) else {},
                "result_preview": result[:200] if isinstance(result, str) else str(result)[:200],
            })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        # Append to message history
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # L1: Compact old tool results if context is growing too large
        if ctx.should_compact(tracker):
            messages, compact_stats = ctx.compact_messages(messages)
            logger.info(f"CLI context compacted: {compact_stats}")

    partial_text = (
        f"Reached maximum tool calls ({effective_max_turns}). "
        f"Used {len(set(tools_used))} unique tools across {tool_index} calls. "
        "Try /turns to increase the limit, or ask a more focused question."
    )

    pad.log_max_turns(tools_used=list(set(tools_used)))
    pad.close()

    # Record Q&A pair in chat history (even for max turns)
    if chat_history:
        chat_history.append(
            user_message=question,
            agent_response=partial_text,
            provider="anthropic",
            model=model_name,
            tools_used=list(set(tools_used)),
            elapsed_seconds=time.time() - _query_start,
            tickers=sorted(_tickers) if _tickers else None,
            tool_calls_detail=_tool_calls_detail or None,
            token_usage=tracker.summary() or None,
        )

    return {
        "answer": partial_text,
        "tools_used": tools_used,
        "messages": messages,
        "scratchpad_path": str(pad.filepath) if pad.filepath else None,
        "token_usage": tracker.summary(),
    }


# ============================================================
# OpenAI Interactive Loop
# ============================================================

def run_openai_interactive(
    question: str,
    dal: Any,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    max_tool_calls: Optional[int] = None,
    attachments: Optional[List[Attachment]] = None,
    chat_history: Optional["ChatHistory"] = None,
) -> Dict[str, Any]:
    """
    Run OpenAI agent query with status display.

    Note: OpenAI Agents SDK handles the tool loop internally,
    so we can't show individual tool calls in real-time.
    """
    import asyncio
    from .openai_agent.agent import run_query

    config = get_agent_config()
    model_name = model or config.openai_model
    effort = reasoning_effort or config.reasoning_effort
    console.print(f"[dim]Model: {model_name} | reasoning: {effort}[/dim]")

    _query_start = time.time()
    with console.status("[cyan]Running agent...", spinner="dots"):
        result = asyncio.run(run_query(
            question=question,
            model=model_name,
            dal=dal,
            reasoning_effort=effort,
            max_tool_calls=max_tool_calls,
            attachments=attachments,
        ))

    # Record Q&A pair in chat history (per-session)
    if chat_history:
        chat_history.append(
            user_message=question,
            agent_response=result["answer"],
            provider="openai",
            model=model_name,
            tools_used=result.get("tools_used", []),
            elapsed_seconds=time.time() - _query_start,
            tickers=result.get("tickers") or None,
            tool_calls_detail=result.get("tool_calls_detail") or None,
            token_usage=result.get("token_usage") or None,
        )

    return {
        "answer": result["answer"],
        "tools_used": result["tools_used"],
        "messages": None,  # OpenAI SDK doesn't expose message history
        "scratchpad_path": None,  # Created inside run_query()
        "token_usage": result.get("token_usage", {}),
    }


# ============================================================
# Slash Command Handlers
# ============================================================

VALID_REASONING = ("none", "minimal", "low", "medium", "high", "xhigh")
VALID_ANTHROPIC_EFFORT = ("max", "high", "medium", "low")

# 每個 Anthropic 模型支援的 effort 選項（prefix match）
_EFFORT_OPTIONS_BY_MODEL = {
    "claude-opus-4-6": ("max", "high", "medium", "low"),
    "claude-sonnet-4-6": ("high", "medium", "low"),
}


def _get_effort_options_for_model(model: str):
    """Return valid effort options for the given model, or None if unsupported."""
    for prefix, options in _EFFORT_OPTIONS_BY_MODEL.items():
        if model.startswith(prefix):
            return options
    return None


def print_reasoning_picker(current: str):
    """Display reasoning effort options and prompt user to pick one."""
    options = VALID_REASONING

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Reasoning Effort", style="cyan")
    table.add_column("", width=3)

    for i, opt in enumerate(options, 1):
        marker = "[bold green]*[/bold green]" if opt == current else ""
        table.add_row(str(i), opt, marker)

    console.print()
    console.print(table)
    console.print("[dim]Enter number, name, or 'q' to cancel:[/dim]", end=" ")

    try:
        choice = console.input("").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not choice or choice.lower() in ("q", "cancel"):
        return None

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass

    if choice.lower() in options:
        return choice.lower()

    return None


def print_effort_picker(current: str, model: str):
    """Display model-aware effort options and prompt user to pick one."""
    options = _get_effort_options_for_model(model)

    if options is None:
        supported = ", ".join(
            f"{prefix} ({', '.join(opts)})"
            for prefix, opts in _EFFORT_OPTIONS_BY_MODEL.items()
        )
        console.print(
            f"[yellow]Effort is not supported for {model}.[/yellow]\n"
            f"[dim]Supported models: {supported}[/dim]\n"
        )
        return None

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Effort Level", style="cyan")
    table.add_column("", width=3)

    for i, opt in enumerate(options, 1):
        marker = "[bold green]*[/bold green]" if opt == current else ""
        table.add_row(str(i), opt, marker)

    console.print()
    console.print(table)
    console.print("[dim]Enter number, name, or 'q' to cancel:[/dim]", end=" ")

    try:
        choice = console.input("").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not choice or choice.lower() in ("q", "cancel"):
        return None

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass

    if choice.lower() in options:
        return choice.lower()

    return None


def handle_model_command(state: SessionState, arg: str) -> None:
    """Handle /model [name] command."""
    if arg:
        # Direct switch: /model opus
        entry = find_model(arg)
        if entry is None:
            console.print(f"[red]Unknown model: {arg}[/red]")
            console.print(
                "[dim]Try: "
                + ", ".join(a for m in MODEL_CATALOG for a in m.aliases[:2])
                + "[/dim]\n"
            )
            return
    else:
        # Interactive picker
        entry = print_model_picker(state.effective_model())
        if entry is None:
            console.print("[dim]Cancelled.[/dim]\n")
            return

    old_provider = state.provider
    state.provider = entry.provider
    state.model = entry.id

    # Clear history when switching providers (message formats differ)
    if old_provider != entry.provider and state.messages_history is not None:
        state.messages_history = []
        console.print("[dim]Conversation cleared (provider changed).[/dim]")

    console.print(
        f"[green]Switched to[/green] [bold cyan]{entry.name}[/bold cyan] "
        f"[dim]({entry.id})[/dim]\n"
    )


def handle_reasoning_command(state: SessionState, arg: str) -> None:
    """Handle /reasoning [effort] command."""
    if not arg:
        selected = print_reasoning_picker(state.effective_reasoning())
        if selected is None:
            console.print("[dim]Cancelled.[/dim]\n")
            return
        state.reasoning_effort = selected
        console.print(f"[green]Reasoning effort set to[/green] [bold]{selected}[/bold]\n")
        return

    if arg.lower() not in VALID_REASONING:
        console.print(
            f"[red]Invalid reasoning effort: {arg}[/red]\n"
            f"[dim]Valid: {', '.join(VALID_REASONING)}[/dim]\n"
        )
        return

    state.reasoning_effort = arg.lower()
    console.print(f"[green]Reasoning effort set to[/green] [bold]{arg.lower()}[/bold]\n")


def handle_skill_command(state: SessionState, arg: str) -> Optional[str]:
    """Handle /skill [name] [params] command.

    Returns expanded prompt string if a skill should be executed (caller
    should feed it to the agent). Returns None if the command was fully
    handled (listed skills or showed an error).
    """
    from .shared.skills import SKILL_REGISTRY, expand_skill, list_skills, parse_skill_command

    if not arg:
        # List all skills
        skills = list_skills()
        table = Table(title="Available Skills", box=box.SIMPLE_HEAVY)
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Params", style="dim")
        table.add_column("Aliases", style="dim")
        for s in skills:
            table.add_row(s["name"], s["description"], s["required_params"], s["aliases"])
        console.print(table)
        console.print("[dim]Usage: /skill <name> [args]  (e.g. /skill full_analysis NVDA)[/dim]\n")
        return None

    skill_name, params = parse_skill_command(arg)
    if skill_name is None:
        return None

    if skill_name not in SKILL_REGISTRY:
        # Check if it was an unresolved alias
        console.print(
            f"[red]Unknown skill: {skill_name}[/red] [dim](try /skill to list)[/dim]\n"
        )
        return None

    expanded = expand_skill(skill_name, params)
    if expanded is None:
        skill = SKILL_REGISTRY[skill_name]
        console.print(
            f"[red]Missing required params for '{skill_name}': "
            f"{', '.join(skill.required_params)}[/red]\n"
            f"[dim]Usage: /skill {skill_name} "
            f"{' '.join(f'<{p}>' for p in skill.required_params)}[/dim]\n"
        )
        return None

    console.print(
        f"[bold cyan]Running skill:[/bold cyan] {skill_name} "
        f"{' '.join(params.values())}\n"
    )
    return expanded


def handle_save_command(state: "SessionState", arg: str) -> None:
    """Handle /save command — save session exchanges as a report.

    /save              Show preview, ask for range + title
    /save 3            Save last 3 exchanges
    /save 2-5          Save exchanges #2 to #5
    /save "title"      Save last 1 with title
    /save 3 "title"    Save last 3 with title
    """
    import re as _re
    import hashlib as _hashlib

    if not state.chat_history:
        console.print("[red]No chat history available.[/red]\n")
        return

    entries = state.chat_history.read_session()
    if not entries:
        console.print("[dim]No exchanges in this session yet.[/dim]\n")
        return

    # Parse arg: optional range + optional quoted title
    range_str = None
    title = None
    if arg:
        # Extract quoted title
        title_match = _re.search(r'["\u201c](.+?)["\u201d]', arg)
        if title_match:
            title = title_match.group(1)
            arg_rest = arg[:title_match.start()].strip()
        else:
            arg_rest = arg.strip()
        # Parse range from remaining
        range_match = _re.match(r'^(\d+)-(\d+)$', arg_rest)
        if range_match:
            range_str = arg_rest
        elif arg_rest.isdigit():
            range_str = arg_rest

    # Determine which entries to save
    selected = None
    if range_str:
        if "-" in range_str:
            parts = range_str.split("-")
            start_idx = int(parts[0]) - 1  # 1-based → 0-based
            end_idx = int(parts[1])
            selected = entries[max(0, start_idx):min(len(entries), end_idx)]
        else:
            n = int(range_str)
            selected = entries[-n:] if n <= len(entries) else entries
    else:
        # Interactive: show preview and ask
        show_n = min(len(entries), 10)
        console.print(f"\n[bold]Session exchanges ({len(entries)} total):[/bold]\n")
        for i, entry in enumerate(entries[-show_n:], len(entries) - show_n + 1):
            _print_history_entry(i, entry)

        try:
            choice = input("\n  Save which? [range e.g. 1-3 / N for last N / Enter=last 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("[dim]Cancelled.[/dim]\n")
            return

        if not choice:
            selected = entries[-1:]
        elif "-" in choice:
            parts = choice.split("-")
            try:
                start_idx = int(parts[0]) - 1
                end_idx = int(parts[1])
                selected = entries[max(0, start_idx):min(len(entries), end_idx)]
            except ValueError:
                console.print("[red]Invalid range format.[/red]\n")
                return
        elif choice.isdigit():
            n = int(choice)
            selected = entries[-n:] if n <= len(entries) else entries
        else:
            console.print("[red]Invalid input.[/red]\n")
            return

    if not selected:
        console.print("[red]No exchanges selected.[/red]\n")
        return

    # Show preview of selected
    console.print(f"\n[bold]Selected {len(selected)} exchange(s):[/bold]")
    for i, entry in enumerate(selected, 1):
        q = entry.get("userMessage", "")[:80]
        console.print(f"  [cyan]#{i}[/cyan] Q: {q}")
    console.print()

    # Get title if not provided
    if not title:
        try:
            default_title = selected[0].get("userMessage", "Untitled")[:40]
            title = input(f"  Title [{default_title}]: ").strip()
            if not title:
                title = default_title
        except (KeyboardInterrupt, EOFError):
            console.print("[dim]Cancelled.[/dim]\n")
            return

    # Collect all tickers from selected entries
    all_tickers: set = set()
    for entry in selected:
        for t in entry.get("tickers", []):
            all_tickers.add(t)

    # Build Markdown content
    from datetime import date as _date
    today = _date.today().isoformat()
    tickers_str = ", ".join(sorted(all_tickers)) if all_tickers else "N/A"

    md_lines = [
        f"# {title}",
        "",
        f"**Date**: {today}",
        f"**Exchanges**: {len(selected)}",
        f"**Tickers**: {tickers_str}",
        "**Source**: manual (/save)",
        "",
        "---",
    ]

    for idx, entry in enumerate(selected, 1):
        ts = entry.get("timestamp", "?")[:19].replace("T", " ")
        provider = entry.get("provider", "?")
        model = entry.get("model", "?")
        elapsed = entry.get("elapsed_seconds", "")
        elapsed_str = f" | {elapsed}s" if elapsed else ""
        tools = entry.get("tools_used", [])
        tools_str = f" | {len(tools)} tools" if tools else ""
        entry_tickers = entry.get("tickers", [])
        tickers_line = f" | {', '.join(entry_tickers)}" if entry_tickers else ""

        md_lines.extend([
            "",
            f"## Exchange {idx}",
            f"> **{ts}** | {provider}/{model}{elapsed_str}{tools_str}{tickers_line}",
            "",
            "### Question",
            entry.get("userMessage", ""),
            "",
            "### Answer",
            entry.get("agentResponse", ""),
            "",
            "---",
        ])

    content = "\n".join(md_lines)

    # Generate filename and write
    from pathlib import Path as _Path
    reports_dir = _Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    ticker_part = "_".join(sorted(all_tickers)[:3]) if all_tickers else "MISC"
    content_hash = _hashlib.md5(
        f"{title}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:8]
    filename = f"{today}_{ticker_part}_{content_hash}.md"
    file_path = reports_dir / filename

    file_path.write_text(content, encoding="utf-8")

    # Try DB insert if available
    report_id = None
    try:
        if hasattr(state, 'chat_history') and state.chat_history:
            # Access DAL through lazy import for DB insert
            from src.tools.data_access import DataAccessLayer
            dal = DataAccessLayer()
            if hasattr(dal, '_backend') and hasattr(dal._backend, 'insert_report'):
                report_id = dal._backend.insert_report(
                    title=title,
                    tickers=sorted(all_tickers),
                    report_type="chat_save",
                    summary=f"Manual save of {len(selected)} exchange(s) from session",
                    file_path=f"data/reports/{filename}",
                )
    except Exception as e:
        logger.debug(f"DB insert for /save report skipped: {e}")

    id_str = f" (id={report_id})" if report_id else ""
    console.print(
        f"[green]✓ Report saved:[/green] data/reports/{filename} "
        f"({len(selected)} exchanges){id_str}\n"
    )


def _print_history_entry(index: int, entry: Dict[str, Any]) -> None:
    """Print a single history entry in compact format."""
    ts = entry.get("timestamp", "?")[:19].replace("T", " ")
    model = entry.get("model", "?")
    # Shorten model name
    if "/" in model:
        model = model.split("/")[-1]
    elapsed = entry.get("elapsed_seconds", "")
    elapsed_str = f" {elapsed}s" if elapsed else ""
    tools = entry.get("tools_used", [])
    tools_str = f" | {len(tools)} tools" if tools else ""
    tickers = entry.get("tickers", [])
    tickers_str = f" | {', '.join(tickers)}" if tickers else ""

    question = entry.get("userMessage", "")
    answer = entry.get("agentResponse", "")

    console.print(
        f"  [bold]#{index}[/bold] [dim]{ts}[/dim] "
        f"{model}{elapsed_str}{tools_str}{tickers_str}"
    )
    console.print(f"    [cyan]Q:[/cyan] {question[:80]}")
    console.print(f"    [green]A:[/green] {answer[:120]}...")
    console.print()


def handle_reports_command(dal, arg: str) -> None:
    """Handle /reports [ticker] command."""
    from src.tools.report_tools import list_reports, get_report

    # /reports <id> — show specific report
    if arg.isdigit():
        report = get_report(dal, report_id=int(arg))
        if "error" in report:
            console.print(f"[red]{report['error']}[/red]\n")
        else:
            console.print(report["content"])
            console.print()
        return

    # /reports [ticker] — list reports
    ticker = arg.upper() if arg and arg.isalpha() else None
    reports = list_reports(dal, ticker=ticker)

    if not reports:
        console.print("[dim]No reports found.[/dim]\n")
        return

    console.print(f"[bold]Research Reports[/bold] ({len(reports)} found)\n")
    for r in reports:
        rid = r.get("id", "-")
        title = r.get("title", "Untitled")
        dt = r.get("created_at", r.get("date", ""))
        conclusion = r.get("conclusion", "")
        tickers = r.get("tickers", [])
        if isinstance(tickers, list):
            tickers = ", ".join(tickers)
        tag = f" [{conclusion}]" if conclusion else ""
        console.print(f"  [cyan]#{rid}[/cyan] {title}{tag} [dim]({tickers}) {dt}[/dim]")
    console.print(f"\n[dim]Use /reports <id> to view a report[/dim]\n")


def _handle_monitor_command(dal, arg: str) -> None:
    """Handle /monitor [scan [TICKERS] | status]."""
    import asyncio
    from src.monitor.engine import MonitorEngine

    parts = arg.split() if arg else []
    subcmd = parts[0].lower() if parts else "scan"

    engine = MonitorEngine(dal=dal)

    if subcmd == "status":
        console.print("[bold]Monitor Configuration[/bold]")
        console.print(f"  Default tickers: {', '.join(engine.default_tickers)}")
        console.print(f"  Active channels: {engine._router.active_channels}")
        console.print(f"  Watchers: {len(engine._watchers)}")
        console.print()
        return

    # Default: scan
    tickers = None
    if subcmd == "scan" and len(parts) > 1:
        tickers = [t.upper() for t in parts[1:]]
    elif subcmd != "scan":
        # User typed /monitor NVDA TSLA (no "scan" keyword)
        tickers = [t.upper() for t in parts]

    scan_tickers = tickers or engine.default_tickers
    console.print(f"[dim]Scanning {len(scan_tickers)} tickers...[/dim]")

    alerts = asyncio.run(engine.scan_once(tickers=tickers, notify=True))
    summary = engine.format_scan_summary(alerts)
    console.print(summary)
    console.print()


def handle_memory_command(dal, arg: str) -> None:
    """Handle /memory [subcommand] [args]."""
    from src.tools.memory_tools import (
        save_memory, recall_memories, list_memories, delete_memory,
    )

    parts = arg.split(None, 1) if arg else []
    subcmd = parts[0].lower() if parts else ""
    subarg = parts[1] if len(parts) > 1 else ""

    # /memory (no args) or /memory list → list recent
    if not subcmd or subcmd == "list":
        memories = list_memories(dal)
        if not memories:
            console.print("[dim]No memories found.[/dim]\n")
            return
        console.print(f"[bold]Memories[/bold] ({len(memories)} found)\n")
        for m in memories:
            mid = m.get("id", "-")
            title = m.get("title", "Untitled")
            cat = m.get("category", "")
            dt = m.get("created_at", m.get("date", ""))
            imp = m.get("importance", 5)
            tickers = m.get("tickers", [])
            if isinstance(tickers, list):
                tickers = ", ".join(tickers) if tickers else ""
            console.print(
                f"  [cyan]#{mid}[/cyan] [{cat}] {title} "
                f"[dim]({tickers}) {dt}[/dim]"
            )
        console.print(f"\n[dim]Use /memory <id> to view, /memory search <query> to search[/dim]\n")
        return

    # /memory <id> → view specific memory
    if subcmd.isdigit():
        results = recall_memories(dal, query="", limit=100)
        target = next(
            (m for m in results if str(m.get("id")) == subcmd), None
        )
        if not target:
            console.print(f"[red]Memory #{subcmd} not found.[/red]\n")
            return
        console.print(f"[bold]#{subcmd}: {target.get('title', '')}[/bold]")
        console.print(
            f"[dim]Category: {target.get('category', '')} | "
            f"Importance: {target.get('importance', 5)} | "
            f"Created: {target.get('created_at', target.get('date', ''))}[/dim]"
        )
        mem_tickers = target.get("tickers")
        if mem_tickers and isinstance(mem_tickers, list):
            console.print(f"[dim]Tickers: {', '.join(mem_tickers)}[/dim]")
        mem_tags = target.get("tags")
        if mem_tags and isinstance(mem_tags, list):
            console.print(f"[dim]Tags: {', '.join(mem_tags)}[/dim]")
        console.print()
        console.print(target.get("content", ""))
        console.print()
        return

    # /memory search <query> → full-text search
    if subcmd == "search":
        if not subarg:
            console.print("[yellow]Usage: /memory search <query>[/yellow]\n")
            return
        results = recall_memories(dal, query=subarg)
        if not results:
            console.print(f"[dim]No memories matching '{subarg}'.[/dim]\n")
            return
        console.print(f"[bold]Memory Search: '{subarg}'[/bold] ({len(results)} found)\n")
        for m in results:
            mid = m.get("id", "-")
            title = m.get("title", "Untitled")
            cat = m.get("category", "")
            preview = (m.get("content", ""))[:100].replace("\n", " ")
            console.print(f"  [cyan]#{mid}[/cyan] [{cat}] {title}")
            console.print(f"      [dim]{preview}...[/dim]")
        console.print()
        return

    # /memory save → interactive manual save
    if subcmd == "save":
        try:
            title = console.input("[bold]Title:[/bold] ").strip()
            if not title:
                console.print("[dim]Cancelled.[/dim]\n")
                return
            content = console.input("[bold]Content:[/bold] ").strip()
            if not content:
                console.print("[dim]Cancelled.[/dim]\n")
                return
            cat = (
                console.input(
                    "[bold]Category[/bold] (analysis/insight/preference/fact/note) [note]: "
                ).strip()
                or "note"
            )
            tickers_str = console.input(
                "[bold]Tickers[/bold] (comma-separated, optional): "
            ).strip()
            tickers = (
                [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
                if tickers_str else None
            )
            tags_str = console.input(
                "[bold]Tags[/bold] (comma-separated, optional): "
            ).strip()
            tags = (
                [t.strip() for t in tags_str.split(",") if t.strip()]
                if tags_str else None
            )

            result = save_memory(
                dal, title=title, content=content, category=cat,
                tickers=tickers, tags=tags, source="user_manual",
            )
            console.print(
                f"[green]Memory saved: #{result.get('id', '?')} — {title}[/green]\n"
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled.[/dim]\n")
        return

    # /memory delete <id>
    if subcmd == "delete":
        if not subarg or not subarg.isdigit():
            console.print("[yellow]Usage: /memory delete <id>[/yellow]\n")
            return
        result = delete_memory(dal, memory_id=int(subarg))
        if result.get("deleted"):
            console.print(f"[green]Memory #{subarg} deleted.[/green]\n")
        else:
            console.print(f"[red]{result.get('error', 'Delete failed')}[/red]\n")
        return

    console.print(f"[red]Unknown memory subcommand: {subcmd}[/red]\n")


def handle_status_command(state: SessionState, backend_type: str, ticker_count: int) -> None:
    """Handle /status command."""
    console.print(
        f"[dim]{state.status_line()} | Backend: {backend_type} | "
        f"{ticker_count} tickers[/dim]\n"
    )


def handle_effort_command(state: SessionState, arg: str) -> None:
    """Handle /effort [level] command (Anthropic only, model-aware)."""
    if state.provider != "anthropic":
        console.print("[yellow]Effort only applies to Anthropic models.[/yellow]\n")
        return

    current_model = state.effective_model()

    if not arg:
        current = state.anthropic_effort or get_agent_config().anthropic_effort or "default"
        selected = print_effort_picker(current, current_model)
        if selected is None:
            # print_effort_picker already prints unsupported message if needed
            if _get_effort_options_for_model(current_model) is not None:
                console.print("[dim]Cancelled.[/dim]\n")
            return
        state.anthropic_effort = selected
        console.print(f"[green]Effort set to[/green] [bold]{selected}[/bold]\n")
        return

    # Direct argument — validate against model-specific options
    model_options = _get_effort_options_for_model(current_model)
    if model_options is None:
        supported = ", ".join(
            f"{prefix} ({', '.join(opts)})"
            for prefix, opts in _EFFORT_OPTIONS_BY_MODEL.items()
        )
        console.print(
            f"[yellow]Effort is not supported for {current_model}.[/yellow]\n"
            f"[dim]Supported models: {supported}[/dim]\n"
        )
        return

    if arg.lower() not in model_options:
        console.print(
            f"[red]Invalid effort for {current_model}: {arg}[/red]\n"
            f"[dim]Valid: {', '.join(model_options)}[/dim]\n"
        )
        return

    state.anthropic_effort = arg.lower()
    console.print(f"[green]Effort set to[/green] [bold]{arg.lower()}[/bold]\n")


def handle_thinking_command(state: SessionState, arg: str) -> None:
    """Handle /thinking [on|off] command (Anthropic only). No arg = toggle."""
    if state.provider != "anthropic":
        console.print("[yellow]Thinking only applies to Anthropic models.[/yellow]\n")
        return
    if not arg:
        # Toggle
        state.anthropic_thinking = not state.anthropic_thinking
        new_status = "ON" if state.anthropic_thinking else "OFF"
        console.print(f"[green]Thinking:[/green] [bold]{new_status}[/bold]\n")
        return
    if arg.lower() in ("on", "true", "1"):
        state.anthropic_thinking = True
        console.print("[green]Thinking:[/green] [bold]ON[/bold]\n")
    elif arg.lower() in ("off", "false", "0"):
        state.anthropic_thinking = False
        console.print("[green]Thinking:[/green] [bold]OFF[/bold]\n")
    else:
        console.print("[red]Usage: /thinking [on|off][/red]\n")


def handle_context_command(state: SessionState, arg: str) -> None:
    """Handle /context [on|off] command (Anthropic only). No arg = toggle."""
    if state.provider != "anthropic":
        console.print("[yellow]1M context beta only applies to Anthropic models.[/yellow]\n")
        return

    model = state.effective_model()
    supported = _use_extended_context(model, True)

    if not supported:
        console.print(
            f"[yellow]1M context beta is not supported for {model}.[/yellow]\n"
            "[dim]Supported: Opus 4.6, Sonnet 4.6[/dim]\n"
        )
        return

    if not arg:
        state.extended_context = not state.extended_context
        new_status = "ON (1M)" if state.extended_context else "OFF (200K)"
        console.print(f"[green]Context:[/green] [bold]{new_status}[/bold]\n")
        return
    if arg.lower() in ("on", "true", "1", "1m"):
        state.extended_context = True
        console.print("[green]Context:[/green] [bold]ON (1M)[/bold]\n")
    elif arg.lower() in ("off", "false", "0", "200k"):
        state.extended_context = False
        console.print("[green]Context:[/green] [bold]OFF (200K)[/bold]\n")
    else:
        console.print("[red]Usage: /context [on|off][/red]\n")


def handle_compaction_command(state: SessionState, arg: str) -> None:
    """Handle /compaction [on|off] command. No arg = toggle.

    Server-side compaction (L2):
    - Anthropic: beta compact-2026-01-12, Opus 4.6 + Sonnet 4.6
    - OpenAI: CompactionSession
    Both work on top of L1 client-side compaction.
    """
    if not arg:
        state.server_compaction = not state.server_compaction
        new_status = "ON" if state.server_compaction else "OFF"
        console.print(f"[green]Server compaction (L2):[/green] [bold]{new_status}[/bold]")
        if state.server_compaction:
            console.print("[dim]Anthropic: Opus 4.6 + Sonnet 4.6 | OpenAI: CompactionSession[/dim]")
        console.print()
        return
    if arg.lower() in ("on", "true", "1"):
        state.server_compaction = True
        console.print("[green]Server compaction (L2):[/green] [bold]ON[/bold]")
        console.print("[dim]Anthropic: Opus 4.6 + Sonnet 4.6 | OpenAI: CompactionSession[/dim]\n")
    elif arg.lower() in ("off", "false", "0"):
        state.server_compaction = False
        console.print("[green]Server compaction (L2):[/green] [bold]OFF[/bold]\n")
    else:
        console.print("[red]Usage: /compaction [on|off][/red]\n")


def handle_subagent_command(state: SessionState, arg: str) -> None:
    """Handle /subagent [name [model | turns N]] command.

    No arg: show all subagent models and max_turns.
    /subagent code_analyst: show + pick model for code_analyst.
    /subagent code_analyst opus: set code_analyst to opus.
    /subagent code_analyst turns 12: set code_analyst max_turns to 12.
    /subagent reset: clear all overrides back to defaults.

    Changes are saved to config/user_profile.local.yaml for persistence.
    """
    from .shared.subagent import SUBAGENT_REGISTRY, _detect_provider
    from .config import get_agent_config, save_local_override

    config = get_agent_config()
    overrides = dict(config.subagent_models)
    turns_overrides = dict(config.subagent_max_turns)

    if arg.lower() == "reset":
        save_local_override("llm_preferences", "subagent_models", {})
        save_local_override("llm_preferences", "subagent_max_turns", {})
        console.print("[green]Subagent overrides reset to defaults.[/green]\n")
        return

    if not arg:
        # Show all subagent models + max_turns
        table = Table(
            box=box.SIMPLE_HEAVY, show_header=True,
            header_style="bold", padding=(0, 1),
        )
        table.add_column("Subagent", style="cyan")
        table.add_column("Default Model", style="dim")
        table.add_column("Active Model", style="bold")
        table.add_column("Provider")
        table.add_column("Max Turns", justify="right")

        for name, sa_config in SUBAGENT_REGISTRY.items():
            active = overrides.get(name, sa_config.model)
            is_overridden = name in overrides and overrides[name] != sa_config.model
            active_style = "[yellow]" if is_overridden else ""
            active_end = "[/yellow]" if is_overridden else ""
            provider = _detect_provider(active)

            active_turns = turns_overrides.get(name, sa_config.max_turns)
            turns_overridden = name in turns_overrides and turns_overrides[name] != sa_config.max_turns
            turns_str = (
                f"[yellow]{active_turns}[/yellow]" if turns_overridden
                else str(active_turns)
            )

            table.add_row(
                name,
                sa_config.model,
                f"{active_style}{active}{active_end}",
                provider,
                turns_str,
            )

        console.print()
        console.print(table)
        console.print(
            "\n[dim]Usage: /subagent <name> <model>    (e.g. /subagent code_analyst opus)\n"
            "       /subagent <name> turns <N>  (e.g. /subagent deep_researcher turns 15)\n"
            "       /subagent reset              (clear all overrides)[/dim]\n"
        )
        return

    # Parse: /subagent <name> [model]
    parts = arg.split(None, 1)
    sa_name = parts[0].lower()

    if sa_name not in SUBAGENT_REGISTRY:
        available = ", ".join(sorted(SUBAGENT_REGISTRY.keys()))
        console.print(f"[red]Unknown subagent: {sa_name}[/red]\n[dim]Available: {available}[/dim]\n")
        return

    if len(parts) == 1:
        # Show current + interactive picker
        sa_config = SUBAGENT_REGISTRY[sa_name]
        current = overrides.get(sa_name, sa_config.model)
        active_turns = turns_overrides.get(sa_name, sa_config.max_turns)
        console.print(
            f"[dim]{sa_name}: model={current}, max_turns={active_turns}[/dim]"
        )
        entry = print_model_picker(current)
        if entry is None:
            console.print("[dim]Cancelled.[/dim]\n")
            return
        new_model = entry.id
    else:
        # Direct: /subagent code_analyst opus  OR  /subagent code_analyst turns 12
        rest = parts[1].strip()

        # Handle "turns N"
        rest_parts = rest.split(None, 1)
        if rest_parts[0].lower() == "turns":
            if len(rest_parts) < 2:
                sa_config = SUBAGENT_REGISTRY[sa_name]
                active_turns = turns_overrides.get(sa_name, sa_config.max_turns)
                console.print(
                    f"[dim]{sa_name}: max_turns={active_turns} "
                    f"(default={sa_config.max_turns})[/dim]\n"
                )
                return
            try:
                n = int(rest_parts[1])
                if n < 1 or n > 100:
                    console.print("[red]max_turns must be 1-100[/red]\n")
                    return
            except ValueError:
                console.print(f"[red]Invalid number: {rest_parts[1]}[/red]\n")
                return
            turns_overrides[sa_name] = n
            save_local_override("llm_preferences", "subagent_max_turns", turns_overrides)
            console.print(
                f"[green]{sa_name}[/green] max_turns → [bold]{n}[/bold] "
                f"[dim](saved)[/dim]\n"
            )
            return

        model_query = rest
        if model_query.lower() in ("default", "reset"):
            # Reset this specific subagent
            if sa_name in overrides:
                del overrides[sa_name]
            if sa_name in turns_overrides:
                del turns_overrides[sa_name]
            save_local_override("llm_preferences", "subagent_models", overrides)
            save_local_override("llm_preferences", "subagent_max_turns", turns_overrides)
            default_model = SUBAGENT_REGISTRY[sa_name].model
            console.print(
                f"[green]{sa_name}[/green] reset to default "
                f"[bold]{default_model}[/bold]\n"
            )
            return

        entry = find_model(model_query)
        if entry is None:
            console.print(f"[red]Unknown model: {model_query}[/red]\n")
            return
        new_model = entry.id

    # Apply and persist
    overrides[sa_name] = new_model
    save_local_override("llm_preferences", "subagent_models", overrides)
    provider = _detect_provider(new_model)
    console.print(
        f"[green]{sa_name}[/green] → [bold cyan]{new_model}[/bold cyan] "
        f"[dim]({provider}, saved)[/dim]\n"
    )


def handle_attach_command(state: SessionState, arg: str) -> None:
    """Handle /attach <path> [pages] | list | clear command."""
    if not arg or arg == "list":
        if not state.attachments:
            console.print("[dim]No attachments.[/dim]\n")
        else:
            for i, att in enumerate(state.attachments, 1):
                info = f"{att.filename} ({att.media_type}, {att.size_kb:.1f} KB)"
                if att.pages:
                    info += f" pages={att.pages}"
                console.print(f"  {i}. {info}")
            console.print()
        return

    if arg == "clear":
        count = len(state.attachments)
        state.attachments.clear()
        console.print(f"[green]Cleared {count} attachment(s).[/green]\n")
        return

    # Parse: /attach <path> [pages]
    parts = arg.split(None, 1)
    file_path = parts[0]
    pages = parts[1] if len(parts) > 1 else ""

    try:
        att = AttachmentManager.load(file_path, pages=pages)
        state.attachments.append(att)
        info = f"{att.filename} ({att.media_type}, {att.size_kb:.1f} KB)"
        if att.pages:
            info += f" pages={att.pages}"
        console.print(f"[green]Attached: {info}[/green]\n")
    except Exception as e:
        console.print(f"[red]Failed to attach: {e}[/red]\n")


def handle_turns_command(state: SessionState, arg: str) -> None:
    """Handle /turns [N] command. Set max tool calls per query.

    /turns      — show current setting
    /turns 30   — set to 30
    /turns reset — reset to config default
    """
    config = get_agent_config()
    current = state.max_tool_calls or config.max_tool_calls

    if not arg:
        default = config.max_tool_calls
        if state.max_tool_calls:
            console.print(
                f"[dim]Max turns: {current} (config default: {default})[/dim]\n"
            )
        else:
            console.print(f"[dim]Max turns: {current} (config default)[/dim]\n")
        return

    if arg.lower() in ("reset", "default"):
        state.max_tool_calls = None
        console.print(
            f"[green]Max turns reset to config default[/green] "
            f"[dim]({config.max_tool_calls})[/dim]\n"
        )
        return

    try:
        n = int(arg)
        if n < 1 or n > 100:
            console.print("[red]Max turns must be 1-100.[/red]\n")
            return
        state.max_tool_calls = n
        console.print(f"[green]Max turns set to[/green] [bold]{n}[/bold]\n")
    except ValueError:
        console.print("[red]Usage: /turns <number> or /turns reset[/red]\n")


def handle_scratchpad_command(arg: str) -> None:
    """Handle /scratchpad [N] command. List recent scratchpad sessions.

    /scratchpad      — list last 10 sessions
    /scratchpad 20   — list last 20 sessions
    /scratchpad <id> — show contents of a specific session file
    """
    from .shared.scratchpad import read_scratchpad

    pad_dir = Path("data/agent_scratchpad")
    if not pad_dir.exists():
        console.print("[dim]No scratchpad directory found.[/dim]\n")
        return

    files = sorted(pad_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        console.print("[dim]No scratchpad files found.[/dim]\n")
        return

    # Check if arg is a session ID (hash fragment)
    if arg and not arg.isdigit():
        matches = [f for f in files if arg in f.stem]
        if matches:
            filepath = matches[0]
            events = read_scratchpad(filepath)
            console.print(f"\n[bold]{filepath.name}[/bold] ({len(events)} events)")
            for ev in events:
                ev_type = ev.get("type", "?")
                data = ev.get("data", {})
                if ev_type == "init":
                    console.print(f"  [cyan]init[/cyan] query={data.get('query', '')[:80]}")
                elif ev_type == "tool_call":
                    console.print(f"  [yellow]tool_call[/yellow] {data.get('tool', '?')}({str(data.get('input', ''))[:60]})")
                elif ev_type == "tool_result":
                    tool = data.get("tool", "?")
                    chars = data.get("result_chars", 0)
                    args_str = str(data.get("args", ""))[:60] if "args" in data else ""
                    result_preview = str(data.get("result", ""))[:120]
                    console.print(f"  [yellow]tool[/yellow] {tool}({args_str}) → {chars} chars")
                    if result_preview:
                        console.print(f"    [dim]{result_preview}[/dim]")
                elif ev_type == "final_answer":
                    answer = data.get("answer", data.get("answer_preview", ""))
                    preview = answer[:120] if answer else ""
                    elapsed = data.get("elapsed_seconds", "?")
                    console.print(f"  [green]final[/green] {elapsed}s | {preview}")
                elif ev_type == "max_turns":
                    elapsed = data.get("elapsed_seconds", "?")
                    console.print(f"  [red]max_turns[/red] {elapsed}s | tools: {data.get('tools_used', [])}")
            console.print()
            return
        console.print(f"[red]No scratchpad matching '{arg}'[/red]\n")
        return

    # List recent sessions
    limit = int(arg) if arg and arg.isdigit() else 10
    shown = files[:limit]

    table = Table(
        box=box.SIMPLE_HEAVY, show_header=True,
        header_style="bold", padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Session", style="cyan")
    table.add_column("Size")
    table.add_column("Events", style="dim")
    table.add_column("Query", style="dim", max_width=40)

    for i, f in enumerate(shown, 1):
        size = f.stat().st_size
        size_str = f"{size:,}" if size < 10000 else f"{size / 1024:.1f}K"
        # Read just init event for query
        query = ""
        event_count = 0
        try:
            events = read_scratchpad(f)
            event_count = len(events)
            for ev in events:
                if ev.get("type") == "init":
                    query = ev.get("data", {}).get("query", "")[:40]
                    break
        except Exception:
            pass
        session_id = f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem
        table.add_row(str(i), session_id, size_str, str(event_count), query)

    console.print()
    console.print(table)
    console.print(
        f"\n[dim]Showing {len(shown)}/{len(files)} sessions from {pad_dir}/\n"
        "Use /scratchpad <session_id> to view details[/dim]\n"
    )


def handle_history_command(state: "SessionState", arg: str) -> None:
    """Handle /history [N] command. Show current session chat history.

    /history      — show all exchanges in this session
    /history 5    — show last 5 exchanges
    """
    if not state.chat_history:
        console.print("[dim]No chat history available.[/dim]\n")
        return

    entries = state.chat_history.read_session()
    if not entries:
        console.print("[dim]No exchanges in this session yet.[/dim]\n")
        return

    limit = int(arg) if arg and arg.isdigit() else len(entries)
    show_entries = entries[-limit:]
    start_idx = len(entries) - len(show_entries) + 1

    console.print(f"\n[bold]Session history[/bold] ({len(entries)} exchanges)\n")
    for i, entry in enumerate(show_entries, start_idx):
        _print_history_entry(i, entry)

    console.print(f"[dim]File: {state.chat_history.path}[/dim]\n")


def handle_code_model_command(state: SessionState, arg: str) -> None:
    """Handle /code-model [model] command. No arg = interactive picker."""
    if not arg:
        # Interactive picker
        current = state.code_model or "(auto)"
        selected = print_model_picker(current)
        if selected is None:
            console.print("[dim]Cancelled.[/dim]\n")
            return
        state.code_model = selected.id
        console.print(f"[green]Code model:[/green] [bold]{selected.id}[/bold]\n")
    elif arg.lower() in ("auto", "none", "reset"):
        state.code_model = ""
        console.print("[green]Code model:[/green] [bold](auto)[/bold]\n")
    else:
        state.code_model = arg
        console.print(f"[green]Code model:[/green] [bold]{arg}[/bold]\n")


def handle_code_backend_command(state: SessionState, arg: str) -> None:
    """Handle /code-backend [backend] command."""
    from src.tools.code_generator import VALID_BACKENDS

    if not arg:
        # Show current
        current = state.code_backend or "api"
        console.print(f"[bold]Code backend:[/bold] {current}")
        console.print("[dim]Options: api, codex, codex-apikey, claude, claude-apikey[/dim]")
        console.print("[dim]  api          — Direct API call (default)[/dim]")
        console.print("[dim]  codex        — Codex CLI with subscription[/dim]")
        console.print("[dim]  codex-apikey — Codex CLI with API key[/dim]")
        console.print("[dim]  claude       — Claude Code with subscription[/dim]")
        console.print("[dim]  claude-apikey— Claude Code with API key[/dim]\n")
        return

    val = arg.lower().strip()
    if val not in VALID_BACKENDS:
        console.print(f"[red]Unknown backend: {val}[/red]")
        console.print(f"[dim]Valid: {', '.join(sorted(VALID_BACKENDS))}[/dim]\n")
        return

    state.code_backend = val
    # Update config so code_generator picks it up
    get_agent_config.cache_clear()
    config = get_agent_config()
    config.code_backend = val
    console.print(f"[green]Code backend:[/green] [bold]{val}[/bold]\n")


# ============================================================
# Main Chat Loop
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="MindfulRL Interactive Agent")
    parser.add_argument(
        "--provider", "-p",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="LLM provider (default: anthropic)"
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Override model name"
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Disable conversation history (each question is independent)"
    )
    parser.add_argument(
        "--reasoning", "-r",
        choices=list(VALID_REASONING),
        default=None,
        help="Reasoning effort for GPT-5.x (default: from config, typically xhigh)"
    )
    parser.add_argument(
        "--effort",
        choices=list(VALID_ANTHROPIC_EFFORT),
        default=None,
        help="Anthropic effort level (Opus 4.5+)"
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Enable Anthropic extended thinking"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Truncate excessively long log messages from OpenAI Agents SDK
    # (SDK dumps entire tool outputs on error, can be 100K+ chars)
    class _TruncateFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            if len(msg) > 2000:
                record.msg = msg[:2000] + f"\n... [truncated, total {len(msg):,} chars]"
                record.args = None
            return True

    logging.getLogger("openai.agents").addFilter(_TruncateFilter())

    # Initialize DAL
    from src.tools.data_access import DataAccessLayer
    with console.status("[cyan]Loading data...", spinner="dots"):
        dal = DataAccessLayer(db_dsn="auto")

    backend_type = dal.backend_type
    ticker_count = len(dal.get_available_tickers("prices"))

    # Build mutable session state
    config = get_agent_config()
    state = SessionState(
        provider=args.provider,
        model=args.model,
        reasoning_effort=args.reasoning,
        no_history=args.no_history,
        verbose=args.verbose,
        messages_history=[] if not args.no_history else None,
        anthropic_effort=args.effort,
        anthropic_thinking=args.thinking,
        server_compaction=config.server_compaction,
        chat_history=ChatHistory.create_session(),
    )

    print_banner()
    console.print(
        f"[dim]{state.status_line()} | Backend: {backend_type} | "
        f"{ticker_count} tickers[/dim]\n"
    )

    completer = SlashCompleter(state)

    while True:
        # Show pending attachments indicator
        if state.attachments:
            att_names = ", ".join(a.filename for a in state.attachments)
            console.print(f"[dim]  Pending: {att_names}[/dim]")
        try:
            question = pt_prompt(
                ANSI("\033[1;36m>\033[0m "),
                completer=completer,
                complete_while_typing=False,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye![/dim]")
            break

        if not question:
            continue

        if question.lower() in ("quit", "exit", "q"):
            console.print("[dim]Bye![/dim]")
            break

        if question.lower() in ("clear", "reset"):
            state.messages_history = [] if not state.no_history else None
            console.print("[dim]Conversation cleared.[/dim]\n")
            continue

        if question.lower() in ("help", "/help"):
            print_help()
            continue

        # --- Skill dispatch (before general slash commands — needs fall-through) ---
        if question.startswith("/"):
            _sk_cmd = question.split(None, 1)[0].lower()
            if _sk_cmd in ("/skill", "/sk"):
                _sk_arg = question.split(None, 1)[1].strip() if " " in question else ""
                _expanded = handle_skill_command(state, _sk_arg)
                if _expanded is not None:
                    question = _expanded
                    # Fall through to query execution below
                else:
                    continue

        # --- Slash commands ---
        if question.startswith("/"):
            parts = question.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("/model", "/m"):
                handle_model_command(state, arg)
            elif cmd in ("/code-model", "/cm"):
                handle_code_model_command(state, arg)
            elif cmd in ("/code-backend", "/cb"):
                handle_code_backend_command(state, arg)
            elif cmd in ("/reasoning", "/r"):
                handle_reasoning_command(state, arg)
            elif cmd in ("/effort", "/e"):
                handle_effort_command(state, arg)
            elif cmd in ("/thinking", "/t"):
                handle_thinking_command(state, arg)
            elif cmd in ("/context", "/ctx"):
                handle_context_command(state, arg)
            elif cmd in ("/compaction", "/cmp"):
                handle_compaction_command(state, arg)
            elif cmd in ("/subagent", "/sa"):
                handle_subagent_command(state, arg)
            elif cmd in ("/scratchpad", "/pad"):
                handle_scratchpad_command(arg)
            elif cmd in ("/history", "/h"):
                handle_history_command(state, arg)
            elif cmd == "/turns":
                handle_turns_command(state, arg)
            elif cmd in ("/attach", "/at"):
                handle_attach_command(state, arg)
            elif cmd in ("/save", "/sv"):
                handle_save_command(state, arg)
            elif cmd in ("/reports", "/rp"):
                handle_reports_command(dal, arg)
            elif cmd in ("/memory", "/mem"):
                handle_memory_command(dal, arg)
            elif cmd in ("/monitor", "/mon"):
                _handle_monitor_command(dal, arg)
            elif cmd in ("/status", "/s"):
                handle_status_command(state, backend_type, ticker_count)
            else:
                console.print(f"[red]Unknown command: {cmd}[/red] [dim](try /help)[/dim]\n")
            continue

        # --- Run query ---
        # Show attachment indicator
        if state.attachments:
            att_names = ", ".join(a.filename for a in state.attachments)
            console.print(f"[dim]Attached: {att_names}[/dim]")

        # Snapshot attachments for this query (cleared after dispatch)
        query_attachments = list(state.attachments) if state.attachments else None

        start = time.time()

        try:
            # Propagate server_compaction toggle to config (Phase 7a)
            get_agent_config().server_compaction = state.server_compaction

            if state.provider == "anthropic":
                result = run_anthropic_interactive(
                    question=question,
                    dal=dal,
                    model=state.model,
                    messages_history=state.messages_history,
                    effort=state.anthropic_effort,
                    thinking=state.anthropic_thinking,
                    extended_context=state.extended_context,
                    max_tool_calls=state.max_tool_calls,
                    attachments=query_attachments,
                    chat_history=state.chat_history,
                )
                # Update history for next turn
                if state.messages_history is not None and result.get("messages"):
                    state.messages_history = result["messages"]
            else:
                result = run_openai_interactive(
                    question=question,
                    dal=dal,
                    model=state.model,
                    reasoning_effort=state.reasoning_effort,
                    max_tool_calls=state.max_tool_calls,
                    attachments=query_attachments,
                    chat_history=state.chat_history,
                )

            # Auto-clear attachments after sending
            if state.attachments:
                state.attachments.clear()

            elapsed = time.time() - start
            print_answer(result["answer"])
            print_summary(
                result["tools_used"], elapsed,
                result.get("scratchpad_path"),
                result.get("token_usage"),
            )
            console.print()

            # Log to agent_queries table (Phase C)
            _log_agent_query(
                dal, question, result, state, elapsed,
            )

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled.[/dim]\n")
            continue
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")
            if state.verbose:
                console.print_exception()
            continue


if __name__ == "__main__":
    main()