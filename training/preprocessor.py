"""
Data preprocessor — local replacement for finrl.meta.preprocessor.

Provides YahooDownloader, FeatureEngineer, and data_split previously imported
from finrl.  External dependencies: yfinance, stockstats, pandas, numpy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
import tempfile

from .config import INDICATORS


# ── YahooDownloader ──────────────────────────────────────────


class YahooDownloader:
    """Download historical OHLCV from Yahoo Finance via yfinance."""

    def __init__(self, start_date: str, end_date: str, ticker_list: list[str]):
        self.start_date = start_date
        self.end_date = end_date
        self.ticker_list = ticker_list

    def fetch_data(self, auto_adjust: bool = True) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        failures = 0

        # Redirect yfinance timezone SQLite cache to a writable temp dir.
        # Some environments have read-only default cache locations.
        try:
            yf.set_tz_cache_location(tempfile.gettempdir())
        except Exception:
            pass

        for tic in self.ticker_list:
            temp = yf.download(
                tic,
                start=self.start_date,
                end=self.end_date,
                auto_adjust=auto_adjust,
                progress=False,
            )
            if temp.columns.nlevels != 1:
                temp.columns = temp.columns.droplevel(1)
            temp["tic"] = tic
            if len(temp) > 0:
                frames.append(temp)
            else:
                failures += 1

        if failures == len(self.ticker_list):
            raise ValueError("No data fetched for any ticker.")

        data = pd.concat(frames, axis=0).reset_index()
        data.rename(
            columns={
                "Date": "date",
                "Adj Close": "adjcp",
                "Close": "close",
                "High": "high",
                "Low": "low",
                "Volume": "volume",
                "Open": "open",
            },
            inplace=True,
        )

        # When auto_adjust=False, manually adjust using Adj Close
        if not auto_adjust and "adjcp" in data.columns:
            adj = data["adjcp"] / data["close"]
            for col in ("open", "high", "low", "close"):
                data[col] *= adj
            data.drop(columns=["adjcp"], inplace=True, errors="ignore")

        data["day"] = data["date"].dt.dayofweek
        data["date"] = data["date"].apply(lambda x: x.strftime("%Y-%m-%d"))
        data = data.dropna().reset_index(drop=True)
        data = data.sort_values(by=["date", "tic"]).reset_index(drop=True)
        print(f"Shape of DataFrame: {data.shape}")
        return data


# ── FeatureEngineer ──────────────────────────────────────────


class FeatureEngineer:
    """Add technical indicators, VIX, and turbulence to OHLCV data.

    Uses the ``stockstats`` library for indicator computation.
    """

    def __init__(
        self,
        use_technical_indicator: bool = True,
        tech_indicator_list: list[str] | None = None,
        use_vix: bool = False,
        use_turbulence: bool = False,
        user_defined_feature: bool = False,
    ):
        self.use_technical_indicator = use_technical_indicator
        self.tech_indicator_list = tech_indicator_list or INDICATORS
        self.use_vix = use_vix
        self.use_turbulence = use_turbulence
        self.user_defined_feature = user_defined_feature

    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._clean_data(df)
        if self.use_technical_indicator:
            df = self._add_technical_indicators(df)
        if self.use_vix:
            df = self._add_vix(df)
        if self.use_turbulence:
            df = self._add_turbulence(df)
        if self.user_defined_feature:
            df["daily_return"] = df["close"].pct_change(1)
        df = df.ffill().bfill()
        return df

    # ── internals ─────────────────────────────────────────

    @staticmethod
    def _clean_data(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df = df.sort_values(["date", "tic"], ignore_index=True)
        df.index = df["date"].factorize()[0]
        merged = df.pivot_table(index="date", columns="tic", values="close")
        merged = merged.dropna(axis=1)
        df = df[df["tic"].isin(merged.columns)]
        return df

    def _add_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        from stockstats import StockDataFrame as Sdf

        df = data.copy().sort_values(by=["tic", "date"])
        stock = Sdf.retype(df.copy())
        tickers = stock["tic"].unique()

        for indicator in self.tech_indicator_list:
            parts: list[pd.DataFrame] = []
            for tic in tickers:
                try:
                    mask = stock["tic"] == tic
                    vals = stock.loc[mask, indicator]
                    tmp = pd.DataFrame(vals)
                    tmp["tic"] = tic
                    tmp["date"] = df.loc[df["tic"] == tic, "date"].to_list()
                    parts.append(tmp)
                except Exception as e:
                    print(f"Indicator {indicator} failed for {tic}: {e}")
            if parts:
                indicator_df = pd.concat(parts, ignore_index=True)
                df = df.merge(
                    indicator_df[["tic", "date", indicator]],
                    on=["tic", "date"],
                    how="left",
                )
        return df.sort_values(by=["date", "tic"])

    def _add_vix(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        vix_df = YahooDownloader(
            start_date=df["date"].min(),
            end_date=df["date"].max(),
            ticker_list=["^VIX"],
        ).fetch_data()
        vix = vix_df[["date", "close"]].rename(columns={"close": "vix"})
        df = df.merge(vix, on="date")
        return df.sort_values(["date", "tic"]).reset_index(drop=True)

    def _add_turbulence(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        turb = self._calculate_turbulence(df)
        df = df.merge(turb, on="date")
        return df.sort_values(["date", "tic"]).reset_index(drop=True)

    @staticmethod
    def _calculate_turbulence(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        pivot = df.pivot(index="date", columns="tic", values="close").pct_change()
        dates = df["date"].unique()
        start = 252
        turb_idx = [0.0] * start
        count = 0

        for i in range(start, len(dates)):
            current = pivot[pivot.index == dates[i]]
            hist = pivot[
                (pivot.index < dates[i]) & (pivot.index >= dates[i - 252])
            ]
            hist = hist.iloc[hist.isna().sum().min() :].dropna(axis=1)
            cov = hist.cov()
            cols = [c for c in hist.columns if c in current.columns]
            curr_dev = current[cols] - hist[cols].mean()
            temp = curr_dev.values.dot(np.linalg.pinv(cov.loc[cols, cols])).dot(
                curr_dev.values.T
            )
            if temp > 0:
                count += 1
                turb_idx.append(temp[0][0] if count > 2 else 0.0)
            else:
                turb_idx.append(0.0)

        return pd.DataFrame({"date": pivot.index, "turbulence": turb_idx})


# ── data_split ───────────────────────────────────────────────


def data_split(
    df: pd.DataFrame,
    start: str,
    end: str,
    target_date_col: str = "date",
) -> pd.DataFrame:
    """Split DataFrame by date range [start, end).

    Returns a copy sorted by (date, tic) with factorized date index.
    """
    data = df[
        (df[target_date_col] >= start) & (df[target_date_col] < end)
    ].copy()
    data = data.sort_values([target_date_col, "tic"], ignore_index=True)
    data.index = data[target_date_col].factorize()[0]
    return data
