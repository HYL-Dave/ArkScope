"""Provider-first listing observations, independently of SEC text extraction."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import re
import time
import requests

from data_sources.lifecycle_provider_census_transport import CensusRequestBudget, CensusTransportFailure, LifecycleProviderCensusTransport
from data_sources.listing_authority_transport import (
    ListingAuthorityTransport, ListingRequestBudget, ListingTransportFailure, NASDAQ_LISTED_URL, OTHER_LISTED_URL,
)
from src.security_lifecycle_listing_evidence import (
    ListingEvidenceFailure, ListingRecord, _evidence, parse_massive_ticker, parse_nasdaq_directories,
)
from src.security_lifecycle_provider_authority import classify_provider_listing, evidence_dict, ticker_event_evidence
from src.security_lifecycle_provider_store import ProviderCheckStore, _instant


DIRECTORY_REFRESH_SECONDS = 24 * 60 * 60
FAILED_DIRECTORY_REFRESH_SECONDS = 6 * 60 * 60
EXACT_REFRESH_SECONDS = 24 * 60 * 60
FAILED_EXACT_REFRESH_SECONDS = 60 * 60
MASSIVE_REQUEST_SPACING_SECONDS = 12.5


def refresh_provider_checks(store, *, tickers, at, provider, target_ticker=None):
    """One shared directory pass per day and at most one exact check per tick."""
    tickers = tuple(sorted(set(tickers) | ({target_ticker} if target_ticker is not None else set())))
    if not tickers:
        return {"exact_ticker": None, "directory_refreshed": False, "diagnostics": {}}
    epoch = int(_instant(at).timestamp())
    latest = store.latest()
    def directory_due(ticker):
        diagnostics = latest.get(ticker, {}).get("diagnostics", {})
        interval = FAILED_DIRECTORY_REFRESH_SECONDS if diagnostics.get("directory_failed") else DIRECTORY_REFRESH_SECONDS
        return epoch - diagnostics.get("directory_checked_epoch_s", 0) >= interval
    refresh = any(directory_due(ticker) for ticker in tickers)
    if refresh:
        material, codes = provider.directories(tickers)
        store.record_many([dict(ticker=ticker, at=at, evidence=material.get(ticker, ()), blockers=codes,
                                diagnostics={**provider.diagnostics(), "directory_checked_epoch_s": epoch, "directory_failed": int(bool(codes))})
                           for ticker in tickers])
        latest = store.latest()

    candidates = []
    for ticker in tickers:
        row = latest.get(ticker)
        if row is None:
            continue
        decision = classify_provider_listing(ticker=ticker, evidence=row["evidence"], today=_instant(at).date(), provider_codes=row["blockers"])
        if decision.state == "active" and target_ticker != ticker:
            continue
        last_exact = row["diagnostics"].get("exact_checked_epoch_s", 0)
        interval = FAILED_EXACT_REFRESH_SECONDS if decision.listing_state == "unresolved" else EXACT_REFRESH_SECONDS
        if target_ticker == ticker or epoch - last_exact >= interval:
            candidates.append((last_exact, ticker))
    candidates.sort()
    if target_ticker is not None:
        candidates = [item for item in candidates if item[1] == target_ticker]
    chosen = candidates[0][1] if candidates else None
    if chosen is not None:
        row = latest[chosen]
        directory_rows = tuple(item for item in row["evidence"] if item["adapter"] in {"nasdaq_symbol_directory", "eodhd_symbol_directory"})
        material, codes = provider.exact(chosen)
        directory_codes = tuple(code for code in row["blockers"] if not code.startswith("massive_"))
        material, codes = store.material(ticker=chosen, evidence=directory_rows + tuple(material),
                                        blockers=directory_codes + tuple(codes), at=at)
        store.record(ticker=chosen, at=at, evidence=material, blockers=codes,
                     diagnostics={**row["diagnostics"], **provider.diagnostics(), "exact_checked_epoch_s": epoch})
    return {"exact_ticker": chosen, "directory_refreshed": refresh, "diagnostics": provider.diagnostics()}


class ProviderScanSession:
    """At most four exact listing reads + one timeline; no retry or key fallback."""

    def __init__(self, *, at, massive_key, eodhd_key, listing_transport=None, event_transport=None, sleep=time.sleep, monotonic=time.monotonic):
        self.at = at
        self.massive_key = massive_key
        self.eodhd_key = eodhd_key
        self.listing = listing_transport or ListingAuthorityTransport()
        self.events = event_transport or LifecycleProviderCensusTransport(session=requests.Session())
        self.listing_budget = ListingRequestBudget()
        self.event_budget = CensusRequestBudget(max_massive_requests=1, max_eodhd_requests=2, max_nasdaq_requests=2)
        self.sleep, self.monotonic = sleep, monotonic
        self.last_massive = None

    def close(self):
        try:
            self.listing.close()
        finally:
            self.events.close()

    def diagnostics(self):
        return {
            "massive_requests": self.listing_budget.massive_request_count + self.event_budget.massive_requests,
            "nasdaq_requests": self.listing_budget.nasdaq_request_count,
            "eodhd_requests": self.event_budget.eodhd_requests,
        }

    def _pace(self):
        if self.last_massive is not None:
            wait = MASSIVE_REQUEST_SPACING_SECONDS - (self.monotonic() - self.last_massive)
            if wait > 0:
                self.sleep(wait)
        self.last_massive = self.monotonic()

    def directories(self, tickers):
        material = {ticker: [] for ticker in tickers}
        codes = []
        # Punctuation is provider-specific, never guess a cross-provider alias.
        exact_symbols = tuple(ticker for ticker in tickers if re.fullmatch(r"[A-Z][A-Z0-9]{0,15}", ticker))
        try:
            first = self.listing.fetch_nasdaq(NASDAQ_LISTED_URL, budget=self.listing_budget)
            second = self.listing.fetch_nasdaq(OTHER_LISTED_URL, budget=self.listing_budget)
            directory = parse_nasdaq_directories(nasdaq_bytes=first.body, other_bytes=second.body, retrieved_at=self.at)
            for ticker in exact_symbols:
                material[ticker].extend(_evidence(row) for row in directory.lookup(ticker))
        except (ListingTransportFailure, ListingEvidenceFailure) as exc:
            codes.append(exc.code)
        if not self.eodhd_key:
            codes.append("eodhd_credential_missing")
        elif exact_symbols:
            try:
                result = self.events.fetch_eodhd_symbol_sets(symbols=exact_symbols, api_key=self.eodhd_key, budget=self.event_budget)
                for ticker in exact_symbols:
                    status = "active" if ticker in result.active else "inactive" if ticker in result.delisted else "unverified"
                    # The paired response establishes a partition, not an inferred absence.
                    digest = result.delisted_response_sha256 if status == "inactive" else result.active_response_sha256
                    source = result.delisted_source_locator if status == "inactive" else result.active_source_locator
                    row = ListingRecord("eodhd", "eodhd_symbol_directory", None, ticker, status, status != "inactive", "stocks",
                                        None, None, None, None, None, self.at, None, status in {"active", "inactive"},
                                        source, digest, self.at)
                    material[ticker].append(_evidence(row))
            except CensusTransportFailure as exc:
                codes.append(exc.code)
        return {ticker: tuple(rows) for ticker, rows in material.items()}, tuple(codes)

    def _massive(self, ticker, *, active, market):
        self._pace()
        payload = self.listing.fetch_massive_ticker(ticker, expected_active=active, market=market, api_key=self.massive_key, budget=self.listing_budget)
        return parse_massive_ticker(payload.body, ticker, expected_active=active, market=market, retrieved_at=payload.retrieved_at, source_url=payload.source_url)

    def exact(self, ticker):
        material = []
        if not self.massive_key:
            return (), ("massive_credential_missing",)
        if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", ticker) is None:
            return (), ("massive_symbol_mapping_required",)
        try:
            for market in ("stocks", "otc"):
                row = self._massive(ticker, active=True, market=market)
                material.append(_evidence(row))
                if row.listing_status == "active":
                    return tuple(material), ()
            old = self._massive(ticker, active=False, market="stocks")
            material.append(_evidence(old))
            if old.listing_status != "inactive" or not old.composite_figi:
                return tuple(material), ()
        except (ListingTransportFailure, ListingEvidenceFailure) as exc:
            return tuple(material), (exc.code,)
        try:
            self._pace()
            timeline = self.events.fetch_massive_ticker_events(stable_id=old.composite_figi, api_key=self.massive_key, budget=self.event_budget)
            material.append(ticker_event_evidence(ticker, timeline, at=self.at))
        except CensusTransportFailure as exc:
            return tuple(material), ("massive_timeline_" + exc.code.removeprefix("massive_"),)
        successors = {new for old_ticker, new, _ in timeline.events if old_ticker == ticker}
        if len(successors) == 1:
            try:
                material.append(_evidence(self._massive(next(iter(successors)), active=True, market="stocks")))
            except (ListingTransportFailure, ListingEvidenceFailure) as exc:
                return tuple(material), ("massive_successor_" + exc.code.removeprefix("massive_"),)
        return tuple(material), ()


def run_provider_scan(*, profile_path, tickers, at, target_ticker=None):
    from src.data_provider_config import ProviderConfigMissing
    from src.security_lifecycle_provider_census_credentials import ReadOnlyProviderCredentialStore, resolve_census_credential
    store = ReadOnlyProviderCredentialStore(profile_path)
    credentials = {}
    for provider in ("massive", "eodhd"):
        try:
            credentials[provider] = resolve_census_credential(store, provider)
        except ProviderConfigMissing:
            credentials[provider] = None
    with ExitStack() as stack:
        session = ProviderScanSession(at=at, massive_key=credentials["massive"], eodhd_key=credentials["eodhd"])
        stack.callback(session.close)
        return refresh_provider_checks(ProviderCheckStore(profile_path), tickers=tickers, at=at, provider=session, target_ticker=target_ticker)
