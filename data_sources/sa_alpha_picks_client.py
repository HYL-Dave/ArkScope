"""
Seeking Alpha Alpha Picks scraper client.

Uses Playwright with a saved session (from scripts/sa_login.py) to scrape
the Alpha Picks portfolio page. Data is persisted via DAL public methods
(DB or file backend).

Usage:
    client = SAAlphaPicksClient(session_file="~/.config/.../storage_state.json", dal=dal)
    portfolio = client.get_portfolio()         # cached, auto-refresh if stale
    detail = client.get_pick_detail("NVDA")    # cached detail report
    result = client.refresh_portfolio(sync_tickers=True)  # force refresh
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# CSS selectors for SA Alpha Picks page — update if DOM structure changes
_PORTFOLIO_URL = "https://seekingalpha.com/alpha-picks/portfolio"
_TABLE_ROW_SELECTOR = "[data-testid='portfolio-table'] tbody tr"
_CLOSED_TAB_SELECTOR = "button:has-text('Closed')"
_CURRENT_TAB_SELECTOR = "button:has-text('Current')"
_PAYWALL_MARKERS = ["Subscribe to unlock", "Upgrade your plan", "Premium required"]
_LOGIN_INDICATORS = ["/login", "/sign_in", "/account/login"]


class SASessionError(Exception):
    """Raised when SA session is invalid or expired."""
    pass


class SAScrapingError(Exception):
    """Raised when scraping fails (DOM changed, paywall, etc.)."""
    pass


class SAAlphaPicksClient:
    """Scraper for Seeking Alpha Alpha Picks portfolio."""

    def __init__(
        self,
        session_file: str,
        dal=None,
        cache_hours: int = 24,
        detail_cache_days: int = 7,
    ):
        self._session_file = os.path.expanduser(session_file)
        self._dal = dal
        self._cache_hours = cache_hours
        self._detail_cache_days = detail_cache_days

    def get_portfolio(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Alpha Picks portfolio with cache TTL check.

        Per-tab TTL: checks current/closed independently.
        Only refreshes expired scopes, not all scopes.
        """
        if self._dal is None:
            return {"error": "DAL not configured"}

        if not force_refresh:
            meta = self._dal.get_sa_refresh_meta()
            now = datetime.now(tz=timezone.utc)

            scopes_to_refresh = []
            for scope in ("current", "closed"):
                scope_meta = meta.get(scope, {})
                last_success = scope_meta.get("last_success_at")
                if last_success and scope_meta.get("ok"):
                    if isinstance(last_success, str):
                        last_success = datetime.fromisoformat(last_success)
                    age_hours = (now - last_success).total_seconds() / 3600
                    if age_hours < self._cache_hours:
                        continue  # Cache still fresh
                scopes_to_refresh.append(scope)

            if not scopes_to_refresh:
                # All scopes fresh — return from cache
                current = self._dal.get_sa_portfolio(portfolio_status="current")
                closed = self._dal.get_sa_portfolio(portfolio_status="closed")
                freshness = meta
                is_partial = not (
                    freshness.get("current", {}).get("ok", False)
                    and freshness.get("closed", {}).get("ok", False)
                )
                return {
                    "current": current,
                    "closed": closed,
                    "freshness": freshness,
                    "is_partial": is_partial,
                }

            # Refresh only stale scopes (sync_tickers=False for auto-refresh)
            return self._refresh_scopes(scopes_to_refresh, sync_tickers=False)

        return self._refresh_scopes(["current", "closed"], sync_tickers=False)

    def get_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detail report for a specific pick.

        picked_date=None: uses deterministic fallback (current + non-stale first).
        """
        if self._dal is None:
            return {"error": "DAL not configured"}

        # Check cache
        cached = self._dal.get_sa_pick_detail(symbol, picked_date)
        if cached and cached.get("detail_report"):
            # Check detail freshness
            fetched_at = cached.get("detail_fetched_at")
            if fetched_at:
                if isinstance(fetched_at, str):
                    fetched_at = datetime.fromisoformat(fetched_at)
                age_days = (datetime.now(tz=timezone.utc) - fetched_at).days
                if age_days < self._detail_cache_days:
                    return cached

        # TODO: Scrape detail page when needed (requires page navigation)
        # For now, return whatever we have from cache
        if cached:
            return cached
        return {"error": None, "detail": None, "symbol": symbol}

    def refresh_portfolio(self, sync_tickers: bool = False) -> Dict[str, Any]:
        """Force refresh both tabs from SA website.

        Args:
            sync_tickers: If True, sync current picks to tickers_core.json.
                Only tool/CLI explicit refresh should pass True.
        """
        return self._refresh_scopes(
            ["current", "closed"], sync_tickers=sync_tickers
        )

    def _refresh_scopes(
        self, scopes: List[str], sync_tickers: bool = False
    ) -> Dict[str, Any]:
        """Refresh specified scopes (current/closed) from SA website."""
        if not self._check_session_file():
            return {
                "error": "Session file not found. Run: python scripts/sa_login.py",
                "session_file": self._session_file,
            }

        refresh_batch_ts = datetime.now(tz=timezone.utc)
        results = {}
        all_current_picks = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"error": "playwright not installed. Run: pip install playwright"}

        try:
            with sync_playwright() as p:
                context = self._create_context(p)
                page = context.new_page()

                # Navigate to portfolio page
                page.goto(_PORTFOLIO_URL, wait_until="networkidle")
                time.sleep(1)  # Small delay for dynamic content

                # Check session validity
                session_error = self._check_session_page(page)
                if session_error:
                    for scope in scopes:
                        self._dal.record_sa_refresh_failure(
                            scope=scope,
                            attempt_ts=refresh_batch_ts,
                            error=session_error,
                        )
                    return {"error": session_error}

                for scope in scopes:
                    try:
                        picks = self._scrape_tab(page, portfolio_status=scope)
                        snapshot_ts = datetime.now(tz=timezone.utc)

                        count = self._dal.apply_sa_refresh(
                            scope=scope,
                            picks=picks,
                            attempt_ts=refresh_batch_ts,
                            snapshot_ts=snapshot_ts,
                        )

                        results[scope] = {
                            "ok": True,
                            "count": count,
                            "error": None,
                        }

                        if scope == "current":
                            all_current_picks = picks

                    except Exception as e:
                        logger.error("Failed to scrape %s tab: %s", scope, e)
                        self._dal.record_sa_refresh_failure(
                            scope=scope,
                            attempt_ts=refresh_batch_ts,
                            error=str(e),
                        )
                        results[scope] = {
                            "ok": False,
                            "count": 0,
                            "error": str(e),
                        }

                context.close()

        except Exception as e:
            logger.error("Playwright error: %s", e)
            for scope in scopes:
                if scope not in results:
                    self._dal.record_sa_refresh_failure(
                        scope=scope,
                        attempt_ts=refresh_batch_ts,
                        error=str(e),
                    )
                    results[scope] = {"ok": False, "count": 0, "error": str(e)}

        # Sync tickers if requested and we have current picks
        if sync_tickers and all_current_picks:
            try:
                self._sync_tickers_to_collection(all_current_picks)
            except Exception as e:
                logger.warning("Ticker sync failed: %s", e)

        # Build response
        meta = self._dal.get_sa_refresh_meta()
        is_partial = not (
            meta.get("current", {}).get("ok", False)
            and meta.get("closed", {}).get("ok", False)
        )

        return {
            "results": results,
            "freshness": meta,
            "is_partial": is_partial,
        }

    def _check_session_file(self) -> bool:
        """Check if session file exists."""
        return os.path.isfile(self._session_file)

    def _check_session_page(self, page) -> Optional[str]:
        """Check if the loaded page indicates a valid session.

        Returns error string if invalid, None if OK.
        """
        url = page.url
        for indicator in _LOGIN_INDICATORS:
            if indicator in url:
                return f"Session expired: redirected to login ({url})"

        content = page.content()
        for marker in _PAYWALL_MARKERS:
            if marker in content:
                return f"Paywall detected: {marker}"

        return None

    def _create_context(self, playwright):
        """Create a Playwright browser context with saved session."""
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=self._session_file,
            viewport={"width": 1280, "height": 800},
        )
        return context

    def _scrape_tab(self, page, portfolio_status: str = "current") -> List[Dict]:
        """Scrape one tab (current or closed) from the portfolio page.

        Returns list of dicts with portfolio data.
        """
        # Switch to the right tab if needed
        if portfolio_status == "closed":
            closed_btn = page.query_selector(_CLOSED_TAB_SELECTOR)
            if closed_btn:
                closed_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)
        elif portfolio_status == "current":
            current_btn = page.query_selector(_CURRENT_TAB_SELECTOR)
            if current_btn:
                current_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)

        rows = page.query_selector_all(_TABLE_ROW_SELECTOR)
        picks = []

        for row in rows:
            try:
                cells = row.query_selector_all("td")
                if len(cells) < 6:
                    continue

                pick = self._parse_row(cells, portfolio_status)
                if pick and pick.get("symbol"):
                    picks.append(pick)
            except Exception as e:
                logger.warning("Failed to parse row: %s", e)
                continue

        if not picks:
            # Check if this is a real empty table or a scraping issue
            page_text = page.inner_text("body")
            for marker in _PAYWALL_MARKERS:
                if marker in page_text:
                    raise SAScrapingError(f"Paywall marker detected: {marker}")

        logger.info("Scraped %d picks from %s tab", len(picks), portfolio_status)
        return picks

    def _parse_row(self, cells, portfolio_status: str) -> Optional[Dict]:
        """Parse a single table row into a pick dict.

        Expected columns: Company, Symbol, Picked, Return, Sector, Rating, Holding %
        Actual order may vary — we try to be flexible.
        """
        try:
            # Extract text from cells, stripping whitespace
            texts = [c.inner_text().strip() for c in cells]

            # Heuristic parsing based on typical SA Alpha Picks layout
            # The exact column order may need adjustment after seeing real DOM
            pick = {
                "company": texts[0] if len(texts) > 0 else "",
                "symbol": self._extract_symbol(texts),
                "picked_date": self._extract_date(texts),
                "return_pct": self._extract_pct(texts),
                "sector": self._extract_sector(texts),
                "sa_rating": self._extract_rating(texts),
                "holding_pct": self._extract_holding_pct(texts),
                "portfolio_status": portfolio_status,
                "is_stale": False,
                "raw_data": {"cells": texts},
            }
            return pick
        except Exception as e:
            logger.debug("Row parse error: %s", e)
            return None

    def _extract_symbol(self, texts: List[str]) -> str:
        """Extract ticker symbol from cell texts."""
        # Symbol is typically short, all uppercase, 1-5 chars
        for t in texts:
            cleaned = t.strip().upper()
            if 1 <= len(cleaned) <= 5 and cleaned.isalpha():
                return cleaned
        return ""

    def _extract_date(self, texts: List[str]) -> Optional[str]:
        """Extract picked date from cell texts."""
        import re
        for t in texts:
            # Match patterns like "Jan 15, 2025" or "2025-01-15" or "01/15/2025"
            # ISO format
            if re.match(r"\d{4}-\d{2}-\d{2}", t):
                return t[:10]
            # Month DD, YYYY
            m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})", t)
            if m:
                from datetime import datetime as dt
                try:
                    d = dt.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")
                    return d.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        return None

    def _extract_pct(self, texts: List[str]) -> Optional[float]:
        """Extract return percentage from cell texts."""
        import re
        for t in texts:
            m = re.search(r"([+-]?\d+\.?\d*)%", t)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    def _extract_sector(self, texts: List[str]) -> Optional[str]:
        """Extract sector from cell texts."""
        sectors = {
            "Technology", "Healthcare", "Financial", "Consumer", "Energy",
            "Industrial", "Communication", "Materials", "Utilities", "Real Estate",
        }
        for t in texts:
            for s in sectors:
                if s.lower() in t.lower():
                    return t.strip()
        return None

    def _extract_rating(self, texts: List[str]) -> Optional[str]:
        """Extract SA rating from cell texts."""
        ratings = {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}
        for t in texts:
            upper = t.strip().upper()
            if upper in ratings:
                return upper
        return None

    def _extract_holding_pct(self, texts: List[str]) -> Optional[float]:
        """Extract holding percentage from cell texts."""
        import re
        # Holding % is typically the last percentage column
        pcts = []
        for t in texts:
            m = re.search(r"(\d+\.?\d*)%", t)
            if m:
                pcts.append(float(m.group(1)))
        # Return the last percentage if there are multiple (return % comes first)
        return pcts[-1] if len(pcts) >= 2 else None

    def _scrape_detail(self, page, detail_url: str) -> Optional[str]:
        """Scrape the detail report for a specific pick."""
        try:
            page.goto(detail_url, wait_until="networkidle")
            time.sleep(1)

            # Check for paywall
            session_error = self._check_session_page(page)
            if session_error:
                return None

            # Extract article content
            article = page.query_selector("article") or page.query_selector("[data-testid='article-body']")
            if article:
                return article.inner_text()

            return None
        except Exception as e:
            logger.error("Failed to scrape detail: %s", e)
            return None

    def _sync_tickers_to_collection(self, picks: List[Dict]) -> None:
        """Sync current + non-stale picks symbols to tickers_core.json tier3."""
        symbols = sorted({
            p["symbol"]
            for p in picks
            if p.get("portfolio_status") == "current"
            and not p.get("is_stale", False)
            and p.get("symbol")
        })

        if not symbols:
            return

        tickers_path = Path("config/tickers_core.json")
        if not tickers_path.exists():
            logger.warning("tickers_core.json not found, skipping ticker sync")
            return

        try:
            with open(tickers_path) as f:
                tickers_config = json.load(f)

            # Ensure tier3_user_watchlist exists
            if "tier3_user_watchlist" not in tickers_config:
                tickers_config["tier3_user_watchlist"] = {}

            tier3 = tickers_config["tier3_user_watchlist"]

            # Get existing auto-sync symbols
            existing = set(
                tier3.get("sa_alpha_picks_auto", {}).get("tickers", [])
            )

            # Append-only: merge new symbols with existing
            merged = sorted(existing | set(symbols))

            tier3["sa_alpha_picks_auto"] = {
                "tickers": merged,
                "description": "Auto-synced from SA Alpha Picks (current, non-stale)",
            }

            # Atomic write: temp file + rename
            tmp_path = tickers_path.with_suffix(".json.tmp")
            with open(tmp_path, "w") as f:
                json.dump(tickers_config, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, tickers_path)

            logger.info(
                "Synced %d SA Alpha Picks symbols to tickers_core.json", len(merged)
            )
        except Exception as e:
            logger.error("Failed to sync tickers: %s", e)
            raise
