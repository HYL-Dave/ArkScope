#!/usr/bin/env python3
"""
Score sentiment of financial news headlines using OpenAI LLMs.
"""
import os
import argparse
import time
import json
import logging
from typing import Optional

import pandas as pd
import numpy as np
import openai

# System prompt for sentiment scoring
SYSTEM_PROMPT = """
You are a sell-side equity strategist.
For each news headline about one stock, assign an integer sentiment score:
 1 = very bearish  (likely >5 % drop)
 2 = bearish       (2–5 % drop)
 3 = neutral / not relevant
 4 = bullish       (2–5 % rise)
 5 = very bullish  (>5 % rise)
Return ONLY valid JSON: {"scores": [s1, s2, ...]}. No other keys, no explanation.
If information is insufficient, use 3.
"""

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
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=50,
            )
            text = response.choices[0].message.content.strip()
            data = json.loads(text)
            if isinstance(data, dict) and "scores" in data and isinstance(data["scores"], list):
                return data["scores"][0]
            logging.warning(f"Unexpected response format: {data}")
            return None
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
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        parser.error("OPENAI_API_KEY environment variable not set")
    openai.api_key = api_key

    def process_csv(input_csv, output_csv, model, sym_col, text_col, date_col, chunk_size, pause):
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
                val = score_headline(row[text_col], row[sym_col], model)
                chunk.at[idx, out_col] = val
                time.sleep(pause)
            # Save only date, symbol and score columns
            save_cols = ([date_col] if date_col else []) + [sym_col, out_col]
            chunk.to_csv(
                output_csv,
                mode='a',
                header=not os.path.exists(output_csv),
                index=False,
                columns=save_cols
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