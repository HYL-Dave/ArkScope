"""
Entry point: python -m src.api
"""

import uvicorn

from .app import create_app

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8420,
        reload=True,
    )