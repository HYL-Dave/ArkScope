#!/usr/bin/env python3
"""
Score downside risk of financial news headlines using OpenAI LLMs.
"""
import os
import argparse
import time
import logging
from typing import Optional

import pandas as pd
import numpy as np
import openai
import json
import re

# API key rotation and token limit support
API_KEYS = []
TOKENS_USED = {}
CURRENT_KEY_IDX = 0
DAILY_TOKEN_LIMIT = None

# Flex mode configuration: switch to flex service_tier after daily token limit
ALLOW_FLEX = False
FLEX_TIMEOUT = 900.0
FLEX_RETRIES = 1

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

### System prompt for risk scoring (JSON + function-calling)
SYSTEM_PROMPT = """
You are a financial risk officer.
Score each headline for downside risk of holding the stock:
 1 = very low risk
 2 = low risk
 3 = moderate / unknown
 4 = high risk
 5 = very high / catastrophic risk
Respond with only the integer risk score (1–5) in JSON format:
```json
{"score": <integer>}
```
Use {"score": 3} when risk cannot be inferred.
"""
functions = [{
    "name": "record_score",
    "parameters": {
        "type": "object",
        "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5}},
        "required": ["score"]
    }
}]

def score_headline(headline: str, symbol: str, model: str, retry: int = 3, pause: float = 0.5) -> Optional[int]:
    """
    Call OpenAI ChatCompletion to score one headline for risk.
    Returns integer risk or None on failure.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"TICKER: {symbol}\nHEADLINES:\n1. {headline}"}
    ]
    use_flex = ALLOW_FLEX and TOKENS_USED.get(API_KEYS[CURRENT_KEY_IDX], 0) >= DAILY_TOKEN_LIMIT if DAILY_TOKEN_LIMIT else False
    max_attempts = FLEX_RETRIES if use_flex else retry
    for attempt in range(1, max_attempts + 1):
        try:
            if model.startswith("o"):
                params = {
                    "model": model,
                    "messages": messages,
                    "max_completion_tokens": 50,
                    "functions": functions,
                    "function_call": {"name": "record_score"},
                }
            else:
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 2,
                }
            if use_flex:
                params["service_tier"] = "flex"
                params["timeout"] = FLEX_TIMEOUT

            response = openai.chat.completions.create(**params)
            usage = response.usage.total_tokens
            TOKENS_USED[API_KEYS[CURRENT_KEY_IDX]] += usage
            rotate_key_if_needed(usage)

            msg = response.choices[0].message
            if hasattr(msg, "function_call") and msg.function_call is not None:
                try:
                    args = json.loads(msg.function_call.arguments)
                    score = int(args.get("score"))
                except Exception:
                    logging.warning(
                        f"Cannot parse risk score from function_call arguments: {msg.function_call.arguments}"
                    )
                    score = None
            else:
                txt = msg.content.strip()
                try:
                    score = json.loads(txt)["score"]
                except Exception:
                    m = re.search(r"\b([1-5])\b", txt)
                    score = int(m.group(1)) if m else None
            if score is not None:
                return score
            logging.warning(
                f"Attempt {attempt}/{retry}: no valid risk score parsed (got: '{txt}'), retrying"
            )
            time.sleep(pause * attempt)
        except Exception as e:
            logging.error(f"Attempt {attempt}/{retry} failed: {e}")
            time.sleep(pause * attempt)
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Score downside risk for financial news headlines using OpenAI"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input CSV with columns: symbol, headline"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output CSV; adds 'risk_deepseek' column"
    )
    parser.add_argument(
        "--model", default="o4-mini",
        help="OpenAI model name (e.g., o4-mini, gpt-4.1, o3)"
    )
    parser.add_argument(
        "--symbol-column", default="Stock_symbol",
        help="Name of the column for stock symbol in input CSV (default: Stock_symbol)"
    )
    parser.add_argument(
        "--text-column", default="Article_title",
        choices=[
            "Article_title", "Article", "Lsa_summary",
            "Luhn_summary", "Textrank_summary", "Lexrank_summary",
        ],
        help=(
            "Name of the column for text/summary in input CSV; one of "
            "Article_title, Article, Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary "
            "(default: Article_title)"
        )
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
        "--allow-flex", action="store_true",
        help="After daily token limit, continue calls in service_tier='flex' mode"
    )
    parser.add_argument(
        "--flex-timeout", type=float, default=900.0,
        help="Timeout in seconds for Flex service calls (e.g. 900s)"
    )
    parser.add_argument(
        "--flex-retries", type=int, default=1,
        help="Number of retries when running in Flex mode (default=1)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging of each request and chunk processing"
    )
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Flex mode parameters
    global ALLOW_FLEX, FLEX_TIMEOUT, FLEX_RETRIES
    ALLOW_FLEX = args.allow_flex
    FLEX_TIMEOUT = args.flex_timeout
    FLEX_RETRIES = args.flex_retries

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

    def process_csv(input_csv, output_csv, model, sym_col, text_col, date_col, chunk_size, pause):
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
        out_col = "risk_deepseek"
        for i, chunk in enumerate(reader):
            logging.info(f"Processing chunk {i}, {len(chunk)} rows")
            if i * chunk_size < processed_rows:
                continue
            # Validate required columns
            required = [sym_col, text_col] + ([date_col] if date_col else [])
            missing = [c for c in required if c and c not in chunk.columns]
            if missing:
                parser.error(f"Input CSV missing columns: {missing}")
            chunk[out_col] = None
            # Score each row
            for idx, row in chunk.iterrows():
                cell = row[text_col]
                if pd.isna(cell) or not str(cell).strip():
                    logging.warning(f"Skipping empty text for {row[sym_col]}:{idx}")
                    continue
                snippet = str(cell)[:200]
                logging.debug(f"Requesting risk for {row[sym_col]}: {snippet}")
                val = score_headline(cell, row[sym_col], model)
                chunk.at[idx, out_col] = val
                time.sleep(pause)
            # Write all original columns plus new risk score
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
        args.chunk_size, pause=0.1,
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()