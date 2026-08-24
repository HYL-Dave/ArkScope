"""Local browser tool for reading a known URL with Playwright."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── Playwright Browse ─────────────────────────────────────────

def web_browse(
    url: str,
    wait_for: str = "networkidle",
    extract_links: bool = False,
    offset: int = 0,
    max_chars: int = 5000,
) -> Dict[str, Any]:
    """Browse a URL with headless Chromium (Playwright).

    Reads JavaScript-rendered pages and supports pagination via
    offset/max_chars. The caller must already know the URL to inspect.

    Args:
        url: URL to browse
        wait_for: Wait strategy - "networkidle", "load", "domcontentloaded"
        extract_links: Also extract page links
        offset: Start position in chars (for pagination)
        max_chars: Max chars to return per call (default 5000)

    Returns:
        Dict with url, title, content, offset, total_chars, was_truncated,
        remaining_chars, links (if extract_links), success
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "url": url,
            "content": "",
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until=wait_for, timeout=30000)

            title = page.title()
            full_text = page.inner_text("body")

            links: List[Dict[str, str]] = []
            if extract_links:
                link_elements = page.query_selector_all("a[href]")
                for el in link_elements[:50]:  # cap at 50 links
                    href = el.get_attribute("href") or ""
                    text = (el.inner_text() or "").strip()
                    if href and text and len(text) < 200:
                        links.append({"text": text, "href": href})

            browser.close()

        total_chars = len(full_text)
        chunk = full_text[offset: offset + max_chars]

        result: Dict[str, Any] = {
            "url": url,
            "title": title,
            "content": chunk,
            "offset": offset,
            "total_chars": total_chars,
            "was_truncated": total_chars > offset + max_chars,
            "remaining_chars": max(0, total_chars - offset - max_chars),
            "success": True,
        }
        if extract_links:
            result["links"] = links
        return result

    except Exception as e:
        logger.error(f"Playwright browse failed for {url}: {e}")
        return {
            "url": url,
            "content": "",
            "success": False,
            "error": str(e),
        }
