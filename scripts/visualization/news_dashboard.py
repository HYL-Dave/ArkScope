#!/usr/bin/env python3
"""
News Data Visualization Dashboard

A Streamlit application for exploring and analyzing collected news data
from Polygon, Finnhub, and IBKR sources.

Usage:
    streamlit run scripts/visualization/news_dashboard.py

Features:
    - Overview: Data summary and statistics
    - Explorer: Browse and search articles with filters
    - Analytics: Statistical analysis and charts
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from data_loader import (
    load_all_sources,
    get_data_summary,
    get_unique_tickers,
    get_unique_publishers,
    get_publisher_stats,
    get_monthly_stats,
    search_articles,
    clean_html_content,
    strip_html_tags,
    DEFAULT_DATA_DIR,
)

# Page config
st.set_page_config(
    page_title="News Data Dashboard",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .article-content {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        max-height: 400px;
        overflow-y: auto;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .source-polygon { color: #7C3AED; }
    .source-finnhub { color: #059669; }
    .source-ibkr { color: #DC2626; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Caching functions
# ============================================================================

@st.cache_data(ttl=3600)
def load_data_cached(sources: tuple, date_from: str = None, date_to: str = None):
    """Load and cache news data."""
    return load_all_sources(
        sources=list(sources),
        date_from=date_from,
        date_to=date_to,
    )


@st.cache_data(ttl=3600)
def get_summary_cached():
    """Get and cache data summary."""
    return get_data_summary()


# ============================================================================
# Sidebar Navigation
# ============================================================================

st.sidebar.title("📰 News Dashboard")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Overview", "🔍 Explorer", "📊 Analytics"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")

# Data source selection
st.sidebar.subheader("Data Sources")
use_polygon = st.sidebar.checkbox("Polygon", value=True)
use_finnhub = st.sidebar.checkbox("Finnhub", value=True)
use_ibkr = st.sidebar.checkbox("IBKR", value=True)

selected_sources = []
if use_polygon:
    selected_sources.append('polygon')
if use_finnhub:
    selected_sources.append('finnhub')
if use_ibkr:
    selected_sources.append('ibkr')

if not selected_sources:
    st.error("Please select at least one data source")
    st.stop()


# ============================================================================
# Overview Page
# ============================================================================

def render_overview():
    st.title("📊 News Data Overview")

    # Get summary
    summary = get_summary_cached()

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)

    total_articles = sum(summary[s]['total_articles'] for s in selected_sources)

    with col1:
        st.metric("Total Articles", f"{total_articles:,}")

    with col2:
        st.metric("Sources", len(selected_sources))

    with col3:
        all_publishers = set()
        for s in selected_sources:
            all_publishers.update(summary[s]['publishers'])
        st.metric("Publishers", len(all_publishers))

    with col4:
        # Get date range
        min_dates = []
        max_dates = []
        for s in selected_sources:
            dr = summary[s]['date_range']
            if dr[0]:
                min_dates.append(dr[0])
            if dr[1]:
                max_dates.append(dr[1])
        date_range = f"{min(min_dates) if min_dates else 'N/A'} ~ {max(max_dates) if max_dates else 'N/A'}"
        st.metric("Date Range", date_range)

    st.markdown("---")

    # Source breakdown
    st.subheader("📈 Articles by Source")

    col1, col2 = st.columns(2)

    with col1:
        source_data = []
        for source in selected_sources:
            source_data.append({
                'Source': source.upper(),
                'Articles': summary[source]['total_articles'],
            })

        if source_data:
            df_sources = pd.DataFrame(source_data)
            fig = px.pie(
                df_sources,
                values='Articles',
                names='Source',
                color='Source',
                color_discrete_map={
                    'POLYGON': '#7C3AED',
                    'FINNHUB': '#059669',
                    'IBKR': '#DC2626',
                },
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, width='stretch')

    with col2:
        if source_data:
            fig = px.bar(
                df_sources,
                x='Source',
                y='Articles',
                color='Source',
                color_discrete_map={
                    'POLYGON': '#7C3AED',
                    'FINNHUB': '#059669',
                    'IBKR': '#DC2626',
                },
            )
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Source details
    st.subheader("📋 Source Details")

    for source in selected_sources:
        info = summary[source]
        with st.expander(f"**{source.upper()}** - {info['total_articles']:,} articles"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Date Range:** {info['date_range'][0]} ~ {info['date_range'][1]}")
                st.write(f"**Files:** {info['file_count']}")
            with col2:
                st.write(f"**Publishers ({len(info['publishers'])}):**")
                for pub in info['publishers'][:10]:
                    st.write(f"  - {pub}")
                if len(info['publishers']) > 10:
                    st.write(f"  ... and {len(info['publishers']) - 10} more")


# ============================================================================
# Explorer Page
# ============================================================================

def render_explorer():
    st.title("🔍 Article Explorer")

    # Load data
    with st.spinner("Loading data..."):
        df = load_data_cached(tuple(selected_sources))

    if df.empty:
        st.warning("No data available for selected sources")
        return

    st.info(f"Loaded {len(df):,} articles from {len(selected_sources)} source(s)")

    # Filters
    st.subheader("Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Date filter
        min_date = df['published_date'].min()
        max_date = df['published_date'].max()

        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.date_input(
                "Date Range",
                value=(min_date.date(), max_date.date()),
                min_value=min_date.date(),
                max_value=max_date.date(),
            )
            if len(date_range) == 2:
                df = df[
                    (df['published_date'].dt.date >= date_range[0]) &
                    (df['published_date'].dt.date <= date_range[1])
                ]

    with col2:
        # Publisher filter
        publishers = get_unique_publishers(df)
        selected_publishers = st.multiselect(
            "Publishers",
            options=publishers,
            default=None,
            placeholder="All publishers",
        )
        if selected_publishers:
            df = df[df['publisher'].isin(selected_publishers)]

    with col3:
        # Ticker filter
        tickers = get_unique_tickers(df)
        selected_tickers = st.multiselect(
            "Tickers",
            options=tickers,
            default=None,
            placeholder="All tickers",
        )
        if selected_tickers:
            df = df[df['ticker'].isin(selected_tickers)]

    # Search
    search_query = st.text_input("🔎 Search keywords", placeholder="Enter keywords...")
    if search_query:
        df = search_articles(df, search_query)

    st.markdown("---")

    # Results
    st.subheader(f"Results ({len(df):,} articles)")

    if df.empty:
        st.warning("No articles match your filters")
        return

    # Pagination
    items_per_page = st.selectbox("Items per page", [10, 25, 50, 100], index=1)
    total_pages = max(1, (len(df) - 1) // items_per_page + 1)
    current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)

    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page

    # Sort
    df = df.sort_values('published_date', ascending=False)

    # Display articles
    page_df = df.iloc[start_idx:end_idx]

    for idx, row in page_df.iterrows():
        source_color = {
            'polygon': '#7C3AED',
            'finnhub': '#059669',
            'ibkr': '#DC2626',
        }.get(row['source_api'], '#666')

        with st.expander(
            f"**{row['title'][:100]}{'...' if len(str(row['title'])) > 100 else ''}** "
            f"| {row['ticker']} | {row['publisher']} | {str(row['published_date'])[:10]}"
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**Source:** <span style='color:{source_color}'>{row['source_api'].upper()}</span>",
                           unsafe_allow_html=True)
                st.write(f"**Published:** {row['published_at']}")
                st.write(f"**Ticker:** {row['ticker']}")
                st.write(f"**Publisher:** {row['publisher']}")

                if row.get('url'):
                    st.write(f"**URL:** [{row['url'][:50]}...]({row['url']})")

            with col2:
                st.write(f"**Content Length:** {row.get('content_length', 0):,} chars")
                if row.get('source_sentiment'):
                    st.write(f"**Sentiment:** {row['source_sentiment']}")

            # Content display
            st.markdown("---")
            content = row.get('content') or row.get('description') or ''

            if content:
                # Check if HTML content (IBKR)
                if row['source_api'] == 'ibkr' and ('<' in str(content) or '&#' in str(content)):
                    st.markdown("**Content (HTML rendered):**")
                    cleaned = clean_html_content(content)
                    st.markdown(f'<div class="article-content">{cleaned}</div>',
                               unsafe_allow_html=True)
                else:
                    st.markdown("**Content:**")
                    st.markdown(f'<div class="article-content">{content}</div>',
                               unsafe_allow_html=True)
            else:
                st.info("No content available")

    # Page info
    st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(df))} of {len(df):,} articles")


# ============================================================================
# Analytics Page
# ============================================================================

def render_analytics():
    st.title("📊 Analytics")

    # Load data
    with st.spinner("Loading data..."):
        df = load_data_cached(tuple(selected_sources))

    if df.empty:
        st.warning("No data available for selected sources")
        return

    # Publisher stats
    st.subheader("📰 Publisher Distribution")

    col1, col2 = st.columns(2)

    with col1:
        publisher_stats = get_publisher_stats(df)
        if not publisher_stats.empty:
            top_n = st.slider("Top N publishers", 5, 30, 15)
            top_publishers = publisher_stats.head(top_n)

            fig = px.bar(
                top_publishers,
                x='Article Count',
                y='Publisher',
                orientation='h',
                color='Article Count',
                color_continuous_scale='Viridis',
            )
            fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Publisher by source
        if 'source_api' in df.columns and 'publisher' in df.columns:
            pub_source = df.groupby(['source_api', 'publisher']).size().reset_index(name='count')
            pub_source = pub_source.sort_values('count', ascending=False).head(20)

            fig = px.bar(
                pub_source,
                x='count',
                y='publisher',
                color='source_api',
                orientation='h',
                color_discrete_map={
                    'polygon': '#7C3AED',
                    'finnhub': '#059669',
                    'ibkr': '#DC2626',
                },
            )
            fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Monthly trends
    st.subheader("📈 Monthly Article Volume")

    monthly_stats = get_monthly_stats(df)
    if not monthly_stats.empty:
        fig = px.line(
            monthly_stats,
            x='year_month',
            y='count',
            color='source_api',
            markers=True,
            color_discrete_map={
                'polygon': '#7C3AED',
                'finnhub': '#059669',
                'ibkr': '#DC2626',
            },
        )
        fig.update_layout(
            height=400,
            xaxis_title="Month",
            yaxis_title="Article Count",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Content length distribution
    st.subheader("📏 Content Length Distribution")

    col1, col2 = st.columns(2)

    with col1:
        if 'content_length' in df.columns:
            fig = px.histogram(
                df[df['content_length'] > 0],
                x='content_length',
                color='source_api',
                nbins=50,
                color_discrete_map={
                    'polygon': '#7C3AED',
                    'finnhub': '#059669',
                    'ibkr': '#DC2626',
                },
            )
            fig.update_layout(height=350, xaxis_title="Content Length (chars)")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Box plot by source
        if 'content_length' in df.columns:
            fig = px.box(
                df[df['content_length'] > 0],
                x='source_api',
                y='content_length',
                color='source_api',
                color_discrete_map={
                    'polygon': '#7C3AED',
                    'finnhub': '#059669',
                    'ibkr': '#DC2626',
                },
            )
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Ticker coverage
    st.subheader("🎯 Top Tickers by Coverage")

    ticker_counts = df.groupby('ticker').size().reset_index(name='count')
    ticker_counts = ticker_counts.sort_values('count', ascending=False).head(20)

    fig = px.bar(
        ticker_counts,
        x='ticker',
        y='count',
        color='count',
        color_continuous_scale='Blues',
    )
    fig.update_layout(height=350, xaxis_title="Ticker", yaxis_title="Article Count")
    st.plotly_chart(fig, use_container_width=True)

    # Daily heatmap
    st.subheader("📅 Daily Publication Heatmap")

    if 'published_date' in df.columns:
        df_recent = df[df['published_date'] >= (datetime.now() - timedelta(days=90))]

        if not df_recent.empty:
            df_recent = df_recent.copy()
            df_recent['weekday'] = df_recent['published_date'].dt.day_name()
            df_recent['week'] = df_recent['published_date'].dt.isocalendar().week

            heatmap_data = df_recent.groupby(['weekday', 'week']).size().reset_index(name='count')

            # Order weekdays
            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            heatmap_data['weekday'] = pd.Categorical(heatmap_data['weekday'], categories=weekday_order, ordered=True)
            heatmap_pivot = heatmap_data.pivot(index='weekday', columns='week', values='count').fillna(0)

            fig = px.imshow(
                heatmap_pivot,
                color_continuous_scale='YlOrRd',
                labels={'color': 'Articles'},
            )
            fig.update_layout(height=300, xaxis_title="Week of Year", yaxis_title="Day of Week")
            st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# Main Router
# ============================================================================

if page == "🏠 Overview":
    render_overview()
elif page == "🔍 Explorer":
    render_explorer()
elif page == "📊 Analytics":
    render_analytics()

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("News Dashboard v1.0")
st.sidebar.caption(f"Data: {DEFAULT_DATA_DIR}")