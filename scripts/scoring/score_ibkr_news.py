#!/usr/bin/env python3
"""
Incremental sentiment/risk scoring for IBKR news (parquet format).

Features:
- Scans IBKR news parquet files for unscored articles
- Dynamic column naming based on model (e.g., sentiment_gpt_5_2, risk_o4_mini)
- Updates parquet files in-place with scores
- Supports multiple API keys with automatic rotation
- Supports Flex mode fallback (--allow-flex)
- Supports --dry-run to preview what would be scored

Column Naming Convention:
    Model name is converted to column suffix: gpt-5.2 → gpt_5_2
    sentiment_gpt_5_2, risk_gpt_5_2, sentiment_o4_mini, etc.

Usage:
    # Score sentiment with gpt-5.2
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2

    # Score risk with o4-mini
    python scripts/scoring/score_ibkr_news.py --mode risk --model o4-mini

    # Preview what would be scored
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 --dry-run

    # With multiple API keys (one per line in file)
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \\
        --api-keys-file ~/.openai_keys --daily-token-limit 1000000

    # Enable Flex mode fallback after token limit
    python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \\
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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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


def get_score_column(mode: str, model: str) -> str:
    """Get dynamic column name based on mode and model."""
    suffix = model_to_column_suffix(model)
    return f"{mode}_{suffix}"


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
            if ALLOW_FLEX:
                logging.warning(
                    f"API key {CURRENT_KEY_IDX} reached limit ({DAILY_TOKEN_LIMIT}); switching to Flex mode"
                )
                USE_FLEX_MODE = True
            else:
                logging.warning(
                    f"API key {CURRENT_KEY_IDX} reached limit ({DAILY_TOKEN_LIMIT}); will stop after batch"
                )
                STOP_AFTER_CHUNK = True
            CURRENT_KEY_IDX = (CURRENT_KEY_IDX + 1) % len(API_KEYS)
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
        verbosity: Verbosity for gpt-5 models
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
            if model.startswith("o"):
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "messages": messages,
                    "max_completion_tokens": 800,
                    "functions": FUNCTIONS,
                    "function_call": {"name": "record_score"},
                }
            elif model.startswith("gpt-5"):
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "verbosity": verbosity,
                    "messages": messages,
                    "max_completion_tokens": 2400,
                    "functions": FUNCTIONS,
                    "function_call": {"name": "record_score"},
                }
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

            # Parse response
            msg = response.choices[0].message
            if hasattr(msg, "function_call") and msg.function_call is not None:
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
    month: Optional[str] = None,
) -> Dict[Path, pd.DataFrame]:
    """
    Find parquet files with unscored articles.

    Args:
        data_dir: IBKR news data directory
        mode: "sentiment" or "risk"
        model: Model name for dynamic column naming
        month: Optional month filter (YYYY-MM)

    Returns:
        Dict mapping parquet file paths to DataFrames with unscored articles
    """
    score_col = get_score_column(mode, model)
    result = {}

    for parquet_file in data_dir.rglob("*.parquet"):
        # Apply month filter if specified
        if month:
            file_month = parquet_file.stem  # e.g., "2025-01"
            if not file_month.startswith(month):
                continue

        try:
            df = pd.read_parquet(parquet_file, engine='pyarrow')

            # Check if score column exists
            if score_col not in df.columns:
                df[score_col] = None

            # Filter unscored articles (only those with content)
            unscored = df[
                (df[score_col].isna()) &
                (df['content_length'] > 0)  # Only score articles with content
            ]

            if not unscored.empty:
                result[parquet_file] = df  # Return full DataFrame for updating
                logging.info(f"{parquet_file.name}: {len(unscored)}/{len(df)} unscored ({score_col})")

        except Exception as e:
            logging.warning(f"Error reading {parquet_file}: {e}")

    return result


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
) -> Dict[str, int]:
    """
    Score unscored articles in a parquet file.

    Args:
        parquet_file: Path to parquet file
        df: Full DataFrame (will be updated in-place)
        mode: "sentiment" or "risk"
        model: OpenAI model name (determines column name)
        reasoning_effort: Effort level
        verbosity: Verbosity level
        max_articles: Max articles to score
        save_every: Save progress every N articles
        text_column: Column to use for scoring text

    Returns:
        Stats dict with scored/failed counts
    """
    score_col = get_score_column(mode, model)
    stats = {"scored": 0, "failed": 0, "skipped": 0}

    # Find unscored rows
    unscored_mask = df[score_col].isna() & (df['content_length'] > 0)
    unscored_idx = df[unscored_mask].index.tolist()

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

    # Final save
    df.to_parquet(parquet_file, index=False, compression='snappy')

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
        help="IBKR news data directory (default: data/news/raw/ibkr)"
    )
    parser.add_argument(
        "--model", default="gpt-5",
        help="OpenAI model name (default: gpt-5)"
    )
    parser.add_argument(
        "--reasoning-effort", default="high",
        choices=["minimal", "low", "medium", "high"],
        help="Reasoning effort level (default: high)"
    )
    parser.add_argument(
        "--verbosity", default="low",
        choices=["low", "medium", "high"],
        help="Verbosity for gpt-5 models (default: low)"
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
        help="Token limit per API key"
    )
    parser.add_argument(
        "--allow-flex", action="store_true",
        help="Switch to Flex mode after token limit"
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
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            keys = [env_key]

    if not keys and not args.dry_run:
        parser.error("No OpenAI API key provided")

    if keys:
        set_api_keys(keys, args.daily_token_limit)

    # Find unscored articles
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        parser.error(f"Data directory not found: {data_dir}")

    # Get dynamic column name based on model
    score_col = get_score_column(args.mode, args.model)
    logging.info(f"Target column: {score_col}")
    logging.info(f"Scanning {data_dir} for unscored {args.mode} articles...")
    files_to_score = find_unscored_articles(data_dir, args.mode, args.model, args.month)

    if not files_to_score:
        logging.info("No unscored articles found!")
        return

    # Count total unscored
    total_unscored = sum(
        len(df[df[score_col].isna() & (df['content_length'] > 0)])
        for df in files_to_score.values()
    )

    logging.info(f"\nFound {total_unscored} unscored articles in {len(files_to_score)} files")

    if args.dry_run:
        logging.info("\n[DRY RUN] Would score:")
        for pf, df in files_to_score.items():
            unscored = len(df[df[score_col].isna() & (df['content_length'] > 0)])
            logging.info(f"  {pf.name}: {unscored} articles → {score_col}")
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