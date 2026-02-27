"""
SEC EDGAR Data Source Implementation.

SEC EDGAR provides:
- Company filings (10-K, 10-Q, 8-K, etc.)
- Company facts (structured financial data)
- Full-text search
- Submissions history

Free & Official - No API key required, but requires User-Agent header.

Rate Limits:
- 10 requests per second (be respectful)

Documentation: https://www.sec.gov/edgar/sec-api-documentation
"""

import os
import time
import logging
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
import requests

from .base import (
    BaseDataSource,
    DataSourceType,
    NewsArticle,
    StockPrice,
    SECFiling,
)

logger = logging.getLogger(__name__)


# CIK to Ticker mapping for common stocks (can be extended)
# SEC uses CIK (Central Index Key) instead of ticker symbols
TICKER_TO_CIK = {
    'AAPL': '0000320193',
    'MSFT': '0000789019',
    'GOOGL': '0001652044',
    'AMZN': '0001018724',
    'META': '0001326801',
    'NVDA': '0001045810',
    'TSLA': '0001318605',
    'JPM': '0000019617',
    'V': '0001403161',
    'JNJ': '0000200406',
    'WMT': '0000104169',
    'PG': '0000080424',
    'MA': '0001141391',
    'UNH': '0000731766',
    'HD': '0000354950',
    'BAC': '0000070858',
    'DIS': '0001744489',
    'ADBE': '0000796343',
    'CRM': '0001108524',
    'NFLX': '0001065280',
    'INTC': '0000050863',
    'AMD': '0000002488',
    'PYPL': '0001633917',
    'CSCO': '0000858877',
    'PEP': '0000077476',
    'KO': '0000021344',
    'COST': '0000909832',
    'TMO': '0000097745',
    'AVGO': '0001730168',
    'ACN': '0001467373',
}


class SECEdgarDataSource(BaseDataSource):
    """
    SEC EDGAR data source implementation.

    Usage:
        sec = SECEdgarDataSource()

        # Fetch recent filings
        filings = sec.fetch_sec_filings(['AAPL', 'MSFT'], filing_types=['10-K', '10-Q'])

        # Fetch company facts (structured financial data)
        facts = sec.fetch_company_facts('AAPL')

        # Search filings
        results = sec.search_filings('artificial intelligence', filing_types=['10-K'])
    """

    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts"
    FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

    # Rate limiting: 10 requests per second max
    REQUEST_DELAY = 0.15  # 150ms between requests to be safe

    def __init__(self, user_agent: Optional[str] = None):
        """
        Initialize SEC EDGAR data source.

        Args:
            user_agent: User-Agent string (required by SEC).
                       Format: "Company Name contact@email.com"
                       If None, reads from SEC_USER_AGENT env var.
        """
        super().__init__(api_key=None)  # No API key needed

        if user_agent:
            self.user_agent = user_agent
        else:
            # Prefer SEC_CONTACT_EMAIL (new), fallback to SEC_USER_AGENT (legacy)
            contact = os.environ.get('SEC_CONTACT_EMAIL', '').strip()
            if contact:
                self.user_agent = f'MindfulRL-Intraday {contact}'
            else:
                self.user_agent = os.environ.get(
                    'SEC_USER_AGENT',
                    'MindfulRL-Intraday research@example.com',
                )

        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json',
        })
        self._last_request_time = 0

        # Cache for CIK lookups
        self._cik_cache: Dict[str, str] = TICKER_TO_CIK.copy()

    @property
    def source_name(self) -> str:
        return "SEC EDGAR"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.SEC_EDGAR

    @property
    def supports_news(self) -> bool:
        return False  # SEC doesn't provide news, but filings can be treated as news

    @property
    def supports_prices(self) -> bool:
        return False

    @property
    def supports_sec_filings(self) -> bool:
        return True

    def _rate_limit_wait(self):
        """Wait to respect rate limits (10 req/sec)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Make an API request with rate limiting.

        Args:
            url: Full URL to request.
            params: Query parameters.

        Returns:
            JSON response or None on error.
        """
        self._rate_limit_wait()

        try:
            response = self._session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {url}")
                return None
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting 10 seconds...")
                time.sleep(10)
                return self._make_request(url, params)
            else:
                logger.error(f"SEC API error {response.status_code}: {response.text[:200]}")
                return None

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def validate_credentials(self) -> bool:
        """
        Validate connection to SEC EDGAR.

        Returns:
            True if connection works.
        """
        # Test with a simple request
        result = self._make_request(f"{self.SUBMISSIONS_URL}/CIK0000320193.json")
        return result is not None

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Get CIK (Central Index Key) for a ticker symbol.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')

        Returns:
            CIK string (e.g., '0000320193') or None if not found.
        """
        ticker = ticker.upper()

        # Check cache first
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        # Try to look up from SEC's ticker mapping
        try:
            response = self._session.get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                params={
                    'action': 'getcompany',
                    'CIK': ticker,
                    'type': '',
                    'dateb': '',
                    'owner': 'include',
                    'count': '1',
                    'output': 'atom',
                },
                timeout=10,
            )

            if response.status_code == 200:
                # Parse CIK from response
                match = re.search(r'CIK=(\d+)', response.text)
                if match:
                    cik = match.group(1).zfill(10)
                    self._cik_cache[ticker] = cik
                    return cik

        except Exception as e:
            logger.warning(f"Failed to lookup CIK for {ticker}: {e}")

        return None

    def fetch_news(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_back: int = 7,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """
        SEC doesn't provide news. Use fetch_sec_filings instead.
        This returns recent 8-K filings as "news-like" items.
        """
        filings = self.fetch_sec_filings(
            tickers=tickers,
            filing_types=['8-K'],  # 8-K are current reports (most news-like)
            start_date=start_date,
            end_date=end_date,
        )

        # Convert filings to NewsArticle format
        articles = []
        for filing in filings:
            articles.append(NewsArticle(
                ticker=filing.ticker,
                title=f"[{filing.filing_type}] {filing.title}",
                published_date=datetime.combine(filing.filing_date, datetime.min.time()),
                source='SEC EDGAR',
                description=filing.description,
                content=filing.content,
                url=filing.url,
                data_source='sec_edgar',
            ))

        if limit:
            articles = articles[:limit]

        return articles

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = 'daily',
    ) -> List[StockPrice]:
        """SEC doesn't provide price data."""
        raise NotImplementedError("SEC EDGAR does not provide stock price data")

    def fetch_sec_filings(
        self,
        tickers: List[str],
        filing_types: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SECFiling]:
        """
        Fetch SEC filings for given tickers.

        Args:
            tickers: List of stock symbols.
            filing_types: Types of filings to fetch (e.g., ['10-K', '10-Q', '8-K']).
                         If None, fetches all types.
            start_date: Start date filter.
            end_date: End date filter.

        Returns:
            List of SECFiling objects.
        """
        if filing_types is None:
            filing_types = ['10-K', '10-Q', '8-K']

        if end_date is None:
            end_date = date.today()

        if start_date is None:
            start_date = end_date - timedelta(days=365)

        all_filings = []

        for ticker in tickers:
            cik = self.get_cik(ticker)
            if not cik:
                logger.warning(f"Could not find CIK for {ticker}")
                continue

            logger.info(f"Fetching SEC filings for {ticker} (CIK: {cik})")

            # Get company submissions
            submissions = self._make_request(f"{self.SUBMISSIONS_URL}/CIK{cik}.json")

            if not submissions:
                continue

            # Parse recent filings
            recent = submissions.get('filings', {}).get('recent', {})
            if not recent:
                continue

            forms = recent.get('form', [])
            filing_dates = recent.get('filingDate', [])
            accession_numbers = recent.get('accessionNumber', [])
            primary_documents = recent.get('primaryDocument', [])
            descriptions = recent.get('primaryDocDescription', [])

            for i in range(len(forms)):
                form_type = forms[i]

                # Filter by filing type
                if form_type not in filing_types:
                    continue

                # Parse filing date
                try:
                    filing_date = datetime.strptime(filing_dates[i], '%Y-%m-%d').date()
                except:
                    continue

                # Filter by date range
                if filing_date < start_date or filing_date > end_date:
                    continue

                # Build URL
                accession = accession_numbers[i].replace('-', '')
                primary_doc = primary_documents[i] if i < len(primary_documents) else ''
                url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{primary_doc}"

                filing = SECFiling(
                    ticker=ticker,
                    filing_type=form_type,
                    filing_date=filing_date,
                    accession_number=accession_numbers[i],
                    url=url,
                    title=f"{ticker} {form_type} Filing",
                    description=descriptions[i] if i < len(descriptions) else '',
                    data_source='sec_edgar',
                )

                all_filings.append(filing)

        # Sort by date descending
        all_filings.sort(key=lambda x: x.filing_date, reverse=True)

        logger.info(f"Fetched {len(all_filings)} SEC filings total")
        return all_filings

    def fetch_company_facts(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch structured financial facts for a company.

        This returns XBRL-structured financial data including:
        - Revenue, net income, assets, liabilities
        - EPS, shares outstanding
        - And many more financial metrics

        Args:
            ticker: Stock symbol.

        Returns:
            Dictionary with company facts or None.
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return None

        url = f"{self.COMPANY_FACTS_URL}/CIK{cik}.json"
        return self._make_request(url)

    def fetch_company_concept(
        self,
        ticker: str,
        taxonomy: str = 'us-gaap',
        concept: str = 'Revenue',
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific financial concept for a company.

        Common concepts:
        - Revenue, Revenues
        - NetIncomeLoss
        - Assets, Liabilities
        - EarningsPerShareBasic, EarningsPerShareDiluted
        - StockholdersEquity
        - OperatingIncomeLoss

        Args:
            ticker: Stock symbol.
            taxonomy: XBRL taxonomy ('us-gaap', 'dei', 'srt').
            concept: Concept name.

        Returns:
            Dictionary with concept data or None.
        """
        cik = self.get_cik(ticker)
        if not cik:
            return None

        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json"
        return self._make_request(url)

    def get_filing_document(self, filing: SECFiling, max_length: int = 50000) -> Optional[str]:
        """
        Fetch the actual document content of a filing.

        Args:
            filing: SECFiling object.
            max_length: Maximum characters to return.

        Returns:
            Document text content or None.
        """
        try:
            self._rate_limit_wait()
            response = self._session.get(filing.url, timeout=30)

            if response.status_code == 200:
                content = response.text
                if len(content) > max_length:
                    content = content[:max_length] + "\n... [truncated]"
                return content

        except Exception as e:
            logger.warning(f"Failed to fetch filing document: {e}")

        return None

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, '_session'):
            self._session.close()