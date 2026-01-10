"""
News Data Loader

Handles loading and caching of news data from Polygon, Finnhub, and IBKR sources.
Optimized for Streamlit with @st.cache_data support.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import html
import re


# Default data directory
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "news" / "raw"


def clean_html_content(content: str) -> str:
    """Clean HTML content for display."""
    if not content or pd.isna(content):
        return ""

    # Decode HTML entities
    content = html.unescape(content)

    # Replace &#10; with newlines
    content = content.replace("&#10;", "\n")

    return content


def strip_html_tags(content: str) -> str:
    """Remove HTML tags for plain text display."""
    if not content or pd.isna(content):
        return ""

    content = clean_html_content(content)
    # Remove HTML tags
    content = re.sub(r'<[^>]+>', '', content)
    # Clean up whitespace
    content = re.sub(r'\s+', ' ', content).strip()

    return content


def load_source_data(
    source: str,
    data_dir: Path = DEFAULT_DATA_DIR,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load news data from a single source.

    Args:
        source: One of 'polygon', 'finnhub', 'ibkr'
        data_dir: Base directory containing raw news data
        date_from: Optional start date filter (YYYY-MM-DD)
        date_to: Optional end date filter (YYYY-MM-DD)

    Returns:
        DataFrame with news articles
    """
    source_dir = data_dir / source

    if not source_dir.exists():
        return pd.DataFrame()

    # Find all parquet files
    parquet_files = list(source_dir.rglob("*.parquet"))

    if not parquet_files:
        return pd.DataFrame()

    # Load and concatenate all files
    dfs = []
    for f in parquet_files:
        try:
            df = pd.read_parquet(f, engine='pyarrow')
            dfs.append(df)
        except Exception as e:
            print(f"Error loading {f}: {e}")
            continue

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    # Ensure source_api column exists
    if 'source_api' not in df.columns:
        df['source_api'] = source

    # Parse dates and normalize to naive datetime (strip timezone)
    df['published_date'] = pd.to_datetime(df['published_at'], errors='coerce')
    if df['published_date'].dt.tz is not None:
        df['published_date'] = df['published_date'].dt.tz_convert(None)

    # Apply date filters
    if date_from:
        df = df[df['published_date'] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df['published_date'] <= pd.to_datetime(date_to)]

    return df


def load_all_sources(
    data_dir: Path = DEFAULT_DATA_DIR,
    sources: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load news data from all sources.

    Args:
        data_dir: Base directory containing raw news data
        sources: List of sources to load (default: all)
        date_from: Optional start date filter
        date_to: Optional end date filter

    Returns:
        Combined DataFrame with all news articles
    """
    if sources is None:
        sources = ['polygon', 'finnhub', 'ibkr']

    all_dfs = []
    for source in sources:
        df = load_source_data(source, data_dir, date_from, date_to)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)


def get_data_summary(data_dir: Path = DEFAULT_DATA_DIR) -> Dict:
    """
    Get summary statistics for all news sources.

    Returns:
        Dict with summary statistics per source
    """
    summary = {}

    for source in ['polygon', 'finnhub', 'ibkr']:
        source_dir = data_dir / source

        if not source_dir.exists():
            summary[source] = {
                'total_articles': 0,
                'date_range': (None, None),
                'publishers': [],
                'file_count': 0,
            }
            continue

        parquet_files = list(source_dir.rglob("*.parquet"))

        if not parquet_files:
            summary[source] = {
                'total_articles': 0,
                'date_range': (None, None),
                'publishers': [],
                'file_count': 0,
            }
            continue

        total_articles = 0
        min_date = None
        max_date = None
        publishers = set()

        for f in parquet_files:
            try:
                df = pd.read_parquet(f, engine='pyarrow')
                total_articles += len(df)

                if 'publisher' in df.columns:
                    publishers.update(df['publisher'].dropna().unique())

                if 'published_at' in df.columns:
                    dates = pd.to_datetime(df['published_at'], errors='coerce')
                    dates = dates.dropna()
                    if not dates.empty:
                        file_min = dates.min()
                        file_max = dates.max()
                        if min_date is None or file_min < min_date:
                            min_date = file_min
                        if max_date is None or file_max > max_date:
                            max_date = file_max
            except Exception as e:
                print(f"Error reading {f}: {e}")
                continue

        summary[source] = {
            'total_articles': total_articles,
            'date_range': (
                min_date.strftime('%Y-%m-%d') if min_date else None,
                max_date.strftime('%Y-%m-%d') if max_date else None,
            ),
            'publishers': sorted(list(publishers)),
            'file_count': len(parquet_files),
        }

    return summary


def get_unique_tickers(df: pd.DataFrame) -> List[str]:
    """Get sorted list of unique tickers from DataFrame."""
    if df.empty or 'ticker' not in df.columns:
        return []
    return sorted(df['ticker'].dropna().unique().tolist())


def get_unique_publishers(df: pd.DataFrame) -> List[str]:
    """Get sorted list of unique publishers from DataFrame."""
    if df.empty or 'publisher' not in df.columns:
        return []
    return sorted(df['publisher'].dropna().unique().tolist())


def get_publisher_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Get article count by publisher."""
    if df.empty or 'publisher' not in df.columns:
        return pd.DataFrame()

    stats = df.groupby('publisher').agg({
        'article_id': 'count',
        'content_length': 'mean',
    }).reset_index()
    stats.columns = ['Publisher', 'Article Count', 'Avg Content Length']
    stats = stats.sort_values('Article Count', ascending=False)

    return stats


def get_monthly_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Get article count by month and source."""
    if df.empty or 'published_date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['year_month'] = df['published_date'].dt.to_period('M')

    stats = df.groupby(['year_month', 'source_api']).size().reset_index(name='count')
    stats['year_month'] = stats['year_month'].astype(str)

    return stats


def search_articles(
    df: pd.DataFrame,
    query: str,
    search_in: List[str] = None,
) -> pd.DataFrame:
    """
    Search articles by keyword.

    Args:
        df: DataFrame to search
        query: Search query
        search_in: Columns to search in (default: title, description, content)

    Returns:
        Filtered DataFrame
    """
    if not query or df.empty:
        return df

    if search_in is None:
        search_in = ['title', 'description', 'content']

    query = query.lower()
    mask = pd.Series([False] * len(df), index=df.index)

    for col in search_in:
        if col in df.columns:
            col_mask = df[col].fillna('').str.lower().str.contains(query, regex=False)
            mask = mask | col_mask

    return df[mask]


# For Streamlit caching
def cached_load_all_sources(
    sources: Tuple[str, ...],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """
    Cacheable version of load_all_sources.
    Use with @st.cache_data in Streamlit.
    """
    return load_all_sources(
        sources=list(sources),
        date_from=date_from,
        date_to=date_to,
    )


def cached_get_data_summary() -> Dict:
    """
    Cacheable version of get_data_summary.
    Use with @st.cache_data in Streamlit.
    """
    return get_data_summary()