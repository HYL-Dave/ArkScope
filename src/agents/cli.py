"""
Interactive CLI chat for MindfulRL agents.

Run:
    python -m src.agents
    python -m src.agents --provider anthropic
    python -m src.agents --provider openai
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
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

from .config import get_agent_config
from .shared.prompts import SYSTEM_PROMPT

console = Console()
logger = logging.getLogger(__name__)


# ============================================================
# Display Helpers
# ============================================================

def print_banner():
    """Print startup banner."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]MindfulRL[/bold cyan] [dim]Interactive Agent[/dim]\n"
            "[dim]Type your question, or 'quit' to exit[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


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
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
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

    config = get_agent_config()
    reasoning = args.reasoning or config.reasoning_effort

    print_banner()

    if args.provider == "openai":
        model_display = args.model or config.openai_model
        console.print(
            f"[dim]Provider: openai | Model: {model_display} | "
            f"Reasoning: {reasoning} | Backend: {backend_type} | "
            f"{ticker_count} tickers[/dim]\n"
        )
    else:
        model_display = args.model or config.anthropic_model
        console.print(
            f"[dim]Provider: anthropic | Model: {model_display} | "
            f"Backend: {backend_type} | {ticker_count} tickers[/dim]\n"
        )

    messages_history: Optional[List[dict]] = [] if not args.no_history else None

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
            messages_history = [] if not args.no_history else None
            console.print("[dim]Conversation cleared.[/dim]\n")
            continue

        if question.lower() == "help":
            console.print(
                "[dim]Commands: quit, clear, help\n"
                "Ask anything about your watchlist tickers, "
                "news, prices, IV, signals, etc.[/dim]\n"
            )
            continue

        start = time.time()

        try:
            if args.provider == "anthropic":
                result = run_anthropic_interactive(
                    question=question,
                    dal=dal,
                    model=args.model,
                    messages_history=messages_history,
                )
                # Update history for next turn
                if messages_history is not None and result.get("messages"):
                    messages_history = result["messages"]
            else:
                result = run_openai_interactive(
                    question=question,
                    dal=dal,
                    model=args.model,
                    reasoning_effort=args.reasoning,
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
            if args.verbose:
                console.print_exception()
            continue


if __name__ == "__main__":
    main()