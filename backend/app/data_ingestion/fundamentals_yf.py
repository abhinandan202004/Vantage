"""
Pulls fundamental figures for a symbol from yfinance's `.info` and
financial statement properties (`.financials`, `.balance_sheet`,
`.cashflow`), and derives the ratios the checklist needs.

IMPORTANT — coverage caveat (flagged in the original stack
recommendation): yfinance's fundamental data for NSE-listed stocks is
patchy compared to US tickers. Some fields (especially ROCE, which
Yahoo doesn't report directly) are computed here from raw statement
line items rather than pulled pre-computed, and may be None for
stocks with incomplete Yahoo coverage. Cross-check a handful of
results against screener.in manually before trusting this at scale —
I can't verify accuracy against real filings from this sandbox.
"""
from dataclasses import dataclass
import yfinance as yf

from app.data_ingestion.yfinance_client import _to_yahoo_symbol


@dataclass
class FundamentalSnapshot:
    period_end: str  # ISO date string of the most recent annual period
    sales: float | None = None
    net_profit: float | None = None
    operating_cash_flow: float | None = None
    total_debt: float | None = None
    total_equity: float | None = None
    roe: float | None = None
    roce: float | None = None
    pe_ratio: float | None = None
    peg_ratio: float | None = None
    sales_cagr_pct: float | None = None
    profit_cagr_pct: float | None = None
    debt_to_equity: float | None = None


def _cagr(oldest: float, newest: float, years: float) -> float | None:
    """% CAGR between two values `years` apart. None if inputs are unusable
    (non-positive base, zero years, etc.) rather than raising — this is a
    background job over many symbols and one bad statement shouldn't crash it."""
    if oldest is None or newest is None or oldest <= 0 or years <= 0:
        return None
    return round((((newest / oldest) ** (1 / years)) - 1) * 100, 2)


def fetch_fundamentals(symbol: str) -> FundamentalSnapshot:
    """
    Returns a FundamentalSnapshot for the given NSE symbol (bare, e.g.
    "RELIANCE" — the .NS suffix is added internally).
    """
    yahoo_symbol = _to_yahoo_symbol(symbol)
    ticker = yf.Ticker(yahoo_symbol)

    info = ticker.info or {}
    financials = ticker.financials  # annual income statement, columns = periods (most recent first)
    balance_sheet = ticker.balance_sheet
    cashflow = ticker.cashflow

    period_end = str(financials.columns[0].date()) if not financials.empty else None

    def _row(df, *possible_labels):
        """Return the first matching row (as a Series) from a statement
        DataFrame — yfinance's exact label names shift between versions/
        tickers, so try a few known variants."""
        for label in possible_labels:
            if label in df.index:
                return df.loc[label]
        return None

    sales_row = _row(financials, "Total Revenue", "TotalRevenue")
    profit_row = _row(financials, "Net Income", "NetIncome")
    ocf_row = _row(cashflow, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    debt_row = _row(balance_sheet, "Total Debt", "TotalDebt")
    equity_row = _row(balance_sheet, "Stockholders Equity", "Common Stock Equity")
    ebit_row = _row(financials, "EBIT")
    total_assets_row = _row(balance_sheet, "Total Assets")
    current_liab_row = _row(balance_sheet, "Current Liabilities")

    sales_latest = sales_row.iloc[0] if sales_row is not None and len(sales_row) > 0 else None
    sales_oldest = sales_row.iloc[-1] if sales_row is not None and len(sales_row) > 1 else None
    profit_latest = profit_row.iloc[0] if profit_row is not None and len(profit_row) > 0 else None
    profit_oldest = profit_row.iloc[-1] if profit_row is not None and len(profit_row) > 1 else None
    ocf_latest = ocf_row.iloc[0] if ocf_row is not None and len(ocf_row) > 0 else None
    debt_latest = debt_row.iloc[0] if debt_row is not None and len(debt_row) > 0 else None
    equity_latest = equity_row.iloc[0] if equity_row is not None and len(equity_row) > 0 else None
    ebit_latest = ebit_row.iloc[0] if ebit_row is not None and len(ebit_row) > 0 else None
    total_assets_latest = total_assets_row.iloc[0] if total_assets_row is not None and len(total_assets_row) > 0 else None
    current_liab_latest = current_liab_row.iloc[0] if current_liab_row is not None and len(current_liab_row) > 0 else None

    years_span = (len(sales_row) - 1) if sales_row is not None else 0

    roe = round((profit_latest / equity_latest) * 100, 2) if profit_latest and equity_latest else None

    # ROCE = EBIT / Capital Employed, where Capital Employed = Total Assets - Current Liabilities.
    # Falls back to None if either statement line is missing rather than guessing.
    roce = None
    if ebit_latest and total_assets_latest and current_liab_latest:
        capital_employed = total_assets_latest - current_liab_latest
        if capital_employed:
            roce = round((ebit_latest / capital_employed) * 100, 2)

    debt_to_equity = round(debt_latest / equity_latest, 2) if debt_latest and equity_latest else None

    return FundamentalSnapshot(
        period_end=period_end,
        sales=sales_latest,
        net_profit=profit_latest,
        operating_cash_flow=ocf_latest,
        total_debt=debt_latest,
        total_equity=equity_latest,
        roe=roe,
        roce=roce,
        pe_ratio=info.get("trailingPE"),
        peg_ratio=info.get("pegRatio") or info.get("trailingPegRatio"),
        sales_cagr_pct=_cagr(sales_oldest, sales_latest, years_span),
        profit_cagr_pct=_cagr(profit_oldest, profit_latest, years_span),
        debt_to_equity=debt_to_equity,
    )


if __name__ == "__main__":
    import sys
    from dataclasses import asdict
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    snap = fetch_fundamentals(sym)
    for k, v in asdict(snap).items():
        print(f"{k}: {v}")
