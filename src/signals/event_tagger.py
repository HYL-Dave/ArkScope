"""
Event type tagger for financial news.

Classifies news articles by event type to enable event chain detection
and sector-level analysis.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import yaml
from pathlib import Path


@dataclass
class TagResult:
    """Result of event tagging."""
    event_types: List[str]
    primary_type: str
    confidence: float
    keywords_matched: List[str]


class EventTagger:
    """
    Event type tagger using rule-based keyword matching.

    For higher accuracy, use the LLM-based tagging via score_sentiment scripts
    with extended prompts.
    """

    # Default event type definitions
    DEFAULT_EVENT_TYPES = {
        'POLICY_POSITIVE': {
            'keywords': ['executive order', 'legislation', 'subsidy', 'approve',
                        'funding boost', 'tax credit', 'incentive', 'support'],
            'weight': 1.0
        },
        'POLICY_NEGATIVE': {
            'keywords': ['ban', 'restriction', 'tariff', 'sanction',
                        'regulation', 'crackdown', 'investigation'],
            'weight': 1.0
        },
        'EXEC_DEPARTURE': {
            'keywords': ['resign', 'step down', 'retire', 'leave', 'departure',
                        'exit', 'ousted'],
            'weight': 0.8
        },
        'EXEC_HIRE': {
            'keywords': ['join', 'appoint', 'name', 'hire', 'promote',
                        'new ceo', 'new cfo', 'brings on'],
            'weight': 0.8
        },
        'TECH_MILESTONE': {
            'keywords': ['launch', 'breakthrough', 'patent', 'first ever',
                        'successful test', 'milestone', 'achievement', 'debut'],
            'weight': 1.2
        },
        'EARNINGS_BEAT': {
            'keywords': ['beat', 'exceed', 'above estimate', 'better than expected',
                        'strong quarter', 'raises guidance', 'tops'],
            'weight': 1.0
        },
        'EARNINGS_MISS': {
            'keywords': ['miss', 'below', 'disappoint', 'worse than expected',
                        'weak quarter', 'lowers guidance', 'falls short'],
            'weight': 1.0
        },
        'FUNDING': {
            'keywords': ['ipo', 'fundraise', 'acquisition', 'merger',
                        'private placement', 'investment round', 'raises'],
            'weight': 0.9
        },
        'ANALYST_UPGRADE': {
            'keywords': ['upgrade', 'raise target', 'overweight', 'buy rating',
                        'bullish', 'initiates coverage'],
            'weight': 0.7
        },
        'ANALYST_DOWNGRADE': {
            'keywords': ['downgrade', 'lower target', 'underweight', 'sell rating',
                        'bearish', 'cut price target'],
            'weight': 0.7
        },
        'PRODUCT_LAUNCH': {
            'keywords': ['launch', 'release', 'unveil', 'introduce', 'announce',
                        'new product', 'rollout'],
            'weight': 0.8
        },
        'PARTNERSHIP': {
            'keywords': ['partner', 'collaborate', 'agreement', 'deal', 'alliance',
                        'joint venture', 'contract'],
            'weight': 0.8
        },
        'LEGAL': {
            'keywords': ['lawsuit', 'sue', 'litigation', 'court', 'settlement',
                        'judgment', 'class action'],
            'weight': 0.9
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize event tagger.

        Args:
            config_path: Optional path to YAML config file with event type definitions.
                        If not provided, uses default definitions.
        """
        if config_path and config_path.exists():
            with open(config_path) as f:
                self.event_types = yaml.safe_load(f)
        else:
            self.event_types = self.DEFAULT_EVENT_TYPES

    def tag(self, title: str, content: str = '') -> TagResult:
        """
        Tag a news article with event types.

        Args:
            title: Article title
            content: Optional article content (body text)

        Returns:
            TagResult with event types, primary type, and confidence
        """
        text = f"{title} {content}".lower()
        matches: Dict[str, List[str]] = {}
        scores: Dict[str, float] = {}

        for event_type, config in self.event_types.items():
            keywords = config.get('keywords', config) if isinstance(config, dict) else config
            weight = config.get('weight', 1.0) if isinstance(config, dict) else 1.0

            matched_keywords = [kw for kw in keywords if kw.lower() in text]
            if matched_keywords:
                matches[event_type] = matched_keywords
                # Score based on number of matches and weight
                scores[event_type] = len(matched_keywords) * weight

        if not matches:
            return TagResult(
                event_types=['GENERAL'],
                primary_type='GENERAL',
                confidence=0.5,
                keywords_matched=[]
            )

        # Sort by score to get primary type
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = sorted_types[0][0]

        # Calculate confidence based on score distribution
        total_score = sum(scores.values())
        confidence = min(sorted_types[0][1] / max(total_score, 1) + 0.5, 1.0)

        all_keywords = []
        for kws in matches.values():
            all_keywords.extend(kws)

        return TagResult(
            event_types=list(matches.keys()),
            primary_type=primary_type,
            confidence=confidence,
            keywords_matched=list(set(all_keywords))
        )

    def tag_batch(self, articles: List[Dict]) -> List[TagResult]:
        """
        Tag multiple articles.

        Args:
            articles: List of dicts with 'title' and optional 'content' keys

        Returns:
            List of TagResult objects
        """
        return [
            self.tag(
                article.get('title', ''),
                article.get('content', '')
            )
            for article in articles
        ]


# LLM-based tagging prompt for use with score_sentiment scripts
LLM_TAGGING_PROMPT = """
Analyze the following news article and identify the event type(s).

Title: {title}
Content: {content}

Select from these event types (can select multiple):
- POLICY_POSITIVE: Government policy favorable to the company/sector
- POLICY_NEGATIVE: Government policy unfavorable to the company/sector
- TECH_MILESTONE: Technical achievement, launch, or breakthrough
- EARNINGS_BEAT: Earnings exceed expectations
- EARNINGS_MISS: Earnings below expectations
- FUNDING: IPO, fundraising, acquisition, or merger
- EXEC_MOVEMENT: Executive hire or departure
- ANALYST_RATING: Analyst upgrade or downgrade
- PRODUCT_LAUNCH: New product or service announcement
- PARTNERSHIP: Business partnership or collaboration
- LEGAL: Lawsuit, investigation, or legal matter
- GENERAL: General news without specific category

Output JSON format:
{{"event_types": ["TYPE1", "TYPE2"], "primary_type": "TYPE1", "confidence": 0.85}}
"""