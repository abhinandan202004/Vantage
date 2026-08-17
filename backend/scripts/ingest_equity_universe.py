"""
Run to (re)populate the `stocks` table with symbol + company name for
NSE's most liquid stocks, powering the search/autocomplete endpoint:

    python -m scripts.ingest_equity_universe

Safe to re-run — upserts by symbol (updates the name if the symbol
already exists, e.g. from a prior portfolio addition, rather than
creating a duplicate). Company names change rarely, so this doesn't
need to run often — monthly is plenty.
"""
from app.db import SessionLocal
from app.models.tables import Stock
from app.data_ingestion.equity_universe import fetch_equity_universe


def ingest_equity_universe(index: str = "NIFTY 500") -> None:
    db = SessionLocal()
    try:
        universe = fetch_equity_universe(index)
        print(f"Fetched {len(universe)} symbols from {index}")

        created, updated = 0, 0
        for symbol, name in universe:
            stock = db.query(Stock).filter_by(symbol=symbol).first()
            if stock is None:
                db.add(Stock(symbol=symbol, name=name))
                created += 1
            elif stock.name != name:
                stock.name = name
                updated += 1

        db.commit()
        print(f"Done: {created} new symbols, {updated} names updated.")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    idx = sys.argv[1] if len(sys.argv) > 1 else "NIFTY 500"
    ingest_equity_universe(idx)
