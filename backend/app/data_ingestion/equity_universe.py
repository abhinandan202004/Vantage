"""
Fetches a list of NSE-listed stocks (symbol + company name) to
populate the local search index that powers stock search/autocomplete
— deliberately NOT hitting NSE live on every keystroke a user types;
this is ingested once (and re-run periodically) into the `stocks`
table, and search queries hit that local data instead.

Uses `NSE.listEquityStocksByIndex()` rather than NSE's raw bulk equity
list CSV export — covers the ~500 most liquid/traded stocks (NIFTY 500
constituents), which is realistic coverage for what a user of this app
will actually search for. Extend to additional indices (e.g. NIFTY
MIDCAP 150, NIFTY SMALLCAP 250) later if you want broader long-tail
coverage.

IMPORTANT: I have NOT verified this against a live NSE response — same
sandbox network limitation as the rest of the NSE integrations in this
project. The exact field names for symbol/company-name in the returned
records are my best inference; uncomment the print() below on first
run to confirm the real shape and adjust `_extract_symbol_and_name` if
needed.
"""


def _extract_symbol_and_name(record: dict) -> tuple[str, str] | None:
    """
    Best-effort extraction of (symbol, company_name) from one
    listEquityStocksByIndex() record. Tries the field names NSE
    commonly uses across its various endpoints. Returns None if
    neither could be found, so the caller can skip that record rather
    than store garbage.
    """
    symbol = None
    for key in ("symbol", "Symbol", "SYMBOL"):
        if key in record and record[key]:
            symbol = record[key]
            break

    name = None
    for key in ("companyName", "company_name", "meta", "symbolName", "name"):
        val = record.get(key)
        if isinstance(val, str) and val:
            name = val
            break
        if isinstance(val, dict) and val.get("companyName"):
            # some NSE endpoints nest company name under a "meta" object
            name = val["companyName"]
            break

    if symbol is None:
        return None
    return symbol, (name or symbol)


def fetch_equity_universe(index: str = "NIFTY 500") -> list[tuple[str, str]]:
    """
    Returns a list of (symbol, company_name) tuples for the
    constituents of `index`.
    """
    from nse import NSE
    from app.data_ingestion.nse_client import _CACHE_DIR

    with NSE(download_folder=_CACHE_DIR) as nse:
        raw = nse.listEquityStocksByIndex(index=index)
        # print(raw)  # uncomment to inspect the real response shape

        records = raw.get("data", raw) if isinstance(raw, dict) else raw
        if not isinstance(records, list):
            return []

        results = []
        for record in records:
            extracted = _extract_symbol_and_name(record)
            if extracted is not None:
                results.append(extracted)
        return results


if __name__ == "__main__":
    import sys
    idx = sys.argv[1] if len(sys.argv) > 1 else "NIFTY 500"
    universe = fetch_equity_universe(idx)
    print(f"Fetched {len(universe)} symbols from {idx}")
    for symbol, name in universe[:10]:
        print(f"  {symbol}: {name}")
