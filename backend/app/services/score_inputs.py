"""
Bridges the DB (Fundamental/Shareholding rows, populated by
scripts/ingest_fundamentals.py) to the scoring functions' plain-dict
inputs. Kept separate from the router so it's testable without
spinning up FastAPI.
"""
from sqlalchemy.orm import Session

from app.models.tables import Stock, Fundamental, Shareholding
from app.scoring.shareholding_trends import compute_shareholding_trends


def get_fundamental_score_inputs(db: Session, symbol: str) -> dict:
    """
    Returns the dict compute_fundamental_score() expects, built from
    the most recent `fundamentals` row and shareholding trend for this
    symbol. Missing data (no ingestion run yet, or a field yfinance
    couldn't supply) comes through as a missing/None key, which the
    scoring function already treats as "not yet computed" rather than
    "failed" — see fundamental_score.py.
    """
    stock = db.query(Stock).filter_by(symbol=symbol).first()
    if stock is None:
        return {}

    latest_fund = (
        db.query(Fundamental)
        .filter_by(stock_id=stock.id)
        .order_by(Fundamental.period_end.desc())
        .first()
    )

    shareholding_rows = (
        db.query(Shareholding)
        .filter_by(stock_id=stock.id)
        .order_by(Shareholding.period_end.asc())
        .all()
    )
    quarters = [
        {"period_end": r.period_end, "promoter_pct": r.promoter_pct,
         "fii_pct": r.fii_pct, "dii_pct": r.dii_pct, "public_pct": r.public_pct}
        for r in shareholding_rows
    ]
    trends = compute_shareholding_trends(quarters)

    inputs = {}
    if latest_fund is not None:
        debt_to_equity = (
            latest_fund.total_debt / latest_fund.total_equity
            if latest_fund.total_debt is not None and latest_fund.total_equity
            else None
        )
        inputs.update({
            "roe_pct": latest_fund.roe,
            "roce_pct": latest_fund.roce,
            "debt_to_equity": debt_to_equity,
            "operating_cash_flow": latest_fund.operating_cash_flow,
            "peg_ratio": latest_fund.peg_ratio,
            "sales_cagr_pct": latest_fund.sales_cagr_pct,
            "profit_cagr_pct": latest_fund.profit_cagr_pct,
            "earnings_growth_trend": latest_fund.earnings_growth_trend,
        })

    inputs["promoter_holding_pct"] = trends.promoter_holding_pct
    if trends.fii_increasing is not None and trends.dii_increasing is not None:
        # "increasing" only if BOTH have data and both show a rising trend —
        # matches the checklist's combined "FII & DII increasing = Accumulation"
        # framing rather than treating them as independent conditions.
        inputs["fii_dii_trend"] = "increasing" if (trends.fii_increasing and trends.dii_increasing) else "flat"

    return inputs


def get_smart_money_signals(
    db: Session, symbol: str, technical_breakdown: dict, delivery_pct: float | None = None
) -> dict:
    """
    Returns the dict compute_smart_money_score() expects — combines
    shareholding-trend data from the DB with a couple of technical
    conditions already computed by the technical score (breakout +
    relative strength overlap between the two frameworks), plus a
    live delivery-percentage figure passed in by the caller (fetched
    fresh per request, same pattern as price/sector data — not cached
    in the DB since it's a daily, not quarterly, figure).
    """
    stock = db.query(Stock).filter_by(symbol=symbol).first()

    fii_increasing = dii_increasing = promoter_buying = None
    if stock is not None:
        shareholding_rows = (
            db.query(Shareholding)
            .filter_by(stock_id=stock.id)
            .order_by(Shareholding.period_end.asc())
            .all()
        )
        quarters = [
            {"period_end": r.period_end, "promoter_pct": r.promoter_pct,
             "fii_pct": r.fii_pct, "dii_pct": r.dii_pct, "public_pct": r.public_pct}
            for r in shareholding_rows
        ]
        trends = compute_shareholding_trends(quarters)
        fii_increasing = trends.fii_increasing
        dii_increasing = trends.dii_increasing
        promoter_buying = trends.promoter_buying

    latest_fund = None
    roce_above_20 = None
    low_debt = None
    earnings_growth = None
    if stock is not None:
        latest_fund = (
            db.query(Fundamental)
            .filter_by(stock_id=stock.id)
            .order_by(Fundamental.period_end.desc())
            .first()
        )
    if latest_fund is not None:
        roce_above_20 = latest_fund.roce > 20 if latest_fund.roce is not None else None
        if latest_fund.total_debt is not None and latest_fund.total_equity:
            low_debt = (latest_fund.total_debt / latest_fund.total_equity) < 0.5
        # Smart Money score's "Earnings Growth" factor is a plain
        # yes/no weight, unlike the Fundamental score's 3-way trend —
        # "accelerating" maps to True, "decelerating"/"flat" to False,
        # matching the checklist's framing of this as a positive
        # institutional-interest signal specifically when growth is
        # speeding up, not merely present.
        if latest_fund.earnings_growth_trend is not None:
            earnings_growth = latest_fund.earnings_growth_trend == "accelerating"

    # "High" delivery is a judgment call, not a fixed industry standard —
    # >60% is a commonly cited rule of thumb (vs. the market-wide NSE
    # average, which typically runs 40-50%) indicating investors are
    # taking actual delivery rather than same-day trading. Revisit this
    # threshold once you can compare against a stock's own historical
    # delivery-% average, which would be a more precise signal than a
    # fixed cutoff applied to every stock alike.
    HIGH_DELIVERY_THRESHOLD = 60.0
    high_delivery_volume = (delivery_pct > HIGH_DELIVERY_THRESHOLD) if delivery_pct is not None else None

    return {
        "fii_increasing": fii_increasing,
        "dii_increasing": dii_increasing,
        "promoter_buying": promoter_buying,
        "mutual_fund_buying": None,  # needs AMFI/paid data source — see README
        "high_delivery_volume": high_delivery_volume,
        "strong_relative_strength": technical_breakdown.get("sector_outperforming_nifty"),
        "breakout_with_volume": (
            technical_breakdown.get("breakout_above_resistance")
            and technical_breakdown.get("volume_above_150pct_avg")
        ) if technical_breakdown.get("breakout_above_resistance") is not None else None,
        "earnings_growth": earnings_growth,
        "roce_above_20": roce_above_20,
        "low_debt": low_debt,
    }
