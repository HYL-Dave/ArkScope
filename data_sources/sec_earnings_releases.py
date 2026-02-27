"""
SEC EDGAR 8-K Parser for Earnings Press Releases.

Replaces Financial Datasets API endpoint 18 (/earnings/press-releases).

Usage:
    from data_sources.sec_earnings_releases import get_earnings_press_releases

    releases = get_earnings_press_releases('COST', limit=5)
    # Returns list of dicts matching FD API format
"""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DEFAULT_SEC_CONTACT = 'MindfulRL-Intraday research@example.com'


def _get_sec_user_agent() -> str:
    """Build SEC User-Agent from env var or default (with warning).

    Reads at call time (not import time) so config/.env can be loaded first.
    """
    contact = os.environ.get('SEC_CONTACT_EMAIL', '').strip()
    if contact:
        return f'MindfulRL-Intraday {contact}'
    legacy = os.environ.get('SEC_USER_AGENT', '').strip()
    if legacy:
        return legacy
    logger.warning(
        "SEC_CONTACT_EMAIL not set — using placeholder User-Agent. "
        "SEC may rate-limit or reject requests. Set SEC_CONTACT_EMAIL in config/.env"
    )
    return _DEFAULT_SEC_CONTACT


@dataclass
class EarningsPressRelease:
    """Single earnings press release record matching FD API format."""
    ticker: str
    title: str
    url: str
    date: str  # ISO format: YYYY-MM-DDTHH:MM:SSZ
    text: str

    def to_dict(self) -> dict:
        return {
            'ticker': self.ticker,
            'title': self.title,
            'url': self.url,
            'date': self.date,
            'text': self.text,
        }


class SECEarningsReleases:
    """Parse SEC 8-K filings to extract earnings press releases."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': _get_sec_user_agent(),
            'Accept': 'application/json, application/xml, text/html',
        })
        self._cik_cache: dict[str, str] = {}

    def _get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK for a ticker symbol."""
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        # Use SEC company_tickers.json
        url = 'https://www.sec.gov/files/company_tickers.json'
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        for entry in data.values():
            if entry['ticker'].upper() == ticker.upper():
                cik = str(entry['cik_str'])
                self._cik_cache[ticker] = cik
                return cik

        return None

    def _get_8k_filings(self, cik: str, limit: int = 20) -> list[dict]:
        """Get list of 8-K filings for a CIK."""
        url = f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json'
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        recent = data.get('filings', {}).get('recent', {})

        forms = recent.get('form', [])
        accessions = recent.get('accessionNumber', [])
        filing_dates = recent.get('filingDate', [])
        primary_docs = recent.get('primaryDocument', [])

        filings = []
        for i, form in enumerate(forms):
            if form == '8-K' and len(filings) < limit:
                filings.append({
                    'accession': accessions[i],
                    'filing_date': filing_dates[i],
                    'primary_doc': primary_docs[i] if i < len(primary_docs) else '',
                })

        return filings

    def _find_exhibit_url(self, cik: str, accession: str, exhibit_type: str = 'EX-99.1') -> Optional[str]:
        """Find the exhibit URL for an 8-K filing."""
        accession_clean = accession.replace('-', '')
        index_url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession}-index.html'

        resp = self._session.get(index_url, timeout=30)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find exhibit link in table rows
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 4:
                doc_type = cols[3].text.strip()
                if doc_type == exhibit_type:
                    link = cols[2].find('a')
                    if link:
                        href = link.get('href', '')
                        if href.startswith('/'):
                            return f'https://www.sec.gov{href}'
                        return href

        return None

    def _parse_exhibit_html(self, html_content: str, ticker: str, filing_date: str, url: str) -> Optional[EarningsPressRelease]:
        """Parse exhibit HTML to extract press release content."""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Get text content
        text = soup.get_text(separator='\n', strip=True)

        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove common header junk
        lines = text.split('\n')
        clean_lines = []
        skip_until_content = True

        for line in lines:
            line = line.strip()
            # Skip document metadata at start
            if skip_until_content:
                if any(keyword in line.upper() for keyword in ['PRESS RELEASE', 'REPORTS', 'ANNOUNCES', 'RESULTS']):
                    skip_until_content = False
                    clean_lines.append(line)
            else:
                clean_lines.append(line)

        if not clean_lines:
            clean_lines = lines  # Fallback to all lines

        text = '\n'.join(clean_lines)

        # Extract title - usually the first line that looks like a title
        title = ''
        for line in clean_lines[:10]:
            if len(line) > 20 and len(line) < 200:
                if any(keyword in line.upper() for keyword in ['REPORTS', 'ANNOUNCES', 'RESULTS', 'QUARTER', 'FISCAL']):
                    title = line
                    break

        if not title and clean_lines:
            title = clean_lines[0][:150]

        # Convert filing_date to ISO format with time (assume end of day)
        try:
            dt = datetime.strptime(filing_date, '%Y-%m-%d')
            date_iso = dt.strftime('%Y-%m-%dT21:15:00Z')  # Typical after-hours time
        except ValueError:
            date_iso = f'{filing_date}T21:15:00Z'

        return EarningsPressRelease(
            ticker=ticker,
            title=title,
            url=url,
            date=date_iso,
            text=text.strip(),
        )

    def _is_earnings_release(self, text: str) -> bool:
        """Check if the press release is about earnings/financial results."""
        keywords = [
            'operating results',
            'quarterly results',
            'financial results',
            'fiscal year',
            'fiscal quarter',
            'net income',
            'net sales',
            'earnings',
            'revenue',
            'eps',
            'per diluted share',
        ]
        text_lower = text.lower()
        return sum(1 for kw in keywords if kw in text_lower) >= 3

    def get_earnings_press_releases(self, ticker: str, limit: int = 5) -> list[dict]:
        """
        Get earnings press releases for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'COST')
            limit: Maximum number of releases to return

        Returns:
            List of release dicts matching Financial Datasets API format
        """
        cik = self._get_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return []

        # Get more filings than needed since not all 8-Ks are earnings
        filings = self._get_8k_filings(cik, limit=limit * 4)

        releases = []
        for filing in filings:
            if len(releases) >= limit:
                break

            # Look for EX-99.1 first, then EX-99.2
            exhibit_url = self._find_exhibit_url(cik, filing['accession'], 'EX-99.1')
            if not exhibit_url:
                exhibit_url = self._find_exhibit_url(cik, filing['accession'], 'EX-99.2')

            if not exhibit_url:
                continue

            try:
                resp = self._session.get(exhibit_url, timeout=30)
                if resp.status_code != 200:
                    continue

                release = self._parse_exhibit_html(
                    resp.text, ticker, filing['filing_date'], exhibit_url
                )

                if release and self._is_earnings_release(release.text):
                    releases.append(release)

            except Exception as e:
                logger.warning(f"Error fetching {exhibit_url}: {e}")
                continue

        return [r.to_dict() for r in releases]


# Convenience function
def get_earnings_press_releases(ticker: str, limit: int = 5) -> list[dict]:
    """
    Get earnings press releases for a ticker from SEC 8-K filings.

    This is a FREE replacement for Financial Datasets API endpoint 18 (/earnings/press-releases).

    Args:
        ticker: Stock symbol (e.g., 'COST')
        limit: Maximum number of releases to return

    Returns:
        List of release dicts with keys:
        - ticker: Stock symbol
        - title: Press release title
        - url: SEC EDGAR URL
        - date: ISO format datetime
        - text: Full press release text

    Example:
        >>> releases = get_earnings_press_releases('COST', limit=3)
        >>> releases[0]
        {'ticker': 'COST', 'title': 'Costco Reports First Quarter...', ...}
    """
    return _get_singleton().get_earnings_press_releases(ticker, limit)


# Module-level singleton — keeps CIK cache + requests.Session across calls
_singleton: Optional[SECEarningsReleases] = None


def _get_singleton() -> SECEarningsReleases:
    global _singleton
    if _singleton is None:
        _singleton = SECEarningsReleases()
    return _singleton


if __name__ == '__main__':
    # Test
    import json
    releases = get_earnings_press_releases('COST', limit=3)
    print(f"Found {len(releases)} earnings releases")
    for r in releases:
        print(f"\n=== {r['date'][:10]} ===")
        print(f"Title: {r['title']}")
        print(f"URL: {r['url']}")
        print(f"Text: {r['text'][:500]}...")