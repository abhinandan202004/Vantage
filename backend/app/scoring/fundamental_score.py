"""
Computes the 10-condition Fundamental Score from the checklist poster.

Takes a plain dict of already-computed fundamental figures rather than
raw financial statements — the assumption is a service layer upstream
has pulled the latest annual/TTM figures from the `fundamentals` and
`shareholding` tables and assembled them here. Keeping this function
pure (no DB/network access) makes it trivial to unit test.
"""
from dataclasses import dataclass, field


@dataclass
class FundamentalScoreResult:
    score: float  # 0-100
    breakdown: dict = field(default_factory=dict)


def compute_fundamental_score(fin: dict) -> FundamentalScoreResult:
    """
    Expected keys in `fin` (all optional — missing keys are skipped
    rather than scored as failing, same reasoning as the technical
    side):
        sales_cagr_pct, profit_cagr_pct, roe_pct, roce_pct,
        debt_to_equity, operating_cash_flow, promoter_holding_pct,
        fii_dii_trend ("increasing" | "decreasing" | "flat"),
        earnings_growth_trend ("accelerating" | "decelerating" | "flat"),
        peg_ratio
    """
    conditions = {}

    def check(key, present_key, cond_fn):
        val = fin.get(present_key)
        conditions[key] = cond_fn(val) if val is not None else None

    check("sales_cagr_above_15", "sales_cagr_pct", lambda v: v > 15)
    check("profit_cagr_above_15", "profit_cagr_pct", lambda v: v > 15)
    check("roe_above_18", "roe_pct", lambda v: v > 18)
    check("roce_above_20", "roce_pct", lambda v: v > 20)
    check("debt_equity_below_0_5", "debt_to_equity", lambda v: v < 0.50)
    check("positive_operating_cash_flow", "operating_cash_flow", lambda v: v > 0)
    check("promoter_holding_above_40", "promoter_holding_pct", lambda v: v > 40)
    check("fii_dii_increasing", "fii_dii_trend", lambda v: v == "increasing")
    check("earnings_growth_accelerating", "earnings_growth_trend", lambda v: v == "accelerating")
    check("peg_below_2", "peg_ratio", lambda v: v < 2)

    scorable = {k: v for k, v in conditions.items() if v is not None}
    score = (sum(1 for v in scorable.values() if v) / len(scorable)) * 100 if scorable else 0.0

    return FundamentalScoreResult(score=round(score, 1), breakdown=conditions)
