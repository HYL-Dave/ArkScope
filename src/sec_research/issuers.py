"""Exact SEC issuer identifiers and official ticker-map decoding."""

import re

from .common import SourceError, decode_object, normalize_cik, text_value


TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_TICKER = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,19}")


def parse_issuer(value: str) -> tuple[str, str]:
    """Accept explicit CIKs or exact uppercase SEC symbols, without aliasing."""
    if not isinstance(value, str):
        raise SourceError("sec_issuer_invalid")
    value = value.strip()
    if value.lower().startswith("cik:") or re.fullmatch(r"[0-9]{1,10}", value):
        try:
            return "cik", normalize_cik(value)
        except SourceError:
            raise SourceError("sec_issuer_invalid") from None
    # Reject Unicode case expansions into otherwise valid ASCII symbols.
    if not value.isascii() or _TICKER.fullmatch(value.upper()) is None:
        raise SourceError("sec_issuer_invalid")
    return "ticker", value.upper()


def parse_ticker_map(body: bytes) -> dict[str, tuple[str, ...]]:
    """Validate every official row; retain distinct CIKs for duplicate symbols."""
    payload = decode_object(body)
    symbols = {}
    for key, row in payload.items():
        if (re.fullmatch(r"[0-9]+", key) is None or not isinstance(row, dict)
                or set(row) != {"cik_str", "ticker", "title"}
                or type(row["cik_str"]) is not int
                or not isinstance(row["ticker"], str)
                or _TICKER.fullmatch(row["ticker"]) is None):
            raise SourceError("issuer_map_invalid")
        text_value(row["title"], "/" + key + "/title")
        cik = normalize_cik(str(row["cik_str"]))
        symbols.setdefault(row["ticker"], set()).add(cik)
    return {symbol: tuple(sorted(ciks)) for symbol, ciks in symbols.items()}
