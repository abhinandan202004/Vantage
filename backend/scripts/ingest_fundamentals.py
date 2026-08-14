"""
Run to (re)populate the `fundamentals` and `shareholding` tables for
one or more symbols:

    python -m scripts.ingest_fundamentals RELIANCE TCS INFY

This is a manual/on-demand script for now — wrap it in APScheduler
(see README "Next steps") once you're ready for a nightly/quarterly
automated run. Fundamentals change slowly (quarterly), so there's no
need to run this often.
"""
import sys
from datetime import date, datetime

from app.db import SessionLocal
from app.models.tables import Stock, Fundamental, Shareholding
from app.data_ingestion.fundamentals_yf import fetch_fundamentals
from app.data_ingestion.nse_client import fetch_shareholding


def _get_or_create_stock(db, symbol: str) -> Stock:
    stock = db.query(Stock).filter_by(symbol=symbol).first()
    if stock is None:
        stock = Stock(symbol=symbol)
        db.add(stock)
        db.flush()  # assigns stock.id without committing yet
    return stock


def ingest_fundamentals_for(db, symbol: str) -> None:
    stock = _get_or_create_stock(db, symbol)

    try:
        snap = fetch_fundamentals(symbol)
    except Exception as e:
        print(f"  [fundamentals] {symbol}: FAILED — {e}")
        return

    if snap.period_end is None:
        print(f"  [fundamentals] {symbol}: no financial statement data returned, skipping")
        return

    period_end_date = date.fromisoformat(snap.period_end)

    existing = db.query(Fundamental).filter_by(
        stock_id=stock.id, period_end=period_end_date, period_type="annual"
    ).first()
    row = existing or Fundamental(stock_id=stock.id, period_end=period_end_date, period_type="annual")

    row.sales = snap.sales
    row.net_profit = snap.net_profit
    row.operating_cash_flow = snap.operating_cash_flow
    row.total_debt = snap.total_debt
    row.total_equity = snap.total_equity
    row.roe = snap.roe
    row.roce = snap.roce
    row.pe_ratio = snap.pe_ratio
    row.peg_ratio = snap.peg_ratio

    if not existing:
        db.add(row)
    print(f"  [fundamentals] {symbol}: OK (period_end={snap.period_end}, "
          f"ROE={snap.roe}, ROCE={snap.roce}, sales_cagr={snap.sales_cagr_pct}%)")


def ingest_shareholding_for(db, symbol: str) -> None:
    stock = _get_or_create_stock(db, symbol)

    try:
        raw = fetch_shareholding(symbol)
    except Exception as e:
        print(f"  [shareholding] {symbol}: FAILED — {e}")
        return

    # NSE's shareholding response shape varies by filing period and has
    # changed over the years — this parsing is a best-effort based on
    # the commonly-seen structure and WILL need adjustment once you can
    # inspect a live response. Run with a print(raw) here the first time
    # to see the actual shape before trusting this blindly.
    records = raw.get("data", []) if isinstance(raw, dict) else []
    if not records:
        print(f"  [shareholding] {symbol}: no records in response (check raw shape — API may have changed)")
        return

    for rec in records:
        try:
            period_end_date = datetime.strptime(rec["date"], "%d-%b-%Y").date()
        except (KeyError, ValueError):
            continue

        existing = db.query(Shareholding).filter_by(
            stock_id=stock.id, period_end=period_end_date
        ).first()
        row = existing or Shareholding(stock_id=stock.id, period_end=period_end_date)

        row.promoter_pct = rec.get("promoter")
        row.fii_pct = rec.get("fii")
        row.dii_pct = rec.get("dii")
        row.public_pct = rec.get("public")

        if not existing:
            db.add(row)

    print(f"  [shareholding] {symbol}: processed {len(records)} quarter(s)")


def main(symbols: list[str]) -> None:
    db = SessionLocal()
    try:
        for symbol in symbols:
            print(f"Ingesting {symbol}...")
            ingest_fundamentals_for(db, symbol)
            ingest_shareholding_for(db, symbol)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    syms = sys.argv[1:] or ["RELIANCE"]
    main(syms)
