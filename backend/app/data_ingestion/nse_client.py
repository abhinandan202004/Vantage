"""
Wraps `nsepython` to pull quote-level fundamentals (P/E, market cap,
52-week range) and shareholding pattern from NSE's public (unofficial)
JSON endpoints.

NSE requires a browser-like session (cookies + headers) before it will
serve these endpoints — nsepython handles that internally. If NSE
changes their anti-bot measures this is the piece most likely to break;
wrap calls in try/except in production and fall back gracefully.
"""
from nsepython import nsefetch


NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity"
NSE_SHAREHOLDING_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"


def fetch_quote(symbol: str) -> dict:
    """
    Returns raw NSE quote JSON for a symbol — includes priceInfo
    (lastPrice, 52-week high/low) and some metadata. This is a good
    source for real-time-ish price display, not for scoring (use
    OHLCV history for that).
    """
    return nsefetch(f"{NSE_QUOTE_URL}?symbol={symbol}")


def fetch_shareholding(symbol: str) -> dict:
    """
    Returns raw shareholding pattern JSON for a symbol.
    Caller is responsible for parsing out promoter/FII/DII percentages
    since NSE's response shape varies by filing period.
    """
    return nsefetch(f"{NSE_SHAREHOLDING_URL}?symbol={symbol}")


if __name__ == "__main__":
    import sys
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    print(json.dumps(fetch_quote(sym), indent=2)[:1000])
