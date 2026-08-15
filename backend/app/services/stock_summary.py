"""
Computes the full technical + fundamental + smart money score for a
symbol — the core logic behind /stock/{symbol}/score. Pulled out into
its own function (rather than living only in the router) so the
chatbot's tools can call the exact same code path instead of
duplicating this logic or making an HTTP round-trip to itself.
"""
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.data_ingestion.yfinance_client import fetch_ohlcv
from app.data_ingestion.sector_mapping import get_sector_index_ticker
from app.data_ingestion.nse_client import fetch_delivery_pct
from app.scoring.technical_score import compute_technical_score, TechnicalScoreResult
from app.scoring.fundamental_score import compute_fundamental_score, FundamentalScoreResult
from app.scoring.smart_money_score import compute_smart_money_score, SmartMoneyScoreResult
from app.services.score_inputs import get_fundamental_score_inputs, get_smart_money_signals
from app.config import settings


@dataclass
class FullScoreResult:
    symbol: str
    technical: TechnicalScoreResult
    fundamental: FundamentalScoreResult
    smart_money: SmartMoneyScoreResult


def compute_full_score(symbol: str, db: Session) -> FullScoreResult:
    """
    Raises ValueError if OHLCV data can't be fetched for `symbol`
    (bad symbol, delisted, etc.) — same contract as fetch_ohlcv, so
    callers (HTTP route or chat tool) can handle it consistently.
    """
    df = fetch_ohlcv(symbol, lookback_days=settings.default_lookback_days)

    try:
        nifty_df = fetch_ohlcv(settings.nifty_symbol, lookback_days=30)
        nifty_return = (nifty_df["close"].iloc[-1] / nifty_df["close"].iloc[0] - 1) * 100
    except ValueError:
        nifty_return = None

    sector_return = None
    sector_ticker = get_sector_index_ticker(symbol)
    if sector_ticker is not None:
        try:
            sector_df = fetch_ohlcv(sector_ticker, lookback_days=30)
            sector_return = (sector_df["close"].iloc[-1] / sector_df["close"].iloc[0] - 1) * 100
        except ValueError:
            sector_return = None

    tech = compute_technical_score(df, sector_return=sector_return, nifty_return=nifty_return)

    fundamental_inputs = get_fundamental_score_inputs(db, symbol)
    fund = compute_fundamental_score(fundamental_inputs)

    try:
        delivery_pct = fetch_delivery_pct(symbol)
    except Exception:
        delivery_pct = None

    smart_money_signals = get_smart_money_signals(db, symbol, tech.breakdown, delivery_pct=delivery_pct)
    smart = compute_smart_money_score(smart_money_signals)

    return FullScoreResult(symbol=symbol, technical=tech, fundamental=fund, smart_money=smart)
