"""
Triggers fundamentals/shareholding ingestion automatically in the
background when a user encounters a stock that hasn't been ingested
yet — instead of requiring someone to run
`python -m scripts.ingest_fundamentals <SYMBOL>` from a terminal.

Design: return whatever data is already available immediately (a
FastAPI BackgroundTask runs AFTER the response is sent), and kick off
ingestion for next time. The user sees partial data (e.g. technical
score only) on first request, then full data on a later request/refresh
once ingestion has finished.

`_in_progress` is a plain in-process set, not a DB table — deliberately
simple for a personal-scale app. It resets on server restart (a
redundant ingestion might run once after a restart, which is harmless,
just a wasted API call) and only dedupes within a single process — fine
here, not fine if this were ever run with multiple worker processes,
in which case a DB-backed status table would be the correct upgrade.
"""
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.tables import Stock, Fundamental
from app.db import SessionLocal

_in_progress: set[str] = set()


def _run_ingestion(symbol: str) -> None:
    """
    Runs in the background, AFTER the triggering request's response
    has already been sent. Uses its own fresh DB session rather than
    reusing the request's — the request's session is closed by the
    `get_db` dependency's `finally` block once the response is sent,
    so reusing it here would fail.
    """
    from scripts.ingest_fundamentals import ingest_fundamentals_for, ingest_shareholding_for

    db = SessionLocal()
    try:
        ingest_fundamentals_for(db, symbol)
        ingest_shareholding_for(db, symbol)
        db.commit()
    except Exception as e:
        # A background ingestion failure shouldn't crash anything —
        # it just means this symbol stays un-ingested until the next
        # trigger. Logged so it's visible in server logs, not silent.
        print(f"[background ingestion] {symbol} failed: {e}")
    finally:
        db.close()
        _in_progress.discard(symbol)


def ensure_fundamentals_ingested(symbol: str, db: Session, background_tasks: BackgroundTasks) -> str:
    """
    Checks whether `symbol` already has fundamentals data. If not (and
    ingestion isn't already running for it in this process), schedules
    a background ingestion and returns a status string the API
    response can surface to the frontend:
        "available"    — already have data, nothing to do
        "in_progress"  — ingestion just kicked off (or already running)
        "not_started"  — ingestion couldn't be scheduled (shouldn't
                          normally happen; included for completeness)
    """
    stock = db.query(Stock).filter_by(symbol=symbol).first()
    if stock is not None:
        existing = db.query(Fundamental).filter_by(stock_id=stock.id).first()
        if existing is not None:
            return "available"

    if symbol in _in_progress:
        return "in_progress"

    _in_progress.add(symbol)
    background_tasks.add_task(_run_ingestion, symbol)
    return "in_progress"
