"""
Computes the technical indicators needed for the checklist, given a
DataFrame of OHLCV data (indexed by date, columns: open, high, low,
close, volume — same shape as data_ingestion.yfinance_client output).

All functions return the *last* value plus, where useful, enough of
the recent series for the scoring layer to reason about (e.g. resistance
levels need the recent price history, not just the last EMA value).
"""
import pandas as pd
import pandas_ta as ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds EMA20/50/200, RSI14, ADX14, and a rolling 20-day average
    volume column onto a copy of the input DataFrame. Returns the
    augmented DataFrame — does not mutate the original.
    """
    out = df.copy()
    out["ema20"] = ta.ema(out["close"], length=20)
    out["ema50"] = ta.ema(out["close"], length=50)
    out["ema200"] = ta.ema(out["close"], length=200)
    out["rsi14"] = ta.rsi(out["close"], length=14)

    adx_df = ta.adx(out["high"], out["low"], out["close"], length=14)
    out["adx14"] = adx_df[f"ADX_14"] if adx_df is not None else None

    out["vol_avg20"] = out["volume"].rolling(window=20).mean()
    out["vol_ratio"] = out["volume"] / out["vol_avg20"]

    return out


def find_resistance(df: pd.DataFrame, lookback: int = 60, order: int = 5) -> float | None:
    """
    Naive swing-high based resistance detection: finds local maxima in
    the `high` column over the lookback window and returns the most
    recent one below the current price (i.e. the level price would
    need to break through). Returns None if none found.

    `order` = number of bars on each side that must be lower for a
    point to count as a local max — tune this to control sensitivity
    (higher order = fewer, more significant swing highs).
    """
    from scipy.signal import argrelextrema
    import numpy as np

    window = df.tail(lookback)
    highs = window["high"].values
    local_max_idx = argrelextrema(highs, comparator=lambda a, b: a > b, order=order)[0]

    if len(local_max_idx) == 0:
        return None

    current_price = df["close"].iloc[-1]
    candidate_levels = [highs[i] for i in local_max_idx if highs[i] > current_price]
    return min(candidate_levels) if candidate_levels else None


def is_tight_consolidation(df: pd.DataFrame, lookback: int = 10, max_range_pct: float = 0.06) -> bool:
    """
    True if the (high-low)/close range over the last `lookback` bars
    stays under `max_range_pct` — a simple proxy for "coiling" price
    action before a breakout.
    """
    window = df.tail(lookback)
    range_pct = (window["high"].max() - window["low"].min()) / window["close"].iloc[-1]
    return range_pct <= max_range_pct
