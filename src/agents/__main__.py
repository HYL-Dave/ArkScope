"""
Entry point for: python -m src.agents

Launches the interactive CLI chat.
"""

import logging

from .cli import main

# Suppress asyncio SSL cleanup noise from WebSocket transport on exit.
# The WebSocket connection may not be fully closed when the event loop shuts
# down, producing harmless "Fatal error on SSL transport" / "Event loop is
# closed" messages.  This only affects log output, not functionality.
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

main()