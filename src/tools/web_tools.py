"""
Web search and browsing tools (Phase 10).

Provides four tools:
- web_search(): Tavily keyword search with AI summary
- web_fetch(): Tavily URL content extraction with pagination
- web_browse(): Playwright headless browser for JS-rendered pages
- codex_web_research(): Codex CLI deep research with live web browsing
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tavily client (lazy-init) ─────────────────────────────────

_tavily_client = None


def _get_tavily_client():
    """Lazy-init Tavily client from TAVILY_API_KEY env var."""
    global _tavily_client
    if _tavily_client is None:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise ValueError(
                "TAVILY_API_KEY not set in environment. "
                "Get a free key at https://tavily.com"
            )
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


def _days_to_time_range(days: int) -> str:
    """Convert days to Tavily time_range parameter."""
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 30:
        return "month"
    return "year"


# ── Tavily Search ─────────────────────────────────────────────

def web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 0,
) -> Dict[str, Any]:
    """Search the web for information using Tavily.

    Args:
        query: Search query string
        max_results: Number of results to return (1-10, default 5)
        search_depth: "basic" (1 credit) or "advanced" (2 credits)
        topic: "general", "news", or "finance"
        days: If > 0, limit to results from last N days

    Returns:
        Dict with query, answer (AI summary), result_count, results list
    """
    try:
        client = _get_tavily_client()
    except ValueError as e:
        return {"error": str(e), "query": query, "results": []}

    max_results = min(max(max_results, 1), 10)

    kwargs: Dict[str, Any] = {
        "query": query,
        "search_depth": search_depth,
        "topic": topic,
        "max_results": max_results,
        "include_answer": "basic",
    }
    if days > 0:
        kwargs["time_range"] = _days_to_time_range(days)

    try:
        response = client.search(**kwargs)
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return {"error": str(e), "query": query, "results": []}

    results = []
    for r in response.get("results", []):
        content = r.get("content", "")
        if len(content) > 500:
            content = content[:500] + "..."
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": content,
            "score": r.get("score", 0),
        })

    return {
        "query": query,
        "answer": response.get("answer", ""),
        "result_count": len(results),
        "results": results,
    }


# ── Tavily Fetch (URL extraction) ────────────────────────────

def web_fetch(
    url: str,
    extract_depth: str = "basic",
    offset: int = 0,
    max_chars: int = 3000,
) -> Dict[str, Any]:
    """Fetch and extract content from a URL using Tavily.

    Supports pagination via offset/max_chars for long content.

    Args:
        url: The URL to fetch content from
        extract_depth: "basic" or "advanced"
        offset: Start position in chars (for pagination)
        max_chars: Max chars to return per call (default 3000)

    Returns:
        Dict with url, content, offset, total_chars, was_truncated,
        remaining_chars, success
    """
    try:
        client = _get_tavily_client()
    except ValueError as e:
        return {"url": url, "content": "", "success": False, "error": str(e)}

    try:
        response = client.extract(
            urls=[url],
            extract_depth=extract_depth,
        )
    except Exception as e:
        logger.error(f"Tavily extract failed for {url}: {e}")
        return {"url": url, "content": "", "success": False, "error": str(e)}

    results = response.get("results", [])
    if results:
        full_content = results[0].get("raw_content", "")
        total_chars = len(full_content)
        chunk = full_content[offset: offset + max_chars]
        return {
            "url": url,
            "content": chunk,
            "offset": offset,
            "total_chars": total_chars,
            "was_truncated": total_chars > offset + max_chars,
            "remaining_chars": max(0, total_chars - offset - max_chars),
            "success": True,
        }

    failed = response.get("failed_results", [])
    error = failed[0].get("error", "Unknown error") if failed else "No content extracted"
    return {"url": url, "content": "", "success": False, "error": error}


# ── Playwright Browse ─────────────────────────────────────────

def web_browse(
    url: str,
    wait_for: str = "networkidle",
    extract_links: bool = False,
    offset: int = 0,
    max_chars: int = 5000,
) -> Dict[str, Any]:
    """Browse a URL with headless Chromium (Playwright).

    Handles JavaScript-rendered pages that Tavily extract cannot process.
    Supports pagination via offset/max_chars.

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


# ── Codex CLI deep research ────────────────────────────────

_CODEX_RESEARCH_PROMPT = """\
You are a financial research analyst. Use web search to deeply investigate:

{query}

{context}

Instructions:
- Search multiple sources to cross-reference information
- Focus on authoritative sources: SEC.gov, Reuters, Bloomberg, WSJ, earnings reports
- Synthesize findings into a structured report
- Include specific data points, dates, and numbers
- Note any conflicting information between sources
- List all sources consulted

Output format:
## Key Findings
- [bullet points with specific data]

## Detailed Analysis
[comprehensive analysis]

## Sources
- [list of URLs and source names]

## Confidence & Gaps
- Confidence: High/Medium/Low
- Data gaps: [what couldn't be found]
"""


def codex_web_research(
    query: str,
    context: str = "",
    timeout: int = 300,
) -> Dict[str, Any]:
    """Deep web research using Codex CLI with live web browsing.

    Runs Codex CLI as an autonomous research agent with --search enabled.
    Uses workspace-write sandbox with network access for web browsing,
    isolated in a temp directory (no access to project files).

    Args:
        query: Research question or topic to investigate.
        context: Optional context from earlier tool calls to inform research.
        timeout: Max seconds for research (default 300, increase for complex topics).

    Returns:
        dict with: success, report, query, error (if failed)
    """
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("codex"):
        return {
            "success": False,
            "query": query,
            "report": "",
            "error": "Codex CLI not installed. Install: npm install -g @openai/codex",
        }

    # Build research prompt
    context_section = f"Additional context:\n{context}" if context else ""
    prompt = _CODEX_RESEARCH_PROMPT.format(query=query, context=context_section)

    # Run in isolated temp directory
    with tempfile.TemporaryDirectory(prefix="codex_research_") as tmpdir:
        output_file = os.path.join(tmpdir, "report.md")

        cmd = [
            "codex", "exec",
            "--full-auto",
            "--sandbox", "workspace-write",
            "--search",
            "-c", "sandbox_workspace_write.network_access=true",
            "--model", "gpt-5.2",
            "--skip-git-repo-check",
            "--ephemeral",
            "-o", output_file,
            prompt,
        ]

        # Use OAuth login (codex login) — subscription quota, not API billing.
        # Strip API keys so Codex CLI falls back to OAuth session token.
        env = os.environ.copy()
        env.pop("CODEX_API_KEY", None)
        env.pop("OPENAI_API_KEY", None)

        logger.info(f"Codex web research: query={query[:80]}... timeout={timeout}s")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "query": query,
                "report": "",
                "error": f"Research timed out after {timeout}s. Try increasing timeout or narrowing the query.",
            }

        # Collect output from stdout and/or output file
        report = result.stdout.strip()

        # Also check if -o file was written
        if os.path.exists(output_file):
            try:
                with open(output_file) as f:
                    file_report = f.read().strip()
                if file_report and len(file_report) > len(report):
                    report = file_report
            except Exception:
                pass

        if result.returncode != 0 and not report:
            return {
                "success": False,
                "query": query,
                "report": "",
                "error": f"Codex CLI error (rc={result.returncode}): {result.stderr[:500]}",
            }

        return {
            "success": True,
            "query": query,
            "report": report,
        }