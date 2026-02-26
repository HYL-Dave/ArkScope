"""
Event chain detection for identifying related event sequences.

Detects patterns like policy announcements followed by technical milestones,
which can be stronger signals than individual events.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class Event:
    """A single event."""
    date: datetime
    ticker: Optional[str]
    sector: Optional[str]
    event_type: str
    sentiment_impact: float  # -1 to 1
    title: str
    article_id: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.date, str):
            self.date = datetime.fromisoformat(self.date.replace('Z', '+00:00'))


@dataclass
class EventChain:
    """A chain of related events."""
    events: List[Event]
    start_date: datetime
    end_date: datetime
    impact_score: float
    pattern: str
    ticker: Optional[str] = None
    sector: Optional[str] = None


# Known high-impact event chain patterns
CHAIN_PATTERNS = {
    'POLICY_TECH_CONFIRMATION': {
        'sequence': ['POLICY_POSITIVE', 'TECH_MILESTONE'],
        'multiplier': 1.5,
        'description': 'Policy support followed by technical achievement'
    },
    'UPGRADE_EARNINGS_CONFIRMATION': {
        'sequence': ['ANALYST_UPGRADE', 'EARNINGS_BEAT'],
        'multiplier': 1.3,
        'description': 'Analyst upgrade validated by earnings'
    },
    'FUNDING_MILESTONE': {
        'sequence': ['FUNDING', 'TECH_MILESTONE'],
        'multiplier': 1.4,
        'description': 'Funding followed by achievement'
    },
    'EARNINGS_MOMENTUM': {
        'sequence': ['EARNINGS_BEAT', 'ANALYST_UPGRADE'],
        'multiplier': 1.3,
        'description': 'Earnings beat followed by upgrades'
    },
    'PARTNERSHIP_LAUNCH': {
        'sequence': ['PARTNERSHIP', 'PRODUCT_LAUNCH'],
        'multiplier': 1.2,
        'description': 'Partnership followed by product launch'
    },
    'NEGATIVE_SPIRAL': {
        'sequence': ['EARNINGS_MISS', 'ANALYST_DOWNGRADE'],
        'multiplier': 1.3,
        'description': 'Earnings miss followed by downgrades (bearish)',
        'is_bearish': True
    },
    'EXEC_TURMOIL': {
        'sequence': ['EXEC_DEPARTURE', 'ANALYST_DOWNGRADE'],
        'multiplier': 1.2,
        'description': 'Executive departure causing concern',
        'is_bearish': True
    },
}


class EventChainDetector:
    """
    Detects event chains - sequences of related events that together
    form stronger signals than individual events.
    """

    def __init__(self, window_days: int = 14):
        """
        Initialize event chain detector.

        Args:
            window_days: Maximum days between related events
        """
        self.window_days = window_days
        self.patterns = CHAIN_PATTERNS

    def events_from_dataframe(
        self,
        df,
        ticker_col: str = 'ticker',
        date_col: str = 'date',
        event_type_col: str = 'event_type',
        sentiment_col: str = 'llm_sentiment',
        title_col: str = 'title',
        sector_col: str = None
    ) -> List[Event]:
        """
        Convert DataFrame rows to Event objects.

        Args:
            df: DataFrame with event data
            ticker_col, date_col, etc: Column names

        Returns:
            List of Event objects
        """
        events = []
        for _, row in df.iterrows():
            # Convert sentiment (1-5) to impact (-1 to 1)
            sentiment = row.get(sentiment_col, 3)
            impact = (sentiment - 3) / 2  # Maps 1->-1, 3->0, 5->1

            event = Event(
                date=row[date_col],
                ticker=row.get(ticker_col),
                sector=row.get(sector_col) if sector_col else None,
                event_type=row.get(event_type_col, 'GENERAL'),
                sentiment_impact=impact,
                title=row.get(title_col, ''),
                article_id=row.get('article_id')
            )
            events.append(event)
        return events

    def detect_chains(self, events: List[Event]) -> List[EventChain]:
        """
        Detect event chains from a list of events.

        Args:
            events: List of Event objects

        Returns:
            List of detected EventChain objects
        """
        if not events:
            return []

        chains = []
        sorted_events = sorted(events, key=lambda x: x.date)

        # Group events by ticker and sector for efficient lookup
        ticker_events = defaultdict(list)
        sector_events = defaultdict(list)

        for event in sorted_events:
            if event.ticker:
                ticker_events[event.ticker].append(event)
            if event.sector:
                sector_events[event.sector].append(event)

        # Find chains within each grouping
        for ticker, ticker_evts in ticker_events.items():
            found_chains = self._find_chains_in_group(ticker_evts)
            for chain in found_chains:
                chain.ticker = ticker
            chains.extend(found_chains)

        for sector, sector_evts in sector_events.items():
            found_chains = self._find_chains_in_group(sector_evts)
            for chain in found_chains:
                if not chain.ticker:  # Don't overwrite ticker-level chains
                    chain.sector = sector
            chains.extend(found_chains)

        # Deduplicate chains with same events
        chains = self._deduplicate_chains(chains)

        return chains

    def _find_chains_in_group(self, events: List[Event]) -> List[EventChain]:
        """Find chains within a group of related events."""
        chains = []

        for i, start_event in enumerate(events):
            # Look for events that follow this one within the window
            chain_events = [start_event]

            for j in range(i + 1, len(events)):
                next_event = events[j]

                days_diff = (next_event.date - start_event.date).days
                if days_diff > self.window_days:
                    break

                # Check if this event extends the chain meaningfully
                if self._should_add_to_chain(chain_events, next_event):
                    chain_events.append(next_event)

            # Only count as chain if 2+ events
            if len(chain_events) >= 2:
                chain = self._create_chain(chain_events)
                if abs(chain.impact_score) > 0.3:  # Minimum impact threshold
                    chains.append(chain)

        return chains

    def _should_add_to_chain(self, chain: List[Event], new_event: Event) -> bool:
        """Determine if new event should be added to chain."""
        # Different event type (same type twice isn't really a chain)
        existing_types = {e.event_type for e in chain}
        if new_event.event_type in existing_types:
            return False

        # Check if it matches known patterns
        current_types = [e.event_type for e in chain]
        potential_types = current_types + [new_event.event_type]

        for pattern_name, pattern in self.patterns.items():
            sequence = pattern['sequence']
            # Check if potential types could be part of this sequence
            if self._is_subsequence(potential_types, sequence):
                return True

        # Allow general catalyst chains (different types, same direction)
        last_event = chain[-1]
        same_direction = (
            (last_event.sentiment_impact > 0 and new_event.sentiment_impact > 0) or
            (last_event.sentiment_impact < 0 and new_event.sentiment_impact < 0)
        )
        return same_direction

    def _is_subsequence(self, subset: List[str], sequence: List[str]) -> bool:
        """Check if subset events are a subsequence of pattern."""
        j = 0
        for item in subset:
            if j < len(sequence) and item == sequence[j]:
                j += 1
        return j > 0  # At least one match

    def _create_chain(self, events: List[Event]) -> EventChain:
        """Create an EventChain from a list of events."""
        pattern = self._identify_pattern(events)
        impact = self._calculate_chain_impact(events, pattern)

        return EventChain(
            events=events,
            start_date=events[0].date,
            end_date=events[-1].date,
            impact_score=impact,
            pattern=pattern
        )

    def _identify_pattern(self, events: List[Event]) -> str:
        """Identify the pattern type of an event chain."""
        event_types = [e.event_type for e in events]

        for pattern_name, pattern in self.patterns.items():
            sequence = pattern['sequence']
            if self._matches_sequence(event_types, sequence):
                return pattern_name

        return 'GENERAL_CATALYST_CHAIN'

    def _matches_sequence(self, event_types: List[str], sequence: List[str]) -> bool:
        """Check if event types match a known sequence."""
        if len(event_types) < len(sequence):
            return False

        # Check if sequence appears in order
        seq_idx = 0
        for evt_type in event_types:
            if seq_idx < len(sequence) and evt_type == sequence[seq_idx]:
                seq_idx += 1

        return seq_idx == len(sequence)

    def _calculate_chain_impact(self, events: List[Event], pattern: str) -> float:
        """Calculate cumulative impact of event chain.

        Sign is determined naturally from event sentiment values:
        bullish events (positive sentiment) → positive impact,
        bearish events (negative sentiment) → negative impact.
        """
        base_impact = 0

        for i, event in enumerate(events):
            # Later events have multiplier effect
            position_multiplier = 1 + (i * 0.2)
            base_impact += event.sentiment_impact * position_multiplier

        # Apply pattern multiplier (preserves sign)
        pattern_config = self.patterns.get(pattern, {})
        pattern_multiplier = pattern_config.get('multiplier', 1.0)

        return base_impact * pattern_multiplier

    def _deduplicate_chains(self, chains: List[EventChain]) -> List[EventChain]:
        """Remove duplicate chains (same events, different grouping)."""
        seen = set()
        unique_chains = []

        for chain in chains:
            # Create a key from event dates and types
            key = tuple(
                (e.date.isoformat(), e.event_type)
                for e in sorted(chain.events, key=lambda x: x.date)
            )
            if key not in seen:
                seen.add(key)
                unique_chains.append(chain)

        return unique_chains