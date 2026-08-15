"""
Fetches quote-level fundamentals and shareholding pattern from NSE,
via the actively-maintained `nse` library (pip install nse[local])
rather than hand-rolling the anti-bot handshake ourselves.

WHY THIS LIBRARY (history of what didn't work): the original version
of this file wrapped `nsepython`, which has a long history of breaking
whenever NSE tightens its anti-bot checks. A hand-rolled httpx-based
replacement still got a 403 (NSE fingerprints the TLS handshake, not
just headers). A curl_cffi-based version with browser TLS impersonation
got past the 403, but the shareholding endpoint URL/params used were
wrong, returning a "missing index" error. Rather than keep guessing at
NSE's exact handshake requirements, this switches to `nse` — a
maintained, documented library (bennythadikaran.github.io/NseIndiaApi)
that handles cookie persistence, session bootstrap, and rate-limiting
internally, and has known-correct endpoint/parameter mappings.

IMPORTANT DATA LIMITATION (confirmed from the library's documented
sample response, not a bug to fix): NSE's shareholding-pattern
endpoint only reports a Promoter vs Public split
(`pr_and_prgrp` / `public_val`) — it does NOT break "Public" down into
FII vs DII at the per-stock level. That distinction matters for two
checklist conditions (`fii_dii_increasing` in the Fundamental score,
`fii_increasing`/`dii_increasing` in the Smart Money score) — those
will stay None/unknown from this data source. Getting real per-stock
FII/DII splits would need a different source (e.g. the full XBRL
shareholding filing, which has finer sub-categories, or a paid data
provider) — flagged as a known gap in the README rather than silently
guessed at.

IMPORTANT: I cannot verify this against a live NSE response from this
sandbox (no network access to nseindia.com here) — this is the third
attempt at this problem, each based on solid reasoning from what the
previous attempt's actual failure told us, but genuinely untested
end-to-end. Run `python -m app.data_ingestion.nse_client RELIANCE` and
report back what happens.
"""
from pathlib import Path
from nse import NSE

# Cookies get cached here between calls (the library's own mechanism) —
# avoids re-bootstrapping a session on every single call.
_CACHE_DIR = Path(__file__).parent / ".nse_cache"
_CACHE_DIR.mkdir(exist_ok=True)


def fetch_quote(symbol: str) -> dict:
    """
    Returns NSE quote data for a symbol — current price, market depth,
    OHLC, trading metrics. Good for real-time-ish price display, not
    for scoring (use OHLCV history for that).
    """
    with NSE(download_folder=_CACHE_DIR) as nse:
        return nse.quote(symbol)


def fetch_shareholding(symbol: str) -> list[dict]:
    """
    Returns a list of quarterly shareholding records for a symbol,
    most recent quarter first. Each record includes (per the library's
    documented response shape):
        symbol, date, pr_and_prgrp (promoter+group %), public_val
        (public %), employeeTrusts, and filing metadata.

    NOTE: no FII/DII split is available here — see module docstring.
    """
    with NSE(download_folder=_CACHE_DIR) as nse:
        return nse.shareholding(symbol)


def fetch_delivery_pct(symbol: str) -> float | None:
    """
    Returns the day's delivery-to-traded-quantity percentage for a
    symbol — the share of traded volume that resulted in actual
    delivery (vs. intraday square-off), a common proxy for "real"
    investor participation vs. speculative/day-trading volume.

    Confirmed live field: NSE's quote-equity response includes this
    under tradeInfo.deliveryToTradedQuantity (seen directly in a real
    RELIANCE quote during this project — no guessing involved).
    Returns None if the field is missing from the response (e.g. for
    a symbol/segment where NSE doesn't report it).
    """
    quote = fetch_quote(symbol)
    trade_info = quote.get("tradeInfo") if isinstance(quote, dict) else None
    if not trade_info:
        return None
    return trade_info.get("deliveryToTradedQuantity")


if __name__ == "__main__":
    import sys
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    print(f"--- quote for {sym} ---")
    try:
        print(json.dumps(fetch_quote(sym), indent=2)[:1500])
    except Exception as e:
        print(f"FAILED: {e}")
    print(f"\n--- shareholding for {sym} ---")
    try:
        print(json.dumps(fetch_shareholding(sym), indent=2)[:1500])
    except Exception as e:
        print(f"FAILED: {e}")
