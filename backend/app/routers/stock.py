from datetime import date
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.data_ingestion.yfinance_client import fetch_ohlcv
from app.services.stock_summary import compute_full_score
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
def get_score(symbol: str, db: Session = Depends(get_db)):
    """
    Returns technical + fundamental + smart money scores for a symbol.

    Fundamental and smart-money figures come from the DB
    (`fundamentals` / `shareholding` tables) — run
    `python -m scripts.ingest_fundamentals <SYMBOL>` first, or these
    will still come back mostly None/placeholder for symbols that
    haven't been ingested yet (which is expected, not a bug).
    """
    try:
        result = compute_full_score(symbol, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return StockScoreResponse(
        symbol=symbol,
        as_of_date=date.today(),
        technical=ScoreBreakdown(score=result.technical.score, breakdown=result.technical.breakdown),
        fundamental=ScoreBreakdown(score=result.fundamental.score, breakdown=result.fundamental.breakdown),
        smart_money=SmartMoneyBreakdown(
            score=result.smart_money.score, interpretation=result.smart_money.interpretation,
            max_possible=result.smart_money.max_possible, breakdown=result.smart_money.breakdown,
        ),
    )
