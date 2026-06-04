"""
Entry point: python -m src.api

Bind host/port/reload are env-driven so the desktop shell can spawn the sidecar
on a private 127.0.0.1 ephemeral port without reload (clean child shutdown):
    ARKSCOPE_API_HOST   (default 0.0.0.0 — unchanged dev default)
    ARKSCOPE_API_PORT   (default 8420)
    ARKSCOPE_API_RELOAD (default 1; the shell sets 0)
"""

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("ARKSCOPE_API_HOST", "0.0.0.0")
    port = int(os.environ.get("ARKSCOPE_API_PORT", "8420"))
    reload = os.environ.get("ARKSCOPE_API_RELOAD", "1") == "1"
    uvicorn.run(
        "src.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
