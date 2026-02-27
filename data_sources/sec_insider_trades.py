"""
SEC EDGAR Form 4 Parser for Insider Trades.

Replaces Financial Datasets API endpoint 14 (/insider-trades).

Usage:
    from data_sources.sec_insider_trades import get_insider_trades

    trades = get_insider_trades('AAPL', limit=10)
    # Returns list of dicts matching FD API format
"""

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DEFAULT_SEC_CONTACT = 'MindfulRL-Intraday research@example.com'


def _get_sec_user_agent() -> str:
    """Build SEC User-Agent from env var or default (with warning)."""
    contact = os.environ.get('SEC_CONTACT_EMAIL', '').strip()
    if contact:
        return f'MindfulRL-Intraday {contact}'
    logger.warning(
        "SEC_CONTACT_EMAIL not set — using placeholder User-Agent. "
        "SEC may rate-limit or reject requests. Set SEC_CONTACT_EMAIL in config/.env"
    )
    return _DEFAULT_SEC_CONTACT


# SEC requires a User-Agent header
SEC_HEADERS = {
    'User-Agent': _get_sec_user_agent(),
    'Accept': 'application/json, application/xml, text/html',
}

# Transaction codes mapping
TRANSACTION_CODES = {
    'P': 'Purchase',
    'S': 'Sale',
    'A': 'Award',
    'D': 'Disposition to issuer',
    'F': 'Payment of exercise price',
    'I': 'Discretionary transaction',
    'M': 'Exercise or conversion',
    'C': 'Conversion of derivative',
    'E': 'Expiration of short position',
    'G': 'Gift',
    'L': 'Small acquisition',
    'W': 'Acquisition or disposition by will',
    'Z': 'Deposit or withdrawal from voting trust',
    'J': 'Other acquisition or disposition',
    'K': 'Equity swap',
    'U': 'Disposition due to tender of shares',
}


@dataclass
class InsiderTrade:
    """Single insider trade record matching FD API format."""
    ticker: str
    issuer: str
    name: str
    title: str
    is_board_director: bool
    transaction_date: str
    transaction_shares: int  # Negative for sales
    transaction_price_per_share: Optional[float]
    transaction_value: Optional[int]
    shares_owned_before_transaction: Optional[int]
    shares_owned_after_transaction: int
    security_title: str
    filing_date: str

    def to_dict(self) -> dict:
        return {
            'ticker': self.ticker,
            'issuer': self.issuer,
            'name': self.name,
            'title': self.title,
            'is_board_director': self.is_board_director,
            'transaction_date': self.transaction_date,
            'transaction_shares': self.transaction_shares,
            'transaction_price_per_share': self.transaction_price_per_share,
            'transaction_value': self.transaction_value,
            'shares_owned_before_transaction': self.shares_owned_before_transaction,
            'shares_owned_after_transaction': self.shares_owned_after_transaction,
            'security_title': self.security_title,
            'filing_date': self.filing_date,
        }


class SECInsiderTrades:
    """Parse SEC Form 4 filings to extract insider trades."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(SEC_HEADERS)
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

    def _get_form4_filings(self, cik: str, limit: int = 20) -> list[dict]:
        """Get list of Form 4 filings for a CIK."""
        url = f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json'
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        recent = data.get('filings', {}).get('recent', {})

        forms = recent.get('form', [])
        accessions = recent.get('accessionNumber', [])
        filing_dates = recent.get('filingDate', [])

        filings = []
        for i, form in enumerate(forms):
            if form == '4' and len(filings) < limit:
                filings.append({
                    'accession': accessions[i],
                    'filing_date': filing_dates[i],
                })

        return filings

    def _find_form4_xml_url(self, cik: str, accession: str) -> Optional[str]:
        """Find the XML file URL for a Form 4 filing."""
        accession_clean = accession.replace('-', '')
        index_url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{accession}-index.htm'

        resp = self._session.get(index_url, timeout=30)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find XML links (exclude XSLT transformed versions)
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if href.endswith('.xml') and 'xsl' not in href.lower():
                if href.startswith('/'):
                    return f'https://www.sec.gov{href}'
                return f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{href}'

        return None

    def _parse_form4_xml(self, xml_content: str, filing_date: str) -> list[InsiderTrade]:
        """Parse Form 4 XML and extract trades."""
        trades = []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse Form 4 XML: {e}")
            return []

        # Extract issuer info
        issuer = root.find('.//issuer')
        if issuer is None:
            return []

        ticker = self._get_text(issuer, 'issuerTradingSymbol', '').upper()
        issuer_name = self._get_text(issuer, 'issuerName', '')

        # Extract reporting owner info
        owner = root.find('.//reportingOwner')
        if owner is None:
            return []

        owner_name = self._get_text(owner, './/rptOwnerName', '')
        # Format name: "LASTNAME FIRSTNAME" -> "Firstname Lastname"
        owner_name = self._format_name(owner_name)

        relationship = owner.find('.//reportingOwnerRelationship')
        is_director = self._get_text(relationship, 'isDirector', '0') == '1' if relationship is not None else False
        is_officer = self._get_text(relationship, 'isOfficer', '0') == '1' if relationship is not None else False
        officer_title = self._get_text(relationship, 'officerTitle', '') if relationship is not None else ''

        # Determine title
        if officer_title:
            title = officer_title
        elif is_director:
            title = 'Director'
        elif is_officer:
            title = 'Officer'
        else:
            title = ''

        # Parse non-derivative transactions (common stock)
        for txn in root.findall('.//nonDerivativeTransaction'):
            trade = self._parse_transaction(
                txn, ticker, issuer_name, owner_name, title,
                is_director, filing_date
            )
            if trade:
                trades.append(trade)

        return trades

    def _parse_transaction(
        self, txn: ET.Element, ticker: str, issuer_name: str,
        owner_name: str, title: str, is_director: bool, filing_date: str
    ) -> Optional[InsiderTrade]:
        """Parse a single transaction element."""

        security_title = self._get_text(txn, './/securityTitle/value', 'Common Stock')
        transaction_date = self._get_text(txn, './/transactionDate/value', '')

        # Get transaction code (S=Sale, P=Purchase, etc.)
        txn_code = self._get_text(txn, './/transactionCoding/transactionCode', '')
        acquired_disposed = self._get_text(txn, './/transactionAcquiredDisposedCode/value', '')

        # Get shares and price
        shares_str = self._get_text(txn, './/transactionShares/value', '0')
        price_str = self._get_text(txn, './/transactionPricePerShare/value', '')
        shares_after_str = self._get_text(txn, './/sharesOwnedFollowingTransaction/value', '0')

        try:
            shares = int(float(shares_str))
            shares_after = int(float(shares_after_str))
            price = float(price_str) if price_str else None
        except (ValueError, TypeError):
            return None

        # Adjust sign: D (disposed) = negative, A (acquired) = positive
        if acquired_disposed == 'D':
            shares = -abs(shares)
        else:
            shares = abs(shares)

        # Calculate shares before
        shares_before = shares_after - shares  # shares is signed

        # Calculate transaction value
        txn_value = abs(int(shares * price)) if price else None

        return InsiderTrade(
            ticker=ticker,
            issuer=issuer_name,
            name=owner_name,
            title=title,
            is_board_director=is_director,
            transaction_date=transaction_date,
            transaction_shares=shares,
            transaction_price_per_share=price,
            transaction_value=txn_value,
            shares_owned_before_transaction=shares_before,
            shares_owned_after_transaction=shares_after,
            security_title=security_title,
            filing_date=filing_date,
        )

    @staticmethod
    def _get_text(element: Optional[ET.Element], path: str, default: str = '') -> str:
        """Safely get text from an XML element."""
        if element is None:
            return default
        found = element.find(path)
        if found is not None and found.text:
            return found.text.strip()
        return default

    @staticmethod
    def _format_name(name: str) -> str:
        """Format 'LASTNAME FIRSTNAME' to 'Firstname Lastname'."""
        parts = name.split()
        if len(parts) >= 2:
            # Assume first part is last name
            return ' '.join(p.title() for p in parts[1:]) + ' ' + parts[0].title()
        return name.title()

    def get_insider_trades(self, ticker: str, limit: int = 10) -> list[dict]:
        """
        Get insider trades for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            limit: Maximum number of trades to return

        Returns:
            List of trade dicts matching Financial Datasets API format
        """
        cik = self._get_cik(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {ticker}")
            return []

        # Get more filings than needed since each filing may have multiple transactions
        filings = self._get_form4_filings(cik, limit=limit * 2)

        all_trades = []
        for filing in filings:
            if len(all_trades) >= limit:
                break

            xml_url = self._find_form4_xml_url(cik, filing['accession'])
            if not xml_url:
                continue

            try:
                resp = self._session.get(xml_url, timeout=30)
                if resp.status_code != 200:
                    continue

                trades = self._parse_form4_xml(resp.text, filing['filing_date'])
                all_trades.extend(trades)

            except Exception as e:
                logger.warning(f"Error fetching {xml_url}: {e}")
                continue

        # Sort by transaction date (most recent first) and limit
        all_trades.sort(key=lambda t: t.transaction_date, reverse=True)

        return [t.to_dict() for t in all_trades[:limit]]


# Convenience function
def get_insider_trades(ticker: str, limit: int = 10) -> list[dict]:
    """
    Get insider trades for a ticker from SEC Form 4.

    This is a FREE replacement for Financial Datasets API endpoint 14 (/insider-trades).

    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        limit: Maximum number of trades to return

    Returns:
        List of trade dicts with keys:
        - ticker, issuer, name, title, is_board_director
        - transaction_date, transaction_shares (negative for sales)
        - transaction_price_per_share, transaction_value
        - shares_owned_before_transaction, shares_owned_after_transaction
        - security_title, filing_date

    Example:
        >>> trades = get_insider_trades('AAPL', limit=5)
        >>> trades[0]
        {'ticker': 'AAPL', 'name': 'Chris Kondo', 'transaction_shares': -3752, ...}
    """
    return _get_singleton().get_insider_trades(ticker, limit)


# Module-level singleton — keeps CIK cache + requests.Session across calls
_singleton: Optional[SECInsiderTrades] = None


def _get_singleton() -> SECInsiderTrades:
    global _singleton
    if _singleton is None:
        _singleton = SECInsiderTrades()
    return _singleton


if __name__ == '__main__':
    # Test
    import json
    trades = get_insider_trades('AAPL', limit=10)
    print(f"Found {len(trades)} trades")
    print(json.dumps(trades[:3], indent=2))