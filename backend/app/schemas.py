from pydantic import BaseModel
from datetime import date


class OHLCVBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class ScoreBreakdown(BaseModel):
    score: float
    breakdown: dict


class SmartMoneyBreakdown(BaseModel):
    score: float
    interpretation: str
    max_possible: float
    breakdown: dict


class StockScoreResponse(BaseModel):
    symbol: str
    as_of_date: date
    technical: ScoreBreakdown
    fundamental: ScoreBreakdown
    smart_money: SmartMoneyBreakdown
