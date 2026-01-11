#!/usr/bin/env python3
"""
Summarize financial news articles using OpenAI LLMs.
"""
import os
import argparse
import time
import logging
from typing import Optional, Tuple

import pandas as pd
import numpy as np
import openai
import csv
import sys
import json

# API key rotation and token limit support
API_KEYS = []
TOKENS_USED = {}
CURRENT_KEY_IDX = 0
DAILY_TOKEN_LIMIT = None
# flag to signal stopping after finishing current chunk when limit reached
STOP_AFTER_CHUNK = False
# global flag to switch to Flex mode once token limit is hit
USE_FLEX_MODE = False
# Flex mode configuration: switch to flex service_tier after daily token limit
ALLOW_FLEX = False
FLEX_TIMEOUT = 900.0
FLEX_RETRIES = 1
# global counters for token usage statistics
TOTAL_PROMPT_TOKENS = 0
TOTAL_COMPLETION_TOKENS = 0
TOTAL_TOKENS = 0
# additional stats: number of calls and max completion tokens
N_CALLS = 0
MAX_COMPLETION_TOKENS = 0

def set_api_keys(keys, daily_limit):
    global API_KEYS, TOKENS_USED, CURRENT_KEY_IDX, DAILY_TOKEN_LIMIT
    API_KEYS = keys
    TOKENS_USED = {k: 0 for k in keys}
    CURRENT_KEY_IDX = 0
    DAILY_TOKEN_LIMIT = daily_limit
    openai.api_key = API_KEYS[0]

def rotate_key_if_needed(usage):
    global CURRENT_KEY_IDX, STOP_AFTER_CHUNK, USE_FLEX_MODE
    if DAILY_TOKEN_LIMIT is not None and TOKENS_USED.get(API_KEYS[CURRENT_KEY_IDX], 0) + usage >= DAILY_TOKEN_LIMIT:
        if ALLOW_FLEX:
            logging.warning(
                f"API key {CURRENT_KEY_IDX} reached token limit ({DAILY_TOKEN_LIMIT}); switching to Flex mode"
            )
            USE_FLEX_MODE = True
        else:
            logging.warning(
                f"API key {CURRENT_KEY_IDX} reached token limit ({DAILY_TOKEN_LIMIT}); rotating key and will stop after current chunk"
            )
            STOP_AFTER_CHUNK = True
        CURRENT_KEY_IDX = (CURRENT_KEY_IDX + 1) % len(API_KEYS)
        openai.api_key = API_KEYS[CURRENT_KEY_IDX]

### System prompt for article summarization (JSON + function-calling)
SYSTEM_PROMPT = """
You are a financial news summarization assistant.
Summarize the following news article in a concise paragraph, focusing on the core facts and implications.
Respond with only the summary text in JSON format:
```json
{"summary": "<your summary>"}
```
If the article is too short or has insufficient content, still return a concise sentence describing that fact.
"""
functions = [{
    "name": "record_summary",
    "parameters": {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"]
    }
}]

def summarize_article(text: str, symbol: str, model: str,
                      reasoning_effort: str = "high", verbosity: str = "low",
                      retry: int = 3, pause: float = 0.5) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Call OpenAI ChatCompletion to summarize one article.
    Returns summary string or None on failure.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"TICKER: {symbol}\nARTICLE:\n{text}"}
    ]
    use_flex = ALLOW_FLEX and USE_FLEX_MODE
    max_attempts = FLEX_RETRIES if use_flex else retry
    for attempt in range(1, max_attempts + 1):
        try:
            if model.startswith("o"):
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "messages": messages,
                    "max_completion_tokens": 1200,
                    "functions": functions,
                    "function_call": {"name": "record_summary"},
                }
            elif model.startswith("gpt-5"):
                params = {
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "verbosity": verbosity,
                    "messages": messages,
                    "max_completion_tokens": 3600,
                    "functions": functions,
                    "function_call": {"name": "record_summary"},
                }
            else:
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 200,
                    "functions": functions,
                    "function_call": {"name": "record_summary"},
                }
            if use_flex:
                params["service_tier"] = "flex"
                params["timeout"] = FLEX_TIMEOUT

            # perform API call and record token usage
            global TOTAL_PROMPT_TOKENS, TOTAL_COMPLETION_TOKENS, TOTAL_TOKENS, N_CALLS, MAX_COMPLETION_TOKENS
            N_CALLS += 1
            response = openai.chat.completions.create(**params)
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            TOKENS_USED[API_KEYS[CURRENT_KEY_IDX]] += total_tokens
            rotate_key_if_needed(total_tokens)
            # accumulate statistics
            TOTAL_PROMPT_TOKENS += prompt_tokens
            TOTAL_COMPLETION_TOKENS += completion_tokens
            TOTAL_TOKENS += total_tokens
            MAX_COMPLETION_TOKENS = max(MAX_COMPLETION_TOKENS, completion_tokens)
            logging.info(
                f"Token usage (prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens})"
            )

            msg = response.choices[0].message
            if hasattr(msg, "function_call") and msg.function_call is not None:
                try:
                    args = json.loads(msg.function_call.arguments)
                    summary = args.get("summary")
                except Exception:
                    logging.warning(f"Cannot parse summary from function_call arguments: {msg.function_call.arguments}")
                    summary = None
            else:
                txt = msg.content.strip()
                try:
                    summary = json.loads(txt)["summary"]
                except Exception:
                    summary = txt
            if summary:
                return summary, prompt_tokens, completion_tokens
            logging.warning(f"Attempt {attempt}/{retry}: empty summary, retrying")
            time.sleep(pause * attempt)
        except Exception as e:
            logging.error(f"Attempt {attempt}/{retry} failed: {e}")
            time.sleep(pause * attempt)
    return None, None, None

def main():
    parser = argparse.ArgumentParser(
        description="Summarize financial news articles using OpenAI"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input CSV with columns: symbol, article text"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output CSV; adds summary column"
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
        "--text-column", default="Article",
        help="Name of the column for article text in input CSV (default: Article)"
    )
    parser.add_argument(
        "--summary-column", default=None,
        help="Name of the column to store summaries (default: <model>_summary)"
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
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--retry", type=int, default=3,
        help="Number of internal retry attempts on failure"
    )
    parser.add_argument(
        "--retry-missing", type=int, default=1,
        help="Number of extra attempts for rows with missing summary"
    )
    parser.add_argument(
        "--max-runtime", type=float, default=None,
        help="Maximum runtime in seconds; after exceeding, finish current chunk and stop"
    )
    parser.add_argument(
        "--reasoning-effort", default="high",
        help="Reasoning effort level for reasoning models (o3, o4-mini, etc.) - choices: low, medium, high; gpt-5 also supports minimal (default: high)"
    )
    parser.add_argument(
        "--verbosity", default="low", choices=["low", "medium", "high"],
        help="Verbosity level for reasoning models (gpt-5) (default: medium)"
    )
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

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

    # determine summary column name
    summary_col = args.summary_column or f"{args.model.replace('-', '_')}_summary"

    def process_csv(input_csv, output_csv, model, sym_col, text_col,
                    summary_col, chunk_size, pause, retry, retry_missing,
                    reasoning_effort, verbosity, max_runtime=None):
        # Ensure output directory exists
        out_dir = os.path.dirname(output_csv)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        # Resume logic: count already processed rows
        if os.path.exists(output_csv):
            prev = pd.read_csv(output_csv, usecols=[summary_col],
                               on_bad_lines='warn', engine='c')
            processed_rows = len(prev)
        else:
            processed_rows = 0

        # start timer for max-runtime enforcement
        start_time = time.time()
        reader = pd.read_csv(input_csv, chunksize=chunk_size,
                             on_bad_lines='warn', engine='c')
        for i, chunk in enumerate(reader):
            logging.info(f"Processing chunk {i}, {len(chunk)} rows")
            if i * chunk_size < processed_rows:
                continue
            # Validate required columns
            required = [sym_col, text_col]
            missing = [c for c in required if c not in chunk.columns]
            if missing:
                parser.error(f"Input CSV missing columns: {missing}")
            chunk[summary_col] = None
            # per-row token usage columns
            chunk["prompt_tokens"] = None
            chunk["completion_tokens"] = None
            # Summarize each row
            for idx, row in chunk.iterrows():
                cell = row[text_col]
                if pd.isna(cell) or not str(cell).strip():
                    logging.warning(f"Skipping empty article for {row[sym_col]}:{idx}")
                    continue
                summary, p_tokens, c_tokens = summarize_article(cell, row[sym_col], model, reasoning_effort, verbosity, retry=retry)
                for _ in range(retry_missing):
                    if summary is not None:
                        break
                    logging.warning(f"Missing summary for {row[sym_col]}:{idx}, retrying")
                    summary, p_tokens, c_tokens = summarize_article(cell, row[sym_col], model, reasoning_effort, verbosity, retry=retry)
                chunk.at[idx, summary_col] = summary
                chunk.at[idx, "prompt_tokens"] = p_tokens
                chunk.at[idx, "completion_tokens"] = c_tokens
                time.sleep(pause)
            # Append chunk to output, with escaping to avoid CSV errors
            try:
                chunk.to_csv(
                    output_csv,
                    mode='a',
                    header=not os.path.exists(output_csv),
                    index=False,
                    quoting=csv.QUOTE_MINIMAL,
                    escapechar='\\'
                )
            except Exception as e:
                logging.error(f"Failed to write chunk {i} to {output_csv}: {e}")
                sys.exit(1)
            # stop if daily token limit was reached during this chunk
            if STOP_AFTER_CHUNK:
                print(f"Daily token limit reached; stopping after chunk {i}.")
                return
            # stop if runtime exceeded max_runtime (after finishing this chunk)
            if max_runtime and (time.time() - start_time) >= max_runtime:
                print(f"Time limit reached; stopping after chunk {i}.")
                return
        print(f"Summarization completed; results saved to {output_csv}")

    # Validate reasoning_effort choices based on model
    valid_efforts = ["low", "medium", "high"]
    if args.model.startswith("gpt-5"):
        valid_efforts.append("minimal")
    
    if args.reasoning_effort not in valid_efforts:
        parser.error(f"Invalid reasoning effort '{args.reasoning_effort}' for model '{args.model}'. Valid options: {valid_efforts}")
    
    process_csv(
        args.input, args.output, args.model,
        args.symbol_column, args.text_column,
        summary_col, args.chunk_size,
        pause=0.1, retry=args.retry,
        retry_missing=args.retry_missing,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
        max_runtime=args.max_runtime,
    )
    # overall token usage summary
    logging.info(
        f"Total calls={N_CALLS}, avg prompt={TOTAL_PROMPT_TOKENS/N_CALLS:.1f}, "
        f"avg completion={TOTAL_COMPLETION_TOKENS/N_CALLS:.1f}, "
        f"avg total={TOTAL_TOKENS/N_CALLS:.1f}, max completion={MAX_COMPLETION_TOKENS}"
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()