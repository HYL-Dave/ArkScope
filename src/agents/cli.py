"""
Interactive CLI chat for MindfulRL agents.

Run:
    python -m src.agents
    python -m src.agents --provider anthropic
    python -m src.agents --provider openai

Slash commands (during chat):
    /model          Show available models and switch
    /model <name>   Switch to model by name or shorthand
    /reasoning <n>  Set reasoning effort (OpenAI only)
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

from .config import get_agent_config, ReasoningEffort
from .shared.prompts import SYSTEM_PROMPT

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
        id="claude-sonnet-4-5-20250929",
        provider="anthropic",
        name="Sonnet 4.5",
        aliases=["sonnet", "sonnet4.5", "sonnet-4.5", "s45", "claude-sonnet"],
        description="Fast, smart — best for agents & coding",
    ),
    ModelEntry(
        id="claude-opus-4-5-20251101",
        provider="anthropic",
        name="Opus 4.5",
        aliases=["opus", "opus4.5", "opus-4.5", "o45", "claude-opus"],
        description="Most intelligent — deep analysis & reasoning",
    ),
    ModelEntry(
        id="claude-haiku-4-5-20251001",
        provider="anthropic",
        name="Haiku 4.5",
        aliases=["haiku", "haiku4.5", "haiku-4.5", "h45", "claude-haiku"],
        description="Fastest & cheapest — quick tasks",
    ),
    ModelEntry(
        id="gpt-5.2",
        provider="openai",
        name="GPT-5.2",
        aliases=["gpt5", "gpt-5", "gpt5.2", "5.2"],
        description="SOTA reasoning with configurable effort",
    ),
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
        history = "on" if not self.no_history else "off"
        parts.append(f"History: {history}")
        return " | ".join(parts)


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
            "  [cyan]/reasoning <n>[/cyan]      Set reasoning effort: none|minimal|low|medium|high|xhigh\n"
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


def print_summary(tools_used: List[str], elapsed: float):
    """Print query summary."""
    if tools_used:
        tool_str = ", ".join(sorted(set(tools_used)))
        console.print(
            f"[dim]Tools: {tool_str} | {elapsed:.1f}s[/dim]"
        )
    else:
        console.print(f"[dim]{elapsed:.1f}s[/dim]")


# ============================================================
# Anthropic Interactive Loop
# ============================================================

def run_anthropic_interactive(
    question: str,
    dal: Any,
    model: Optional[str] = None,
    messages_history: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """
    Run Anthropic agent with live tool call display.

    Returns dict with answer, tools_used, messages (for conversation continuity).
    """
    from anthropic import Anthropic
    from .anthropic_agent.tools import get_anthropic_tools, execute_tool

    config = get_agent_config()
    model_name = model or config.anthropic_model
    client = Anthropic()
    tools = get_anthropic_tools()
    tools_used: List[str] = []
    tool_index = 0

    # Build messages
    if messages_history is not None:
        messages = messages_history + [{"role": "user", "content": question}]
    else:
        messages = [{"role": "user", "content": question}]

    console.print(f"[dim]Model: {model_name}[/dim]")

    for turn in range(config.max_tool_calls):
        with console.status("[cyan]Thinking...", spinner="dots"):
            response = client.messages.create(
                model=model_name,
                max_tokens=config.max_tokens,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )

        # Done - no more tool calls
        if response.stop_reason != "tool_use":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            # Update messages for conversation continuity
            messages.append({"role": "assistant", "content": response.content})

            return {
                "answer": final_text,
                "tools_used": tools_used,
                "messages": messages,
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

            # Execute with spinner
            with console.status("", spinner="dots"):
                result = execute_tool(tool_name, tool_input, dal)

            print_tool_result_summary(tool_name, result)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        # Append to message history
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": "Reached maximum tool calls.",
        "tools_used": tools_used,
        "messages": messages,
    }


# ============================================================
# OpenAI Interactive Loop
# ============================================================

def run_openai_interactive(
    question: str,
    dal: Any,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
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

    with console.status("[cyan]Running agent...", spinner="dots"):
        result = asyncio.run(run_query(
            question=question,
            model=model_name,
            dal=dal,
            reasoning_effort=effort,
        ))

    return {
        "answer": result["answer"],
        "tools_used": result["tools_used"],
        "messages": None,  # OpenAI SDK doesn't expose message history
    }


# ============================================================
# Slash Command Handlers
# ============================================================

VALID_REASONING = ("none", "minimal", "low", "medium", "high", "xhigh")


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
    """Handle /reasoning <effort> command."""
    if not arg:
        console.print(
            f"[dim]Current: {state.effective_reasoning()}  "
            f"Options: {', '.join(VALID_REASONING)}[/dim]\n"
        )
        return

    if arg.lower() not in VALID_REASONING:
        console.print(
            f"[red]Invalid reasoning effort: {arg}[/red]\n"
            f"[dim]Valid: {', '.join(VALID_REASONING)}[/dim]\n"
        )
        return

    state.reasoning_effort = arg.lower()
    console.print(f"[green]Reasoning effort set to[/green] [bold]{arg.lower()}[/bold]\n")


def handle_status_command(state: SessionState, backend_type: str, ticker_count: int) -> None:
    """Handle /status command."""
    console.print(
        f"[dim]{state.status_line()} | Backend: {backend_type} | "
        f"{ticker_count} tickers[/dim]\n"
    )


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
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Initialize DAL
    from src.tools.data_access import DataAccessLayer
    with console.status("[cyan]Loading data...", spinner="dots"):
        dal = DataAccessLayer(db_dsn="auto")

    backend_type = dal.backend_type
    ticker_count = len(dal.get_available_tickers("prices"))

    # Build mutable session state
    state = SessionState(
        provider=args.provider,
        model=args.model,
        reasoning_effort=args.reasoning,
        no_history=args.no_history,
        verbose=args.verbose,
        messages_history=[] if not args.no_history else None,
    )

    print_banner()
    console.print(
        f"[dim]{state.status_line()} | Backend: {backend_type} | "
        f"{ticker_count} tickers[/dim]\n"
    )

    while True:
        try:
            question = console.input("[bold cyan]>[/bold cyan] ").strip()
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

        # --- Slash commands ---
        if question.startswith("/"):
            parts = question.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("/model", "/m"):
                handle_model_command(state, arg)
            elif cmd in ("/reasoning", "/r"):
                handle_reasoning_command(state, arg)
            elif cmd in ("/status", "/s"):
                handle_status_command(state, backend_type, ticker_count)
            else:
                console.print(f"[red]Unknown command: {cmd}[/red] [dim](try /help)[/dim]\n")
            continue

        # --- Run query ---
        start = time.time()

        try:
            if state.provider == "anthropic":
                result = run_anthropic_interactive(
                    question=question,
                    dal=dal,
                    model=state.model,
                    messages_history=state.messages_history,
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
                )

            elapsed = time.time() - start
            print_answer(result["answer"])
            print_summary(result["tools_used"], elapsed)
            console.print()

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