"""
Computes the "Smart Money Score" (0-100) from the Smart Money Trail
checklist — a THIRD independent axis alongside Technical and
Fundamental scores. Unlike those two (flat 10-points-per-condition),
this one is weighted: each factor contributes its own point value
toward a max of 100, per the poster's weight table.

Weights (from the poster):
    FII Increasing            15
    DII Increasing            10
    Promoter Buying           15
    Mutual Fund Buying        10
    High Delivery Volume      10
    Strong Relative Strength  10
    Breakout with Volume      10
    Earnings Growth           10
    ROCE > 20%                 5
    Low Debt                   5
    -----------------------------
    TOTAL MAX                100

Same "missing data excluded, not scored as failing" philosophy as the
technical/fundamental modules: if a factor can't be determined yet,
its weight is dropped from both the numerator and the denominator
rather than counted against the stock.
"""
from dataclasses import dataclass, field

# (breakdown_key, input_key, weight)
FACTOR_WEIGHTS = [
    ("fii_increasing", "fii_increasing", 15),
    ("dii_increasing", "dii_increasing", 10),
    ("promoter_buying", "promoter_buying", 15),
    ("mutual_fund_buying", "mutual_fund_buying", 10),
    ("high_delivery_volume", "high_delivery_volume", 10),
    ("strong_relative_strength", "strong_relative_strength", 10),
    ("breakout_with_volume", "breakout_with_volume", 10),
    ("earnings_growth", "earnings_growth", 10),
    ("roce_above_20", "roce_above_20", 5),
    ("low_debt", "low_debt", 5),
]

SCORE_BANDS = [
    (85, 100, "Strong institutional accumulation"),
    (70, 84, "Positive smart money signals"),
    (50, 69, "Mixed signals; monitor closely"),
    (0, 49, "Limited evidence of institutional accumulation"),
]


@dataclass
class SmartMoneyScoreResult:
    score: float  # 0-100, weighted
    interpretation: str
    breakdown: dict = field(default_factory=dict)
    max_possible: float = 100.0  # < 100 when some factors are undetermined


def _interpret(score: float) -> str:
    for low, high, label in SCORE_BANDS:
        if low <= score <= high:
            return label
    return "Unknown"


def compute_smart_money_score(signals: dict) -> SmartMoneyScoreResult:
    """
    `signals`: dict mapping each factor's breakdown key (see
    FACTOR_WEIGHTS above) to True / False / None.
        True  -> factor confirmed present (e.g. FII stake rose 2-4
                 consecutive quarters, promoters bought in the open
                 market, stock broke out on above-average volume)
        False -> factor checked and did not hold
        None  -> not yet computed / data unavailable (excluded from
                 scoring rather than penalized)

    Each factor is a simplification of a richer real-world check —
    e.g. "fii_increasing" ideally reflects 2-4 consecutive quarters of
    rising FII holding (per the poster), not just quarter-over-quarter.
    The caller (a future shareholding-trend service) is responsible for
    turning raw shareholding history into that boolean.
    """
    breakdown = {}
    earned = 0.0
    possible = 0.0

    for key, input_key, weight in FACTOR_WEIGHTS:
        val = signals.get(input_key)
        breakdown[key] = val
        if val is None:
            continue
        possible += weight
        if val:
            earned += weight

    if possible == 0:
        return SmartMoneyScoreResult(score=0.0, interpretation="Unknown", breakdown=breakdown, max_possible=0.0)

    # Scale to a 0-100 score based on what was actually determinable,
    # so a stock with 4 unknown factors isn't unfairly capped below 100.
    scaled_score = round((earned / possible) * 100, 1)

    return SmartMoneyScoreResult(
        score=scaled_score,
        interpretation=_interpret(scaled_score),
        breakdown=breakdown,
        max_possible=possible,
    )
