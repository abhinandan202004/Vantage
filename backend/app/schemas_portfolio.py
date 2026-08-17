from datetime import date
from pydantic import BaseModel


class HoldingCreate(BaseModel):
    symbol: str
    quantity: float
    buy_price: float | None = None
    buy_date: date | None = None
    notes: str | None = None


class HoldingResponse(BaseModel):
    id: int
    symbol: str
    quantity: float
    buy_price: float | None
    buy_date: date | None
    notes: str | None

    class Config:
        from_attributes = True
