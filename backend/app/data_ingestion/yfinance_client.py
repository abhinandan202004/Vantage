"""
Fetches daily OHLCV candles for NSE-listed stocks via Yahoo Finance.

NSE tickers need a ".NS" suffix on Yahoo (e.g. RELIANCE -> RELIANCE.NS).
Index tickers use "^" prefixes (Nifty 50 -> ^NSEI).

This is the primary source for price data in the MVP — reliable, free,
no auth needed. Fundamental fields from yfinance are NOT used (patchy
for Indian stocks) — see nse_client.py / bhavcopy.py for that side.
"""
from datetime import date, timedelta
import pandas as pd
import yfinance as yf


def _to_yahoo_symbol(symbol: str) -> str:
    """Convert a bare NSE symbol to its Yahoo Finance ticker."""
    if symbol.startswith("^"):
        return symbol  # already an index ticker like ^NSEI
    return f"{symbol}.NS"


def fetch_ohlcv(symbol: str, lookback_days: int = 400) -> pd.DataFrame:
    """
    Returns a DataFrame indexed by date with columns:
    open, high, low, close, volume

    Raises ValueError if no data comes back (bad symbol, delisted, etc.)
    so callers can decide how to handle it rather than silently
    persisting an empty result.
    """
    yahoo_symbol = _to_yahoo_symbol(symbol)
    start = date.today() - timedelta(days=lookback_days)

    ticker = yf.Ticker(yahoo_symbol)
    df = ticker.history(start=start, interval="1d", auto_adjust=False)

    if df.empty:
        raise ValueError(f"No OHLCV data returned for {symbol} ({yahoo_symbol})")

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })[["open", "high", "low", "close", "volume"]]
    df.index = df.index.date
    df.index.name = "date"
    return df


if __name__ == "__main__":
    # Quick manual check — run with: python -m app.data_ingestion.yfinance_client
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    data = fetch_ohlcv(sym, lookback_days=30)
    print(data.tail())
