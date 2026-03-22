#!/usr/bin/env python3
"""
Incremental sentiment/risk scoring for news parquet files.

Works with ANY news source that uses the unified parquet schema
(ticker, title, content, content_length, etc.), including:
- Polygon (data/news/raw/polygon/)
- Finnhub (data/news/raw/finnhub/)
- IBKR (data/news/raw/ibkr/)

Features:
- Scans parquet files recursively for unscored articles
- Dynamic column naming based on model (e.g., sentiment_gpt_5_2, risk_o4_mini)
- Updates parquet files in-place with scores
- Supports model switching with --continue-from to pick up where another model left off
- Supports --rescore to force re-scoring articles that already have scores
- Supports multiple API keys with automatic rotation
- Supports Flex mode fallback (--allow-flex)
- Supports --dry-run to preview what would be scored

Column Naming Convention:
    Model name is converted to column suffix: gpt-5.4 → gpt_5_4
    sentiment_gpt_5_4, risk_gpt_5_4, sentiment_gpt_5_4_mini, etc.

Usage:
    # Score Polygon news
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \\
        --data-dir data/news/raw/polygon

    # Score Finnhub news
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \\
        --data-dir data/news/raw/finnhub

    # Score IBKR news (default data-dir)
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4

    # Continue from previous model (only scores articles not yet covered)
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \\
        --continue-from gpt-5.2 --reasoning-effort xhigh

    # Chain: continue from multiple predecessors (comma-separated)
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-6 \\
        --continue-from gpt-5.2,gpt-5.4 --reasoning-effort high

    # Force re-score everything (overwrite existing scores)
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 --rescore

    # Preview what would be scored
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 --dry-run

    # With multiple API keys (one per line in file)
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \\
        --api-keys-file ~/.openai_keys --daily-token-limit 1000000

    # Enable Flex mode fallback after token limit
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \\
        --daily-token-limit 1000000 --allow-flex

    # Limit to specific month
    python scripts/scoring/score_ibkr_news.py --mode sentiment --month 2025-01
"""
import os
import sys
import argparse
import time
import json
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

import pandas as pd
import openai

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from config/.env automatically
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables

# =============================================================================
# API Key Management (shared with score_sentiment_openai.py)
# =============================================================================

API_KEYS = []
TOKENS_USED = {}
CURRENT_KEY_IDX = 0
DAILY_TOKEN_LIMIT = None
STOP_AFTER_CHUNK = False
USE_FLEX_MODE = False
ALLOW_FLEX = False
FLEX_TIMEOUT = 900.0
FLEX_RETRIES = 1

# Token usage stats
TOTAL_PROMPT_TOKENS = 0
TOTAL_COMPLETION_TOKENS = 0
TOTAL_TOKENS = 0
N_CALLS = 0

# Current model (for dynamic column naming)
CURRENT_MODEL = "gpt-5"


def model_to_column_suffix(model: str) -> str:
    """Convert model name to column suffix (e.g., gpt-5.2 → gpt_5_2)."""
    return model.replace("-", "_").replace(".", "_")


def get_score_column(mode: str, model: str, reasoning_effort: str = "high") -> str:
    """
    Get dynamic column name based on mode, model, and reasoning effort.

    Column naming convention:
        {mode}_{model}_{effort}
        e.g., sentiment_gpt_5_2_high, risk_o4_mini_medium

    Note: This includes reasoning_effort (not verbosity) to distinguish
    different scoring configurations. Verbosity is a legacy parameter
    only supported on gpt-5, gpt-5-mini, gpt-5.1 (removed in gpt-5.2+).

    Args:
        mode: "sentiment" or "risk"
        model: Model name (e.g., "gpt-5.2", "o4-mini")
        reasoning_effort: Reasoning effort level (none/minimal/low/medium/high/xhigh)

    Returns:
        Column name like "sentiment_gpt_5_2_high"
    """
    suffix = model_to_column_suffix(model)
    return f"{mode}_{suffix}_{reasoning_effort}"


def set_api_keys(keys: List[str], daily_limit: Optional[int]):
    """Initialize API keys and token limits."""
    global API_KEYS, TOKENS_USED, CURRENT_KEY_IDX, DAILY_TOKEN_LIMIT
    API_KEYS = keys
    TOKENS_USED = {k: 0 for k in keys}
    CURRENT_KEY_IDX = 0
    DAILY_TOKEN_LIMIT = daily_limit
    openai.api_key = API_KEYS[0]


def rotate_key_if_needed(usage: int):
    """Rotate to next API key if token limit reached."""
    global CURRENT_KEY_IDX, STOP_AFTER_CHUNK, USE_FLEX_MODE
    if DAILY_TOKEN_LIMIT is not None:
        if TOKENS_USED.get(API_KEYS[CURRENT_KEY_IDX], 0) + usage >= DAILY_TOKEN_LIMIT:
            # Calculate next key index
            next_idx = (CURRENT_KEY_IDX + 1) % len(API_KEYS)

            # Check if we've cycled through all keys (back to start)
            if next_idx == 0:
                # All keys exhausted
                if ALLOW_FLEX:
                    logging.warning(
                        f"All {len(API_KEYS)} API keys exhausted; switching to Flex mode"
                    )
                    USE_FLEX_MODE = True
                else:
                    logging.warning(
                        f"All {len(API_KEYS)} API keys exhausted; will stop after batch"
                    )
                    STOP_AFTER_CHUNK = True
            else:
                # Still have more keys - rotate without stopping
                logging.info(
                    f"API key {CURRENT_KEY_IDX+1}/{len(API_KEYS)} reached limit ({DAILY_TOKEN_LIMIT:,} tokens); "
                    f"rotating to key {next_idx+1}/{len(API_KEYS)}"
                )

            CURRENT_KEY_IDX = next_idx
            openai.api_key = API_KEYS[CURRENT_KEY_IDX]


# =============================================================================
# Scoring Prompts
# =============================================================================

SENTIMENT_SYSTEM_PROMPT = """
You are a sell-side equity strategist.
For each news headline about one stock, assign an integer sentiment score:
 1 = very bearish  (likely >5 % drop)
 2 = bearish       (2–5 % drop)
 3 = neutral / not relevant
 4 = bullish       (2–5 % rise)
 5 = very bullish  (>5 % rise)
Respond with only the integer sentiment score (1–5). **in JSON**:
```json
{"score": <integer>}
```
If information is insufficient, respond with {"score": 3}.
"""

RISK_SYSTEM_PROMPT = """
You are an equity risk manager.
For each news headline about one stock, assign an integer risk score:
 1 = very low risk    (routine news, no impact)
 2 = low risk         (minor concern)
 3 = moderate risk    (notable but manageable)
 4 = high risk        (significant concern)
 5 = very high risk   (major threat)
Respond with only the integer risk score (1–5). **in JSON**:
```json
{"score": <integer>}
```
If information is insufficient, respond with {"score": 1}.
"""

# Tools format (new) — used for gpt-5.4+ with reasoning_effort
TOOLS = [{
    "type": "function",
    "function": {
        "name": "record_score",
        "parameters": {
            "type": "object",
            "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5}},
            "required": ["score"]
        }
    }
}]

# Legacy functions format — used for gpt-5/gpt-5.1/gpt-5.2 and o-series
FUNCTIONS = [{
    "name": "record_score",
    "parameters": {
        "type": "object",
        "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5}},
        "required": ["score"]
    }
}]


def score_article(
    text: str,
    symbol: str,
    model: str,
    mode: str = "sentiment",
    reasoning_effort: str = "high",
    verbosity: str = "low",
    retry: int = 3,
    pause: float = 0.5,
) -> Optional[int]:
    """
    Score one article using OpenAI API.

    Args:
        text: Article title or content to score
        symbol: Stock ticker symbol
        model: OpenAI model name
        mode: "sentiment" or "risk"
        reasoning_effort: Effort level for reasoning models
        verbosity: Verbosity for legacy gpt-5/gpt-5-mini only (ignored for gpt-5.2+)
        retry: Number of retries
        pause: Pause between retries

    Returns:
        Integer score 1-5 or None on failure
    """
    global TOTAL_PROMPT_TOKENS, TOTAL_COMPLETION_TOKENS, TOTAL_TOKENS, N_CALLS

    system_prompt = SENTIMENT_SYSTEM_PROMPT if mode == "sentiment" else RISK_SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"TICKER: {symbol}\nHEADLINE:\n{text}"}
    ]

    use_flex = ALLOW_FLEX and USE_FLEX_MODE
    max_attempts = FLEX_RETRIES if use_flex else retry

    for attempt in range(1, max_attempts + 1):
        try:
            # Build parameters based on model type
            # gpt-5.4+ requires new tools format with reasoning_effort
            # (legacy functions format not supported with reasoning_effort)
            _is_gpt54_plus = model.startswith("gpt-5.4")

            if model.startswith("o"):
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "messages": messages,
                    "max_completion_tokens": 800,
                    "functions": FUNCTIONS,
                    "function_call": {"name": "record_score"},
                }
            elif _is_gpt54_plus:
                # gpt-5.4+: new tools format (required for reasoning_effort)
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "messages": messages,
                    "max_completion_tokens": 2400,
                    "tools": TOOLS,
                    "tool_choice": {"type": "function", "function": {"name": "record_score"}},
                }
            elif model.startswith("gpt-5"):
                # gpt-5/5.1/5.2: legacy functions format
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "messages": messages,
                    "max_completion_tokens": 2400,
                    "functions": FUNCTIONS,
                    "function_call": {"name": "record_score"},
                }
                # verbosity only supported on gpt-5, gpt-5-mini, gpt-5.1 (removed in gpt-5.2+)
                if model in ("gpt-5", "gpt-5-mini", "gpt-5.1"):
                    params["verbosity"] = verbosity
            else:
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 20,
                }

            if use_flex:
                params["service_tier"] = "flex"
                params["timeout"] = FLEX_TIMEOUT

            N_CALLS += 1
            response = openai.chat.completions.create(**params)
            usage = response.usage
            pt = usage.prompt_tokens
            ct = usage.completion_tokens
            tt = usage.total_tokens

            TOTAL_PROMPT_TOKENS += pt
            TOTAL_COMPLETION_TOKENS += ct
            TOTAL_TOKENS += tt
            TOKENS_USED[API_KEYS[CURRENT_KEY_IDX]] += tt
            rotate_key_if_needed(tt)

            logging.debug(f"Token usage: prompt={pt}, completion={ct}, total={tt}")

            # Parse response — handle both tools format and legacy function_call
            msg = response.choices[0].message
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                try:
                    args = json.loads(msg.tool_calls[0].function.arguments)
                    score = int(args.get("score"))
                    if 1 <= score <= 5:
                        return score
                except Exception:
                    pass
            elif hasattr(msg, "function_call") and msg.function_call is not None:
                try:
                    args = json.loads(msg.function_call.arguments)
                    score = int(args.get("score"))
                    if 1 <= score <= 5:
                        return score
                except Exception:
                    pass
            else:
                txt = msg.content.strip()
                try:
                    score = json.loads(txt)["score"]
                    if 1 <= score <= 5:
                        return score
                except Exception:
                    m = re.search(r"\b([1-5])\b", txt)
                    if m:
                        return int(m.group(1))

            logging.warning(f"Attempt {attempt}/{retry}: no valid score parsed")
            time.sleep(pause * attempt)

        except Exception as e:
            logging.error(f"Attempt {attempt}/{retry} failed: {e}")
            time.sleep(pause * attempt)

    return None


# =============================================================================
# IBKR News Processing
# =============================================================================

def find_unscored_articles(
    data_dir: Path,
    mode: str,
    model: str,
    reasoning_effort: str = "high",
    month: Optional[str] = None,
    continue_from: Optional[str] = None,
    continue_from_effort: Optional[str] = None,
    rescore: bool = False,
) -> Dict[Path, pd.DataFrame]:
    """
    Find parquet files with articles that need scoring.

    Scoring modes:
        Default: Score articles where the target column is empty.
        --continue-from: Score articles where ALL listed predecessor models
            have NO score (i.e. truly new articles) and the new model also
            has no score. Supports comma-separated model chains to prevent
            re-scoring when multiple generations of models have been used.
        --rescore: Score all articles (overwrite existing scores in target column).

    Args:
        data_dir: News data directory
        mode: "sentiment" or "risk"
        model: Target model name for dynamic column naming
        reasoning_effort: Reasoning effort level for column naming
        month: Optional month filter (YYYY-MM)
        continue_from: Previous model name(s) to continue from.
            Comma-separated for chains: "gpt-5.2,gpt-5.4"
            Only articles NOT scored by ANY of these models (and also not yet
            scored by the new model) will be selected.
        continue_from_effort: Reasoning effort of the previous model(s). If None,
            auto-detects by scanning columns. Applied to all models in the chain.
        rescore: If True, re-score all articles (ignore existing scores).

    Returns:
        Dict mapping parquet file paths to DataFrames with articles to score
    """
    score_col = get_score_column(mode, model, reasoning_effort)

    # Parse comma-separated model chain for --continue-from
    prev_models = []
    if continue_from:
        prev_models = [m.strip() for m in continue_from.split(",") if m.strip()]

    result = {}

    for parquet_file in sorted(data_dir.rglob("*.parquet")):
        # Apply month filter if specified
        if month:
            file_month = parquet_file.stem  # e.g., "2025-01"
            if not file_month.startswith(month):
                continue

        try:
            df = pd.read_parquet(parquet_file, engine='pyarrow')

            # Ensure target score column exists
            if score_col not in df.columns:
                df[score_col] = None

            # Determine which rows to score
            has_content = df['content_length'] > 0

            if rescore:
                # Re-score everything with content
                to_score = has_content
            elif prev_models:
                # Chain mode: skip articles scored by ANY predecessor column.
                # Each model may have multiple effort columns; OR them all.
                any_prev_scored = pd.Series(False, index=df.index)
                for pm in prev_models:
                    if continue_from_effort:
                        cols = [get_score_column(mode, pm, continue_from_effort)]
                        cols = [c for c in cols if c in df.columns]
                    else:
                        cols = _detect_prev_columns(df, mode, pm)
                    if cols:
                        for pc in cols:
                            any_prev_scored = any_prev_scored | df[pc].notna()
                    else:
                        logging.debug(
                            f"{parquet_file.name}: no column for "
                            f"'{pm}' ({mode}), ignoring in chain"
                        )
                new_unscored = df[score_col].isna()
                to_score = has_content & ~any_prev_scored & new_unscored
            else:
                # Default: only articles where target column is empty
                to_score = has_content & df[score_col].isna()

            unscored = df[to_score]

            if not unscored.empty:
                result[parquet_file] = df
                extra = ""
                if continue_from:
                    extra = f" (continue from {continue_from})"
                elif rescore:
                    extra = " (rescore)"
                logging.info(
                    f"{parquet_file.name}: {len(unscored)}/{len(df)} "
                    f"to score ({score_col}){extra}"
                )

        except Exception as e:
            logging.warning(f"Error reading {parquet_file}: {e}")

    return result


def _detect_prev_columns(df: pd.DataFrame, mode: str, model: str) -> List[str]:
    """Auto-detect ALL score columns for a previous model.

    Scans DataFrame columns for patterns like {mode}_{model_suffix}_{effort}
    and returns all matches. A model may have multiple effort columns
    (e.g., sentiment_gpt_5_2_high AND sentiment_gpt_5_2_xhigh).
    """
    suffix = model_to_column_suffix(model)
    prefix = f"{mode}_{suffix}"
    matches = []

    # Exact match without effort (legacy columns like sentiment_haiku)
    if prefix in df.columns:
        matches.append(prefix)

    # Match with any effort suffix
    for col in df.columns:
        if col.startswith(prefix + "_") and col not in matches:
            matches.append(col)

    return matches


def score_parquet_file(
    parquet_file: Path,
    df: pd.DataFrame,
    mode: str,
    model: str,
    reasoning_effort: str = "high",
    verbosity: str = "low",
    max_articles: Optional[int] = None,
    save_every: int = 20,
    text_column: str = "title",
    continue_from: Optional[str] = None,
    continue_from_effort: Optional[str] = None,
    rescore: bool = False,
) -> Dict[str, int]:
    """
    Score articles in a parquet file.

    Args:
        parquet_file: Path to parquet file
        df: Full DataFrame (will be updated in-place)
        mode: "sentiment" or "risk"
        model: OpenAI model name (determines column name)
        reasoning_effort: Effort level
        verbosity: Verbosity for legacy gpt-5/gpt-5-mini only
        max_articles: Max articles to score
        save_every: Save progress every N articles
        text_column: Column to use for scoring text
        continue_from: Previous model name(s), comma-separated for chains
        continue_from_effort: Reasoning effort of previous model(s)
        rescore: If True, re-score all articles

    Returns:
        Stats dict with scored/failed counts
    """
    score_col = get_score_column(mode, model, reasoning_effort)
    stats = {"scored": 0, "failed": 0, "skipped": 0}

    # Determine which rows need scoring
    has_content = df['content_length'] > 0

    if rescore:
        target_mask = has_content
    elif continue_from:
        # Chain mode: skip articles scored by ANY predecessor column
        prev_models = [m.strip() for m in continue_from.split(",") if m.strip()]
        any_prev_scored = pd.Series(False, index=df.index)
        for pm in prev_models:
            if continue_from_effort:
                cols = [get_score_column(mode, pm, continue_from_effort)]
                cols = [c for c in cols if c in df.columns]
            else:
                cols = _detect_prev_columns(df, mode, pm)
            for pc in cols:
                any_prev_scored = any_prev_scored | df[pc].notna()
        target_mask = has_content & ~any_prev_scored & df[score_col].isna()
    else:
        target_mask = has_content & df[score_col].isna()

    unscored_idx = df[target_mask].index.tolist()

    if max_articles:
        unscored_idx = unscored_idx[:max_articles]

    if not unscored_idx:
        logging.info(f"No unscored articles in {parquet_file.name}")
        return stats

    logging.info(f"Scoring {len(unscored_idx)} articles in {parquet_file.name}")

    for i, idx in enumerate(unscored_idx):
        row = df.loc[idx]

        # Get text to score (prefer content, fallback to title)
        if text_column == "content" and row.get('content'):
            text = str(row['content'])[:2000]  # Truncate long content
        else:
            text = str(row['title'])

        symbol = row.get('ticker', 'UNKNOWN')

        # Skip if no text
        if not text.strip():
            stats["skipped"] += 1
            continue

        # Score
        score = score_article(
            text=text,
            symbol=symbol,
            model=model,
            mode=mode,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
        )

        if score is not None:
            df.at[idx, score_col] = score
            stats["scored"] += 1
            logging.info(f"  [{i+1}/{len(unscored_idx)}] {symbol}: {score}")
        else:
            stats["failed"] += 1
            logging.warning(f"  [{i+1}/{len(unscored_idx)}] {symbol}: FAILED")

        # Save progress periodically
        if (i + 1) % save_every == 0:
            df.to_parquet(parquet_file, index=False, compression='snappy')
            logging.info(f"  [Checkpoint] Saved progress ({i+1} processed)")

        # Check if we should stop
        if STOP_AFTER_CHUNK:
            logging.info("Token limit reached; stopping")
            break

    # Final save (covers any articles after the last checkpoint)
    df.to_parquet(parquet_file, index=False, compression='snappy')
    saved_total = stats["scored"] + stats["failed"]
    last_checkpoint = (saved_total // save_every) * save_every
    remaining = saved_total - last_checkpoint
    if remaining > 0:
        logging.info(f"  [Final save] {remaining} articles since last checkpoint (total: {saved_total})")
    else:
        logging.info(f"  [Final save] All {saved_total} articles already checkpointed")

    return stats


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Incremental sentiment/risk scoring for IBKR news",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mode", required=True, choices=["sentiment", "risk"],
        help="Scoring mode: sentiment or risk"
    )
    parser.add_argument(
        "--data-dir", type=str, default="data/news/raw/ibkr",
        help="News data directory with parquet files (default: data/news/raw/ibkr). "
             "Works with any source: polygon, finnhub, ibkr, etc."
    )
    parser.add_argument(
        "--model", default="gpt-5",
        help="OpenAI model name (default: gpt-5)"
    )
    parser.add_argument(
        "--reasoning-effort", default="high",
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="Reasoning effort level: none/minimal/low/medium/high/xhigh (default: high). "
             "Note: 'xhigh' requires Pro subscription."
    )
    parser.add_argument(
        "--verbosity", default="low",
        choices=["low", "medium", "high"],
        help="Verbosity for legacy gpt-5/gpt-5-mini/gpt-5.1 only (ignored for gpt-5.2+). Default: low"
    )
    parser.add_argument(
        "--text-column", default="title",
        choices=["title", "content"],
        help="Column to use for scoring text (default: title)"
    )
    parser.add_argument(
        "--month", type=str, default=None,
        help="Limit to specific month (YYYY-MM)"
    )
    parser.add_argument(
        "--max-articles", type=int, default=None,
        help="Max articles to score per file"
    )
    parser.add_argument(
        "--max-total", type=int, default=None,
        help="Max total articles to score across all files"
    )
    parser.add_argument(
        "--save-every", type=int, default=20,
        help="Save progress every N articles (default: 20)"
    )
    parser.add_argument(
        "--api-key", default=None,
        help="OpenAI API key (default: OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--api-keys-file", default=None,
        help="File with one API key per line"
    )
    parser.add_argument(
        "--daily-token-limit", type=int, default=None,
        help="Token limit PER API KEY (not total). E.g., 2 keys with 1000000 = 2M total"
    )
    parser.add_argument(
        "--allow-flex", action="store_true",
        help="Switch to Flex mode after token limit"
    )
    # --- Model switching ---
    parser.add_argument(
        "--continue-from", type=str, default=None, metavar="MODEL[,MODEL,...]",
        help="Continue scoring from where previous model(s) left off. "
             "Comma-separated for model chains. Only articles NOT scored by "
             "ANY listed model will be selected. "
             "E.g.: --model gpt-5.4 --continue-from gpt-5.2 | "
             "--model gpt-6 --continue-from gpt-5.2,gpt-5.4"
    )
    parser.add_argument(
        "--continue-from-effort", type=str, default=None,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="Restrict predecessor lookup to this effort column. "
             "Usually omit — auto-detect finds ALL effort columns per model. "
             "Only use to target a specific effort level."
    )
    parser.add_argument(
        "--rescore", action="store_true",
        help="Force re-score all articles, overwriting existing scores for this model"
    )

    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be scored without calling API"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Setup API keys
    global ALLOW_FLEX
    ALLOW_FLEX = args.allow_flex

    keys = []
    if args.api_keys_file:
        with open(args.api_keys_file) as f:
            keys = [line.strip() for line in f if line.strip()]
    elif args.api_key:
        keys = [args.api_key]
    else:
        # Check OPENAI_API_KEYS first (comma-separated, for rotation)
        env_keys = os.getenv("OPENAI_API_KEYS")
        if env_keys:
            keys = [k.strip() for k in env_keys.split(",") if k.strip()]
            logging.info(f"Loaded {len(keys)} API keys from OPENAI_API_KEYS env var")
        else:
            # Fallback to single OPENAI_API_KEY
            env_key = os.getenv("OPENAI_API_KEY")
            if env_key:
                keys = [env_key]
                logging.info("Loaded 1 API key from OPENAI_API_KEY env var")

    if not keys and not args.dry_run:
        parser.error("No OpenAI API key provided")

    if keys:
        set_api_keys(keys, args.daily_token_limit)
        if args.daily_token_limit:
            logging.info(f"Token limit: {args.daily_token_limit:,} per key × {len(keys)} keys = {args.daily_token_limit * len(keys):,} total")

    # Find unscored articles
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        parser.error(f"Data directory not found: {data_dir}")

    # Validate: --continue-from and --rescore are mutually exclusive
    if args.continue_from and args.rescore:
        parser.error("--continue-from and --rescore are mutually exclusive")

    # Get dynamic column name based on model and reasoning effort
    score_col = get_score_column(args.mode, args.model, args.reasoning_effort)
    logging.info(f"Target column: {score_col}")
    if args.continue_from:
        logging.info(f"Mode: continue from {args.continue_from}")
    elif args.rescore:
        logging.info(f"Mode: rescore (overwrite existing)")
    logging.info(f"Scanning {data_dir} for {args.mode} articles to score...")
    files_to_score = find_unscored_articles(
        data_dir, args.mode, args.model, args.reasoning_effort, args.month,
        continue_from=args.continue_from,
        continue_from_effort=args.continue_from_effort,
        rescore=args.rescore,
    )

    if not files_to_score:
        logging.info("No unscored articles found!")
        return

    # Count articles to score (must mirror find_unscored_articles logic)
    def _count_to_score(df):
        has_content = df['content_length'] > 0
        if args.rescore:
            return int(has_content.sum())
        elif args.continue_from:
            prev_models = [m.strip() for m in args.continue_from.split(",") if m.strip()]
            any_prev_scored = pd.Series(False, index=df.index)
            for pm in prev_models:
                if args.continue_from_effort:
                    cols = [get_score_column(args.mode, pm, args.continue_from_effort)]
                    cols = [c for c in cols if c in df.columns]
                else:
                    cols = _detect_prev_columns(df, args.mode, pm)
                for pc in cols:
                    any_prev_scored = any_prev_scored | df[pc].notna()
            return int((has_content & ~any_prev_scored & df[score_col].isna()).sum())
        else:
            return int((has_content & df[score_col].isna()).sum())

    total_to_score = sum(_count_to_score(df) for df in files_to_score.values())

    mode_label = "rescore" if args.rescore else (
        f"continue from {args.continue_from}" if args.continue_from else "default"
    )
    logging.info(f"\nFound {total_to_score} articles to score in {len(files_to_score)} files ({mode_label})")

    if args.dry_run:
        logging.info("\n[DRY RUN] Would score:")
        for pf, df in files_to_score.items():
            count = _count_to_score(df)
            logging.info(f"  {pf.name}: {count} articles → {score_col}")
        return

    # Score articles
    start_time = time.time()
    total_scored = 0
    total_failed = 0

    for parquet_file, df in files_to_score.items():
        if args.max_total and total_scored >= args.max_total:
            logging.info(f"Reached max-total limit ({args.max_total})")
            break

        remaining = args.max_total - total_scored if args.max_total else None
        max_for_file = min(args.max_articles or float('inf'), remaining or float('inf'))
        if max_for_file == float('inf'):
            max_for_file = None

        stats = score_parquet_file(
            parquet_file=parquet_file,
            df=df,
            mode=args.mode,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            verbosity=args.verbosity,
            max_articles=int(max_for_file) if max_for_file else None,
            save_every=args.save_every,
            text_column=args.text_column,
            continue_from=args.continue_from,
            continue_from_effort=args.continue_from_effort,
            rescore=args.rescore,
        )

        total_scored += stats["scored"]
        total_failed += stats["failed"]

        if STOP_AFTER_CHUNK:
            break

    # Summary
    elapsed = time.time() - start_time
    logging.info("\n" + "=" * 60)
    logging.info("SCORING COMPLETE")
    logging.info("=" * 60)
    logging.info(f"Mode: {args.mode}")
    logging.info(f"Model: {args.model}")
    logging.info(f"Articles scored: {total_scored}")
    logging.info(f"Articles failed: {total_failed}")
    logging.info(f"Time: {elapsed:.1f}s")

    if N_CALLS > 0:
        logging.info(f"\nToken usage:")
        logging.info(f"  Total calls: {N_CALLS}")
        logging.info(f"  Avg prompt tokens: {TOTAL_PROMPT_TOKENS/N_CALLS:.1f}")
        logging.info(f"  Avg completion tokens: {TOTAL_COMPLETION_TOKENS/N_CALLS:.1f}")
        logging.info(f"  Total tokens: {TOTAL_TOKENS:,}")


if __name__ == "__main__":
    main()