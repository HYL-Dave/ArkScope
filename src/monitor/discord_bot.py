"""
Discord Bot for monitor notifications + two-way interaction.

Phase 2: one-way notifications (alerts → Discord).
Phase 3: slash commands, buttons, select menus, free chat (@mention + #agent channel).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import discord
from discord import app_commands

from .notifiers import Alert

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

logger = logging.getLogger(__name__)

# Severity → embed color mapping
_SEVERITY_COLORS = {
    "critical": discord.Color.red(),
    "warning": discord.Color.orange(),
    "info": discord.Color.blue(),
}

# Alert type → emoji
_TYPE_EMOJI = {
    "price": "\U0001F4C8",      # 📈
    "sentiment": "\U0001F4F0",   # 📰
    "signal": "\U0001F6A8",      # 🚨
    "sector": "\U0001F30D",      # 🌍
}


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def _load_token() -> str:
    """Load Discord bot token from config/.env or environment."""
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if token:
        return token

    env_path = Path("config/.env")
    if env_path.exists():
        from dotenv import dotenv_values
        values = dotenv_values(env_path)
        token = values.get("DISCORD_BOT_TOKEN", "")

    return token


def _load_channel_id() -> Optional[int]:
    """Load Discord channel ID from config/.env or environment."""
    return _load_env_int("DISCORD_CHANNEL_ID")


def _load_alert_channel_id() -> Optional[int]:
    """Load alert channel ID from config/.env or environment."""
    return _load_env_int("DISCORD_ALERT_CHANNEL_ID")


def _load_agent_channel_id() -> Optional[int]:
    """Load agent channel ID from config/.env or environment."""
    return _load_env_int("DISCORD_AGENT_CHANNEL_ID")


def _load_report_channel_id() -> Optional[int]:
    """Load report channel ID from config/.env or environment."""
    return _load_env_int("DISCORD_REPORT_CHANNEL_ID")


def _load_env_int(key: str) -> Optional[int]:
    """Load an integer value from env or config/.env."""
    raw = os.environ.get(key, "")
    if not raw:
        env_path = Path("config/.env")
        if env_path.exists():
            from dotenv import dotenv_values
            values = dotenv_values(env_path)
            raw = values.get(key, "")

    if raw and raw.strip():
        try:
            return int(raw.strip())
        except ValueError:
            logger.warning("Invalid %s: %s", key, raw)
    return None


# ---------------------------------------------------------------------------
# Embed helpers
# ---------------------------------------------------------------------------

def alert_to_embed(alert: Alert) -> discord.Embed:
    """Convert an Alert to a Discord Embed."""
    color = _SEVERITY_COLORS.get(alert.severity, discord.Color.greyple())
    emoji = _TYPE_EMOJI.get(alert.alert_type, "\u2139\ufe0f")

    embed = discord.Embed(
        title=f"{emoji} {alert.title}",
        description=alert.message,
        color=color,
        timestamp=alert.timestamp,
    )

    if alert.ticker:
        embed.set_author(name=alert.ticker)

    embed.add_field(name="Type", value=alert.alert_type.title(), inline=True)
    embed.add_field(name="Severity", value=alert.severity.upper(), inline=True)

    # Add key data fields
    for key, value in list(alert.data.items())[:3]:
        if isinstance(value, float):
            embed.add_field(name=key, value=f"{value:.2f}", inline=True)
        elif not isinstance(value, (list, dict)):
            embed.add_field(name=key, value=str(value), inline=True)

    embed.set_footer(text="MindfulRL Monitor")
    return embed


# ---------------------------------------------------------------------------
# Interactive Views (Buttons + Select Menus)
# ---------------------------------------------------------------------------

class AlertActionView(discord.ui.View):
    """Buttons attached to alert embeds — analyze or view news for the ticker."""

    def __init__(
        self, ticker: str, dal: DataAccessLayer,
        report_channel: Optional[discord.TextChannel] = None,
    ) -> None:
        super().__init__(timeout=300)  # 5 minutes
        self.ticker = ticker
        self._dal = dal
        self._report_channel = report_channel

    @discord.ui.button(label="Analyze", style=discord.ButtonStyle.primary, emoji="\U0001F50D")
    async def analyze_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(thinking=True)
        answer = await _run_agent_query(
            f"Run a full analysis on {self.ticker}. Cover technicals, fundamentals, "
            f"recent news sentiment, and provide an actionable recommendation.",
            self._dal,
        )
        await _send_long_followup(interaction, answer, self._report_channel)

    @discord.ui.button(label="News", style=discord.ButtonStyle.secondary, emoji="\U0001F4F0")
    async def news_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(thinking=True)
        answer = await _run_agent_query(
            f"Get recent news for {self.ticker} with sentiment analysis. "
            f"Summarize the key headlines and overall sentiment trend.",
            self._dal,
        )
        await _send_long_followup(interaction, answer, self._report_channel)


class SkillSelectView(discord.ui.View):
    """Dropdown to pick a skill when /skill is called without arguments."""

    def __init__(
        self, dal: DataAccessLayer,
        report_channel: Optional[discord.TextChannel] = None,
    ) -> None:
        super().__init__(timeout=120)
        self._dal = dal
        self._report_channel = report_channel

    @discord.ui.select(
        placeholder="Select a skill...",
        options=[
            discord.SelectOption(
                label="Full Analysis", value="full_analysis",
                description="Complete ticker analysis", emoji="\U0001F4CA",
            ),
            discord.SelectOption(
                label="Portfolio Scan", value="portfolio_scan",
                description="Scan entire watchlist", emoji="\U0001F4CB",
            ),
            discord.SelectOption(
                label="Earnings Prep", value="earnings_prep",
                description="Prepare for earnings report", emoji="\U0001F4C5",
            ),
            discord.SelectOption(
                label="Sector Rotation", value="sector_rotation",
                description="Analyze sector trends", emoji="\U0001F310",
            ),
        ],
    )
    async def skill_select(
        self, interaction: discord.Interaction, select: discord.ui.Select,
    ) -> None:
        selected = select.values[0]
        from src.agents.shared.skills import expand_skill, SKILL_REGISTRY

        skill_def = SKILL_REGISTRY.get(selected)
        if skill_def and skill_def.required_params:
            # Need ticker — ask via modal
            modal = TickerModal(
                skill_name=selected, dal=self._dal,
                report_channel=self._report_channel,
            )
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.defer(thinking=True)
            expanded = expand_skill(selected, {})
            if expanded:
                answer = await _run_agent_query(expanded, self._dal)
                await _send_long_followup(interaction, answer, self._report_channel)
            else:
                await interaction.followup.send("Failed to expand skill.")


class TickerModal(discord.ui.Modal, title="Enter Ticker"):
    """Modal to collect ticker input for skills that need it."""

    ticker_input = discord.ui.TextInput(
        label="Ticker Symbol",
        placeholder="e.g. NVDA",
        max_length=10,
        required=True,
    )

    def __init__(
        self, skill_name: str, dal: DataAccessLayer,
        report_channel: Optional[discord.TextChannel] = None,
    ) -> None:
        super().__init__()
        self._skill_name = skill_name
        self._dal = dal
        self._report_channel = report_channel

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from src.agents.shared.skills import expand_skill

        ticker = self.ticker_input.value.strip().upper()
        await interaction.response.defer(thinking=True)
        expanded = expand_skill(self._skill_name, {"ticker": ticker})
        if expanded:
            answer = await _run_agent_query(expanded, self._dal)
            await _send_long_followup(interaction, answer, self._report_channel)
        else:
            await interaction.followup.send(f"Failed to expand skill '{self._skill_name}' for {ticker}.")


# ---------------------------------------------------------------------------
# Agent query helper
# ---------------------------------------------------------------------------

async def _run_agent_query(question: str, dal: DataAccessLayer) -> str:
    """Run an agent query in a separate thread to avoid blocking Discord heartbeat.

    The Anthropic agent's tool execution (HTTP calls to Finnhub, IBKR, etc.)
    is synchronous and can block for 10-15+ seconds per tool.  Running the
    entire query on the Discord event-loop thread causes gateway heartbeat
    timeouts.  We solve this by running the async generator in a *new* event
    loop on a background thread via ``asyncio.to_thread``.
    """
    import asyncio

    def _sync_agent_call() -> str:
        """Blocking wrapper executed in a thread-pool thread."""
        from src.agents.anthropic_agent.agent import run_query_stream
        from src.agents.shared.events import EventType

        async def _consume() -> str:
            answer = ""
            async for event in run_query_stream(question=question, dal=dal):
                if event.type == EventType.done:
                    answer = event.data.get("answer", "No response.")
            return answer or "No response from agent."

        return asyncio.run(_consume())

    try:
        return await asyncio.to_thread(_sync_agent_call)
    except Exception:
        logger.exception("Agent query failed")
        return "Agent query failed. Check logs for details."


# ---------------------------------------------------------------------------
# Markdown → Discord formatting
# ---------------------------------------------------------------------------

import re as _re

def _format_for_discord(text: str) -> str:
    """Convert standard Markdown to Discord-compatible format.

    Discord natively supports: # ## ### headings, bold, italic, code
    blocks, block quotes, lists, masked links.

    Discord does NOT support: tables (| col | syntax), H4-H6, ---
    horizontal rules (renders as text, not a line).
    """
    # 1. Convert markdown tables to monospace code blocks.
    text = _convert_tables(text)

    # 2. H4-H6 → H3 (Discord only supports H1-H3).
    text = _re.sub(r"^#{4,6}\s+", "### ", text, flags=_re.MULTILINE)

    # 3. Horizontal rules → Unicode separator.
    text = _re.sub(
        r"^[ \t]*[-*_]{3,}[ \t]*$",
        "\u2501" * 20,  # ━━━━━━━━━━━━━━━━━━━━
        text,
        flags=_re.MULTILINE,
    )

    return text


def _convert_tables(text: str) -> str:
    """Wrap Markdown tables in ``` code blocks for monospace rendering."""
    lines = text.split("\n")
    result: List[str] = []
    table_lines: List[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        # Detect table rows: starts and ends with |, or is a separator row
        is_table_row = (
            stripped.startswith("|") and stripped.endswith("|")
        )

        if is_table_row:
            if not in_table:
                in_table = True
                result.append("```")
            # Skip separator rows like |---|---|
            if _re.match(r"^\|[\s\-:| ]+\|$", stripped):
                # Emit a separator using dashes
                result.append(stripped)
            else:
                result.append(line)
        else:
            if in_table:
                result.append("```")
                in_table = False
            result.append(line)

    if in_table:
        result.append("```")

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Smart message splitting
# ---------------------------------------------------------------------------

def _split_message(text: str, limit: int = 1900) -> List[str]:
    """Split text at paragraph/line boundaries, respecting Discord limits."""
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        # Try to break at: paragraph → newline → space
        cut = -1
        for sep in ("\n\n", "\n", " "):
            idx = remaining.rfind(sep, 0, limit)
            if idx > 0:
                cut = idx
                break

        if cut <= 0:
            # Hard break as last resort
            cut = limit

        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")

    return chunks


# ---------------------------------------------------------------------------
# Response senders
# ---------------------------------------------------------------------------

async def _send_long_followup(
    interaction: discord.Interaction,
    text: str,
    report_channel: Optional[discord.TextChannel] = None,
) -> None:
    """Send a formatted response as interaction followup.

    If *report_channel* is given, the full response goes there and only
    a short notice is sent back to the interaction.
    """
    if not text:
        text = "No response."
    text = _format_for_discord(text)

    if report_channel:
        # Send full response to #report as embeds
        await _send_as_embeds(report_channel, text)
        await interaction.followup.send(
            f"Analysis posted to <#{report_channel.id}>",
        )
        return

    # Send inline
    for chunk in _split_message(text):
        await interaction.followup.send(chunk)


async def _send_long_message(
    channel: discord.abc.Messageable,
    text: str,
    reference: Optional[discord.Message] = None,
    report_channel: Optional[discord.TextChannel] = None,
) -> None:
    """Send a formatted message to a channel.

    If *report_channel* is given, the full response goes there.
    """
    if not text:
        text = "No response."
    text = _format_for_discord(text)

    if report_channel:
        await _send_as_embeds(report_channel, text)
        await channel.send(
            f"Analysis posted to <#{report_channel.id}>",
            reference=reference,
        )
        return

    chunks = _split_message(text)
    await channel.send(chunks[0], reference=reference)
    for chunk in chunks[1:]:
        await channel.send(chunk)


async def _send_as_embeds(
    channel: discord.TextChannel,
    text: str,
    color: discord.Color = discord.Color.teal(),
) -> None:
    """Send long text as a sequence of Discord Embeds (max 4096 chars each).

    Up to 10 embeds per message, continuing in a new message if needed.
    """
    from datetime import datetime as _dt

    chunks = _split_message(text, limit=4000)
    embeds: List[discord.Embed] = []

    for i, chunk in enumerate(chunks):
        embed = discord.Embed(description=chunk, color=color)
        if i == 0:
            embed.set_author(name="MindfulRL Analysis")
        if i == len(chunks) - 1:
            embed.set_footer(text="MindfulRL Agent")
            embed.timestamp = _dt.now()
        embeds.append(embed)

    # Discord allows max 10 embeds per message
    for batch_start in range(0, len(embeds), 10):
        batch = embeds[batch_start:batch_start + 10]
        await channel.send(embeds=batch)


# ---------------------------------------------------------------------------
# Main Bot
# ---------------------------------------------------------------------------

class MindfulDiscordBot(discord.Client):
    """Discord bot for monitor alerts + two-way agent interaction.

    Features:
    - One-way alert notifications with severity-based channel routing
    - Slash commands: /ask, /analyze, /news, /scan, /skill
    - Buttons on alert embeds (Analyze, News)
    - Skill select dropdown menu
    - Free chat via @mention or dedicated #agent channel
    """

    def __init__(
        self,
        channel_id: Optional[int] = None,
        alert_channel_id: Optional[int] = None,
        agent_channel_id: Optional[int] = None,
        report_channel_id: Optional[int] = None,
        dal: Optional[DataAccessLayer] = None,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # Phase 3: needed for free chat
        super().__init__(intents=intents)

        self._channel_id = channel_id or _load_channel_id()
        self._alert_channel_id = alert_channel_id or _load_alert_channel_id()
        self._agent_channel_id = agent_channel_id or _load_agent_channel_id()
        self._report_channel_id = report_channel_id or _load_report_channel_id()

        self._ready_event = asyncio.Event()
        self._channel: Optional[discord.TextChannel] = None
        self._alert_channel: Optional[discord.TextChannel] = None
        self._agent_channel: Optional[discord.TextChannel] = None
        self._report_channel: Optional[discord.TextChannel] = None

        self._dal = dal
        self.tree = app_commands.CommandTree(self)
        self._setup_commands()

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def on_ready(self) -> None:
        logger.info("Discord bot connected as %s", self.user)

        # Resolve main channel
        self._channel = self._resolve_channel(self._channel_id, "main")
        if not self._channel:
            self._channel = self._auto_detect_channel()

        # Resolve alert channel (fallback to main)
        self._alert_channel = self._resolve_channel(self._alert_channel_id, "alert")

        # Resolve agent channel
        self._agent_channel = self._resolve_channel(self._agent_channel_id, "agent")

        # Resolve report channel (analysis results go here)
        self._report_channel = self._resolve_channel(self._report_channel_id, "report")

        # Sync slash commands per guild (instant) instead of global (up to 1h delay)
        try:
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info("Synced %d slash command(s) to guild %s", len(synced), guild.name)
        except Exception:
            logger.exception("Failed to sync slash commands")

        self._ready_event.set()

    def _resolve_channel(
        self, channel_id: Optional[int], label: str,
    ) -> Optional[discord.TextChannel]:
        """Resolve a channel by ID, logging the result."""
        if not channel_id:
            return None
        ch = self.get_channel(channel_id)
        if ch:
            logger.info("Resolved %s channel: #%s", label, ch.name)
        else:
            logger.warning("%s channel ID %d not found", label.title(), channel_id)
        return ch

    def _auto_detect_channel(self) -> Optional[discord.TextChannel]:
        """Auto-detect first text channel with send permissions."""
        for guild in self.guilds:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    self._channel_id = ch.id
                    logger.info("Auto-detected channel: #%s (guild: %s)", ch.name, guild.name)
                    return ch
        return None

    async def wait_until_ready_custom(self, timeout: float = 30) -> bool:
        """Wait until the bot is connected and channel is resolved."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return self._channel is not None
        except asyncio.TimeoutError:
            logger.error("Discord bot connection timed out")
            return False

    # ── Free chat (on_message) ────────────────────────────────────────

    async def on_message(self, message: discord.Message) -> None:
        # Ignore own messages and bot messages
        if message.author == self.user or message.author.bot:
            return

        # Dedicated #agent channel — all messages trigger agent
        if self._agent_channel and message.channel.id == self._agent_channel.id:
            await self._handle_agent_query(message)
            return

        # @MindfulRL mention in any channel
        if self.user and self.user.mentioned_in(message):
            await self._handle_agent_query(message)
            return

    async def _handle_agent_query(self, message: discord.Message) -> None:
        """Process a free-chat message through the agent."""
        if not self._dal:
            await message.reply("Agent not configured (no DAL).")
            return

        # Strip @mention to get clean question
        question = message.content
        if self.user:
            question = question.replace(f"<@{self.user.id}>", "").strip()
            question = question.replace(f"<@!{self.user.id}>", "").strip()
        if not question:
            await message.reply("Please provide a question.")
            return

        async with message.channel.typing():
            answer = await _run_agent_query(question, self._dal)

        await _send_long_message(
            message.channel, answer, reference=message,
            report_channel=self._report_channel,
        )

    # ── Alert sending (with severity routing) ─────────────────────────

    async def send_alert(self, alert: Alert) -> bool:
        """Send a single alert, routing by severity if alert channel is configured."""
        # Route critical/warning to alert channel if available
        channel = self._channel
        if alert.severity in ("critical", "warning") and self._alert_channel:
            channel = self._alert_channel

        if not channel:
            logger.warning("No Discord channel available")
            return False

        try:
            embed = alert_to_embed(alert)
            # Attach buttons if alert has a ticker and DAL is available
            view = None
            if alert.ticker and self._dal:
                view = AlertActionView(
                    alert.ticker, self._dal,
                    report_channel=self._report_channel,
                )
            await channel.send(embed=embed, view=view)
            return True
        except Exception:
            logger.exception("Failed to send Discord alert")
            return False

    async def send_alerts(self, alerts: List[Alert]) -> int:
        """Send multiple alerts. Returns count of successful sends."""
        sent = 0
        for alert in alerts:
            if await self.send_alert(alert):
                sent += 1
        return sent

    async def send_summary(self, summary: str) -> bool:
        """Send a plain text summary (e.g., scan results)."""
        if not self._channel:
            return False

        try:
            if len(summary) > 1900:
                summary = summary[:1900] + "\n... (truncated)"
            await self._channel.send(f"```\n{summary}\n```")
            return True
        except Exception:
            logger.exception("Failed to send Discord summary")
            return False

    # ── Slash commands setup ──────────────────────────────────────────

    def _setup_commands(self) -> None:
        """Register all slash commands on the CommandTree."""
        bot = self  # capture for closures

        @self.tree.command(name="ask", description="Ask the AI agent a question")
        @app_commands.describe(question="Your question")
        async def ask_cmd(interaction: discord.Interaction, question: str) -> None:
            if not bot._dal:
                await interaction.response.send_message("Agent not configured.")
                return
            await interaction.response.defer(thinking=True)
            answer = await _run_agent_query(question, bot._dal)
            await _send_long_followup(interaction, answer, bot._report_channel)

        @self.tree.command(name="analyze", description="Run full analysis on a ticker")
        @app_commands.describe(ticker="Stock ticker symbol (e.g. NVDA)")
        async def analyze_cmd(interaction: discord.Interaction, ticker: str) -> None:
            if not bot._dal:
                await interaction.response.send_message("Agent not configured.")
                return
            await interaction.response.defer(thinking=True)
            from src.agents.shared.skills import expand_skill
            expanded = expand_skill("full_analysis", {"ticker": ticker.upper()})
            if expanded:
                answer = await _run_agent_query(expanded, bot._dal)
            else:
                answer = await _run_agent_query(
                    f"Run a full analysis on {ticker.upper()}.", bot._dal,
                )
            await _send_long_followup(interaction, answer, bot._report_channel)

        @self.tree.command(name="news", description="Get recent news and sentiment for a ticker")
        @app_commands.describe(ticker="Stock ticker symbol (e.g. NVDA)")
        async def news_cmd(interaction: discord.Interaction, ticker: str) -> None:
            if not bot._dal:
                await interaction.response.send_message("Agent not configured.")
                return
            await interaction.response.defer(thinking=True)
            answer = await _run_agent_query(
                f"Get recent news for {ticker.upper()} with sentiment analysis. "
                f"Summarize the key headlines and overall sentiment trend.",
                bot._dal,
            )
            await _send_long_followup(interaction, answer, bot._report_channel)

        @self.tree.command(name="scan", description="Scan watchlist for alerts")
        async def scan_cmd(interaction: discord.Interaction) -> None:
            if not bot._dal:
                await interaction.response.send_message("Agent not configured.")
                return
            await interaction.response.defer(thinking=True)
            from .engine import MonitorEngine
            engine = MonitorEngine(dal=bot._dal)
            alerts = await engine.scan_once(notify=False)
            summary = engine.format_scan_summary(alerts)
            if len(summary) > 1900:
                summary = summary[:1900] + "\n... (truncated)"
            await interaction.followup.send(f"```\n{summary}\n```")

        @self.tree.command(name="skill", description="Run a predefined analysis skill")
        @app_commands.describe(
            name="Skill name or alias (leave empty for menu)",
            ticker="Ticker symbol (if required by skill)",
        )
        async def skill_cmd(
            interaction: discord.Interaction,
            name: str = "",
            ticker: str = "",
        ) -> None:
            if not bot._dal:
                await interaction.response.send_message("Agent not configured.")
                return

            # No skill specified → show dropdown
            if not name:
                view = SkillSelectView(bot._dal, report_channel=bot._report_channel)
                await interaction.response.send_message(
                    "Select a skill:", view=view, ephemeral=True,
                )
                return

            from src.agents.shared.skills import parse_skill_command, expand_skill
            skill_name, params = parse_skill_command(
                f"{name} {ticker}".strip(),
            )
            if not skill_name:
                await interaction.response.send_message(
                    f"Unknown skill: `{name}`. Available: full_analysis, "
                    f"portfolio_scan, earnings_prep, sector_rotation",
                )
                return

            await interaction.response.defer(thinking=True)
            expanded = expand_skill(skill_name, params)
            if expanded:
                answer = await _run_agent_query(expanded, bot._dal)
            else:
                answer = f"Failed to expand skill '{skill_name}'. Missing required parameters?"
            await _send_long_followup(interaction, answer, bot._report_channel)

    # ── Bot start ─────────────────────────────────────────────────────

    async def start_bot(self) -> None:
        """Start the bot (call from an existing event loop)."""
        token = _load_token()
        if not token:
            raise ValueError(
                "DISCORD_BOT_TOKEN not set. "
                "Add it to config/.env or set the environment variable."
            )
        await self.start(token)