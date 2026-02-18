"""Shared database configuration utilities.

Centralizes DSN loading and SSL mode detection used by:
- src/tools/data_access.py (DAL auto-detect)
- scripts/migrate_to_supabase.py (data import)
- tests/test_db_backend.py (integration tests)
"""

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


def load_database_url(env_path: Path) -> Optional[str]:
    """Load DATABASE_URL (primary) or SUPABASE_DB_URL (legacy) from .env file.

    Priority: DATABASE_URL > SUPABASE_DB_URL.
    Returns None if no valid PostgreSQL DSN is found.
    """
    if not env_path.exists():
        return None
    dsn = None
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    continue
                if line.startswith("DATABASE_URL="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and val.startswith("postgresql"):
                        dsn = val
                elif line.startswith("SUPABASE_DB_URL=") and dsn is None:
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and val.startswith("postgresql"):
                        dsn = val
    except Exception:
        return None
    return dsn


def load_sslmode(env_path: Path, dsn: str) -> str:
    """Load DB_SSLMODE from .env, or auto-detect from DSN hostname."""
    if env_path.exists():
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DB_SSLMODE=") and not line.startswith("#"):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return infer_sslmode(dsn)


def infer_sslmode(dsn: str) -> str:
    """Auto-detect sslmode from DSN hostname.

    Returns "disable" for local/LAN addresses, "require" for remote.
    """
    try:
        host = urlparse(dsn).hostname or ""
        if host in ("localhost", "127.0.0.1", "::1"):
            return "disable"
        if host.startswith("192.168.") or host.startswith("10."):
            return "disable"
    except Exception:
        pass
    return "require"