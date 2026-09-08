import importlib.util
from pathlib import Path
import sqlite3

import pytest


spec = importlib.util.spec_from_file_location("price_readback", Path(__file__).with_name("readback.py"))
readback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readback)


def test_readback_allows_prices_but_not_credentials_or_mutation(tmp_path):
    path = tmp_path / "market.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE prices(close REAL)")
        conn.execute("INSERT INTO prices VALUES(1)")
        conn.execute("CREATE TABLE data_provider_config(value TEXT)")
    with readback.readonly_databases({"market": path}):
        with pytest.raises(ValueError, match="readback_database_scope"):
            sqlite3.connect(path)
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            assert conn.execute("SELECT close FROM prices").fetchall() == [(1,)]
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("SELECT value FROM data_provider_config").fetchall()
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM prices")
        finally:
            conn.close()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM prices").fetchone()[0] == 1


def test_readback_does_not_allow_provider_connections_or_children():
    for event in ("socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"):
        with pytest.raises(ValueError, match="readback_external_operation_forbidden"):
            readback.no_network_or_process(event, ())
    readback.no_network_or_process("open", ())
