"""
Skills system — predefined goal-oriented analysis workflows (Phase 13).

Skills are NOT subagents or execution engines. They are structured prompt
injections that define goals, minimum data sources, and output requirements.
The LLM decides tool selection, call order, and analysis strategy on its own.

Usage:
    /skill full_analysis NVDA   → expands to goal-oriented prompt → fed to agent
    /skill portfolio_scan       → no params needed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SkillDefinition:
    """A predefined goal-oriented analysis workflow."""

    name: str
    description: str
    prompt_template: str  # Contains {ticker} etc. placeholders
    required_params: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


# ── Skill prompt templates ────────────────────────────────────

_FULL_ANALYSIS_PROMPT = """\
Perform a comprehensive entry analysis for {ticker}.

GOAL: Determine whether {ticker} presents a compelling entry opportunity right now.

MINIMUM DATA SOURCES (use all that are relevant):
- News sentiment and recent headlines
- Price action across multiple timeframes (7d, 30d, 90d)
- Fundamental metrics (P/E, ROE, margins, revenue growth)
- Analyst consensus (recommendations, price targets, earnings surprise history)
- IV/options data (IV rank, VRP, unusual activity)
- SEC filings and insider trades (Form 4)
- Web search for recent catalysts not captured in local data

QUANTITATIVE ANALYSIS:
- Use execute_python_analysis for any calculations beyond simple lookups \
(Sharpe ratio, z-score of recent moves, correlation with SPY, drawdown analysis)

REQUIRED OUTPUT:
1. Bull case — specific reasons and supporting data
2. Bear case — specific reasons and supporting data
3. Adversarial check — actively seek evidence against your thesis
4. Key risk factors
5. Data gaps — what information is missing
6. Confidence rating (High/Medium/Low) with explanation
7. Actionable conclusion

AFTER ANALYSIS: Save as a research report using save_report() with \
report_type="entry_analysis".\
"""

_PORTFOLIO_SCAN_PROMPT = """\
Perform a comprehensive scan of the current watchlist.

GOAL: Identify the most actionable opportunities and risks across all positions.

MINIMUM DATA SOURCES:
- Watchlist overview (current positions and status)
- Morning brief (market context)
- Price changes for each ticker (7d and 30d)
- News sentiment for tickers with significant moves

ANALYSIS APPROACH:
- Screen all tickers for significant movers (price, sentiment, volume)
- Rank by opportunity/risk
- For the top 3 most actionable tickers, perform deeper analysis \
(fundamentals, analyst consensus, IV if available)

REQUIRED OUTPUT:
1. Market context summary
2. Watchlist status table (ticker, price change, sentiment, key event)
3. Top 3 opportunities with brief analysis
4. Risk alerts (any position with concerning signals)
5. Recommended actions

AFTER ANALYSIS: Save as a research report using save_report() with \
report_type="morning_brief".\
"""

_EARNINGS_PREP_PROMPT = """\
Prepare a pre-earnings analysis for {ticker}.

GOAL: Assess the risk/reward of holding {ticker} through its upcoming earnings report.

MINIMUM DATA SOURCES:
- Analyst consensus (EPS estimates, recommendation distribution, earnings date)
- Historical earnings surprise pattern (beat/miss history)
- IV analysis (current IV rank vs historical, implied move)
- SEC filings (recent 10-K/10-Q for guidance clues)
- Insider trades (Form 4 — any unusual pre-earnings activity)
- Web search for recent analyst commentary and guidance previews

QUANTITATIVE ANALYSIS:
- Compare implied move (from IV) with historical actual moves around earnings
- Assess whether options are pricing in too much or too little risk
- Calculate risk/reward scenarios (beat, meet, miss)

REQUIRED OUTPUT:
1. Earnings date and consensus estimates
2. Historical surprise pattern (last 4-8 quarters)
3. Expected move vs IV implied move
4. Pre-earnings insider activity
5. Key metrics to watch
6. Risk assessment (High/Medium/Low)
7. Strategy recommendation (hold/trim/hedge/avoid)

AFTER ANALYSIS: Save as a research report using save_report() with \
report_type="earnings_review".\
"""

_SECTOR_ROTATION_PROMPT = """\
Analyze current sector rotation dynamics across the market.

GOAL: Identify which sectors are gaining/losing relative strength and why.

MINIMUM DATA SOURCES:
- Sector performance data (all major sectors)
- Sector ETF price changes across multiple timeframes
- Web search for macro catalysts (Fed policy, economic data, geopolitical)

QUANTITATIVE ANALYSIS:
- Rank sectors by relative strength (multi-timeframe)
- Identify rotation patterns (cyclical vs defensive, growth vs value)
- Compare current rotation to historical patterns

REQUIRED OUTPUT:
1. Sector performance table (1w, 1m, 3m returns)
2. Relative strength ranking
3. Rotation direction (where money is flowing from/to)
4. Macro catalysts driving the rotation
5. Sectors to overweight/underweight
6. Specific ticker ideas within favored sectors

AFTER ANALYSIS: Save as a research report using save_report() with \
report_type="sector_review".\
"""


# ── Skill registry ────────────────────────────────────────────

SKILL_REGISTRY: Dict[str, SkillDefinition] = {
    "full_analysis": SkillDefinition(
        name="full_analysis",
        description="Comprehensive single-ticker entry analysis",
        prompt_template=_FULL_ANALYSIS_PROMPT,
        required_params=["ticker"],
        aliases=["analyze", "fa"],
    ),
    "portfolio_scan": SkillDefinition(
        name="portfolio_scan",
        description="Watchlist-wide screening with drill-down on movers",
        prompt_template=_PORTFOLIO_SCAN_PROMPT,
        required_params=[],
        aliases=["scan", "ps"],
    ),
    "earnings_prep": SkillDefinition(
        name="earnings_prep",
        description="Pre-earnings research and risk assessment",
        prompt_template=_EARNINGS_PREP_PROMPT,
        required_params=["ticker"],
        aliases=["earnings", "ep"],
    ),
    "sector_rotation": SkillDefinition(
        name="sector_rotation",
        description="Cross-sector relative strength and rotation analysis",
        prompt_template=_SECTOR_ROTATION_PROMPT,
        required_params=[],
        aliases=["sectors", "sr"],
    ),
}

# Build alias → skill name lookup
_ALIAS_MAP: Dict[str, str] = {}
for _skill in SKILL_REGISTRY.values():
    for _alias in _skill.aliases:
        _ALIAS_MAP[_alias] = _skill.name


# ── Public API ────────────────────────────────────────────────

def list_skills() -> List[Dict[str, str]]:
    """Return skill info for display."""
    return [
        {
            "name": s.name,
            "description": s.description,
            "required_params": ", ".join(s.required_params) or "(none)",
            "aliases": ", ".join(s.aliases),
        }
        for s in SKILL_REGISTRY.values()
    ]


def expand_skill(name: str, params: Dict[str, str]) -> Optional[str]:
    """Expand a skill template with parameters.

    Returns the expanded prompt string, or None if skill not found
    or required params are missing.
    """
    # Resolve alias
    resolved = _ALIAS_MAP.get(name, name)
    skill = SKILL_REGISTRY.get(resolved)
    if skill is None:
        return None

    # Check required params
    for p in skill.required_params:
        if p not in params or not params[p].strip():
            return None

    # Expand template
    try:
        return skill.prompt_template.format_map(params)
    except KeyError:
        return None


def parse_skill_command(arg: str) -> Tuple[Optional[str], Dict[str, str]]:
    """Parse a /skill command argument string.

    Examples:
        "full_analysis NVDA"  → ("full_analysis", {"ticker": "NVDA"})
        "scan"                → ("portfolio_scan", {})
        "ep TSLA"             → ("earnings_prep", {"ticker": "TSLA"})
        ""                    → (None, {})

    Returns (skill_name, params_dict). skill_name is None if empty input.
    """
    parts = arg.strip().split()
    if not parts:
        return None, {}

    name_or_alias = parts[0].lower()

    # Resolve alias
    resolved = _ALIAS_MAP.get(name_or_alias, name_or_alias)
    skill = SKILL_REGISTRY.get(resolved)
    if skill is None:
        return name_or_alias, {}  # Return unresolved name for error reporting

    # Map positional args to required_params
    params: Dict[str, str] = {}
    remaining = parts[1:]
    for i, param_name in enumerate(skill.required_params):
        if i < len(remaining):
            params[param_name] = remaining[i].upper()  # Tickers are uppercase

    return resolved, params