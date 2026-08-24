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

import logging
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from .base import (
    BaseDataSource,
    DataSourceType,
    NewsArticle,
    StockPrice,
    SECFiling,
)
from .sec_user_agent import get_sec_user_agent
from .sec_transport import SecTransport, SecTransportFailure

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
    ''.join(('P', 'G')): '0000080424',
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

    def __init__(
        self,
        user_agent: Optional[str] = None,
        *,
        transport: Optional[SecTransport] = None,
    ):
        """
        Initialize SEC EDGAR data source.

        Args:
            user_agent: User-Agent string (required by SEC).
                       Format: "Company Name contact@email.com"
                       If None, uses the shared SEC User-Agent resolver.
        """
        super().__init__(api_key=None)  # No API key needed

        self.user_agent = user_agent or get_sec_user_agent()
        self.transport = transport or SecTransport(user_agent=self.user_agent)

        # Cache for CIK lookups
        self._cik_cache: Dict[str, str] = TICKER_TO_CIK.copy()
        self._ticker_map_loaded = False

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
        try:
            response = self.transport.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {url}")
                return None
            else:
                logger.error("SEC API error %s", response.status_code)
                return None

        except SecTransportFailure as exc:
            logger.error("SEC request failed: %s", exc.code)
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

        # Load the official mapping once. A universe run must not make one
        # legacy CGI lookup per ticker.
        if not self._ticker_map_loaded:
            self._ticker_map_loaded = True
            payload = self._make_request("https://www.sec.gov/files/company_tickers.json")
            if isinstance(payload, dict):
                for item in payload.values():
                    if not isinstance(item, dict):
                        continue
                    symbol = str(item.get("ticker") or "").strip().upper()
                    raw_cik = str(item.get("cik_str") or "").strip()
                    if re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", symbol) and raw_cik.isdigit():
                        self._cik_cache[symbol] = raw_cik.zfill(10)
        return self._cik_cache.get(ticker)

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

    def fetch_submissions(self, cik: str) -> Optional[Dict[str, Any]]:
        """Return one filer's official submissions metadata by 10-digit CIK."""
        normalized = str(cik or '').strip().zfill(10)
        if not re.fullmatch(r'\d{10}', normalized):
            raise ValueError("invalid SEC CIK")
        result = self._make_request(f"{self.SUBMISSIONS_URL}/CIK{normalized}.json")
        return result if isinstance(result, dict) else None

    def fetch_filing_document_text(
        self,
        url: str,
        *,
        max_bytes: int = 1_048_576,
    ) -> Optional[str]:
        """Fetch a filing document with a hard response-body bound.

        Corporate-action extraction needs more than the legacy 50,000-character
        preview, but it must not accept an unbounded filing into memory.
        """
        if not str(url).startswith("https://www.sec.gov/Archives/"):
            raise ValueError("unsupported SEC filing URL")
        if isinstance(max_bytes, bool) or not 1024 <= int(max_bytes) <= 5_242_880:
            raise ValueError("invalid max_bytes")
        try:
            response = self.transport.get(
                url,
                timeout=30,
                max_bytes=int(max_bytes),
                document=True,
            )
            if response.status_code != 200:
                logger.warning(
                    "SEC filing document unavailable (%s)", response.status_code
                )
                return None
            return response.text
        except SecTransportFailure as exc:
            logger.warning("Failed to fetch SEC filing document: %s", exc.code)
            return None

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
            content = self.fetch_filing_document_text(
                filing.url,
                max_bytes=max(1024, min(int(max_length) * 4, 5_242_880)),
            )
            if content is None:
                return None
            if len(content) > max_length:
                return content[:max_length] + "\n... [truncated]"
            return content
        except Exception as e:
            logger.warning(f"Failed to fetch filing document: {e}")
            return None

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.transport.close()

    def __del__(self):
        """Clean up session on deletion."""
        self.close()
