"""
Downloads and parses BSE's daily "bhavcopy" — an official end-of-day
CSV bulk file covering every listed scrip's OHLC + volume for one
trading day. Good for backfilling a historical price archive without
per-symbol API calls.

IMPORTANT: BSE has changed this URL/format several times over the
years (plain CSV -> zipped CSV -> different filename patterns). The
pattern below (EQ<DD><MM><YY>_CSV.zip) is the current documented
format as of writing, but verify against bseindia.com's
Markets > Market Info > Bhav Copy page before relying on it, since I
can't test live network access to BSE from this sandbox — its domain
isn't reachable here, so please confirm this works from your machine
and adjust the URL pattern if BSE has changed it again.
"""
from datetime import date
import io
import zipfile
import httpx
import pandas as pd

BHAVCOPY_URL_TEMPLATE = "https://www.bseindia.com/download/BhavCopy/Equity/EQ{ddmmyy}_CSV.zip"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_bhavcopy(for_date: date) -> pd.DataFrame:
    """
    Returns the full-market EOD bar for `for_date` as a DataFrame with
    normalized column names: symbol, open, high, low, close, volume.

    Raises httpx.HTTPStatusError on bad dates (holidays/weekends won't
    have a file) — callers should catch and skip.
    """
    ddmmyy = for_date.strftime("%d%m%y")
    url = BHAVCOPY_URL_TEMPLATE.format(ddmmyy=ddmmyy)

    resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)

    df.columns = [c.strip().lower() for c in df.columns]

    rename_map = {
        "sc_name": "symbol", "symbol": "symbol",
        "open": "open", "high": "high", "low": "low",
        "close": "close", "no_of_shrs": "volume", "volume": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    keep = [c for c in ["symbol", "open", "high", "low", "close", "volume"] if c in df.columns]
    return df[keep]


if __name__ == "__main__":
    import sys
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(fetch_bhavcopy(d).head())
