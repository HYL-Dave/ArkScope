"""
EvidencePacket — the deterministic, objective evidence gatherer for §2 AI cards.

ProductSpec §2.4 makes the card pipeline a three-step contract:
``EvidencePacket -> structured synthesis -> validated ResultCard``. This module
is step 1: a *deterministic* gather of OBJECTIVE / provider-native evidence only.
No LLM runs here, and ArkScope-generated LLM scores are excluded by design
(ToolCatalog §3 rule 9):

  EXCLUDED from the v1 packet
    - ``news_scores`` multi-model columns and any ``sentiment_score`` /
      ``risk_score`` carried on news rows (stripped here)
    - ``get_news_sentiment_summary`` (sentiment_mean) and ``search_news_advanced``
    - ``get_signal_factors`` / ``synthesize_signal`` — built on the ``llm_sentiment``
      pipeline; the whole ``signal_tools`` module is intentionally NOT imported
    - ``get_earnings_impact`` composed conclusions (directional bias, surprise
      correlation, expected move)
    - the ``signal`` label from ``get_iv_analysis`` (a judgment, not a fact)

  INCLUDED (each tagged with ``source_type`` + ``as_of`` + freshness)
    - observed market: price summary, IV environment numbers
    - deterministic_metric: clean technicals computed straight from raw OHLCV
      (returns, range, realized vol, volume vs trailing average) — NO trend
      labels, NO action/confidence, NO composite score
    - observed_news: raw news rows (title/source/time/url/excerpt) — scores stripped
    - provider_native: analyst recommendations + raw earnings facts + price target
    - institutional: fundamentals as normalized numeric metrics (SEC/IBKR/FD)
    - sa_community: Seeking Alpha digest, opinion-tagged (rule-based, no LLM scores)
    - coverage: which sources had data, which were missing, and the exclusion note

Signals as a richer capability are deliberately a *separate* future surface; the
old ``signal_tools`` is legacy / needs-redesign and is not the authority here.
"""

from __future__ import annotations

import logging
import math
import statistics
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from src.env_keys import ensure_env_loaded

logger = logging.getLogger(__name__)

SourceType = Literal[
    "observed_market",
    "observed_news",
    "deterministic_metric",
    "provider_native",
    "institutional",
    "sa_community",
    "coverage",
]

# News-row projection: packet field -> NewsArticle attribute. This map is the
# SINGLE source of truth for what a news row may carry. sentiment_score /
# risk_score are intentionally absent — they are ArkScope LLM scores, excluded
# by §2.4. Rows are built by projecting through this map (see gather step 3), so
# the score-strip is enforced by construction, not by a hand-maintained literal.
_NEWS_FIELD_MAP = {
    "date": "date",
    "ticker": "ticker",
    "title": "title",
    "source": "source",
    "url": "url",
    "publisher": "publisher",
    "excerpt": "description",
}
_NEWS_WHITELIST = tuple(_NEWS_FIELD_MAP)

_EXCLUSION_NOTE = (
    "ArkScope-generated LLM scores are excluded by design (ProductSpec §2.4 / "
    "ToolCatalog rule 9): news_scores, per-row sentiment_score/risk_score, "
    "get_news_sentiment_summary, and signal_tools composite/sentiment outputs are "
    "NOT objective evidence and were not gathered."
)


def _as_str(value: Any) -> Optional[str]:
    """Coerce a value (e.g. a DB date/datetime) to str; None stays None.

    Keeps the packet JSON-safe so ``CardRunStore.record``'s ``json.dumps`` never
    meets a raw datetime/date object.
    """
    return None if value is None else str(value)


class EvidenceItem(BaseModel):
    """One objective evidence fact, traceable by ``evidence_id``."""

    evidence_id: str
    source: str            # e.g. "price_summary", "fundamentals:sec_edgar"
    source_type: SourceType
    as_of: Optional[str] = None
    is_real_time: bool = False
    freshness: Optional[str] = None
    derived_from: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None


class EvidencePacket(BaseModel):
    """Deterministic, objective evidence for one ticker (no LLM scores)."""

    ticker: str
    generated_at: str
    question: Optional[str] = None
    horizon: Optional[str] = None
    items: list[EvidenceItem] = Field(default_factory=list)
    excluded_note: str = _EXCLUSION_NOTE


# ── deterministic technical block (raw OHLCV only) ──────────────────────────


def _pct(numer: float, denom: float) -> Optional[float]:
    if denom in (0, None):
        return None
    return round((numer / denom - 1.0) * 100.0, 2)


def compute_technical_evidence(bars: list) -> dict[str, Any]:
    """Clean technical facts from raw daily OHLCV bars.

    Pure arithmetic on prices/volumes. Emits NUMBERS only — no bullish/bearish,
    no action, no score, no event tags. ``latest_volume_vs_20d_avg`` is a neutral
    ratio (not framed as an "anomaly"). The card synthesis may interpret these;
    this block never does.
    """
    closes = [float(b.close) for b in bars]
    highs = [float(b.high) for b in bars]
    lows = [float(b.low) for b in bars]
    vols = [float(b.volume) for b in bars]
    n = len(bars)
    windows = [1, 5, 20]

    def ret(w: int) -> Optional[float]:
        if n >= w + 1:
            return _pct(closes[-1], closes[-1 - w])
        return None

    win = bars[-20:] if n >= 20 else bars
    win_high = max(float(b.high) for b in win) if win else None
    win_low = min(float(b.low) for b in win) if win else None
    latest_close = closes[-1] if closes else None

    range_20d_pct = (
        round((win_high - win_low) / win_low * 100.0, 2)
        if win_high is not None and win_low not in (None, 0)
        else None
    )
    dist_high = (
        round((latest_close - win_high) / win_high * 100.0, 2)
        if latest_close is not None and win_high not in (None, 0)
        else None
    )
    dist_low = (
        round((latest_close - win_low) / win_low * 100.0, 2)
        if latest_close is not None and win_low not in (None, 0)
        else None
    )

    # Realized vol from up to 20 daily log returns, annualized (×√252), in %.
    log_rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(max(1, n - 20), n)
        if closes[i - 1] > 0 and closes[i] > 0
    ]
    realized_vol = (
        round(statistics.pstdev(log_rets) * math.sqrt(252) * 100.0, 2)
        if len(log_rets) >= 2
        else None
    )

    vol_win = vols[-20:] if vols else []
    avg_vol_20d = round(sum(vol_win) / len(vol_win)) if vol_win else None
    latest_vol = vols[-1] if vols else None
    vol_vs_avg = (
        round(latest_vol / avg_vol_20d, 2)
        if latest_vol is not None and avg_vol_20d not in (None, 0)
        else None
    )

    missing = [f"return_{w}d" for w in windows if n < w + 1]
    if range_20d_pct is None:
        missing.append("range_20d")
    if realized_vol is None:
        missing.append("realized_vol_20d")

    return {
        "bar_count": n,
        "windows_used": windows,
        "return_1d_pct": ret(1),
        "return_5d_pct": ret(5),
        "return_20d_pct": ret(20),
        "range_20d_pct": range_20d_pct,
        "distance_to_20d_high_pct": dist_high,
        "distance_to_20d_low_pct": dist_low,
        "realized_vol_20d_annualized_pct": realized_vol,
        "avg_volume_20d": avg_vol_20d,
        "latest_volume": latest_vol,
        "latest_volume_vs_20d_avg": vol_vs_avg,
        "data_quality": {
            "enough_bars": n >= 21,
            "missing_windows": missing,
            "notes": None if n >= 21 else f"only {n} daily bars (need 21 for 20d window)",
        },
    }


def _daily_bars(dal: Any, ticker: str, days: int) -> tuple[list, Optional[str]]:
    """Daily OHLCV bars, mirroring get_price_change's 15min→daily fallback.

    Returns (bars, date_range). Never raises — empty list on no data.
    """
    res = dal.get_prices(ticker=ticker, interval="1d", days=days)
    if not res.bars:
        res15 = dal.get_prices(ticker=ticker, interval="15min", days=days)
        if res15.bars:
            from src.tools.price_tools import _resample_to_daily_result

            res = _resample_to_daily_result(res15)
    return res.bars, getattr(res, "date_range", None)


# ── gather ──────────────────────────────────────────────────────────────────


class _PacketBuilder:
    def __init__(self) -> None:
        self.items: list[EvidenceItem] = []
        self._n = 0

    def add(
        self,
        source: str,
        source_type: SourceType,
        data: dict,
        *,
        as_of: Optional[str] = None,
        is_real_time: bool = False,
        freshness: Optional[str] = None,
        derived_from: Optional[list[str]] = None,
        note: Optional[str] = None,
    ) -> str:
        self._n += 1
        eid = f"E{self._n}"
        self.items.append(
            EvidenceItem(
                evidence_id=eid,
                source=source,
                source_type=source_type,
                as_of=as_of,
                is_real_time=is_real_time,
                freshness=freshness,
                derived_from=derived_from or [],
                data=data,
                note=note,
            )
        )
        return eid


def gather_evidence(
    dal: Any,
    ticker: str,
    *,
    now_iso: str,
    price_days: int = 60,
    news_days: int = 21,
    max_news: int = 12,
    question: Optional[str] = None,
    horizon: Optional[str] = None,
    sa_enabled: bool = False,
) -> EvidencePacket:
    """Build the deterministic, objective EvidencePacket for one ticker.

    Each source is gathered independently (one failure never zeros the packet);
    failures are recorded in the trailing ``coverage`` item. ``now_iso`` is passed
    in (callers stamp time) so this stays free of wall-clock side effects.
    """
    ensure_env_loaded()
    tkr = (ticker or "").strip().upper()
    b = _PacketBuilder()
    present: list[str] = []
    missing: list[str] = []
    errors: dict[str, str] = {}

    # 1. Price summary (observed) + clean technicals (deterministic) — one fetch.
    price_as_of: Optional[str] = None
    try:
        bars, date_range = _daily_bars(dal, tkr, price_days)
        if bars:
            price_as_of = str(bars[-1].datetime)
            last, first = bars[-1], bars[0]
            b.add(
                "price_summary",
                "observed_market",
                {
                    "latest_close": round(float(last.close), 4),
                    "period_open": round(float(first.open), 4),
                    "period_high": round(max(float(x.high) for x in bars), 4),
                    "period_low": round(min(float(x.low) for x in bars), 4),
                    "bar_count": len(bars),
                    "date_range": date_range,
                },
                as_of=price_as_of,
            )
            price_eid = b.items[-1].evidence_id
            b.add(
                "technical_metrics",
                "deterministic_metric",
                compute_technical_evidence(bars),
                as_of=price_as_of,
                derived_from=[price_eid],
                note="Computed from raw OHLCV only; numeric facts, not a signal.",
            )
            present.append("price")
            present.append("technicals")
        else:
            missing.append("price")
            missing.append("technicals")
    except Exception as exc:  # pragma: no cover - defensive
        errors["price"] = str(exc)
        missing.append("price")
        missing.append("technicals")

    # 2. Fundamentals — normalized numeric metrics (no prose).
    try:
        from src.tools.analysis_tools import get_fundamentals_analysis

        f = get_fundamentals_analysis(dal, tkr)
        metrics = {
            k: getattr(f, k, None)
            for k in (
                "roe", "roa", "debt_to_equity", "current_ratio",
                "revenue_growth", "earnings_growth", "gross_margin",
                "operating_margin", "net_margin", "free_cash_flow",
                "cash_and_equivalents", "total_debt",
            )
        }
        if any(v is not None for v in metrics.values()):
            src_label = getattr(f, "data_source", None) or "fundamentals"
            b.add(
                f"fundamentals:{src_label}",
                "institutional",
                metrics,
                as_of=getattr(f, "snapshot_date", None),
                note="Normalized metrics from filings/provider; no interpretation.",
            )
            present.append("fundamentals")
        else:
            missing.append("fundamentals")
    except Exception as exc:
        errors["fundamentals"] = str(exc)
        missing.append("fundamentals")

    # 3. Raw news rows — scores STRIPPED (scored_only=False = all news).
    try:
        news = dal.get_news(ticker=tkr, days=news_days, scored_only=False)
        rows = []
        latest_date: Optional[str] = None
        for a in news.articles[:max_news]:
            # Project through the whitelist map — only mapped attrs are read, so
            # sentiment_score/risk_score can never enter the packet by accident.
            row = {field: getattr(a, attr, None) for field, attr in _NEWS_FIELD_MAP.items()}
            rows.append(row)
            if row["date"] and (latest_date is None or row["date"] > latest_date):
                latest_date = row["date"]
        if rows:
            b.add(
                "news_rows",
                "observed_news",
                {"count": len(rows), "lookback_days": news_days, "rows": rows},
                as_of=latest_date,
                note="Raw headlines only; LLM sentiment/risk scores excluded by design.",
            )
            present.append("news")
        else:
            missing.append("news")
    except Exception as exc:
        errors["news"] = str(exc)
        missing.append("news")

    # 4. Analyst consensus + raw earnings facts + price target (provider-native).
    try:
        from src.tools.analyst_tools import get_analyst_consensus

        consensus = get_analyst_consensus(tkr)
        # _fetch_recommendations returns a truthy wrapper {"current": None,
        # "trend": []} even on no-data/403/429 — gate on real payload, not the
        # wrapper, so an empty Finnhub response degrades into coverage.missing
        # rather than polluting the packet with an empty provider_native item.
        recs = consensus.get("recommendations") or {}
        price_target = consensus.get("price_target")
        has_recs = bool(recs.get("current") or recs.get("trend") or price_target)
        if has_recs:
            b.add(
                "analyst_recommendations",
                "provider_native",
                {"recommendations": recs, "price_target": price_target},
                as_of=now_iso,
                note="Finnhub provider-native ratings; source-labeled, not re-scored.",
            )
            present.append("analyst")
        earnings = consensus.get("earnings") or {}
        has_earnings = bool(earnings.get("history") or earnings.get("upcoming"))
        if has_earnings:
            b.add(
                "earnings_facts",
                "provider_native",
                {
                    "history": earnings.get("history", []),
                    "upcoming": earnings.get("upcoming"),
                },
                as_of=now_iso,
                note="Raw actual-vs-estimate + upcoming date; NOT a composed earnings-impact view.",
            )
            present.append("earnings")
        if not has_recs and not has_earnings:
            missing.append("analyst")
    except Exception as exc:
        errors["analyst"] = str(exc)
        missing.append("analyst")

    # 5. IV environment — numeric only; the judgment `signal` field is dropped.
    try:
        from src.tools.options_tools import get_iv_analysis

        iv = get_iv_analysis(dal, tkr)
        iv_data = {
            k: getattr(iv, k, None)
            for k in (
                "current_iv", "hv_30d", "vrp", "iv_rank",
                "iv_percentile", "spot_price", "history_days",
            )
        }
        if iv_data.get("current_iv") is not None:
            b.add(
                "iv_environment",
                "observed_market",
                iv_data,
                note="IV numbers + derived rank/percentile; the get_iv_analysis 'signal' label is dropped.",
            )
            present.append("iv")
        else:
            missing.append("iv")
    except Exception as exc:
        errors["iv"] = str(exc)
        missing.append("iv")

    # 6. Seeking Alpha digest — opinion/community, only if enabled (no LLM scores).
    if sa_enabled:
        try:
            from src.tools.sa_digest_tools import get_sa_digest

            digest = get_sa_digest(dal, tkr)
            if digest and "message" not in digest:
                articles = [
                    {
                        "title": a.get("title"),
                        "date": _as_str(a.get("published_date")),
                        "url": a.get("url"),
                        "excerpt": a.get("summary_excerpt"),
                    }
                    for a in (digest.get("recent_articles") or [])
                ]
                # comments live under high_value_comments.{ticker,candidate}_mentions;
                # excerpt is `preview`, high_value_score is rule-based (Stage 1), NOT LLM.
                hvc = digest.get("high_value_comments") or {}
                raw_comments = (hvc.get("ticker_mentions") or []) + (hvc.get("candidate_mentions") or [])
                comments = [
                    {
                        "excerpt": c.get("preview"),
                        "high_value_score": c.get("high_value_score"),
                        "upvotes": c.get("upvotes"),
                        "date": _as_str(c.get("comment_date")),
                        "needs_verification": c.get("needs_verification"),
                    }
                    for c in raw_comments
                ]
                if articles or comments:
                    b.add(
                        "sa_digest",
                        "sa_community",
                        {
                            "window": digest.get("window"),
                            "recent_articles": articles,
                            "high_value_comments": comments,
                        },
                        note="Seeking Alpha community/opinion evidence; rule-based high_value_score (Stage 1), NOT LLM sentiment.",
                    )
                    present.append("sa")
                else:
                    missing.append("sa")
            else:
                missing.append("sa")
        except Exception as exc:
            errors["sa"] = str(exc)
            missing.append("sa")

    # 7. Coverage / missing-data facts + the exclusion note.
    b.add(
        "coverage",
        "coverage",
        {
            "present": present,
            "missing": missing,
            "errors": errors,
            "excluded": _EXCLUSION_NOTE,
        },
    )

    return EvidencePacket(
        ticker=tkr,
        generated_at=now_iso,
        question=question,
        horizon=horizon,
        items=b.items,
    )
