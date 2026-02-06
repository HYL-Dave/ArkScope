#!/usr/bin/env python3
"""
migrate_to_supabase.py — Import historical data files into Supabase PostgreSQL.

Usage:
    python scripts/migrate_to_supabase.py              # Import all data types
    python scripts/migrate_to_supabase.py --news       # News articles only
    python scripts/migrate_to_supabase.py --scores     # News scores only (multi-model)
    python scripts/migrate_to_supabase.py --prices     # Prices only
    python scripts/migrate_to_supabase.py --iv         # IV history only
    python scripts/migrate_to_supabase.py --fundamentals  # Fundamentals only
    python scripts/migrate_to_supabase.py --dry-run    # Count rows without importing

The --scores flag imports multi-model scores into the news_scores table.
It auto-detects score columns (sentiment_haiku, risk_gpt_5_2_xhigh, etc.)
from parquet/CSV files and upserts them incrementally.

Reads SUPABASE_DB_URL from config/.env.
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BATCH_SIZE = 1000


def load_db_url() -> str:
    """Load SUPABASE_DB_URL from config/.env."""
    env_path = PROJECT_ROOT / "config" / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"config/.env not found at {env_path}")

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SUPABASE_DB_URL=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and val.startswith("postgresql"):
                    return val
    raise ValueError("SUPABASE_DB_URL not found or empty in config/.env")


def get_connection(db_url: str) -> psycopg2.extensions.connection:
    """Create a database connection."""
    conn = psycopg2.connect(db_url, sslmode="require", connect_timeout=15)
    conn.autocommit = False
    return conn


def article_hash(ticker: str, title: str, date_str: str) -> str:
    """Generate a dedup hash for a news article."""
    raw = f"{ticker}|{title}|{date_str}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:64]


def safe_str(val) -> str | None:
    """Convert to string, handling NaN."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    return str(val)


def safe_int(val) -> int | None:
    """Convert to int, handling NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        if pd.isna(f):
            return None
        return int(f)
    except (ValueError, TypeError):
        return None


def safe_float(val) -> float | None:
    """Convert to float, handling NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


# =============================================================================
# News Import
# =============================================================================

def import_news(conn: psycopg2.extensions.connection, dry_run: bool = False):
    """Import scored news from IBKR and Polygon files."""
    news_dir = PROJECT_ROOT / "data" / "news"
    total_imported = 0

    # --- IBKR News ---
    ibkr_path = news_dir / "ibkr_scored_final.parquet"
    if ibkr_path.exists():
        logger.info(f"Loading IBKR news from {ibkr_path}")
        df = pd.read_parquet(ibkr_path)
        logger.info(f"  Loaded {len(df)} rows")

        if dry_run:
            logger.info(f"  [DRY RUN] Would import {len(df)} IBKR news rows")
        else:
            rows = []
            for _, r in df.iterrows():
                date_str = pd.to_datetime(r.get("published_at"), errors="coerce")
                date_str = date_str.isoformat() if pd.notna(date_str) else None
                if date_str is None:
                    continue
                ticker = str(r.get("ticker", ""))
                title = str(r.get("title", ""))
                rows.append((
                    ticker,
                    title,
                    safe_str(r.get("description")),
                    safe_str(r.get("url")),
                    safe_str(r.get("publisher")),
                    "ibkr",
                    date_str,
                    safe_int(r.get("sentiment_haiku")),
                    safe_int(r.get("risk_haiku")),
                    "haiku",
                    article_hash(ticker, title, date_str[:10]),
                ))

            count = _insert_news_batch(conn, rows)
            total_imported += count
            logger.info(f"  Imported {count}/{len(rows)} IBKR news rows")

    # --- Polygon News ---
    polygon_path = news_dir / "polygon_scored_final.csv"
    if polygon_path.exists():
        logger.info(f"Loading Polygon news from {polygon_path}")
        df = pd.read_csv(polygon_path)
        logger.info(f"  Loaded {len(df)} rows")

        if dry_run:
            logger.info(f"  [DRY RUN] Would import {len(df)} Polygon news rows")
        else:
            rows = []
            for _, r in df.iterrows():
                date_str = pd.to_datetime(r.get("published_at"), errors="coerce")
                date_str = date_str.isoformat() if pd.notna(date_str) else None
                if date_str is None:
                    continue
                ticker = str(r.get("Stock_symbol", ""))
                title = str(r.get("Article_title", ""))
                rows.append((
                    ticker,
                    title,
                    safe_str(r.get("description")),
                    safe_str(r.get("url")),
                    safe_str(r.get("publisher")),
                    "polygon",
                    date_str,
                    safe_int(r.get("sentiment_haiku")),
                    safe_int(r.get("risk_haiku")),
                    "haiku",
                    article_hash(ticker, title, date_str[:10]),
                ))

            count = _insert_news_batch(conn, rows)
            total_imported += count
            logger.info(f"  Imported {count}/{len(rows)} Polygon news rows")

    logger.info(f"News import complete: {total_imported} total rows")
    return total_imported


def _insert_news_batch(conn, rows: list) -> int:
    """Batch insert news rows with ON CONFLICT DO NOTHING."""
    sql = """
        INSERT INTO news (
            ticker, title, description, url, publisher, source,
            published_at, sentiment_score, risk_score, scored_model, article_hash
        ) VALUES %s
        ON CONFLICT (article_hash) DO NOTHING
    """
    inserted = 0
    cur = conn.cursor()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            psycopg2.extras.execute_values(cur, sql, batch, page_size=BATCH_SIZE)
            conn.commit()
            inserted += len(batch)
            if (i // BATCH_SIZE) % 20 == 0:
                logger.info(f"    Progress: {inserted}/{len(rows)} rows")
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"    Batch error at {i}: {e}")
    cur.close()
    return inserted


# =============================================================================
# News Scores Import (multi-model)
# =============================================================================

# Pattern to detect score columns: sentiment_haiku, risk_gpt_5_2_xhigh, etc.
SCORE_COLUMN_PATTERN = re.compile(
    r"^(sentiment|risk)_(.+?)(?:_(none|minimal|low|medium|high|xhigh))?$"
)

# Known non-model suffixes to exclude from detection (e.g. 'score' from 'sentiment_score')
_NON_MODEL_SUFFIXES = {"score"}


def detect_score_columns(df: pd.DataFrame) -> list[tuple[str, str, str | None, str]]:
    """Auto-detect score columns from a DataFrame.

    Returns list of (score_type, model, reasoning_effort, column_name).
    Example: [('sentiment', 'gpt_5_2', 'xhigh', 'sentiment_gpt_5_2_xhigh'),
              ('risk', 'haiku', None, 'risk_haiku')]
    """
    results = []
    for col in df.columns:
        m = SCORE_COLUMN_PATTERN.match(col)
        if m:
            model = m.group(2)
            if model in _NON_MODEL_SUFFIXES:
                continue
            score_type = m.group(1)
            effort = m.group(3)  # None for legacy columns like sentiment_haiku
            results.append((score_type, model, effort, col))
    return results


def load_article_hash_map(conn) -> dict[str, int]:
    """Load article_hash → news.id mapping from the database."""
    cur = conn.cursor()
    cur.execute("SELECT article_hash, id FROM news")
    result = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    logger.info(f"  Loaded {len(result)} article hashes from DB")
    return result


def _upsert_scores_batch(conn, rows: list) -> int:
    """Batch upsert score rows into news_scores.

    Each row is (news_id, score_type, model, reasoning_effort, score).
    Uses ON CONFLICT DO UPDATE to allow score corrections.
    """
    sql = """
        INSERT INTO news_scores (news_id, score_type, model, reasoning_effort, score)
        VALUES %s
        ON CONFLICT (news_id, score_type, model, reasoning_effort)
        DO UPDATE SET score = EXCLUDED.score, scored_at = NOW()
    """
    inserted = 0
    cur = conn.cursor()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            psycopg2.extras.execute_values(cur, sql, batch, page_size=BATCH_SIZE)
            conn.commit()
            inserted += len(batch)
            if (i // BATCH_SIZE) % 20 == 0 and i > 0:
                logger.info(f"    Progress: {inserted}/{len(rows)} score rows")
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"    Score batch error at {i}: {e}")
    cur.close()
    return inserted


def import_news_scores(conn: psycopg2.extensions.connection, dry_run: bool = False):
    """Import multi-model news scores into news_scores table.

    Scans scored files for all {sentiment|risk}_{model}_{effort} columns,
    resolves article_hash to news_id, and upserts scores.
    """
    news_dir = PROJECT_ROOT / "data" / "news"
    total_imported = 0

    # Load hash → id mapping once
    if not dry_run:
        hash_to_id = load_article_hash_map(conn)
    else:
        hash_to_id = {}

    # --- IBKR scored file ---
    ibkr_path = news_dir / "ibkr_scored_final.parquet"
    if ibkr_path.exists():
        logger.info(f"Scanning IBKR scores from {ibkr_path}")
        df = pd.read_parquet(ibkr_path)
        score_cols = detect_score_columns(df)
        logger.info(f"  Found {len(score_cols)} score columns: {[c[3] for c in score_cols]}")

        if dry_run:
            for st, model, effort, col in score_cols:
                non_null = df[col].notna().sum()
                logger.info(f"  [DRY RUN] {col}: {non_null} non-null scores")
        else:
            count = _import_scores_from_df(
                conn, df, score_cols, hash_to_id,
                ticker_col="ticker", title_col="title", date_col="published_at",
            )
            total_imported += count
            logger.info(f"  Imported {count} IBKR score rows")

    # --- Polygon scored file ---
    polygon_path = news_dir / "polygon_scored_final.csv"
    if polygon_path.exists():
        logger.info(f"Scanning Polygon scores from {polygon_path}")
        df = pd.read_csv(polygon_path)
        score_cols = detect_score_columns(df)
        logger.info(f"  Found {len(score_cols)} score columns: {[c[3] for c in score_cols]}")

        if dry_run:
            for st, model, effort, col in score_cols:
                non_null = df[col].notna().sum()
                logger.info(f"  [DRY RUN] {col}: {non_null} non-null scores")
        else:
            count = _import_scores_from_df(
                conn, df, score_cols, hash_to_id,
                ticker_col="Stock_symbol", title_col="Article_title",
                date_col="published_at",
            )
            total_imported += count
            logger.info(f"  Imported {count} Polygon score rows")

    # --- Raw scored parquets (e.g. data/news/raw/polygon/*.parquet) ---
    raw_polygon_dir = news_dir / "raw" / "polygon"
    if raw_polygon_dir.exists():
        parquet_files = sorted(raw_polygon_dir.glob("*.parquet"))
        if parquet_files:
            logger.info(f"Scanning {len(parquet_files)} raw Polygon parquets")
            for pf in parquet_files:
                df = pd.read_parquet(pf)
                score_cols = detect_score_columns(df)
                if not score_cols:
                    continue
                logger.info(f"  {pf.name}: {len(score_cols)} score cols")

                if dry_run:
                    for st, model, effort, col in score_cols:
                        non_null = df[col].notna().sum()
                        logger.info(f"    [DRY RUN] {col}: {non_null}")
                else:
                    # Determine column names (raw files may have different names)
                    ticker_col = "Stock_symbol" if "Stock_symbol" in df.columns else "ticker"
                    title_col = "Article_title" if "Article_title" in df.columns else "title"
                    count = _import_scores_from_df(
                        conn, df, score_cols, hash_to_id,
                        ticker_col=ticker_col, title_col=title_col,
                        date_col="published_at",
                    )
                    total_imported += count

    logger.info(f"News scores import complete: {total_imported} total score rows")
    return total_imported


def _import_scores_from_df(
    conn,
    df: pd.DataFrame,
    score_cols: list[tuple],
    hash_to_id: dict[str, int],
    ticker_col: str = "ticker",
    title_col: str = "title",
    date_col: str = "published_at",
) -> int:
    """Extract scores from a DataFrame and upsert into news_scores."""
    total = 0
    for score_type, model, effort, col_name in score_cols:
        rows = []
        for _, r in df.iterrows():
            score = safe_int(r.get(col_name))
            if score is None:
                continue
            ticker = str(r.get(ticker_col, ""))
            title = str(r.get(title_col, ""))
            date_str = pd.to_datetime(r.get(date_col), errors="coerce")
            if pd.isna(date_str):
                continue
            h = article_hash(ticker, title, date_str.strftime("%Y-%m-%d"))
            news_id = hash_to_id.get(h)
            if news_id is None:
                continue
            rows.append((news_id, score_type, model, effort, score))

        if rows:
            count = _upsert_scores_batch(conn, rows)
            total += count
            logger.info(f"    {col_name}: upserted {count}/{len(rows)} rows")
    return total


# =============================================================================
# Prices Import
# =============================================================================

def import_prices(conn: psycopg2.extensions.connection, dry_run: bool = False):
    """Import 15min price data from CSV files."""
    prices_dir = PROJECT_ROOT / "data" / "prices" / "15min"
    if not prices_dir.exists():
        logger.warning(f"Prices directory not found: {prices_dir}")
        return 0

    csv_files = sorted(prices_dir.glob("*.csv"))
    logger.info(f"Found {len(csv_files)} price files in {prices_dir}")

    total_imported = 0
    for fi, csv_path in enumerate(csv_files):
        # Extract ticker from filename: NVDA_15min_2024_2026.csv -> NVDA
        ticker = csv_path.stem.split("_")[0].upper()

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.warning(f"  Error reading {csv_path.name}: {e}")
            continue

        if dry_run:
            logger.info(f"  [{fi+1}/{len(csv_files)}] {csv_path.name}: {len(df)} rows [DRY RUN]")
            continue

        rows = []
        for _, r in df.iterrows():
            dt = pd.to_datetime(r.get("datetime"), errors="coerce")
            if pd.isna(dt):
                continue
            rows.append((
                ticker,
                dt.isoformat(),
                "15min",
                safe_float(r.get("open")),
                safe_float(r.get("high")),
                safe_float(r.get("low")),
                safe_float(r.get("close")),
                safe_int(r.get("volume")),
            ))

        count = _insert_prices_batch(conn, rows)
        total_imported += count

        if (fi + 1) % 20 == 0 or fi == len(csv_files) - 1:
            logger.info(
                f"  [{fi+1}/{len(csv_files)}] {ticker}: {count} rows "
                f"(total: {total_imported})"
            )

    logger.info(f"Prices import complete: {total_imported} total rows")
    return total_imported


def _insert_prices_batch(conn, rows: list) -> int:
    """Batch insert price rows with ON CONFLICT DO NOTHING."""
    sql = """
        INSERT INTO prices (ticker, datetime, interval, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (ticker, datetime, interval) DO NOTHING
    """
    inserted = 0
    cur = conn.cursor()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            psycopg2.extras.execute_values(cur, sql, batch, page_size=BATCH_SIZE)
            conn.commit()
            inserted += len(batch)
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"    Price batch error at {i}: {e}")
    cur.close()
    return inserted


# =============================================================================
# IV History Import
# =============================================================================

def import_iv_history(conn: psycopg2.extensions.connection, dry_run: bool = False):
    """Import IV history from Parquet files."""
    iv_dir = PROJECT_ROOT / "data" / "options" / "iv_history"
    if not iv_dir.exists():
        logger.warning(f"IV history directory not found: {iv_dir}")
        return 0

    parquet_files = sorted(iv_dir.glob("*.parquet"))
    logger.info(f"Found {len(parquet_files)} IV history files")

    total_imported = 0
    for pf in parquet_files:
        ticker = pf.stem.upper()
        df = pd.read_parquet(pf)
        logger.info(f"  {ticker}: {len(df)} rows")

        if dry_run:
            continue

        rows = []
        for _, r in df.iterrows():
            date_val = str(r.get("date", ""))
            rows.append((
                ticker,
                date_val,
                safe_float(r.get("atm_iv")),
                safe_float(r.get("hv_30d")),
                safe_float(r.get("vrp")),
                safe_float(r.get("spot_price")),
                safe_int(r.get("num_quotes")),
            ))

        count = _insert_iv_batch(conn, rows)
        total_imported += count
        logger.info(f"  Imported {count} IV rows for {ticker}")

    logger.info(f"IV history import complete: {total_imported} total rows")
    return total_imported


def _insert_iv_batch(conn, rows: list) -> int:
    """Batch insert IV history rows."""
    sql = """
        INSERT INTO iv_history (ticker, date, atm_iv, hv_30d, vrp, spot_price, num_quotes)
        VALUES %s
        ON CONFLICT (ticker, date) DO NOTHING
    """
    inserted = 0
    cur = conn.cursor()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            psycopg2.extras.execute_values(cur, sql, batch, page_size=BATCH_SIZE)
            conn.commit()
            inserted += len(batch)
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"    IV batch error at {i}: {e}")
    cur.close()
    return inserted


# =============================================================================
# Fundamentals Import
# =============================================================================

def import_fundamentals(conn: psycopg2.extensions.connection, dry_run: bool = False):
    """Import fundamentals from IBKR JSON files."""
    fund_dir = PROJECT_ROOT / "data_lake" / "raw" / "ibkr_fundamentals"
    if not fund_dir.exists():
        logger.warning(f"Fundamentals directory not found: {fund_dir}")
        return 0

    json_files = sorted(fund_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} fundamental files")

    if dry_run:
        logger.info(f"  [DRY RUN] Would import {len(json_files)} fundamentals")
        return 0

    total_imported = 0
    cur = conn.cursor()
    for jf in json_files:
        # Extract ticker from filename: AAPL_fundamentals_20250101.json -> AAPL
        ticker = jf.stem.split("_")[0].upper()
        try:
            with open(jf) as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"  Error reading {jf.name}: {e}")
            continue

        collected_at = data.get("collected_at", "")[:10]
        if not collected_at:
            collected_at = "2025-01-01"  # fallback

        try:
            cur.execute(
                """
                INSERT INTO fundamentals (ticker, snapshot_date, data)
                VALUES (%s, %s, %s)
                ON CONFLICT (ticker, snapshot_date) DO UPDATE SET data = EXCLUDED.data
                """,
                (ticker, collected_at, json.dumps(data)),
            )
            conn.commit()
            total_imported += 1
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"  Error importing {jf.name}: {e}")

    cur.close()
    logger.info(f"Fundamentals import complete: {total_imported} total rows")
    return total_imported


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Import data into Supabase")
    parser.add_argument("--news", action="store_true", help="Import news articles only")
    parser.add_argument("--scores", action="store_true", help="Import news scores to news_scores table (multi-model)")
    parser.add_argument("--prices", action="store_true", help="Import prices only")
    parser.add_argument("--iv", action="store_true", help="Import IV history only")
    parser.add_argument("--fundamentals", action="store_true", help="Import fundamentals only")
    parser.add_argument("--dry-run", action="store_true", help="Count rows without importing")
    args = parser.parse_args()

    # If no specific flag, import all
    import_all = not (args.news or args.scores or args.prices or args.iv or args.fundamentals)

    try:
        db_url = load_db_url()
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info("Connecting to Supabase...")
    conn = get_connection(db_url)
    logger.info("Connected")

    start = time.time()
    totals = {}

    try:
        if import_all or args.news:
            totals["news"] = import_news(conn, dry_run=args.dry_run)

        if import_all or args.scores:
            totals["news_scores"] = import_news_scores(conn, dry_run=args.dry_run)

        if import_all or args.iv:
            totals["iv_history"] = import_iv_history(conn, dry_run=args.dry_run)

        if import_all or args.fundamentals:
            totals["fundamentals"] = import_fundamentals(conn, dry_run=args.dry_run)

        if import_all or args.prices:
            totals["prices"] = import_prices(conn, dry_run=args.dry_run)

    finally:
        conn.close()

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"Migration complete in {elapsed:.1f}s")
    for table, count in totals.items():
        logger.info(f"  {table}: {count} rows")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()