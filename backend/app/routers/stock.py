from datetime import date
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.data_ingestion.yfinance_client import fetch_ohlcv
from app.services.stock_summary import compute_full_score
from app.services.ingestion_trigger import ensure_fundamentals_ingested
from app.schemas import OHLCVBar, StockScoreResponse, ScoreBreakdown, SmartMoneyBreakdown
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/{symbol}/ohlcv", response_model=list[OHLCVBar])
def get_ohlcv(symbol: str, lookback_days: int = settings.default_lookback_days):
    """
    Returns daily OHLCV bars for a symbol — feeds the candlestick chart
    directly on the frontend (lightweight-charts expects this shape).
    """
    try:
        df = fetch_ohlcv(symbol, lookback_days=lookback_days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return [
        OHLCVBar(date=idx, open=row.open, high=row.high, low=row.low,
                 close=row.close, volume=int(row.volume))
        for idx, row in df.iterrows()
    ]


@router.get("/{symbol}/score", response_model=StockScoreResponse)
def get_score(symbol: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Returns technical + fundamental + smart money scores for a symbol.

    If this symbol has never had fundamentals/shareholding data
    ingested, this endpoint automatically schedules that ingestion in
    the background (see app/services/ingestion_trigger.py) and
    returns immediately with whatever's available right now — the
    technical score is always live, but fundamental/smart_money will
    be mostly null on this first request. `fundamentals_status` in
    the response tells the frontend whether to show a "still
    loading fundamentals" indicator and poll again shortly.
    """
    try:
        result = compute_full_score(symbol, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    fundamentals_status = ensure_fundamentals_ingested(symbol, db, background_tasks)

    return StockScoreResponse(
        symbol=symbol,
        as_of_date=date.today(),
        technical=ScoreBreakdown(score=result.technical.score, breakdown=result.technical.breakdown),
        fundamental=ScoreBreakdown(score=result.fundamental.score, breakdown=result.fundamental.breakdown),
        smart_money=SmartMoneyBreakdown(
            score=result.smart_money.score, interpretation=result.smart_money.interpretation,
            max_possible=result.smart_money.max_possible, breakdown=result.smart_money.breakdown,
        ),
        fundamentals_status=fundamentals_status,
    )
