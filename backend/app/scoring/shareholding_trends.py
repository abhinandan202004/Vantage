"""
Turns a sequence of quarterly shareholding snapshots (from the
`Shareholding` DB table — populated by nse_client.fetch_shareholding,
see scripts/ingest_shareholding.py) into the boolean/trend signals the
Fundamental and Smart Money scores need.

Kept as a pure function over a list of dicts (not the ORM model
directly) so it's trivially unit-testable without a DB.
"""
from dataclasses import dataclass


@dataclass
class ShareholdingTrends:
    fii_increasing: bool | None
    dii_increasing: bool | None
    promoter_buying: bool | None
    promoter_holding_pct: float | None


def _is_rising(values: list[float], min_quarters: int = 2) -> bool | None:
    """
    True if `values` (oldest -> newest) shows a non-decreasing trend
    across at least `min_quarters` consecutive quarters, per the
    poster's "2-4 consecutive quarters increase" rule. None if there
    isn't enough history to judge yet.
    """
    if len(values) < min_quarters:
        return None
    recent = values[-min_quarters:]
    return all(b >= a for a, b in zip(recent, recent[1:])) and recent[-1] > recent[0]


def compute_shareholding_trends(quarters: list[dict], min_quarters: int = 2) -> ShareholdingTrends:
    """
    `quarters`: list of dicts sorted OLDEST -> NEWEST, each with keys
    matching the Shareholding model: period_end, promoter_pct,
    fii_pct, dii_pct, public_pct. Missing keys/values are tolerated —
    trends for fields with insufficient data come back as None.
    """
    if not quarters:
        return ShareholdingTrends(None, None, None, None)

    fii_series = [q["fii_pct"] for q in quarters if q.get("fii_pct") is not None]
    dii_series = [q["dii_pct"] for q in quarters if q.get("dii_pct") is not None]
    promoter_series = [q["promoter_pct"] for q in quarters if q.get("promoter_pct") is not None]

    return ShareholdingTrends(
        fii_increasing=_is_rising(fii_series, min_quarters),
        dii_increasing=_is_rising(dii_series, min_quarters),
        promoter_buying=_is_rising(promoter_series, min_quarters),
        promoter_holding_pct=promoter_series[-1] if promoter_series else None,
    )
