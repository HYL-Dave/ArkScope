#!/usr/bin/env python3
"""
Score sentiment of financial news headlines using OpenAI LLMs.
"""
import os
import argparse
import time
import logging
from typing import Optional
import json
import re

import pandas as pd
import numpy as np
import openai

# API key rotation and token limit support
API_KEYS = []
TOKENS_USED = {}
CURRENT_KEY_IDX = 0
DAILY_TOKEN_LIMIT = None

def set_api_keys(keys, daily_limit):
    global API_KEYS, TOKENS_USED, CURRENT_KEY_IDX, DAILY_TOKEN_LIMIT
    API_KEYS = keys
    TOKENS_USED = {k: 0 for k in keys}
    CURRENT_KEY_IDX = 0
    DAILY_TOKEN_LIMIT = daily_limit
    openai.api_key = API_KEYS[0]

def rotate_key_if_needed(usage):
    global CURRENT_KEY_IDX
    if DAILY_TOKEN_LIMIT and TOKENS_USED.get(API_KEYS[CURRENT_KEY_IDX], 0) + usage >= DAILY_TOKEN_LIMIT:
        logging.warning(
            f"API key {CURRENT_KEY_IDX} reached token limit ({DAILY_TOKEN_LIMIT}), rotating key"
        )
        CURRENT_KEY_IDX = (CURRENT_KEY_IDX + 1) % len(API_KEYS)
        openai.api_key = API_KEYS[CURRENT_KEY_IDX]

# System prompt for sentiment scoring
SYSTEM_PROMPT = """
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
functions=[{
  "name":"record_score",
  "parameters":{
     "type":"object",
     "properties":{"score":{"type":"integer","minimum":1,"maximum":5}},
     "required":["score"]
  }
}]

def score_headline(headline: str, symbol: str, model: str, retry: int = 3, pause: float = 0.5) -> Optional[int]:
    """
    Call OpenAI ChatCompletion to score one headline.
    Returns integer score or None on failure.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"TICKER: {symbol}\nHEADLINES:\n1. {headline}"}
    ]
    for attempt in range(1, retry + 1):
        try:
            # Use function-calling for o3 models; fallback to simple JSON/text parsing for others
            if model.startswith("o"):
                response = openai.chat.completions.create(
                    model=model,
                    reasoning_effort="high",
                    messages=messages,
                    max_completion_tokens=600,
                    functions=functions,
                    function_call={"name": "record_score"}
                )
            else:
                response = openai.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=2,
                )
            # track token usage and rotate key if needed
            usage = response.usage.total_tokens
            TOKENS_USED[API_KEYS[CURRENT_KEY_IDX]] += usage
            rotate_key_if_needed(usage)

            # text = response.choices[0].message.content.strip()
            # # Parse single integer score from model response
            # try:
            #     return int(text.split()[0])
            # except Exception:
            #     logging.warning(f"Cannot parse integer score from response: {text}")
            #     return None
            msg = response.choices[0].message
            # parse score from function_call arguments or JSON/text content
            if hasattr(msg, "function_call") and msg.function_call is not None:
                try:
                    args = json.loads(msg.function_call.arguments)
                    score = int(args.get("score"))
                except Exception:
                    logging.warning(
                        f"Cannot parse score from function_call arguments: {msg.function_call.arguments}"
                    )
                    score = None
            else:
                txt = msg.content.strip()
                try:
                    score = json.loads(txt)["score"]
                except Exception:
                    m = re.search(r"\b([1-5])\b", txt)
                    score = int(m.group(1)) if m else None
            # retry on parsing failure
            if score is not None:
                return score
            logging.warning(
                f"Attempt {attempt}/{retry}: no valid score parsed (got: '{msg.content.strip()}'), retrying"
            )
            time.sleep(pause * attempt)
        except Exception as e:
            logging.error(f"Attempt {attempt}/{retry} failed: {e}")
            time.sleep(pause * attempt)
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Score sentiment for financial news headlines using OpenAI"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input CSV with columns: symbol, headline"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output CSV; adds 'sentiment_deepseek' column"
    )
    parser.add_argument(
        "--model", default="o4-mini",
        help="OpenAI model name (e.g., o4-mini, gpt-4.1, o3)"
    )
    parser.add_argument(
        "--symbol-column", default="symbol",
        help="Name of the column for stock symbol in input CSV"
    )
    parser.add_argument(
        "--text-column", default="headline",
        help="Name of the column for text/summary in input CSV"
    )
    parser.add_argument(
        "--date-column", default=None,
        help="Name of the column for date in input CSV (optional)"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=1000,
        help="Number of rows to process at a time (for resumable processing)"
    )
    parser.add_argument(
        "--api-key", default=None,
        help="OpenAI API key; if not set, uses OPENAI_API_KEY env var or --api-keys-file"
    )
    parser.add_argument(
        "--api-keys-file", default=None,
        help="Path to file with one OpenAI API key per line; keys are rotated upon reaching token limit"
    )
    parser.add_argument(
        "--daily-token-limit", type=int, default=None,
        help="Token limit per API key per run (approximate); keys rotate upon reaching this limit"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging of each request and chunk processing"
    )
    parser.add_argument(
        "--retry-missing", type=int, default=3,
        help="Number of extra attempts for rows with missing sentiment score"
    )
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # setup API keys and token limits
    keys = []
    if args.api_keys_file:
        with open(args.api_keys_file) as f:
            keys = [l.strip() for l in f if l.strip()]
    elif args.api_key:
        keys = [args.api_key]
    else:
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            keys = [env_key]
    if not keys:
        parser.error("No OpenAI API key provided; set --api-key, --api-keys-file, or OPENAI_API_KEY env var")
    set_api_keys(keys, args.daily_token_limit)

    def process_csv(input_csv, output_csv, model, sym_col, text_col, date_col,
                    chunk_size, pause, retry_missing):
        # Ensure output directory exists for chunked writes
        out_dir = os.path.dirname(output_csv)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        # Resume logic: count already processed rows
        if os.path.exists(output_csv):
            prev = pd.read_csv(output_csv, usecols=[date_col] if date_col else [],
                               on_bad_lines='warn', engine='python')
            processed_rows = len(prev)
        else:
            processed_rows = 0

        reader = pd.read_csv(input_csv, chunksize=chunk_size,
                             on_bad_lines='warn', engine='python')
        out_col = "sentiment_deepseek"
        for i, chunk in enumerate(reader):
            logging.info(f"Processing chunk {i}, {len(chunk)} rows")
            if i * chunk_size < processed_rows:
                continue
            # Validate required columns
            required = [sym_col, text_col] + ([date_col] if date_col else [])
            missing = [c for c in required if c and c not in chunk.columns]
            if missing:
                parser.error(f"Input CSV missing columns: {missing}")
            # Initialize output column
            chunk[out_col] = np.nan
            # Score each row
            for idx, row in chunk.iterrows():
                snippet = str(row[text_col])[:200]
                logging.debug(f"Requesting score for {row[sym_col]}: {snippet}")
                # initial inference
                val = score_headline(row[text_col], row[sym_col], model)
                # extra retries if missing
                for _ in range(retry_missing):
                    if val is not None:
                        break
                    logging.warning(
                        f"Missing sentiment for {row[sym_col]}:{idx}, retrying"
                    )
                    val = score_headline(row[text_col], row[sym_col], model)
                chunk.at[idx, out_col] = val
                time.sleep(pause)
            # Write all original columns plus new sentiment score
            chunk.to_csv(
                output_csv,
                mode='a',
                header=not os.path.exists(output_csv),
                index=False
            )
        print(f"Scoring completed; results saved to {output_csv}")

    process_csv(
        args.input, args.output, args.model,
        args.symbol_column, args.text_column, args.date_column,
        args.chunk_size, pause=0.1, retry_missing=args.retry_missing,
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()