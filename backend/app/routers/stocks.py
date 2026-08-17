from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.stock_search import search_stocks
from app.schemas_search import StockSearchResultResponse

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/search", response_model=list[StockSearchResultResponse])
def search(
    q: str = Query(..., min_length=1, description="Symbol or company name, partial match OK"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Autocomplete/typeahead search over NSE symbols and company names.
    Searches the local `stocks` table only (never hits NSE/Yahoo live)
    — run `python -m scripts.ingest_equity_universe` first to populate
    it, or results will be limited to whatever symbols have already
    been looked up / added to a portfolio individually.
    """
    results = search_stocks(db, query=q, limit=limit)
    return [StockSearchResultResponse(symbol=r.symbol, name=r.name) for r in results]
