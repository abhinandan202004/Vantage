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
        records = fetch_shareholding(symbol)
    except Exception as e:
        print(f"  [shareholding] {symbol}: FAILED — {e}")
        return

    if not records:
        print(f"  [shareholding] {symbol}: no records returned")
        return

    for rec in records:
        try:
            # nse library's documented date format: "31-DEC-2025"
            period_end_date = datetime.strptime(rec["date"], "%d-%b-%Y").date()
        except (KeyError, ValueError):
            continue

        existing = db.query(Shareholding).filter_by(
            stock_id=stock.id, period_end=period_end_date
        ).first()
        row = existing or Shareholding(stock_id=stock.id, period_end=period_end_date)

        def _to_float(val):
            try:
                return float(val) if val not in (None, "", "-") else None
            except ValueError:
                return None

        row.promoter_pct = _to_float(rec.get("pr_and_prgrp"))
        row.public_pct = _to_float(rec.get("public_val"))
        # NSE's shareholding-pattern endpoint reports Promoter vs Public
        # only — it does NOT break Public down into FII/DII at the
        # per-stock level (confirmed from the nse library's documented
        # sample response). Leaving these None (not guessed/zeroed) is
        # correct — the scoring functions already treat None as
        # "not yet computed" rather than "failed". A real per-stock
        # FII/DII split would need a different data source (full XBRL
        # filing, or a paid provider) — see README.
        row.fii_pct = None
        row.dii_pct = None

        if not existing:
            db.add(row)

    print(f"  [shareholding] {symbol}: processed {len(records)} quarter(s) "
          f"(promoter/public only — no FII/DII split available from this endpoint)")


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
