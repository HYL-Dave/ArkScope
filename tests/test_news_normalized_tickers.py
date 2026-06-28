import sqlite3

from src.news_normalized.tickers import canonical_ticker, load_ticker_aliases


def test_canonical_ticker_normalizes_spelling_through_shared_alias_map():
    aliases = {"LC": "HAPN", "BRK.B": "BRK B"}

    assert canonical_ticker(" lc ", aliases) == "HAPN"
    assert canonical_ticker("brk.b", aliases) == "BRK B"
    assert canonical_ticker("aapl", aliases) == "AAPL"


def test_load_ticker_aliases_is_safe_for_precanonical_database():
    conn = sqlite3.connect(":memory:")

    assert load_ticker_aliases(conn) == {}

    conn.execute(
        "CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO ticker_aliases VALUES (?,?)",
        [("LC", "HAPN"), ("BRK.B", "BRK B")],
    )
    assert load_ticker_aliases(conn) == {"BRK.B": "BRK B", "LC": "HAPN"}
