# Current Quote Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class current stock quote capability for agents and the API, using IBKR snapshot data first and an explicitly labeled local last-bar fallback.

**Architecture:** This slice adds a read-through quote tool; it does not add ingestion, scheduling, or persistence. `IBKRDataSource.get_current_quote()` is the provider adapter, wrapped by a small `src.tools.current_quote` contract that normalizes IBKR snapshots and local fallback bars into one Pydantic result. Tool registry, OpenAI/Anthropic bridge tools, OAuth research allowlists, and `/prices/{ticker}/quote` all expose the same read-only capability.

**Tech Stack:** Python, FastAPI, Pydantic, existing ToolRegistry/agent tool wiring, IBKR Gateway through `data_sources.ibkr_source.IBKRDataSource`, local SQLite price bars through `DataAccessLayer`.

---

## Concurrency With Track A

This slice is safe to develop in parallel with Investor Profile Track A if it stays in an isolated branch/worktree. Expected overlap is low:

- Current Quote touches: `src/tools/schemas.py`, `src/tools/current_quote.py`, `src/tools/registry.py`, `src/api/routes/prices.py`, agent tool wiring, OAuth allowlists, price/tool tests.
- Track A touches: profile store/routes, query/card prompt assembly, run trace metadata, settings UI.

Potential shared files are limited to agent bridge files if Track A changes query execution. If a merge conflict appears, resolve by preserving both changes: Track A personalization must not affect tool results, and quote tool registration must remain read-only.

---

## Grounding

Current code has price history, but not current quote:

- `src/tools/price_tools.py` exposes `get_ticker_prices`, `get_price_change`, and `get_sector_performance`; all are based on local OHLCV bars.
- `src/tools/registry.py::_register_price_tools` registers those three tools only.
- `src/api/routes/prices.py` exposes bars/change/sector only.
- `data_sources/ibkr_source.py::IBKRDataSource.get_current_quote()` already exists and uses `reqMktData(..., snapshot=True)`.
- `src/tools/option_chain_tools.py` already calls `ibkr.get_current_quote(ticker)` internally for option-chain spot price.
- `src/auth_drivers/claude_code_sdk_driver.py` and `src/auth_drivers/chatgpt_oauth_driver.py` have hardcoded read-only allowlists. Adding a registry tool is not enough for subscription-backed research.

---

## Decisions Locked

1. **Do not call it guaranteed real-time.** IBKR snapshot may be live or delayed depending on subscriptions and Gateway settings. The returned `mode` is `ibkr_snapshot`, with `source_note` explaining entitlement ambiguity.
2. **No persistence.** Quote reads do not write `market_data.db`, job telemetry, or scheduler state.
3. **Fallback is explicit.** If `source="auto"` and IBKR fails or returns no usable price, return the latest local bar as `mode="local_last_bar"` with `stale=True`; do not pretend it is current.
4. **`source="ibkr"` is strict.** If IBKR fails, return `mode="unavailable"` and do not fall back.
5. **`source="local"` never touches IBKR.** It returns latest local bar or unavailable.
6. **Separate IBKR client id domain.** Add `quotes` to `data_sources.ibkr_client_id.DOMAIN_OFFSETS` with offset `5`, avoiding collision with `options=10`, `prices=20`, `news=30`, and `iv=40`.
7. **No Polygon/Finnhub in v1.** Provider quote capability display can add those later with explicit free-tier semantics.
8. **No UI panel in v1 unless a later review requests it.** This slice delivers the agent tool and API surface. Existing UI can call the API later.

---

## Files

- Create `src/tools/current_quote.py` — normalization, IBKR snapshot wrapper, local fallback, public `get_current_quote()`.
- Modify `src/tools/schemas.py` — add `CurrentQuoteResult`.
- Modify `data_sources/ibkr_client_id.py` — add `quotes` offset and label.
- Modify `src/tools/registry.py` — register `get_current_quote`.
- Modify `src/agents/openai_agent/tools.py` — expose OpenAI agent function tool.
- Modify `src/agents/anthropic_agent/tools.py` — expose Anthropic tool schema + dispatcher.
- Modify `src/auth_drivers/claude_code_sdk_driver.py` and `src/auth_drivers/chatgpt_oauth_driver.py` — add quote to read-only allowlists.
- Modify `src/api/routes/prices.py` — add `GET /prices/{ticker}/quote`.
- Modify tests:
  - `tests/test_current_quote_tools.py` (new)
  - `tests/test_option_chain_tools.py`
  - `tests/test_tools.py`
  - `tests/test_agents.py`
  - `tests/test_claude_code_sdk_driver.py`
  - `tests/test_prices_quote_route.py` (new)

---

## Task 1: Quote Result Contract + Local Fallback

**Files:**
- Modify: `src/tools/schemas.py`
- Create: `src/tools/current_quote.py`
- Test: `tests/test_current_quote_tools.py`

- [ ] **Step 1: Write failing schema/local tests**

Create `tests/test_current_quote_tools.py`:

```python
from types import SimpleNamespace

from src.tools.current_quote import get_current_quote


class _FakeDAL:
    def __init__(self, bars):
        self._bars = bars
        self.calls = []

    def get_prices(self, ticker, interval="15min", days=30):
        self.calls.append((ticker, interval, days))
        return SimpleNamespace(ticker=ticker.upper(), interval=interval, count=len(self._bars), bars=self._bars)


def _bar(ts="2026-07-07T14:45:00+00:00", close=123.45):
    return SimpleNamespace(datetime=ts, close=close, open=120.0, high=124.0, low=119.5, volume=1000)


def test_local_quote_returns_explicit_last_bar():
    dal = _FakeDAL([_bar()])

    result = get_current_quote(dal, "nvda", source="local")

    assert result.ticker == "NVDA"
    assert result.provider == "local"
    assert result.mode == "local_last_bar"
    assert result.price == 123.45
    assert result.close == 123.45
    assert result.timestamp == "2026-07-07T14:45:00+00:00"
    assert result.stale is True
    assert "last stored bar" in result.source_note
    assert dal.calls == [("NVDA", "15min", 10)]


def test_local_quote_unavailable_when_no_bars():
    result = get_current_quote(_FakeDAL([]), "MSFT", source="local")

    assert result.ticker == "MSFT"
    assert result.provider == "local"
    assert result.mode == "unavailable"
    assert result.price is None
    assert result.error == "no_local_price_bars"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_current_quote_tools.py -q
```

Expected: FAIL because `src.tools.current_quote` and `CurrentQuoteResult` do not exist.

- [ ] **Step 3: Add `CurrentQuoteResult`**

Add to `src/tools/schemas.py` after `PriceQueryResult`:

```python
class CurrentQuoteResult(BaseModel):
    """Read-through current quote result.

    ``mode`` is intentionally explicit:
      - ibkr_snapshot: IBKR returned a snapshot; live-vs-delayed depends on account entitlement.
      - local_last_bar: fallback to latest stored OHLCV close; not current.
      - unavailable: no usable quote from the requested source.
    """
    ticker: str
    provider: str
    mode: str
    price: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    timestamp: Optional[str] = None
    currency: Optional[str] = None
    stale: bool = False
    source_note: str = ""
    error: Optional[str] = None
```

- [ ] **Step 4: Add local quote implementation**

Create `src/tools/current_quote.py`:

```python
"""Current quote tool.

Read-through only: no persistence, no scheduling, no telemetry writes.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .schemas import CurrentQuoteResult

if TYPE_CHECKING:
    from .data_access import DataAccessLayer


_VALID_SOURCES = {"auto", "ibkr", "local"}


def _clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out <= 0:
        return None
    return out


def _clean_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out if out >= 0 else None


def _local_last_bar_quote(dal: DataAccessLayer, ticker: str) -> CurrentQuoteResult:
    t = ticker.upper()
    result = dal.get_prices(t, interval="15min", days=10)
    if not result.bars:
        result = dal.get_prices(t, interval="1d", days=365)
    if not result.bars:
        return CurrentQuoteResult(
            ticker=t,
            provider="local",
            mode="unavailable",
            error="no_local_price_bars",
            source_note="No stored local price bars were available.",
        )
    bar = result.bars[-1]
    close = _clean_float(getattr(bar, "close", None))
    volume = _clean_int(getattr(bar, "volume", None))
    return CurrentQuoteResult(
        ticker=t,
        provider="local",
        mode="local_last_bar",
        price=close,
        close=close,
        volume=volume,
        timestamp=str(getattr(bar, "datetime", "")) or None,
        stale=True,
        source_note="Latest stored local OHLCV close; this is not a live quote.",
    )


def _quote_from_ibkr_payload(ticker: str, payload: dict[str, Any]) -> CurrentQuoteResult:
    bid = _clean_float(payload.get("bid"))
    ask = _clean_float(payload.get("ask"))
    last = _clean_float(payload.get("last"))
    close = _clean_float(payload.get("close"))
    mid = ((bid + ask) / 2.0) if bid is not None and ask is not None else None
    price = last or mid or close
    if price is None:
        return CurrentQuoteResult(
            ticker=ticker.upper(),
            provider="ibkr",
            mode="unavailable",
            error="ibkr_quote_no_price",
            source_note="IBKR returned a snapshot but no usable last, bid/ask midpoint, or close.",
        )
    return CurrentQuoteResult(
        ticker=ticker.upper(),
        provider="ibkr",
        mode="ibkr_snapshot",
        price=round(price, 6),
        bid=bid,
        ask=ask,
        last=last,
        close=close,
        volume=_clean_int(payload.get("volume")),
        timestamp=datetime.now(timezone.utc).isoformat(),
        stale=False,
        source_note="IBKR market-data snapshot; live vs delayed depends on account subscriptions and Gateway market-data type.",
    )


def _fetch_ibkr_quote(ticker: str) -> CurrentQuoteResult:
    from data_sources.ibkr_client_id import ibkr_client_id_for
    from data_sources.ibkr_source import IBKRDataSource

    source = IBKRDataSource(client_id=ibkr_client_id_for("quotes"), readonly=True)
    try:
        source.connect()
        payload = source.get_current_quote(ticker.upper()) or {}
    finally:
        source.disconnect()
    return _quote_from_ibkr_payload(ticker, payload)


def get_current_quote(
    dal: DataAccessLayer,
    ticker: str,
    source: str = "auto",
) -> CurrentQuoteResult:
    """Return a current quote or an explicitly labeled local fallback."""
    t = ticker.upper()
    src = (source or "auto").lower()
    if src not in _VALID_SOURCES:
        return CurrentQuoteResult(
            ticker=t,
            provider=src,
            mode="unavailable",
            error="invalid_quote_source",
            source_note="source must be one of: auto, ibkr, local",
        )
    if src == "local":
        return _local_last_bar_quote(dal, t)
    try:
        quote = _fetch_ibkr_quote(t)
    except Exception as exc:
        quote = CurrentQuoteResult(
            ticker=t,
            provider="ibkr",
            mode="unavailable",
            error=f"ibkr_quote_failed:{type(exc).__name__}",
            source_note="IBKR quote request failed.",
        )
    if quote.mode != "unavailable" or src == "ibkr":
        return quote
    fallback = _local_last_bar_quote(dal, t)
    fallback.source_note = f"IBKR unavailable ({quote.error}); {fallback.source_note}"
    return fallback
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_current_quote_tools.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tools/schemas.py src/tools/current_quote.py tests/test_current_quote_tools.py
git commit -m "feat: add current quote contract"
```

---

## Task 2: IBKR Quote Source + Client-ID Domain

**Files:**
- Modify: `data_sources/ibkr_client_id.py`
- Modify: `tests/test_option_chain_tools.py`
- Test: `tests/test_current_quote_tools.py`

- [ ] **Step 1: Add failing IBKR tests**

Append to `tests/test_current_quote_tools.py`:

```python
def test_ibkr_quote_uses_quotes_client_id_and_disconnects(monkeypatch):
    import src.tools.current_quote as mod

    seen = {}

    class _FakeIBKR:
        def __init__(self, **kwargs):
            seen["init"] = kwargs

        def connect(self):
            seen["connected"] = True

        def get_current_quote(self, ticker):
            seen["ticker"] = ticker
            return {"bid": 100.0, "ask": 102.0, "last": 101.25, "close": 99.5, "volume": 1234}

        def disconnect(self):
            seen["disconnected"] = True

    monkeypatch.setattr("data_sources.ibkr_client_id.ibkr_client_id_for", lambda domain: 606 if domain == "quotes" else -1)
    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _FakeIBKR)

    result = mod.get_current_quote(_FakeDAL([]), "aapl", source="ibkr")

    assert seen["init"] == {"client_id": 606, "readonly": True}
    assert seen["connected"] is True
    assert seen["ticker"] == "AAPL"
    assert seen["disconnected"] is True
    assert result.provider == "ibkr"
    assert result.mode == "ibkr_snapshot"
    assert result.price == 101.25
    assert result.bid == 100.0
    assert result.ask == 102.0
    assert result.volume == 1234


def test_auto_falls_back_to_local_when_ibkr_unavailable(monkeypatch):
    import src.tools.current_quote as mod

    monkeypatch.setattr(mod, "_fetch_ibkr_quote", lambda ticker: (_ for _ in ()).throw(RuntimeError("gateway down")))

    result = mod.get_current_quote(_FakeDAL([_bar(close=88.0)]), "aapl", source="auto")

    assert result.provider == "local"
    assert result.mode == "local_last_bar"
    assert result.price == 88.0
    assert "ibkr_quote_failed" in result.source_note


def test_strict_ibkr_does_not_fallback(monkeypatch):
    import src.tools.current_quote as mod

    monkeypatch.setattr(mod, "_fetch_ibkr_quote", lambda ticker: (_ for _ in ()).throw(RuntimeError("gateway down")))

    result = mod.get_current_quote(_FakeDAL([_bar(close=88.0)]), "aapl", source="ibkr")

    assert result.provider == "ibkr"
    assert result.mode == "unavailable"
    assert result.price is None
    assert result.error == "ibkr_quote_failed:RuntimeError"
```

Append to `tests/test_option_chain_tools.py`:

```python
def test_ibkr_client_id_quotes_domain(monkeypatch):
    from data_sources.ibkr_client_id import ibkr_client_id_for

    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)

    assert ibkr_client_id_for("quotes") == 6
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_current_quote_tools.py tests/test_option_chain_tools.py::test_ibkr_client_id_quotes_domain -q
```

Expected: FAIL because `quotes` is not a known domain.

- [ ] **Step 3: Add client-id domain**

Modify `data_sources/ibkr_client_id.py`:

```python
DOMAIN_OFFSETS = {
    "manual": 0,
    "quotes": 5,   # ad hoc read-through quote snapshots
    "options": 10,
    "prices": 20,
    "news": 30,
    "iv": 40,
}
```

and:

```python
DOMAIN_LABELS_ZH = {
    "manual": "基底",
    "quotes": "即時股價",
    "options": "選擇權",
    "prices": "股價",
    "news": "新聞",
    "iv": "IV",
}
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_current_quote_tools.py tests/test_option_chain_tools.py::test_ibkr_client_id_quotes_domain tests/test_option_chain_tools.py::test_get_ibkr_uses_options_domain_client_id -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data_sources/ibkr_client_id.py tests/test_current_quote_tools.py tests/test_option_chain_tools.py
git commit -m "feat: wire ibkr quote client id"
```

---

## Task 3: Tool Registry + Agent Tool Wiring

**Files:**
- Modify: `src/tools/registry.py`
- Modify: `src/agents/openai_agent/tools.py`
- Modify: `src/agents/anthropic_agent/tools.py`
- Modify: `src/auth_drivers/claude_code_sdk_driver.py`
- Modify: `src/auth_drivers/chatgpt_oauth_driver.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_claude_code_sdk_driver.py`

- [ ] **Step 1: Write/update failing registry and agent tests**

Modify `tests/test_tools.py`:

```python
def test_register_all(self, registry):
    """All tools should be registered (incl. current quote)."""
    assert len(registry.list_all()) == 55
```

and include `"get_current_quote"` after `"get_ticker_prices"` in `TestRegistry::test_tool_names`.

Modify `tests/test_agents.py`:

```python
def test_tool_count(self):
    """All bridge tools (registry + delegate_to_subagent)."""
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    tools = get_anthropic_tools()
    assert len(tools) == 56
```

and include `"get_current_quote"` after `"get_ticker_prices"` in `TestAnthropicToolSchemas::test_tool_names`.

Modify `tests/test_claude_code_sdk_driver.py` by adding this test near the allowlist tests:

```python
def test_current_quote_is_research_readonly_allowlisted():
    from src.auth_drivers.chatgpt_oauth_driver import _RESEARCH_READONLY_TOOLS as openai_tools
    from src.auth_drivers.claude_code_sdk_driver import _RESEARCH_READONLY_TOOLS as claude_tools

    assert "get_current_quote" in openai_tools
    assert "get_current_quote" in claude_tools
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_tools.py::TestRegistry::test_register_all tests/test_tools.py::TestRegistry::test_tool_names tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names tests/test_claude_code_sdk_driver.py::test_current_quote_is_research_readonly_allowlisted -q
```

Expected: FAIL because the tool is not registered/wired.

- [ ] **Step 3: Register ToolRegistry tool**

Modify `src/tools/registry.py::_register_price_tools` import:

```python
from .current_quote import get_current_quote
from .price_tools import (
    get_ticker_prices,
    get_price_change,
    get_sector_performance,
)
```

Add before `get_ticker_prices`:

```python
self.register(ToolDefinition(
    name="get_current_quote",
    description=(
        "Get a read-through current quote for a stock ticker. Uses IBKR snapshot "
        "when available; source='auto' may fall back to the latest local bar, "
        "explicitly marked as local_last_bar."
    ),
    function=get_current_quote,
    category="prices",
    parameters=[
        ToolParameter("ticker", "string", "Stock ticker symbol"),
        ToolParameter("source", "string", "Quote source", required=False, default="auto",
                      enum=["auto", "ibkr", "local"]),
    ],
))
```

- [ ] **Step 4: Wire OpenAI agent tool**

Modify `src/agents/openai_agent/tools.py` import block:

```python
from src.tools.current_quote import get_current_quote
```

Add after `tool_get_ticker_prices`:

```python
@function_tool
def tool_get_current_quote(ticker: str, source: str = "auto") -> str:
    """Get a read-through current quote for a stock ticker.

    source='auto' tries IBKR first and may fall back to latest local bar.
    source='ibkr' is strict IBKR snapshot.
    source='local' returns latest stored local bar only.
    """
    result = get_current_quote(dal, ticker, source=source)
    return _serialize_result(result, "get_current_quote")
```

Add `tool_get_current_quote` to the returned tool list immediately after `tool_get_ticker_prices`.

- [ ] **Step 5: Wire Anthropic tool schema and dispatcher**

Modify `src/agents/anthropic_agent/tools.py`:

1. Add a schema entry next to `get_ticker_prices`:

```python
{
    "name": "get_current_quote",
    "description": (
        "Get a read-through current quote for a stock ticker. Uses IBKR snapshot "
        "when available; source='auto' may fall back to latest local bar."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol"},
            "source": {
                "type": "string",
                "enum": ["auto", "ibkr", "local"],
                "description": "Quote source. auto=IBKR then explicit local fallback.",
                "default": "auto",
            },
        },
        "required": ["ticker"],
    },
},
```

2. Import `get_current_quote` where price tools are imported.

3. Add dispatcher entry:

```python
"get_current_quote": lambda: get_current_quote(
    dal,
    tool_input["ticker"],
    source=tool_input.get("source", "auto"),
),
```

- [ ] **Step 6: Add OAuth research allowlist entries**

Modify both:

- `src/auth_drivers/claude_code_sdk_driver.py`
- `src/auth_drivers/chatgpt_oauth_driver.py`

Add `"get_current_quote"` to `_RESEARCH_READONLY_TOOLS` next to `"get_ticker_prices"`.

- [ ] **Step 7: Run focused tests**

Run:

```bash
pytest tests/test_tools.py::TestRegistry tests/test_agents.py::TestAnthropicToolSchemas tests/test_claude_code_sdk_driver.py::test_current_quote_is_research_readonly_allowlisted -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/tools/registry.py src/agents/openai_agent/tools.py src/agents/anthropic_agent/tools.py src/auth_drivers/claude_code_sdk_driver.py src/auth_drivers/chatgpt_oauth_driver.py tests/test_tools.py tests/test_agents.py tests/test_claude_code_sdk_driver.py
git commit -m "feat: expose current quote as agent tool"
```

---

## Task 4: HTTP API Route

**Files:**
- Modify: `src/api/routes/prices.py`
- Create: `tests/test_prices_quote_route.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/test_prices_quote_route.py`:

```python
from src.api.routes import prices as route
from src.tools.schemas import CurrentQuoteResult


def test_quote_route_returns_model_dump(monkeypatch):
    seen = {}

    def fake_quote(dal, ticker, source="auto"):
        seen.update({"dal": dal, "ticker": ticker, "source": source})
        return CurrentQuoteResult(
            ticker="NVDA",
            provider="ibkr",
            mode="ibkr_snapshot",
            price=123.45,
            source_note="fake",
        )

    monkeypatch.setattr(route, "get_current_quote", fake_quote)

    out = route.current_quote("nvda", source="ibkr", dal=object())

    assert seen["ticker"] == "nvda"
    assert seen["source"] == "ibkr"
    assert out["ticker"] == "NVDA"
    assert out["mode"] == "ibkr_snapshot"
    assert out["price"] == 123.45
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_prices_quote_route.py -q
```

Expected: FAIL because `current_quote` route does not exist.

- [ ] **Step 3: Add route**

Modify `src/api/routes/prices.py` imports:

```python
from src.tools.current_quote import get_current_quote
```

Add before `@router.get("/{ticker}")` so `/quote` does not conflict with sector route:

```python
@router.get("/{ticker}/quote")
def current_quote(
    ticker: str,
    source: str = Query("auto", pattern="^(auto|ibkr|local)$"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get a read-through current quote for a ticker."""
    result = get_current_quote(dal, ticker=ticker, source=source)
    return result.model_dump()
```

- [ ] **Step 4: Run test**

Run:

```bash
pytest tests/test_prices_quote_route.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/prices.py tests/test_prices_quote_route.py
git commit -m "feat: add current quote api route"
```

---

## Task 5: Prompt/Tool Guidance and Replay Safety

**Files:**
- Modify: `src/agents/shared/prompts.py`
- Test: focused registry/agent tests from Task 3

- [ ] **Step 1: Update ticker lookup guidance**

Modify `src/agents/shared/prompts.py` line containing:

```python
- Simple ticker lookups — use get_ticker_news, get_ticker_prices first
```

to:

```python
- Simple ticker lookups — use get_current_quote for current price, get_ticker_prices for bars/history, and get_ticker_news for news
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
pytest tests/test_tools.py::TestRegistry tests/test_agents.py::TestAnthropicToolSchemas -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/agents/shared/prompts.py
git commit -m "docs: guide agents to current quote tool"
```

---

## Task 6: Verification Gates

**Files:** no code changes unless a gate fails.

- [ ] **Step 1: Run backend focused suite**

Run:

```bash
pytest tests/test_current_quote_tools.py tests/test_prices_quote_route.py tests/test_tools.py::TestRegistry tests/test_agents.py::TestAnthropicToolSchemas tests/test_option_chain_tools.py::test_ibkr_client_id_quotes_domain tests/test_option_chain_tools.py::test_get_ibkr_uses_options_domain_client_id tests/test_claude_code_sdk_driver.py -q
```

Expected: PASS. If `tests/test_claude_code_sdk_driver.py` contains unrelated existing failures, stop and report exact failures before changing scope.

- [ ] **Step 2: Run PG-unreachable smoke**

Run:

```bash
python -m src.smoke.pg_unreachable_e2e
```

Expected: `ok: true`, `pg_attempts: []`. The new quote API should not create PG dependency.

- [ ] **Step 3: Run import/compile check**

Run:

```bash
python -m compileall -q src data_sources tests/test_current_quote_tools.py tests/test_prices_quote_route.py
```

Expected: exit 0.

- [ ] **Step 4: Run full A/B if reviewer requests**

Expected: failure set identical except tool-count tests intentionally updated; passed count should increase by the number of new tests.

- [ ] **Step 5: Commit any gate-only fixes**

Only commit fixes directly related to this slice. Stop if failures reveal Track A or unrelated changes.

---

## Stop-Loss Conditions

Stop and report if any of these occur:

1. Adding `quotes` client-id domain changes existing `options/prices/news/iv` values.
2. Any quote path writes to SQLite, job_runs, scheduler state, or provider telemetry.
3. `source="local"` imports or instantiates `IBKRDataSource`.
4. OAuth research bridge rejects the registry because `get_current_quote` is not allowlisted.
5. Tests require live IB Gateway. Unit tests must use fakes only.
6. Full A/B shows head-only failures outside named tool ledger changes.

---

## Review Gates

1. `get_current_quote` result distinguishes `ibkr_snapshot`, `local_last_bar`, and `unavailable`.
2. IBKR snapshot failure in `auto` falls back; strict `ibkr` does not.
3. Local fallback is marked stale and never described as live.
4. New `quotes` client-id domain is covered and does not perturb existing domains.
5. Tool registry, Anthropic tools, OpenAI tools, and OAuth read-only allowlists all include `get_current_quote`.
6. `/prices/{ticker}/quote` returns the same model shape as the tool.
7. PG-unreachable smoke remains clean.

