from datetime import date
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.data_ingestion.yfinance_client import fetch_ohlcv
from app.scoring.technical_score import compute_technical_score
from app.scoring.fundamental_score import compute_fundamental_score
from app.scoring.smart_money_score import compute_smart_money_score
from app.services.score_inputs import get_fundamental_score_inputs, get_smart_money_signals
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

    Fundamental and smart-money figures now come from the DB
    (`fundamentals` / `shareholding` tables) — run
    `python -m scripts.ingest_fundamentals <SYMBOL>` first, or these
    will still come back mostly None/placeholder for symbols that
    haven't been ingested yet (which is expected, not a bug).
    """
    try:
        df = fetch_ohlcv(symbol, lookback_days=settings.default_lookback_days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        nifty_df = fetch_ohlcv(settings.nifty_symbol, lookback_days=30)
        nifty_return = (nifty_df["close"].iloc[-1] / nifty_df["close"].iloc[0] - 1) * 100
        sector_return = None  # requires stock -> sector index mapping (see Stock.sector_index_symbol)
    except ValueError:
        nifty_return = None
        sector_return = None

    tech = compute_technical_score(df, sector_return=sector_return, nifty_return=nifty_return)

    fundamental_inputs = get_fundamental_score_inputs(db, symbol)
    fund = compute_fundamental_score(fundamental_inputs)

    smart_money_signals = get_smart_money_signals(db, symbol, tech.breakdown)
    smart = compute_smart_money_score(smart_money_signals)

    return StockScoreResponse(
        symbol=symbol,
        as_of_date=date.today(),
        technical=ScoreBreakdown(score=tech.score, breakdown=tech.breakdown),
        fundamental=ScoreBreakdown(score=fund.score, breakdown=fund.breakdown),
        smart_money=SmartMoneyBreakdown(
            score=smart.score, interpretation=smart.interpretation,
            max_possible=smart.max_possible, breakdown=smart.breakdown,
        ),
    )
