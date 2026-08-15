"""
Maps NSE stock symbols to their sector, and sectors to the Yahoo
Finance ticker for that sector's NSE index — needed for the
"sector outperforming Nifty" technical condition (compares a stock's
sector index return against the Nifty 50's return over the same
window).

Yahoo Finance tickers below were confirmed via live Yahoo Finance
pages at the time of writing (not guessed) — see comments per ticker.
If any of these stop resolving, search "<index name> yahoo finance
ticker" to find the current one; NSE sector indices don't get renamed
often, but Yahoo's ticker symbols for them have shifted before.

STOCK_SECTOR_MAP below is a manually curated starter list covering
commonly-traded large-caps across the main sectors — NOT exhaustive.
For any symbol not in this map, the "sector outperforming Nifty"
condition will correctly come back as `None` (not computed) rather
than guessing at a sector. Extend this list as you add symbols you
care about; a fuller version would ideally pull sector classification
from NSE's own listings data instead of being hand-maintained.
"""

SECTOR_INDEX_TICKERS = {
    "banking": "^NSEBANK",       # NIFTY BANK
    "it": "^CNXIT",               # NIFTY IT
    "auto": "^CNXAUTO",           # NIFTY AUTO
    "pharma": "^CNXPHARMA",       # NIFTY PHARMA
    "metal": "^CNXMETAL",         # NIFTY METAL
    "fmcg": "^CNXFMCG",           # NIFTY FMCG
    "energy": "^CNXENERGY",       # NIFTY ENERGY
    "financial_services": "^CNXFIN",  # NIFTY FINANCIAL SERVICES
    "realty": "^CNXREALTY",       # NIFTY REALTY
}

# symbol -> sector key (must match a key in SECTOR_INDEX_TICKERS)
STOCK_SECTOR_MAP = {
    # Banking
    "HDFCBANK": "banking", "ICICIBANK": "banking", "SBIN": "banking",
    "AXISBANK": "banking", "KOTAKBANK": "banking", "INDUSINDBK": "banking",
    "BANKBARODA": "banking", "PNB": "banking", "FEDERALBNK": "banking",
    "IDFCFIRSTB": "banking", "RBLBANK": "banking",

    # IT
    "TCS": "it", "INFY": "it", "WIPRO": "it", "HCLTECH": "it",
    "TECHM": "it", "LTIM": "it", "MPHASIS": "it", "COFORGE": "it",

    # Auto
    "MARUTI": "auto", "TATAMOTORS": "auto", "M&M": "auto",
    "BAJAJ-AUTO": "auto", "EICHERMOT": "auto", "HEROMOTOCO": "auto",
    "TVSMOTOR": "auto", "ASHOKLEY": "auto",

    # Pharma
    "SUNPHARMA": "pharma", "DRREDDY": "pharma", "CIPLA": "pharma",
    "DIVISLAB": "pharma", "LUPIN": "pharma", "AUROPHARMA": "pharma",
    "TORNTPHARM": "pharma", "ALKEM": "pharma",

    # Metal
    "TATASTEEL": "metal", "JSWSTEEL": "metal", "HINDALCO": "metal",
    "VEDL": "metal", "JINDALSTEL": "metal", "SAIL": "metal",
    "NATIONALUM": "metal", "NMDC": "metal",

    # FMCG
    "HINDUNILVR": "fmcg", "ITC": "fmcg", "NESTLEIND": "fmcg",
    "BRITANNIA": "fmcg", "DABUR": "fmcg", "MARICO": "fmcg",
    "GODREJCP": "fmcg", "TATACONSUM": "fmcg", "COLPAL": "fmcg",

    # Energy
    "RELIANCE": "energy", "ONGC": "energy", "NTPC": "energy",
    "POWERGRID": "energy", "COALINDIA": "energy", "BPCL": "energy",
    "IOC": "energy", "GAIL": "energy",

    # Financial Services (non-bank)
    "BAJFINANCE": "financial_services", "BAJAJFINSV": "financial_services",
    "HDFCLIFE": "financial_services", "SBILIFE": "financial_services",
    "ICICIPRULI": "financial_services", "ICICIGI": "financial_services",
    "SHRIRAMFIN": "financial_services", "CHOLAFIN": "financial_services",

    # Realty
    "DLF": "realty", "GODREJPROP": "realty", "OBEROIRLTY": "realty",
    "PHOENIXLTD": "realty", "PRESTIGE": "realty",
}


def get_sector_index_ticker(symbol: str) -> str | None:
    """Returns the Yahoo Finance ticker for `symbol`'s sector index,
    or None if the symbol isn't in the curated map (not an error —
    the caller treats None as "sector data unavailable for this stock",
    same as any other not-yet-computed condition)."""
    sector = STOCK_SECTOR_MAP.get(symbol.upper())
    if sector is None:
        return None
    return SECTOR_INDEX_TICKERS.get(sector)
