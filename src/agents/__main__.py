"""
Entry point for: python -m src.agents

Launches the interactive CLI chat.
"""

import logging

from .cli import main

# Suppress asyncio SSL cleanup noise from optional OpenAI websocket transport
# on exit. HTTP is the default; when websocket is explicitly enabled, the
# connection may not be fully closed during event-loop shutdown, producing
# harmless "Fatal error on SSL transport" / "Event loop is closed" messages.
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

main()
