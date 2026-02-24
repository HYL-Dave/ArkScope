"""
Discord Bot for monitor notifications.

Sends Alert embeds to configured Discord channels.
Phase 2: one-way notifications (alerts → Discord).
Phase 3 will add slash commands for two-way interaction.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

import discord

from .notifiers import Alert

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


def _load_token() -> str:
    """Load Discord bot token from config/.env or environment."""
    # Try environment first
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if token:
        return token

    # Try config/.env
    env_path = Path("config/.env")
    if env_path.exists():
        from dotenv import dotenv_values
        values = dotenv_values(env_path)
        token = values.get("DISCORD_BOT_TOKEN", "")

    return token


def _load_channel_id() -> Optional[int]:
    """Load Discord channel ID from config/.env or environment."""
    raw = os.environ.get("DISCORD_CHANNEL_ID", "")
    if not raw:
        env_path = Path("config/.env")
        if env_path.exists():
            from dotenv import dotenv_values
            values = dotenv_values(env_path)
            raw = values.get("DISCORD_CHANNEL_ID", "")

    if raw and raw.strip():
        try:
            return int(raw.strip())
        except ValueError:
            logger.warning("Invalid DISCORD_CHANNEL_ID: %s", raw)
    return None


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


class MindfulDiscordBot(discord.Client):
    """Discord bot for sending monitor alerts.

    Usage:
        bot = MindfulDiscordBot()
        await bot.start_bot()  # connects and stays ready
        await bot.send_alert(alert)  # send individual alert
        await bot.send_alerts(alerts)  # send batch
        await bot.close()
    """

    def __init__(self, channel_id: Optional[int] = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = False  # Phase 2: no need to read messages
        super().__init__(intents=intents)

        self._channel_id = channel_id or _load_channel_id()
        self._ready_event = asyncio.Event()
        self._channel: Optional[discord.TextChannel] = None

    async def on_ready(self) -> None:
        logger.info("Discord bot connected as %s", self.user)

        if self._channel_id:
            self._channel = self.get_channel(self._channel_id)
            if self._channel:
                logger.info("Target channel: #%s", self._channel.name)
            else:
                logger.warning("Channel ID %d not found", self._channel_id)
        else:
            # Auto-detect first text channel
            for guild in self.guilds:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        self._channel = ch
                        self._channel_id = ch.id
                        logger.info(
                            "Auto-detected channel: #%s (guild: %s)",
                            ch.name, guild.name,
                        )
                        break
                if self._channel:
                    break

        self._ready_event.set()

    async def wait_until_ready_custom(self, timeout: float = 30) -> bool:
        """Wait until the bot is connected and channel is resolved."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return self._channel is not None
        except asyncio.TimeoutError:
            logger.error("Discord bot connection timed out")
            return False

    async def send_alert(self, alert: Alert) -> bool:
        """Send a single alert as an embed to the configured channel."""
        if not self._channel:
            logger.warning("No Discord channel available")
            return False

        try:
            embed = alert_to_embed(alert)
            await self._channel.send(embed=embed)
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
            # Discord message limit is 2000 chars
            if len(summary) > 1900:
                summary = summary[:1900] + "\n... (truncated)"
            await self._channel.send(f"```\n{summary}\n```")
            return True
        except Exception:
            logger.exception("Failed to send Discord summary")
            return False

    async def start_bot(self) -> None:
        """Start the bot (call from an existing event loop)."""
        token = _load_token()
        if not token:
            raise ValueError(
                "DISCORD_BOT_TOKEN not set. "
                "Add it to config/.env or set the environment variable."
            )
        await self.start(token)