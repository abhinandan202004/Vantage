"""
Computes the 10-condition Technical Score from the checklist poster.

Each condition contributes 10 points if met, 0 if not (simple equal
weighting to start — once you've backtested this against real
outcomes, revisit the weights; RSI/ADX/volume probably deserve more
nuance than a flat pass/fail).

`sector_return` and `nifty_return` are passed in separately since they
require a second symbol's OHLCV (the sector index) — the caller
(a router/service layer) is responsible for fetching that.
"""
from dataclasses import dataclass, field
import pandas as pd

from app.indicators.technical import add_indicators, find_resistance, is_tight_consolidation


@dataclass
class TechnicalScoreResult:
    score: float  # 0-100
    breakdown: dict = field(default_factory=dict)


def compute_technical_score(
    df: pd.DataFrame,
    sector_return: float | None = None,
    nifty_return: float | None = None,
) -> TechnicalScoreResult:
    """
    df: raw OHLCV DataFrame (as returned by yfinance_client.fetch_ohlcv),
        needs at least 200 rows for the 200 EMA to be meaningful.
    sector_return / nifty_return: % returns over the same lookback
        window, used for the "sector outperforming Nifty" condition.
        If either is None, that condition is skipped (not scored
        against the total — see note below).
    """
    ind = add_indicators(df)
    latest = ind.iloc[-1]

    conditions = {}

    conditions["price_above_20ema"] = bool(latest["close"] > latest["ema20"])
    conditions["ema20_above_ema50"] = bool(latest["ema20"] > latest["ema50"])
    conditions["ema50_above_ema200"] = bool(latest["ema50"] > latest["ema200"])
    conditions["rsi_above_55"] = bool(latest["rsi14"] > 55)
    conditions["adx_above_25"] = bool(latest["adx14"] > 25)
    conditions["volume_above_150pct_avg"] = bool(latest["vol_ratio"] > 1.5)

    resistance = find_resistance(ind)
    conditions["breakout_above_resistance"] = bool(
        resistance is not None and latest["close"] > resistance
    )

    conditions["tight_consolidation"] = bool(is_tight_consolidation(ind))

    # "No nearby overhead supply" needs a volume-profile calculation —
    # not implemented yet. Flagging as None (excluded from scoring)
    # rather than silently scoring it False, so it's visible in the UI
    # as "not yet computed" vs. "failed".
    conditions["no_overhead_supply"] = None

    if sector_return is not None and nifty_return is not None:
        conditions["sector_outperforming_nifty"] = bool(sector_return > nifty_return)
    else:
        conditions["sector_outperforming_nifty"] = None

    scorable = {k: v for k, v in conditions.items() if v is not None}
    score = (sum(1 for v in scorable.values() if v) / len(scorable)) * 100 if scorable else 0.0

    return TechnicalScoreResult(score=round(score, 1), breakdown=conditions)
