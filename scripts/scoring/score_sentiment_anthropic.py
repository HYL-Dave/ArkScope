#!/usr/bin/env python3
"""
Score sentiment of financial news headlines using Anthropic Claude.

This script mirrors score_sentiment_openai.py but uses Claude models.
Supports Batch API for 50% cost savings (async processing).

Supported input/output formats:
- CSV (.csv) - legacy format, compatible with FNSPID
- Parquet (.parquet) - recommended for Polygon/Finnhub collected data

Models available:
- claude-sonnet-4-5-20250929 (recommended): $3/$15 per 1M tokens
- claude-haiku-4-5-20251001 (economy): $1/$5 per 1M tokens
- claude-opus-4-6 (premium): $5/$25 per 1M tokens

Batch API pricing (50% off, results within 24 hours):
- Sonnet batch: $1.50/$7.50 per 1M tokens

Key differences from OpenAI version:
- No "flex mode" (Anthropic uses Batch API instead for discounts)
- Batch API is async (submit batch, poll for results)
- Different token tracking format

Usage:
    # === CSV format (legacy, compatible with FNSPID) ===
    python score_sentiment_anthropic.py --input news.csv --output scored.csv

    # === Parquet format (recommended for Polygon/Finnhub data) ===
    python score_sentiment_anthropic.py \\
        --input data/news/raw/polygon/2024/2024-12.parquet \\
        --output data/news/scored/2024-12.parquet \\
        --symbol-column ticker \\
        --text-column title

    # Batch scoring (50% cheaper, async processing)
    python score_sentiment_anthropic.py \\
        --input data.parquet --output scored.parquet --batch

    # Use economy model
    python score_sentiment_anthropic.py --input news.csv --output scored.csv --model haiku

Column mapping for Parquet (Polygon/Finnhub format):
    --symbol-column ticker      # Stock symbol column
    --text-column title         # Text to score (headline)
"""

import os
import sys
import argparse
import time
import logging
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass

import pandas as pd
import anthropic

# Load environment variables from config/.env
try:
    from dotenv import load_dotenv
    # Try project config/.env first, then root .env
    env_paths = [
        Path(__file__).parent / "config" / ".env",
        Path(__file__).parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables


# =============================================================================
# File I/O Helpers (CSV and Parquet support)
# =============================================================================

def read_dataframe(path: Union[str, Path], **kwargs) -> pd.DataFrame:
    """
    Read DataFrame from CSV or Parquet based on file extension.

    Args:
        path: Path to CSV (.csv) or Parquet (.parquet) file.
        **kwargs: Additional arguments passed to read function.

    Returns:
        pandas DataFrame.
    """
    path = Path(path)
    if path.suffix.lower() == '.parquet':
        return pd.read_parquet(path, **{k: v for k, v in kwargs.items()
                                        if k not in ['on_bad_lines', 'engine', 'chunksize']})
    else:
        return pd.read_csv(path, **kwargs)


def write_dataframe(df: pd.DataFrame, path: Union[str, Path], **kwargs) -> None:
    """
    Write DataFrame to CSV or Parquet based on file extension.

    Args:
        df: DataFrame to write.
        path: Output path (.csv or .parquet).
        **kwargs: Additional arguments passed to write function.
    """
    path = Path(path)
    if path.suffix.lower() == '.parquet':
        # Filter out CSV-specific kwargs
        parquet_kwargs = {k: v for k, v in kwargs.items()
                          if k not in ['mode', 'header']}
        df.to_parquet(path, index=False, compression='snappy', **parquet_kwargs)
    else:
        df.to_csv(path, index=False, **kwargs)


def get_file_format(path: Union[str, Path]) -> str:
    """Return 'parquet' or 'csv' based on file extension."""
    return 'parquet' if Path(path).suffix.lower() == '.parquet' else 'csv'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Model configurations
MODELS = {
    "sonnet": "claude-sonnet-4-5-20250929",
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-6",
}

# Default model
DEFAULT_MODEL = "sonnet"

# System prompt (aligned with OpenAI version for comparability)
SYSTEM_PROMPT = """You are a sell-side equity strategist.
For each news headline about one stock, assign an integer sentiment score:
 1 = very bearish  (likely >5% drop)
 2 = bearish       (2-5% drop)
 3 = neutral / not relevant
 4 = bullish       (2-5% rise)
 5 = very bullish  (>5% rise)

Respond with ONLY a JSON object in this exact format:
{"score": <integer from 1-5>}

If information is insufficient, respond with {"score": 3}."""


@dataclass
class TokenUsage:
    """Track token usage across API calls."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    n_calls: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, usage):
        """Add usage from API response."""
        self.prompt_tokens += usage.input_tokens
        self.completion_tokens += usage.output_tokens
        self.total_tokens += usage.input_tokens + usage.output_tokens
        self.n_calls += 1
        # Track cache tokens if available
        if hasattr(usage, 'cache_read_input_tokens'):
            self.cache_read_tokens += usage.cache_read_input_tokens or 0
        if hasattr(usage, 'cache_creation_input_tokens'):
            self.cache_write_tokens += usage.cache_creation_input_tokens or 0

    def summary(self) -> str:
        """Return usage summary string."""
        if self.n_calls == 0:
            return "No API calls made"
        return (
            f"Total calls: {self.n_calls}, "
            f"Avg prompt: {self.prompt_tokens/self.n_calls:.1f}, "
            f"Avg completion: {self.completion_tokens/self.n_calls:.1f}, "
            f"Total tokens: {self.total_tokens}, "
            f"Cache read: {self.cache_read_tokens}, "
            f"Cache write: {self.cache_write_tokens}"
        )

    def estimated_cost(self, model: str = "sonnet", is_batch: bool = False) -> float:
        """Estimate cost based on model pricing."""
        # Prices per 1M tokens (input, output)
        prices = {
            "sonnet": (3.0, 15.0),  # $3/1M input, $15/1M output
            "haiku": (1.0, 5.0),    # $1/1M input, $5/1M output
            "opus": (5.0, 25.0),    # $5/1M input, $25/1M output
        }
        input_price, output_price = prices.get(model, prices["sonnet"])

        # Batch API is 50% off
        if is_batch:
            input_price *= 0.5
            output_price *= 0.5

        input_cost = (self.prompt_tokens / 1_000_000) * input_price
        output_cost = (self.completion_tokens / 1_000_000) * output_price
        return input_cost + output_cost


# Global token tracker
token_usage = TokenUsage()


def create_client(api_key: Optional[str] = None) -> anthropic.Anthropic:
    """Create Anthropic client with API key."""
    key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise ValueError(
            "No Anthropic API key provided. "
            "Set ANTHROPIC_API_KEY environment variable or use --api-key argument."
        )
    return anthropic.Anthropic(api_key=key)


def score_headline(
    client: anthropic.Anthropic,
    headline: str,
    symbol: str,
    model: str = "sonnet",
    retry: int = 3,
    pause: float = 0.5,
) -> Optional[int]:
    """
    Score a single headline for sentiment using Claude (real-time).

    Args:
        client: Anthropic client instance.
        headline: News headline text.
        symbol: Stock ticker symbol.
        model: Model shorthand (sonnet, haiku, opus).
        retry: Number of retry attempts.
        pause: Pause between retries in seconds.

    Returns:
        Integer sentiment score 1-5, or None on failure.
    """
    model_id = MODELS.get(model, MODELS[DEFAULT_MODEL])
    user_message = f"TICKER: {symbol}\nHEADLINE:\n{headline}"

    for attempt in range(1, retry + 1):
        try:
            response = client.messages.create(
                model=model_id,
                max_tokens=50,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ],
            )

            # Track usage
            token_usage.add(response.usage)

            # Parse response
            content = response.content[0].text.strip()

            # Try JSON parsing first
            try:
                result = json.loads(content)
                score = int(result.get('score', 3))
                if 1 <= score <= 5:
                    return score
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

            # Fallback: extract integer from text
            match = re.search(r'\b([1-5])\b', content)
            if match:
                return int(match.group(1))

            logger.warning(
                f"Attempt {attempt}/{retry}: Could not parse score from: '{content[:100]}'"
            )

        except anthropic.RateLimitError as e:
            logger.warning(f"Rate limit hit, waiting 60s: {e}")
            time.sleep(60)

        except anthropic.APIError as e:
            logger.error(f"API error on attempt {attempt}/{retry}: {e}")
            time.sleep(pause * attempt)

        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt}/{retry}: {e}")
            time.sleep(pause * attempt)

    return None


def prepare_batch_requests(
    df: pd.DataFrame,
    symbol_col: str,
    text_col: str,
    model: str = "sonnet",
) -> List[Dict[str, Any]]:
    """
    Prepare batch requests for Anthropic Batch API.

    Args:
        df: DataFrame with headlines to score.
        symbol_col: Column name for stock symbol.
        text_col: Column name for headline text.
        model: Model shorthand.

    Returns:
        List of batch request objects.
    """
    model_id = MODELS.get(model, MODELS[DEFAULT_MODEL])
    requests = []

    for idx, row in df.iterrows():
        text = row[text_col]
        symbol = row[symbol_col]

        if pd.isna(text) or not str(text).strip():
            continue

        user_message = f"TICKER: {symbol}\nHEADLINE:\n{str(text)[:500]}"

        request = {
            "custom_id": str(idx),
            "params": {
                "model": model_id,
                "max_tokens": 50,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_message}
                ],
            }
        }
        requests.append(request)

    return requests


def submit_batch(
    client: anthropic.Anthropic,
    requests: List[Dict[str, Any]],
) -> str:
    """
    Submit a batch of requests to Anthropic Batch API.

    Args:
        client: Anthropic client.
        requests: List of batch request objects.

    Returns:
        Batch ID for tracking.
    """
    batch = client.messages.batches.create(requests=requests)
    logger.info(f"Batch submitted: {batch.id}, {len(requests)} requests")
    return batch.id


def poll_batch_results(
    client: anthropic.Anthropic,
    batch_id: str,
    poll_interval: float = 60.0,
    max_wait: float = 86400.0,  # 24 hours
) -> Dict[str, int]:
    """
    Poll for batch results until complete.

    Args:
        client: Anthropic client.
        batch_id: Batch ID to poll.
        poll_interval: Seconds between polls.
        max_wait: Maximum wait time in seconds.

    Returns:
        Dictionary mapping custom_id to sentiment score.
    """
    start_time = time.time()
    results = {}

    while time.time() - start_time < max_wait:
        batch = client.messages.batches.retrieve(batch_id)

        if batch.processing_status == "ended":
            logger.info(f"Batch {batch_id} completed")

            # Retrieve results
            for result in client.messages.batches.results(batch_id):
                custom_id = result.custom_id

                if result.result.type == "succeeded":
                    content = result.result.message.content[0].text.strip()

                    # Parse score
                    try:
                        score = json.loads(content).get('score', 3)
                        if 1 <= score <= 5:
                            results[custom_id] = score
                        else:
                            results[custom_id] = 3
                    except (json.JSONDecodeError, TypeError):
                        match = re.search(r'\b([1-5])\b', content)
                        results[custom_id] = int(match.group(1)) if match else 3
                else:
                    logger.warning(f"Request {custom_id} failed: {result.result.type}")
                    results[custom_id] = None

            return results

        elif batch.processing_status == "failed":
            logger.error(f"Batch {batch_id} failed")
            return results

        logger.info(f"Batch {batch_id} status: {batch.processing_status}, waiting...")
        time.sleep(poll_interval)

    logger.warning(f"Batch {batch_id} timed out after {max_wait}s")
    return results


def process_file_realtime(
    input_path: str,
    output_path: str,
    client: anthropic.Anthropic,
    model: str = "sonnet",
    symbol_col: str = "Stock_symbol",
    text_col: str = "Article_title",
    chunk_size: int = 1000,
    retry: int = 3,
    retry_missing: int = 3,
    pause: float = 0.1,
    max_runtime: Optional[float] = None,
) -> None:
    """
    Process CSV or Parquet file with real-time API calls (immediate results).

    Supports both CSV and Parquet formats based on file extension.
    """
    input_format = get_file_format(input_path)
    output_format = get_file_format(output_path)

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Resume logic
    processed_rows = 0
    if os.path.exists(output_path):
        prev = read_dataframe(output_path, on_bad_lines='warn', engine='c')
        processed_rows = len(prev)
        logger.info(f"Resuming from row {processed_rows}")

    start_time = time.time()
    # Dynamic column name based on model (e.g., sonnet → sentiment_sonnet)
    out_col = f"sentiment_{model}"

    # Handle Parquet vs CSV differently
    if input_format == 'parquet':
        # Parquet: load entire file, process in memory chunks
        df = pd.read_parquet(input_path)
        logger.info(f"Loaded {len(df)} rows from Parquet")

        # Validate columns
        required = [symbol_col, text_col]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}. Available: {list(df.columns)}")

        df[out_col] = None
        all_chunks = []

        for chunk_start in range(0, len(df), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(df))

            if chunk_end <= processed_rows:
                continue

            logger.info(f"Processing rows {chunk_start}-{chunk_end}")

            for idx in range(chunk_start, chunk_end):
                if idx < processed_rows:
                    continue

                row = df.iloc[idx]
                text = row[text_col]
                symbol = row[symbol_col]

                if pd.isna(text) or not str(text).strip():
                    logger.warning(f"Skipping empty text for {symbol}:{idx}")
                    continue

                score = score_headline(
                    client=client,
                    headline=str(text)[:500],
                    symbol=symbol,
                    model=model,
                    retry=retry,
                )

                # Extra retries if needed
                for _ in range(retry_missing):
                    if score is not None:
                        break
                    logger.warning(f"Missing sentiment for {symbol}:{idx}, retrying...")
                    score = score_headline(
                        client=client,
                        headline=str(text)[:500],
                        symbol=symbol,
                        model=model,
                        retry=retry,
                    )

                df.iat[idx, df.columns.get_loc(out_col)] = score
                time.sleep(pause)

            # Checkpoint: save progress
            write_dataframe(df, output_path)
            logger.info(f"Checkpoint saved at row {chunk_end}, {token_usage.n_calls} total API calls")

            if max_runtime and (time.time() - start_time) >= max_runtime:
                logger.info(f"Max runtime reached at row {chunk_end}")
                break

    else:
        # CSV: use chunked reader for memory efficiency
        cleaned_csv = input_path + '.cleaned'
        with open(input_path, 'rb') as f_in, open(cleaned_csv, 'wb') as f_out:
            content = f_in.read()
            content = content.replace(b'\x00', b'')
            f_out.write(content)

        reader = pd.read_csv(cleaned_csv, chunksize=chunk_size, on_bad_lines='warn', engine='c')

        for i, chunk in enumerate(reader):
            chunk_start = i * chunk_size
            chunk_end = chunk_start + len(chunk)

            if chunk_end <= processed_rows:
                continue

            logger.info(f"Processing chunk {i}: rows {chunk_start}-{chunk_end}")

            # Validate columns
            required = [symbol_col, text_col]
            missing = [c for c in required if c not in chunk.columns]
            if missing:
                raise ValueError(f"Missing required columns: {missing}")

            chunk[out_col] = None

            for idx, row in chunk.iterrows():
                if idx < processed_rows:
                    continue

                text = row[text_col]
                symbol = row[symbol_col]

                if pd.isna(text) or not str(text).strip():
                    logger.warning(f"Skipping empty text for {symbol}:{idx}")
                    continue

                score = score_headline(
                    client=client,
                    headline=str(text)[:500],
                    symbol=symbol,
                    model=model,
                    retry=retry,
                )

                # Extra retries if needed
                for _ in range(retry_missing):
                    if score is not None:
                        break
                    logger.warning(f"Missing sentiment for {symbol}:{idx}, retrying...")
                    score = score_headline(
                        client=client,
                        headline=str(text)[:500],
                        symbol=symbol,
                        model=model,
                        retry=retry,
                    )

                chunk.at[idx, out_col] = score
                time.sleep(pause)

            # Write chunk (CSV append mode)
            header = not os.path.exists(output_path)
            chunk.to_csv(output_path, mode='a', header=header, index=False)
            logger.info(f"Chunk {i} written, {token_usage.n_calls} total API calls")

            if max_runtime and (time.time() - start_time) >= max_runtime:
                logger.info(f"Max runtime reached after chunk {i}")
                break

        # Cleanup
        if os.path.exists(cleaned_csv):
            os.remove(cleaned_csv)

    logger.info(f"Processing complete. Output: {output_path}")
    logger.info(f"Token usage: {token_usage.summary()}")
    logger.info(f"Estimated cost: ${token_usage.estimated_cost(model):.4f}")


def process_file_batch(
    input_path: str,
    output_path: str,
    client: anthropic.Anthropic,
    model: str = "sonnet",
    symbol_col: str = "Stock_symbol",
    text_col: str = "Article_title",
    batch_size: int = 10000,
    poll_interval: float = 60.0,
) -> None:
    """
    Process CSV or Parquet file using Batch API (50% cheaper, async).

    Supports both CSV and Parquet formats based on file extension.
    """
    input_format = get_file_format(input_path)

    # Load input data
    if input_format == 'parquet':
        df = pd.read_parquet(input_path)
        logger.info(f"Loaded {len(df)} rows from Parquet for batch processing")
    else:
        # Clean CSV file (remove null bytes)
        cleaned_csv = input_path + '.cleaned'
        with open(input_path, 'rb') as f_in, open(cleaned_csv, 'wb') as f_out:
            content = f_in.read()
            content = content.replace(b'\x00', b'')
            f_out.write(content)
        df = pd.read_csv(cleaned_csv, on_bad_lines='warn', engine='c')
        logger.info(f"Loaded {len(df)} rows from CSV for batch processing")

    # Validate columns
    required = [symbol_col, text_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Available: {list(df.columns)}")

    # Process in batches
    # Dynamic column name based on model (e.g., sonnet → sentiment_sonnet)
    out_col = f"sentiment_{model}"
    df[out_col] = None

    all_results = {}

    for batch_start in range(0, len(df), batch_size):
        batch_end = min(batch_start + batch_size, len(df))
        batch_df = df.iloc[batch_start:batch_end]

        logger.info(f"Preparing batch: rows {batch_start}-{batch_end}")

        # Prepare and submit batch
        requests = prepare_batch_requests(batch_df, symbol_col, text_col, model)

        if not requests:
            logger.warning(f"No valid requests in batch {batch_start}-{batch_end}")
            continue

        batch_id = submit_batch(client, requests)

        # Poll for results
        results = poll_batch_results(client, batch_id, poll_interval)
        all_results.update(results)

        logger.info(f"Batch complete: {len(results)} results")

    # Apply results to DataFrame
    for idx_str, score in all_results.items():
        idx = int(idx_str)
        df.at[idx, out_col] = score

    # Save output
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    write_dataframe(df, output_path)

    # Cleanup (CSV only)
    if input_format == 'csv':
        cleaned_csv = input_path + '.cleaned'
        if os.path.exists(cleaned_csv):
            os.remove(cleaned_csv)

    scored_count = df[out_col].notna().sum()
    logger.info(f"Batch processing complete. {scored_count}/{len(df)} rows scored.")
    logger.info(f"Output saved to: {output_path}")
    logger.info(f"Estimated cost (batch pricing): ${token_usage.estimated_cost(model, is_batch=True):.4f}")


def process_file_incremental(
    input_path: str,
    output_path: str,
    client: anthropic.Anthropic,
    model: str = "sonnet",
    symbol_col: str = "Stock_symbol",
    text_col: str = "Article_title",
    merge_key: Optional[str] = None,
    chunk_size: int = 1000,
    retry: int = 3,
    retry_missing: int = 3,
    pause: float = 0.1,
    max_runtime: Optional[float] = None,
    use_batch: bool = False,
    batch_size: int = 10000,
    poll_interval: float = 60.0,
) -> None:
    """
    Process file in incremental mode: merge with existing output and only score new/NULL rows.

    This is the recommended mode for daily updates when new data is added to the input file.

    Args:
        input_path: Path to input file (full dataset, may include new rows).
        output_path: Path to output file (may contain previously scored rows).
        client: Anthropic client.
        model: Model shorthand.
        symbol_col: Column name for stock symbol.
        text_col: Column name for headline text.
        merge_key: Column to use for merging (default: article_id/dedup_hash).
        chunk_size: Rows per checkpoint in real-time mode.
        retry: Retry attempts per headline.
        retry_missing: Extra retries for missing scores.
        pause: Pause between API calls.
        max_runtime: Maximum runtime in seconds.
        use_batch: Use Batch API for scoring.
        batch_size: Requests per batch.
        poll_interval: Seconds between batch status checks.
    """
    input_format = get_file_format(input_path)
    # Dynamic column name based on model (e.g., sonnet → sentiment_sonnet)
    out_col = f"sentiment_{model}"

    # Determine merge key
    if merge_key is None:
        merge_key = "article_id" if input_format == "parquet" else "dedup_hash"

    # Load input data
    logger.info(f"Loading input file: {input_path}")
    if input_format == 'parquet':
        df_input = pd.read_parquet(input_path)
    else:
        df_input = pd.read_csv(input_path, on_bad_lines='warn', engine='c', low_memory=False)
    logger.info(f"Input rows: {len(df_input):,}")

    # Validate merge key exists
    if merge_key not in df_input.columns:
        logger.error(f"Merge key '{merge_key}' not found in input. Available: {list(df_input.columns)[:10]}...")
        raise ValueError(f"Merge key '{merge_key}' not found in input file")

    # Load existing output if exists
    if os.path.exists(output_path):
        logger.info(f"Loading existing output: {output_path}")
        df_existing = read_dataframe(output_path, on_bad_lines='warn', engine='c')
        logger.info(f"Existing rows: {len(df_existing):,}")

        if merge_key not in df_existing.columns:
            logger.warning(f"Merge key '{merge_key}' not in existing output, will re-score all")
            df_merged = df_input.copy()
            df_merged[out_col] = None
        else:
            # Merge: keep all input rows, join existing scores
            existing_scores = df_existing[[merge_key, out_col]].drop_duplicates(subset=[merge_key])
            df_merged = df_input.merge(
                existing_scores,
                on=merge_key,
                how='left',
                suffixes=('', '_existing')
            )
            # If score column already exists in input, prefer existing output's scores
            if out_col + '_existing' in df_merged.columns:
                df_merged[out_col] = df_merged[out_col + '_existing']
                df_merged.drop(columns=[out_col + '_existing'], inplace=True)
            elif out_col not in df_merged.columns:
                df_merged[out_col] = None

            logger.info(f"Merged rows: {len(df_merged):,}")
    else:
        logger.info("No existing output file, will score all rows")
        df_merged = df_input.copy()
        df_merged[out_col] = None

    # Find rows that need scoring
    needs_scoring = df_merged[out_col].isna()
    # Also check for valid text
    has_text = df_merged[text_col].notna() & (df_merged[text_col].astype(str).str.strip() != '')
    to_score_mask = needs_scoring & has_text

    to_score_count = to_score_mask.sum()
    already_scored = (~needs_scoring).sum()

    logger.info(f"Already scored: {already_scored:,}")
    logger.info(f"Needs scoring: {to_score_count:,}")
    logger.info(f"Empty text (skipped): {(needs_scoring & ~has_text).sum():,}")

    if to_score_count == 0:
        logger.info("All rows already scored, nothing to do")
        # Still save output in case we need to update format
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        write_dataframe(df_merged, output_path)
        return

    # Get indices that need scoring
    to_score_indices = df_merged[to_score_mask].index.tolist()
    logger.info(f"Scoring {len(to_score_indices):,} rows...")

    start_time = time.time()

    if use_batch:
        # Batch mode for incremental
        df_to_score = df_merged.loc[to_score_indices]
        requests = prepare_batch_requests(df_to_score, symbol_col, text_col, model)

        if requests:
            for batch_start in range(0, len(requests), batch_size):
                batch_end = min(batch_start + batch_size, len(requests))
                batch_requests = requests[batch_start:batch_end]

                logger.info(f"Submitting batch: {batch_start}-{batch_end} of {len(requests)}")
                batch_id = submit_batch(client, batch_requests)
                results = poll_batch_results(client, batch_id, poll_interval)

                # Apply results
                for idx_str, score in results.items():
                    original_idx = int(idx_str)
                    df_merged.at[original_idx, out_col] = score

                # Checkpoint
                write_dataframe(df_merged, output_path)
                logger.info(f"Checkpoint saved after batch")
    else:
        # Real-time mode for incremental
        scored_count = 0
        for i, idx in enumerate(to_score_indices):
            row = df_merged.loc[idx]
            text = row[text_col]
            symbol = row[symbol_col]

            score = score_headline(
                client=client,
                headline=str(text)[:500],
                symbol=symbol,
                model=model,
                retry=retry,
            )

            # Extra retries if needed
            for _ in range(retry_missing):
                if score is not None:
                    break
                score = score_headline(
                    client=client,
                    headline=str(text)[:500],
                    symbol=symbol,
                    model=model,
                    retry=retry,
                )

            df_merged.at[idx, out_col] = score
            scored_count += 1
            time.sleep(pause)

            # Checkpoint every chunk_size rows
            if scored_count % chunk_size == 0:
                write_dataframe(df_merged, output_path)
                logger.info(f"Checkpoint: {scored_count}/{to_score_count} scored, {token_usage.n_calls} API calls")

            # Check runtime limit
            if max_runtime and (time.time() - start_time) >= max_runtime:
                logger.info(f"Max runtime reached after {scored_count} rows")
                break

    # Final save
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    write_dataframe(df_merged, output_path)

    final_scored = df_merged[out_col].notna().sum()
    logger.info(f"Incremental processing complete.")
    logger.info(f"Total rows: {len(df_merged):,}, Scored: {final_scored:,}")
    logger.info(f"Token usage: {token_usage.summary()}")
    logger.info(f"Estimated cost: ${token_usage.estimated_cost(model, is_batch=use_batch):.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Score sentiment for financial news using Anthropic Claude"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input file (CSV or Parquet)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output file (CSV or Parquet, adds 'sentiment_{model}' column, e.g., sentiment_sonnet)"
    )
    parser.add_argument(
        "--model", default="sonnet",
        choices=["sonnet", "haiku", "opus"],
        help="Claude model to use (default: sonnet)"
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Use Batch API (50%% cheaper, async processing up to 24h)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=10000,
        help="Requests per batch when using --batch (default: 10000)"
    )
    parser.add_argument(
        "--poll-interval", type=float, default=60.0,
        help="Seconds between batch status checks (default: 60)"
    )
    parser.add_argument(
        "--symbol-column", default="Stock_symbol",
        help="Column name for stock symbol (default: Stock_symbol)"
    )
    parser.add_argument(
        "--text-column", default="Article_title",
        help="Column name for text to score (default: Article_title). Common: title, Article_title, headline"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=1000,
        help="Rows per checkpoint in real-time mode (default: 1000)"
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Anthropic API key (default: uses ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--retry", type=int, default=3,
        help="Retry attempts per headline in real-time mode (default: 3)"
    )
    parser.add_argument(
        "--retry-missing", type=int, default=3,
        help="Extra retries for missing scores in real-time mode (default: 3)"
    )
    parser.add_argument(
        "--max-runtime", type=float, default=None,
        help="Maximum runtime in seconds (real-time mode only)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate setup without making API calls"
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Incremental mode: merge with existing output, only score rows with NULL scores"
    )
    parser.add_argument(
        "--merge-key", default=None,
        help="Column to use for merging in incremental mode (default: article_id for parquet, dedup_hash for csv)"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create client
    try:
        client = create_client(args.api_key)
        logger.info(f"Using model: {MODELS[args.model]}")
        logger.info(f"Mode: {'Batch API (50% off)' if args.batch else 'Real-time'}")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Validate input
    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run: testing single headline...")
        test_score = score_headline(
            client=client,
            headline="Apple announces record iPhone sales in Q4",
            symbol="AAPL",
            model=args.model,
        )
        logger.info(f"Test sentiment score: {test_score}")
        logger.info(f"Token usage: {token_usage.summary()}")
        logger.info(f"Estimated cost per headline: ${token_usage.estimated_cost(args.model):.6f}")
        return

    # Process based on mode
    if args.incremental:
        # Incremental mode: merge with existing output, only score NULL rows
        logger.info("Using INCREMENTAL mode (recommended for daily updates)")
        process_file_incremental(
            input_path=args.input,
            output_path=args.output,
            client=client,
            model=args.model,
            symbol_col=args.symbol_column,
            text_col=args.text_column,
            merge_key=args.merge_key,
            chunk_size=args.chunk_size,
            retry=args.retry,
            retry_missing=args.retry_missing,
            max_runtime=args.max_runtime,
            use_batch=args.batch,
            batch_size=args.batch_size,
            poll_interval=args.poll_interval,
        )
    elif args.batch:
        process_file_batch(
            input_path=args.input,
            output_path=args.output,
            client=client,
            model=args.model,
            symbol_col=args.symbol_column,
            text_col=args.text_column,
            batch_size=args.batch_size,
            poll_interval=args.poll_interval,
        )
    else:
        process_file_realtime(
            input_path=args.input,
            output_path=args.output,
            client=client,
            model=args.model,
            symbol_col=args.symbol_column,
            text_col=args.text_column,
            chunk_size=args.chunk_size,
            retry=args.retry,
            retry_missing=args.retry_missing,
            max_runtime=args.max_runtime,
        )


if __name__ == "__main__":
    main()