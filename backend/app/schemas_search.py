from pydantic import BaseModel


class StockSearchResultResponse(BaseModel):
    symbol: str
    name: str | None
