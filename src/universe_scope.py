from src.active_universe import build_active_universe_snapshot


def resolve_active_universe() -> list[str]:
    return list(build_active_universe_snapshot().tickers)
