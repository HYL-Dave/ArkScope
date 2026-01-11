"""
Multi-factor signal detection system.

This module provides tools for detecting trading signals from multiple factors:
- Event tagging: Classify news by event type
- Sector aggregation: Calculate sector-level metrics
- Event chain detection: Identify related event sequences
- Anomaly detection: Statistical anomaly detection
- Signal synthesis: Combine multiple signals into trading decisions
"""

from .event_tagger import EventTagger
from .sector_aggregator import SectorAggregator
from .event_chain import EventChainDetector
from .anomaly_detector import AnomalyDetector
from .synthesizer import SignalSynthesizer

__all__ = [
    'EventTagger',
    'SectorAggregator',
    'EventChainDetector',
    'AnomalyDetector',
    'SignalSynthesizer',
]