"""
Multi-factor signal synthesizer.

Combines signals from multiple sources (sector momentum, event chains,
anomaly detection) into actionable trading recommendations.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class SignalAction(Enum):
    """Trading action recommendations."""
    STRONG_BUY = 'STRONG_BUY'
    BUY = 'BUY'
    HOLD = 'HOLD'
    SELL = 'SELL'
    STRONG_SELL = 'STRONG_SELL'


@dataclass
class SignalFactor:
    """A single factor contributing to the signal."""
    factor_type: str
    impact: float
    weight: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradingSignal:
    """Synthesized trading signal."""
    action: SignalAction
    confidence: float
    composite_score: float
    risk_level: int  # 1-5
    factors: List[SignalFactor]
    ticker: Optional[str] = None
    sector: Optional[str] = None
    reasoning: str = ''


class SignalSynthesizer:
    """
    Multi-factor signal synthesizer.

    Combines multiple signal sources with configurable weights to produce
    trading recommendations with confidence scores and risk levels.
    """

    # Default factor weights
    DEFAULT_WEIGHTS = {
        'sector_momentum': 0.25,
        'event_chain': 0.30,
        'sentiment_anomaly': 0.20,
        'volume_anomaly': 0.15,
        'extreme_sentiment': 0.10,
    }

    # Action thresholds
    THRESHOLDS = {
        'strong_buy': 0.6,
        'buy': 0.3,
        'sell': -0.3,
        'strong_sell': -0.6,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize signal synthesizer.

        Args:
            weights: Optional custom weights for factors.
                    Keys should match signal types.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def synthesize(
        self,
        signals: Dict[str, Any],
        ticker: Optional[str] = None,
        sector: Optional[str] = None
    ) -> TradingSignal:
        """
        Synthesize multiple signals into a trading recommendation.

        Args:
            signals: Dict containing signal data from various sources:
                - sector_momentum: SectorMomentum or dict with 'trend'
                - event_chains: List of EventChain or dicts
                - sentiment_anomaly: SentimentAnomaly or dict
                - volume_anomaly: VolumeAnomaly or dict
                - extreme_sentiment: bool or float
            ticker: Optional ticker symbol
            sector: Optional sector name

        Returns:
            TradingSignal with action recommendation
        """
        score = 0.0
        factors = []

        # Process sector momentum
        sector_data = signals.get('sector_momentum', {})
        if sector_data:
            score_delta, factor = self._process_sector_momentum(sector_data)
            if factor:
                score += score_delta
                factors.append(factor)

        # Process event chains
        chains = signals.get('event_chains', [])
        if chains:
            score_delta, factor = self._process_event_chains(chains)
            if factor:
                score += score_delta
                factors.append(factor)

        # Process sentiment anomaly
        sentiment_anomaly = signals.get('sentiment_anomaly', {})
        if sentiment_anomaly:
            score_delta, factor = self._process_sentiment_anomaly(sentiment_anomaly)
            if factor:
                score += score_delta
                factors.append(factor)

        # Process volume anomaly
        volume_anomaly = signals.get('volume_anomaly', {})
        if volume_anomaly:
            score_delta, factor = self._process_volume_anomaly(volume_anomaly)
            if factor:
                score += score_delta
                factors.append(factor)

        # Process extreme sentiment
        extreme = signals.get('extreme_sentiment')
        if extreme:
            score_delta, factor = self._process_extreme_sentiment(extreme)
            if factor:
                score += score_delta
                factors.append(factor)

        # Determine action
        action = self._score_to_action(score)
        confidence = self._calculate_confidence(score, factors)
        risk_level = self._assess_risk(signals, factors)
        reasoning = self._generate_reasoning(action, factors)

        return TradingSignal(
            action=action,
            confidence=confidence,
            composite_score=score,
            risk_level=risk_level,
            factors=factors,
            ticker=ticker,
            sector=sector,
            reasoning=reasoning
        )

    def _process_sector_momentum(self, data) -> tuple:
        """Process sector momentum signal."""
        # Handle both dataclass and dict
        trend = data.trend if hasattr(data, 'trend') else data.get('trend', '')
        momentum = data.momentum if hasattr(data, 'momentum') else data.get('momentum', 0)

        weight = self.weights.get('sector_momentum', 0.25)

        if trend == 'ACCELERATING':
            return weight, SignalFactor(
                factor_type='SECTOR_MOMENTUM',
                impact=weight,
                weight=weight,
                details={'trend': trend, 'momentum': momentum}
            )
        elif trend == 'DECELERATING':
            return -weight * 0.5, SignalFactor(
                factor_type='SECTOR_MOMENTUM',
                impact=-weight * 0.5,
                weight=weight,
                details={'trend': trend, 'momentum': momentum}
            )
        return 0, None

    def _process_event_chains(self, chains: List) -> tuple:
        """Process event chain signals."""
        if not chains:
            return 0, None

        weight = self.weights.get('event_chain', 0.30)

        # Find best chain
        best_chain = None
        best_impact = 0

        for chain in chains:
            impact = chain.impact_score if hasattr(chain, 'impact_score') else chain.get('impact_score', 0)
            if abs(impact) > abs(best_impact):
                best_impact = impact
                best_chain = chain

        if not best_chain:
            return 0, None

        # Normalize impact to weight range
        pattern = best_chain.pattern if hasattr(best_chain, 'pattern') else best_chain.get('pattern', '')
        num_events = len(best_chain.events) if hasattr(best_chain, 'events') else best_chain.get('events', 1)
        if isinstance(num_events, list):
            num_events = len(num_events)

        score_delta = min(abs(best_impact) / 2, 1) * weight
        if best_impact < 0:
            score_delta = -score_delta

        return score_delta, SignalFactor(
            factor_type='EVENT_CHAIN',
            impact=score_delta,
            weight=weight,
            details={
                'pattern': pattern,
                'num_events': num_events,
                'chain_impact': best_impact
            }
        )

    def _process_sentiment_anomaly(self, anomaly) -> tuple:
        """Process sentiment anomaly signal."""
        is_anomaly = anomaly.is_anomaly if hasattr(anomaly, 'is_anomaly') else anomaly.get('is_anomaly', False)

        if not is_anomaly:
            return 0, None

        weight = self.weights.get('sentiment_anomaly', 0.20)
        direction = anomaly.direction if hasattr(anomaly, 'direction') else anomaly.get('direction', '')
        z_score = anomaly.z_score if hasattr(anomaly, 'z_score') else anomaly.get('z_score', 0)

        if direction == 'POSITIVE':
            return weight, SignalFactor(
                factor_type='SENTIMENT_ANOMALY',
                impact=weight,
                weight=weight,
                details={'direction': direction, 'z_score': z_score}
            )
        elif direction == 'NEGATIVE':
            return -weight, SignalFactor(
                factor_type='SENTIMENT_ANOMALY',
                impact=-weight,
                weight=weight,
                details={'direction': direction, 'z_score': z_score}
            )
        return 0, None

    def _process_volume_anomaly(self, anomaly) -> tuple:
        """Process volume anomaly signal."""
        is_anomaly = anomaly.is_anomaly if hasattr(anomaly, 'is_anomaly') else anomaly.get('is_anomaly', False)

        if not is_anomaly:
            return 0, None

        weight = self.weights.get('volume_anomaly', 0.15)
        z_score = anomaly.z_score if hasattr(anomaly, 'z_score') else anomaly.get('z_score', 0)

        # Volume spike is generally attention-worthy (neutral to slightly bullish)
        return weight * 0.5, SignalFactor(
            factor_type='VOLUME_SPIKE',
            impact=weight * 0.5,
            weight=weight,
            details={'z_score': z_score}
        )

    def _process_extreme_sentiment(self, extreme) -> tuple:
        """Process extreme sentiment signal."""
        weight = self.weights.get('extreme_sentiment', 0.10)

        if isinstance(extreme, bool):
            if extreme:
                return weight, SignalFactor(
                    factor_type='EXTREME_SENTIMENT',
                    impact=weight,
                    weight=weight,
                    details={}
                )
        elif isinstance(extreme, (int, float)):
            # Could be a count or value
            if extreme > 0:
                return weight, SignalFactor(
                    factor_type='EXTREME_SENTIMENT',
                    impact=weight,
                    weight=weight,
                    details={'count': extreme}
                )
        return 0, None

    def _score_to_action(self, score: float) -> SignalAction:
        """Convert composite score to action."""
        if score >= self.THRESHOLDS['strong_buy']:
            return SignalAction.STRONG_BUY
        elif score >= self.THRESHOLDS['buy']:
            return SignalAction.BUY
        elif score <= self.THRESHOLDS['strong_sell']:
            return SignalAction.STRONG_SELL
        elif score <= self.THRESHOLDS['sell']:
            return SignalAction.SELL
        else:
            return SignalAction.HOLD

    def _calculate_confidence(self, score: float, factors: List[SignalFactor]) -> float:
        """Calculate confidence in the signal."""
        if not factors:
            return 0.5

        # Base confidence from score magnitude
        base_confidence = min(abs(score), 1.0)

        # Boost confidence if multiple factors agree
        factor_agreement = len(factors) / len(self.weights)
        agreement_boost = factor_agreement * 0.2

        return min(base_confidence + agreement_boost, 1.0)

    def _assess_risk(self, signals: Dict, factors: List[SignalFactor]) -> int:
        """Assess risk level (1-5)."""
        risk = 3  # Base risk

        # Extreme sentiment increases risk
        if signals.get('extreme_sentiment'):
            risk += 1

        # High volatility in sentiment increases risk
        sentiment_anomaly = signals.get('sentiment_anomaly', {})
        z_score = sentiment_anomaly.z_score if hasattr(sentiment_anomaly, 'z_score') else sentiment_anomaly.get('z_score', 0)
        if abs(z_score) > 3:
            risk += 1

        # Multiple conflicting factors increase risk
        positive_factors = sum(1 for f in factors if f.impact > 0)
        negative_factors = sum(1 for f in factors if f.impact < 0)
        if positive_factors > 0 and negative_factors > 0:
            risk += 1

        return min(max(risk, 1), 5)

    def _generate_reasoning(self, action: SignalAction, factors: List[SignalFactor]) -> str:
        """Generate human-readable reasoning for the signal."""
        if not factors:
            return "Insufficient signal strength for recommendation."

        parts = []
        for factor in factors:
            direction = "bullish" if factor.impact > 0 else "bearish"
            parts.append(f"{factor.factor_type}: {direction} (impact: {factor.impact:.2f})")

        factor_summary = "; ".join(parts)
        return f"Action: {action.value}. Factors: {factor_summary}"

    def adjust_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Adjust factor weights.

        Args:
            new_weights: Dict of factor names to new weights
        """
        self.weights.update(new_weights)

    def get_factor_contributions(self, signal: TradingSignal) -> Dict[str, float]:
        """
        Get percentage contribution of each factor to the signal.

        Args:
            signal: A TradingSignal object

        Returns:
            Dict mapping factor types to contribution percentages
        """
        total_impact = sum(abs(f.impact) for f in signal.factors)
        if total_impact == 0:
            return {}

        return {
            f.factor_type: abs(f.impact) / total_impact
            for f in signal.factors
        }